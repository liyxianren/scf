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
        color_tag='green',
    )
    schedule_id = schedule.id
    create_todo(title='跟进课程', responsible_person='级联管理员', schedule=schedule)
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
