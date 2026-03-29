import json
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import current_app, jsonify, render_template, request
from flask_login import current_user

from extensions import db
from modules.auth.decorators import role_required
from modules.auth.models import Enrollment, LeaveRequest, User
from modules.auth.services import (
    BUSINESS_TIMEZONE,
    _schedule_effective_student_profile_id,
    build_schedule_payload,
    get_course_feedback_skip_reason,
    get_business_now,
    get_business_today,
    schedule_has_historical_facts,
    schedule_requires_course_feedback,
    sync_schedule_student_snapshot,
    sync_enrollment_status,
)
from modules.oa import oa_bp
from . import schedule_actions
from modules.oa.models import CourseFeedback, CourseSchedule, OATodo
from modules.oa.reminder_services import record_schedule_action_reminders
from modules.oa.services import (
    apply_schedule_excel_import,
    build_schedule_delivery_fields,
    delivery_mode_from_color_tag,
    resolve_schedule_teacher_reference,
    validate_schedule_conflicts,
)


def _get_staff_options():
    """从数据库动态获取员工列表，替代硬编码。"""
    try:
        users = User.query.filter(User.is_active == True).all()
        if users:
            return [user.display_name for user in users]
    except Exception:
        pass
    return ['李宇', '范晓东', '周行', '包睿旻', '黎怡君', '张渝', '陈冠如', '王艳龙', '卢老师', '田鹏', '陈东豪']


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


def _time_to_minutes(time_str):
    hour, minute = time_str.split(':')
    return int(hour) * 60 + int(minute)


def _time_ranges_overlap(start_a, end_a, start_b, end_b):
    return max(_time_to_minutes(start_a), _time_to_minutes(start_b)) < min(
        _time_to_minutes(end_a),
        _time_to_minutes(end_b),
    )


def _shift_schedule_time_value(time_str, minutes_delta):
    total_minutes = _time_to_minutes(time_str)
    shifted_minutes = total_minutes + minutes_delta
    if shifted_minutes < 0 or shifted_minutes > (23 * 60 + 59):
        return None
    return f'{shifted_minutes // 60:02d}:{shifted_minutes % 60:02d}'


def _parse_job_now_override(value):
    normalized = str(value or '').strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None)
    return parsed


def _resolve_teacher_or_error(teacher_value):
    teacher_user, teacher_name, _, error = resolve_schedule_teacher_reference(teacher_value)
    if error or not teacher_user:
        return None, '授课教师不存在，请先创建教师账号'
    return teacher_user, None


def _validate_schedule_conflicts(*, schedule_id=None, course_date=None, time_start=None, time_end=None, teacher_id=None, enrollment_id=None):
    return validate_schedule_conflicts(
        schedule_id=schedule_id,
        course_date=course_date,
        time_start=time_start,
        time_end=time_end,
        teacher_id=teacher_id,
        enrollment_id=enrollment_id,
    )


def _schedule_locked_by_leave(schedule, updates):
    if not schedule:
        return False
    protected_fields = {'date', 'time_start', 'time_end', 'teacher', 'teacher_id', 'enrollment_id'}
    if not any(field in (updates or {}) for field in protected_fields):
        return False
    latest_leave = LeaveRequest.query.filter_by(schedule_id=schedule.id).order_by(
        LeaveRequest.created_at.desc()
    ).first()
    if not latest_leave:
        return False
    if latest_leave.status == 'pending':
        return True
    if latest_leave.status != 'approved':
        return False

    open_makeup = OATodo.query.filter(
        OATodo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP,
        OATodo.leave_request_id == latest_leave.id,
        OATodo.is_completed == False,
        ~OATodo.workflow_status.in_([
            OATodo.WORKFLOW_STATUS_COMPLETED,
            OATodo.WORKFLOW_STATUS_CANCELLED,
        ]),
    ).count()
    return open_makeup > 0


def _direct_schedule_enrollment_error(enrollment):
    if not enrollment:
        return None
    if enrollment.status in {'pending_info', 'pending_schedule', 'pending_student_confirm'}:
        return '该报名仍在排课工作流中，请通过工作流发送给学生确认后再生成正式课次'

    from modules.auth.workflow_services import has_open_process_workflow

    if has_open_process_workflow(enrollment_id=enrollment.id):
        return '该报名存在未完成的排课/补课工作流，请先完成工作流再直接改课表'
    return None


