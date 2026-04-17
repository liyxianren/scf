import json
from datetime import date, datetime

from sqlalchemy import or_

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import ChatMessage, Enrollment, LeaveRequest
from modules.oa.models import CourseSchedule, OATodo

MAKEUP_FEEDBACK_PREFIX = '[补课反馈]'
MAKEUP_PLAN_PREFIX = '[补课方案]'
PROCESS_WORKFLOW_TYPES = {
    OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
    OATodo.TODO_TYPE_LEAVE_MAKEUP,
}


def _copy_jsonable(value):
    if value is None:
        return None
    return json.loads(json.dumps(value, ensure_ascii=False))


def _now():
    return auth_services.get_business_now()


def _today():
    return auth_services.get_business_today()


def _set_todo_state(todo, workflow_status):
    todo.workflow_status = workflow_status
    todo.is_completed = workflow_status in {
        OATodo.WORKFLOW_STATUS_COMPLETED,
        OATodo.WORKFLOW_STATUS_CANCELLED,
    }
    todo.completed_at = _now() if todo.is_completed else None


def _load_enrollment_confirmed_slot(enrollment):
    if not enrollment or not enrollment.confirmed_slot:
        return None
    try:
        raw_plan = json.loads(enrollment.confirmed_slot)
    except (TypeError, ValueError):
        return None
    return auth_services.normalize_plan(raw_plan, enrollment)


def _payload_rejections(payload):
    rejections = payload.get('rejections') or []
    return rejections if isinstance(rejections, list) else []


def _append_rejection(payload, user, message_text):
    rejections = _payload_rejections(payload)
    message = (message_text or '').strip() or '学生对当前方案有疑问，请重新调整。'
    rejections.append({
        'message': message,
        'reason': message,
        'actor_user_id': getattr(user, 'id', None),
        'actor_name': getattr(user, 'display_name', None),
        'created_at': _now().isoformat(),
    })
    payload['rejections'] = rejections
    payload['latest_rejection'] = rejections[-1]
    return rejections


def _append_system_rejection(payload, message_text):
    rejections = _payload_rejections(payload)
    message = (message_text or '').strip() or '当前方案已失效，请重新提案'
    rejection = {
        'message': message,
        'reason': message,
        'actor_user_id': None,
        'actor_name': 'system',
        'source': 'system',
        'created_at': _now().isoformat(),
    }
    rejections.append(rejection)
    payload['rejections'] = rejections
    payload['latest_rejection'] = rejection
    return rejection


def _teacher_admin_responsible_people(enrollment):
    names = []
    teacher = getattr(enrollment, 'teacher', None)
    if teacher and teacher.display_name:
        names.append(teacher.display_name)
    names.append('教务')
    return OATodo.normalize_responsible_people(names)


def _student_responsible_people(enrollment):
    names = [enrollment.student_name] if enrollment and enrollment.student_name else []
    return OATodo.normalize_responsible_people(names)


def _workflow_target_teacher_id(todo):
    if todo.enrollment and todo.enrollment.teacher_id:
        return todo.enrollment.teacher_id
    if todo.schedule and todo.schedule.teacher_id:
        return todo.schedule.teacher_id
    if todo.leave_request and todo.leave_request.schedule and todo.leave_request.schedule.teacher_id:
        return todo.leave_request.schedule.teacher_id
    payload = todo.get_payload_data() or {}
    context = payload.get('context') or {}
    return context.get('teacher_id')


def _workflow_target_teacher_name(todo):
    if todo.enrollment and todo.enrollment.teacher:
        return todo.enrollment.teacher.display_name
    if todo.schedule and todo.schedule.teacher:
        return todo.schedule.teacher
    if todo.leave_request and todo.leave_request.schedule and todo.leave_request.schedule.teacher:
        return todo.leave_request.schedule.teacher
    payload = todo.get_payload_data() or {}
    context = payload.get('context') or {}
    return context.get('teacher_name')


def _actor_can_submit_teacher_workflow(actor, todo):
    if (
        todo
        and todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and todo.enrollment
        and auth_services.teacher_auto_accept_enabled(todo.enrollment.teacher or todo.enrollment.teacher_id)
        and not auth_services.enrollment_requires_teacher_confirmation(todo.enrollment)
    ):
        return False
    return auth_services._schedule_matches_teacher_actor(
        actor,
        teacher_id=_workflow_target_teacher_id(todo),
        teacher_name=_workflow_target_teacher_name(todo),
    )


def _student_preference_context(enrollment):
    profile = getattr(enrollment, 'student_profile', None)
    profile_payload = profile.to_dict() if profile else {}
    available_slots = profile_payload.get('available_slots') or []
    excluded_dates = profile_payload.get('excluded_dates') or []
    intake_note = (profile_payload.get('notes') or '').strip() or None
    availability_intake = auth_services._enrollment_json_field(getattr(enrollment, 'availability_intake', None)) or {}
    candidate_slot_pool = auth_services._enrollment_json_field(getattr(enrollment, 'candidate_slot_pool', None)) or []
    recommended_bundle = auth_services._enrollment_json_field(getattr(enrollment, 'recommended_bundle', None)) or None
    risk_assessment = auth_services._enrollment_json_field(getattr(enrollment, 'risk_assessment', None)) or {}
    teacher_context = auth_services._teacher_work_context(getattr(enrollment, 'teacher', None) or enrollment.teacher_id)
    teacher_context['requires_teacher_proposal'] = auth_services.enrollment_requires_teacher_confirmation(enrollment)

    return {
        **teacher_context,
        'student_available_slots': available_slots,
        'student_available_slots_summary': auth_services._summarize_available_slots(available_slots),
        'student_excluded_dates': excluded_dates,
        'student_excluded_dates_summary': auth_services._summarize_excluded_dates(excluded_dates),
        'student_intake_note': intake_note,
        'availability_intake': availability_intake,
        'availability_intake_summary': availability_intake.get('summary'),
        'candidate_slot_pool': candidate_slot_pool,
        'recommended_bundle': recommended_bundle,
        'risk_assessment': risk_assessment,
        'sessions_per_week_required': max(int(getattr(enrollment, 'sessions_per_week', 1) or 1), 1),
        'target_finish_date': enrollment.target_finish_date.isoformat() if getattr(enrollment, 'target_finish_date', None) else None,
        'delivery_urgency': getattr(enrollment, 'delivery_urgency', 'normal'),
    }


def _enrollment_replan_uses_teacher_queue(enrollment):
    return bool(enrollment) and auth_services.enrollment_requires_teacher_confirmation(enrollment)


def _enrollment_replan_status(enrollment):
    if _enrollment_replan_uses_teacher_queue(enrollment):
        return OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
    return OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW


def _enrollment_replan_responsible_people(enrollment):
    if _enrollment_replan_uses_teacher_queue(enrollment):
        return _teacher_admin_responsible_people(enrollment)
    return '教务'


def _seed_full_time_enrollment_proposal(payload, enrollment, *, note_text=None):
    context = payload.get('context') or {}
    recommended_bundle = auth_services.normalize_plan(context.get('recommended_bundle'), enrollment)
    risk_assessment = context.get('risk_assessment') or {}
    payload['recommended_bundle'] = recommended_bundle
    payload['candidate_slot_pool'] = context.get('candidate_slot_pool') or []
    payload['risk_assessment'] = risk_assessment
    payload.pop('sent_to_student_at', None)
    payload.pop('sent_to_student_by', None)
    payload.pop('sent_to_student_by_name', None)

    if recommended_bundle:
        proposal = _copy_jsonable(recommended_bundle)
        proposal['note'] = (
            (note_text or '').strip()
            or proposal.get('note')
            or 'AI 已按全职老师统一工作时段生成推荐方案，待教务复核。'
        )
        proposal['warnings'] = list(dict.fromkeys(risk_assessment.get('warnings') or []))
        proposal['quota_required'] = max(int(getattr(enrollment, 'sessions_per_week', 1) or 1), 1)
        proposal['quota_selected'] = len(proposal.get('weekly_slots') or [])
        payload['current_proposal'] = proposal
        payload['proposal_note'] = proposal.get('note')
        payload['proposal_warnings'] = proposal.get('warnings') or []
    else:
        payload['current_proposal'] = None
        payload['proposal_note'] = (note_text or '').strip() or None
        payload['proposal_warnings'] = list(dict.fromkeys(risk_assessment.get('warnings') or []))
    return payload


