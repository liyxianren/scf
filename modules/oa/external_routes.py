"""External OA API routes."""
from calendar import monthrange
from datetime import date, datetime, timedelta

from flask import request
from sqlalchemy import func

from extensions import db
from modules.auth.models import Enrollment, LeaveRequest, User
from modules.auth.services import (
    get_course_feedback_skip_reason,
    schedule_requires_course_feedback,
    sync_enrollment_status,
    sync_schedule_student_snapshot,
)
from modules.oa import oa_bp
from modules.oa import schedule_actions
from modules.oa.external_api import external_api_required, external_error, external_success
from modules.oa.models import CourseFeedback, CourseSchedule, OATodo, ScheduleMeetingMaterial
from modules.oa.services import (
    apply_schedule_excel_import,
    build_schedule_delivery_fields,
    resolve_schedule_teacher_reference,
)


def _get_json_payload():
    data = request.get_json(silent=True)
    if not data:
        return None, external_error('请提供 JSON 数据')
    return data, None


def _filter_visible_todos(todos, *, reconcile_feedback_visibility=False):
    visible = []
    changed = False
    for todo in todos:
        if todo.is_workflow:
            from modules.auth.workflow_services import reconcile_stale_workflow_todo, workflow_todo_stale_reason

            if reconcile_stale_workflow_todo(todo):
                changed = True
            if workflow_todo_stale_reason(todo):
                continue
            if todo.is_completed or todo.workflow_status in {
                OATodo.WORKFLOW_STATUS_COMPLETED,
                OATodo.WORKFLOW_STATUS_CANCELLED,
            }:
                continue
        if (
            todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK
            and not schedule_requires_course_feedback(getattr(todo, 'schedule', None))
        ):
            if reconcile_feedback_visibility and not todo.is_completed:
                from modules.auth.workflow_services import cancel_schedule_feedback_todo

                cancel_schedule_feedback_todo(
                    todo.schedule_id,
                    reason=get_course_feedback_skip_reason(getattr(todo, 'schedule', None)) or '',
                )
                changed = True
            continue
        visible.append(todo)
    if changed:
        db.session.commit()
    return visible


def _guard_external_generic_todo_mutation(todo):
    if todo and todo.is_workflow:
        return external_error(
            '工作流待办不能通过通用待办接口修改，请使用对应工作流动作',
            status=400,
            code='workflow_todo_guarded',
        )
    return None


def _parse_iso_date(value, field_name='date'):
    try:
        return date.fromisoformat(value), None
    except (TypeError, ValueError):
        return None, external_error(f'{field_name} 格式错误，请使用 YYYY-MM-DD')


def _resolve_teacher_from_payload(data):
    teacher_name = (data.get('teacher') or data.get('teacher_name') or '').strip()
    teacher_id = data.get('teacher_id')
    teacher_user = None

    if teacher_id:
        teacher_user = User.query.get(teacher_id)
        if not teacher_user:
            return None, None, external_error('授课老师不存在', status=404)
        return teacher_user, teacher_user.display_name, None

    if teacher_name:
        teacher_user, canonical_name, _, error = resolve_schedule_teacher_reference(teacher_name)
        if error or not teacher_user:
            return None, None, external_error(error or f'未找到老师: {teacher_name}')
        return teacher_user, canonical_name, None

    return None, None, external_error('缺少 teacher_id 或 teacher_name')


@oa_bp.route('/api/external/dashboard-stats', methods=['GET'])
@external_api_required
def external_dashboard_stats():
    today = date.today()
    today_count = CourseSchedule.query.filter(CourseSchedule.date == today).count()
    pending_count = len(_filter_visible_todos(
        OATodo.query.filter(OATodo.is_completed == False).all(),
        reconcile_feedback_visibility=True,
    ))
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_count = CourseSchedule.query.filter(
        CourseSchedule.date >= monday,
        CourseSchedule.date <= sunday
    ).count()
    today_schedules = CourseSchedule.query.filter(
        CourseSchedule.date == today
    ).order_by(CourseSchedule.time_start).all()

    return external_success({
        'today_count': today_count,
        'pending_todos': pending_count,
        'week_count': week_count,
        'today_schedules': [s.to_dict() for s in today_schedules],
    })


