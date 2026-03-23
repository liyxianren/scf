"""Reminder event services for OpenClaw pull feeds."""

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import LeaveRequest, ReminderDelivery, ReminderEvent
from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user
from modules.oa.models import CourseSchedule
from modules.oa.schedule_actions import build_schedule_preview_payload


OPENCLAW_FEED_CHANNEL = 'openclaw_feed'
SNAPSHOT_EVENT_TYPES = {'workflow.todo', 'leave.request', 'feedback.overdue'}


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


def _workflow_payloads(actor):
    items = [
        build_workflow_todo_payload(todo, actor)
        for todo in list_workflow_todos_for_user(actor, status='open')
    ]
    items = [
        item for item in items
        if item.get('next_action_role') == actor.role
    ]
    return _sort_items(items)


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


def _pending_feedback_payloads(actor):
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


def _deep_link_for_actor(actor):
    if actor.role == 'admin':
        return '/oa/'
    return '/auth/teacher/dashboard'


def _workflow_action_key(actor, payload):
    if payload.get('todo_type') == 'schedule_feedback':
        return 'feedback.submit'
    if actor.role == 'admin' and payload.get('next_action_role') == 'admin':
        return 'workflow.admin_send_to_student'
    if actor.role == 'teacher' and payload.get('next_action_role') == 'teacher':
        return 'workflow.teacher_proposal.submit'
    return None


def _create_or_update_event(
    *,
    event_key,
    event_type,
    target_user_id,
    target_role,
    scope_type,
    scope_id,
    title,
    summary,
    action_key,
    payload,
    source_request_id=None,
    source_action=None,
):
    event = ReminderEvent.query.filter_by(event_key=event_key).first()
    if not event:
        event = ReminderEvent(
            event_key=event_key,
            event_type=event_type,
            target_user_id=target_user_id,
            target_role=target_role,
            scope_type=scope_type,
            scope_id=scope_id,
            title=title,
            summary=summary,
            action_key=action_key,
            status='pending',
            source_request_id=source_request_id,
            source_action=source_action,
        )
        event.set_payload_data(payload)
        db.session.add(event)
        db.session.flush()
        return event, True

    event.event_type = event_type
    event.target_user_id = target_user_id
    event.target_role = target_role
    event.scope_type = scope_type
    event.scope_id = scope_id
    event.title = title
    event.summary = summary
    event.action_key = action_key
    event.status = 'pending'
    event.source_request_id = source_request_id
    event.source_action = source_action
    event.set_payload_data(payload)
    db.session.flush()
    return event, False


def _cancel_stale_snapshot_events(actor, active_keys):
    stale_events = ReminderEvent.query.filter(
        ReminderEvent.target_user_id == actor.id,
        ReminderEvent.event_type.in_(tuple(SNAPSHOT_EVENT_TYPES)),
        ReminderEvent.status == 'pending',
    ).all()
    changed = False
    for event in stale_events:
        if event.event_key in active_keys:
            continue
        event.status = 'cancelled'
        changed = True
    return changed


def sync_actor_snapshot_reminders(actor):
    active_keys = set()
    changed = False
    deep_link = _deep_link_for_actor(actor)

    for payload in _workflow_payloads(actor):
        event_key = f'workflow.todo:{actor.id}:{payload["id"]}:{payload.get("workflow_status")}'
        active_keys.add(event_key)
        _, created = _create_or_update_event(
            event_key=event_key,
            event_type='workflow.todo',
            target_user_id=actor.id,
            target_role=actor.role,
            scope_type='workflow_todo',
            scope_id=payload['id'],
            title=payload.get('title') or payload.get('todo_type_label') or '工作流待办',
            summary=payload.get('context_summary') or payload.get('next_action_label') or '',
            action_key=_workflow_action_key(actor, payload),
            payload={
                'workflow_todo': payload,
                'deep_link': deep_link,
            },
        )
        changed = changed or created

    for payload in _pending_leave_request_payloads(actor):
        event_key = f'leave.request:{actor.id}:{payload["id"]}:{payload.get("status")}'
        active_keys.add(event_key)
        _, created = _create_or_update_event(
            event_key=event_key,
            event_type='leave.request',
            target_user_id=actor.id,
            target_role=actor.role,
            scope_type='leave_request',
            scope_id=payload['id'],
            title='待处理请假申请' if payload.get('status') == 'pending' else '请假状态更新',
            summary=payload.get('original_schedule_summary') or payload.get('student_name') or '',
            action_key='leave.approve' if payload.get('can_approve_leave') else None,
            payload={
                'leave_request': payload,
                'deep_link': deep_link,
            },
        )
        changed = changed or created

    for payload in _pending_feedback_payloads(actor):
        event_key = f'feedback.overdue:{actor.id}:{payload["id"]}:{payload.get("next_action_status")}'
        active_keys.add(event_key)
        _, created = _create_or_update_event(
            event_key=event_key,
            event_type='feedback.overdue',
            target_user_id=actor.id,
            target_role=actor.role,
            scope_type='schedule',
            scope_id=payload['id'],
            title='待提交课程反馈' if actor.role == 'teacher' else '待跟进课程反馈',
            summary=auth_services._summarize_schedule_summary(payload) or payload.get('course_name') or '',
            action_key='feedback.submit' if actor.role == 'teacher' else None,
            payload={
                'schedule': payload,
                'deep_link': deep_link,
            },
        )
        changed = changed or created

    changed = _cancel_stale_snapshot_events(actor, active_keys) or changed
    if changed:
        db.session.commit()
    return changed


