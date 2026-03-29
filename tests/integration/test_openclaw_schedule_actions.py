from datetime import date

from extensions import db
from modules.auth.models import IntegrationActionLog
from modules.auth.workflow_services import ensure_schedule_feedback_todo
from modules.oa.models import OATodo
from tests.factories import (
    create_enrollment,
    create_external_identity,
    create_schedule,
    create_student_profile,
    create_teacher_availability,
    create_todo,
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


def test_openclaw_schedule_quick_shift_is_admin_only_and_idempotent(client, app):
    admin = create_user(role='admin', username='schedule-admin')
    teacher = create_user(role='teacher', username='schedule-teacher')
    admin_identity = create_external_identity(user=admin, external_user_id='ou_schedule_admin')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_schedule_teacher')

    schedule = create_schedule(
        teacher=teacher,
        course_name='Biology',
        students='Legacy Student',
        schedule_date=date(2026, 3, 20),
        time_start='10:00',
        time_end='12:00',
    )

    forbidden = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            teacher_identity,
            'req-quick-shift-forbidden',
            'schedule.quick_shift',
            {
                'schedule_id': schedule.id,
                'date_shift_days': 1,
                'time_shift_minutes': 30,
            },
        ),
        headers=_headers(app),
    )
    assert forbidden.status_code == 403

    payload = _command(
        admin_identity,
        'req-quick-shift-success',
        'schedule.quick_shift',
        {
            'schedule_id': schedule.id,
            'date_shift_days': 1,
            'time_shift_minutes': 30,
        },
    )
    first = client.post('/oa/api/integration/openclaw/command', json=payload, headers=_headers(app))
    assert first.status_code == 200
    db.session.refresh(schedule)
    assert schedule.date.isoformat() == '2026-03-21'
    assert schedule.time_start == '10:30'
    assert schedule.time_end == '12:30'

    replay = client.post('/oa/api/integration/openclaw/command', json=payload, headers=_headers(app))
    assert replay.status_code == 200
    assert replay.get_json()['data']['integration_meta']['replayed'] is True
    assert IntegrationActionLog.query.filter_by(request_id='req-quick-shift-success').count() == 1


def test_openclaw_schedule_quick_shift_blocks_conflicts(client, app):
    admin = create_user(role='admin', username='schedule-admin-conflict')
    teacher = create_user(role='teacher', username='schedule-teacher-conflict')
    identity = create_external_identity(user=admin, external_user_id='ou_schedule_admin_conflict')

    base_schedule = create_schedule(
        teacher=teacher,
        course_name='Physics',
        students='Student A',
        schedule_date=date(2026, 3, 20),
        time_start='10:00',
        time_end='12:00',
    )
    create_schedule(
        teacher=teacher,
        course_name='Physics',
        students='Student B',
        schedule_date=date(2026, 3, 21),
        time_start='10:30',
        time_end='12:30',
    )

    response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-quick-shift-conflict',
            'schedule.quick_shift',
            {
                'schedule_id': base_schedule.id,
                'date_shift_days': 1,
                'time_shift_minutes': 30,
            },
        ),
        headers=_headers(app),
    )
    assert response.status_code == 400
    db.session.refresh(base_schedule)
    assert base_schedule.date.isoformat() == '2026-03-20'
    assert base_schedule.time_start == '10:00'


