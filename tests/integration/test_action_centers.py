from datetime import date

import pytest
from freezegun import freeze_time

from modules.auth.services import _build_manual_plan
from modules.oa.models import OATodo
from tests.factories import (
    create_enrollment,
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
    assert payload['waiting_teacher_proposal_workflows'][0]['context_summary'].startswith('原请假课次：')
    assert '本次可补课时间' in payload['waiting_teacher_proposal_workflows'][0]['context_summary']
    assert [item['id'] for item in payload['pending_admin_send_workflows']] == [admin_review_todo.id]
    assert payload['pending_admin_send_workflows'][0]['proposal_warnings'] == ['2026-03-24 10:00-12:00 超出老师原始可用时间']
    assert '老师原始可用时间' in payload['pending_admin_send_workflows'][0]['proposal_warning_summary']
    assert [item['id'] for item in payload['waiting_student_confirm_workflows']] == [waiting_student_todo.id]
    assert payload['waiting_student_confirm_workflows'][0]['payload']['current_proposal']['session_dates'][0]['date'] == '2026-03-25'
    assert [item['id'] for item in payload['waiting_student_confirm_enrollments']] == [enrollment_waiting_confirm.id]
    assert payload['pending_feedback_schedules'][0]['id'] == overdue_feedback_schedule.id
    assert [item['id'] for item in payload['pending_leave_requests']] == [pending_leave.id]
    assert '周四晚上更方便' in payload['pending_leave_requests'][0]['makeup_preference_summary']

    login_as(student)
    payload = client.get('/auth/api/student/action-center').get_json()['data']
    assert [item['id'] for item in payload['pending_workflows']] == [waiting_student_todo.id]
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