@oa_bp.route('/api/external/schedules', methods=['GET'])
@external_api_required
def external_list_schedules():
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if start_str or end_str:
        if not start_str or not end_str:
            return external_error('请同时提供 start 和 end 日期参数')
        start_date, error = _parse_iso_date(start_str, 'start')
        if error:
            return error
        end_date, error = _parse_iso_date(end_str, 'end')
        if error:
            return error
    else:
        year = request.args.get('year', type=int, default=datetime.utcnow().year)
        month = request.args.get('month', type=int, default=datetime.utcnow().month)
        _, last_day = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

    query = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date
    )
    teacher = request.args.get('teacher')
    if teacher:
        query = query.filter(CourseSchedule.teacher.contains(teacher))
    student_name = request.args.get('student_name')
    if student_name:
        query = query.filter(CourseSchedule.students.contains(student_name))
    course_name = request.args.get('course_name')
    if course_name:
        query = query.filter(CourseSchedule.course_name.contains(course_name))

    schedules = query.order_by(CourseSchedule.date, CourseSchedule.time_start).all()
    return external_success({'items': [s.to_dict() for s in schedules], 'total': len(schedules)})


@oa_bp.route('/api/external/schedules/date-range', methods=['GET'])
@external_api_required
def external_schedules_date_range():
    result = db.session.query(
        func.min(CourseSchedule.date),
        func.max(CourseSchedule.date),
        func.count(CourseSchedule.id)
    ).first()
    return external_success({
        'min_date': result[0].isoformat() if result and result[0] else None,
        'max_date': result[1].isoformat() if result and result[1] else None,
        'total': result[2] if result else 0,
    })


@oa_bp.route('/api/external/schedules/by-date', methods=['GET'])
@external_api_required
def external_schedules_by_date():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        return external_error('请提供 start 和 end 日期参数')

    start_date, error = _parse_iso_date(start_str, 'start')
    if error:
        return error
    end_date, error = _parse_iso_date(end_str, 'end')
    if error:
        return error

    schedules = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()
    return external_success({'items': [s.to_dict() for s in schedules], 'total': len(schedules)})


@oa_bp.route('/api/external/schedules/<int:schedule_id>', methods=['GET'])
@external_api_required
def external_get_schedule(schedule_id):
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return external_error('课程不存在', status=404)
    return external_success(schedule.to_dict())


@oa_bp.route('/api/external/schedules', methods=['POST'])
@external_api_required
def external_create_schedule():
    from modules.auth.workflow_services import ensure_schedule_feedback_todo

    data, error = _get_json_payload()
    if error:
        return error

    for field in ['date', 'time_start', 'time_end', 'course_name']:
        if not data.get(field):
            return external_error(f'缺少必填字段: {field}')

    course_date, error = _parse_iso_date(data.get('date'))
    if error:
        return error

    teacher_user, teacher_name, error = _resolve_teacher_from_payload(data)
    if error:
        return error

    enrollment = None
    if data.get('enrollment_id'):
        enrollment = db.session.get(Enrollment, data.get('enrollment_id'))
        if not enrollment:
            return external_error('报名记录不存在', status=404)
        if teacher_user and enrollment.teacher_id != teacher_user.id:
            return external_error('所选教师与报名绑定教师不一致')

    try:
        delivery_fields = build_schedule_delivery_fields(
            delivery_mode=data.get('delivery_mode'),
            color_tag=data.get('color_tag'),
            fallback_delivery_mode=(
                enrollment.delivery_preference
                if enrollment and getattr(enrollment, 'delivery_preference', None) not in {None, '', 'unknown'}
                else 'online'
            ),
            allow_unknown=False,
        )
    except ValueError as exc:
        return external_error(str(exc))

    conflict_error = schedule_actions.validate_schedule_conflicts_or_error(
        course_date=course_date,
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher_id=teacher_user.id if teacher_user else None,
        enrollment_id=enrollment.id if enrollment else None,
    )
    if conflict_error:
        return external_error(conflict_error)

    schedule = CourseSchedule(
        date=course_date,
        day_of_week=course_date.weekday(),
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher=teacher_name,
        teacher_id=teacher_user.id if teacher_user else None,
        course_name=data['course_name'],
        enrollment_id=data.get('enrollment_id'),
        students=data.get('students', ''),
        location=data.get('location', ''),
        notes=data.get('notes', ''),
        **delivery_fields,
    )
    sync_schedule_student_snapshot(schedule, enrollment=enrollment, preserve_history=False)
    db.session.add(schedule)
    db.session.flush()
    ensure_schedule_feedback_todo(schedule, created_by=None)
    if enrollment:
        sync_enrollment_status(enrollment)
    db.session.commit()
    return external_success(schedule.to_dict(), status=201)


