from datetime import date, datetime, timedelta

import pytest
from freezegun import freeze_time

from extensions import db
from modules.auth.services import _build_manual_plan
from modules.oa.models import OATodo
from tests.factories import (
    create_enrollment,
    create_feedback,
    create_leave_request,
    create_schedule,
    create_student_profile,
    create_todo,
    create_user,
)


pytestmark = pytest.mark.integration


@freeze_time('2026-03-21 12:00:00')
def test_role_action_centers_group_items_and_sort_overdue(client, login_as):
    admin = create_user(username='action-admin', display_name='行动教务', role='admin')
    teacher = create_user(username='action-teacher', display_name='行动老师', role='teacher')
    student = create_user(username='action-student', display_name='行动学生用户', role='student')
    profile = create_student_profile(user=student, name='行动学生')

    active_enrollment = create_enrollment(
        teacher=teacher,
        student_name='行动学生',
        course_name='行动课程',
        student_profile=profile,
        status='active',
    )
    overdue_feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='行动课程',
        students='行动学生',
        enrollment=active_enrollment,
        schedule_date=date(2026, 3, 18),
        time_start='08:00',
        time_end='09:00',
    )
    current_feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='行动课程',
        students='行动学生',
        enrollment=active_enrollment,
        schedule_date=date(2026, 3, 21),
        time_start='09:30',
        time_end='10:30',
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='行动课程',
        students='行动学生',
        enrollment=active_enrollment,
        schedule_date=date(2026, 3, 23),
        time_start='10:00',
        time_end='12:00',
    )
    pending_leave = create_leave_request(
        schedule=leave_schedule,
        student_name='行动学生',
        enrollment=active_enrollment,
        status='pending',
        makeup_available_slots=[{'day': 3, 'start': '19:00', 'end': '20:00'}],
        makeup_preference_note='周四晚上更方便',
    )
    approved_leave = create_leave_request(
        schedule=leave_schedule,
        student_name='行动学生',
        enrollment=active_enrollment,
        status='approved',
        makeup_available_slots=[{'day': 1, 'start': '18:00', 'end': '20:00'}],
        makeup_preference_note='本周只能晚上补课',
    )
    approved_leave_todo = create_todo(
        title='老师待补课提案',
        responsible_person='行动老师, 教务',
        schedule=leave_schedule,
        enrollment=active_enrollment,
        leave_request=approved_leave,
        due_date=date(2026, 3, 20),
        priority=1,
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
        payload={
            'context': {
                'original_schedule': {
                    'date': leave_schedule.date.isoformat(),
                    'day_of_week': leave_schedule.day_of_week,
                    'time_start': leave_schedule.time_start,
                    'time_end': leave_schedule.time_end,
                },
                'makeup_available_slots': [{'day': 1, 'start': '18:00', 'end': '20:00'}],
                'makeup_preference_summary': '本次可补课时间：周二 18:00-20:00 · 补课备注：本周只能晚上补课',
            },
        },
    )

    teacher_replan_enrollment = create_enrollment(
        teacher=teacher,
        student_name='行动学生',
        course_name='老师待提案课程',
        student_profile=profile,
        status='pending_schedule',
    )
    teacher_replan_todo = create_todo(
        title='老师待提案',
        responsible_person='行动老师',
        enrollment=teacher_replan_enrollment,
        due_date=date(2026, 3, 21),
        priority=1,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
        payload={
            'latest_rejection': {
                'message': '周三不方便，请换时间',
                'created_at': '2026-03-20T10:00:00',
            },
        },
    )

    admin_review_enrollment = create_enrollment(
        teacher=teacher,
        student_name='行动学生',
        course_name='待教务发送课程',
        student_profile=profile,
        status='pending_schedule',
    )
    admin_review_todo = create_todo(
        title='待教务发送',
        responsible_person='教务',
        enrollment=admin_review_enrollment,
        due_date=date(2026, 3, 22),
        priority=1,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW,
        payload={
            'current_proposal': {
                'session_dates': [{'date': '2026-03-24', 'time_start': '10:00', 'time_end': '12:00'}],
                'submitted_at': '2026-03-20T11:00:00',
            },
            'proposal_warnings': ['2026-03-24 10:00-12:00 超出老师原始可用时间'],
        },
    )

    enrollment_waiting_confirm = create_enrollment(
        teacher=teacher,
        student_name='行动学生',
        course_name='待学生确认课程',
        student_profile=profile,
        status='pending_student_confirm',
        confirmed_slot=_build_manual_plan([
            {'date': '2026-03-24', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
        ]),
    )
    workflow_waiting_confirm_enrollment = create_enrollment(
        teacher=teacher,
        student_name='行动学生',
        course_name='工作流待确认课程',
        student_profile=profile,
        status='pending_student_confirm',
        confirmed_slot=_build_manual_plan([
            {'date': '2026-03-25', 'day_of_week': 2, 'time_start': '10:00', 'time_end': '12:00'},
        ]),
    )
    waiting_student_todo = create_todo(
        title='待学生确认重排',
        responsible_person='行动学生',
        enrollment=workflow_waiting_confirm_enrollment,
        due_date=date(2026, 3, 23),
        priority=1,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM,
        payload={
            'current_proposal': {
                'session_dates': [{'date': '2026-03-25', 'time_start': '10:00', 'time_end': '12:00'}],
            },
            'sent_to_student_at': '2026-03-20T12:00:00',
        },
    )

    login_as(teacher)
    payload = client.get('/auth/api/teacher/action-center').get_json()['data']
    assert [item['id'] for item in payload['proposal_workflows']] == [
        approved_leave_todo.id,
        teacher_replan_todo.id,
    ]
    assert [item['id'] for item in payload['pending_feedback_schedules'][:2]] == [
        overdue_feedback_schedule.id,
        current_feedback_schedule.id,
    ]
    assert payload['pending_feedback_schedules'][0]['is_overdue'] is True
    assert [item['id'] for item in payload['leave_requests']] == [pending_leave.id]
    assert '周四晚上更方便' in payload['leave_requests'][0]['makeup_preference_summary']

    login_as(admin)
    payload = client.get('/auth/api/admin/action-center').get_json()['data']
    assert [item['id'] for item in payload['waiting_teacher_proposal_workflows']] == [
        approved_leave_todo.id,
        teacher_replan_todo.id,
    ]
    assert payload['waiting_teacher_proposal_workflows'][0]['teacher_name'] == teacher.display_name
    assert payload['waiting_teacher_proposal_workflows'][0]['context_summary'].startswith('原请假课次：')
    assert '本次可补课时间' in payload['waiting_teacher_proposal_workflows'][0]['context_summary']
    assert [item['id'] for item in payload['pending_admin_send_workflows']] == [admin_review_todo.id]
    assert payload['pending_admin_send_workflows'][0]['proposal_warnings'] == ['2026-03-24 10:00-12:00 超出老师原始可用时间']
    assert '老师原始可用时间' in payload['pending_admin_send_workflows'][0]['proposal_warning_summary']
    assert [item['id'] for item in payload['waiting_student_confirm_workflows']] == [waiting_student_todo.id]
    assert payload['waiting_student_confirm_workflows'][0]['payload']['current_proposal']['session_dates'][0]['date'] == '2026-03-25'
    assert [item['id'] for item in payload['waiting_student_confirm_enrollments']] == [enrollment_waiting_confirm.id]
    assert payload['waiting_student_confirm_enrollments'][0]['session_preview_lines'] == ['2026-03-24 10:00-12:00']
    assert payload['pending_feedback_schedules'][0]['id'] == overdue_feedback_schedule.id
    assert payload['pending_feedback_schedules'][0]['feedback_delay_days'] == 3
    assert payload['pending_feedback_schedules'][0]['missing_feedback_count_for_teacher_recent'] == 2
    assert payload['pending_feedback_schedules'][0]['is_repeat_late_teacher'] is True
    assert [item['id'] for item in payload['pending_leave_requests']] == [pending_leave.id]
    assert '周四晚上更方便' in payload['pending_leave_requests'][0]['makeup_preference_summary']
    assert {item['id'] for item in payload['leave_cases']} == {approved_leave.id, pending_leave.id}
    approved_case = next(item for item in payload['leave_cases'] if item['id'] == approved_leave.id)
    assert approved_case['case_stage_label'] == '待老师提案'
    assert approved_case['related_workflow_id'] == approved_leave_todo.id
    pending_case = next(item for item in payload['leave_cases'] if item['id'] == pending_leave.id)
    assert pending_case['case_stage_label'] == '待审批'

    login_as(student)
    payload = client.get('/auth/api/student/action-center').get_json()['data']
    assert [item['id'] for item in payload['pending_workflows']] == [
        approved_leave_todo.id,
        teacher_replan_todo.id,
        admin_review_todo.id,
        waiting_student_todo.id,
    ]
    assert [item['id'] for item in payload['pending_enrollments']] == [enrollment_waiting_confirm.id]
    assert [item['id'] for item in payload['leave_requests']] == [approved_leave.id, pending_leave.id]


@freeze_time('2026-03-21 12:00:00')
def test_admin_action_center_removes_feedback_after_submit_and_student_sees_feedback(client, login_as):
    admin = create_user(username='feedback-action-admin', display_name='反馈教务', role='admin')
    teacher = create_user(username='feedback-action-teacher', display_name='反馈老师', role='teacher')
    student = create_user(username='feedback-action-student', display_name='反馈学生用户', role='student')
    profile = create_student_profile(user=student, name='反馈学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='反馈学生',
        course_name='反馈行动课程',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='反馈行动课程',
        students='反馈学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 20),
        time_start='08:00',
        time_end='09:00',
    )

    login_as(admin)
    payload = client.get('/auth/api/admin/action-center').get_json()['data']
    assert [item['id'] for item in payload['pending_feedback_schedules']] == [schedule.id]

    login_as(teacher)
    response = client.post(
        f'/auth/api/schedules/{schedule.id}/feedback/submit',
        json={'summary': '本次课程已完成复盘', 'homework': '整理资料', 'next_focus': '准备下一次讨论'},
    )
    assert response.status_code == 200
    assert response.get_json()['success'] is True

    login_as(admin)
    payload = client.get('/auth/api/admin/action-center').get_json()['data']
    assert payload['pending_feedback_schedules'] == []

    login_as(student)
    payload = client.get('/auth/api/student/my-info').get_json()['data']
    schedule_payload = next(item for item in payload['schedules'] if item['id'] == schedule.id)
    assert schedule_payload['feedback']['status'] == 'submitted'
    assert schedule_payload['feedback']['summary'] == '本次课程已完成复盘'
    assert payload['recent_feedbacks'][0]['id'] == schedule.id


@freeze_time('2026-03-21 12:00:00')
def test_student_my_info_uses_upcoming_schedules_and_recent_feedbacks_independently(client, login_as):
    teacher = create_user(username='student-info-teacher', display_name='信息老师', role='teacher')
    student = create_user(username='student-info-student', display_name='信息学生用户', role='student')
    profile = create_student_profile(
        user=student,
        name='信息学生',
        available_slots=[
            {'day': 0, 'start': '10:00', 'end': '12:00'},
            {'day': 2, 'start': '18:00', 'end': '20:00'},
        ],
        excluded_dates=['2026-03-28'],
    )
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='信息学生',
        course_name='信息课程',
        student_profile=profile,
        status='confirmed',
    )
    past_schedule = create_schedule(
        teacher=teacher,
        course_name='信息课程',
        students='信息学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 1),
        time_start='09:00',
        time_end='10:00',
    )
    create_feedback(
        schedule=past_schedule,
        teacher=teacher,
        summary='最早反馈也应出现在 recent_feedbacks',
        status='submitted',
        submitted_at=datetime(2026, 3, 2, 9, 0, 0),
    )
    for offset in range(55):
        create_schedule(
            teacher=teacher,
            course_name='信息课程',
            students='信息学生',
            enrollment=enrollment,
            schedule_date=date(2026, 3, 22) + timedelta(days=offset),
            time_start='10:00',
            time_end='12:00',
        )

    login_as(student)
    payload = client.get('/auth/api/student/my-info').get_json()['data']
    assert payload['profile']['available_times_summary'] == '周一 10:00-12:00；周三 18:00-20:00'
    assert payload['profile']['excluded_dates_summary'] == '2026-03-28'
    assert payload['upcoming_schedules'][0]['date'] == '2026-03-22'
    assert payload['upcoming_schedules'][1]['date'] == '2026-03-23'
    assert payload['recent_feedbacks'][0]['id'] == past_schedule.id
    assert payload['recent_feedbacks'][0]['feedback']['summary'] == '最早反馈也应出现在 recent_feedbacks'


