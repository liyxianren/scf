import json
from datetime import date

import pytest
from freezegun import freeze_time

from extensions import db
from modules.auth import availability_ai_services
from modules.auth.models import ChatMessage, Enrollment, LeaveRequest, User
from modules.auth.services import (
    FEEDBACK_PREFIX,
    _build_manual_plan,
    _linked_schedule_query,
    backfill_schedule_relationships,
    find_matching_slots,
    propose_enrollment_schedule,
    reject_enrollment_schedule,
    refresh_enrollment_scheduling_ai_state,
    student_confirm_schedule,
)
from modules.oa.models import CourseSchedule, OATodo
from tests.factories import (
    create_enrollment,
    create_leave_request,
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
        ['/auth/api/workflow-todos/<int:id>/proposal-preview', '/auth/api/workflow-todos/<int:todo_id>/proposal-preview'],
        ['/auth/api/workflow-todos/<int:id>/teacher-proposal', '/auth/api/workflow-todos/<int:todo_id>/teacher-proposal'],
        ['/auth/api/workflow-todos/<int:id>/admin-return-to-teacher', '/auth/api/workflow-todos/<int:todo_id>/admin-return-to-teacher'],
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
            'sessions_per_week': 3,
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
            'delivery_preference': 'online',
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
            'sessions_per_week': 3,
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
            'delivery_preference': 'online',
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
    workflow_payload = client.get('/auth/api/workflow-todos').get_json()['data']
    todo = next(item for item in workflow_payload if item.get('enrollment_id') == enrollment_id)
    assert todo['workflow_status'] == 'waiting_teacher_proposal'
    todo_id = todo['id']
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/teacher-proposal',
        json={
            'session_dates': [
                {'date': '2026-03-20', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-25', 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'note': '按学生反馈调整首周节奏',
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
        sessions_per_week=5,
    )

    plans, error = find_matching_slots(enrollment.id)
    assert error is None
    assert plans

    first_plan = plans[0]
    assert first_plan['total_sessions'] == 10
    assert first_plan['distinct_days'] == 5


def test_full_time_teacher_uses_company_template_for_low_risk_matching(app):
    teacher = create_user(
        username='fulltime-smooth-teacher',
        display_name='全职顺滑老师',
        role='teacher',
        teacher_work_mode='full_time',
    )
    student = create_user(username='fulltime-smooth-student', display_name='全职顺滑学生', role='student')
    profile = create_student_profile(
        user=student,
        name='全职顺滑学生',
        available_slots=_slots_for_days([2, 3, 4], start='10:00', end='12:00'),
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='全职顺滑学生',
        course_name='全职低风险课',
        student_profile=profile,
        status='pending_schedule',
        total_hours=8,
        hours_per_session=2.0,
        sessions_per_week=2,
    )

    state = refresh_enrollment_scheduling_ai_state(enrollment)
    risk = state['risk_assessment']

    assert risk['teacher_work_mode'] == 'full_time'
    assert risk['availability_source'] == 'company_template'
    assert risk['teacher_confirmation_required'] is False
    assert risk['recommended_action'] in {'direct_to_student', 'needs_admin_review'}
    assert len(state['candidate_slot_pool']) >= 2
    assert state['recommended_bundle'] is not None


def test_full_time_teacher_outside_template_requires_teacher_confirmation(app):
    teacher = create_user(
        username='fulltime-exception-teacher',
        display_name='全职例外老师',
        role='teacher',
        teacher_work_mode='full_time',
    )
    student = create_user(username='fulltime-exception-student', display_name='全职例外学生', role='student')
    profile = create_student_profile(
        user=student,
        name='全职例外学生',
        available_slots=_slots_for_days([0, 1], start='10:00', end='12:00'),
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='全职例外学生',
        course_name='模板外协同课',
        student_profile=profile,
        status='pending_schedule',
        total_hours=8,
        hours_per_session=2.0,
        sessions_per_week=2,
    )

    plans, error = find_matching_slots(enrollment.id)

    assert plans == []
    assert '必须由老师确认模板外时段' in error
    todo = OATodo.query.filter_by(
        enrollment_id=enrollment.id,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
    ).order_by(OATodo.created_at.desc()).first()
    assert todo is not None
    assert todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL


def test_full_time_teacher_reject_flow_stays_with_admin_when_template_is_sufficient(app):
    teacher = create_user(
        username='fulltime-reject-teacher',
        display_name='全职复核老师',
        role='teacher',
        teacher_work_mode='full_time',
    )
    student = create_user(username='fulltime-reject-student', display_name='全职复核学生', role='student')
    profile = create_student_profile(
        user=student,
        name='全职复核学生',
        available_slots=_slots_for_days([2, 3, 4], start='10:00', end='12:00'),
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='全职复核学生',
        course_name='全职复核课',
        student_profile=profile,
        status='pending_schedule',
        total_hours=8,
        hours_per_session=2.0,
        sessions_per_week=2,
    )
    state = refresh_enrollment_scheduling_ai_state(enrollment)
    enrollment.confirmed_slot = json.dumps(state['recommended_bundle'], ensure_ascii=False)
    enrollment.status = 'pending_student_confirm'
    db.session.commit()

    success, message = reject_enrollment_schedule(enrollment.id, '周四要临时调一下')

    assert success is True
    todo = OATodo.query.filter_by(
        enrollment_id=enrollment.id,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
    ).order_by(OATodo.created_at.desc()).first()
    assert todo is not None
    assert todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW
    assert todo.responsible_person == '教务'
    payload = _as_json(todo.payload)
    assert payload['current_proposal'] is not None


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
            'delivery_preference': 'offline',
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
            'delivery_preference': 'online',
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
    assert payload['data']['next_workflow_id'] is not None
    assert payload['data']['next_action_label'] == '提交补课建议'
    assert '教务会继续发送给学生确认' in payload['data']['next_action_hint']

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
    draft_center = client.get('/auth/api/teacher/action-center').get_json()['data']
    draft_item = next(item for item in draft_center['pending_feedback_schedules'] if item['id'] == feedback_schedule.id)
    assert draft_item['feedback']['status'] == 'draft'
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
    enrollment_payload = client.get('/auth/api/student/my-info').get_json()['data']['enrollments'][0]
    assert enrollment_payload['latest_teacher_feedback_detail']['summary'] == '完成了一次项目拆解'
    assert enrollment_payload['latest_teacher_feedback_detail']['homework'] == '整理项目思路'
    assert enrollment_payload['latest_teacher_feedback_detail']['next_focus'] == '准备需求文档'

    response = client.get('/auth/api/chat/conversations')
    payload = response.get_json()
    assert any('请假审批' in item['last_message'] for item in payload['data'])


def test_leave_request_rejects_invalid_makeup_preferences(client, login_as):
    teacher = create_user(username='invalid-leave-teacher', display_name='非法请假老师', role='teacher')
    student = create_user(username='invalid-leave-student', display_name='非法请假学生', role='student')
    profile = create_student_profile(user=student, name='非法请假学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='非法请假学生',
        course_name='非法请假课程',
        student_profile=profile,
        status='confirmed',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='非法请假课程',
        students='非法请假学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 25),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={
        'schedule_id': schedule.id,
        'reason': '需要请假',
        'makeup_available_slots': [{'day': 0, 'start': '20:00', 'end': '18:00'}],
        'makeup_excluded_dates': ['2026/03/26'],
    })
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert '结束时间必须晚于开始时间' in payload['error']
    assert '禁排日期格式错误' in payload['error']


def test_leave_request_requires_non_empty_reason(client, login_as):
    teacher = create_user(username='blank-leave-teacher', display_name='空原因老师', role='teacher')
    student = create_user(username='blank-leave-student', display_name='空原因学生', role='student')
    profile = create_student_profile(user=student, name='空原因学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='空原因学生',
        course_name='空原因课程',
        student_profile=profile,
        status='confirmed',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='空原因课程',
        students='空原因学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 25),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={
        'schedule_id': schedule.id,
        'reason': '   ',
    })
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert payload['error'] == '请填写请假原因'


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
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    refreshed_schedule = db.session.get(CourseSchedule, future_schedule.id)
    assert refreshed_schedule is not None
    assert refreshed_schedule.is_cancelled is True

    refreshed = db.session.get(Enrollment, enrollment.id)
    assert refreshed.status == 'completed'

    response = client.get(f'/auth/api/enrollments/{enrollment.id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['status'] == 'completed'


def test_leave_reject_requires_comment_and_notifies_student(client, login_as, logout):
    teacher = create_user(username='reject-comment-teacher', display_name='驳回老师', role='teacher')
    student = create_user(username='reject-comment-student', display_name='驳回学生用户', role='student')
    profile = create_student_profile(user=student, name='驳回学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='驳回学生',
        course_name='驳回课程',
        student_profile=profile,
        status='confirmed',
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='驳回课程',
        students='驳回学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 23),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={'schedule_id': leave_schedule.id, 'reason': '校内活动'})
    assert response.status_code == 201
    leave_id = response.get_json()['data']['id']
    logout()

    login_as(teacher)
    response = client.put(f'/auth/api/leave-requests/{leave_id}/reject', json={})
    assert response.status_code == 400
    assert response.get_json()['error'] == '请先填写处理说明'

    response = client.put(
        f'/auth/api/leave-requests/{leave_id}/reject',
        json={'comment': '请先补充新的可补课时段后再重新申请'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['decision_comment'] == '请先补充新的可补课时段后再重新申请'
    assert db.session.get(LeaveRequest, leave_id).decision_comment == '请先补充新的可补课时段后再重新申请'
    logout()

    login_as(student)
    leave_payload = client.get('/auth/api/leave-requests').get_json()['data'][0]
    assert leave_payload['status'] == 'rejected'
    assert leave_payload['decision_comment'] == '请先补充新的可补课时段后再重新申请'

    latest_notice = ChatMessage.query.filter_by(enrollment_id=enrollment.id).order_by(ChatMessage.created_at.desc()).first()
    assert latest_notice is not None
    assert '处理说明：请先补充新的可补课时段后再重新申请' in latest_notice.content


def test_teacher_proposal_warnings_surface_to_admin_action_center(client, app, login_as, logout):
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
    assert response.status_code == 200
    logout()

    login_as(admin)
    todo = next(item for item in client.get('/auth/api/workflow-todos').get_json()['data'] if item.get('enrollment_id') == enrollment_id)
    todo_id = todo['id']
    assert '周一 10:00-12:00' in todo['context']['student_available_slots_summary']
    assert todo['context']['student_excluded_dates_summary'] == '2026-03-18'
    assert '学生长期可上课：周一 10:00-12:00' in todo['context_summary']
    assert '学生禁排日期：2026-03-18' in todo['context_summary']
    logout()

    login_as(teacher)
    preview_response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/proposal-preview',
        json={
            'session_dates': [
                {'date': '2026-03-17', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-18', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-20', 'time_start': '10:00', 'time_end': '12:00'},
            ],
        },
    )
    preview_payload = preview_response.get_json()
    assert preview_response.status_code == 200
    assert preview_payload['success'] is True
    assert any('老师原始可用时间' in item for item in preview_payload['data']['warnings'])
    assert any('不可上课日期' in item for item in preview_payload['data']['warnings'])
    assert db.session.get(OATodo, todo_id).workflow_status == 'waiting_teacher_proposal'

    teacher_center = client.get('/auth/api/teacher/action-center').get_json()['data']
    teacher_todo = next(item for item in teacher_center['proposal_workflows'] if item['id'] == todo_id)
    assert '周一 10:00-12:00' in teacher_todo['context']['student_available_slots_summary']
    assert teacher_todo['context']['student_excluded_dates_summary'] == '2026-03-18'
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/teacher-proposal',
        json={
            'session_dates': [
                {'date': '2026-03-17', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-18', 'time_start': '10:00', 'time_end': '12:00'},
                {'date': '2026-03-20', 'time_start': '10:00', 'time_end': '12:00'},
            ],
            'note': '带提醒项的老师提案',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert any('老师原始可用时间' in item for item in payload['warnings'])
    assert any('不可上课日期' in item for item in payload['warnings'])
    assert payload['data']['proposal_warnings'] == payload['warnings']
    assert '老师原始可用时间' in payload['data']['proposal_warning_summary']
    logout()

    login_as(admin)
    admin_center = client.get('/auth/api/admin/action-center').get_json()['data']
    admin_item = next(item for item in admin_center['pending_admin_send_workflows'] if item['id'] == todo_id)
    assert admin_item['proposal_warnings'] == payload['warnings']
    assert '不可上课日期' in admin_item['proposal_warning_summary']


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
    assert todo['context_summary'].startswith('原请假课次：')
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
    workflow_payload = client.get('/auth/api/workflow-todos').get_json()['data']
    reopened_todo = next(item for item in workflow_payload if item.get('id') == todo_id)
    assert reopened_todo['latest_rejection_text'] == '这周一时间冲突，请重新安排'
    logout()


def test_leave_makeup_confirmation_persists_schedule_link_and_student_view(client, app, login_as, logout):
    _require_workflow_contract(app)
    teacher = create_user(username='leave-link-teacher', display_name='补课老师', role='teacher')
    admin = create_user(username='leave-link-admin', display_name='补课教务', role='admin')
    student = create_user(username='leave-link-student', display_name='补课学生用户', role='student')
    profile = create_student_profile(
        user=student,
        name='补课学生',
        available_slots=_slots_for_days([1, 3]),
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='补课学生',
        course_name='补课确认课程',
        student_profile=profile,
        status='confirmed',
        total_hours=4,
        hours_per_session=2.0,
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='补课确认课程',
        students='补课学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )
    create_teacher_availability(user=teacher, day_of_week=1, time_start='18:00', time_end='20:00')

    login_as(student)
    response = client.post('/auth/api/leave-requests', json={
        'schedule_id': leave_schedule.id,
        'reason': '校内活动',
        'makeup_available_slots': [{'day': 1, 'start': '18:00', 'end': '20:00'}],
        'makeup_excluded_dates': ['2026-03-25'],
        'makeup_preference_note': '这周只能晚上补课',
    })
    payload = response.get_json()
    assert response.status_code == 201
    assert payload['data']['makeup_available_slots'] == [{'day': 1, 'start': '18:00', 'end': '20:00'}]
    assert payload['data']['makeup_excluded_dates'] == ['2026-03-25']
    assert payload['data']['makeup_preference_note'] == '这周只能晚上补课'
    assert '本次可补课时间：周二 18:00-20:00' in payload['data']['makeup_preference_summary']
    leave_id = payload['data']['id']
    logout()

    login_as(teacher)
    response = client.put(f'/auth/api/leave-requests/{leave_id}/approve')
    assert response.status_code == 200
    teacher_center = client.get('/auth/api/teacher/action-center').get_json()['data']
    assert len(teacher_center['proposal_workflows']) == 1
    assert '本次可补课时间：周二 18:00-20:00' in teacher_center['proposal_workflows'][0]['context_summary']
    todo_id = teacher_center['proposal_workflows'][0]['id']
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/teacher-proposal',
        json={
            'session_dates': [{'date': '2026-03-24', 'time_start': '18:00', 'time_end': '20:00'}],
            'note': '按学生本次晚间偏好顺延一周补课',
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['warnings'] == []
    logout()

    login_as(admin)
    admin_center = client.get('/auth/api/admin/action-center').get_json()['data']
    assert [item['id'] for item in admin_center['pending_admin_send_workflows']] == [todo_id]
    response = client.post(
        f'/auth/api/workflow-todos/{todo_id}/admin-send-to-student',
        json={'force_save': True},
    )
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    logout()

    login_as(student)
    response = client.post(f'/auth/api/workflow-todos/{todo_id}/student-confirm')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True

    leave_request = db.session.get(LeaveRequest, leave_id)
    assert leave_request.makeup_schedule_id is not None
    makeup_schedule = db.session.get(CourseSchedule, leave_request.makeup_schedule_id)
    assert makeup_schedule is not None
    assert makeup_schedule.date.isoformat() == '2026-03-24'
    assert makeup_schedule.time_start == '18:00'
    assert makeup_schedule.time_end == '20:00'
    assert makeup_schedule.enrollment_id == enrollment.id

    leave_payload = client.get('/auth/api/leave-requests').get_json()['data'][0]
    assert leave_payload['makeup_schedule_id'] == makeup_schedule.id
    assert leave_payload['makeup_status'] == 'confirmed'
    assert leave_payload['makeup_schedule']['date'] == '2026-03-24'
    assert leave_payload['makeup_preference_note'] == '这周只能晚上补课'

    student_center = client.get('/auth/api/student/action-center').get_json()['data']
    assert student_center['pending_workflows'] == []
    assert student_center['leave_requests'][0]['makeup_schedule_id'] == makeup_schedule.id
    assert student_center['leave_requests'][0]['makeup_schedule']['date'] == '2026-03-24'
    logout()


def test_workflow_reject_without_message_uses_chinese_fallback(client, app, login_as, logout):
    _require_workflow_contract(app)
    teacher = create_user(username='workflow-empty-reject-teacher', display_name='空理由老师', role='teacher')
    student = create_user(username='workflow-empty-reject-student', display_name='空理由学生用户', role='student')
    profile = create_student_profile(user=student, name='空理由学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='空理由学生',
        course_name='空理由课程',
        student_profile=profile,
        status='pending_student_confirm',
    )
    todo = create_todo(
        title='等待学生确认',
        responsible_person='空理由学生',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM,
        payload={'current_proposal': {'session_dates': []}},
    )

    login_as(student)
    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/student-reject',
        json={},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    refreshed = db.session.get(OATodo, todo.id)
    rejections = _as_json(refreshed.payload)['rejections']
    assert rejections[-1]['reason'] == '学生对当前方案有疑问，请重新调整。'
    assert refreshed.notes == '学生对当前方案有疑问，请重新调整。'
    logout()


def test_student_confirm_schedule_returns_readable_student_conflict_message(app):
    teacher = create_user(username='student-conflict-teacher', display_name='冲突老师', role='teacher')
    other_teacher = create_user(username='student-conflict-other-teacher', display_name='另一个冲突老师', role='teacher')
    student = create_user(username='student-conflict-student', display_name='冲突学生用户', role='student')
    profile = create_student_profile(user=student, name='冲突学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='冲突学生',
        course_name='待确认课程',
        student_profile=profile,
        status='pending_student_confirm',
        total_hours=2,
        hours_per_session=2.0,
    )
    conflicting_enrollment = create_enrollment(
        teacher=other_teacher,
        student_name='冲突学生',
        course_name='已有课程',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    create_schedule(
        teacher=other_teacher,
        course_name='已有课程',
        students='冲突学生',
        enrollment=conflicting_enrollment,
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )

    plan = _build_manual_plan([
        {'date': '2026-03-17', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
    ])
    enrollment.confirmed_slot = json.dumps(plan, ensure_ascii=False)
    db.session.commit()

    success, message, created_count = student_confirm_schedule(enrollment.id)
    assert success is False
    assert created_count == 0
    assert message == '2026-03-17 10:00-12:00 与同一学生现有课程冲突：已有课程 10:00-12:00'


def test_legacy_student_confirm_conflict_stays_visible_in_student_action_center(client, login_as):
    teacher = create_user(username='legacy-visible-teacher', display_name='可见老师', role='teacher')
    other_teacher = create_user(username='legacy-visible-other-teacher', display_name='其他可见老师', role='teacher')
    student = create_user(username='legacy-visible-student', display_name='可见学生用户', role='student')
    profile = create_student_profile(user=student, name='可见学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='可见学生',
        course_name='待确认课程',
        student_profile=profile,
        status='pending_student_confirm',
        total_hours=2,
        hours_per_session=2.0,
    )
    conflicting_enrollment = create_enrollment(
        teacher=other_teacher,
        student_name='可见学生',
        course_name='已有课程',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    create_schedule(
        teacher=other_teacher,
        course_name='已有课程',
        students='可见学生',
        enrollment=conflicting_enrollment,
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )
    enrollment.confirmed_slot = json.dumps(_build_manual_plan([
        {'date': '2026-03-17', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
    ]), ensure_ascii=False)
    db.session.commit()

    login_as(student)
    response = client.post(f'/auth/api/enrollments/{enrollment.id}/student-confirm')
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert payload['error'] == '2026-03-17 10:00-12:00 与同一学生现有课程冲突：已有课程 10:00-12:00'

    action_center = client.get('/auth/api/student/action-center').get_json()['data']
    workflow = next(item for item in action_center['pending_workflows'] if item['enrollment_id'] == enrollment.id)
    assert workflow['todo_type'] == 'enrollment_replan'
    assert workflow['workflow_status'] == 'waiting_teacher_proposal'
    assert workflow['latest_rejection_text'] == payload['error']
    assert db.session.get(Enrollment, enrollment.id).status == 'pending_schedule'


def test_confirm_slot_rejects_non_initial_enrollment_and_keeps_history(client, login_as):
    admin = create_user(username='reconfirm-admin', display_name='重发教务', role='admin')
    teacher = create_user(username='reconfirm-teacher', display_name='重发老师', role='teacher')
    student = create_user(username='reconfirm-student', display_name='重发学生用户', role='student')
    profile = create_student_profile(user=student, name='重发学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='重发学生',
        course_name='已运行课程',
        student_profile=profile,
        status='active',
        total_hours=2,
        hours_per_session=2.0,
        proposed_slots=[{
            'weekly_slots': [{'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'}],
            'session_dates': [
                {'date': '2026-03-24', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
            ],
        }],
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='已运行课程',
        students='重发学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
    )
    todo = create_todo(
        title='历史待办',
        responsible_person='重发老师',
        schedule=schedule,
        enrollment=enrollment,
    )
    leave_request = create_leave_request(
        schedule=schedule,
        student_name='重发学生',
        enrollment=enrollment,
        status='pending',
    )

    login_as(admin)
    response = client.post(f'/auth/api/enrollments/{enrollment.id}/confirm', json={'slot_index': 0})
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert payload['error'] == '当前状态不允许重新发送排课方案'
    assert db.session.get(Enrollment, enrollment.id).status == 'active'
    assert db.session.get(CourseSchedule, schedule.id) is not None
    assert db.session.get(OATodo, todo.id) is not None
    assert db.session.get(LeaveRequest, leave_request.id) is not None


def test_legacy_send_routes_reject_when_replan_workflow_exists(client, login_as):
    admin = create_user(username='legacy-block-admin', display_name='流程教务', role='admin')
    teacher = create_user(username='legacy-block-teacher', display_name='流程老师', role='teacher')
    student = create_user(username='legacy-block-student', display_name='流程学生用户', role='student')
    profile = create_student_profile(user=student, name='流程学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='流程学生',
        course_name='流程课程',
        student_profile=profile,
        status='pending_schedule',
        total_hours=2,
        hours_per_session=2.0,
        proposed_slots=[{
            'weekly_slots': [{'day_of_week': 0, 'time_start': '10:00', 'time_end': '12:00'}],
            'session_dates': [
                {'date': '2026-03-23', 'day_of_week': 0, 'time_start': '10:00', 'time_end': '12:00'},
            ],
        }],
    )
    todo = create_todo(
        title='流程中重排',
        responsible_person='流程老师, 教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )

    login_as(admin)
    response = client.post(f'/auth/api/enrollments/{enrollment.id}/confirm', json={'slot_index': 0})
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['error'] == '当前报名存在进行中的排课工作流，请通过工作流继续处理'

    response = client.post(
        f'/auth/api/enrollments/{enrollment.id}/manual-plan',
        json={'session_dates': [{'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'}]},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['error'] == '当前报名存在进行中的排课工作流，请通过工作流继续处理'
    assert db.session.get(OATodo, todo.id).workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL


def test_workflow_admin_send_rejects_when_legacy_pending_student_confirm_exists(client, login_as):
    admin = create_user(username='workflow-guard-admin', display_name='守卫教务', role='admin')
    teacher = create_user(username='workflow-guard-teacher', display_name='守卫老师', role='teacher')
    student = create_user(username='workflow-guard-student', display_name='守卫学生用户', role='student')
    profile = create_student_profile(user=student, name='守卫学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='守卫学生',
        course_name='守卫课程',
        student_profile=profile,
        status='pending_student_confirm',
        total_hours=2,
        hours_per_session=2.0,
        confirmed_slot=_build_manual_plan([
            {'date': '2026-03-23', 'day_of_week': 0, 'time_start': '10:00', 'time_end': '12:00'},
        ]),
    )
    todo = create_todo(
        title='待教务发送',
        responsible_person='教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW,
        payload={
            'current_proposal': {
                'session_dates': [{'date': '2026-03-24', 'time_start': '10:00', 'time_end': '12:00'}],
            },
        },
    )

    login_as(admin)
    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/admin-send-to-student',
        json={'force_save': True},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['error'] == '当前报名已通过其他入口发送给学生确认，请刷新状态后再处理'
    assert db.session.get(OATodo, todo.id).workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW


def test_admin_teacher_can_preview_and_submit_workflow_proposal(client, login_as):
    admin_teacher = create_user(username='admin-teacher-workflow', display_name='兼课教务', role='admin')
    student = create_user(username='admin-teacher-student', display_name='兼课学生用户', role='student')
    profile = create_student_profile(user=student, name='兼课学生')
    enrollment = create_enrollment(
        teacher=admin_teacher,
        student_name='兼课学生',
        course_name='兼课课程',
        student_profile=profile,
        status='pending_schedule',
        total_hours=2,
        hours_per_session=2.0,
    )
    todo = create_todo(
        title='兼课待提案',
        responsible_person='兼课教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )

    login_as(admin_teacher)
    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/proposal-preview',
        json={'session_dates': [{'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'}]},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['errors'] == []

    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/teacher-proposal',
        json={
            'session_dates': [{'date': '2026-03-23', 'time_start': '10:00', 'time_end': '12:00'}],
            'note': '兼课教务直接提案',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert db.session.get(OATodo, todo.id).workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW


def test_admin_can_return_workflow_to_teacher_and_cannot_skip_teacher_stage(client, app, login_as, logout):
    _require_workflow_contract(app)
    admin = create_user(username='workflow-return-admin', display_name='退回教务', role='admin')
    teacher = create_user(username='workflow-return-teacher', display_name='退回老师', role='teacher')
    student = create_user(username='workflow-return-student', display_name='退回学生用户', role='student')
    profile = create_student_profile(user=student, name='退回学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='退回学生',
        course_name='退回流程课程',
        student_profile=profile,
        status='pending_schedule',
        total_hours=2,
        hours_per_session=2.0,
    )
    todo = create_todo(
        title='退回待提案',
        responsible_person='退回老师, 教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )

    login_as(admin)
    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/admin-send-to-student',
        json={'force_save': True},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['error'] == '老师尚未提交方案，请先等待老师提案或退回老师重提'
    logout()

    login_as(teacher)
    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/teacher-proposal',
        json={
            'session_dates': [{'date': '2026-03-24', 'time_start': '10:00', 'time_end': '12:00'}],
            'note': '老师先给一版初稿',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert db.session.get(OATodo, todo.id).workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW
    logout()

    login_as(admin)
    response = client.post(
        f'/auth/api/workflow-todos/{todo.id}/admin-return-to-teacher',
        json={'message': '这版时间太靠前，请改成下午档'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    refreshed = db.session.get(OATodo, todo.id)
    assert refreshed.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
    assert _as_json(refreshed.payload)['latest_rejection']['reason'] == '这版时间太靠前，请改成下午档'
    logout()

    login_as(teacher)
    response = client.get('/auth/api/workflow-todos')
    payload = response.get_json()
    reopened = next(item for item in payload['data'] if item['id'] == todo.id)
    assert reopened['can_teacher_propose'] is True
    assert reopened['can_admin_send'] is False
    assert reopened['latest_rejection_text'] == '这版时间太靠前，请改成下午档'


def test_linked_schedule_query_matches_legacy_enrollment_notes_exactly(app):
    teacher = create_user(username='legacy-query-teacher', display_name='LegacyQueryTeacher', role='teacher')
    enrollments = [
        create_enrollment(
            teacher=teacher,
            student_name=f'Legacy学生{i}',
            course_name=f'Legacy课程{i}',
            status='confirmed',
        )
        for i in range(10)
    ]
    target = enrollments[0]
    other = enrollments[-1]
    schedule = create_schedule(
        teacher=teacher,
        course_name='Legacy课程10',
        students='Legacy学生10',
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
        notes=f'自动排课 - 报名#{other.id}',
    )

    assert [item.id for item in _linked_schedule_query(target.id).all()] == []
    assert [item.id for item in _linked_schedule_query(other.id).all()] == [schedule.id]


def test_backfill_schedule_relationships_matches_legacy_notes_exactly(app):
    teacher = create_user(username='legacy-backfill-teacher', display_name='LegacyBackfillTeacher', role='teacher')
    enrollments = [
        create_enrollment(
            teacher=teacher,
            student_name=f'Backfill学生{i}',
            course_name=f'Backfill课程{i}',
            status='confirmed',
        )
        for i in range(10)
    ]
    target = enrollments[0]
    other = enrollments[-1]
    exact_schedule = create_schedule(
        teacher=teacher,
        course_name='Backfill课程10',
        students='Backfill学生10',
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
        notes=f'自动排课 - 报名#{other.id}',
    )
    ambiguous_schedule = create_schedule(
        teacher=teacher,
        course_name='Backfill模糊课程',
        students='Backfill模糊学生',
        schedule_date=date(2026, 3, 19),
        time_start='10:00',
        time_end='12:00',
        notes=f'自动排课 - 报名#{target.id} / 报名#{other.id}',
    )
    exact_schedule.enrollment_id = None
    exact_schedule.teacher_id = None
    ambiguous_schedule.enrollment_id = None
    ambiguous_schedule.teacher_id = None
    db.session.commit()

    updated = backfill_schedule_relationships()
    db.session.expire_all()

    refreshed_exact = db.session.get(CourseSchedule, exact_schedule.id)
    refreshed_ambiguous = db.session.get(CourseSchedule, ambiguous_schedule.id)
    assert updated >= 1
    assert refreshed_exact.enrollment_id == other.id
    assert refreshed_exact.teacher_id == teacher.id
    assert refreshed_ambiguous.enrollment_id is None
    assert refreshed_ambiguous.teacher_id == teacher.id
    assert refreshed_ambiguous.enrollment_id != target.id


def test_update_intake_reopens_waiting_student_confirm_workflow_with_latest_profile_context(client, login_as, logout):
    teacher = create_user(username='intake-refresh-teacher', display_name='改档老师', role='teacher')
    admin = create_user(username='intake-refresh-admin', display_name='改档教务', role='admin')
    student = create_user(username='intake-refresh-student', display_name='改档学生用户', role='student')
    profile = create_student_profile(
        user=student,
        name='改档学生',
        available_slots=[{'day': 0, 'start': '10:00', 'end': '12:00'}],
        excluded_dates=['2026-03-28'],
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='改档学生',
        course_name='改档课程',
        student_profile=profile,
        status='pending_student_confirm',
        confirmed_slot=_build_manual_plan([
            {'date': '2026-03-24', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
        ]),
    )
    workflow = create_todo(
        title='待学生确认重排',
        responsible_person='改档学生',
        enrollment=enrollment,
        due_date=date(2026, 3, 23),
        priority=1,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM,
        payload={
            'current_proposal': {
                'session_dates': [{'date': '2026-03-24', 'time_start': '10:00', 'time_end': '12:00'}],
                'note': '旧方案',
            },
            'context': {
                'student_available_slots_summary': '周一 10:00-12:00',
                'student_excluded_dates_summary': '2026-03-28',
            },
            'sent_to_student_at': '2026-03-20T12:00:00',
        },
    )

    login_as(student)
    response = client.put(
        f'/auth/api/enrollments/{enrollment.id}/intake',
        json={
            'name': '改档学生',
            'phone': profile.phone,
            'delivery_preference': 'offline',
            'available_slots': [{'day': 2, 'start': '18:00', 'end': '20:00'}],
            'excluded_dates': ['2026-03-30'],
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    refreshed_enrollment = db.session.get(Enrollment, enrollment.id)
    refreshed_workflow = db.session.get(OATodo, workflow.id)
    assert refreshed_enrollment.status == 'pending_schedule'
    assert refreshed_enrollment.confirmed_slot is None
    assert refreshed_workflow.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
    assert '学生信息已更新' in refreshed_workflow.notes
    logout()

    login_as(admin)
    action_center = client.get('/auth/api/admin/action-center').get_json()['data']
    assert all(item['enrollment_id'] != enrollment.id for item in action_center['waiting_student_confirm_workflows'])
    assert any(item['id'] == enrollment.id for item in action_center['pending_schedule_enrollments'])
    reopened = next(item for item in action_center['waiting_teacher_proposal_workflows'] if item['id'] == workflow.id)
    assert '周三 18:00-20:00' in reopened['context_summary']
    assert '2026-03-30' in reopened['context_summary']


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
            'course_name': '允许直接改绑',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['enrollment_id'] is None
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


def test_public_intake_availability_parse_returns_structured_slots(client, login_as):
    admin = create_user(username='parse-admin', display_name='解析教务', role='admin')
    teacher = create_user(username='parse-teacher', display_name='解析老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '解析学生',
            'course_name': '解析课程',
            'teacher_id': teacher.id,
            'total_hours': 2,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    token = payload['data']['intake_url'].rsplit('/', 1)[-1]

    response = client.post(
        f'/auth/intake/{token}/availability-parse',
        json={'availability_input_text': '周二周四 19:00-21:00 可以；3月18日不行'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['weekly_slots'] == [
        {'day': 1, 'start': '19:00', 'end': '21:00'},
        {'day': 3, 'start': '19:00', 'end': '21:00'},
    ]
    assert payload['data']['excluded_dates'] == ['2026-03-18']
    assert payload['data']['needs_review'] is True
    assert payload['data']['confidence'] < 0.75
    assert '周二 19:00-21:00' in payload['data']['summary']
    assert '禁排日期：2026-03-18' in payload['data']['summary']


def test_public_intake_availability_parse_can_extract_text_from_image_evidence(client, login_as):
    admin = create_user(username='ocr-admin', display_name='识图教务', role='admin')
    teacher = create_user(username='ocr-teacher', display_name='识图老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '识图学生',
            'course_name': '识图课程',
            'teacher_id': teacher.id,
            'total_hours': 2,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    token = payload['data']['intake_url'].rsplit('/', 1)[-1]

    client.application.config['DOUBAO_VISION_ENABLED'] = True
    client.application.config['DOUBAO_VISION_API_KEY'] = 'test-doubao-key'
    client.application.config['DOUBAO_VISION_MODEL'] = 'doubao-seed-2-0-pro-260215'

    class _FakeVisionResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'output': [
                    {
                        'content': [
                            {'text': '周二周四 19:00-21:00 可以；3月18日不行'},
                        ]
                    }
                ]
            }

    captured = {}
    monkeypatch = pytest.MonkeyPatch()

    def _fake_post(url, headers=None, json=None, timeout=None):
        captured['url'] = url
        captured['headers'] = headers or {}
        captured['json'] = json or {}
        captured['timeout'] = timeout
        return _FakeVisionResponse()

    monkeypatch.setattr(availability_ai_services.requests, 'post', _fake_post)
    try:
        response = client.post(
            f'/auth/intake/{token}/availability-parse',
            json={
                'availability_evidence_items': [
                    {'type': 'image_url', 'content': 'https://example.com/timetable.png'},
                ],
            },
        )
    finally:
        monkeypatch.undo()

    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert captured['json']['input'][0]['content'][0]['image_url'] == 'https://example.com/timetable.png'
    assert payload['data']['weekly_slots'] == [
        {'day': 1, 'start': '19:00', 'end': '21:00'},
        {'day': 3, 'start': '19:00', 'end': '21:00'},
    ]
    assert payload['data']['excluded_dates'] == ['2026-03-18']
    assert any(item['type'] == 'image_ocr' for item in payload['data']['source_evidence_items'])


def test_public_intake_can_submit_confirmed_parse_without_manual_grid(client, login_as):
    admin = create_user(username='parse-submit-admin', display_name='解析提交教务', role='admin')
    teacher = create_user(username='parse-submit-teacher', display_name='解析提交老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '解析提交学生',
            'course_name': '解析提交课程',
            'teacher_id': teacher.id,
            'total_hours': 4,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    enrollment_id = payload['data']['id']
    token = payload['data']['intake_url'].rsplit('/', 1)[-1]

    preview_response = client.post(
        f'/auth/intake/{token}/availability-parse',
        json={'availability_input_text': '周二周四 19:00-21:00 可以；3月18日不行'},
    )
    preview_payload = preview_response.get_json()['data']

    response = client.post(
        f'/auth/intake/{token}',
        json={
            'name': '解析提交学生',
            'phone': '13800000009',
            'delivery_preference': 'online',
            'availability_input_text': '周二周四 19:00-21:00 可以；3月18日不行',
            'confirmed_parse_result': preview_payload,
            'manual_adjustments': {'weekly_slots': [], 'excluded_dates': []},
            'available_times': [],
            'excluded_dates': [],
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True

    enrollment = db.session.get(Enrollment, enrollment_id)
    assert enrollment.status == 'pending_schedule'
    intake = enrollment.to_dict()['availability_intake']
    assert intake['weekly_slots'] == [
        {'day': 1, 'start': '19:00', 'end': '21:00'},
        {'day': 3, 'start': '19:00', 'end': '21:00'},
    ]
    assert intake['excluded_dates'] == ['2026-03-18']


def test_create_enrollment_requires_target_finish_date_for_rush_delivery(client, login_as):
    admin = create_user(username='rush-admin', display_name='冲刺教务', role='admin')
    teacher = create_user(username='rush-teacher', display_name='冲刺老师', role='teacher')

    login_as(admin)
    response = client.post(
        '/auth/api/enrollments',
        json={
            'student_name': '冲刺学生',
            'course_name': '竞赛冲刺课',
            'teacher_id': teacher.id,
            'total_hours': 6,
            'delivery_urgency': 'rush',
        },
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert payload['error'] == '冲刺交付必须填写目标完成日'


def test_student_action_center_unifies_pending_enrollment_and_confirm_action(client, login_as):
    teacher = create_user(username='unified-action-teacher', display_name='统一动作老师', role='teacher')
    student = create_user(username='unified-action-student', display_name='统一动作学生用户', role='student')
    profile = create_student_profile(user=student, name='统一动作学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='统一动作学生',
        course_name='统一动作课程',
        student_profile=profile,
        status='pending_student_confirm',
        total_hours=2,
        hours_per_session=2.0,
        confirmed_slot=_build_manual_plan([
            {'date': '2026-03-24', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
        ]),
    )

    login_as(student)
    payload = client.get('/auth/api/student/action-center').get_json()['data']
    assert payload['counts']['student_action_items'] == 1
    assert payload['student_tracking_items'] == []
    action_item = payload['student_action_items'][0]
    assert action_item['entity_ref'] == {'kind': 'enrollment', 'id': enrollment.id}
    assert action_item['primary_action'] == {'label': '确认当前方案', 'action': 'confirm'}
    assert action_item['secondary_action']['action'] == 'reject'

    response = client.post(
        '/auth/api/student-actions/confirm',
        json={'entity_ref': action_item['entity_ref']},
    )
    result = response.get_json()
    assert response.status_code == 200
    assert result['success'] is True
    assert result['created_count'] == 1
    assert CourseSchedule.query.filter_by(enrollment_id=enrollment.id).count() == 1
    assert db.session.get(Enrollment, enrollment.id).status in {'confirmed', 'active'}


def test_admin_action_center_surfaces_scheduling_risk_cases(client, login_as):
    admin = create_user(username='risk-case-admin', display_name='风险教务', role='admin')
    teacher = create_user(username='risk-case-teacher', display_name='风险老师', role='teacher')
    student = create_user(username='risk-case-student', display_name='风险学生用户', role='student')
    profile = create_student_profile(
        user=student,
        name='风险学生',
        available_slots=[{'day': 0, 'start': '18:00', 'end': '20:00'}],
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='风险学生',
        course_name='风险课程',
        student_profile=profile,
        status='pending_schedule',
        total_hours=4,
        hours_per_session=2.0,
        sessions_per_week=2,
    )
    create_teacher_availability(user=teacher, day_of_week=0, time_start='18:00', time_end='20:00')
    refresh_enrollment_scheduling_ai_state(enrollment)
    db.session.commit()

    login_as(admin)
    payload = client.get('/auth/api/admin/action-center').get_json()['data']
    case_item = next(
        item for item in payload['scheduling_risk_cases']
        if item['entity_ref'] == {'kind': 'enrollment', 'id': enrollment.id}
    )
    assert case_item['severity'] == 'hard'
    assert case_item['recommended_action'] == 'needs_admin_intervention'
    assert '不足以支撑每周 2 节' in case_item['summary']
    assert case_item['hard_errors']
