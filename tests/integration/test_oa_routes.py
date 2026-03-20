import pytest

from extensions import db
from modules.auth.models import LeaveRequest
from modules.oa.models import CourseSchedule
from tests.factories import create_enrollment, create_leave_request, create_student_profile, create_user


pytestmark = pytest.mark.integration


def test_oa_schedule_delete_cleans_leave_and_todo(client, login_as):
    admin = create_user(username='oa-admin', display_name='OA管理员', role='admin')
    teacher = create_user(username='oa-teacher', display_name='OA老师', role='teacher')

    login_as(admin)

    response = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-16',
            'time_start': '10:00',
            'time_end': '12:00',
            'teacher': teacher.display_name,
            'course_name': 'OA 新建课程',
            'students': '排课学生',
            'location': '线上',
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    assert payload['success'] is True
    schedule_id = payload['data']['id']

    response = client.get('/oa/api/schedules?year=2026&month=3')
    payload = response.get_json()
    assert payload['success'] is True
    assert any(item['id'] == schedule_id for item in payload['data'])

    response = client.put(
        f'/oa/api/schedules/{schedule_id}',
        json={
            'course_name': 'OA 更新课程',
            'time_end': '12:30',
            'teacher': teacher.display_name,
        },
    )
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['course_name'] == 'OA 更新课程'
    assert payload['data']['teacher_id'] == teacher.id

    response = client.post(
        '/oa/api/todos',
        json={
            'title': '课后跟进',
            'responsible_people': ['OA管理员'],
            'schedule_id': schedule_id,
        },
    )
    assert response.status_code == 201

    schedule = db.session.get(CourseSchedule, schedule_id)
    create_leave_request(schedule=schedule, student_name='排课学生')

    response = client.delete(f'/oa/api/schedules/{schedule_id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert db.session.get(CourseSchedule, schedule_id) is None
    assert LeaveRequest.query.count() == 0

    response = client.get('/oa/api/todos')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['total'] == 0


def test_oa_todo_batch_operations(client, login_as):
    admin = create_user(username='todo-admin', display_name='待办管理员', role='admin')
    login_as(admin)

    first = client.post(
        '/oa/api/todos',
        json={'title': '待办 A', 'responsible_people': ['待办管理员'], 'priority': 1},
    ).get_json()['data']
    second = client.post(
        '/oa/api/todos',
        json={'title': '待办 B', 'responsible_people': ['待办管理员'], 'priority': 2},
    ).get_json()['data']

    response = client.post(
        '/oa/api/todos/batch',
        json={'action': 'complete', 'ids': [first['id'], second['id']]},
    )
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['affected'] == 2

    response = client.get('/oa/api/todos?status=completed')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['total'] == 2

    response = client.post(
        '/oa/api/todos/batch',
        json={'action': 'delete', 'ids': [first['id'], second['id']]},
    )
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['data']['affected'] == 2

    response = client.get('/oa/api/todos')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['total'] == 0


def test_manual_schedule_conflicts_and_leave_lock(client, login_as):
    admin = create_user(username='conflict-admin', display_name='冲突管理员', role='admin')
    teacher = create_user(username='conflict-teacher', display_name='冲突老师', role='teacher')
    student = create_user(username='conflict-student', display_name='冲突学生', role='student')
    profile = create_student_profile(user=student, name='冲突学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='冲突学生',
        course_name='冲突课程',
        student_profile=profile,
        status='confirmed',
    )

    login_as(admin)
    first = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-18',
            'time_start': '10:00',
            'time_end': '12:00',
            'teacher': teacher.display_name,
            'course_name': '冲突课程',
            'students': '冲突学生',
            'enrollment_id': enrollment.id,
        },
    )
    assert first.status_code == 201
    schedule_id = first.get_json()['data']['id']

    response = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-18',
            'time_start': '11:00',
            'time_end': '13:00',
            'teacher': teacher.display_name,
            'course_name': '冲突课程 2',
            'students': '另一个学生',
        },
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False

    schedule = db.session.get(CourseSchedule, schedule_id)
    create_leave_request(schedule=schedule, student_name='冲突学生', enrollment=enrollment)
    response = client.put(
        f'/oa/api/schedules/{schedule_id}',
        json={'time_start': '14:00', 'time_end': '16:00', 'teacher': teacher.display_name},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert '请假记录' in payload['error']
