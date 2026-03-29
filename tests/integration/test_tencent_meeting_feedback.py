import base64
import hashlib
import json
from datetime import date, timedelta

import pytest

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import FeedbackShareLink, IntegrationActionLog
from modules.oa import tencent_meeting_services
from modules.oa.models import CourseFeedback, CourseSchedule, ScheduleMeetingMaterial
from tests.factories import (
    create_enrollment,
    create_feedback,
    create_schedule,
    create_schedule_meeting_material,
    create_student_profile,
    create_user,
)


pytestmark = pytest.mark.integration


def _configure_tencent(app):
    app.config.update({
        'TENCENT_MEETING_ENABLED': True,
        'TENCENT_MEETING_APP_ID': 'app-id',
        'TENCENT_MEETING_SDK_ID': 'sdk-id',
        'TENCENT_MEETING_SECRET_ID': 'secret-id',
        'TENCENT_MEETING_SECRET_KEY': 'secret-key',
        'TENCENT_MEETING_CREATOR_USERID': 'creator-user',
        'TENCENT_MEETING_CREATOR_INSTANCE_ID': 1,
        'TENCENT_MEETING_JOB_TOKEN': 'meeting-job-token',
        'TENCENT_MEETING_WEBHOOK_TOKEN': 'meeting-webhook-token',
        'TENCENT_MEETING_WEBHOOK_AES_KEY': '',
        'COURSE_FEEDBACK_AI_PROVIDER': 'zhipu',
    })


def _job_headers():
    return {'X-Tencent-Meeting-Job-Token': 'meeting-job-token'}


def _webhook_headers(data_value, *, token='meeting-webhook-token', timestamp='1742083200000', nonce='33445566'):
    values = [token, timestamp, nonce, data_value]
    values.sort()
    signature = hashlib.sha1(''.join(values).encode('utf-8')).hexdigest()
    return {
        'timestamp': timestamp,
        'nonce': nonce,
        'signature': signature,
    }


def test_internal_tencent_meeting_create_due_job_is_idempotent(client, app):
    _configure_tencent(app)
    teacher = create_user(username='tm-create-teacher', display_name='腾讯会议老师', role='teacher')
    student = create_user(username='tm-create-student', display_name='腾讯会议学生', role='student')
    profile = create_student_profile(user=student, name='腾讯会议学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='腾讯会议学生',
        course_name='线上反馈课',
        student_profile=profile,
        status='confirmed',
        delivery_preference='online',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='线上反馈课',
        students='腾讯会议学生',
        schedule_date=date(2026, 3, 16),
        time_start='10:00',
        time_end='12:00',
        enrollment=enrollment,
        delivery_mode='online',
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        tencent_meeting_services.TencentMeetingClient,
        'create_meeting',
        lambda self, _schedule: {
            'meeting_external_id': 'meeting-001',
            'meeting_code': '99887766',
            'meeting_password': '2468',
            'meeting_join_url': 'https://meeting.tencent.test/join/meeting-001',
        },
    )
    try:
        dry_run = client.post(
            '/oa/api/internal/tencent-meeting/create-due',
            headers=_job_headers(),
            json={'dry_run': True, 'now': '2026-03-16T08:00:00'},
        )
        assert dry_run.status_code == 200
        assert dry_run.get_json()['data']['eligible'] == 1

        first_run = client.post(
            '/oa/api/internal/tencent-meeting/create-due',
            headers=_job_headers(),
            json={'now': '2026-03-16T08:00:00'},
        )
        assert first_run.status_code == 200
        assert first_run.get_json()['data']['created'] == 1
        refreshed = db.session.get(CourseSchedule, schedule.id)
        assert refreshed.meeting_status == 'ready'
        assert refreshed.meeting_external_id == 'meeting-001'
        assert refreshed.meeting_code == '99887766'
        assert refreshed.meeting_join_url == 'https://meeting.tencent.test/join/meeting-001'

        second_run = client.post(
            '/oa/api/internal/tencent-meeting/create-due',
            headers=_job_headers(),
            json={'now': '2026-03-16T08:05:00'},
        )
        assert second_run.status_code == 200
        assert second_run.get_json()['data']['skipped']['existing_meeting'] == 1
    finally:
        monkeypatch.undo()