def _direct_schedule_update_workflow_error(schedule, updates):
    if not schedule:
        return None

    from modules.auth.workflow_services import has_open_process_workflow, has_open_workflow

    touched_fields = {field for field in (updates or {})}
    if not touched_fields:
        return None

    target_enrollment_id = (updates or {}).get('enrollment_id', schedule.enrollment_id)
    process_locked_fields = {'date', 'time_start', 'time_end', 'teacher', 'enrollment_id', 'course_name', 'students'}
    if (
        touched_fields & process_locked_fields
        and has_open_process_workflow(schedule_id=schedule.id, enrollment_id=target_enrollment_id)
    ):
        return '该课程关联未完成的工作流，仅允许修改备注、地点或上课方式'

    relationship_locked_fields = {'enrollment_id'}
    if (
        touched_fields & relationship_locked_fields
        and has_open_workflow(schedule_id=schedule.id, enrollment_id=target_enrollment_id)
    ):
        return '该课程关联未完成的工作流，不能直接改绑报名'
    return None


def _normalize_schedule_compare_value(field, value):
    if field in {'teacher', 'time_start', 'time_end', 'course_name', 'students', 'location', 'notes', 'color_tag', 'delivery_mode'}:
        return str(value or '').strip()
    return value


def _historical_schedule_mutation_error(schedule, *, proposed_values=None, deleting=False):
    if not schedule or not schedule_has_historical_facts(schedule):
        return None
    if deleting:
        return '该课程已产生交付事实，不能直接删除'
    changed_fields = {
        field
        for field, value in (proposed_values or {}).items()
        if _normalize_schedule_compare_value(field, value)
        != _normalize_schedule_compare_value(field, getattr(schedule, field, None))
    }
    if not changed_fields:
        return None
    if changed_fields.issubset({'notes', 'location', 'color_tag', 'delivery_mode'}):
        return None
    return '该课程已产生交付事实，仅允许修改备注、地点或上课方式'


def _build_schedule_update_context(schedule, data, *, allow_admin_override=False):
    if not data:
        return None, ('请提供 JSON 数据', 400)
    if not allow_admin_override and _schedule_locked_by_leave(schedule, data):
        return None, ('该课程已有请假记录，请通过调课流程处理，不能直接覆盖', 400)

    next_date = schedule.date
    if 'date' in data:
        try:
            next_date = date.fromisoformat(data['date'])
        except ValueError:
            return None, ('日期格式错误', 400)

    next_teacher_name = data.get('teacher', schedule.teacher)
    if 'teacher' not in data and schedule.teacher_id:
        teacher_user = db.session.get(User, schedule.teacher_id)
        if teacher_user:
            next_teacher_name = teacher_user.display_name
    teacher_user, error = _resolve_teacher_or_error(next_teacher_name)
    if error:
        return None, (error, 400)

    original_enrollment_id = schedule.enrollment_id
    original_enrollment = db.session.get(Enrollment, original_enrollment_id) if original_enrollment_id else None
    next_enrollment_id = data.get('enrollment_id', schedule.enrollment_id)
    if next_enrollment_id:
        enrollment = db.session.get(Enrollment, next_enrollment_id)
        if not enrollment:
            return None, ('报名记录不存在', 404)
        if enrollment.teacher_id != teacher_user.id:
            return None, ('所选教师与报名绑定教师不一致', 400)
        if not allow_admin_override:
            enrollment_error = _direct_schedule_enrollment_error(enrollment)
            if enrollment_error:
                return None, (enrollment_error, 400)
    else:
        enrollment = None

    next_time_start = data.get('time_start', schedule.time_start)
    next_time_end = data.get('time_end', schedule.time_end)
    next_course_name = data.get('course_name', schedule.course_name)
    next_students = data.get('students')
    if next_students is None:
        next_students = (
            enrollment.student_name if next_enrollment_id != original_enrollment_id and enrollment else schedule.students
        )
    next_location = data.get('location', schedule.location)
    next_notes = data.get('notes', schedule.notes)
    current_delivery_mode = (schedule.delivery_mode or '').strip().lower()
    fallback_delivery_mode = (
        current_delivery_mode
        if current_delivery_mode in {'online', 'offline'}
        else delivery_mode_from_color_tag(schedule.color_tag)
    )
    if 'delivery_mode' in data or 'color_tag' in data:
        try:
            delivery_fields = build_schedule_delivery_fields(
                delivery_mode=data.get('delivery_mode'),
                color_tag=data.get('color_tag'),
                fallback_delivery_mode=fallback_delivery_mode,
                existing_schedule=schedule,
                allow_unknown=False,
            )
        except ValueError as exc:
            return None, (str(exc), 400)
    else:
        delivery_fields = {
            'delivery_mode': schedule.delivery_mode,
            'color_tag': schedule.color_tag,
            'meeting_provider': schedule.meeting_provider,
            'meeting_status': schedule.meeting_status,
            'meeting_join_url': schedule.meeting_join_url,
            'meeting_external_id': schedule.meeting_external_id,
            'meeting_code': schedule.meeting_code,
            'meeting_password': schedule.meeting_password,
            'meeting_created_at': schedule.meeting_created_at,
            'meeting_ended_at': schedule.meeting_ended_at,
        }

    if not allow_admin_override:
        workflow_error = _direct_schedule_update_workflow_error(schedule, data)
        if workflow_error:
            return None, (workflow_error, 400)

        historical_error = _historical_schedule_mutation_error(
            schedule,
            proposed_values={
                'date': next_date,
                'time_start': next_time_start,
                'time_end': next_time_end,
                'teacher': teacher_user.display_name,
                'teacher_id': teacher_user.id,
                'course_name': next_course_name,
                'students': next_students,
                'location': next_location,
                'notes': next_notes,
                'color_tag': delivery_fields['color_tag'],
                'delivery_mode': delivery_fields['delivery_mode'],
                'enrollment_id': next_enrollment_id,
            },
        )
        if historical_error:
            return None, (historical_error, 400)

    conflict_error = _validate_schedule_conflicts(
        schedule_id=schedule.id,
        course_date=next_date,
        time_start=next_time_start,
        time_end=next_time_end,
        teacher_id=teacher_user.id,
        enrollment_id=next_enrollment_id,
    )
    if conflict_error:
        return None, (conflict_error, 400)

    return {
        'original_enrollment_id': original_enrollment_id,
        'original_enrollment': original_enrollment,
        'historical_student_profile_id': _schedule_effective_student_profile_id(schedule),
        'preserve_student_snapshot': schedule_has_historical_facts(schedule),
        'enrollment': enrollment,
        'next_date': next_date,
        'next_time_start': next_time_start,
        'next_time_end': next_time_end,
        'teacher_user': teacher_user,
        'next_course_name': next_course_name,
        'next_students': next_students or '',
        'next_location': next_location,
        'next_notes': next_notes,
        'delivery_fields': delivery_fields,
        'next_enrollment_id': next_enrollment_id,
    }, None