@oa_bp.route('/api/external/schedules/<int:schedule_id>', methods=['PUT'])
@external_api_required
def external_update_schedule(schedule_id):
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return external_error('课程不存在', status=404)

    data, error = _get_json_payload()
    if error:
        return error

    if 'date' in data:
        course_date, error = _parse_iso_date(data.get('date'))
        if error:
            return error
        schedule.date = course_date
        schedule.day_of_week = course_date.weekday()

    if 'teacher' in data or 'teacher_name' in data or 'teacher_id' in data:
        teacher_user, teacher_name, error = _resolve_teacher_from_payload(data)
        if error:
            return error
        data['teacher'] = teacher_name

    result = schedule_actions.apply_schedule_update(
        schedule,
        data,
        allow_admin_override=True,
    )
    if not result.get('success'):
        return external_error(result.get('error') or '更新失败', status=result.get('status_code', 400))
    return external_success(schedule.to_dict())


@oa_bp.route('/api/external/schedules/<int:schedule_id>', methods=['DELETE'])
@external_api_required
def external_delete_schedule(schedule_id):
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return external_error('课程不存在', status=404)

    OATodo.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    LeaveRequest.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    CourseFeedback.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    ScheduleMeetingMaterial.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    db.session.delete(schedule)
    db.session.commit()
    return external_success({'id': schedule_id}, message='课程已删除')


@oa_bp.route('/api/external/schedules/teachers', methods=['GET'])
@external_api_required
def external_list_schedule_teachers():
    teachers = db.session.query(CourseSchedule.teacher).distinct().all()
    return external_success(sorted([row[0] for row in teachers if row[0]]))


@oa_bp.route('/api/external/schedules/students', methods=['GET'])
@external_api_required
def external_list_schedule_students():
    rows = db.session.query(CourseSchedule.students).filter(
        CourseSchedule.students.isnot(None),
        CourseSchedule.students != ''
    ).all()
    student_set = set()
    for row in rows:
        for name in row[0].replace('、', ',').replace('，', ',').split(','):
            name = name.strip()
            if name:
                student_set.add(name)
    return external_success(sorted(student_set))


@oa_bp.route('/api/external/schedules/progress', methods=['GET'])
@external_api_required
def external_schedule_progress():
    all_schedules = CourseSchedule.query.order_by(CourseSchedule.date, CourseSchedule.time_start).all()
    progress_map = {}
    grouped = {}
    for schedule in all_schedules:
        key = (schedule.course_name, schedule.teacher, schedule.students or '')
        grouped.setdefault(key, []).append(schedule)

    for schedules in grouped.values():
        total = len(schedules)
        if total < 2:
            continue
        for index, schedule in enumerate(schedules, 1):
            progress_map[schedule.id] = {
                'current': index,
                'total': total,
                'is_ending': index > max(total - 3, 0),
            }

    return external_success(progress_map)


@oa_bp.route('/api/external/todos', methods=['GET'])
@external_api_required
def external_list_todos():
    query = OATodo.query

    status = request.args.get('status')
    if status == 'pending':
        query = query.filter(OATodo.is_completed == False)
    elif status == 'completed':
        query = query.filter(OATodo.is_completed == True)

    person = request.args.get('person')
    if person:
        query = query.filter(OATodo.responsible_person.contains(person))

    priority = request.args.get('priority', type=int)
    if priority:
        query = query.filter(OATodo.priority == priority)

    todos = _filter_visible_todos(
        query.order_by(
            OATodo.is_completed,
            OATodo.priority,
            OATodo.due_date.asc().nullslast()
        ).all(),
        reconcile_feedback_visibility=True,
    )
    return external_success({'items': [todo.to_dict() for todo in todos], 'total': len(todos)})


@oa_bp.route('/api/external/todos/<int:todo_id>', methods=['GET'])
@external_api_required
def external_get_todo(todo_id):
    todo = OATodo.query.get(todo_id)
    if not todo:
        return external_error('待办不存在', status=404)
    return external_success(todo.to_dict())


