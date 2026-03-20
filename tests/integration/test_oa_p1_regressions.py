import io
import json
from datetime import date

import pytest
from openpyxl import Workbook
from openpyxl.utils.datetime import to_excel

from extensions import db
from modules.auth.models import Enrollment
from modules.auth.services import _build_manual_plan
from modules.auth.workflow_services import ensure_schedule_feedback_todo
from modules.oa.models import CourseSchedule, OATodo
from tests.factories import (
    create_enrollment,
    create_leave_request,
    create_schedule,
    create_student_profile,
    create_todo,
    create_user,
)


pytestmark = pytest.mark.integration


def _build_import_workbook():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = '3月'
    sheet['H1'] = 'todo'
    sheet['A2'] = int(to_excel(date(2026, 3, 16)))
    sheet['B2'] = int(to_excel(date(2026, 3, 17)))
    sheet['C2'] = int(to_excel(date(2026, 3, 18)))
    sheet['A3'] = '10:00-12:00 ImportTeacher\nImportCourse AI\nImportStudent'
    sheet['B3'] = '10:00-12:00 ImportTeacher\nUnknownCourse AI\nUnknownStudent'
    sheet['C3'] = '10:00-12:00 ImportTeacher\nConflictImport AI\nOtherStudent'

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def test_admin_instructor_can_submit_feedback_and_complete_enrollment(client, login_as):
    admin_teacher = create_user(
        username='oa-p1-admin-teacher',
        display_name='AdminTeacher',
        role='admin',
    )
    student = create_user(
        username='oa-p1-feedback-student',
        display_name='FeedbackStudentUser',
        role='student',
    )
    profile = create_student_profile(user=student, name='FeedbackStudent')
    enrollment = create_enrollment(
        teacher=admin_teacher,
        student_name='FeedbackStudent',
        course_name='FeedbackCourse',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    schedule = create_schedule(
        teacher=admin_teacher,
        course_name='FeedbackCourse',
        students='FeedbackStudent',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 16),
        time_start='08:00',
        time_end='09:00',
    )
    todo = ensure_schedule_feedback_todo(schedule, created_by=admin_teacher.id)
    db.session.commit()

    login_as(admin_teacher)
    response = client.get('/oa/api/schedules?year=2026&month=3')
    payload = response.get_json()
    schedule_payload = next(item for item in payload['data'] if item['id'] == schedule.id)
    assert schedule_payload['can_submit_feedback'] is True

    response = client.post(
        f'/auth/api/schedules/{schedule.id}/feedback/submit',
        json={
            'summary': 'Admin submitted the final feedback.',
            'homework': 'Review the notes.',
            'next_focus': 'Prepare the next course.',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['status'] == 'submitted'
    assert db.session.get(Enrollment, enrollment.id).status == 'completed'
    assert db.session.get(OATodo, todo.id).workflow_status == OATodo.WORKFLOW_STATUS_COMPLETED


def test_student_workflow_todos_hide_schedule_feedback(client, login_as):
    teacher = create_user(username='oa-p1-student-visible-teacher', display_name='VisibleTeacher', role='teacher')
    student = create_user(username='oa-p1-student-visible-student', display_name='VisibleStudentUser', role='student')
    profile = create_student_profile(user=student, name='VisibleStudent')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='VisibleStudent',
        course_name='VisibleCourse',
        student_profile=profile,
        status='confirmed',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='VisibleCourse',
        students='VisibleStudent',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 16),
        time_start='08:00',
        time_end='09:00',
    )
    create_todo(
        title='Feedback workflow',
        responsible_person='VisibleTeacher',
        schedule=schedule,
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )
    create_todo(
        title='Replan workflow',
        responsible_person='VisibleStudent',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM,
    )

    login_as(student)
    response = client.get('/auth/api/workflow-todos')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    todo_types = {item['todo_type'] for item in payload['data']}
    assert 'schedule_feedback' not in todo_types
    assert 'enrollment_replan' in todo_types


