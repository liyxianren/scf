"""API endpoints for the AI scheduling agent."""
import json
import queue
import threading

from flask import request, jsonify, Response, stream_with_context, current_app
from flask_login import current_user, login_required

from extensions import db
from modules.oa import oa_bp
from modules.oa.models import CourseSchedule, OATodo
from modules.oa.agent.agent import ScheduleAgent


@oa_bp.route('/api/schedule-agent/chat', methods=['POST'])
@login_required
def schedule_agent_chat():
    """Main chat endpoint. Runs the agent loop and streams NDJSON events.

    Request body:
        {"message": "...", "history": [...]}

    Response: NDJSON stream with events:
        {"type": "thinking", "data": "..."}
        {"type": "tool_call", "data": {"name": "...", "args": {...}}}
        {"type": "response", "content": "...", "proposal": {...}|null, "messages": [...]}
        {"type": "error", "content": "..."}
    """
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    history = data.get('history') or []

    if not user_message:
        return jsonify({'error': '请输入消息'}), 400

    # Build messages list
    messages = list(history)
    messages.append({"role": "user", "content": user_message})

    def generate():
        q = queue.Queue()

        def on_event(event_type, evt_data):
            q.put({"type": event_type, "data": evt_data})

        app = current_app._get_current_object()

        def run_agent():
            with app.app_context():
                try:
                    agent = ScheduleAgent()
                    result = agent.run(messages, on_event=on_event)
                    q.put({
                        "type": "response",
                        "content": result["response"],
                        "proposal": result.get("proposal"),
                        "messages": result["messages"],
                    })
                except Exception as e:
                    q.put({"type": "error", "content": str(e)})
                finally:
                    q.put(None)  # sentinel

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()

        while True:
            try:
                item = q.get(timeout=180)
            except queue.Empty:
                yield json.dumps({"type": "error", "content": "请求超时"}, ensure_ascii=False) + "\n"
                break
            if item is None:
                break
            yield json.dumps(item, ensure_ascii=False, default=str) + "\n"

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Content-Type': 'application/x-ndjson',
    }
    return Response(stream_with_context(generate()), headers=headers)


@oa_bp.route('/api/schedule-agent/confirm', methods=['POST'])
@login_required
def schedule_agent_confirm():
    """Execute a confirmed proposal (create / delete / update).

    Request body: the proposal object returned by the chat endpoint.
    """
    data = request.get_json(silent=True) or {}
    action = data.get('action')

    if action == 'create':
        return _confirm_create(data)
    elif action == 'delete':
        return _confirm_delete(data)
    elif action == 'update':
        return _confirm_update(data)
    elif action == 'create_todos':
        return _confirm_create_todos(data)
    elif action == 'delete_todos':
        return _confirm_delete_todos(data)
    elif action == 'update_todos':
        return _confirm_update_todos(data)
    else:
        return jsonify({'success': False, 'error': f'未知操作: {action}'}), 400


# ------------------------------------------------------------------
# Confirm handlers
# ------------------------------------------------------------------

def _confirm_create(data):
    from modules.auth.services import sync_enrollment_status, sync_schedule_student_snapshot
    from modules.auth.workflow_services import ensure_schedule_feedback_todo
    from modules.oa import schedule_actions
    from modules.oa.services import build_schedule_delivery_fields

    schedules = data.get('schedules', [])
    if not schedules:
        return jsonify({'success': False, 'error': '没有要创建的课程'}), 400

    created = 0
    errors = []
    for s in schedules:
        try:
            from datetime import date as date_type
            d = date_type.fromisoformat(s['date'])
            teacher_user, error = schedule_actions.resolve_teacher_or_error(s.get('teacher', ''))
            if error:
                errors.append({'date': s.get('date'), 'error': error})
                continue
            conflict_error = schedule_actions.validate_schedule_conflicts_or_error(
                course_date=d,
                time_start=s['time_start'],
                time_end=s['time_end'],
                teacher_id=teacher_user.id,
                enrollment_id=s.get('enrollment_id'),
            )
            if conflict_error:
                errors.append({'date': s.get('date'), 'error': conflict_error})
                continue
            course = CourseSchedule(
                date=d,
                day_of_week=d.weekday(),
                time_start=s['time_start'],
                time_end=s['time_end'],
                teacher=teacher_user.display_name,
                teacher_id=teacher_user.id,
                course_name=s.get('course_name', ''),
                enrollment_id=s.get('enrollment_id'),
                students=s.get('students', ''),
                location=s.get('location', ''),
                notes=s.get('notes', ''),
                **build_schedule_delivery_fields(
                    delivery_mode=s.get('delivery_mode'),
                    color_tag=s.get('color_tag'),
                    fallback_delivery_mode='online',
                    allow_unknown=False,
                ),
            )
            db.session.add(course)
            db.session.flush()
            sync_schedule_student_snapshot(course, enrollment=course.enrollment, preserve_history=False)
            ensure_schedule_feedback_todo(course, created_by=getattr(current_user, 'id', None))
            if course.enrollment:
                sync_enrollment_status(course.enrollment)
            created += 1
        except Exception as exc:
            errors.append({'date': s.get('date'), 'error': str(exc)})
            continue

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'已成功创建 {created} 节课程',
        'affected_count': created,
        'errors': errors,
    })


