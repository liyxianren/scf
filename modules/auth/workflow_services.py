import json
from datetime import date, datetime

from sqlalchemy import or_

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import ChatMessage, Enrollment
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
    return {
        'id': leave_request.id,
        'status': leave_request.status,
        'leave_date': leave_request.leave_date.isoformat() if leave_request.leave_date else None,
        'reason': leave_request.reason,
        'schedule_id': leave_request.schedule_id,
        'student_name': leave_request.student_name,
    }


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
        return bool(todo.schedule and todo.schedule.teacher_id == user.id)

    if user.role == 'student':
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
        query = query.filter(
            or_(
                OATodo.enrollment.has(Enrollment.teacher_id == user.id),
                OATodo.schedule.has(CourseSchedule.teacher_id == user.id),
            )
        )
    elif user.role == 'student':
        profile = getattr(user, 'student_profile', None)
        if not profile:
            return []
        query = query.filter(OATodo.enrollment.has(Enrollment.student_profile_id == profile.id))

    return query.order_by(
        OATodo.is_completed,
        OATodo.priority,
        OATodo.due_date.asc().nullslast(),
        OATodo.created_at.desc(),
    ).all()


def get_workflow_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo or not todo.is_workflow:
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


def build_workflow_todo_payload(todo, actor=None):
    if not todo:
        return None

    payload = todo.to_dict()
    workflow_payload = todo.get_payload_data()
    enrollment = todo.enrollment
    schedule = todo.schedule
    leave_request = todo.leave_request

    payload.update({
        'payload': workflow_payload,
        'enrollment': _enrollment_summary(enrollment),
        'schedule': _schedule_summary(schedule),
        'leave_request': _leave_request_summary(leave_request),
        'latest_rejection': workflow_payload.get('latest_rejection'),
        'revision': int(workflow_payload.get('revision') or 0),
        'current_proposal': workflow_payload.get('current_proposal'),
        'previous_confirmed_slot': workflow_payload.get('previous_confirmed_slot'),
        'context': workflow_payload.get('context') or {},
        'todo_type_label': _todo_type_label(todo.todo_type),
        'workflow_status_label': _workflow_status_label(todo.todo_type, todo.workflow_status),
        'can_teacher_propose': False,
        'can_admin_send': False,
        'can_student_confirm': False,
        'can_student_reject': False,
        'can_submit_feedback': False,
    })

    if actor and getattr(actor, 'is_authenticated', False) and user_can_access_workflow_todo(actor, todo):
        if actor.role == 'teacher':
            payload['can_teacher_propose'] = todo.todo_type in {
                OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
                OATodo.TODO_TYPE_LEAVE_MAKEUP,
            } and todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
            payload['can_submit_feedback'] = (
                todo.todo_type == OATodo.TODO_TYPE_SCHEDULE_FEEDBACK
                and schedule is not None
                and auth_services.user_can_submit_feedback(actor, schedule)
            )
        elif actor.role == 'admin':
            payload['can_admin_send'] = todo.todo_type in {
                OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
                OATodo.TODO_TYPE_LEAVE_MAKEUP,
            } and todo.workflow_status in {
                OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
                OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW,
            }
        elif actor.role == 'student':
            payload['can_student_confirm'] = todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM
            payload['can_student_reject'] = todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM

    return payload


def get_enrollment_workflow_todos(enrollment_id, actor=None, *, include_closed=False):
    query = OATodo.query.filter(
        OATodo.todo_type != OATodo.TODO_TYPE_GENERIC,
        OATodo.enrollment_id == enrollment_id,
    )
    if not include_closed:
        query = query.filter(OATodo.is_completed == False)
    todos = query.order_by(OATodo.created_at.desc()).all()
    return [build_workflow_todo_payload(todo, actor) for todo in todos]


def get_schedule_workflow_todos(schedule_id, actor=None, *, include_closed=False):
    query = OATodo.query.filter(
        OATodo.todo_type != OATodo.TODO_TYPE_GENERIC,
        OATodo.schedule_id == schedule_id,
    )
    if not include_closed:
        query = query.filter(OATodo.is_completed == False)
    todos = query.order_by(OATodo.created_at.desc()).all()
    return [build_workflow_todo_payload(todo, actor) for todo in todos]


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
    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        enrollment_id=enrollment.id,
    ).order_by(OATodo.created_at.desc()).first()
    if not todo:
        todo = OATodo(
            title=f'排课重排：{enrollment.student_name} · {enrollment.course_name}',
            description='学生退回了当前排课方案，等待老师和教务重新处理。',
            responsible_person=_teacher_admin_responsible_people(enrollment),
            priority=1,
            due_date=_today(),
            todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
            workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
            enrollment_id=enrollment.id,
            created_by=getattr(actor_user, 'id', None),
        )
        db.session.add(todo)
        db.session.flush()
    return todo