def _apply_schedule_update_context(schedule, context):
    from modules.auth.workflow_services import sync_schedule_feedback_todo

    original_enrollment_id = context['original_enrollment_id']
    enrollment = context['enrollment']

    schedule.date = context['next_date']
    schedule.day_of_week = context['next_date'].weekday()
    schedule.time_start = context['next_time_start']
    schedule.time_end = context['next_time_end']
    schedule.teacher = context['teacher_user'].display_name
    schedule.teacher_id = context['teacher_user'].id
    schedule.course_name = context['next_course_name']
    schedule.students = context['next_students']
    schedule.location = context['next_location']
    schedule.notes = context['next_notes']
    for field, value in context['delivery_fields'].items():
        setattr(schedule, field, value)
    schedule.enrollment_id = context['next_enrollment_id']
    if context.get('preserve_student_snapshot'):
        historical_student_profile_id = context.get('historical_student_profile_id')
        if historical_student_profile_id is not None:
            schedule.student_profile_id_snapshot = historical_student_profile_id
        else:
            sync_schedule_student_snapshot(
                schedule,
                enrollment=context.get('original_enrollment'),
                preserve_history=False,
                force=True,
            )
    else:
        sync_schedule_student_snapshot(
            schedule,
            enrollment=enrollment,
            preserve_history=False,
        )

    db.session.flush()
    if original_enrollment_id:
        original_enrollment = db.session.get(Enrollment, original_enrollment_id)
        if original_enrollment and (not enrollment or original_enrollment.id != enrollment.id):
            sync_enrollment_status(original_enrollment)
    if enrollment:
        sync_enrollment_status(enrollment)
    sync_schedule_feedback_todo(schedule)
    db.session.commit()
    return schedule


def _schedule_factual_edit_block_reason(schedule):
    return schedule_actions.schedule_factual_edit_block_reason(schedule)


def _build_oa_schedule_payload(schedule):
    payload = build_schedule_payload(schedule, current_user)
    delete_block_reason = schedule_actions.schedule_cancel_block_reason(schedule)
    reschedule_block_reason = (
        '该课程已取消'
        if getattr(schedule, 'is_cancelled', False)
        else schedule_actions.schedule_factual_edit_block_reason(schedule)
    )
    payload.update({
        'admin_can_delete': delete_block_reason is None,
        'admin_delete_block_reason': delete_block_reason,
        'admin_can_reschedule': reschedule_block_reason is None,
        'admin_reschedule_block_reason': reschedule_block_reason,
    })
    return payload