@freeze_time('2026-03-21 12:00:00')
def test_student_history_stays_with_original_student_after_admin_rebind(client, login_as, logout):
    admin = create_user(username='student-snapshot-admin', display_name='学生快照教务', role='admin')
    teacher = create_user(username='student-snapshot-teacher', display_name='学生快照老师', role='teacher')
    first_student = create_user(username='student-snapshot-a', display_name='原学生用户', role='student')
    second_student = create_user(username='student-snapshot-b', display_name='新学生用户', role='student')
    first_profile = create_student_profile(user=first_student, name='原学生')
    second_profile = create_student_profile(user=second_student, name='新学生')
    first_enrollment = create_enrollment(
        teacher=teacher,
        student_name='原学生',
        course_name='归属课程',
        student_profile=first_profile,
        status='confirmed',
    )
    second_enrollment = create_enrollment(
        teacher=teacher,
        student_name='新学生',
        course_name='归属课程',
        student_profile=second_profile,
        status='confirmed',
    )
    delivered_schedule = create_schedule(
        teacher=teacher,
        course_name='归属课程',
        students='原学生',
        enrollment=first_enrollment,
        schedule_date=date(2026, 3, 10),
        time_start='09:00',
        time_end='11:00',
    )
    future_schedule = create_schedule(
        teacher=teacher,
        course_name='归属课程',
        students='原学生',
        enrollment=first_enrollment,
        schedule_date=date(2026, 3, 25),
        time_start='10:00',
        time_end='12:00',
    )
    create_feedback(
        schedule=delivered_schedule,
        teacher=teacher,
        summary='历史反馈应留在原学生侧',
        status='submitted',
        submitted_at=datetime(2026, 3, 11, 9, 0, 0),
    )

    login_as(admin)
    response = client.put(
        f'/oa/api/schedules/{delivered_schedule.id}',
        json={'enrollment_id': second_enrollment.id, 'students': '新学生'},
    )
    assert response.status_code == 200
    response = client.put(
        f'/oa/api/schedules/{future_schedule.id}',
        json={'enrollment_id': second_enrollment.id, 'students': '新学生'},
    )
    assert response.status_code == 200
    logout()

    login_as(first_student)
    payload = client.get('/auth/api/student/my-info').get_json()['data']
    assert delivered_schedule.id in [item['id'] for item in payload['schedules']]
    assert delivered_schedule.id in [item['id'] for item in payload['recent_feedbacks']]
    assert future_schedule.id not in [item['id'] for item in payload['upcoming_schedules']]
    response = client.get(f'/auth/api/schedules/{delivered_schedule.id}/feedback')
    assert response.status_code == 200
    assert response.get_json()['data']['summary'] == '历史反馈应留在原学生侧'
    logout()

    login_as(second_student)
    payload = client.get('/auth/api/student/my-info').get_json()['data']
    assert future_schedule.id in [item['id'] for item in payload['upcoming_schedules']]
    assert delivered_schedule.id not in [item['id'] for item in payload['recent_feedbacks']]
    response = client.get(f'/auth/api/schedules/{delivered_schedule.id}/feedback')
    assert response.status_code == 403