def _confirm_delete(data):
    ids = data.get('schedule_ids', [])
    if not ids:
        return jsonify({'success': False, 'error': '没有要删除的课程'}), 400

    from modules.oa import schedule_actions

    cancelled = 0
    errors = []
    for schedule in CourseSchedule.query.filter(CourseSchedule.id.in_(ids)).all():
        _, error = schedule_actions.cancel_schedule(
            schedule,
            actor=current_user,
            reason=(data.get('summary') or '').strip() or '通过 AI 助手取消课次',
        )
        if error:
            errors.append({'id': schedule.id, 'error': error[0]})
            continue
        cancelled += 1
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'已成功取消 {cancelled} 节课程',
        'affected_count': cancelled,
        'errors': errors,
    })


def _confirm_update(data):
    from modules.oa import schedule_actions

    updates = data.get('updates', [])
    if not updates:
        return jsonify({'success': False, 'error': '没有要修改的课程'}), 400

    updated = 0
    errors = []
    for upd in updates:
        course = CourseSchedule.query.get(upd.get('schedule_id'))
        if not course:
            continue

        payload = {
            'date': upd.get('new_date'),
            'time_start': upd.get('new_time_start'),
            'time_end': upd.get('new_time_end'),
            'teacher': upd.get('new_teacher'),
            'course_name': upd.get('new_course_name'),
            'students': upd.get('new_students'),
            'location': upd.get('new_location'),
            'delivery_mode': upd.get('new_delivery_mode') or upd.get('delivery_mode'),
            'color_tag': upd.get('new_color_tag'),
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        result = schedule_actions.apply_schedule_update(
            course,
            payload,
            allow_admin_override=True,
        )
        if not result.get('success'):
            errors.append({
                'id': course.id,
                'error': result.get('error') or '修改失败',
            })
            continue
        updated += 1

    return jsonify({
        'success': True,
        'message': f'已成功修改 {updated} 节课程',
        'affected_count': updated,
        'errors': errors,
    })


# ------------------------------------------------------------------
# Todo confirm handlers
# ------------------------------------------------------------------

def _confirm_create_todos(data):
    todos = data.get('todos', [])
    if not todos:
        return jsonify({'success': False, 'error': '没有要创建的待办'}), 400

    from datetime import date as date_type
    created = 0
    for t in todos:
        try:
            due_date = None
            if t.get('due_date'):
                due_date = date_type.fromisoformat(t['due_date'])

            people = t.get('responsible_people', [])
            responsible_person = ', '.join(people) if isinstance(people, list) else str(people or '')

            todo = OATodo(
                title=t.get('title', ''),
                description=t.get('description', ''),
                responsible_person=responsible_person,
                is_completed=False,
                due_date=due_date,
                priority=t.get('priority', 2),
                notes=t.get('notes', ''),
            )
            db.session.add(todo)
            created += 1
        except Exception:
            continue

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'已成功创建 {created} 条待办',
        'affected_count': created,
    })


def _confirm_delete_todos(data):
    ids = data.get('todo_ids', [])
    if not ids:
        return jsonify({'success': False, 'error': '没有要删除的待办'}), 400

    deleted = OATodo.query.filter(OATodo.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'已成功删除 {deleted} 条待办',
        'affected_count': deleted,
    })


def _confirm_update_todos(data):
    updates = data.get('updates', [])
    if not updates:
        return jsonify({'success': False, 'error': '没有要修改的待办'}), 400

    from datetime import date as date_type
    updated = 0
    for upd in updates:
        todo = OATodo.query.get(upd.get('todo_id'))
        if not todo:
            continue

        field_map = {
            'new_title': 'title',
            'new_description': 'description',
            'new_due_date': 'due_date',
            'new_priority': 'priority',
            'new_notes': 'notes',
        }
        for src, dst in field_map.items():
            if src in upd and upd[src] is not None:
                val = upd[src]
                if dst == 'due_date':
                    val = date_type.fromisoformat(val) if val else None
                setattr(todo, dst, val)

        if 'new_responsible_people' in upd and upd['new_responsible_people'] is not None:
            people = upd['new_responsible_people']
            todo.responsible_person = ', '.join(people) if isinstance(people, list) else str(people)

        if upd.get('toggle_completion'):
            todo.is_completed = not todo.is_completed

        updated += 1

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'已成功修改 {updated} 条待办',
        'affected_count': updated,
    })
