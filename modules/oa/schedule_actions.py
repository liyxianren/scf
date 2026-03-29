"""Shared schedule action helpers for OA and external integrations."""
from datetime import date, timedelta

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import Enrollment, LeaveRequest, User
from modules.oa.models import CourseSchedule, OATodo
from modules.oa.services import (
    build_schedule_delivery_fields,
    delivery_mode_from_color_tag,
    delivery_mode_label,
    meeting_status_label,
    resolve_schedule_teacher_reference,
    validate_schedule_conflicts,
)


def validate_schedule_conflicts_or_error(**kwargs):
    return validate_schedule_conflicts(**kwargs)


def time_to_minutes(time_str):
    hour, minute = str(time_str).split(':', 1)
    return int(hour) * 60 + int(minute)


def shift_schedule_time_value(time_str, minutes_delta):
    total_minutes = time_to_minutes(time_str)
    shifted_minutes = total_minutes + minutes_delta
    if shifted_minutes < 0 or shifted_minutes > (23 * 60 + 59):
        return None
    return f'{shifted_minutes // 60:02d}:{shifted_minutes % 60:02d}'


def resolve_teacher_or_error(teacher_value):
    teacher_user, _, _, error = resolve_schedule_teacher_reference(teacher_value)
    if error or not teacher_user:
        return None, '授课老师不存在，请先创建教师账号'
    return teacher_user, None


def resolve_teacher_for_reassign(payload):
    teacher_id = payload.get('teacher_id')
    teacher_name = (payload.get('teacher_name') or payload.get('teacher') or '').strip()

    if teacher_id:
        teacher_user = db.session.get(User, teacher_id)
        if (
            teacher_user
            and teacher_user.is_active
            and teacher_user.role in {'teacher', 'admin'}
        ):
            return teacher_user, None
        return None, ('授课老师不存在，请先创建教师账号', 400, 'teacher_not_found')

    if teacher_name:
        teacher_user, error = resolve_teacher_or_error(teacher_name)
        if error:
            return None, (error, 400, 'teacher_not_found')
        return teacher_user, None

    return None, ('缺少 teacher_id 或 teacher_name', 400, 'missing_teacher_reference')


def schedule_locked_by_leave(schedule, updates):
    if not schedule:
        return False
    touched_fields = {field for field in (updates or {})}
    protected_fields = {'date', 'time_start', 'time_end', 'teacher', 'teacher_id', 'enrollment_id'}
    if not (touched_fields & protected_fields):
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

    return OATodo.query.filter(
        OATodo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP,
        OATodo.leave_request_id == latest_leave.id,
        OATodo.is_completed == False,
        ~OATodo.workflow_status.in_([
            OATodo.WORKFLOW_STATUS_COMPLETED,
            OATodo.WORKFLOW_STATUS_CANCELLED,
        ]),
    ).count() > 0


def direct_schedule_enrollment_error(enrollment):
    if not enrollment:
        return None
    if enrollment.status in {'pending_info', 'pending_schedule', 'pending_student_confirm'}:
        return '该报名仍在排课工作流中，请通过工作流发送给学生确认后再生成正式课次'

    from modules.auth.workflow_services import has_open_process_workflow

    if has_open_process_workflow(enrollment_id=enrollment.id):
        return '该报名存在未完成的排课/补课工作流，请先完成工作流再直接改课表'
    return None


def direct_schedule_update_workflow_error(schedule, updates):
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


def normalize_schedule_compare_value(field, value):
    if field in {'teacher', 'time_start', 'time_end', 'course_name', 'students', 'location', 'notes', 'color_tag', 'delivery_mode'}:
        return str(value or '').strip()
    return value


def historical_schedule_mutation_error(schedule, *, proposed_values=None, deleting=False):
    if not schedule or not auth_services.schedule_has_historical_facts(schedule):
        return None
    if deleting:
        return '该课程已产生交付事实，不能直接取消课次'
    changed_fields = {
        field
        for field, value in (proposed_values or {}).items()
        if normalize_schedule_compare_value(field, value)
        != normalize_schedule_compare_value(field, getattr(schedule, field, None))
    }
    if not changed_fields:
        return None
    if changed_fields.issubset({'notes', 'location', 'color_tag', 'delivery_mode'}):
        return None
    return '该课程已产生交付事实，仅允许修改备注、地点或上课方式'