@freeze_time('2026-03-21 12:00:00')
def test_teacher_action_center_keeps_old_feedback_items_and_hides_approved_leave_from_upcoming(client, login_as):
    teacher = create_user(username='teacher-truth-teacher', display_name='真相老师', role='teacher')
    student = create_user(username='teacher-truth-student', display_name='真相学生用户', role='student')
    profile = create_student_profile(user=student, name='真相学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='真相学生',
        course_name='真相课程',
        student_profile=profile,
        status='active',
    )
    old_feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='真相课程',
        students='真相学生',
        enrollment=enrollment,
        schedule_date=date(2026, 2, 15),
        time_start='08:00',
        time_end='09:00',
    )
    approved_leave_schedule = create_schedule(
        teacher=teacher,
        course_name='真相课程',
        students='真相学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 23),
        time_start='10:00',
        time_end='12:00',
    )
    create_leave_request(
        schedule=approved_leave_schedule,
        student_name='真相学生',
        enrollment=enrollment,
        status='approved',
    )

    login_as(teacher)
    payload = client.get('/auth/api/teacher/action-center').get_json()['data']
    assert old_feedback_schedule.id in [item['id'] for item in payload['pending_feedback_schedules']]
    assert approved_leave_schedule.id not in [item['id'] for item in payload['upcoming_schedules']]


