from datetime import date

from modules.auth.models import ReminderDelivery, ReminderEvent
from tests.factories import (
    create_external_identity,
    create_schedule,
    create_user,
)


def _headers(app):
    return {'X-Integration-Token': app.config['OPENCLAW_INTEGRATION_TOKEN']}


def _identity_params(identity):
    return {
        'provider': identity.provider,
        'external_user_id': identity.external_user_id,
    }


def _command(identity, request_id, action, payload):
    return {
        'provider': identity.provider,
        'external_user_id': identity.external_user_id,
        'request_id': request_id,
        'action': action,
        'payload': payload,
    }


def test_schedule_action_creates_teacher_reminder_and_replay_does_not_duplicate(client, app):
    admin = create_user(role='admin', username='reminder-admin')
    teacher = create_user(role='teacher', username='reminder-teacher')
    admin_identity = create_external_identity(user=admin, external_user_id='ou_reminder_admin')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_reminder_teacher')

    schedule = create_schedule(
        teacher=teacher,
        course_name='Chemistry',
        students='Legacy Student',
        schedule_date=date(2026, 3, 20),
        time_start='10:00',
        time_end='12:00',
    )

    payload = _command(
        admin_identity,
        'req-reminder-quick-shift',
        'schedule.quick_shift',
        {
            'schedule_id': schedule.id,
            'date_shift_days': 1,
            'time_shift_minutes': 30,
        },
    )
    first = client.post('/oa/api/integration/openclaw/command', json=payload, headers=_headers(app))
    assert first.status_code == 200
    assert ReminderEvent.query.filter_by(
        target_user_id=teacher.id,
        event_type='schedule.quick_shift.apply',
        source_request_id='req-reminder-quick-shift',
    ).count() == 1

    replay = client.post('/oa/api/integration/openclaw/command', json=payload, headers=_headers(app))
    assert replay.status_code == 200
    assert replay.get_json()['data']['integration_meta']['replayed'] is True
    assert ReminderEvent.query.filter_by(
        target_user_id=teacher.id,
        event_type='schedule.quick_shift.apply',
        source_request_id='req-reminder-quick-shift',
    ).count() == 1

    teacher_feed = client.get(
        '/oa/api/integration/openclaw/reminders',
        query_string=_identity_params(teacher_identity),
        headers=_headers(app),
    )
    assert teacher_feed.status_code == 200
    items = teacher_feed.get_json()['data']['items']
    assert any(item['event_type'] == 'schedule.quick_shift.apply' for item in items)


def test_reminders_are_actor_scoped_and_ack_removes_pending_item(client, app):
    admin = create_user(role='admin', username='reminder-admin-scope')
    teacher = create_user(role='teacher', username='reminder-teacher-scope')
    admin_identity = create_external_identity(user=admin, external_user_id='ou_reminder_admin_scope')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_reminder_teacher_scope')

    schedule = create_schedule(
        teacher=teacher,
        course_name='Math',
        students='Legacy Student',
        schedule_date=date(2026, 3, 20),
        time_start='09:00',
        time_end='11:00',
    )

    action_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            admin_identity,
            'req-reminder-reschedule',
            'schedule.reschedule.apply',
            {
                'schedule_id': schedule.id,
                'date': '2026-03-21',
                'time_start': '11:00',
                'time_end': '13:00',
            },
        ),
        headers=_headers(app),
    )
    assert action_response.status_code == 200

    admin_feed = client.get(
        '/oa/api/integration/openclaw/reminders',
        query_string=_identity_params(admin_identity),
        headers=_headers(app),
    )
    assert admin_feed.status_code == 200
    assert admin_feed.get_json()['data']['items'] == []

    teacher_feed = client.get(
        '/oa/api/integration/openclaw/reminders',
        query_string=_identity_params(teacher_identity),
        headers=_headers(app),
    )
    assert teacher_feed.status_code == 200
    teacher_items = teacher_feed.get_json()['data']['items']
    schedule_item = next(item for item in teacher_items if item['event_type'] == 'schedule.reschedule.apply')
    delivery = ReminderDelivery.query.filter_by(
        event_id=schedule_item['id'],
        receiver_external_id=teacher_identity.external_user_id,
    ).first()
    assert delivery is not None
    assert delivery.delivery_status == 'pending'

    ack = client.post(
        '/oa/api/integration/openclaw/reminders/ack',
        json={
            'provider': teacher_identity.provider,
            'external_user_id': teacher_identity.external_user_id,
            'request_id': 'req-reminder-ack-1',
            'event_ids': [schedule_item['id']],
        },
        headers=_headers(app),
    )
    assert ack.status_code == 200
    assert ack.get_json()['data']['acked_event_ids'] == [schedule_item['id']]

    pending_again = client.get(
        '/oa/api/integration/openclaw/reminders',
        query_string=_identity_params(teacher_identity),
        headers=_headers(app),
    )
    assert pending_again.status_code == 200
    assert all(item['id'] != schedule_item['id'] for item in pending_again.get_json()['data']['items'])

    acked_feed = client.get(
        '/oa/api/integration/openclaw/reminders',
        query_string={**_identity_params(teacher_identity), 'status': 'acked'},
        headers=_headers(app),
    )
    assert acked_feed.status_code == 200
    assert any(item['id'] == schedule_item['id'] for item in acked_feed.get_json()['data']['items'])
