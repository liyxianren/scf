import json
from datetime import date

import pytest
from freezegun import freeze_time

from extensions import db
from modules.auth.models import ChatMessage, Enrollment, User
from modules.auth.services import (
    FEEDBACK_PREFIX,
    find_matching_slots,
    propose_enrollment_schedule,
    student_confirm_schedule,
)
from modules.oa.models import CourseSchedule, OATodo
from tests.factories import (
    create_enrollment,
    create_schedule,
    create_todo,
    create_student_profile,
    create_teacher_availability,
    create_user,
)


pytestmark = pytest.mark.integration


def _slots_for_days(days, start='10:00', end='12:00'):
    return [{'day': day, 'start': start, 'end': end} for day in days]


def _has_rule(app, rule, methods):
    expected_methods = {method.upper() for method in methods}
    for mapped_rule in app.url_map.iter_rules():
        if mapped_rule.rule != rule:
            continue
        if expected_methods.issubset(mapped_rule.methods):
            return True
    return False


def _workflow_contract_ready(app):
    rule_candidates = [
        ['/auth/api/workflow-todos'],
        ['/auth/api/workflow-todos/<int:id>/teacher-proposal', '/auth/api/workflow-todos/<int:todo_id>/teacher-proposal'],
        ['/auth/api/workflow-todos/<int:id>/admin-send-to-student', '/auth/api/workflow-todos/<int:todo_id>/admin-send-to-student'],
        ['/auth/api/workflow-todos/<int:id>/student-confirm', '/auth/api/workflow-todos/<int:todo_id>/student-confirm'],
        ['/auth/api/workflow-todos/<int:id>/student-reject', '/auth/api/workflow-todos/<int:todo_id>/student-reject'],
    ]
    method_sets = [
        {'GET'},
        {'POST'},
        {'POST'},
        {'POST'},
        {'POST'},
    ]
    for candidates, methods in zip(rule_candidates, method_sets):
        if not any(_has_rule(app, rule, methods) for rule in candidates):
            return False
    return True


def _require_workflow_contract(app):
    if not _workflow_contract_ready(app):
        pytest.skip('workflow todo contract is not implemented yet')


def _as_json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value or {}