@freeze_time('2026-03-21 12:00:00')
def test_teacher_action_center_supports_name_only_teacher_schedules_and_feedback_submit(client, login_as):
    teacher = create_user(username='teacher-nameonly-teacher', display_name='姓名匹配老师', role='teacher')
    past_schedule = create_schedule(
        teacher=teacher,
        course_name='姓名匹配课程',
        students='姓名匹配学生',
        schedule_date=date(2026, 3, 20),
        time_start='08:00',
        time_end='09:00',
    )
    future_schedule = create_schedule(
        teacher=teacher,
        course_name='姓名匹配课程',
        students='姓名匹配学生',
        schedule_date=date(2026, 3, 23),
        time_start='10:00',
        time_end='12:00',
    )
    past_schedule.teacher_id = None
    future_schedule.teacher_id = None
    db.session.commit()

    login_as(teacher)
    payload = client.get('/auth/api/teacher/action-center').get_json()['data']
    assert past_schedule.id in [item['id'] for item in payload['pending_feedback_schedules']]
    assert future_schedule.id in [item['id'] for item in payload['upcoming_schedules']]

    response = client.post(
        f'/auth/api/schedules/{past_schedule.id}/feedback/submit',
        json={'summary': '姓名匹配反馈', 'homework': '整理记录', 'next_focus': '继续推进'},
    )
    assert response.status_code == 200
    assert response.get_json()['success'] is True