@oa_bp.route('/api/external/todos', methods=['POST'])
@external_api_required
def external_create_todo():
    data, error = _get_json_payload()
    if error:
        return error
    if not data.get('title'):
        return external_error('缺少必填字段: title')

    due_date = None
    if data.get('due_date'):
        due_date, error = _parse_iso_date(data.get('due_date'), 'due_date')
        if error:
            return error

    todo = OATodo(
        title=data['title'],
        description=data.get('description', ''),
        responsible_person=OATodo.normalize_responsible_people(
            data.get('responsible_people', data.get('responsible_person', ''))
        ),
        is_completed=bool(data.get('is_completed', False)),
        due_date=due_date,
        priority=data.get('priority', 2),
        notes=data.get('notes', ''),
        schedule_id=data.get('schedule_id'),
    )
    db.session.add(todo)
    db.session.commit()
    return external_success(todo.to_dict(), status=201)


@oa_bp.route('/api/external/todos/<int:todo_id>', methods=['PUT'])
@external_api_required
def external_update_todo(todo_id):
    todo = OATodo.query.get(todo_id)
    if not todo:
        return external_error('待办不存在', status=404)
    guarded = _guard_external_generic_todo_mutation(todo)
    if guarded:
        return guarded

    data, error = _get_json_payload()
    if error:
        return error

    if 'due_date' in data:
        if data.get('due_date'):
            due_date, error = _parse_iso_date(data.get('due_date'), 'due_date')
            if error:
                return error
            todo.due_date = due_date
        else:
            todo.due_date = None

    for field in ['title', 'description', 'is_completed', 'priority', 'notes', 'schedule_id']:
        if field in data:
            setattr(todo, field, data[field])

    if 'responsible_person' in data or 'responsible_people' in data:
        todo.responsible_person = OATodo.normalize_responsible_people(
            data.get('responsible_people', data.get('responsible_person', ''))
        )

    db.session.commit()
    return external_success(todo.to_dict())


@oa_bp.route('/api/external/todos/<int:todo_id>', methods=['DELETE'])
@external_api_required
def external_delete_todo(todo_id):
    todo = OATodo.query.get(todo_id)
    if not todo:
        return external_error('待办不存在', status=404)
    guarded = _guard_external_generic_todo_mutation(todo)
    if guarded:
        return guarded

    db.session.delete(todo)
    db.session.commit()
    return external_success({'id': todo_id}, message='待办已删除')


@oa_bp.route('/api/external/todos/<int:todo_id>/toggle', methods=['POST'])
@external_api_required
def external_toggle_todo(todo_id):
    todo = OATodo.query.get(todo_id)
    if not todo:
        return external_error('待办不存在', status=404)
    guarded = _guard_external_generic_todo_mutation(todo)
    if guarded:
        return guarded

    todo.is_completed = not todo.is_completed
    db.session.commit()
    return external_success(todo.to_dict())


@oa_bp.route('/api/external/todos/batch', methods=['POST'])
@external_api_required
def external_batch_todos():
    data, error = _get_json_payload()
    if error:
        return error

    action = data.get('action')
    ids = data.get('ids', [])
    if not action or not ids:
        return external_error('缺少 action 或 ids 参数')

    todos = OATodo.query.filter(OATodo.id.in_(ids)).all()
    if not todos:
        return external_error('未找到匹配的待办', status=404)

    guarded_todo = next((todo for todo in todos if todo.is_workflow), None)
    if guarded_todo:
        return _guard_external_generic_todo_mutation(guarded_todo)

    if action == 'complete':
        for todo in todos:
            todo.is_completed = True
    elif action == 'uncomplete':
        for todo in todos:
            todo.is_completed = False
    elif action == 'delete':
        for todo in todos:
            db.session.delete(todo)
    else:
        return external_error(f'不支持的操作: {action}')

    db.session.commit()
    return external_success({'action': action, 'affected': len(todos)})


@oa_bp.route('/api/external/import-excel', methods=['POST'])
@external_api_required
def external_import_excel():
    file = request.files.get('file')
    if not file:
        return external_error('请上传文件')
    if not file.filename.endswith(('.xlsx', '.xls')):
        return external_error('仅支持 .xlsx 或 .xls 文件')

    try:
        _, summary = apply_schedule_excel_import(file)
        return external_success(summary)
    except Exception as exc:
        db.session.rollback()
        return external_error(f'导入失败: {str(exc)}', status=500)