def _workflow_base_payload(todo, payload=None):
    data = todo.get_payload_data()
    if payload:
        data.update(payload)
    return data


def _enrollment_summary(enrollment):
    if not enrollment:
        return None
    return {
        'id': enrollment.id,
        'student_name': enrollment.student_name,
        'course_name': enrollment.course_name,
        'teacher_id': enrollment.teacher_id,
        'teacher_name': enrollment.teacher.display_name if enrollment.teacher else None,
        'status': enrollment.status,
    }


def _schedule_summary(schedule):
    if not schedule:
        return None
    return {
        'id': schedule.id,
        'date': schedule.date.isoformat() if schedule.date else None,
        'time_start': schedule.time_start,
        'time_end': schedule.time_end,
        'course_name': schedule.course_name,
        'teacher_id': schedule.teacher_id,
        'teacher_name': schedule.teacher,
        'students': schedule.students,
        'enrollment_id': schedule.enrollment_id,
    }


def _leave_request_summary(leave_request):
    if not leave_request:
        return None
    payload = leave_request.to_dict()
    payload.update({
        'original_schedule_summary': auth_services._summarize_schedule_summary(leave_request.schedule),
        'makeup_preference_summary': auth_services._summarize_makeup_preferences(
            payload.get('makeup_available_slots'),
            payload.get('makeup_excluded_dates'),
            payload.get('makeup_preference_note'),
        ),
    })
    return payload


def _process_workflow_query():
    return OATodo.query.filter(
        OATodo.todo_type.in_(tuple(PROCESS_WORKFLOW_TYPES)),
        OATodo.is_completed == False,
        ~OATodo.workflow_status.in_([
            OATodo.WORKFLOW_STATUS_COMPLETED,
            OATodo.WORKFLOW_STATUS_CANCELLED,
        ]),
    )


def user_can_access_workflow_todo(user, todo):
    if not user or not getattr(user, 'is_authenticated', False) or not todo:
        return False
    if user.role == 'admin':
        return True

    enrollment = todo.enrollment
    if user.role == 'teacher':
        if enrollment and enrollment.teacher_id == user.id:
            return True
        if todo.schedule and auth_services._schedule_matches_teacher_actor(user, todo.schedule):
            return True
        return bool(
            todo.leave_request
            and todo.leave_request.schedule
            and auth_services._schedule_matches_teacher_actor(user, todo.leave_request.schedule)
        )

    if user.role == 'student':
        if todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK:
            return False
        profile = getattr(user, 'student_profile', None)
        return bool(profile and enrollment and enrollment.student_profile_id == profile.id)

    return False


def list_workflow_todos_for_user(user, *, status='open', todo_type=None, enrollment_id=None):
    query = OATodo.query.filter(OATodo.todo_type != OATodo.TODO_TYPE_GENERIC)
    if todo_type:
        query = query.filter(OATodo.todo_type == todo_type)
    if enrollment_id:
        query = query.filter(OATodo.enrollment_id == enrollment_id)

    if status == 'open':
        query = query.filter(OATodo.is_completed == False)
    elif status == 'completed':
        query = query.filter(OATodo.is_completed == True)

    if not user or not getattr(user, 'is_authenticated', False):
        return []

    if user.role == 'teacher':
        teacher_schedule_filter = auth_services._teacher_schedule_identity_filter(CourseSchedule, user)
        query = query.filter(
            or_(
                OATodo.enrollment.has(Enrollment.teacher_id == user.id),
                OATodo.schedule.has(teacher_schedule_filter),
                OATodo.leave_request.has(LeaveRequest.schedule.has(teacher_schedule_filter)),
            )
        )
    elif user.role == 'student':
        profile = getattr(user, 'student_profile', None)
        if not profile:
            return []
        query = query.filter(
            OATodo.todo_type.in_(tuple(PROCESS_WORKFLOW_TYPES)),
            OATodo.enrollment.has(Enrollment.student_profile_id == profile.id),
        )

    todos = query.order_by(
        OATodo.is_completed,
        OATodo.priority,
        OATodo.due_date.is_(None).asc(),
        OATodo.due_date.asc(),
        OATodo.created_at.desc(),
    ).all()
    visible_todos = []
    changed = False
    for todo in todos:
        if reconcile_stale_workflow_todo(todo):
            changed = True
        if workflow_todo_stale_reason(todo):
            continue
        if (
            todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK
            and not auth_services.schedule_requires_course_feedback(todo.schedule)
        ):
            if not todo.is_completed:
                cancel_schedule_feedback_todo(
                    todo.schedule_id,
                    reason=auth_services.get_course_feedback_skip_reason(todo.schedule) or '',
                )
                changed = True
            continue
        visible_todos.append(todo)
    if changed:
        db.session.commit()
    return visible_todos


def get_workflow_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo or not todo.is_workflow:
        return None
    if reconcile_stale_workflow_todo(todo):
        db.session.commit()
    if workflow_todo_stale_reason(todo):
        return None
    return todo


def _todo_type_label(todo_type):
    return {
        OATodo.TODO_TYPE_GENERIC: '普通待办',
        OATodo.TODO_TYPE_ENROLLMENT_REPLAN: '排课重排',
        OATodo.TODO_TYPE_LEAVE_MAKEUP: '补课安排',
        OATodo.TODO_TYPE_SCHEDULE_FEEDBACK: '课后反馈',
    }.get(todo_type, todo_type or OATodo.TODO_TYPE_GENERIC)


def _workflow_status_label(todo_type, workflow_status):
    if todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK and workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL:
        return '待老师提交反馈'
    return {
        OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL: '待老师提案',
        OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW: '待教务处理',
        OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM: '待学生确认',
        OATodo.WORKFLOW_STATUS_COMPLETED: '已完成',
        OATodo.WORKFLOW_STATUS_CANCELLED: '已取消',
    }.get(workflow_status, workflow_status or '')


def _latest_rejection_text(workflow_payload):
    latest_rejection = workflow_payload.get('latest_rejection') or {}
    return (latest_rejection.get('message') or latest_rejection.get('reason') or '').strip() or None


def _proposal_note(workflow_payload):
    current_proposal = workflow_payload.get('current_proposal') or {}
    return (
        (workflow_payload.get('proposal_note') or '').strip()
        or (current_proposal.get('note') or '').strip()
        or None
    )


def _proposal_warnings(workflow_payload):
    current_proposal = workflow_payload.get('current_proposal') or {}
    warnings = workflow_payload.get('proposal_warnings')
    if warnings is None:
        warnings = current_proposal.get('warnings')
    if not isinstance(warnings, list):
        return []
    return [str(item).strip() for item in warnings if str(item).strip()]


def _proposal_warning_summary(workflow_payload):
    warnings = _proposal_warnings(workflow_payload)
    if not warnings:
        return None
    return '；'.join(warnings)


def _context_summary(todo_type, workflow_payload):
    context = workflow_payload.get('context') or {}
    parts = []

    if todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP:
        original_schedule_summary = auth_services._summarize_schedule_summary(context.get('original_schedule'))
        if original_schedule_summary:
            parts.append(f'原请假课次：{original_schedule_summary}')
        makeup_preference_summary = (
            context.get('makeup_preference_summary')
            or auth_services._summarize_makeup_preferences(
                context.get('makeup_available_slots'),
                context.get('makeup_excluded_dates'),
                context.get('makeup_preference_note'),
            )
        )
        if makeup_preference_summary:
            parts.append(makeup_preference_summary)
    elif todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        previous_plan_summary = auth_services._summarize_plan(workflow_payload.get('previous_confirmed_slot'))
        if previous_plan_summary:
            parts.append(f'上次方案：{previous_plan_summary}')
        student_available_slots_summary = (
            context.get('student_available_slots_summary')
            or auth_services._summarize_available_slots(context.get('student_available_slots'))
        )
        if student_available_slots_summary:
            parts.append(f'学生长期可上课：{student_available_slots_summary}')
        student_excluded_dates_summary = (
            context.get('student_excluded_dates_summary')
            or auth_services._summarize_excluded_dates(context.get('student_excluded_dates'))
        )
        if student_excluded_dates_summary:
            parts.append(f'学生禁排日期：{student_excluded_dates_summary}')
        availability_intake_summary = context.get('availability_intake_summary')
        if availability_intake_summary:
            parts.append(f'学生表达：{availability_intake_summary}')
        sessions_per_week_required = context.get('sessions_per_week_required')
        if sessions_per_week_required:
            parts.append(f'每周目标：{sessions_per_week_required} 节')
        target_finish_date = context.get('target_finish_date')
        if target_finish_date:
            parts.append(f'目标完成日：{target_finish_date}')
        risk_assessment = context.get('risk_assessment') or {}
        if risk_assessment.get('summary'):
            parts.append(f'风险提示：{risk_assessment.get("summary")}')
    elif todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK:
        schedule_summary = auth_services._summarize_schedule_summary(context.get('schedule'))
        if schedule_summary:
            parts.append(f'课次：{schedule_summary}')

    return ' · '.join(parts) or None


