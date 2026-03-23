"""OpenClaw integration read helpers."""
from datetime import timedelta

from modules.auth import services as auth_services
from modules.auth.models import LeaveRequest
from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user
from modules.oa.models import CourseSchedule


OPENCLAW_ALLOWED_ROLES = {'admin', 'teacher'}


def actor_supported_for_openclaw(actor):
    return bool(
        actor
        and getattr(actor, 'is_authenticated', False)
        and getattr(actor, 'role', None) in OPENCLAW_ALLOWED_ROLES
    )


def _item_sort_key(item):
    return (
        item.get('due_date') or '9999-12-31',
        item.get('date') or '9999-12-31',
        item.get('time_start') or '99:99',
        item.get('waiting_since') or item.get('updated_at') or item.get('created_at') or '',
    )


def _sort_items(items):
    return sorted(items or [], key=_item_sort_key)


def _actor_schedule_query(actor, *, start=None, end=None):
    query = CourseSchedule.query
    if actor.role == 'teacher':
        query = query.filter(auth_services._teacher_schedule_identity_filter(CourseSchedule, actor))
    elif actor.role != 'admin':
        return CourseSchedule.query.filter(False)
    if start is not None:
        query = query.filter(CourseSchedule.date >= start)
    if end is not None:
        query = query.filter(CourseSchedule.date <= end)
    return query.order_by(CourseSchedule.date, CourseSchedule.time_start)


def _exclude_approved_leave(payloads):
    return [item for item in (payloads or []) if item.get('leave_status') != 'approved']


def _pending_feedback_payloads_for_actor(actor):
    today = auth_services.get_business_today()
    payloads = [
        auth_services.build_schedule_payload(schedule, actor)
        for schedule in _actor_schedule_query(actor, end=today).all()
    ]
    pending = [
        item for item in payloads
        if item.get('next_action_status') == 'waiting_teacher_feedback'
    ]
    teacher_counts = {}
    for item in pending:
        teacher_id = item.get('teacher_id')
        if teacher_id is None:
            continue
        teacher_counts[teacher_id] = teacher_counts.get(teacher_id, 0) + 1
    for item in pending:
        teacher_id = item.get('teacher_id')
        item['missing_feedback_count_for_teacher_recent'] = teacher_counts.get(teacher_id, 0)
        item['is_repeat_late_teacher'] = teacher_counts.get(teacher_id, 0) >= 2
        item['feedback_delay_days'] = max(int(item.get('feedback_delay_days') or 0), 0)
    return _sort_items(pending)


def _pending_leave_request_payloads(actor):
    query = LeaveRequest.query.filter(LeaveRequest.status == 'pending')
    if actor.role == 'teacher':
        query = query.join(CourseSchedule, LeaveRequest.schedule_id == CourseSchedule.id).filter(
            auth_services._teacher_schedule_identity_filter(CourseSchedule, actor)
        )
    items = [
        auth_services.build_leave_request_payload(leave_request, actor)
        for leave_request in query.order_by(LeaveRequest.created_at.desc()).all()
    ]
    return _sort_items(items)


def _workflow_payloads(actor):
    items = [
        build_workflow_todo_payload(todo, actor)
        for todo in list_workflow_todos_for_user(actor, status='open')
    ]
    return _sort_items(items)


def _upcoming_schedule_payloads(actor, *, days=7):
    today = auth_services.get_business_today()
    end = today + timedelta(days=days)
    payloads = [
        auth_services.build_schedule_payload(schedule, actor)
        for schedule in _actor_schedule_query(actor, start=today, end=end).all()
    ]
    return _sort_items(_exclude_approved_leave(payloads))