@freeze_time('2026-03-21 12:00:00')
def test_teacher_schedule_summary_and_calendar_use_truthful_leave_and_feedback_windows(client, login_as):
    teacher = create_user(username='teacher-window-teacher', display_name='窗口老师', role='teacher')
    student = create_user(username='teacher-window-student', display_name='窗口学生用户', role='student')
    profile = create_student_profile(user=student, name='窗口学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='窗口学生',
        course_name='窗口课程',
        student_profile=profile,
        status='active',
    )
    overdue_feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='窗口课程',
        students='窗口学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 10),
        time_start='08:00',
        time_end='09:00',
    )
    cross_week_schedule = create_schedule(
        teacher=teacher,
        course_name='窗口课程',
        students='窗口学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 23),
        time_start='10:00',
        time_end='12:00',
    )
    approved_leave_schedule = create_schedule(
        teacher=teacher,
        course_name='窗口课程',
        students='窗口学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 24),
        time_start='13:00',
        time_end='15:00',
    )
    create_leave_request(
        schedule=approved_leave_schedule,
        student_name='窗口学生',
        enrollment=enrollment,
        status='approved',
    )

    login_as(teacher)
    payload = client.get('/auth/api/teacher/my-schedule').get_json()['data']
    assert overdue_feedback_schedule.id in [item['id'] for item in payload['pending_feedback_schedules']]
    assert cross_week_schedule.id in [item['id'] for item in payload['upcoming_schedules']]
    assert approved_leave_schedule.id not in [item['id'] for item in payload['upcoming_schedules']]

    payload = client.get('/auth/api/teacher/my-schedules/by-date?start=2026-03-23&end=2026-03-29').get_json()['data']
    assert cross_week_schedule.id in [item['id'] for item in payload]
    assert approved_leave_schedule.id not in [item['id'] for item in payload]


@freeze_time('2026-03-21 12:00:00')
def test_teacher_action_center_recovers_missing_makeup_workflow(client, login_as):
    teacher = create_user(username='teacher-recover-teacher', display_name='补课恢复老师', role='teacher')
    student = create_user(username='teacher-recover-student', display_name='补课恢复学生用户', role='student')
    profile = create_student_profile(user=student, name='补课恢复学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='补课恢复学生',
        course_name='补课恢复课程',
        student_profile=profile,
        status='active',
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='补课恢复课程',
        students='补课恢复学生',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 23),
        time_start='10:00',
        time_end='12:00',
    )
    approved_leave = create_leave_request(
        schedule=leave_schedule,
        student_name='补课恢复学生',
        enrollment=enrollment,
        status='approved',
    )
    assert OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        leave_request_id=approved_leave.id,
    ).count() == 0

    login_as(teacher)
    payload = client.get('/auth/api/teacher/action-center').get_json()['data']
    workflow = next(item for item in payload['proposal_workflows'] if item.get('leave_request_id') == approved_leave.id)
    assert workflow['workflow_status'] == 'waiting_teacher_proposal'
    assert OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        leave_request_id=approved_leave.id,
    ).count() == 1