def ensure_enrollment_replan_workflow(enrollment, *, rejection_text='', actor_user=None):
    todo = _ensure_enrollment_replan_workflow(enrollment, actor_user=actor_user)
    payload = _workflow_base_payload(todo, {
        'context': {
            'student_name': enrollment.student_name,
            'course_name': enrollment.course_name,
            'teacher_name': enrollment.teacher.display_name if enrollment.teacher else '',
        },
        'previous_confirmed_slot': _copy_jsonable(_load_enrollment_confirmed_slot(enrollment)),
    })

    revision = int(payload.get('revision') or 0) + 1
    payload['revision'] = revision
    _append_rejection(payload, actor_user, rejection_text)
    payload.setdefault('current_proposal', None)
    todo.description = rejection_text or '学生对当前排课方案有疑问，等待老师重新提案。'
    todo.notes = rejection_text or todo.notes
    todo.responsible_person = _teacher_admin_responsible_people(enrollment)
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL)
    todo.set_payload_data(payload)
    return todo


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
        },
        'current_proposal': None,
    })
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
    student_ranges = auth_services._load_student_available_ranges(enrollment.student_profile)
    excluded_dates = auth_services._load_student_excluded_dates(enrollment.student_profile)

    if teacher_ranges and not auth_services._session_within_ranges(session, teacher_ranges):
        warnings.append(
            f'{session["date"]} {session["time_start"]}-{session["time_end"]} 超出老师原始可用时间'
        )
    if student_ranges and not auth_services._session_within_ranges(session, student_ranges):
        warnings.append(
            f'{session["date"]} {session["time_start"]}-{session["time_end"]} 超出学生填写的可上课时间'
        )
    if session['date'] in excluded_dates:
        warnings.append(f'{session["date"]} 命中学生标记的不可上课日期')
    if leave_request.leave_date and session['date'] == leave_request.leave_date.isoformat():
        warnings.append('补课日期与请假日期相同，请确认是否为真实补课安排')

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _proposal_validation(todo, session_dates):
    normalized_dates, errors, warnings = _normalize_proposal_session_dates(session_dates)
    if errors:
        return None, errors, warnings

    if todo.todo_type == OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        linked_enrollment = todo.enrollment
        errors, warnings = auth_services._collect_manual_plan_issues(linked_enrollment, normalized_dates)
    elif todo.todo_type == OATodo.TODO_TYPE_LEAVE_MAKEUP:
        errors, warnings = _collect_makeup_plan_issues(todo.leave_request, normalized_dates)
    else:
        errors = ['当前待办不支持提交排课方案']
        warnings = []

    if errors:
        return None, errors, warnings
    plan = auth_services._build_manual_plan(normalized_dates)
    return plan, [], warnings


def submit_teacher_workflow_proposal(todo, actor, session_dates, note=''):
    if not user_can_access_workflow_todo(actor, todo) or actor.role != 'teacher':
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

    plan, errors, warnings = _proposal_validation(todo, session_dates)
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
    payload['current_proposal'] = proposal
    payload['proposal_note'] = proposal['note']
    payload['proposal_warnings'] = warnings
    todo.notes = proposal['note'] or todo.notes
    todo.description = proposal['note'] or todo.description
    todo.responsible_person = '教务'
    _set_todo_state(todo, OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW)
    todo.set_payload_data(payload)
    db.session.commit()
    return {
        'success': True,
        'status_code': 200,
        'message': '老师提案已提交，等待教务处理',
        'warnings': warnings,
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

    payload = _workflow_base_payload(todo)
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


def _create_makeup_schedule(todo):
    from modules.oa.services import delivery_mode_from_color_tag

    leave_request = todo.leave_request
    enrollment = todo.enrollment or (leave_request.enrollment if leave_request else None)
    if not leave_request or not enrollment:
        return None, '补课工作流缺少关联数据'

    proposal = (todo.get_payload_data().get('current_proposal') or {})
    session_dates = proposal.get('session_dates') or []
    if len(session_dates) != 1:
        return None, '当前补课方案无效'

    session = session_dates[0]
    schedule_date = date.fromisoformat(session['date'])
    original_schedule = leave_request.schedule
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
        color_tag='teal',
        delivery_mode=delivery_mode_from_color_tag('teal'),
    )
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
        success, message, created_count = auth_services.student_confirm_schedule(todo.enrollment_id)
        if not success:
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
        schedule, error = _create_makeup_schedule(todo)
        if error:
            return {
                'success': False,
                'status_code': 400,
                'error': error,
            }
        if todo.enrollment:
            auth_services.sync_enrollment_status(todo.enrollment)
        payload = _workflow_base_payload(todo)
        payload['replacement_schedule'] = _schedule_summary(schedule)
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
    if not schedule or not schedule.teacher_id:
        return None
    latest_leave = auth_services._latest_leave_request(schedule)
    if latest_leave and latest_leave.status == 'approved':
        return cancel_schedule_feedback_todo(schedule.id, reason='课程已请假')

    todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
        schedule_id=schedule.id,
    ).order_by(OATodo.created_at.desc()).first()
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