def build_workflow_todo_payload(todo, actor=None):
    if not todo:
        return None

    payload = todo.to_dict()
    workflow_payload = _copy_jsonable(todo.get_payload_data()) or {}
    enrollment = todo.enrollment
    schedule = todo.schedule
    leave_request = todo.leave_request
    latest_rejection_text = _latest_rejection_text(workflow_payload)
    proposal_note = _proposal_note(workflow_payload)
    proposal_warnings = _proposal_warnings(workflow_payload)
    proposal_warning_summary = _proposal_warning_summary(workflow_payload)
    current_plan_session_dates = (
        ((workflow_payload.get('current_proposal') or {}).get('session_dates'))
        or ((workflow_payload.get('previous_confirmed_slot') or {}).get('session_dates'))
        or []
    )
    current_plan_summary = (
        auth_services._summarize_plan(workflow_payload.get('current_proposal'))
        or auth_services._summarize_plan(workflow_payload.get('previous_confirmed_slot'))
    )
    previous_plan_summary = auth_services._summarize_plan(workflow_payload.get('previous_confirmed_slot'))
    original_schedule_summary = auth_services._summarize_schedule_summary(
        (workflow_payload.get('context') or {}).get('original_schedule')
    )
    context_summary = _context_summary(todo.todo_type, workflow_payload)
    context = workflow_payload.get('context') or {}
    teacher_context = {
        'teacher_work_mode': context.get('teacher_work_mode'),
        'teacher_work_mode_label': context.get('teacher_work_mode_label'),
        'default_working_template': context.get('default_working_template') or [],
        'default_working_template_summary': context.get('default_working_template_summary'),
        'using_company_template': bool(context.get('using_company_template')),
        'availability_source': context.get('availability_source'),
        'teacher_auto_accept_enabled': bool(context.get('teacher_auto_accept_enabled')),
        'requires_teacher_proposal': bool(context.get('requires_teacher_proposal')),
    }
    quota_required = context.get('sessions_per_week_required') or (todo.enrollment.sessions_per_week if todo.enrollment else 1)
    recommended_bundle = (
        workflow_payload.get('recommended_bundle')
        or context.get('recommended_bundle')
    )
    candidate_slot_pool = workflow_payload.get('candidate_slot_pool') or context.get('candidate_slot_pool') or []
    risk_assessment = workflow_payload.get('risk_assessment') or context.get('risk_assessment') or {}

    workflow_payload.update({
        'context_summary': context_summary,
        'latest_rejection_text': latest_rejection_text,
        'proposal_note': proposal_note,
        'proposal_warnings': proposal_warnings,
        'proposal_warning_summary': proposal_warning_summary,
        'current_plan_session_dates': current_plan_session_dates,
        'session_preview_lines': auth_services._session_preview_lines(current_plan_session_dates),
        'current_plan_summary': current_plan_summary,
        'previous_plan_summary': previous_plan_summary,
        'original_schedule_summary': original_schedule_summary,
        'recommended_bundle': recommended_bundle,
        'candidate_slot_pool': candidate_slot_pool,
        'risk_assessment': risk_assessment,
        'quota_required': quota_required,
    })

    payload.update({
        'payload': workflow_payload,
        'enrollment': _enrollment_summary(enrollment),
        'schedule': _schedule_summary(schedule),
        'leave_request': _leave_request_summary(leave_request),
        'latest_rejection': workflow_payload.get('latest_rejection'),
        'latest_rejection_text': latest_rejection_text,
        'revision': int(workflow_payload.get('revision') or 0),
        'current_proposal': workflow_payload.get('current_proposal'),
        'proposal_note': proposal_note,
        'proposal_warnings': proposal_warnings,
        'proposal_warning_summary': proposal_warning_summary,
        'current_plan_session_dates': current_plan_session_dates,
        'session_preview_lines': auth_services._session_preview_lines(current_plan_session_dates),
        'current_plan_summary': current_plan_summary,
        'previous_plan_summary': previous_plan_summary,
        'original_schedule_summary': original_schedule_summary,
        'context_summary': context_summary,
        'previous_confirmed_slot': workflow_payload.get('previous_confirmed_slot'),
        'context': context,
        'recommended_bundle': recommended_bundle,
        'candidate_slot_pool': candidate_slot_pool,
        'risk_assessment': risk_assessment,
        'quota_required': quota_required,
        **teacher_context,
        'student_name': enrollment.student_name if enrollment else workflow_payload.get('context', {}).get('student_name'),
        'course_name': (
            enrollment.course_name
            if enrollment
            else (schedule.course_name if schedule else workflow_payload.get('context', {}).get('course_name'))
        ),
        'teacher_name': (
            enrollment.teacher.display_name
            if enrollment and enrollment.teacher
            else (schedule.teacher if schedule else workflow_payload.get('context', {}).get('teacher_name'))
        ),
        'teacher_id': (
            enrollment.teacher_id
            if enrollment and enrollment.teacher_id
            else (schedule.teacher_id if schedule else workflow_payload.get('context', {}).get('teacher_id'))
        ),
        'todo_type_label': _todo_type_label(todo.todo_type),
        'workflow_status_label': _workflow_status_label(todo.todo_type, todo.workflow_status),
        'can_teacher_propose': False,
        'can_admin_send': False,
        'can_admin_return_to_teacher': False,
        'can_student_confirm': False,
        'can_student_reject': False,
        'can_submit_feedback': False,
    })
    payload.update(auth_services.get_workflow_next_action_meta(todo, payload=workflow_payload))

    if actor and getattr(actor, 'is_authenticated', False) and user_can_access_workflow_todo(actor, todo):
        payload['can_teacher_propose'] = (
            _actor_can_submit_teacher_workflow(actor, todo)
            and todo.todo_type in {
                OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
                OATodo.TODO_TYPE_LEAVE_MAKEUP,
            }
            and todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
        )
        payload['can_submit_feedback'] = (
            todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK
            and schedule is not None
            and auth_services.user_can_submit_feedback(actor, schedule)
        )
        if actor.role == 'teacher':
            pass
        elif actor.role == 'admin':
            payload['can_admin_send'] = todo.todo_type in {
                OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
                OATodo.TODO_TYPE_LEAVE_MAKEUP,
            } and todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW
            payload['can_admin_return_to_teacher'] = todo.todo_type in {
                OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
                OATodo.TODO_TYPE_LEAVE_MAKEUP,
            } and todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW
        elif actor.role == 'student':
            payload['can_student_confirm'] = todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM
            payload['can_student_reject'] = todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM

    payload['current_stage_label'] = {
        OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL: '待老师提案',
        OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW: '待教务发送给学生',
        OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM: '待学生确认',
        OATodo.WORKFLOW_STATUS_COMPLETED: '已完成',
        OATodo.WORKFLOW_STATUS_CANCELLED: '已取消',
    }.get(todo.workflow_status, payload.get('next_action_label'))
    payload['next_step_hint'] = {
        OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL: '老师提交建议后，教务会继续微调并发送给学生。',
        OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW: (
            'AI 已按全职老师统一工作时段生成方案，教务复核后会发给学生。'
            if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and teacher_context.get('teacher_auto_accept_enabled')
            else '教务确认后会把方案发给学生，或退回老师重新提案。'
        ),
        OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM: (
            '学生确认后补课时间会正式生效。'
            if todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP
            else '学生确认后系统会生成正式课表。'
        ),
    }.get(todo.workflow_status)
    return payload