def _build_schedule_change_summary(before_payload, after_payload, action_key):
    before_line = f'{before_payload.get("date")} {before_payload.get("time_start")}-{before_payload.get("time_end")}'
    after_line = f'{after_payload.get("date")} {after_payload.get("time_start")}-{after_payload.get("time_end")}'
    if action_key == 'schedule.reassign_teacher.apply':
        return f'{after_payload.get("course_name") or "课次"} 已改为 {after_payload.get("teacher")}'
    if before_line == after_line:
        return after_payload.get('course_name') or '课次信息已更新'
    return f'{before_line} -> {after_line}'


def record_schedule_action_reminders(
    schedule,
    *,
    actor,
    action_key,
    before_payload=None,
    source_request_id=None,
    extra_payload=None,
):
    if not schedule or not schedule.teacher_id:
        return []

    before_payload = before_payload or build_schedule_preview_payload(schedule)
    after_payload = build_schedule_preview_payload(schedule)
    extra_payload = extra_payload or {}
    created_events = []
    target_user_ids = [('new_teacher', schedule.teacher_id)]

    previous_teacher_id = before_payload.get('teacher_id')
    if (
        action_key == 'schedule.reassign_teacher.apply'
        and previous_teacher_id
        and previous_teacher_id != schedule.teacher_id
    ):
        target_user_ids.append(('previous_teacher', previous_teacher_id))

    for target_kind, target_user_id in target_user_ids:
        if source_request_id:
            event_key = f'{action_key}:{source_request_id}:{target_user_id}:{target_kind}'
        else:
            event_key = (
                f'{action_key}:{schedule.id}:{target_user_id}:{target_kind}:'
                f'{auth_services.get_business_now().isoformat()}'
            )

        title = '课表已更新'
        summary = _build_schedule_change_summary(before_payload, after_payload, action_key)
        target_action_key = 'schedule.reschedule.apply'
        if action_key == 'schedule.quick_shift.apply':
            title = '课次已快捷调课'
            target_action_key = 'schedule.quick_shift'
        elif action_key == 'schedule.reassign_teacher.apply':
            if target_kind == 'previous_teacher':
                title = '课次已转交其他老师'
                summary = (
                    f'{before_payload.get("course_name") or "课次"} '
                    f'{before_payload.get("date")} {before_payload.get("time_start")}-{before_payload.get("time_end")}'
                )
                target_action_key = None
            else:
                title = '有新的课次指派给你'
                target_action_key = 'schedule.reassign_teacher.apply'

        event, _ = _create_or_update_event(
            event_key=event_key,
            event_type=action_key,
            target_user_id=target_user_id,
            target_role='teacher',
            scope_type='schedule',
            scope_id=schedule.id,
            title=title,
            summary=summary,
            action_key=target_action_key,
            payload={
                'before': before_payload,
                'after': after_payload,
                'extra': extra_payload,
                'deep_link': '/auth/teacher/dashboard',
                'actor': actor.to_dict() if actor else None,
            },
            source_request_id=source_request_id,
            source_action=action_key,
        )
        created_events.append(event)

    if created_events:
        db.session.commit()
    return created_events