def test_stale_replan_confirmation_returns_workflow_to_teacher(client, login_as):
    teacher = create_user(username='oa-p1-replan-teacher', display_name='ReplanTeacher', role='teacher')
    other_teacher = create_user(username='oa-p1-replan-other-teacher', display_name='ReplanOtherTeacher', role='teacher')
    student = create_user(username='oa-p1-replan-student', display_name='ReplanStudentUser', role='student')
    profile = create_student_profile(user=student, name='ReplanStudent')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='ReplanStudent',
        course_name='ReplanCourse',
        student_profile=profile,
        status='pending_student_confirm',
        total_hours=2,
        hours_per_session=2.0,
    )
    session_dates = [
        {'date': '2026-03-17', 'day_of_week': 1, 'time_start': '10:00', 'time_end': '12:00'},
    ]
    plan = _build_manual_plan(session_dates)
    enrollment.confirmed_slot = json.dumps(plan, ensure_ascii=False)
    db.session.commit()
    todo = create_todo(
        title='Replan waiting student',
        responsible_person='ReplanStudent',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM,
        payload={'current_proposal': plan},
    )
    other_enrollment = create_enrollment(
        teacher=other_teacher,
        student_name='ReplanStudent',
        course_name='OtherCourse',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    create_schedule(
        teacher=other_teacher,
        course_name='OtherCourse',
        students='ReplanStudent',
        enrollment=other_enrollment,
        schedule_date=date(2026, 3, 17),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(student)
    response = client.post(f'/auth/api/workflow-todos/{todo.id}/student-confirm')
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    refreshed_todo = db.session.get(OATodo, todo.id)
    refreshed_enrollment = db.session.get(Enrollment, enrollment.id)
    assert refreshed_todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
    assert refreshed_enrollment.confirmed_slot is None
    assert refreshed_enrollment.status == 'pending_schedule'


def test_stale_makeup_confirmation_returns_workflow_to_teacher(client, login_as):
    teacher = create_user(username='oa-p1-makeup-teacher', display_name='MakeupTeacher', role='teacher')
    other_teacher = create_user(username='oa-p1-makeup-other-teacher', display_name='MakeupOtherTeacher', role='teacher')
    student = create_user(username='oa-p1-makeup-student', display_name='MakeupStudentUser', role='student')
    profile = create_student_profile(user=student, name='MakeupStudent')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='MakeupStudent',
        course_name='MakeupCourse',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    original_schedule = create_schedule(
        teacher=teacher,
        course_name='MakeupCourse',
        students='MakeupStudent',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 16),
        time_start='08:00',
        time_end='09:00',
    )
    leave_request = create_leave_request(
        schedule=original_schedule,
        student_name='MakeupStudent',
        enrollment=enrollment,
        status='approved',
        approved_by=teacher,
    )
    plan = _build_manual_plan([
        {'date': '2026-03-18', 'day_of_week': 2, 'time_start': '14:00', 'time_end': '16:00'},
    ])
    todo = create_todo(
        title='Makeup waiting student',
        responsible_person='MakeupStudent',
        schedule=original_schedule,
        enrollment=enrollment,
        leave_request=leave_request,
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM,
        payload={'current_proposal': plan},
    )
    other_enrollment = create_enrollment(
        teacher=other_teacher,
        student_name='MakeupStudent',
        course_name='OtherMakeupCourse',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    create_schedule(
        teacher=other_teacher,
        course_name='OtherMakeupCourse',
        students='MakeupStudent',
        enrollment=other_enrollment,
        schedule_date=date(2026, 3, 18),
        time_start='14:00',
        time_end='16:00',
    )

    login_as(student)
    response = client.post(f'/auth/api/workflow-todos/{todo.id}/student-confirm')
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    refreshed_todo = db.session.get(OATodo, todo.id)
    assert refreshed_todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
    assert CourseSchedule.query.filter(
        CourseSchedule.notes.contains(f'请假#{leave_request.id}')
    ).count() == 0


def test_same_student_conflict_and_leave_lock_behaviour(client, login_as):
    admin = create_user(username='oa-p1-routes-admin', display_name='RoutesAdmin', role='admin')
    teacher = create_user(username='oa-p1-routes-teacher', display_name='RoutesTeacher', role='teacher')
    other_teacher = create_user(username='oa-p1-routes-other-teacher', display_name='RoutesOtherTeacher', role='teacher')
    student = create_user(username='oa-p1-routes-student', display_name='RoutesStudentUser', role='student')
    profile = create_student_profile(user=student, name='RoutesStudent')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='RoutesStudent',
        course_name='RoutesCourse',
        student_profile=profile,
        status='confirmed',
    )
    other_enrollment = create_enrollment(
        teacher=other_teacher,
        student_name='RoutesStudent',
        course_name='RoutesOtherCourse',
        student_profile=profile,
        status='confirmed',
    )
    create_schedule(
        teacher=teacher,
        course_name='RoutesCourse',
        students='RoutesStudent',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
    )
    rejected_leave_schedule = create_schedule(
        teacher=teacher,
        course_name='RejectedLeaveCourse',
        students='RoutesStudent',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 19),
        time_start='10:00',
        time_end='12:00',
    )
    create_leave_request(
        schedule=rejected_leave_schedule,
        student_name='RoutesStudent',
        enrollment=enrollment,
        status='rejected',
        approved_by=teacher,
    )

    login_as(admin)
    response = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-18',
            'time_start': '10:30',
            'time_end': '11:30',
            'teacher': other_teacher.display_name,
            'course_name': 'RoutesOtherCourse',
            'students': 'RoutesStudent',
            'enrollment_id': other_enrollment.id,
        },
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert CourseSchedule.query.filter_by(
        enrollment_id=other_enrollment.id,
        date=date(2026, 3, 18),
    ).count() == 0

    response = client.put(
        f'/oa/api/schedules/{rejected_leave_schedule.id}',
        json={
            'teacher': teacher.display_name,
            'time_start': '13:00',
            'time_end': '15:00',
        },
    )
    assert response.status_code == 200

    approved_leave_schedule = create_schedule(
        teacher=teacher,
        course_name='ApprovedLeaveCourse',
        students='RoutesStudent',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 20),
        time_start='10:00',
        time_end='12:00',
    )
    approved_leave = create_leave_request(
        schedule=approved_leave_schedule,
        student_name='RoutesStudent',
        enrollment=enrollment,
        status='approved',
        approved_by=teacher,
    )
    create_todo(
        title='Open makeup workflow',
        responsible_person='RoutesTeacher',
        schedule=approved_leave_schedule,
        enrollment=enrollment,
        leave_request=approved_leave,
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )

    response = client.put(
        f'/oa/api/schedules/{approved_leave_schedule.id}',
        json={
            'teacher': teacher.display_name,
            'time_start': '13:00',
            'time_end': '15:00',
        },
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert '请假记录' in payload['error']


def test_excel_import_creates_binding_todo_and_feedback_workflow(client, login_as):
    admin = create_user(username='oa-p1-import-admin', display_name='ImportAdmin', role='admin')
    teacher = create_user(username='oa-p1-import-teacher', display_name='ImportTeacher', role='teacher')
    student = create_user(username='oa-p1-import-student', display_name='ImportStudentUser', role='student')
    profile = create_student_profile(user=student, name='ImportStudent')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='ImportStudent',
        course_name='ImportCourse AI',
        student_profile=profile,
        status='confirmed',
        total_hours=2,
        hours_per_session=2.0,
    )
    create_schedule(
        teacher=teacher,
        course_name='ExistingConflict',
        students='OtherStudent',
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(admin)
    response = client.post(
        '/oa/api/import-excel',
        data={'file': (_build_import_workbook(), '2026-oa.xlsx')},
        content_type='multipart/form-data',
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    summary = payload['data']
    assert summary['binding_todos_created'] == 1
    assert len(summary['unmatched_schedules']) == 1
    assert len(summary['conflict_rows']) == 1

    bound_schedule = CourseSchedule.query.filter_by(
        enrollment_id=enrollment.id,
        date=date(2026, 3, 16),
        course_name='ImportCourse AI',
    ).first()
    assert bound_schedule is not None
    assert OATodo.query.filter_by(
        schedule_id=bound_schedule.id,
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
    ).count() == 1

    unmatched_schedule = CourseSchedule.query.filter_by(
        enrollment_id=None,
        date=date(2026, 3, 17),
        course_name='UnknownCourse AI',
    ).first()
    assert unmatched_schedule is not None
    unmatched_todo = OATodo.query.filter_by(
        schedule_id=unmatched_schedule.id,
        todo_type=OATodo.TODO_TYPE_EXCEL_IMPORT,
    ).first()
    assert unmatched_todo is not None
    todo_payload = unmatched_todo.get_payload_data()
    assert todo_payload['issue_type'] == 'unmatched_enrollment'
    assert todo_payload['schedule_id'] == unmatched_schedule.id

    assert CourseSchedule.query.filter_by(
        date=date(2026, 3, 18),
        course_name='ConflictImport AI',
    ).count() == 0
