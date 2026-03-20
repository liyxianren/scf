from datetime import datetime

import pytest

from extensions import db
from modules.auth.models import ChatMessage, Enrollment, User
from tests.factories import create_chat_message, create_enrollment, create_student_profile, create_user


pytestmark = pytest.mark.integration


def test_login_and_role_redirects(client, login_as, logout):
    admin = create_user(username='admin-user', display_name='管理员甲', role='admin')
    teacher = create_user(username='teacher-user', display_name='教师甲', role='teacher')
    student = create_user(username='student-user', display_name='学生甲', role='student')

    response = login_as(admin)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/admin/dashboard')
    logout()

    response = login_as(teacher)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/teacher/dashboard')
    logout()

    response = login_as(student)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/student/dashboard')
    logout()

    response = client.get('/auth/admin/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']

    login_as(teacher)
    response = client.get('/auth/admin/dashboard')
    assert response.status_code == 403


def test_chat_unread_count_and_mark_read(client, login_as):
    teacher = create_user(username='teacher-chat', display_name='聊天老师', role='teacher')
    student = create_user(username='student-chat', display_name='聊天学生', role='student')
    profile = create_student_profile(user=student, name='聊天学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='聊天学生',
        course_name='聊天课程',
        student_profile=profile,
        status='active',
    )
    create_chat_message(sender=student, receiver=teacher, enrollment=enrollment, content='老师您好', is_read=False)

    login_as(teacher)

    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    assert payload['success'] is True
    assert len(payload['data']) == 1
    conversation = payload['data'][0]
    assert conversation['user_id'] == student.id
    assert conversation['unread'] == 1
    assert conversation['unread_count'] == 1

    response = client.get(f'/auth/api/chat/messages?with={student.id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data'][0]['content'] == '老师您好'
    assert payload['data'][0]['created_at'].endswith('+08:00')

    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    conversation = payload['data'][0]
    assert conversation['unread'] == 0
    assert conversation['unread_count'] == 0


def test_chat_timestamps_are_serialized_as_business_time(client, login_as):
    teacher = create_user(username='time-teacher', display_name='时间老师', role='teacher')
    student = create_user(username='time-student', display_name='时间学生', role='student')
    profile = create_student_profile(user=student, name='时间学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='时间学生',
        course_name='时间课程',
        student_profile=profile,
        status='active',
    )
    message = create_chat_message(sender=student, receiver=teacher, enrollment=enrollment, content='测试时区')
    message.created_at = datetime(2026, 3, 19, 2, 30, 0)
    db.session.commit()

    login_as(teacher)
    response = client.get(f'/auth/api/chat/messages?with={student.id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data'][0]['created_at'] == '2026-03-19T10:30:00+08:00'


def test_chat_send_and_message_access_are_relationship_scoped(client, login_as, logout):
    admin = create_user(username='chat-admin', display_name='聊天管理员', role='admin')
    teacher = create_user(username='chat-teacher', display_name='关联老师', role='teacher')
    related_student = create_user(username='chat-student', display_name='关联学生', role='student')
    unrelated_student = create_user(username='chat-student-other', display_name='无关学生', role='student')
    unrelated_teacher = create_user(username='chat-teacher-other', display_name='无关老师', role='teacher')

    related_profile = create_student_profile(user=related_student, name='关联学生')
    create_student_profile(user=unrelated_student, name='无关学生')
    create_enrollment(
        teacher=teacher,
        student_name='关联学生',
        course_name='聊天权限课',
        student_profile=related_profile,
        status='active',
    )

    login_as(teacher)
    response = client.post('/auth/api/chat/send', json={'receiver_id': related_student.id, 'content': '排课沟通'})
    assert response.status_code == 201
    response = client.post('/auth/api/chat/send', json={'receiver_id': unrelated_student.id, 'content': '越权消息'})
    assert response.status_code == 403
    response = client.get(f'/auth/api/chat/messages?with={unrelated_student.id}')
    assert response.status_code == 403
    logout()

    login_as(related_student)
    response = client.post('/auth/api/chat/send', json={'receiver_id': teacher.id, 'content': '老师好'})
    assert response.status_code == 201
    response = client.post('/auth/api/chat/send', json={'receiver_id': unrelated_teacher.id, 'content': '越权消息'})
    assert response.status_code == 403
    logout()

    login_as(admin)
    response = client.post('/auth/api/chat/send', json={'receiver_id': unrelated_student.id, 'content': '管理员消息'})
    assert response.status_code == 201
    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    assert payload['success'] is True
    assert any(item['user_id'] == unrelated_student.id for item in payload['data'])