def get_enrollment_workflow_todos(enrollment_id, actor=None, *, include_closed=False):
    query = OATodo.query.filter(
        OATodo.todo_type != OATodo.TODO_TYPE_GENERIC,
        OATodo.enrollment_id == enrollment_id,
    )
    if not include_closed:
        query = query.filter(OATodo.is_completed == False)
    if actor and getattr(actor, 'role', None) == 'student':
        query = query.filter(OATodo.todo_type.in_(tuple(PROCESS_WORKFLOW_TYPES)))
    todos = query.order_by(OATodo.created_at.desc()).all()
    return [build_workflow_todo_payload(todo, actor) for todo in todos]


def get_schedule_workflow_todos(schedule_id, actor=None, *, include_closed=False):
    query = OATodo.query.filter(
        OATodo.todo_type != OATodo.TODO_TYPE_GENERIC,
        OATodo.schedule_id == schedule_id,
    )
    if not include_closed:
        query = query.filter(OATodo.is_completed == False)
    if actor and getattr(actor, 'role', None) == 'student':
        query = query.filter(OATodo.todo_type.in_(tuple(PROCESS_WORKFLOW_TYPES)))
    todos = query.order_by(OATodo.created_at.desc()).all()
    visible_todos = []
    changed = False
    for todo in todos:
        if (
            todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK
            and not auth_services.schedule_requires_course_feedback(todo.schedule)
        ):
            if not todo.is_completed:
                cancel_schedule_feedback_todo(
                    todo.schedule_id,
                    reason=auth_services.get_course_feedback_skip_reason(todo.schedule) or '',
                )
                changed = True
            continue
        visible_todos.append(todo)
    if changed:
        db.session.commit()
    return [build_workflow_todo_payload(todo, actor) for todo in visible_todos]


def get_leave_request_workflow(leave_request_id, actor=None):
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        leave_request_id=leave_request_id,
    ).order_by(OATodo.created_at.desc()).first()
    return build_workflow_todo_payload(todo, actor) if todo else None


def has_open_process_workflow(*, schedule_id=None, enrollment_id=None, exclude_todo_id=None):
    query = _process_workflow_query()
    if exclude_todo_id:
        query = query.filter(OATodo.id != exclude_todo_id)

    clauses = []
    if schedule_id:
        clauses.append(OATodo.schedule_id == schedule_id)
    if enrollment_id:
        clauses.append(OATodo.enrollment_id == enrollment_id)
    if not clauses:
        return False
    return query.filter(or_(*clauses)).count() > 0


def has_open_enrollment_replan_workflow(enrollment_id, *, exclude_todo_id=None):
    if not enrollment_id:
        return False
    query = OATodo.query.filter(
        OATodo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        OATodo.enrollment_id == enrollment_id,
        OATodo.is_completed == False,
        ~OATodo.workflow_status.in_([
            OATodo.WORKFLOW_STATUS_COMPLETED,
            OATodo.WORKFLOW_STATUS_CANCELLED,
        ]),
    )
    if exclude_todo_id:
        query = query.filter(OATodo.id != exclude_todo_id)
    return query.count() > 0


def has_open_workflow(*, schedule_id=None, enrollment_id=None, exclude_todo_id=None):
    query = OATodo.query.filter(
        OATodo.todo_type != OATodo.TODO_TYPE_GENERIC,
        OATodo.is_completed == False,
        ~OATodo.workflow_status.in_([
            OATodo.WORKFLOW_STATUS_COMPLETED,
            OATodo.WORKFLOW_STATUS_CANCELLED,
        ]),
    )
    if exclude_todo_id:
        query = query.filter(OATodo.id != exclude_todo_id)

    clauses = []
    if schedule_id:
        clauses.append(OATodo.schedule_id == schedule_id)
    if enrollment_id:
        clauses.append(OATodo.enrollment_id == enrollment_id)
    if not clauses:
        return False
    return query.filter(or_(*clauses)).count() > 0


def _ensure_enrollment_replan_workflow(enrollment, *, actor_user=None):
    initial_status = _enrollment_replan_status(enrollment)
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        enrollment_id=enrollment.id,
    ).order_by(OATodo.created_at.desc()).first()
    if not todo:
        todo = OATodo(
            title=f'排课重排：{enrollment.student_name} · {enrollment.course_name}',
            description=(
                '学生退回了当前排课方案，等待老师和教务重新处理。'
                if initial_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
                else '学生退回了当前排课方案，AI 已按全职老师工作模板重算，等待教务复核。'
            ),
            responsible_person=_enrollment_replan_responsible_people(enrollment),
            priority=1,
            due_date=_today(),
            todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
            workflow_status=initial_status,
            enrollment_id=enrollment.id,
            created_by=getattr(actor_user, 'id', None),
        )
        db.session.add(todo)
        db.session.flush()
    return todo


def ensure_enrollment_replan_workflow(enrollment, *, rejection_text='', actor_user=None):
    auth_services.refresh_enrollment_scheduling_ai_state(enrollment)
    todo = _ensure_enrollment_replan_workflow(enrollment, actor_user=actor_user)
    payload = _workflow_base_payload(todo, {
        'context': {
            'student_name': enrollment.student_name,
            'course_name': enrollment.course_name,
            'teacher_name': enrollment.teacher.display_name if enrollment.teacher else '',
            **_student_preference_context(enrollment),
        },
        'previous_confirmed_slot': _copy_jsonable(_load_enrollment_confirmed_slot(enrollment)),
    })

    revision = int(payload.get('revision') or 0) + 1
    payload['revision'] = revision
    _append_rejection(payload, actor_user, rejection_text)
    payload.setdefault('current_proposal', None)
    if _enrollment_replan_uses_teacher_queue(enrollment):
        payload['current_proposal'] = None
        payload['proposal_note'] = None
        payload['proposal_warnings'] = []
        payload.pop('sent_to_student_at', None)
        payload.pop('sent_to_student_by', None)
        payload.pop('sent_to_student_by_name', None)
        todo.description = rejection_text or '学生对当前排课方案有疑问，等待老师重新提案。'
    else:
        _seed_full_time_enrollment_proposal(payload, enrollment)
        todo.description = rejection_text or '学生对当前排课方案有疑问，AI 已按全职老师工作模板重算，等待教务复核。'
    todo.notes = rejection_text or todo.notes
    todo.responsible_person = _enrollment_replan_responsible_people(enrollment)
    _set_todo_state(todo, _enrollment_replan_status(enrollment))
    todo.set_payload_data(payload)
    return todo


def refresh_enrollment_replan_workflows(
    enrollment,
    *,
    reset_to_teacher_proposal=False,
    reason='',
    previous_confirmed_slot=None,
):
    if not enrollment:
        return []

    todos = OATodo.query.filter(
        OATodo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        OATodo.enrollment_id == enrollment.id,
        OATodo.is_completed == False,
    ).all()
    if not todos:
        return []

    refresh_reason = (reason or '').strip() or '学生信息已更新，请基于最新可上课时间重新提案。'
    refreshed = []
    auth_services.refresh_enrollment_scheduling_ai_state(enrollment)
    for todo in todos:
        payload = _workflow_base_payload(todo)
        payload['context'] = {
            'student_name': enrollment.student_name,
            'course_name': enrollment.course_name,
            'teacher_name': enrollment.teacher.display_name if enrollment.teacher else '',
            **_student_preference_context(enrollment),
        }
        if previous_confirmed_slot is not None:
            payload['previous_confirmed_slot'] = _copy_jsonable(previous_confirmed_slot)
        elif payload.get('previous_confirmed_slot') is None:
            payload['previous_confirmed_slot'] = _copy_jsonable(_load_enrollment_confirmed_slot(enrollment))

        if reset_to_teacher_proposal:
            target_status = _enrollment_replan_status(enrollment)
            should_record_reset = (
                todo.workflow_status != target_status
                or bool(payload.get('current_proposal'))
            )
            if should_record_reset:
                _append_system_rejection(payload, refresh_reason)
                payload['revision'] = int(payload.get('revision') or 0) + 1
            todo.description = refresh_reason
            todo.notes = refresh_reason
            todo.responsible_person = _enrollment_replan_responsible_people(enrollment)
            if _enrollment_replan_uses_teacher_queue(enrollment):
                payload['current_proposal'] = None
                payload['proposal_note'] = None
                payload['proposal_warnings'] = []
                payload.pop('sent_to_student_at', None)
                payload.pop('sent_to_student_by', None)
                payload.pop('sent_to_student_by_name', None)
            else:
                _seed_full_time_enrollment_proposal(payload, enrollment, note_text=refresh_reason)
            _set_todo_state(todo, target_status)
        else:
            todo.responsible_person = _enrollment_replan_responsible_people(enrollment)

        todo.set_payload_data(payload)
        refreshed.append(todo)
    return refreshed