def _guard_generic_todo_mutation(todo):
    if todo and todo.is_workflow:
        return jsonify({'success': False, 'error': '工作流待办不能通过通用待办接口修改，请使用对应工作流动作'}), 400
    return None


def _workflow_todo_target(todo):
    if not todo or not todo.is_workflow:
        return None, None
    if todo.enrollment:
        return f'/auth/enrollments/{todo.enrollment.id}', '打开报名流程'
    if todo.schedule or (todo.leave_request and todo.leave_request.schedule):
        return '/oa/schedule', '打开课表查看'
    return None, None


def _build_oa_todo_payload(todo):
    payload = todo.to_dict()
    target_url, target_label = _workflow_todo_target(todo)
    payload.update({
        'workflow_target_url': target_url,
        'workflow_target_label': target_label,
    })
    return payload


# ========== 页面路由 ==========


@oa_bp.route('/')
@role_required('admin')
def oa_dashboard():
    return render_template('oa/dashboard.html')


@oa_bp.route('/schedule')
@role_required('admin')
def oa_schedule():
    return render_template('oa/schedule.html')


@oa_bp.route('/todos')
@role_required('admin')
def oa_todos():
    return render_template('oa/todos.html', staff_options=_get_staff_options())


@oa_bp.route('/painpoints')
@role_required('admin')
def oa_painpoints():
    return render_template('oa/painpoints.html', staff_options=_get_staff_options())


# ========== 课程排课 API ==========


@oa_bp.route('/api/schedules', methods=['GET'])
@role_required('admin')
def api_list_schedules():
    today = get_business_today()
    year = request.args.get('year', type=int, default=today.year)
    month = request.args.get('month', type=int, default=today.month)

    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    schedules = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date,
        CourseSchedule.is_cancelled == False,
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': [_build_oa_schedule_payload(schedule) for schedule in schedules],
        'total': len(schedules),
    })


@oa_bp.route('/api/schedules/date-range', methods=['GET'])
@role_required('admin')
def api_schedules_date_range():
    from sqlalchemy import func

    result = db.session.query(
        func.min(CourseSchedule.date),
        func.max(CourseSchedule.date),
        func.count(CourseSchedule.id),
    ).filter(CourseSchedule.is_cancelled == False).first()
    if result and result[0]:
        return jsonify({
            'success': True,
            'data': {
                'min_date': result[0].isoformat() if result[0] else None,
                'max_date': result[1].isoformat() if result[1] else None,
                'total': result[2],
            }
        })
    return jsonify({'success': True, 'data': {'min_date': None, 'max_date': None, 'total': 0}})


@oa_bp.route('/api/schedules/by-date', methods=['GET'])
@role_required('admin')
def api_schedules_by_date():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        return jsonify({'success': False, 'error': '请提供 start 和 end 日期参数'}), 400

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return jsonify({'success': False, 'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400

    schedules = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date,
        CourseSchedule.is_cancelled == False,
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': [_build_oa_schedule_payload(schedule) for schedule in schedules],
        'total': len(schedules),
    })


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['GET'])
@role_required('admin')
def api_get_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    return jsonify({'success': True, 'data': _build_oa_schedule_payload(schedule)})


