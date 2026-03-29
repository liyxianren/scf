from datetime import datetime

import pytest

from extensions import db
from modules.auth.models import ChatMessage, Enrollment, TeacherAvailability, User
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


def test_chat_contacts_include_all_allowed_partners_for_student_and_teacher(client, login_as, logout):
    admin = create_user(username='contacts-admin', display_name='联系人教务', role='admin')
    teacher = create_user(username='contacts-teacher', display_name='联系人老师', role='teacher')
    unrelated_teacher = create_user(username='contacts-teacher-other', display_name='无关老师', role='teacher')
    student = create_user(username='contacts-student', display_name='联系人学生', role='student')
    related_profile = create_student_profile(user=student, name='联系人学生')
    create_enrollment(
        teacher=teacher,
        student_name='联系人学生',
        course_name='联系人课程',
        student_profile=related_profile,
        status='active',
    )

    login_as(student)
    response = client.get('/auth/api/chat/contacts')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert {item['id'] for item in payload['data']} == {admin.id, teacher.id}
    assert all(item['id'] != unrelated_teacher.id for item in payload['data'])
    logout()

    login_as(teacher)
    response = client.get('/auth/api/chat/contacts')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert {item['id'] for item in payload['data']} == {admin.id, student.id}


def test_chat_history_remains_visible_after_relationship_is_removed(client, login_as):
    teacher = create_user(username='history-teacher', display_name='历史老师', role='teacher')
    student = create_user(username='history-student', display_name='历史学生', role='student')
    profile = create_student_profile(user=student, name='历史学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='历史学生',
        course_name='历史聊天课程',
        student_profile=profile,
        status='active',
    )
    create_chat_message(sender=student, receiver=teacher, enrollment=enrollment, content='老师，我想确认一下时间', is_read=False)

    enrollment.student_profile_id = None
    db.session.commit()

    login_as(teacher)
    contacts = client.get('/auth/api/chat/contacts').get_json()['data']
    assert all(item['id'] != student.id for item in contacts)

    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert [item['user_id'] for item in payload['data']] == [student.id]
    assert payload['data'][0]['unread_count'] == 1

    response = client.get('/auth/api/chat/unread-count')
    assert response.status_code == 200
    assert response.get_json()['count'] == 1

    response = client.get(f'/auth/api/chat/messages?with={student.id}')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data'][0]['content'] == '老师，我想确认一下时间'

    response = client.get('/auth/api/chat/unread-count')
    assert response.status_code == 200
    assert response.get_json()['count'] == 0

    response = client.post('/auth/api/chat/send', json={'receiver_id': student.id, 'content': '继续追问'})
    assert response.status_code == 403


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
        'delivery_preference': 'online',
        'available_times': [{'day': 0, 'start': '10:00', 'end': '12:00'}],
    })
    first_account = response.get_json()['account']

    response = client.post(f'/auth/intake/{token_two}', json={
        'name': '重名学生',
        'phone': '13800000002',
        'delivery_preference': 'offline',
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
    assert '教师排课工作台' in html
    assert 'AI 排课工作台' in html
    assert '我提交后的排课进度' in html
    assert 'trackingWorkflowList' in html
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
    assert '/auth/api/chat/contacts' in html

    html = client.get('/auth/student/dashboard').get_data(as_text=True)
    assert '学生任务中心' in html
    assert '现在需要你做什么' in html
    assert '现在需要你处理' in html
    assert 'pending-plan-calendar' in html
    assert 'renderPendingPlanCalendars' in html
    assert '打开报名详情' not in html
    logout()

    login_as(admin)
    html = client.get('/auth/admin/dashboard').get_data(as_text=True)
    assert '教务协同台' in html
    assert '排课风险台' in html
    assert 'schedulingRiskList' in html
    assert 'waiting_student_confirm_items' in html
    html = client.get(f'/auth/enrollments/{enrollment.id}').get_data(as_text=True)
    assert 'manualPlanModal' in html
    assert '/manual-plan' in html
    assert '手动微调' in html


def test_oa_templates_expose_workflow_and_schedule_guard_hooks(client, login_as):
    admin = create_user(username='oa-template-admin', display_name='OA模板管理员', role='admin')

    login_as(admin)
    todos_html = client.get('/oa/todos').get_data(as_text=True)
    assert 'showWorkflowTodoHint' in todos_html
    assert 'isWorkflowTodo' in todos_html
    assert 'workflowHint' in todos_html

    schedule_html = client.get('/oa/schedule').get_data(as_text=True)
    assert 'courseGuardNotice' in schedule_html
    assert 'admin_delete_block_reason' in schedule_html
    assert 'admin_reschedule_block_reason' in schedule_html
    assert 'id="qnTeacher"' in schedule_html
    assert "teacher:     '—'" not in schedule_html


def test_teacher_availability_validation_rejects_invalid_slots_and_keeps_existing_data(client, login_as):
    teacher = create_user(username='availability-teacher', display_name='可用时间老师', role='teacher')

    login_as(teacher)
    response = client.post(
        f'/auth/api/teacher/{teacher.id}/availability',
        json={'available': [{'day': 1, 'start': '10:00', 'end': '12:00'}], 'preferred': []},
    )
    assert response.status_code == 200

    response = client.post(
        f'/auth/api/teacher/{teacher.id}/availability',
        json={
            'available': [
                {'day': 7, 'start': '10:00', 'end': '12:00'},
                {'day': 2, 'start': 'bad', 'end': '12:00'},
                {'day': 3, 'start': '14:00', 'end': '13:00'},
            ],
            'preferred': [{'day': 1, 'start': '09:00', 'end': 'bad'}],
        },
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert any('星期超出范围' in item for item in payload['errors'])
    assert any('时间格式错误' in item for item in payload['errors'])
    assert any('结束时间必须晚于开始时间' in item for item in payload['errors'])
    slots = TeacherAvailability.query.filter_by(user_id=teacher.id).all()
    assert len(slots) == 1
    assert slots[0].day_of_week == 1
    assert slots[0].time_start == '10:00'
    assert slots[0].time_end == '12:00'


def test_teacher_availability_can_switch_to_full_time_company_template(client, login_as):
    teacher = create_user(username='fulltime-api-teacher', display_name='全职接口老师', role='teacher')

    login_as(teacher)
    response = client.post(
        f'/auth/api/teacher/{teacher.id}/availability',
        json={'teacher_work_mode': 'full_time'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['teacher_work_mode'] == 'full_time'
    assert payload['data']['using_company_template'] is True

    response = client.get(f'/auth/api/teacher/{teacher.id}/availability')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['teacher_work_mode'] == 'full_time'
    assert len(payload['data']['available']) == 5
    assert payload['data']['default_working_template_summary']


def test_admin_user_api_persists_teacher_work_mode(client, login_as):
    admin = create_user(username='teacher-mode-admin', display_name='老师模式管理员', role='admin')

    login_as(admin)
    response = client.post('/auth/api/users', json={
        'username': 'teacher-mode-user',
        'display_name': '模式老师',
        'password': 'scf123',
        'role': 'teacher',
        'teacher_work_mode': 'full_time',
    })
    payload = response.get_json()
    assert response.status_code == 201
    assert payload['data']['teacher_work_mode'] == 'full_time'

    teacher_id = payload['data']['id']
    response = client.put(f'/auth/api/users/{teacher_id}', json={
        'teacher_work_mode': 'part_time',
    })
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['teacher_work_mode'] == 'part_time'