def ensure_leave_makeup_workflow(leave_request, *, actor_user=None):
    enrollment = leave_request.enrollment or (leave_request.schedule.enrollment if leave_request.schedule else None)
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        leave_request_id=leave_request.id,
    ).order_by(OATodo.created_at.desc()).first()
    if not todo:
        todo = OATodo(
            title=f'补课安排：{leave_request.student_name} · {leave_request.schedule.course_name if leave_request.schedule else ""}',
            description='请假已批准，等待老师提交补课提案。',
            responsible_person=_teacher_admin_responsible_people(enrollment) if enrollment else '教务',
            priority=1,
            due_date=leave_request.leave_date,
            todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
            workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
            enrollment_id=enrollment.id if enrollment else None,
            leave_request_id=leave_request.id,
            schedule_id=leave_request.schedule_id,
            created_by=getattr(actor_user, 'id', None),
        )
        db.session.add(todo)
        db.session.flush()

    payload = _workflow_base_payload(todo, {
        'context': {
            'student_name': leave_request.student_name,
            'course_name': leave_request.schedule.course_name if leave_request.schedule else '',
            'teacher_name': leave_request.schedule.teacher if leave_request.schedule else '',
            'leave_date': leave_request.leave_date.isoformat() if leave_request.leave_date else None,
            'original_schedule': _schedule_summary(leave_request.schedule),
            'makeup_available_slots': leave_request.to_dict().get('makeup_available_slots'),
            'makeup_excluded_dates': leave_request.to_dict().get('makeup_excluded_dates'),
            'makeup_preference_note': leave_request.makeup_preference_note,
            'makeup_preference_summary': auth_services._summarize_makeup_preferences(
                leave_request.to_dict().get('makeup_available_slots'),
                leave_request.to_dict().get('makeup_excluded_dates'),
                leave_request.makeup_preference_note,
            ),
        },
    })
    payload.setdefault('current_proposal', None)
    todo.description = '请假已批准，等待老师提交补课提案。'
    todo.notes = leave_request.reason
    todo.responsible_person = _teacher_admin_responsible_people(enrollment) if enrollment else '教务'
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL)
    todo.set_payload_data(payload)
    return todo


def _normalize_proposal_session_dates(session_dates):
    normalized_dates, parse_errors = auth_services._normalize_manual_session_dates(session_dates)
    if parse_errors:
        return None, parse_errors, []
    return normalized_dates, [], []


def _collect_makeup_plan_issues(leave_request, session_dates):
    enrollment = leave_request.enrollment or (leave_request.schedule.enrollment if leave_request.schedule else None)
    if not enrollment:
        return ['请假记录未绑定报名，无法创建补课方案'], []

    errors = []
    warnings = []
    if len(session_dates) != 1:
        errors.append('补课方案必须且只能保留 1 节课')
        return errors, warnings

    session = session_dates[0]
    start_at = datetime.combine(
        date.fromisoformat(session['date']),
        datetime.strptime(session['time_start'], '%H:%M').time(),
    )
    if start_at < _now():
        errors.append('补课时间不能早于当前业务时间')

    ignore_ids = [leave_request.schedule_id] if leave_request.schedule_id else []
    query = CourseSchedule.query.filter(
        CourseSchedule.teacher_id == enrollment.teacher_id,
        CourseSchedule.date == date.fromisoformat(session['date']),
    )
    if ignore_ids:
        query = query.filter(~CourseSchedule.id.in_(ignore_ids))
    for existing in query.all():
        if auth_services._slots_overlap(
            session['time_start'],
            session['time_end'],
            existing.time_start,
            existing.time_end,
        ):
            errors.append(
                f'{session["date"]} {session["time_start"]}-{session["time_end"]} '
                f'与老师现有课程冲突：{existing.course_name} {existing.time_start}-{existing.time_end}'
            )

    teacher_ranges = auth_services._load_teacher_available_ranges(enrollment.teacher_id)
    preferred_slot_entries = auth_services._normalize_available_slot_entries(leave_request.makeup_available_slots_json)
    student_ranges = [
        {
            'day_of_week': slot['day'],
            'time_start': slot['start'],
            'time_end': slot['end'],
        }
        for slot in preferred_slot_entries
    ]
    if not student_ranges:
        student_ranges = auth_services._load_student_available_ranges(enrollment.student_profile)

    excluded_dates = set(auth_services._normalize_excluded_dates_entries(leave_request.makeup_excluded_dates_json))
    if not excluded_dates:
        excluded_dates = auth_services._load_student_excluded_dates(enrollment.student_profile)

    if teacher_ranges and not auth_services._session_within_ranges(session, teacher_ranges):
        warnings.append(
            f'{session["date"]} {session["time_start"]}-{session["time_end"]} 超出老师原始可用时间'
        )
    if student_ranges and not auth_services._session_within_ranges(session, student_ranges):
        warnings.append(
            f'{session["date"]} {session["time_start"]}-{session["time_end"]} 超出'
            f'{"本次补课偏好时间" if preferred_slot_entries else "学生填写的可上课时间"}'
        )
    if session['date'] in excluded_dates:
        warnings.append(
            f'{session["date"]} 命中'
            f'{"本次补课禁排日期" if leave_request.makeup_excluded_dates_json else "学生标记的不可上课日期"}'
        )
    if leave_request.leave_date and session['date'] == leave_request.leave_date.isoformat():
        warnings.append('补课日期与请假日期相同，请确认是否为真实补课安排')

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _collect_student_profile_conflicts(enrollment, session_dates):
    if not enrollment or not getattr(enrollment, 'student_profile_id', None) or not session_dates:
        return []

    session_dates_set = {session['date'] for session in session_dates if session.get('date')}
    if not session_dates_set:
        return []

    query = db.session.query(CourseSchedule).filter(
        auth_services.student_schedule_profile_clause(enrollment.student_profile_id, schedule_model=CourseSchedule),
        CourseSchedule.date.in_(session_dates_set),
    )
    if enrollment.id:
        query = query.filter(
            or_(CourseSchedule.enrollment_id.is_(None), CourseSchedule.enrollment_id != enrollment.id)
        )

    existing_by_date = {}
    for schedule in query.all():
        existing_by_date.setdefault(schedule.date.isoformat(), []).append(schedule)

    errors = []
    for session in session_dates:
        for existing in existing_by_date.get(session.get('date'), []):
            if auth_services._slots_overlap(
                session['time_start'],
                session['time_end'],
                existing.time_start,
                existing.time_end,
            ):
                errors.append(
                    f'{session["date"]} {session["time_start"]}-{session["time_end"]} '
                    f'与同一学生跨报名课次冲突：{existing.course_name} {existing.time_start}-{existing.time_end}'
                )
    return list(dict.fromkeys(errors))


def _current_proposal_session_dates(todo):
    payload = todo.get_payload_data()
    current_proposal = payload.get('current_proposal') or {}
    session_dates = current_proposal.get('session_dates') or []
    if session_dates:
        return _copy_jsonable(session_dates), None

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and todo.enrollment:
        confirmed_plan = _load_enrollment_confirmed_slot(todo.enrollment)
        if confirmed_plan and confirmed_plan.get('session_dates'):
            return _copy_jsonable(confirmed_plan.get('session_dates') or []), None

    return [], '当前方案无可用课次'


def _restore_workflow_to_teacher_proposal(todo, message_text, *, clear_confirmed_slot=False):
    payload = _workflow_base_payload(todo)
    message = (message_text or '').strip() or '当前方案已失效，请老师重新提案。'
    _append_system_rejection(payload, message)
    payload['revision'] = int(payload.get('revision') or 0) + 1
    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and todo.enrollment and not _enrollment_replan_uses_teacher_queue(todo.enrollment):
        _seed_full_time_enrollment_proposal(payload, todo.enrollment, note_text=message)
        todo.responsible_person = _enrollment_replan_responsible_people(todo.enrollment)
        _set_todo_state(todo, _enrollment_replan_status(todo.enrollment))
    else:
        payload['current_proposal'] = _copy_jsonable(payload.get('current_proposal'))
        todo.responsible_person = _teacher_admin_responsible_people(todo.enrollment)
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL)
    todo.description = message
    todo.notes = message
    todo.set_payload_data(payload)
    if clear_confirmed_slot and todo.enrollment:
        todo.enrollment.confirmed_slot = None
        todo.enrollment.status = 'pending_schedule'