def build_schedule_update_context(schedule, data, *, allow_admin_override=False):
    if not data:
        return None, ('请提供 JSON 数据', 400)
    if not allow_admin_override and schedule_locked_by_leave(schedule, data):
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
    teacher_user, error = resolve_teacher_or_error(next_teacher_name)
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
            return None, ('所选老师与报名绑定老师不一致', 400)
        if not allow_admin_override:
            enrollment_error = direct_schedule_enrollment_error(enrollment)
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
        workflow_error = direct_schedule_update_workflow_error(schedule, data)
        if workflow_error:
            return None, (workflow_error, 400)

        historical_error = historical_schedule_mutation_error(
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

    conflict_error = validate_schedule_conflicts(
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
        'historical_student_profile_id': auth_services._schedule_effective_student_profile_id(schedule),
        'preserve_student_snapshot': auth_services.schedule_has_historical_facts(schedule),
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


def apply_schedule_update_context(schedule, context):
    from modules.auth.workflow_services import sync_schedule_feedback_todo
    from modules.oa.tencent_meeting_services import _extract_schedule_meeting_state, sync_schedule_meeting_after_update

    original_enrollment_id = context['original_enrollment_id']
    enrollment = context['enrollment']
    previous_meeting_state = _extract_schedule_meeting_state(schedule)

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
            auth_services.sync_schedule_student_snapshot(
                schedule,
                enrollment=context.get('original_enrollment'),
                preserve_history=False,
                force=True,
            )
    else:
        auth_services.sync_schedule_student_snapshot(
            schedule,
            enrollment=enrollment,
            preserve_history=False,
        )
    sync_schedule_meeting_after_update(schedule, previous_state=previous_meeting_state)

    db.session.flush()
    if original_enrollment_id:
        original_enrollment = db.session.get(Enrollment, original_enrollment_id)
        if original_enrollment and (not enrollment or original_enrollment.id != enrollment.id):
            auth_services.sync_enrollment_status(original_enrollment)
    if enrollment:
        auth_services.sync_enrollment_status(enrollment)
    sync_schedule_feedback_todo(schedule)
    db.session.commit()
    return schedule


def schedule_factual_edit_block_reason(schedule):
    mutation_probe = {
        'date': schedule.date.isoformat() if schedule.date else None,
        'time_start': schedule.time_start,
        'time_end': schedule.time_end,
        'teacher': schedule.teacher,
        'enrollment_id': schedule.enrollment_id,
        'course_name': schedule.course_name,
        'students': schedule.students,
    }
    if schedule_locked_by_leave(schedule, mutation_probe):
        return '该课程已有请假记录，请通过调课流程处理，不能直接覆盖'
    workflow_error = direct_schedule_update_workflow_error(schedule, mutation_probe)
    if workflow_error:
        return workflow_error
    if getattr(schedule, 'is_cancelled', False):
        return '该课程已取消'
    if auth_services.schedule_has_historical_facts(schedule):
        return '该课程已产生交付事实，仅允许修改备注、地点或上课方式'
    return None


def schedule_cancel_block_reason(schedule):
    if not schedule:
        return '课程不存在'
    if getattr(schedule, 'is_cancelled', False):
        return '该课程已取消'
    if auth_services._schedule_has_started(schedule):
        return '该课程已产生交付事实，不能直接取消课次'
    feedback = getattr(schedule, 'feedback', None)
    if feedback and feedback.status == 'submitted':
        return '该课程已产生交付事实，不能直接取消课次'
    return None


def _append_schedule_note(original_text, appended_text):
    base = (original_text or '').strip()
    extra = (appended_text or '').strip()
    if not extra:
        return base
    return f'{base}\n{extra}'.strip() if base else extra


def cancel_schedule(schedule, *, actor=None, reason=''):
    from modules.auth.workflow_services import (
        _restore_workflow_to_teacher_proposal,
        cancel_schedule_feedback_todo,
        close_process_workflows_for_schedule,
        ensure_leave_makeup_workflow,
    )
    from modules.oa.tencent_meeting_services import sync_schedule_meeting_after_cancel

    block_reason = schedule_cancel_block_reason(schedule)
    if block_reason:
        return None, (block_reason, 400)

    cancel_reason = (reason or '').strip() or '教务取消课次'
    cancelled_at = auth_services.get_business_now()
    actor_id = getattr(actor, 'id', None)
    cancellation_note = (
        f'系统记录：课次已取消。原因：{cancel_reason}'
        + (f'；操作人：{getattr(actor, "display_name", "")}' if getattr(actor, 'display_name', None) else '')
    )

    schedule.is_cancelled = True
    schedule.cancelled_at = cancelled_at
    schedule.cancel_reason = cancel_reason
    schedule.cancelled_by_user_id = actor_id

    for todo in OATodo.query.filter_by(schedule_id=schedule.id).all():
        if todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK:
            cancel_schedule_feedback_todo(schedule.id, reason=cancel_reason)
            continue
        if todo.todo_type in {
            OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
            OATodo.TODO_TYPE_LEAVE_MAKEUP,
        }:
            continue
        if not todo.is_completed:
            todo.is_completed = True
            todo.completed_at = cancelled_at
        todo.notes = _append_schedule_note(todo.notes, cancellation_note)

    closed_workflows = close_process_workflows_for_schedule(
        schedule.id,
        status=OATodo.WORKFLOW_STATUS_CANCELLED,
    )
    for todo in closed_workflows:
        payload = todo.get_payload_data()
        payload['cancel_reason'] = cancel_reason
        todo.set_payload_data(payload)
        todo.notes = _append_schedule_note(todo.notes, cancellation_note)

    original_leave_requests = LeaveRequest.query.filter_by(schedule_id=schedule.id).all()
    for leave_request in original_leave_requests:
        if leave_request.status in {'pending', 'approved'}:
            leave_request.status = 'cancelled'
        leave_request.decision_comment = _append_schedule_note(
            leave_request.decision_comment,
            cancellation_note,
        )

    makeup_leave_requests = LeaveRequest.query.filter_by(makeup_schedule_id=schedule.id).all()
    for leave_request in makeup_leave_requests:
        leave_request.makeup_schedule_id = None
        if leave_request.status == 'approved':
            reopen_reason = f'原补课课次已取消，请老师重新提案。原因：{cancel_reason}'
            workflow = ensure_leave_makeup_workflow(leave_request, actor_user=actor)
            if workflow:
                _restore_workflow_to_teacher_proposal(workflow, reopen_reason, clear_confirmed_slot=False)
                workflow.notes = reopen_reason
                workflow.description = reopen_reason

    linked_enrollment = schedule.enrollment
    sync_schedule_meeting_after_cancel(schedule, cancel_reason=cancel_reason)
    db.session.flush()
    if linked_enrollment:
        auth_services.sync_enrollment_status(linked_enrollment)
    return schedule, None


def build_schedule_preview_payload(schedule, *, overrides=None, teacher_user=None):
    overrides = overrides or {}
    payload = {
        'id': schedule.id,
        'date': schedule.date.isoformat() if schedule.date else None,
        'time_start': schedule.time_start,
        'time_end': schedule.time_end,
        'teacher': schedule.teacher,
        'teacher_id': schedule.teacher_id,
        'course_name': schedule.course_name,
        'students': schedule.students,
        'location': schedule.location,
        'notes': schedule.notes,
        'color_tag': schedule.color_tag,
        'delivery_mode': schedule.delivery_mode,
        'delivery_mode_label': delivery_mode_label(schedule.delivery_mode),
        'meeting_status': schedule.meeting_status,
        'meeting_status_label': meeting_status_label(schedule.meeting_status),
        'meeting_provider': schedule.meeting_provider,
        'meeting_join_url': schedule.meeting_join_url,
        'meeting_external_id': schedule.meeting_external_id,
        'meeting_code': schedule.meeting_code,
        'meeting_password': schedule.meeting_password,
        'meeting_created_at': schedule.meeting_created_at.isoformat() if schedule.meeting_created_at else None,
        'meeting_ended_at': schedule.meeting_ended_at.isoformat() if schedule.meeting_ended_at else None,
        'enrollment_id': schedule.enrollment_id,
    }
    if teacher_user is not None:
        payload['teacher'] = teacher_user.display_name
        payload['teacher_id'] = teacher_user.id

    for field, value in overrides.items():
        if field == 'date' and hasattr(value, 'isoformat'):
            payload['date'] = value.isoformat()
        elif field == 'teacher' and teacher_user is None:
            payload['teacher'] = value
        else:
            payload[field] = value

    current_delivery_mode = (schedule.delivery_mode or '').strip().lower()
    fallback_delivery_mode = (
        current_delivery_mode
        if current_delivery_mode in {'online', 'offline'}
        else delivery_mode_from_color_tag(schedule.color_tag)
    )
    try:
        delivery_fields = build_schedule_delivery_fields(
            delivery_mode=payload.get('delivery_mode'),
            color_tag=payload.get('color_tag'),
            fallback_delivery_mode=fallback_delivery_mode,
            existing_schedule=schedule,
            allow_unknown=True,
        )
        payload.update({
            'delivery_mode': delivery_fields['delivery_mode'],
            'color_tag': delivery_fields['color_tag'],
            'meeting_provider': delivery_fields.get('meeting_provider'),
            'meeting_status': delivery_fields.get('meeting_status'),
            'meeting_join_url': delivery_fields.get('meeting_join_url'),
            'meeting_external_id': delivery_fields.get('meeting_external_id'),
            'meeting_code': delivery_fields.get('meeting_code'),
            'meeting_password': delivery_fields.get('meeting_password'),
            'meeting_created_at': (
                delivery_fields.get('meeting_created_at').isoformat()
                if delivery_fields.get('meeting_created_at') else None
            ),
            'meeting_ended_at': (
                delivery_fields.get('meeting_ended_at').isoformat()
                if delivery_fields.get('meeting_ended_at') else None
            ),
        })
    except ValueError:
        payload['delivery_mode'] = payload.get('delivery_mode') or schedule.delivery_mode or 'unknown'
        payload['color_tag'] = payload.get('color_tag') or schedule.color_tag or 'blue'
    payload['delivery_mode_label'] = delivery_mode_label(payload['delivery_mode'])
    payload['meeting_status_label'] = meeting_status_label(payload.get('meeting_status'))
    return payload


def prepare_quick_shift_payload(schedule, payload):
    try:
        date_shift_days = int(payload.get('date_shift_days', 0) or 0)
        time_shift_minutes = int(payload.get('time_shift_minutes', 0) or 0)
    except (TypeError, ValueError):
        return None, ('快捷调课参数必须是整数', 400)

    if date_shift_days == 0 and time_shift_minutes == 0:
        return None, ('请至少提供一个时间或日期调整量', 400)

    next_time_start = shift_schedule_time_value(schedule.time_start, time_shift_minutes)
    next_time_end = shift_schedule_time_value(schedule.time_end, time_shift_minutes)
    if not next_time_start or not next_time_end:
        return None, ('快捷调课不能跨天，请改用完整编辑', 400)

    next_date = schedule.date + timedelta(days=date_shift_days)
    return {
        'date': next_date.isoformat(),
        'time_start': next_time_start,
        'time_end': next_time_end,
    }, {
        'date_shift_days': date_shift_days,
        'time_shift_minutes': time_shift_minutes,
    }


def _build_context_after_payload(schedule, context):
    return build_schedule_preview_payload(
        schedule,
        overrides={
            'date': context['next_date'],
            'time_start': context['next_time_start'],
            'time_end': context['next_time_end'],
            'course_name': context['next_course_name'],
            'students': context['next_students'],
            'location': context['next_location'],
            'notes': context['next_notes'],
            'delivery_mode': context['delivery_fields']['delivery_mode'],
            'color_tag': context['delivery_fields']['color_tag'],
            'enrollment_id': context['next_enrollment_id'],
        },
        teacher_user=context['teacher_user'],
    )


def preview_schedule_update(schedule, data, *, allow_admin_override=False, error_code=None):
    before_payload = build_schedule_preview_payload(schedule)
    context, error = build_schedule_update_context(
        schedule,
        data,
        allow_admin_override=allow_admin_override,
    )
    if error:
        after_payload = build_schedule_preview_payload(
            schedule,
            overrides=data or {},
        )
        result = {
            'success': True,
            'status_code': 200,
            'data': {
                'before': before_payload,
                'after': after_payload,
                'can_apply': False,
                'block_reason': error[0],
                'conflict_summary': error[0],
            },
        }
        if error_code:
            result['code'] = error_code
        return result

    return {
        'success': True,
        'status_code': 200,
        'data': {
            'before': before_payload,
            'after': _build_context_after_payload(schedule, context),
            'can_apply': True,
            'block_reason': None,
            'conflict_summary': None,
        },
    }


def apply_schedule_update(schedule, data, *, allow_admin_override=False):
    context, error = build_schedule_update_context(
        schedule,
        data,
        allow_admin_override=allow_admin_override,
    )
    if error:
        return {
            'success': False,
            'status_code': error[1],
            'error': error[0],
        }

    apply_schedule_update_context(schedule, context)
    return {
        'success': True,
        'status_code': 200,
        'data': {
            'schedule': build_schedule_preview_payload(schedule),
            'schedule_id': schedule.id,
        },
    }


def quick_shift_schedule(schedule, *, date_shift_days=0, time_shift_minutes=0, allow_admin_override=False):
    update_payload, meta_or_error = prepare_quick_shift_payload(
        schedule,
        {
            'date_shift_days': date_shift_days,
            'time_shift_minutes': time_shift_minutes,
        },
    )
    if update_payload is None:
        return {
            'success': False,
            'status_code': meta_or_error[1],
            'error': meta_or_error[0],
        }

    result = apply_schedule_update(
        schedule,
        update_payload,
        allow_admin_override=allow_admin_override,
    )
    if result.get('success'):
        result.setdefault('data', {})
        result['data']['meta'] = meta_or_error
        result['data']['schedule_id'] = schedule.id
    return result


def preview_schedule_reassign_teacher(schedule, payload, *, allow_admin_override=False):
    if schedule.enrollment_id:
        return {
            'success': True,
            'status_code': 200,
            'code': 'reassign_teacher_requires_unbound_schedule',
            'data': {
                'before': build_schedule_preview_payload(schedule),
                'after': build_schedule_preview_payload(schedule),
                'can_apply': False,
                'block_reason': '当前仅支持未绑定报名的课次换老师',
                'conflict_summary': None,
            },
        }

    teacher_user, error = resolve_teacher_for_reassign(payload or {})
    if error:
        return preview_schedule_update(
            schedule,
            {},
            allow_admin_override=allow_admin_override,
            error_code=error[2],
        ) if error[2] == 'missing_teacher_reference' else {
            'success': True,
            'status_code': 200,
            'code': error[2],
            'data': {
                'before': build_schedule_preview_payload(schedule),
                'after': build_schedule_preview_payload(schedule),
                'can_apply': False,
                'block_reason': error[0],
                'conflict_summary': error[0],
            },
        }

    return preview_schedule_update(
        schedule,
        {'teacher': teacher_user.display_name},
        allow_admin_override=allow_admin_override,
    )


def apply_schedule_reassign_teacher(schedule, payload, *, allow_admin_override=False):
    if schedule.enrollment_id:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前仅支持未绑定报名的课次换老师',
            'code': 'reassign_teacher_requires_unbound_schedule',
        }

    teacher_user, error = resolve_teacher_for_reassign(payload or {})
    if error:
        return {
            'success': False,
            'status_code': error[1],
            'error': error[0],
            'code': error[2],
        }

    return apply_schedule_update(
        schedule,
        {'teacher': teacher_user.display_name},
        allow_admin_override=allow_admin_override,
    )
