import json
from datetime import date

import pytest

from extensions import db
from modules.auth.models import ChatMessage, Enrollment, User
from modules.auth.services import (
    FEEDBACK_PREFIX,
    find_matching_slots,
    propose_enrollment_schedule,
    student_confirm_schedule,
)
from modules.oa.models import CourseSchedule
from tests.factories import (
    create_enrollment,
    create_schedule,
    create_student_profile,
    create_teacher_availability,
    create_user,
)


pytestmark = pytest.mark.integration


def _slots_for_days(days, start='10:00', end='12:00'):
    return [{'day': day, 'start': start, 'end': end} for day in days]


def test_enrollment_lifecycle_reject_then_confirm(client, login_as, logout):
    admin = create_user(username='flow-admin', display_name='流程管理员', role='admin')
    teacher = create_user(username='flow-teacher', display_name='流程老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '流程学生',
            'course_name': 'Python 正课',
            'teacher_id': teacher.id,
            'total_hours': 6,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    assert payload['success'] is True
    enrollment_id = payload['data']['id']
    intake_url = payload['data']['intake_url']
    token = intake_url.rsplit('/', 1)[-1]
    logout()

    response = client.post(
        f'/auth/intake/{token}',
        json={
            'name': '流程学生',
            'phone': '13800138000',
            'available_times': _slots_for_days([0, 2, 4]),
            'excluded_dates': ['2026-03-18'],
            'notes': '周三第一周不行',
        },
    )
    payload = response.get_json()
    assert payload['success'] is True
    student = db.session.get(User, payload['account']['user_id'])
    assert student is not None

    login_as(teacher)
    response = client.post(
        f'/auth/api/teacher/{teacher.id}/availability',
        json={
            'available': _slots_for_days([0, 2, 4]),
            'preferred': [{'day': 0, 'start': '10:00', 'end': '12:00'}],
        },
    )
    assert response.get_json()['success'] is True
    logout()

    login_as(admin)
    response = client.post(f'/auth/api/enrollments/{enrollment_id}/match')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['proposed_slots']
    assert payload['proposed_slots'][0]['weekly_slots']

    response = client.post(f'/auth/api/enrollments/{enrollment_id}/confirm', json={'slot_index': 0})
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['dates']
    assert db.session.get(Enrollment, enrollment_id).status == 'pending_student_confirm'
    logout()

    login_as(student)
    response = client.post(
        f'/auth/api/enrollments/{enrollment_id}/student-reject',
        json={'message': '周三第一周上不了，请重排'},
    )
    payload = response.get_json()
    assert payload['success'] is True
    enrollment = db.session.get(Enrollment, enrollment_id)
    assert enrollment.status == 'pending_schedule'

    feedback = ChatMessage.query.filter_by(enrollment_id=enrollment_id).order_by(ChatMessage.created_at.desc()).first()
    assert feedback is not None
    assert feedback.content.startswith(FEEDBACK_PREFIX)
    logout()

    login_as(teacher)
    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    assert payload['success'] is True
    conversation = next(item for item in payload['data'] if item['user_id'] == student.id)
    assert conversation['unread_count'] == 1
    logout()

    login_as(admin)
    response = client.post(f'/auth/api/enrollments/{enrollment_id}/match')
    assert response.get_json()['success'] is True
    response = client.post(f'/auth/api/enrollments/{enrollment_id}/confirm', json={'slot_index': 0})
    assert response.get_json()['success'] is True
    logout()

    login_as(student)
    response = client.post(f'/auth/api/enrollments/{enrollment_id}/student-confirm')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['created_count'] == 3

    schedules = CourseSchedule.query.filter_by(enrollment_id=enrollment_id).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()
    assert len(schedules) == 3
    assert all(schedule.teacher_id == teacher.id for schedule in schedules)
    assert all(schedule.enrollment_id == enrollment_id for schedule in schedules)
    assert db.session.get(Enrollment, enrollment_id).status == 'confirmed'


def test_schedule_matching_creates_multi_session_records(app):
    teacher = create_user(username='algo-teacher', display_name='算法老师', role='teacher')
    student = create_user(username='algo-student', display_name='算法学生', role='student')

    for day in [0, 2, 3, 4, 5]:
        create_teacher_availability(user=teacher, day_of_week=day, time_start='10:00', time_end='12:00')

    profile = create_student_profile(
        user=student,
        name='算法学生',
        available_slots=_slots_for_days([0, 2, 3, 4, 5, 6]),
        excluded_dates=['2026-03-18'],
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='算法学生',
        course_name='多日排课课',
        student_profile=profile,
        status='pending_schedule',
        total_hours=20,
        hours_per_session=2.0,
    )

    plans, error = find_matching_slots(enrollment.id)
    assert error is None
    assert plans

    first_plan = plans[0]
    assert first_plan['total_sessions'] == 10
    assert first_plan['distinct_days'] == 5
    assert {slot['day_of_week'] for slot in first_plan['weekly_slots']} == {0, 2, 3, 4, 5}
    assert all(session['date'] != '2026-03-18' for session in first_plan['session_dates'])

    enrollment.proposed_slots = json.dumps(plans, ensure_ascii=False)
    response, message, dates = propose_enrollment_schedule(enrollment.id, 0)
    assert response is True
    assert dates
    assert '已通知学生确认' in message

    response, message, created_count = student_confirm_schedule(enrollment.id)
    assert response is True
    assert created_count == 10

    schedules = CourseSchedule.query.filter_by(enrollment_id=enrollment.id).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()
    assert len(schedules) == 10
    assert {schedule.day_of_week for schedule in schedules} == {0, 2, 3, 4, 5}
    assert all(schedule.teacher_id == teacher.id for schedule in schedules)
    assert all(schedule.enrollment_id == enrollment.id for schedule in schedules)


def test_student_can_update_intake_and_force_rematch(client, login_as):
    admin = create_user(username='intake-admin', display_name='改档管理员', role='admin')
    teacher = create_user(username='intake-teacher', display_name='改档老师', role='teacher')
    student = create_user(username='intake-student', display_name='改档学生', role='student')
    profile = create_student_profile(
        user=student,
        name='改档学生',
        available_slots=_slots_for_days([0, 2]),
        excluded_dates=['2026-03-18'],
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='改档学生',
        course_name='可改时间课程',
        student_profile=profile,
        status='pending_student_confirm',
        proposed_slots=[{'day_of_week': 0, 'time_start': '10:00', 'time_end': '12:00'}],
        confirmed_slot={'day_of_week': 0, 'time_start': '10:00', 'time_end': '12:00'},
    )

    login_as(student)
    response = client.put(
        f'/auth/api/enrollments/{enrollment.id}/intake',
        json={
            'name': '改档学生',
            'phone': '13800138001',
            'available_times': _slots_for_days([1, 3, 5]),
            'excluded_dates': ['2026-03-20'],
            'notes': '只想要周二周四周六',
        },
    )
    payload = response.get_json()
    assert payload['success'] is True

    enrollment = db.session.get(Enrollment, enrollment.id)
    assert enrollment.status == 'pending_schedule'
    assert enrollment.proposed_slots is None
    assert enrollment.confirmed_slot is None
    assert profile.to_dict()['available_slots'] == _slots_for_days([1, 3, 5])

    login_as(admin)
    response = client.get(f'/auth/api/enrollments/{enrollment.id}')
    payload = response.get_json()['data']
    assert payload['status'] == 'pending_schedule'
    assert payload['can_edit'] is True


def test_leave_approval_and_feedback_visibility(client, login_as, logout):
    teacher = create_user(username='feedback-teacher', display_name='反馈老师', role='teacher')
    student = create_user(username='feedback-student', display_name='反馈学生', role='student')
    profile = create_student_profile(user=student, name='反馈学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='反馈学生',
        course_name='反馈课程',
        student_profile=profile,
        status='confirmed',
    )
    feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='反馈课程',
        students='反馈学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 16),
        time_start='08:00',
        time_end='09:00',
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='反馈课程',
        students='反馈学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 17),
    )

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={'schedule_id': leave_schedule.id, 'reason': '校内活动'})
    payload = response.get_json()
    assert response.status_code == 201
    assert payload['success'] is True
    leave_id = payload['data']['id']

    response = client.get(f'/auth/api/schedules/{feedback_schedule.id}/feedback')
    assert response.get_json()['data'] is None
    logout()

    login_as(teacher)
    response = client.get('/auth/api/leave-requests')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data'][0]['can_approve_leave'] is True

    response = client.put(f'/auth/api/leave-requests/{leave_id}/approve')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['status'] == 'approved'

    response = client.post(
        f'/auth/api/schedules/{leave_schedule.id}/feedback',
        json={'summary': '未来课程不能写反馈', 'homework': '无', 'next_focus': '无'},
    )
    assert response.status_code == 400

    response = client.post(
        f'/auth/api/schedules/{feedback_schedule.id}/feedback',
        json={'summary': '草稿总结', 'homework': '草稿作业', 'next_focus': '草稿重点'},
    )
    assert response.get_json()['success'] is True
    logout()

    login_as(student)
    response = client.get(f'/auth/api/schedules/{feedback_schedule.id}/feedback')
    assert response.get_json()['data'] is None
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/schedules/{feedback_schedule.id}/feedback/submit',
        json={'summary': '完成了一次项目拆解', 'homework': '整理项目思路', 'next_focus': '准备需求文档'},
    )
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['status'] == 'submitted'
    logout()

    login_as(student)
    response = client.get(f'/auth/api/schedules/{feedback_schedule.id}/feedback')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['summary'] == '完成了一次项目拆解'

    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    assert any('请假审批' in item['last_message'] for item in payload['data'])


