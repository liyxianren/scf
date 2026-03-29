import pytest

from extensions import db
from modules.auth.models import ChatMessage, Enrollment, StudentProfile, User
from modules.oa.models import CourseFeedback, CourseSchedule, OATodo
from tests.factories import (
    create_chat_message,
    create_enrollment,
    create_feedback,
    create_leave_request,
    create_schedule,
    create_student_profile,
    create_todo,
    create_user,
)


pytestmark = pytest.mark.integration


def test_delete_student_blocked_then_allowed(client, login_as):
    admin = create_user(username='delete-admin', display_name='删除管理员', role='admin')
    teacher = create_user(username='delete-teacher', display_name='删除老师', role='teacher')
    student = create_user(username='delete-student', display_name='删除学生', role='student')
    profile = create_student_profile(user=student, name='删除学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='删除学生',
        course_name='删除前课程',
        student_profile=profile,
        status='pending_schedule',
    )

    login_as(admin)

    response = client.delete(f'/auth/api/users/{student.id}')
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert '报名记录' in payload['error']

    response = client.delete(f'/auth/api/enrollments/{enrollment.id}')
    payload = response.get_json()
    assert payload['success'] is True

    response = client.delete(f'/auth/api/users/{student.id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert db.session.get(User, student.id) is None


def test_delete_enrollment_cascades_related_records(client, login_as):
    admin = create_user(username='cascade-admin', display_name='级联管理员', role='admin')
    teacher = create_user(username='cascade-teacher', display_name='级联老师', role='teacher')
    student = create_user(username='cascade-student', display_name='级联学生', role='student')
    profile = create_student_profile(user=student, name='级联学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='级联学生',
        course_name='级联课程',
        student_profile=profile,
        status='confirmed',
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='级联课程',
        students='级联学生',
        enrollment=enrollment,
        notes=f'自动排课 - 报名#{enrollment.id}',
        delivery_mode='online',
    )
    schedule_id = schedule.id
    create_todo(title='跟进课程', responsible_person='级联管理员', schedule=schedule)
    create_todo(
        title='排课重排',
        responsible_person='级联老师, 教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )
    create_leave_request(schedule=schedule, student_name='级联学生', enrollment=enrollment)
    create_feedback(schedule=schedule, teacher=teacher, status='submitted')
    create_chat_message(sender=student, receiver=teacher, content='关联消息', enrollment=enrollment)

    login_as(admin)
    response = client.delete(f'/auth/api/enrollments/{enrollment.id}')
    payload = response.get_json()
    assert payload['success'] is True

    assert db.session.get(Enrollment, enrollment.id) is None
    assert db.session.get(StudentProfile, profile.id) is None
    assert db.session.get(CourseSchedule, schedule_id) is None
    assert CourseFeedback.query.count() == 0
    assert OATodo.query.count() == 0
    assert ChatMessage.query.count() == 0


def test_stale_replan_workflow_is_hidden_from_auth_and_oa_lists(client, login_as):
    admin = create_user(username='stale-workflow-admin', display_name='孤儿流程管理员', role='admin')
    teacher = create_user(username='stale-workflow-teacher', display_name='孤儿流程老师', role='teacher')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='孤儿流程学生',
        course_name='孤儿流程课程',
        status='pending_schedule',
    )
    workflow_todo = create_todo(
        title='孤儿排课重排',
        responsible_person='孤儿流程老师, 教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )

    db.session.delete(enrollment)
    db.session.commit()
    db.session.expire_all()

    login_as(admin)

    oa_response = client.get('/oa/api/todos')
    oa_payload = oa_response.get_json()
    assert oa_response.status_code == 200
    assert workflow_todo.id not in {item['id'] for item in oa_payload['data']}

    refreshed_todo = db.session.get(OATodo, workflow_todo.id)
    assert refreshed_todo.workflow_status == OATodo.WORKFLOW_STATUS_CANCELLED
    assert refreshed_todo.is_completed is True
    assert '关联报名已删除' in (refreshed_todo.get_payload_data().get('cancel_reason') or '')

    auth_response = client.get('/auth/api/workflow-todos')
    auth_payload = auth_response.get_json()
    assert auth_response.status_code == 200
    assert workflow_todo.id not in {item['id'] for item in auth_payload['data']}