def test_oa_schedule_delete_cancels_ready_tencent_meeting(client, app, login_as):
    _configure_tencent(app)
    admin = create_user(username='tm-delete-admin', display_name='删课教务', role='admin')
    teacher = create_user(username='tm-delete-teacher', display_name='删课老师', role='teacher')

    schedule = create_schedule(
        teacher=teacher,
        course_name='待取消线上课',
        students='删课学生',
        schedule_date=date(2026, 3, 16),
        time_start='10:00',
        time_end='12:00',
        delivery_mode='online',
    )
    schedule.meeting_provider = 'tencent_meeting'
    schedule.meeting_status = 'ready'
    schedule.meeting_external_id = 'meeting-delete-001'
    schedule.meeting_join_url = 'https://meeting.tencent.test/join/delete'
    schedule.meeting_code = '11223344'
    db.session.commit()

    cancelled = []
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        tencent_meeting_services.TencentMeetingClient,
        'cancel_meeting',
        lambda self, meeting_id, reason_detail='': cancelled.append((meeting_id, reason_detail)) or {'success': True},
    )
    try:
        login_as(admin)
        response = client.delete(
            f'/oa/api/schedules/{schedule.id}',
            json={'reason': '线上课取消'},
        )
        assert response.status_code == 200
        refreshed = db.session.get(CourseSchedule, schedule.id)
        assert refreshed.is_cancelled is True
        assert refreshed.meeting_status == 'cancelled'
        assert refreshed.meeting_join_url is None
        assert cancelled[0][0] == 'meeting-delete-001'
    finally:
        monkeypatch.undo()


def test_tencent_meeting_webhook_marks_meeting_end_and_is_idempotent(client, app):
    _configure_tencent(app)
    teacher = create_user(username='tm-webhook-teacher', display_name='Webhook老师', role='teacher')
    schedule = create_schedule(
        teacher=teacher,
        course_name='Webhook 线上课',
        students='Webhook 学生',
        schedule_date=date(2026, 3, 16),
        time_start='10:00',
        time_end='12:00',
        delivery_mode='online',
    )
    schedule.meeting_provider = 'tencent_meeting'
    schedule.meeting_status = 'ready'
    schedule.meeting_external_id = 'meeting-webhook-001'
    db.session.commit()

    payload = {
        'event': 'meeting.end',
        'trace_id': 'trace-meeting-end-001',
        'payload': [{
            'operate_time': 1742090400000,
            'meeting_info': {
                'meeting_id': 'meeting-webhook-001',
                'meeting_code': '77889900',
            },
        }],
    }
    data_value = base64.b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    ).decode('utf-8')

    first = client.post(
        '/oa/api/integrations/tencent-meeting/webhook',
        headers=_webhook_headers(data_value),
        json={'data': data_value},
    )
    assert first.status_code == 200
    assert first.data.decode('utf-8') == tencent_meeting_services.WEBHOOK_SUCCESS_BODY

    refreshed = db.session.get(CourseSchedule, schedule.id)
    assert refreshed.meeting_status == 'ended'
    assert refreshed.meeting_ended_at is not None
    assert ScheduleMeetingMaterial.query.filter_by(schedule_id=schedule.id).count() == 1

    replay = client.post(
        '/oa/api/integrations/tencent-meeting/webhook',
        headers=_webhook_headers(data_value),
        json={'data': data_value},
    )
    assert replay.status_code == 200
    assert IntegrationActionLog.query.filter_by(client_name='tencent_meeting_webhook').count() == 1


def test_tencent_meeting_materials_and_feedback_draft_jobs(client, app, login_as):
    _configure_tencent(app)
    teacher = create_user(username='tm-material-teacher', display_name='材料老师', role='teacher')
    student = create_user(username='tm-material-student', display_name='材料学生', role='student')
    profile = create_student_profile(user=student, name='材料学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='材料学生',
        course_name='纪要课',
        student_profile=profile,
        status='active',
        delivery_preference='online',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='纪要课',
        students='材料学生',
        schedule_date=date(2026, 3, 15),
        time_start='10:00',
        time_end='12:00',
        enrollment=enrollment,
        delivery_mode='online',
    )
    schedule.meeting_provider = 'tencent_meeting'
    schedule.meeting_status = 'ended'
    schedule.meeting_external_id = 'meeting-material-001'
    db.session.commit()
    create_schedule_meeting_material(schedule=schedule, record_id='record-001', material_status='pending')

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        tencent_meeting_services.TencentMeetingClient,
        'get_smart_minutes',
        lambda self, record_id: {'meeting_minute': {'minute': f'{record_id}: 今天完成循环与函数讲解'}},
    )
    monkeypatch.setattr(
        tencent_meeting_services,
        'generate_feedback_ai_draft',
        lambda _schedule, _material: {
            'content_summary': '今天完成循环与函数讲解，并结合例题做了课堂练习。',
            'source_type': 'minutes',
            'provider': 'zhipu',
        },
    )
    try:
        material_job = client.post(
            '/oa/api/internal/tencent-meeting/materials/run',
            headers=_job_headers(),
            json={'now': '2026-03-16T09:00:00'},
        )
        assert material_job.status_code == 200
        assert material_job.get_json()['data']['synced'] == 1

        draft_job = client.post(
            '/oa/api/internal/tencent-meeting/feedback-drafts/run',
            headers=_job_headers(),
            json={'now': '2026-03-16T09:10:00'},
        )
        assert draft_job.status_code == 200
        assert draft_job.get_json()['data']['generated'] == 1

        login_as(teacher)
        feedback_response = client.get(f'/auth/api/schedules/{schedule.id}/feedback')
        payload = feedback_response.get_json()['data']
        assert payload['ai_content_draft'] == '今天完成循环与函数讲解，并结合例题做了课堂练习。'
        assert payload['ai_draft_status'] == 'ready'
        assert payload['ai_model_provider'] == 'zhipu'
        assert payload['summary'] is None
    finally:
        monkeypatch.undo()