def build_openclaw_summary(actor):
    workflow_todos = _workflow_payloads(actor)
    pending_feedback = _pending_feedback_payloads_for_actor(actor)
    pending_leave_requests = _pending_leave_request_payloads(actor)
    upcoming_schedules = _upcoming_schedule_payloads(actor)

    if actor.role == 'admin':
        waiting_teacher = [
            item for item in workflow_todos
            if item.get('next_action_role') == 'teacher'
            and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
        ]
        pending_admin_send = [
            item for item in workflow_todos
            if item.get('next_action_role') == 'admin'
            and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
        ]
        waiting_student = [
            item for item in workflow_todos
            if item.get('next_action_role') == 'student'
            and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
        ]
        counts = {
            'waiting_teacher_proposal_workflows': len(waiting_teacher),
            'pending_admin_send_workflows': len(pending_admin_send),
            'waiting_student_confirm_workflows': len(waiting_student),
            'pending_leave_requests': len(pending_leave_requests),
            'pending_feedback_schedules': len(pending_feedback),
            'upcoming_schedules': len(upcoming_schedules),
        }
        cards = [
            {
                'key': 'pending_admin_send_workflows',
                'title': '待发送给学生',
                'count': counts['pending_admin_send_workflows'],
                'items': pending_admin_send[:5],
                'primary_action': 'workflow.admin_send_to_student',
                'deep_link': '/oa/',
            },
            {
                'key': 'pending_leave_requests',
                'title': '待审批请假',
                'count': counts['pending_leave_requests'],
                'items': pending_leave_requests[:5],
                'primary_action': 'leave.approve',
                'deep_link': '/oa/',
            },
            {
                'key': 'pending_feedback_schedules',
                'title': '待跟进反馈',
                'count': counts['pending_feedback_schedules'],
                'items': pending_feedback[:5],
                'primary_action': None,
                'deep_link': '/oa/',
            },
        ]
        primary_action = 'workflow.admin_send_to_student' if pending_admin_send else 'leave.approve'
        return {
            'actor': actor.to_dict(),
            'counts': counts,
            'cards': cards,
            'deep_link': '/oa/',
            'primary_action': primary_action,
        }

    proposal_workflows = [
        item for item in workflow_todos
        if item.get('next_action_role') == 'teacher'
        and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
    ]
    tracking_workflows = [
        item for item in workflow_todos
        if item not in proposal_workflows
    ]
    counts = {
        'proposal_workflows': len(proposal_workflows),
        'tracking_workflows': len(tracking_workflows),
        'pending_feedback_schedules': len(pending_feedback),
        'pending_leave_requests': len(pending_leave_requests),
        'upcoming_schedules': len(upcoming_schedules),
    }
    cards = [
        {
            'key': 'proposal_workflows',
            'title': '待提案工作流',
            'count': counts['proposal_workflows'],
            'items': proposal_workflows[:5],
            'primary_action': 'workflow.teacher_proposal.submit',
            'deep_link': '/auth/teacher/dashboard',
        },
        {
            'key': 'pending_feedback_schedules',
            'title': '待提交反馈',
            'count': counts['pending_feedback_schedules'],
            'items': pending_feedback[:5],
            'primary_action': 'feedback.submit',
            'deep_link': '/auth/teacher/dashboard',
        },
        {
            'key': 'pending_leave_requests',
            'title': '待审批请假',
            'count': counts['pending_leave_requests'],
            'items': pending_leave_requests[:5],
            'primary_action': 'leave.approve',
            'deep_link': '/auth/teacher/dashboard',
        },
    ]
    primary_action = 'workflow.teacher_proposal.submit' if proposal_workflows else 'feedback.submit'
    return {
        'actor': actor.to_dict(),
        'counts': counts,
        'cards': cards,
        'deep_link': '/auth/teacher/dashboard',
        'primary_action': primary_action,
    }


def list_openclaw_schedules(actor, *, start=None, end=None):
    payloads = [
        auth_services.build_schedule_payload(schedule, actor)
        for schedule in _actor_schedule_query(actor, start=start, end=end).all()
    ]
    return _sort_items(payloads)


def list_openclaw_work_items(actor):
    workflow_todos = _workflow_payloads(actor)
    pending_feedback = _pending_feedback_payloads_for_actor(actor)
    pending_leave_requests = _pending_leave_request_payloads(actor)
    return {
        'actor': actor.to_dict(),
        'workflow_todos': workflow_todos,
        'pending_feedback_schedules': pending_feedback,
        'pending_leave_requests': pending_leave_requests,
        'counts': {
            'workflow_todos': len(workflow_todos),
            'pending_feedback_schedules': len(pending_feedback),
            'pending_leave_requests': len(pending_leave_requests),
        },
    }