def test_student_and_teacher_access_are_scoped(client, login_as, logout):
    admin = create_user(username='scope-admin', display_name='权限管理员', role='admin')
    teacher = create_user(username='scope-teacher', display_name='权限老师', role='teacher')
    other_teacher = create_user(username='other-teacher', display_name='其他老师', role='teacher')
    student = create_user(username='scope-student', display_name='权限学生', role='student')
    other_student = create_user(username='other-student', display_name='其他学生', role='student')
    student_profile = create_student_profile(user=student, name='权限学生')
    other_profile = create_student_profile(user=other_student, name='其他学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='权限学生',
        course_name='权限课程',
        student_profile=student_profile,
        status='pending_student_confirm',
    )
    other_enrollment = create_enrollment(
        teacher=teacher,
        student_name='其他学生',
        course_name='别人的课程',
        student_profile=other_profile,
        status='pending_schedule',
    )

    login_as(student)
    assert client.get('/oa/api/schedules?year=2026&month=3').status_code == 403
    assert client.get(f'/auth/api/enrollments/{other_enrollment.id}').status_code == 403
    assert client.post(f'/auth/api/teacher/{other_teacher.id}/availability', json={'available': [], 'preferred': []}).status_code == 403
    logout()

    login_as(teacher)
    assert client.post(f'/auth/api/enrollments/{enrollment.id}/student-confirm').status_code == 403
    assert client.post(f'/auth/api/teacher/{other_teacher.id}/availability', json={'available': [], 'preferred': []}).status_code == 403
    logout()

    login_as(admin)
    response = client.get(f'/auth/api/enrollments/{enrollment.id}')
    assert response.status_code == 200


def test_same_name_students_get_unique_accounts_and_renames_do_not_break_scopes(client, login_as, logout):
    admin = create_user(username='identity-admin', display_name='身份管理员', role='admin')
    teacher = create_user(username='identity-teacher', display_name='身份老师', role='teacher')

    login_as(admin)
    first = client.post('/auth/api/enrollments', json={
        'student_name': '重名学生',
        'course_name': '课程 A',
        'teacher_id': teacher.id,
        'total_hours': 4,
    }).get_json()['data']
    second = client.post('/auth/api/enrollments', json={
        'student_name': '重名学生',
        'course_name': '课程 B',
        'teacher_id': teacher.id,
        'total_hours': 4,
    }).get_json()['data']
    logout()

    token_one = first['intake_url'].rsplit('/', 1)[-1]
    token_two = second['intake_url'].rsplit('/', 1)[-1]

    response = client.post(f'/auth/intake/{token_one}', json={
        'name': '重名学生',
        'phone': '13800000001',
        'available_times': [{'day': 0, 'start': '10:00', 'end': '12:00'}],
    })
    first_account = response.get_json()['account']

    response = client.post(f'/auth/intake/{token_two}', json={
        'name': '重名学生',
        'phone': '13800000002',
        'available_times': [{'day': 2, 'start': '10:00', 'end': '12:00'}],
    })
    second_account = response.get_json()['account']

    assert first_account['user_id'] != second_account['user_id']
    assert first_account['username'] != second_account['username']
    assert first_account['username'] == '重名学生'
    assert second_account['username'] == '重名学生2'

    first_student = db.session.get(User, first_account['user_id'])
    second_student = db.session.get(User, second_account['user_id'])

    login_as(admin)
    client.put(f'/auth/api/users/{teacher.id}', json={'display_name': '改名后的老师'})
    client.put(f'/auth/api/users/{first_student.id}', json={'display_name': '改名后的学生'})
    logout()

    login_as(first_student)
    response = client.get('/auth/api/student/my-info')
    payload = response.get_json()
    assert payload['success'] is True
    assert len(payload['data']['enrollments']) == 1
    assert payload['data']['enrollments'][0]['course_name'] == '课程 A'
    logout()

    login_as(teacher)
    response = client.get('/auth/api/teacher/my-schedule?range=all')
    payload = response.get_json()
    assert payload['success'] is True
    assert any(item['course'] == '课程 A' for item in payload['data']['students'])
    response = client.get('/auth/teacher/dashboard')
    html = response.get_data(as_text=True)
    assert '/auth/enrollments' in html
    assert '/oa/schedule' not in html
    assert '/oa/todos' not in html


def test_chat_and_schedule_templates_include_preview_hooks(client, login_as, logout):
    admin = create_user(username='template-admin', display_name='模板管理员', role='admin')
    teacher = create_user(username='template-teacher', display_name='模板老师', role='teacher')
    student = create_user(username='template-student', display_name='模板学生', role='student')
    profile = create_student_profile(user=student, name='模板学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='模板学生',
        course_name='模板课程',
        student_profile=profile,
        status='pending_student_confirm',
        total_hours=4,
        hours_per_session=2.0,
        confirmed_slot={
            'weekly_slots': [{'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'}],
            'session_dates': [
                {'date': '2026-03-17', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-24', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'is_manual': True,
        },
    )

    login_as(student)
    html = client.get('/auth/chat').get_data(as_text=True)
    assert 'msg-card' in html
    assert 'white-space:pre-wrap' in html

    html = client.get('/auth/student/dashboard').get_data(as_text=True)
    assert 'pending-plan-calendar' in html
    assert 'renderPendingPlanCalendars' in html
    logout()

    login_as(admin)
    html = client.get(f'/auth/enrollments/{enrollment.id}').get_data(as_text=True)
    assert 'manualPlanModal' in html
    assert '/manual-plan' in html
    assert '手动微调' in html
