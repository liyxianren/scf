from datetime import date

import pytest

from extensions import db
from modules.auth.models import LeaveRequest
from modules.oa.models import CourseSchedule, OATodo
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


def test_oa_schedule_delete_cleans_todo_for_unprotected_schedule(client, login_as):
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

    response = client.delete(f'/oa/api/schedules/{schedule_id}')
    payload = response.get_json()
    assert payload['success'] is True
    assert db.session.get(CourseSchedule, schedule_id) is None

    response = client.get('/oa/api/todos')
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['total'] == 0


def test_admin_can_edit_and_delete_historical_schedules(client, login_as):
    admin = create_user(username='history-admin', display_name='历史管理员', role='admin')
    teacher = create_user(username='history-teacher', display_name='历史老师', role='teacher')

    login_as(admin)

    started_schedule = create_schedule(
        teacher=teacher,
        course_name='已开始课程',
        students='开始学生',
        schedule_date=None,
        time_start='07:00',
        time_end='08:00',
        notes='开始前备注',
        location='线上',
        color_tag='blue',
    )
    started_schedule.date = started_schedule.date.replace(year=2026, month=3, day=15)
    started_schedule.day_of_week = started_schedule.date.weekday()
    db.session.commit()

    response = client.put(
        f'/oa/api/schedules/{started_schedule.id}',
        json={'teacher': teacher.display_name, 'time_end': '08:30'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['time_end'] == '08:30'

    response = client.put(
        f'/oa/api/schedules/{started_schedule.id}',
        json={
            'teacher': teacher.display_name,
            'notes': '已补充执行备注',
            'location': '线下教室',
            'color_tag': 'green',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['notes'] == '已补充执行备注'
    assert payload['data']['location'] == '线下教室'
    assert payload['data']['color_tag'] == 'green'

    response = client.delete(f'/oa/api/schedules/{started_schedule.id}')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert db.session.get(CourseSchedule, started_schedule.id) is None

    feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='已反馈课程',
        students='反馈学生',
        schedule_date=started_schedule.date.replace(day=20),
        time_start='10:00',
        time_end='12:00',
    )
    create_feedback(schedule=feedback_schedule, teacher=teacher, status='submitted')

    response = client.put(
        f'/oa/api/schedules/{feedback_schedule.id}',
        json={'teacher': teacher.display_name, 'course_name': '改名失败课程'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['course_name'] == '改名失败课程'

    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='请假历史课程',
        students='请假学生',
        schedule_date=started_schedule.date.replace(day=21),
        time_start='14:00',
        time_end='16:00',
    )
    create_leave_request(schedule=leave_schedule, student_name='请假学生', status='rejected', approved_by=teacher)
    create_todo(title='保留待办', responsible_person='历史管理员', schedule=leave_schedule)

    response = client.put(
        f'/oa/api/schedules/{leave_schedule.id}',
        json={'teacher': teacher.display_name, 'students': '新学生'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['students'] == '新学生'

    response = client.delete(f'/oa/api/schedules/{leave_schedule.id}')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert db.session.get(CourseSchedule, leave_schedule.id) is None
    assert LeaveRequest.query.filter_by(schedule_id=leave_schedule.id).count() == 0
    assert OATodo.query.filter_by(schedule_id=leave_schedule.id).count() == 0


def test_schedule_payload_exposes_admin_guard_reasons(client, login_as):
    admin = create_user(username='schedule-guard-admin', display_name='课表保护管理员', role='admin')
    teacher = create_user(username='schedule-guard-teacher', display_name='课表保护老师', role='teacher')

    protected_schedule = create_schedule(
        teacher=teacher,
        course_name='受保护课程',
        students='受保护学生',
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
    )
    create_feedback(schedule=protected_schedule, teacher=teacher, status='submitted')

    login_as(admin)
    response = client.get(f'/oa/api/schedules/{protected_schedule.id}')
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['admin_can_delete'] is True
    assert payload['data']['admin_delete_block_reason'] is None
    assert payload['data']['admin_can_reschedule'] is True
    assert payload['data']['admin_reschedule_block_reason'] is None


def test_admin_can_create_schedule_for_pending_workflow_enrollment(client, login_as):
    admin = create_user(username='schedule-create-admin', display_name='直建管理员', role='admin')
    teacher = create_user(username='schedule-create-teacher', display_name='直建老师', role='teacher')
    profile = create_student_profile(name='直建学生')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='直建学生',
        course_name='直建报名',
        status='pending_student_confirm',
        student_profile=profile,
    )

    login_as(admin)
    response = client.post(
        '/oa/api/schedules',
        json={
            'date': '2026-03-26',
            'time_start': '10:00',
            'time_end': '12:00',
            'teacher': teacher.display_name,
            'course_name': '直建正式课次',
            'enrollment_id': enrollment.id,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    assert payload['success'] is True
    assert payload['data']['enrollment_id'] == enrollment.id
    assert payload['data']['teacher_id'] == teacher.id


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
    assert response.status_code == 200
    assert payload['data']['time_start'] == '14:00'
    assert payload['data']['time_end'] == '16:00'


def test_admin_can_quick_shift_schedule_time_and_date(client, login_as):
    admin = create_user(username='quick-shift-admin', display_name='快捷调课管理员', role='admin')
    teacher = create_user(username='quick-shift-teacher', display_name='快捷调课老师', role='teacher')

    schedule = create_schedule(
        teacher=teacher,
        course_name='快捷调课课程',
        students='调课学生',
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
    )

    login_as(admin)
    response = client.post(
        f'/oa/api/schedules/{schedule.id}/quick-shift',
        json={'time_shift_minutes': 240},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['date'] == '2026-03-18'
    assert payload['data']['time_start'] == '14:00'
    assert payload['data']['time_end'] == '16:00'

    response = client.post(
        f'/oa/api/schedules/{schedule.id}/quick-shift',
        json={'date_shift_days': 2},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    assert payload['data']['date'] == '2026-03-20'
    assert payload['data']['time_start'] == '14:00'
    assert payload['data']['time_end'] == '16:00'


def test_quick_shift_blocks_conflicts_but_admin_can_move_historical_schedule(client, login_as):
    admin = create_user(username='quick-shift-guard-admin', display_name='快捷防护管理员', role='admin')
    teacher = create_user(username='quick-shift-guard-teacher', display_name='快捷防护老师', role='teacher')

    movable_schedule = create_schedule(
        teacher=teacher,
        course_name='待挪课课程',
        students='待挪课学生',
        schedule_date=date(2026, 3, 18),
        time_start='10:00',
        time_end='12:00',
    )
    create_schedule(
        teacher=teacher,
        course_name='冲突课程',
        students='其他学生',
        schedule_date=date(2026, 3, 18),
        time_start='14:00',
        time_end='16:00',
    )

    historical_schedule = create_schedule(
        teacher=teacher,
        course_name='历史课程',
        students='历史学生',
        schedule_date=date(2026, 3, 19),
        time_start='09:00',
        time_end='11:00',
    )
    create_feedback(schedule=historical_schedule, teacher=teacher, status='submitted')

    login_as(admin)
    response = client.post(
        f'/oa/api/schedules/{movable_schedule.id}/quick-shift',
        json={'time_shift_minutes': 240},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['error'] == '该老师在相同时段已有课程安排'

    response = client.post(
        f'/oa/api/schedules/{historical_schedule.id}/quick-shift',
        json={'date_shift_days': 1},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['date'] == '2026-03-20'