def test_openclaw_schedule_reschedule_preview_and_apply_update_schedule(client, app):
    admin = create_user(role='admin', username='schedule-admin-reschedule')
    teacher = create_user(role='teacher', username='schedule-teacher-reschedule')
    student_user = create_user(role='student', username='schedule-student-reschedule')
    identity = create_external_identity(user=admin, external_user_id='ou_schedule_admin_reschedule')
    create_teacher_availability(user=teacher)
    profile = create_student_profile(user=student_user, name='Reschedule Student')
    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Reschedule Student',
        course_name='History',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='History',
        students='Reschedule Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 20),
        time_start='10:00',
        time_end='12:00',
    )
    todo = ensure_schedule_feedback_todo(schedule, created_by=teacher.id)
    db.session.commit()

    preview = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-reschedule-preview',
            'schedule.reschedule.preview',
            {
                'schedule_id': schedule.id,
                'date': '2026-03-22',
                'time_start': '13:00',
                'time_end': '15:00',
                'location': 'Room 301',
                'notes': 'shifted',
                'delivery_mode': 'offline',
            },
        ),
        headers=_headers(app),
    )
    assert preview.status_code == 200
    preview_payload = preview.get_json()['data']
    assert preview_payload['before']['date'] == '2026-03-20'
    assert preview_payload['after']['date'] == '2026-03-22'
    assert preview_payload['can_apply'] is True
    db.session.refresh(schedule)
    assert schedule.date.isoformat() == '2026-03-20'

    apply_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-reschedule-apply',
            'schedule.reschedule.apply',
            {
                'schedule_id': schedule.id,
                'date': '2026-03-22',
                'time_start': '13:00',
                'time_end': '15:00',
                'location': 'Room 301',
                'notes': 'shifted',
                'delivery_mode': 'offline',
            },
        ),
        headers=_headers(app),
    )
    assert apply_response.status_code == 200
    db.session.refresh(schedule)
    db.session.refresh(todo)
    db.session.refresh(enrollment)
    assert schedule.date.isoformat() == '2026-03-22'
    assert schedule.time_start == '13:00'
    assert schedule.location == 'Room 301'
    assert schedule.color_tag == 'orange'
    assert schedule.delivery_mode == 'offline'
    assert todo.schedule_id == schedule.id
    assert todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
    assert enrollment.status == 'confirmed'


def test_openclaw_schedule_reassign_teacher_preview_and_apply_require_unbound_schedule(client, app):
    admin = create_user(role='admin', username='schedule-admin-reassign')
    teacher = create_user(role='teacher', username='schedule-teacher-reassign-1')
    new_teacher = create_user(role='teacher', username='schedule-teacher-reassign-2')
    student_user = create_user(role='student', username='schedule-student-reassign')
    identity = create_external_identity(user=admin, external_user_id='ou_schedule_admin_reassign')
    profile = create_student_profile(user=student_user, name='Reassign Student')
    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Reassign Student',
        course_name='Economics',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    bound_schedule = create_schedule(
        teacher=teacher,
        course_name='Economics',
        students='Reassign Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 21),
    )
    unbound_schedule = create_schedule(
        teacher=teacher,
        course_name='Legacy Course',
        students='Legacy Student',
        schedule_date=date(2026, 3, 21),
    )

    blocked_preview = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-reassign-preview-blocked',
            'schedule.reassign_teacher.preview',
            {
                'schedule_id': bound_schedule.id,
                'teacher_id': new_teacher.id,
            },
        ),
        headers=_headers(app),
    )
    assert blocked_preview.status_code == 200
    assert blocked_preview.get_json()['data']['code'] == 'reassign_teacher_requires_unbound_schedule'
    db.session.refresh(bound_schedule)
    assert bound_schedule.teacher_id == teacher.id

    success_preview = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-reassign-preview-success',
            'schedule.reassign_teacher.preview',
            {
                'schedule_id': unbound_schedule.id,
                'teacher_id': new_teacher.id,
            },
        ),
        headers=_headers(app),
    )
    assert success_preview.status_code == 200
    assert success_preview.get_json()['data']['after']['teacher_id'] == new_teacher.id

    apply_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-reassign-apply-success',
            'schedule.reassign_teacher.apply',
            {
                'schedule_id': unbound_schedule.id,
                'teacher_id': new_teacher.id,
            },
        ),
        headers=_headers(app),
    )
    assert apply_response.status_code == 200
    db.session.refresh(unbound_schedule)
    assert unbound_schedule.teacher_id == new_teacher.id

    blocked_apply = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-reassign-apply-blocked',
            'schedule.reassign_teacher.apply',
            {
                'schedule_id': bound_schedule.id,
                'teacher_id': new_teacher.id,
            },
        ),
        headers=_headers(app),
    )
    assert blocked_apply.status_code == 400
    assert blocked_apply.get_json()['code'] == 'reassign_teacher_requires_unbound_schedule'
