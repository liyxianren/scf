from datetime import date

import pytest

from extensions import db
from modules.auth.models import Enrollment, ReminderDelivery
from modules.oa import sms_reminder_services
from modules.oa import services as oa_services
from modules.oa.models import CourseSchedule
from tests.factories import create_enrollment, create_schedule, create_student_profile, create_user


pytestmark = pytest.mark.integration


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_intake_requires_delivery_preference_and_persists(client, login_as):
    admin = create_user(username='delivery-intake-admin', display_name='报名管理员', role='admin')
    teacher = create_user(username='delivery-intake-teacher', display_name='报名老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '方式学生',
            'course_name': '方式课程',
            'teacher_id': teacher.id,
            'total_hours': 4,
        },
    )
    payload = response.get_json()['data']
    token = payload['intake_url'].rsplit('/', 1)[-1]

    missing = client.post(
        f'/auth/intake/{token}',
        json={
            'name': '方式学生',
            'phone': '13800138009',
            'available_times': [{'day': 0, 'start': '10:00', 'end': '12:00'}],
        },
    )
    assert missing.status_code == 400
    assert missing.get_json()['error'] == '请先选择线上或线下上课方式'

    success = client.post(
        f'/auth/intake/{token}',
        json={
            'name': '方式学生',
            'phone': '13800138009',
            'delivery_preference': 'online',
            'available_times': [{'day': 0, 'start': '10:00', 'end': '12:00'}],
        },
    )
    assert success.status_code == 200
    enrollment = db.session.get(Enrollment, payload['id'])
    assert enrollment.delivery_preference == 'online'


def test_oa_schedule_delivery_mode_sets_color_and_meeting_defaults(client, login_as):
    admin = create_user(username='delivery-mode-admin', display_name='排课管理员', role='admin')
    teacher = create_user(username='delivery-mode-teacher', display_name='排课老师', role='teacher')

    login_as(admin)

    online = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-16',
            'time_start': '10:00',
            'time_end': '12:00',
            'teacher': teacher.display_name,
            'course_name': '线上课',
            'delivery_mode': 'online',
        },
    )
    online_payload = online.get_json()['data']
    assert online.status_code == 201
    assert online_payload['color_tag'] == 'blue'
    assert online_payload['delivery_mode'] == 'online'
    assert online_payload['meeting_status'] == 'pending'
    assert online_payload['meeting_provider'] == 'tencent_meeting'

    offline = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-17',
            'time_start': '10:00',
            'time_end': '12:00',
            'teacher': teacher.display_name,
            'course_name': '线下课',
            'delivery_mode': 'offline',
        },
    )
    offline_payload = offline.get_json()['data']
    assert offline.status_code == 201
    assert offline_payload['color_tag'] == 'orange'
    assert offline_payload['delivery_mode'] == 'offline'
    assert offline_payload['meeting_status'] == 'not_required'
    assert offline_payload['meeting_provider'] is None


def test_oa_schedule_create_rejects_legacy_green_color_tag(client, login_as):
    admin = create_user(username='legacy-green-admin', display_name='老颜色管理员', role='admin')
    teacher = create_user(username='legacy-green-teacher', display_name='老颜色老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-16',
            'time_start': '13:00',
            'time_end': '15:00',
            'teacher': teacher.display_name,
            'course_name': '旧颜色课次',
            'color_tag': 'green',
        },
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == '课程颜色已改为线上/线下两种模式；仅支持 blue 或 orange'


def test_backfill_schedule_delivery_sms_state_normalizes_legacy_teal_color(app):
    teacher = create_user(username='legacy-teal-teacher', display_name='历史颜色老师', role='teacher')
    student = create_user(username='legacy-teal-student', display_name='历史颜色学生', role='student')
    profile = create_student_profile(user=student, name='历史颜色学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='历史颜色学生',
        course_name='历史社团课',
        student_profile=profile,
        status='confirmed',
        delivery_preference='online',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='历史社团课',
        students='历史颜色学生',
        schedule_date=date(2026, 3, 16),
        time_start='19:00',
        time_end='21:00',
        enrollment=enrollment,
        color_tag='blue',
        delivery_mode='online',
        location='线上',
    )
    schedule.color_tag = 'teal'
    schedule.delivery_mode = 'unknown'
    schedule.meeting_provider = None
    schedule.meeting_status = 'not_required'
    db.session.commit()

    result = oa_services.backfill_schedule_delivery_sms_state()
    db.session.refresh(schedule)

    assert result['schedule_updates'] >= 1
    assert result['legacy_color_backfills']
    assert result['legacy_color_backfills'][0]['from_color_tag'] == 'teal'
    assert result['legacy_color_backfills'][0]['to_delivery_mode'] == 'online'
    assert schedule.color_tag == 'blue'
    assert schedule.delivery_mode == 'online'
    assert schedule.meeting_provider == 'tencent_meeting'
    assert schedule.meeting_status == 'pending'