def test_feedback_api_share_link_and_pdf_export(client, app, login_as):
    _configure_tencent(app)
    admin = create_user(username='tm-share-admin', display_name='反馈教务', role='admin')
    teacher = create_user(username='tm-share-teacher', display_name='反馈老师', role='teacher')
    student = create_user(username='tm-share-student', display_name='反馈学生', role='student')
    profile = create_student_profile(user=student, name='反馈学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='反馈学生',
        course_name='反馈课程',
        student_profile=profile,
        status='active',
        delivery_preference='online',
    )
    submitted_schedule = create_schedule(
        teacher=teacher,
        course_name='反馈课程',
        students='反馈学生',
        schedule_date=date(2026, 3, 15),
        time_start='07:00',
        time_end='08:00',
        enrollment=enrollment,
        delivery_mode='online',
    )
    create_feedback(
        schedule=submitted_schedule,
        teacher=teacher,
        summary='第一节课完成变量与条件判断。',
        student_performance='能主动回答问题，但书写还需要更规范。',
        homework='整理课堂笔记并完成两道练习题。',
        next_focus='下次进入循环结构。',
        status='submitted',
    )

    editable_schedule = create_schedule(
        teacher=teacher,
        course_name='反馈课程',
        students='反馈学生',
        schedule_date=date(2026, 3, 16),
        time_start='07:00',
        time_end='08:00',
        enrollment=enrollment,
        delivery_mode='online',
    )

    login_as(teacher)
    save_response = client.post(
        f'/auth/api/schedules/{editable_schedule.id}/feedback',
        json={
            'summary': '第二节课完成 while 与 for 循环。',
            'student_performance': '能够独立完成基础循环题，调试速度更快。',
            'homework': '完成循环练习题 3 题。',
            'next_focus': '数组与列表。',
        },
    )
    assert save_response.status_code == 200
    saved_payload = save_response.get_json()['data']
    assert saved_payload['student_performance'] == '能够独立完成基础循环题，调试速度更快。'

    submit_response = client.post(
        f'/auth/api/schedules/{editable_schedule.id}/feedback/submit',
        json={
            'summary': '第二节课完成 while 与 for 循环。',
            'student_performance': '能够独立完成基础循环题，调试速度更快。',
            'homework': '完成循环练习题 3 题。',
            'next_focus': '数组与列表。',
        },
    )
    assert submit_response.status_code == 200
    assert db.session.get(CourseFeedback, saved_payload['id']).status == 'submitted'

    login_as(admin)
    share_response = client.post(f'/auth/api/enrollments/{enrollment.id}/feedback-share-links', json={})
    assert share_response.status_code == 200
    share_payload = share_response.get_json()['data']
    assert '/auth/feedback-share/' in share_payload['share_url']

    html_response = client.get(f"/auth/feedback-share/{share_payload['token']}")
    assert html_response.status_code == 200
    assert '第一节课完成变量与条件判断'.encode('utf-8') in html_response.data
    assert '学生表现'.encode('utf-8') in html_response.data

    pdf_response = client.get(f"/auth/feedback-share/{share_payload['token']}/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.content_type == 'application/pdf'

    internal_pdf = client.get(f'/auth/api/enrollments/{enrollment.id}/feedback-report.pdf')
    assert internal_pdf.status_code == 200
    assert internal_pdf.content_type == 'application/pdf'

    link = FeedbackShareLink.query.filter_by(token=share_payload['token']).first()
    link.expires_at = auth_services.get_business_now() - timedelta(days=1)
    db.session.commit()

    expired_response = client.get(f"/auth/feedback-share/{share_payload['token']}")
    assert expired_response.status_code == 403