@oa_bp.route('/api/schedules', methods=['POST'])
@role_required('admin')
def api_create_schedule():
    from modules.auth.workflow_services import ensure_schedule_feedback_todo

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    required = ['date', 'time_start', 'time_end', 'teacher', 'course_name']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400

    try:
        course_date = date.fromisoformat(data['date'])
    except ValueError:
        return jsonify({'success': False, 'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400

    teacher_user, error = schedule_actions.resolve_teacher_or_error(data['teacher'])
    if error:
        return jsonify({'success': False, 'error': error}), 400

    enrollment_id = data.get('enrollment_id')
    if enrollment_id:
        enrollment = db.session.get(Enrollment, enrollment_id)
        if not enrollment:
            return jsonify({'success': False, 'error': '报名记录不存在'}), 404
        if enrollment.teacher_id != teacher_user.id:
            return jsonify({'success': False, 'error': '所选教师与报名绑定教师不一致'}), 400
    else:
        enrollment = None

    conflict_error = schedule_actions.validate_schedule_conflicts_or_error(
        course_date=course_date,
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher_id=teacher_user.id,
        enrollment_id=enrollment_id,
    )
    if conflict_error:
        return jsonify({'success': False, 'error': conflict_error}), 400

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
        return jsonify({'success': False, 'error': str(exc)}), 400

    schedule = CourseSchedule(
        date=course_date,
        day_of_week=course_date.weekday(),
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher=teacher_user.display_name,
        teacher_id=teacher_user.id,
        course_name=data['course_name'],
        enrollment_id=enrollment.id if enrollment else None,
        students=data.get('students') or (enrollment.student_name if enrollment else ''),
        location=data.get('location', ''),
        notes=data.get('notes', ''),
        **delivery_fields,
    )
    sync_schedule_student_snapshot(schedule, enrollment=enrollment, preserve_history=False)
    db.session.add(schedule)
    db.session.flush()
    ensure_schedule_feedback_todo(schedule, created_by=current_user.id)
    if enrollment:
        sync_enrollment_status(enrollment)
    db.session.commit()

    return jsonify({'success': True, 'data': _build_oa_schedule_payload(schedule)}), 201


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
@role_required('admin')
def api_update_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404

    before_payload = schedule_actions.build_schedule_preview_payload(schedule)
    result = schedule_actions.apply_schedule_update(
        schedule,
        request.get_json(),
        allow_admin_override=True,
    )
    if not result.get('success'):
        return jsonify({'success': False, 'error': result.get('error')}), result.get('status_code', 400)
    record_schedule_action_reminders(
        schedule,
        actor=current_user,
        action_key='schedule.reschedule.apply',
        before_payload=before_payload,
    )

    return jsonify({'success': True, 'data': _build_oa_schedule_payload(schedule)})


@oa_bp.route('/api/schedules/<int:schedule_id>/quick-shift', methods=['POST'])
@role_required('admin')
def api_quick_shift_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404

    update_payload, meta_or_error = schedule_actions.prepare_quick_shift_payload(
        schedule,
        request.get_json() or {},
    )
    if update_payload is None:
        return jsonify({'success': False, 'error': meta_or_error[0]}), meta_or_error[1]

    before_payload = schedule_actions.build_schedule_preview_payload(schedule)
    result = schedule_actions.apply_schedule_update(
        schedule,
        update_payload,
        allow_admin_override=True,
    )
    if not result.get('success'):
        return jsonify({'success': False, 'error': result.get('error')}), result.get('status_code', 400)
    record_schedule_action_reminders(
        schedule,
        actor=current_user,
        action_key='schedule.quick_shift.apply',
        before_payload=before_payload,
        extra_payload=meta_or_error,
    )

    return jsonify({
        'success': True,
        'data': _build_oa_schedule_payload(schedule),
        'meta': meta_or_error,
    })


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
@role_required('admin')
def api_delete_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    data = request.get_json(silent=True) or {}
    _, error = schedule_actions.cancel_schedule(
        schedule,
        actor=current_user,
        reason=data.get('reason', ''),
    )
    if error:
        return jsonify({'success': False, 'error': error[0]}), error[1]
    db.session.commit()
    return jsonify({
        'success': True,
        'message': '课次已取消并保留业务记录',
        'data': {
            'id': schedule_id,
            'status': 'cancelled',
            'cancel_reason': schedule.cancel_reason,
        },
    })


@oa_bp.route('/api/internal/reminders/sms/run', methods=['POST'])
def api_run_internal_sms_reminders():
    expected_token = (current_app.config.get('SCF_REMINDER_JOB_TOKEN') or '').strip()
    provided_token = (request.headers.get('X-Reminder-Job-Token') or '').strip()
    if not expected_token:
        return jsonify({'success': False, 'error': '短信提醒任务未配置 token'}), 503
    if provided_token != expected_token:
        return jsonify({'success': False, 'error': '无效的提醒任务 token'}), 401

    payload = request.get_json(silent=True) or {}
    now_override = None
    if 'now' in payload:
        now_override = _parse_job_now_override(payload.get('now'))
        if payload.get('now') and now_override is None:
            return jsonify({'success': False, 'error': 'now 参数格式错误，请使用 ISO 时间'}), 400

    from modules.oa.sms_reminder_services import run_schedule_sms_reminder_job

    result = run_schedule_sms_reminder_job(
        now=now_override or get_business_now(),
        dry_run=bool(payload.get('dry_run')),
    )
    return jsonify({'success': True, 'data': result})


@oa_bp.route('/api/internal/tencent-meeting/create-due', methods=['POST'])
def api_run_internal_tencent_meeting_create_due():
    expected_token = (current_app.config.get('TENCENT_MEETING_JOB_TOKEN') or '').strip()
    provided_token = (request.headers.get('X-Tencent-Meeting-Job-Token') or '').strip()
    if not expected_token:
        return jsonify({'success': False, 'error': '腾讯会议任务未配置 token'}), 503
    if provided_token != expected_token:
        return jsonify({'success': False, 'error': '无效的腾讯会议任务 token'}), 401

    payload = request.get_json(silent=True) or {}
    now_override = None
    if 'now' in payload:
        now_override = _parse_job_now_override(payload.get('now'))
        if payload.get('now') and now_override is None:
            return jsonify({'success': False, 'error': 'now 参数格式错误，请使用 ISO 时间'}), 400

    from modules.oa.tencent_meeting_services import run_due_meeting_creation_job

    result = run_due_meeting_creation_job(
        now=now_override or get_business_now(),
        dry_run=bool(payload.get('dry_run')),
    )
    return jsonify({'success': True, 'data': result})


@oa_bp.route('/api/internal/tencent-meeting/materials/run', methods=['POST'])
def api_run_internal_tencent_meeting_materials():
    expected_token = (current_app.config.get('TENCENT_MEETING_JOB_TOKEN') or '').strip()
    provided_token = (request.headers.get('X-Tencent-Meeting-Job-Token') or '').strip()
    if not expected_token:
        return jsonify({'success': False, 'error': '腾讯会议任务未配置 token'}), 503
    if provided_token != expected_token:
        return jsonify({'success': False, 'error': '无效的腾讯会议任务 token'}), 401

    payload = request.get_json(silent=True) or {}
    now_override = None
    if 'now' in payload:
        now_override = _parse_job_now_override(payload.get('now'))
        if payload.get('now') and now_override is None:
            return jsonify({'success': False, 'error': 'now 参数格式错误，请使用 ISO 时间'}), 400

    from modules.oa.tencent_meeting_services import run_material_sync_job

    result = run_material_sync_job(
        now=now_override or get_business_now(),
        dry_run=bool(payload.get('dry_run')),
    )
    return jsonify({'success': True, 'data': result})


@oa_bp.route('/api/internal/tencent-meeting/feedback-drafts/run', methods=['POST'])
def api_run_internal_tencent_meeting_feedback_drafts():
    expected_token = (current_app.config.get('TENCENT_MEETING_JOB_TOKEN') or '').strip()
    provided_token = (request.headers.get('X-Tencent-Meeting-Job-Token') or '').strip()
    if not expected_token:
        return jsonify({'success': False, 'error': '腾讯会议任务未配置 token'}), 503
    if provided_token != expected_token:
        return jsonify({'success': False, 'error': '无效的腾讯会议任务 token'}), 401

    payload = request.get_json(silent=True) or {}
    now_override = None
    if 'now' in payload:
        now_override = _parse_job_now_override(payload.get('now'))
        if payload.get('now') and now_override is None:
            return jsonify({'success': False, 'error': 'now 参数格式错误，请使用 ISO 时间'}), 400

    from modules.oa.tencent_meeting_services import run_feedback_draft_job

    result = run_feedback_draft_job(
        now=now_override or get_business_now(),
        dry_run=bool(payload.get('dry_run')),
    )
    return jsonify({'success': True, 'data': result})


@oa_bp.route('/api/integrations/tencent-meeting/webhook', methods=['GET', 'POST'])
def api_tencent_meeting_webhook():
    from modules.oa.tencent_meeting_services import (
        WEBHOOK_SUCCESS_BODY,
        TencentMeetingError,
        _decode_webhook_payload,
        process_tencent_meeting_webhook,
        validate_tencent_meeting_webhook_signature,
    )

    timestamp = (request.headers.get('timestamp') or '').strip()
    nonce = (request.headers.get('nonce') or '').strip()
    signature = (request.headers.get('signature') or '').strip()
    if request.method == 'GET':
        data_value = (request.args.get('check_str') or '').strip()
    else:
        body = request.get_json(silent=True) or {}
        data_value = str(body.get('data') or '').strip()

    if not timestamp or not nonce or not signature or not data_value:
        return 'invalid webhook request', 400
    try:
        if not validate_tencent_meeting_webhook_signature(
            timestamp=timestamp,
            nonce=nonce,
            signature=signature,
            data_value=data_value,
        ):
            return 'invalid signature', 401
        decoded = _decode_webhook_payload(data_value)
    except TencentMeetingError as exc:
        return str(exc), 503 if '未配置' in str(exc) else 400

    if request.method == 'GET':
        return decoded if isinstance(decoded, str) else json.dumps(decoded, ensure_ascii=False)

    if not isinstance(decoded, dict):
        return 'invalid webhook payload', 400
    process_tencent_meeting_webhook(decoded)
    return WEBHOOK_SUCCESS_BODY


@oa_bp.route('/api/schedules/teachers', methods=['GET'])
@role_required('admin')
def api_list_teachers():
    teachers = User.query.filter(User.role.in_(['teacher', 'admin']), User.is_active == True).all()
    return jsonify({'success': True, 'data': sorted({teacher.display_name for teacher in teachers})})


@oa_bp.route('/api/schedules/students', methods=['GET'])
@role_required('admin')
def api_list_students():
    names = [
        row[0] for row in db.session.query(Enrollment.student_name).distinct().filter(
            Enrollment.student_name.isnot(None),
            Enrollment.student_name != '',
        ).all()
    ]
    return jsonify({'success': True, 'data': sorted(names)})


# ========== 课程进度（基于课表） ==========


@oa_bp.route('/api/schedules/progress', methods=['GET'])
@role_required('admin')
def api_schedule_progress():
    all_schedules = CourseSchedule.query.filter(
        CourseSchedule.is_cancelled == False,
    ).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()

    groups = defaultdict(list)
    for schedule in all_schedules:
        if schedule.enrollment_id:
            key = ('enrollment', schedule.enrollment_id)
        else:
            key = ('legacy', schedule.course_name, schedule.teacher_id or schedule.teacher, schedule.students or '')
        groups[key].append(schedule)

    progress_map = {}
    for schedules in groups.values():
        total = len(schedules)
        if total < 2:
            continue
        for index, schedule in enumerate(schedules, 1):
            progress_map[schedule.id] = {
                'current': index,
                'total': total,
                'is_ending': index > max(total - 3, 0),
            }

    return jsonify({'success': True, 'data': progress_map})


# ========== 待办事项 API ==========


@oa_bp.route('/api/todos', methods=['GET'])
@role_required('admin')
def api_list_todos():
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

    todo_type = request.args.get('todo_type')
    if todo_type:
        query = query.filter(OATodo.todo_type == todo_type)

    todos = _filter_visible_todos(
        query.order_by(OATodo.is_completed, OATodo.priority, OATodo.due_date.asc().nullslast()).all(),
        reconcile_feedback_visibility=True,
    )
    return jsonify({'success': True, 'data': [_build_oa_todo_payload(todo) for todo in todos], 'total': len(todos)})


@oa_bp.route('/api/todos/<int:todo_id>', methods=['GET'])
@role_required('admin')
def api_get_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404
    return jsonify({'success': True, 'data': _build_oa_todo_payload(todo)})


@oa_bp.route('/api/todos', methods=['POST'])
@role_required('admin')
def api_create_todo():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400
    if not data.get('title'):
        return jsonify({'success': False, 'error': '缺少必填字段: title'}), 400
    if data.get('todo_type') and data.get('todo_type') != OATodo.TODO_TYPE_GENERIC:
        return jsonify({'success': False, 'error': '工作流待办不能通过通用待办接口创建'}), 400

    due_date = None
    if data.get('due_date'):
        try:
            due_date = date.fromisoformat(data['due_date'])
        except ValueError:
            return jsonify({'success': False, 'error': '日期格式错误'}), 400

    todo = OATodo(
        title=data['title'],
        description=data.get('description', ''),
        responsible_person=OATodo.normalize_responsible_people(
            data.get('responsible_people', data.get('responsible_person', ''))
        ),
        is_completed=data.get('is_completed', False),
        due_date=due_date,
        priority=data.get('priority', 2),
        notes=data.get('notes', ''),
        schedule_id=data.get('schedule_id'),
        todo_type=OATodo.TODO_TYPE_GENERIC,
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()}), 201


@oa_bp.route('/api/todos/<int:todo_id>', methods=['PUT'])
@role_required('admin')
def api_update_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404
    guarded = _guard_generic_todo_mutation(todo)
    if guarded:
        return guarded

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    if 'due_date' in data:
        if data['due_date']:
            try:
                todo.due_date = date.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'success': False, 'error': '日期格式错误'}), 400
        else:
            todo.due_date = None

    for field in ['title', 'description', 'responsible_person', 'is_completed', 'priority', 'notes', 'schedule_id']:
        if field in data:
            if field == 'responsible_person':
                todo.responsible_person = OATodo.normalize_responsible_people(
                    data.get('responsible_people', data.get('responsible_person', ''))
                )
            else:
                setattr(todo, field, data[field])

    if 'responsible_people' in data and 'responsible_person' not in data:
        todo.responsible_person = OATodo.normalize_responsible_people(data.get('responsible_people', []))

    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@role_required('admin')