def _get_delivery_map(event_ids, external_user_id):
    if not event_ids:
        return {}
    deliveries = ReminderDelivery.query.filter(
        ReminderDelivery.event_id.in_(event_ids),
        ReminderDelivery.channel == OPENCLAW_FEED_CHANNEL,
        ReminderDelivery.receiver_external_id == external_user_id,
    ).all()
    return {delivery.event_id: delivery for delivery in deliveries}


def _touch_delivery(event, external_user_id, *, ack=False):
    delivery = ReminderDelivery.query.filter_by(
        event_id=event.id,
        channel=OPENCLAW_FEED_CHANNEL,
        receiver_external_id=external_user_id,
    ).first()
    now = auth_services.get_business_now()
    if not delivery:
        delivery = ReminderDelivery(
            event_id=event.id,
            channel=OPENCLAW_FEED_CHANNEL,
            receiver_external_id=external_user_id,
            delivery_status='acked' if ack else 'pending',
            fetched_at=now,
            acked_at=now if ack else None,
        )
        db.session.add(delivery)
        db.session.flush()
        return delivery

    if ack:
        delivery.delivery_status = 'acked'
        delivery.acked_at = now
        if not delivery.fetched_at:
            delivery.fetched_at = now
    elif delivery.delivery_status != 'acked':
        delivery.delivery_status = 'pending'
        delivery.fetched_at = now
    db.session.flush()
    return delivery


def build_reminder_payload(event, delivery=None):
    return {
        'id': event.id,
        'event_type': event.event_type,
        'title': event.title,
        'summary': event.summary,
        'action_key': event.action_key,
        'scope_type': event.scope_type,
        'scope_id': event.scope_id,
        'status': event.status,
        'delivery_status': delivery.delivery_status if delivery else None,
        'payload': event.get_payload_data(),
        'created_at': event.created_at.isoformat() if event.created_at else None,
        'updated_at': event.updated_at.isoformat() if event.updated_at else None,
    }


def list_openclaw_reminders(actor, external_user_id, *, status='pending', limit=20, cursor=None):
    sync_actor_snapshot_reminders(actor)

    query = ReminderEvent.query.filter(
        ReminderEvent.target_user_id == actor.id,
        ReminderEvent.status != 'cancelled',
    ).order_by(ReminderEvent.created_at.desc(), ReminderEvent.id.desc())
    events = query.all()
    if cursor is not None:
        try:
            cursor_id = int(cursor)
            events = [event for event in events if event.id < cursor_id]
        except (TypeError, ValueError):
            pass

    event_ids = [event.id for event in events]
    delivery_map = _get_delivery_map(event_ids, external_user_id)
    items = []
    for event in events:
        delivery = delivery_map.get(event.id)
        is_acked = bool(delivery and delivery.delivery_status == 'acked')
        if status == 'acked' and not is_acked:
            continue
        if status != 'acked' and is_acked:
            continue
        items.append((event, delivery))

    normalized_limit = max(int(limit or 20), 1)
    limited = items[:normalized_limit]
    for event, delivery in limited:
        if status != 'acked':
            delivery = _touch_delivery(event, external_user_id, ack=False)
            delivery_map[event.id] = delivery
    if limited:
        db.session.commit()

    payload_items = [
        build_reminder_payload(event, delivery_map.get(event.id) or delivery)
        for event, delivery in limited
    ]
    next_cursor = limited[-1][0].id if len(items) > len(limited) and limited else None
    return {
        'actor': actor.to_dict(),
        'status': 'acked' if status == 'acked' else 'pending',
        'items': payload_items,
        'total': len(items),
        'next_cursor': next_cursor,
        'has_more': next_cursor is not None,
    }


def ack_openclaw_reminders(actor, external_user_id, event_ids):
    normalized_ids = []
    for event_id in event_ids or []:
        try:
            normalized_ids.append(int(event_id))
        except (TypeError, ValueError):
            continue
    if not normalized_ids:
        return {'acked_count': 0, 'acked_event_ids': []}

    events = ReminderEvent.query.filter(
        ReminderEvent.target_user_id == actor.id,
        ReminderEvent.id.in_(normalized_ids),
        ReminderEvent.status != 'cancelled',
    ).all()
    acked_ids = []
    for event in events:
        _touch_delivery(event, external_user_id, ack=True)
        acked_ids.append(event.id)
    db.session.commit()
    return {
        'acked_count': len(acked_ids),
        'acked_event_ids': acked_ids,
    }