def _build_workflow_enrollment(client, login_as, logout):
    admin = create_user(username='workflow-admin', display_name='工作流管理员', role='admin')
    teacher = create_user(username='workflow-teacher', display_name='工作流老师', role='teacher')
    student_name = '工作流学生'
    intake_name = '工作流学生'

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': student_name,
            'course_name': '工作流课程',
            'teacher_id': teacher.id,
            'total_hours': 6,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    enrollment_id = payload['data']['id']
    token = payload['data']['intake_url'].rsplit('/', 1)[-1]
    logout()

    response = client.post(
        f'/auth/intake/{token}',
        json={
            'name': intake_name,
            'phone': '13800138000',
            'available_times': _slots_for_days([0, 2, 4]),
            'excluded_dates': ['2026-03-18'],
            'notes': '工作流测试学生',
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
    response = client.post(f'/auth/api/enrollments/{enrollment_id}/confirm', json={'slot_index': 0})
    payload = response.get_json()
    assert payload['success'] is True
    assert db.session.get(Enrollment, enrollment_id).status == 'pending_student_confirm'
    logout()

    return {
        'admin': admin,
        'teacher': teacher,
        'student': student,
        'enrollment_id': enrollment_id,
        'intake_token': token,
    }


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
    assert db.session.get(Enrollment, enrollment_id).status == 'active'


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


def test_manual_plan_force_save_and_student_confirmation(client, login_as, logout):
    admin = create_user(username='manual-admin', display_name='手动排课管理员', role='admin')
    teacher = create_user(username='manual-teacher', display_name='手动排课老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '手动排课学生',
            'course_name': '手动微调课',
            'teacher_id': teacher.id,
            'total_hours': 6,
        },
    )
    payload = response.get_json()
    enrollment_id = payload['data']['id']
    token = payload['data']['intake_url'].rsplit('/', 1)[-1]
    logout()

    response = client.post(
        f'/auth/intake/{token}',
        json={
            'name': '手动排课学生',
            'phone': '13800138088',
            'available_times': _slots_for_days([0], start='10:00', end='12:00'),
            'excluded_dates': ['2026-03-24'],
        },
    )
    student = db.session.get(User, response.get_json()['account']['user_id'])

    login_as(teacher)
    response = client.post(
        f'/auth/api/teacher/{teacher.id}/availability',
        json={
            'available': _slots_for_days([0], start='10:00', end='12:00'),
            'preferred': _slots_for_days([0], start='10:00', end='12:00'),
        },
    )
    assert response.get_json()['success'] is True
    logout()

    manual_dates = [
        {'date': '2026-03-17', 'time_start': '10:00', 'time_end': '12:00'},
        {'date': '2026-03-24', 'time_start': '10:00', 'time_end': '12:00'},
        {'date': '2026-03-31', 'time_start': '10:00', 'time_end': '12:00'},
    ]

    login_as(admin)
    response = client.post(
        f'/auth/api/enrollments/{enrollment_id}/manual-plan',
        json={'session_dates': manual_dates, 'force_save': False},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is False
    assert payload['can_force_save'] is True
    assert any('不可上课日期' in warning for warning in payload['warnings'])
    assert any('老师原始可用时间' in warning for warning in payload['warnings'])

    response = client.post(
        f'/auth/api/enrollments/{enrollment_id}/manual-plan',
        json={'session_dates': manual_dates, 'force_save': True},
    )
    payload = response.get_json()
    assert payload['success'] is True

    enrollment = db.session.get(Enrollment, enrollment_id)
    confirmed_slot = enrollment.to_dict()['confirmed_slot']
    assert enrollment.status == 'pending_student_confirm'
    assert confirmed_slot['is_manual'] is True
    assert [item['date'] for item in confirmed_slot['session_dates']] == ['2026-03-17', '2026-03-24', '2026-03-31']
    logout()

    login_as(student)
    response = client.get('/auth/api/student/my-info')
    payload = response.get_json()
    pending = payload['data']['enrollments'][0]['confirmed_slot']
    assert pending['is_manual'] is True
    assert [item['date'] for item in pending['session_dates']] == ['2026-03-17', '2026-03-24', '2026-03-31']

    response = client.post(f'/auth/api/enrollments/{enrollment_id}/student-confirm')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['created_count'] == 3

    schedules = CourseSchedule.query.filter_by(enrollment_id=enrollment_id).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()
    assert [(schedule.date.isoformat(), schedule.time_start, schedule.time_end) for schedule in schedules] == [
        ('2026-03-17', '10:00', '12:00'),
        ('2026-03-24', '10:00', '12:00'),
        ('2026-03-31', '10:00', '12:00'),
    ]


def test_manual_plan_blocks_teacher_schedule_conflicts(client, login_as):
    admin = create_user(username='manual-conflict-admin', display_name='冲突管理员', role='admin')
    teacher = create_user(username='manual-conflict-teacher', display_name='冲突老师', role='teacher')
    student = create_user(username='manual-conflict-student', display_name='冲突学生', role='student')
    profile = create_student_profile(
        user=student,
        name='冲突学生',
        available_slots=_slots_for_days([1, 2]),
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='冲突学生',
        course_name='冲突校验课',
        student_profile=profile,
        status='pending_schedule',
        total_hours=4,
        hours_per_session=2.0,
    )
    create_schedule(
        teacher=teacher,
        course_name='老师已有课',
        students='其他学生',
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(admin)
    response = client.post(
        f'/auth/api/enrollments/{enrollment.id}/manual-plan',
        json={
            'session_dates': [
                {'date': '2026-03-17', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-18', 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'force_save': True,
        },
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert '老师现有课程冲突' in payload['error']


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


def test_generic_todo_crud_still_works(client, login_as):
    admin = create_user(username='todo-admin', display_name='待办管理员', role='admin')

    login_as(admin)
    todo = create_todo(
        title='通用待办',
        responsible_person='教务, 教师',
        due_date=date(2026, 3, 20),
        priority=1,
        notes='generic todo regression',
    )

    response = client.get('/oa/api/todos')
    payload = response.get_json()
    assert payload['success'] is True
    assert any(item['id'] == todo.id for item in payload['data'])

    response = client.post(f'/oa/api/todos/{todo.id}/toggle')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['is_completed'] is True

    response = client.delete(f'/oa/api/todos/{todo.id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['id'] == todo.id


def test_workflow_replan_contract_from_reject_to_active(client, app, login_as, logout):
    _require_workflow_contract(app)
    context = _build_workflow_enrollment(client, login_as, logout)
    admin = context['admin']
    teacher = context['teacher']
    student = context['student']
    enrollment_id = context['enrollment_id']

    login_as(student)
    response = client.post(
        f'/auth/api/enrollments/{enrollment_id}/student-reject',
        json={'message': '周三第一周上不了，请重排'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    feedback = ChatMessage.query.filter_by(enrollment_id=enrollment_id).order_by(ChatMessage.created_at.desc()).first()
    assert feedback is not None
    assert feedback.content.startswith(FEEDBACK_PREFIX)
    logout()

    login_as(admin)
    response = client.get('/auth/api/workflow-todos')
    payload = response.get_json()
    assert payload['success'] is True
    todo = next(item for item in payload['data'] if item.get('enrollment_id') == enrollment_id)
    assert todo['todo_type'] == 'enrollment_replan'
    assert todo['workflow_status'] == 'waiting_teacher_proposal'
    assert todo['payload']['previous_confirmed_slot']
    todo_id = todo['id']
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/teacher-proposal',
        json={
            'session_dates': [
                {'date': '2026-03-18', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-20', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'note': '按老师可用时间重新安排',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    todo = db.session.get(OATodo, todo_id)
    assert todo.workflow_status == 'waiting_admin_review'
    assert _as_json(todo.payload)['current_proposal']['session_dates']
    logout()

    login_as(admin)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/admin-send-to-student',
        json={'force_save': True},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    enrollment = db.session.get(Enrollment, enrollment_id)
    assert enrollment.status == 'pending_student_confirm'
    assert enrollment.to_dict()['confirmed_slot']['session_dates']
    logout()

    login_as(student)
    response = client.post(f'/auth/api/workflow-todos/{todo_id}/student-confirm')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['created_count'] == 3
    logout()

    refreshed = db.session.get(OATodo, todo_id)
    assert refreshed.workflow_status == 'completed'
    schedules = CourseSchedule.query.filter_by(enrollment_id=enrollment_id).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()
    assert len(schedules) == 3
    assert db.session.get(Enrollment, enrollment_id).status in {'confirmed', 'active'}


def test_workflow_leave_makeup_contract_and_reject_reopens(client, app, login_as, logout):
    _require_workflow_contract(app)
    teacher = create_user(username='leave-workflow-teacher', display_name='请假老师', role='teacher')
    student = create_user(username='leave-workflow-student', display_name='请假学生', role='student')
    profile = create_student_profile(
        user=student,
        name='请假学生',
        available_slots=_slots_for_days([0, 2, 4]),
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='请假学生',
        course_name='请假补课课程',
        student_profile=profile,
        status='confirmed',
        total_hours=4,
        hours_per_session=2.0,
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='请假补课课程',
        students='请假学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )
    create_teacher_availability(user=teacher, day_of_week=0, time_start='10:00', time_end='12:00')

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={'schedule_id': leave_schedule.id, 'reason': '校内活动'})
    payload = response.get_json()
    assert response.status_code == 201
    leave_id = payload['data']['id']
    logout()

    login_as(teacher)
    response = client.put(f'/auth/api/leave-requests/{leave_id}/approve')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True

    response = client.get('/auth/api/workflow-todos')
    payload = response.get_json()
    assert payload['success'] is True
    todo = next(item for item in payload['data'] if item.get('leave_request_id') == leave_id)
    assert todo['todo_type'] == 'leave_makeup'
    assert todo['workflow_status'] == 'waiting_teacher_proposal'
    todo_id = todo['id']
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/teacher-proposal',
        json={
            'session_dates': [
                {'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'note': '补课安排在下周一',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    logout()

    admin = create_user(username='leave-workflow-admin', display_name='请假教务', role='admin')
    login_as(admin)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/admin-send-to-student',
        json={'force_save': True},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    logout()

    login_as(student)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/student-reject',
        json={'message': '这周一时间冲突，请重新安排'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    todo = db.session.get(OATodo, todo_id)
    assert todo.workflow_status == 'waiting_teacher_proposal'
    assert _as_json(todo.payload)['rejections'][-1]['reason'] == '这周一时间冲突，请重新安排'
    logout()


def test_workflow_schedule_feedback_contract_and_schedule_lock(client, app, login_as, logout):
    _require_workflow_contract(app)
    context = _build_workflow_enrollment(client, login_as, logout)
    admin = context['admin']
    teacher = context['teacher']
    student = context['student']
    enrollment_id = context['enrollment_id']

    login_as(student)
    response = client.post(
        f'/auth/api/enrollments/{enrollment_id}/student-reject',
        json={'message': '先按工作流测试重排'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    logout()

    login_as(admin)
    todo = next(item for item in client.get('/auth/api/workflow-todos').get_json()['data'] if item.get('enrollment_id') == enrollment_id)
    todo_id = todo['id']
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/teacher-proposal',
        json={
            'session_dates': [
                {'date': '2026-03-18', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-20', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'note': '准备生成反馈待办',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True

    logout()
    login_as(admin)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/admin-send-to-student',
        json={'force_save': True},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True

    logout()
    login_as(student)
    response = client.post(f'/auth/api/workflow-todos/{todo_id}/student-confirm')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True

    schedules = CourseSchedule.query.filter_by(enrollment_id=enrollment_id).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()
    assert len(schedules) == 3
    first_schedule = schedules[0]
    first_schedule_id = first_schedule.id
    logout()

    login_as(admin)
    feedback_todos = [item for item in client.get('/auth/api/workflow-todos').get_json()['data'] if item.get('schedule_id') == first_schedule_id]
    assert feedback_todos
    feedback_todo = next(item for item in feedback_todos if item.get('todo_type') == 'schedule_feedback')
    assert feedback_todo['workflow_status'] == 'waiting_teacher_proposal'
    assert feedback_todo['due_date'] == first_schedule.date.isoformat()
    feedback_todo_id = feedback_todo['id']

    response = client.put(
        f'/oa/api/schedules/{first_schedule_id}',
        json={
            'enrollment_id': None,
            'course_name': '不允许直接改绑',
        },
    )
    assert response.status_code == 400
    logout()

    with freeze_time('2026-03-18 12:30:00'):
        login_as(teacher)
        response = client.post(
            f'/auth/api/schedules/{first_schedule_id}/feedback/submit',
            json={'summary': '项目拆解完成', 'homework': '继续整理材料', 'next_focus': '准备下次反馈'},
        )
        payload = response.get_json()
        assert response.status_code == 200
        assert payload['success'] is True
        assert db.session.get(OATodo, feedback_todo_id).workflow_status == 'completed'