def test_time_based_leave_and_status_sync(client, login_as, logout):
    admin = create_user(username='status-admin', display_name='状态管理员', role='admin')
    teacher = create_user(username='status-teacher', display_name='状态老师', role='teacher')
    student = create_user(username='status-student', display_name='状态学生', role='student')
    profile = create_student_profile(user=student, name='状态学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='状态学生',
        course_name='状态课程',
        student_profile=profile,
        status='confirmed',
    )
    started_schedule = create_schedule(
        teacher=teacher,
        course_name='状态课程',
        students='状态学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 16),
        time_start='08:00',
        time_end='09:00',
    )
    future_schedule = create_schedule(
        teacher=teacher,
        course_name='状态课程',
        students='状态学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={'schedule_id': started_schedule.id, 'reason': '已开始不可请假'})
    assert response.status_code == 403
    response = client.post('/auth/api/leave-requests', json={'schedule_id': future_schedule.id, 'reason': '明天请假'})
    assert response.status_code == 201
    leave_id = response.get_json()['data']['id']
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/schedules/{future_schedule.id}/feedback/submit',
        json={'summary': '未来课次', 'homework': '无', 'next_focus': '无'},
    )
    assert response.status_code == 400

    response = client.put(f'/auth/api/leave-requests/{leave_id}/approve')
    assert response.status_code == 200

    response = client.post(
        f'/auth/api/schedules/{started_schedule.id}/feedback/submit',
        json={'summary': '已完成', 'homework': '复盘', 'next_focus': '继续推进'},
    )
    assert response.status_code == 200
    assert db.session.get(Enrollment, enrollment.id).status == 'active'
    logout()

    login_as(admin)
    response = client.delete(f'/oa/api/schedules/{future_schedule.id}')
    assert response.status_code == 200

    refreshed = db.session.get(Enrollment, enrollment.id)
    assert refreshed.status == 'completed'

    response = client.get(f'/auth/api/enrollments/{enrollment.id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['status'] == 'completed'