def api_delete_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404
    guarded = _guard_generic_todo_mutation(todo)
    if guarded:
        return guarded

    db.session.delete(todo)
    db.session.commit()
    return jsonify({'success': True, 'data': {'id': todo_id}})


@oa_bp.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@role_required('admin')
def api_toggle_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404
    guarded = _guard_generic_todo_mutation(todo)
    if guarded:
        return guarded

    todo.is_completed = not todo.is_completed
    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos/batch', methods=['POST'])
@role_required('admin')
def api_batch_todos():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    action = data.get('action')
    ids = data.get('ids', [])
    if not action or not ids:
        return jsonify({'success': False, 'error': '缺少 action 或 ids 参数'}), 400

    todos = OATodo.query.filter(OATodo.id.in_(ids)).all()
    if not todos:
        return jsonify({'success': False, 'error': '未找到匹配的待办'}), 404
    if any(todo.is_workflow for todo in todos):
        return jsonify({'success': False, 'error': '批量操作仅支持普通待办，工作流待办请使用对应动作'}), 400

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
        return jsonify({'success': False, 'error': f'不支持的操作: {action}'}), 400

    db.session.commit()
    return jsonify({'success': True, 'data': {'action': action, 'affected': len(todos)}})


# ========== Excel 导入 API ==========