def _normalize_weekly_proposal_slots(weekly_slots):
    normalized_entries, errors = auth_services._validate_available_slot_entries(weekly_slots)
    if errors:
        return [], errors
    return [
        {
            'day_of_week': item['day'],
            'time_start': item['start'],
            'time_end': item['end'],
            'score': 0,
            'is_preferred': False,
            'conflicts': [],
        }
        for item in normalized_entries
    ], []


def _proposal_quota_required(todo):
    return max(int(getattr(todo.enrollment, 'sessions_per_week', 1) or 1), 1) if todo.enrollment else 1


def _proposal_quota_selected(plan):
    return len((plan or {}).get('weekly_slots') or [])


def _proposal_validation(todo, session_dates=None, weekly_slots=None):
    normalized_dates = []
    normalized_weekly_slots = None
    errors = []
    warnings = []
    if weekly_slots:
        normalized_weekly_slots, weekly_errors = _normalize_weekly_proposal_slots(weekly_slots)
        if weekly_errors:
            return None, weekly_errors, []
        if todo.todo_type != OATodo.TODO_TYPE_ENROLLMENT_REPLAN or not todo.enrollment:
            return None, ['当前待办暂不支持按每周时段提交方案'], []
        plan = auth_services._build_plan(
            normalized_weekly_slots,
            auth_services._get_total_sessions(todo.enrollment),
            auth_services._load_student_excluded_dates(todo.enrollment.student_profile),
        )
        normalized_dates = plan.get('session_dates') or []
    else:
        normalized_dates, errors, warnings = _normalize_proposal_session_dates(session_dates or [])
    if not errors:
        linked_enrollment = todo.enrollment
        if todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP and todo.leave_request:
            linked_enrollment = todo.leave_request.enrollment or (
                todo.leave_request.schedule.enrollment if todo.leave_request.schedule else linked_enrollment
            )
        errors.extend(_collect_student_profile_conflicts(linked_enrollment, normalized_dates))

    if errors:
        return None, errors, warnings

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        linked_enrollment = todo.enrollment
        errors, warnings = auth_services._collect_manual_plan_issues(
            linked_enrollment,
            normalized_dates,
            weekly_slots=normalized_weekly_slots,
        )
    elif todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP:
        errors, warnings = _collect_makeup_plan_issues(todo.leave_request, normalized_dates)
    else:
        errors = ['当前待办不支持提交排课方案']
        warnings = []

    if errors:
        return None, errors, warnings
    plan = auth_services._build_manual_plan(normalized_dates)
    return plan, [], warnings


def preview_teacher_workflow_proposal(todo, actor, session_dates, weekly_slots=None):
    if not user_can_access_workflow_todo(actor, todo) or not _actor_can_submit_teacher_workflow(actor, todo):
        return {
            'success': False,
            'status_code': 403,
            'error': '无权预检该工作流提案',
        }
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不在待老师提案状态',
        }

    normalized_dates, parse_errors, _ = _normalize_proposal_session_dates(session_dates)
    plan = None
    errors = list(parse_errors)
    warnings = []
    if weekly_slots:
        errors = []
        normalized_dates = []
    if not errors:
        plan, errors, warnings = _proposal_validation(todo, session_dates, weekly_slots=weekly_slots)

    current_plan_summary = auth_services._summarize_plan(plan) if plan else None
    context = (todo.get_payload_data() or {}).get('context') or {}
    risk_assessment = context.get('risk_assessment') or {}
    return {
        'success': True,
        'status_code': 200,
        'data': {
            'errors': errors,
            'warnings': warnings,
            'quota_required': _proposal_quota_required(todo),
            'quota_selected': _proposal_quota_selected(plan),
            'recommended_bundle': context.get('recommended_bundle'),
            'candidate_slot_pool': context.get('candidate_slot_pool') or [],
            'risk_assessment': risk_assessment,
            'current_plan_summary': current_plan_summary,
            'current_plan_session_dates': (plan or {}).get('session_dates') or normalized_dates,
            'session_preview_lines': auth_services._session_preview_lines(
                (plan or {}).get('session_dates') or normalized_dates
            ),
        },
    }


def submit_teacher_workflow_proposal(todo, actor, session_dates, note='', weekly_slots=None):
    if not user_can_access_workflow_todo(actor, todo) or not _actor_can_submit_teacher_workflow(actor, todo):
        return {
            'success': False,
            'status_code': 403,
            'error': '无权提交该工作流提案',
        }
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不在待老师提案状态',
        }

    plan, errors, warnings = _proposal_validation(todo, session_dates, weekly_slots=weekly_slots)
    if errors:
        return {
            'success': False,
            'status_code': 400,
            'error': '；'.join(errors),
            'errors': errors,
        }

    payload = _workflow_base_payload(todo)
    proposal = _copy_jsonable(plan)
    proposal['note'] = (note or '').strip() or None
    proposal['warnings'] = warnings
    proposal['submitted_by'] = actor.id
    proposal['submitted_by_name'] = actor.display_name
    proposal['submitted_at'] = _now().isoformat()
    proposal['quota_required'] = _proposal_quota_required(todo)
    proposal['quota_selected'] = _proposal_quota_selected(plan)
    payload['current_proposal'] = proposal
    payload['proposal_note'] = proposal['note']
    payload['proposal_warnings'] = warnings
    payload['risk_assessment'] = payload.get('risk_assessment') or (payload.get('context') or {}).get('risk_assessment') or {}
    todo.notes = proposal['note'] or todo.notes
    todo.description = proposal['note'] or todo.description
    can_direct_send = (
        todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and not warnings
        and proposal.get('quota_selected') == proposal.get('quota_required')
        and (payload.get('risk_assessment') or {}).get('severity') == 'ok'
    )
    if can_direct_send and todo.enrollment:
        todo.enrollment.confirmed_slot = json.dumps(proposal, ensure_ascii=False)
        todo.enrollment.status = 'pending_student_confirm'
        auth_services._send_schedule_notification(todo.enrollment, proposal)
        payload['sent_to_student_at'] = _now().isoformat()
        payload['sent_to_student_by'] = actor.id
        payload['sent_to_student_by_name'] = actor.display_name
        todo.responsible_person = _student_responsible_people(todo.enrollment)
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM)
    else:
        todo.responsible_person = '教务'
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW)
    todo.set_payload_data(payload)
    db.session.commit()
    return {
        'success': True,
        'status_code': 200,
        'message': '老师提案已直接发送给学生确认' if can_direct_send else '老师提案已提交，等待教务处理',
        'warnings': warnings,
        'data': build_workflow_todo_payload(todo, actor),
    }


def admin_return_workflow_to_teacher(todo, actor, message_text=''):
    if not user_can_access_workflow_todo(actor, todo) or actor.role != 'admin':
        return {
            'success': False,
            'status_code': 403,
            'error': '无权退回该工作流',
        }
    if todo.todo_type not in {
        OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        OATodo.TODO_TYPE_LEAVE_MAKEUP,
    }:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不支持退回老师重提',
        }
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不在待教务审核状态',
        }
    if (
        todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and todo.enrollment
        and not _enrollment_replan_uses_teacher_queue(todo.enrollment)
    ):
        return {
            'success': False,
            'status_code': 400,
            'error': '全职老师方案默认由教务复核，请直接调整后发送给学生或补充风险说明',
        }

    message = (message_text or '').strip()
    if not message:
        return {
            'success': False,
            'status_code': 400,
            'error': '请填写退回原因',
        }

    payload = _workflow_base_payload(todo)
    _append_rejection(payload, actor, message)
    payload['revision'] = int(payload.get('revision') or 0) + 1
    payload['current_proposal'] = _copy_jsonable(payload.get('current_proposal'))
    payload.pop('sent_to_student_at', None)
    payload.pop('sent_to_student_by', None)
    payload.pop('sent_to_student_by_name', None)
    todo.description = message
    todo.notes = message
    todo.responsible_person = _teacher_admin_responsible_people(todo.enrollment)
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL)
    todo.set_payload_data(payload)
    db.session.commit()
    return {
        'success': True,
        'status_code': 200,
        'message': '已退回老师重新提案',
        'data': build_workflow_todo_payload(todo, actor),
    }