def test_internal_sms_reminder_job_is_idempotent_and_reconciles(client, app):
    teacher = create_user(username='sms-teacher', display_name='短信老师', role='teacher')
    student = create_user(username='sms-student', display_name='短信学生', role='student')
    profile = create_student_profile(user=student, name='短信学生', phone='13800138077')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='短信学生',
        course_name='短信提醒课',
        student_profile=profile,
        status='confirmed',
        delivery_preference='online',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='短信提醒课',
        students='短信学生',
        schedule_date=date(2026, 3, 16),
        time_start='10:00',
        time_end='12:00',
        enrollment=enrollment,
        delivery_mode='online',
    )

    app.config.update({
        'SCF_REMINDER_JOB_TOKEN': 'reminder-token',
        'ALIYUN_SMS_ENABLED': True,
        'ALIYUN_SMS_ACCESS_KEY_ID': 'ak',
        'ALIYUN_SMS_ACCESS_KEY_SECRET': 'sk',
        'ALIYUN_SMS_SIGN_NAME': 'SCF',
        'ALIYUN_SMS_TEMPLATE_CODE_ONLINE': 'SMS_ONLINE',
        'ALIYUN_SMS_TEMPLATE_CODE_OFFLINE': 'SMS_OFFLINE',
    })

    call_log = []

    def _fake_post(url, params=None, headers=None, timeout=None):
        action = headers.get('x-acs-action')
        call_log.append({'action': action, 'params': dict(params or {})})
        if action == 'SendSms':
            return _DummyResponse({
                'Code': 'OK',
                'Message': 'OK',
                'BizId': 'biz-1',
                'RequestId': 'req-send',
            })
        return _DummyResponse({
            'Code': 'OK',
            'Message': 'OK',
            'RequestId': 'req-query',
            'TotalCount': '1',
            'SmsSendDetailDTOs': {
                'SmsSendDetailDTO': [
                    {
                        'ErrCode': 'DELIVERED',
                        'ReceiveDate': '2026-03-16 08:01:00',
                        'SendDate': '2026-03-16 08:00:10',
                        'PhoneNum': '13800138077',
                        'SendStatus': 3,
                    }
                ]
            },
        })

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(sms_reminder_services.requests, 'post', _fake_post)
    try:
        dry_run = client.post(
            '/oa/api/internal/reminders/sms/run',
            headers={'X-Reminder-Job-Token': 'reminder-token'},
            json={'dry_run': True, 'now': '2026-03-16T08:00:00'},
        )
        assert dry_run.status_code == 200
        assert dry_run.get_json()['data']['eligible'] == 1

        first_run = client.post(
            '/oa/api/internal/reminders/sms/run',
            headers={'X-Reminder-Job-Token': 'reminder-token'},
            json={'now': '2026-03-16T08:00:00'},
        )
        first_payload = first_run.get_json()['data']
        assert first_run.status_code == 200
        assert first_payload['sent'] == 1
        assert call_log[0]['action'] == 'SendSms'
        assert call_log[0]['params']['TemplateCode'] == 'SMS_ONLINE'

        second_run = client.post(
            '/oa/api/internal/reminders/sms/run',
            headers={'X-Reminder-Job-Token': 'reminder-token'},
            json={'now': '2026-03-16T08:05:00'},
        )
        second_payload = second_run.get_json()['data']
        assert second_run.status_code == 200
        assert second_payload['skipped']['existing_delivery'] == 1

        delivery = ReminderDelivery.query.filter_by(
            channel='aliyun_sms',
            receiver_external_id='13800138077',
        ).first()
        assert delivery is not None
        assert delivery.delivery_status == 'delivered'
        assert delivery.provider_message_id == 'biz-1'
    finally:
        monkeypatch.undo()