@oa_bp.route('/api/import-excel', methods=['POST'])
@role_required('admin')
def api_import_excel():
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': '请上传文件'}), 400
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': '仅支持 .xlsx 或 .xls 文件'}), 400

    try:
        _, summary = apply_schedule_excel_import(
            file,
            uploaded_by=current_user.id if getattr(current_user, 'is_authenticated', False) else None,
        )
        return jsonify({
            'success': True,
            'data': summary,
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'导入失败: {str(exc)}'}), 500


# ========== 仪表盘统计 API ==========


@oa_bp.route('/api/dashboard-stats', methods=['GET'])
@role_required('admin')
def api_dashboard_stats():
    today = get_business_today()
    today_count = CourseSchedule.query.filter(
        CourseSchedule.date == today,
        CourseSchedule.is_cancelled == False,
    ).count()
    pending_count = len(_filter_visible_todos(
        OATodo.query.filter(OATodo.is_completed == False).all(),
        reconcile_feedback_visibility=True,
    ))

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_count = CourseSchedule.query.filter(
        CourseSchedule.date >= monday,
        CourseSchedule.date <= sunday,
        CourseSchedule.is_cancelled == False,
    ).count()

    today_schedules = CourseSchedule.query.filter(
        CourseSchedule.date == today,
        CourseSchedule.is_cancelled == False,
    ).order_by(CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': {
            'today_count': today_count,
            'pending_todos': pending_count,
            'week_count': week_count,
        'today_schedules': [_build_oa_schedule_payload(schedule) for schedule in today_schedules],
        }
    })