def _send_makeup_notification(leave_request):
    enrollment = leave_request.enrollment or (leave_request.schedule.enrollment if leave_request.schedule else None)
    profile = enrollment.student_profile if enrollment else None
    if not profile or not profile.user_id:
        return

    sender_id = leave_request.approved_by or (leave_request.schedule.teacher_id if leave_request.schedule else None)
    if sender_id is None:
        return

    course_name = leave_request.schedule.course_name if leave_request.schedule else ''
    content = f'{MAKEUP_PLAN_PREFIX}[{course_name}] 教务已提交补课方案，请登录系统确认。'
    db.session.add(ChatMessage(
        sender_id=sender_id,
        receiver_id=profile.user_id,
        enrollment_id=enrollment.id if enrollment else None,
        content=content,
        is_read=False,
    ))


def admin_send_workflow_to_student(todo, actor, *, session_dates=None, note='', force_save=False):
    if not user_can_access_workflow_todo(actor, todo) or actor.role != 'admin':
        return {
            'success': False,
            'status_code': 403,
            'error': '无权处理该工作流',
        }
    if todo.todo_type not in {
        OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        OATodo.TODO_TYPE_LEAVE_MAKEUP,
    }:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不支持发送给学生确认',
        }
    if todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL:
        return {
            'success': False,
            'status_code': 400,
            'error': '老师尚未提交方案，请先等待老师提案或退回老师重提',
        }
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不在可发送给学生确认的状态',
        }

    payload = _workflow_base_payload(todo)
    if (
        todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and todo.enrollment
        and todo.enrollment.status == 'pending_student_confirm'
        and todo.enrollment.confirmed_slot
        and not payload.get('sent_to_student_at')
    ):
        return {
            'success': False,
            'status_code': 400,
            'error': '当前报名已通过其他入口发送给学生确认，请刷新状态后再处理',
        }
    source_proposal = session_dates
    if source_proposal is None:
        source_proposal = (payload.get('current_proposal') or {}).get('session_dates') or []

    plan, errors, warnings = _proposal_validation(todo, source_proposal)
    if errors:
        return {
            'success': False,
            'status_code': 400,
            'error': '；'.join(errors),
            'errors': errors,
        }
    if warnings and not force_save:
        return {
            'success': False,
            'status_code': 200,
            'error': '方案存在提示项，请确认是否继续发送给学生',
            'warnings': warnings,
            'can_force_save': True,
        }

    normalized_plan = _copy_jsonable(plan)
    normalized_plan['note'] = (note or '').strip() or payload.get('proposal_note')
    if warnings:
        normalized_plan['manual_warnings'] = warnings

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        enrollment = todo.enrollment
        if not enrollment:
            return {
                'success': False,
                'status_code': 404,
                'error': '关联报名不存在',
            }
        enrollment.confirmed_slot = json.dumps(normalized_plan, ensure_ascii=False)
        enrollment.status = 'pending_student_confirm'
        auth_services._send_schedule_notification(enrollment, normalized_plan)
        todo.responsible_person = _student_responsible_people(enrollment)
    else:
        leave_request = todo.leave_request
        if not leave_request:
            return {
                'success': False,
                'status_code': 404,
                'error': '关联请假记录不存在',
            }
        _send_makeup_notification(leave_request)
        enrollment = leave_request.enrollment or (leave_request.schedule.enrollment if leave_request.schedule else None)
        todo.responsible_person = _student_responsible_people(enrollment) if enrollment else todo.responsible_person

    payload['current_proposal'] = normalized_plan
    payload['proposal_note'] = normalized_plan.get('note')
    payload['proposal_warnings'] = warnings
    payload['sent_to_student_at'] = _now().isoformat()
    payload['sent_to_student_by'] = actor.id
    payload['sent_to_student_by_name'] = actor.display_name
    todo.notes = normalized_plan.get('note') or todo.notes
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM)
    todo.set_payload_data(payload)
    db.session.commit()
    return {
        'success': True,
        'status_code': 200,
        'message': '已发送给学生确认',
        'warnings': warnings,
        'data': build_workflow_todo_payload(todo, actor),
    }


def _create_makeup_schedule(todo, plan=None):
    from modules.oa.services import build_schedule_delivery_fields

    leave_request = todo.leave_request
    enrollment = todo.enrollment or (leave_request.enrollment if leave_request else None)
    if not leave_request or not enrollment:
        return None, '补课工作流缺少关联数据'

    proposal = plan or (todo.get_payload_data().get('current_proposal') or {})
    session_dates = proposal.get('session_dates') or []
    if len(session_dates) != 1:
        return None, '当前补课方案无效'

    session = session_dates[0]
    schedule_date = date.fromisoformat(session['date'])
    original_schedule = leave_request.schedule
    delivery_fields = build_schedule_delivery_fields(
        delivery_mode=(
            getattr(original_schedule, 'delivery_mode', None)
            or getattr(enrollment, 'delivery_preference', None)
        ),
        color_tag=getattr(original_schedule, 'color_tag', None),
        fallback_delivery_mode=getattr(enrollment, 'delivery_preference', None),
        existing_schedule=original_schedule,
        allow_unknown=False,
    )
    schedule = CourseSchedule(
        date=schedule_date,
        day_of_week=session['day_of_week'],
        time_start=session['time_start'],
        time_end=session['time_end'],
        teacher=enrollment.teacher.display_name if enrollment.teacher else (original_schedule.teacher if original_schedule else ''),
        teacher_id=enrollment.teacher_id,
        course_name=enrollment.course_name,
        enrollment_id=enrollment.id,
        students=enrollment.student_name,
        location=original_schedule.location if original_schedule else '',
        notes=f'补课安排 - 请假#{leave_request.id}',
        **delivery_fields,
    )
    auth_services.sync_schedule_student_snapshot(schedule, enrollment=enrollment, preserve_history=False)
    db.session.add(schedule)
    db.session.flush()
    ensure_schedule_feedback_todo(schedule, created_by=todo.created_by or enrollment.teacher_id)
    return schedule, None


def student_confirm_workflow_todo(todo, actor):
    if not user_can_access_workflow_todo(actor, todo) or actor.role != 'student':
        return {
            'success': False,
            'status_code': 403,
            'error': '无权确认该工作流',
        }
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不在待学生确认状态',
        }

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        session_dates, error = _current_proposal_session_dates(todo)
        if error:
            _restore_workflow_to_teacher_proposal(todo, error, clear_confirmed_slot=True)
            db.session.commit()
            return {
                'success': False,
                'status_code': 400,
                'error': error,
            }
        plan, errors, warnings = _proposal_validation(todo, session_dates)
        if errors or not plan:
            message = '；'.join(errors) if errors else '当前排课方案已失效，请重新提案'
            _restore_workflow_to_teacher_proposal(todo, message, clear_confirmed_slot=True)
            db.session.commit()
            return {
                'success': False,
                'status_code': 400,
                'error': message,
                'errors': errors,
            }
        success, message, created_count = auth_services.student_confirm_schedule(todo.enrollment_id)
        if not success:
            _restore_workflow_to_teacher_proposal(todo, message, clear_confirmed_slot=True)
            db.session.commit()
            return {
                'success': False,
                'status_code': 400,
                'error': message,
            }
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_COMPLETED)
        db.session.commit()
        return {
            'success': True,
            'status_code': 200,
            'message': message,
            'created_count': created_count,
            'data': build_workflow_todo_payload(todo, actor),
        }

    if todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP:
        session_dates, error = _current_proposal_session_dates(todo)
        if error:
            _restore_workflow_to_teacher_proposal(todo, error, clear_confirmed_slot=False)
            db.session.commit()
            return {
                'success': False,
                'status_code': 400,
                'error': error,
            }
        plan, errors, warnings = _proposal_validation(todo, session_dates)
        if errors or not plan:
            message = '；'.join(errors) if errors else '当前补课方案已失效，请重新提案'
            _restore_workflow_to_teacher_proposal(todo, message, clear_confirmed_slot=False)
            db.session.commit()
            return {
                'success': False,
                'status_code': 400,
                'error': message,
                'errors': errors,
            }
        schedule, error = _create_makeup_schedule(todo, plan=plan)
        if error:
            _restore_workflow_to_teacher_proposal(todo, error, clear_confirmed_slot=False)
            db.session.commit()
            return {
                'success': False,
                'status_code': 400,
                'error': error,
            }
        if todo.leave_request:
            todo.leave_request.makeup_schedule_id = schedule.id
        if todo.enrollment:
            auth_services.sync_enrollment_status(todo.enrollment)
        payload = _workflow_base_payload(todo)
        payload['replacement_schedule'] = _schedule_summary(schedule)
        payload['makeup_schedule_id'] = schedule.id
        todo.set_payload_data(payload)
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_COMPLETED)
        db.session.commit()
        return {
            'success': True,
            'status_code': 200,
            'message': '补课安排已确认并生成',
            'created_schedule_id': schedule.id,
            'data': build_workflow_todo_payload(todo, actor),
        }

    return {
        'success': False,
        'status_code': 400,
        'error': '当前工作流不支持学生确认',
    }