# --- OA route overrides and request-scoped helpers ---

from flask import has_request_context
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session


def _schedule_has_open_leave_workflow(schedule):
    if not schedule:
        return False

    approved_leave_ids = [
        row[0]
        for row in db.session.query(LeaveRequest.id).filter(
            LeaveRequest.schedule_id == schedule.id,
            LeaveRequest.status == 'approved',
        ).all()
    ]
    if not approved_leave_ids:
        return False

    return OATodo.query.filter(
        OATodo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP,
        OATodo.leave_request_id.in_(approved_leave_ids),
        OATodo.is_completed == False,
        ~OATodo.workflow_status.in_([
            OATodo.WORKFLOW_STATUS_COMPLETED,
            OATodo.WORKFLOW_STATUS_CANCELLED,
        ]),
    ).count() > 0


def _schedule_locked_by_leave(schedule, updates):
    if not schedule:
        return False

    touched_fields = {field for field in (updates or {})}
    protected_fields = {'date', 'time_start', 'time_end', 'teacher', 'enrollment_id'}
    if not (touched_fields & protected_fields):
        return False

    pending_leave_exists = LeaveRequest.query.filter(
        LeaveRequest.schedule_id == schedule.id,
        LeaveRequest.status == 'pending',
    ).count() > 0
    if pending_leave_exists:
        return True

    return _schedule_has_open_leave_workflow(schedule)


@event.listens_for(Session, 'before_flush')
def _oa_sync_schedule_students(session, flush_context, instances):
    if not has_request_context():
        return
    if request.method not in {'POST', 'PUT'}:
        return
    if not (request.path or '').startswith('/oa/api/schedules'):
        return

    data = request.get_json(silent=True) or {}
    if 'students' in data:
        return

    targets = list(session.new) + list(session.dirty)
    for obj in targets:
        if not isinstance(obj, CourseSchedule):
            continue

        state = inspect(obj)
        if not state.attrs.enrollment_id.history.has_changes():
            continue

        enrollment_id = obj.enrollment_id
        if enrollment_id:
            enrollment = session.get(Enrollment, enrollment_id)
            obj.students = enrollment.student_name if enrollment else ''
        else:
            obj.students = ''