def _send_rejection_chat(todo, actor, message_text):
    enrollment = todo.enrollment
    if not enrollment or not enrollment.teacher_id:
        return
    prefix = auth_services.FEEDBACK_PREFIX
    if todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP:
        prefix = MAKEUP_FEEDBACK_PREFIX
    db.session.add(ChatMessage(
        sender_id=actor.id,
        receiver_id=enrollment.teacher_id,
        enrollment_id=enrollment.id,
        content=f'{prefix}[{enrollment.course_name}] {message_text or "学生对当前方案有疑问，请重新调整。"}',
        is_read=False,
    ))


def student_reject_workflow_todo(todo, actor, message_text=''):
    if not user_can_access_workflow_todo(actor, todo) or actor.role != 'student':
        return {
            'success': False,
            'status_code': 403,
            'error': '无权退回该工作流',
        }
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前工作流不在待学生确认状态',
        }

    payload = _workflow_base_payload(todo)
    _append_rejection(payload, actor, message_text)
    payload['revision'] = int(payload.get('revision') or 0) + 1
    payload['current_proposal'] = _copy_jsonable(payload.get('current_proposal'))
    todo.description = payload['latest_rejection']['message']
    todo.notes = payload['latest_rejection']['message']
    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and todo.enrollment and not _enrollment_replan_uses_teacher_queue(todo.enrollment):
        _seed_full_time_enrollment_proposal(payload, todo.enrollment, note_text=payload['latest_rejection']['message'])
        todo.responsible_person = _enrollment_replan_responsible_people(todo.enrollment)
        _set_todo_state(todo, _enrollment_replan_status(todo.enrollment))
    else:
        todo.responsible_person = _teacher_admin_responsible_people(todo.enrollment)
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL)
    todo.set_payload_data(payload)

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and todo.enrollment:
        todo.enrollment.confirmed_slot = None
        todo.enrollment.status = 'pending_schedule'
    _send_rejection_chat(todo, actor, message_text)
    db.session.commit()
    return {
        'success': True,
        'status_code': 200,
        'message': '已退回给老师和教务重新处理',
        'data': build_workflow_todo_payload(todo, actor),
    }


def ensure_schedule_feedback_todo(schedule, *, created_by=None):
    if not schedule:
        return None
    auth_services._hydrate_schedule_teacher_id(schedule)
    if not schedule.teacher_id:
        return None
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
        schedule_id=schedule.id,
    ).order_by(OATodo.created_at.desc()).first()
    if not auth_services.schedule_requires_course_feedback(schedule):
        if todo and not (todo.is_completed and todo.workflow_status == OATodo.WORKFLOW_STATUS_COMPLETED):
            return cancel_schedule_feedback_todo(
                schedule.id,
                reason=auth_services.get_course_feedback_skip_reason(schedule) or '',
            )
        return todo
    latest_leave = auth_services._latest_leave_request(schedule)
    if latest_leave and latest_leave.status == 'approved':
        return cancel_schedule_feedback_todo(schedule.id, reason='课程已请假')
    if not todo:
        todo = OATodo(
            title=f'课后反馈：{schedule.course_name} · {schedule.students or "未绑定学生"}',
            description=f'{schedule.date.isoformat()} {schedule.time_start}-{schedule.time_end}',
            responsible_person=schedule.teacher,
            due_date=schedule.date,
            priority=2,
            todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
            workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
            schedule_id=schedule.id,
            enrollment_id=schedule.enrollment_id,
            created_by=created_by,
        )
        db.session.add(todo)
        db.session.flush()

    todo.title = f'课后反馈：{schedule.course_name} · {schedule.students or "未绑定学生"}'
    todo.description = f'{schedule.date.isoformat()} {schedule.time_start}-{schedule.time_end}'
    todo.responsible_person = schedule.teacher
    todo.due_date = schedule.date
    todo.enrollment_id = schedule.enrollment_id
    payload = _workflow_base_payload(todo, {
        'context': {
            'course_name': schedule.course_name,
            'student_name': schedule.students,
            'teacher_name': schedule.teacher,
            'schedule': _schedule_summary(schedule),
        }
    })
    todo.set_payload_data(payload)
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL)
    return todo


def sync_schedule_feedback_todo(schedule):
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
        schedule_id=schedule.id,
    ).order_by(OATodo.created_at.desc()).first()
    if not todo:
        return ensure_schedule_feedback_todo(schedule)
    if todo.is_completed and todo.workflow_status == OATodo.WORKFLOW_STATUS_COMPLETED:
        return todo
    return ensure_schedule_feedback_todo(schedule, created_by=todo.created_by)


def complete_schedule_feedback_todo(schedule_id):
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
        schedule_id=schedule_id,
    ).order_by(OATodo.created_at.desc()).first()
    if not todo:
        return None
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_COMPLETED)
    return todo


def cancel_schedule_feedback_todo(schedule_id, *, reason=''):
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
        schedule_id=schedule_id,
    ).order_by(OATodo.created_at.desc()).first()
    if not todo:
        return None
    payload = _workflow_base_payload(todo)
    if reason:
        payload['cancel_reason'] = reason
    todo.set_payload_data(payload)
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_CANCELLED)
    return todo


def workflow_todo_stale_reason(todo):
    if not todo or not todo.is_workflow:
        return None

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        if todo.enrollment:
            return None
        return '关联报名已删除，流程待办已自动关闭'

    if todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP:
        if not todo.leave_request:
            return '关联请假请求已删除，流程待办已自动关闭'
        if todo.enrollment or todo.schedule or getattr(todo.leave_request, 'schedule', None):
            return None
        return '关联课次或报名已删除，流程待办已自动关闭'

    if todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK:
        if todo.schedule:
            return None
        return '关联课次已删除，流程待办已自动关闭'

    return None


def reconcile_stale_workflow_todo(todo):
    reason = workflow_todo_stale_reason(todo)
    if not reason:
        return False

    changed = False
    payload = _workflow_base_payload(todo)
    if payload.get('cancel_reason') != reason:
        payload['cancel_reason'] = reason
        todo.set_payload_data(payload)
        changed = True
    if todo.description != reason:
        todo.description = reason
        changed = True
    if todo.notes != reason:
        todo.notes = reason
        changed = True
    if todo.workflow_status != OATodo.WORKFLOW_STATUS_CANCELLED or not todo.is_completed:
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_CANCELLED)
        changed = True
    return changed


def close_process_workflows_for_enrollment(enrollment_id, *, status=OATodo.WORKFLOW_STATUS_CANCELLED):
    todos = OATodo.query.filter(
        OATodo.todo_type.in_(tuple(PROCESS_WORKFLOW_TYPES)),
        OATodo.enrollment_id == enrollment_id,
        OATodo.is_completed == False,
    ).all()
    for todo in todos:
        _set_todo_state(todo, status)
    return todos


def close_process_workflows_for_schedule(schedule_id, *, status=OATodo.WORKFLOW_STATUS_CANCELLED):
    todos = OATodo.query.filter(
        OATodo.todo_type.in_(tuple(PROCESS_WORKFLOW_TYPES)),
        OATodo.schedule_id == schedule_id,
        OATodo.is_completed == False,
    ).all()
    for todo in todos:
        _set_todo_state(todo, status)
    return todos


def complete_replan_workflows_for_enrollment(enrollment_id):
    todos = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        enrollment_id=enrollment_id,
        is_completed=False,
    ).all()
    for todo in todos:
        _set_todo_state(todo, OATodo.WORKFLOW_STATUS_COMPLETED)
    return todos
