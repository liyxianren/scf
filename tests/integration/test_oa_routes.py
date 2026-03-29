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


def test_oa_schedule_delete_cancels_schedule_and_preserves_flow_records(client, login_as):
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

    leave_request = create_leave_request(
        schedule=db.session.get(CourseSchedule, schedule_id),
        student_name='排课学生',
        status='pending',
    )

    response = client.delete(
        f'/oa/api/schedules/{schedule_id}',
        json={'reason': '学生暂不继续上课'},
    )
    payload = response.get_json()
    assert payload['success'] is True
    cancelled_schedule = db.session.get(CourseSchedule, schedule_id)
    assert cancelled_schedule is not None
    assert cancelled_schedule.is_cancelled is True
    assert cancelled_schedule.cancel_reason == '学生暂不继续上课'

    generic_todo = OATodo.query.filter_by(title='课后跟进').first()
    assert generic_todo is not None
    assert generic_todo.is_completed is True
    assert '学生暂不继续上课' in (generic_todo.notes or '')

    feedback_todo = OATodo.query.filter_by(
        schedule_id=schedule_id,
        todo_type=OATodo.TODO_TYPE_SCHEDULE_FEEDBACK,
    ).first()
    assert feedback_todo is not None
    assert feedback_todo.workflow_status == OATodo.WORKFLOW_STATUS_CANCELLED

    refreshed_leave = db.session.get(LeaveRequest, leave_request.id)
    assert refreshed_leave.status == 'cancelled'
    assert '学生暂不继续上课' in (refreshed_leave.decision_comment or '')

    response = client.get('/oa/api/schedules?year=2026&month=3')
    payload = response.get_json()
    assert payload['success'] is True
    assert all(item['id'] != schedule_id for item in payload['data'])


def test_admin_cannot_cancel_historical_schedules(client, login_as):
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
            'delivery_mode': 'offline',
        },
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['data']['notes'] == '已补充执行备注'
    assert payload['data']['location'] == '线下教室'
    assert payload['data']['color_tag'] == 'orange'
    assert payload['data']['delivery_mode'] == 'offline'

    response = client.delete(
        f'/oa/api/schedules/{started_schedule.id}',
        json={'reason': '历史课次不允许取消'},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['success'] is False
    assert payload['error'] == '该课程已产生交付事实，不能直接取消课次'
    assert db.session.get(CourseSchedule, started_schedule.id) is not None

    feedback_schedule = create_schedule(
        teacher=teacher,
        course_name='已反馈课程',
        students='反馈学生',
        schedule_date=started_schedule.date.replace(day=20),
        time_start='10:00',
        time_end='12:00',
    )
    create_feedback(schedule=feedback_schedule, teacher=teacher, status='submitted')

    response = client.delete(
        f'/oa/api/schedules/{feedback_schedule.id}',
        json={'reason': '已反馈课程不可取消'},
    )
    payload = response.get_json()
    assert response.status_code == 400
    assert payload['error'] == '该课程已产生交付事实，不能直接取消课次'
    assert db.session.get(CourseSchedule, feedback_schedule.id) is not None

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

    response = client.delete(
        f'/oa/api/schedules/{leave_schedule.id}',
        json={'reason': '已有请假记录的历史课次不可取消'},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload['success'] is True
    refreshed_leave_schedule = db.session.get(CourseSchedule, leave_schedule.id)
    assert refreshed_leave_schedule is not None
    assert refreshed_leave_schedule.is_cancelled is True
    assert LeaveRequest.query.filter_by(schedule_id=leave_schedule.id).count() == 1
    assert OATodo.query.filter_by(schedule_id=leave_schedule.id).count() == 1
    assert LeaveRequest.query.filter_by(schedule_id=leave_schedule.id).first().status == 'rejected'
    assert OATodo.query.filter_by(schedule_id=leave_schedule.id).first().is_completed is True


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
    assert payload['data']['admin_can_delete'] is False
    assert payload['data']['admin_delete_block_reason'] == '该课程已产生交付事实，不能直接取消课次'
    assert payload['data']['admin_can_reschedule'] is False
    assert payload['data']['admin_reschedule_block_reason'] == '该课程已产生交付事实，仅允许修改备注、地点或上课方式'


def test_oa_workflow_todos_expose_business_target_links(client, login_as):
    admin = create_user(username='todo-workflow-admin', display_name='流程待办管理员', role='admin')
    teacher = create_user(username='todo-workflow-teacher', display_name='流程待办老师', role='teacher')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='流程待办学生',
        course_name='流程待办课程',
        status='pending_schedule',
    )
    workflow_todo = create_todo(
        title='待老师提案',
        responsible_person='流程待办老师, 教务',
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
    )

    login_as(admin)
    response = client.get('/oa/api/todos')
    payload = response.get_json()
    assert response.status_code == 200
    todo_payload = next(item for item in payload['data'] if item['id'] == workflow_todo.id)
    assert todo_payload['is_workflow'] is True
    assert todo_payload['workflow_target_url'] == f'/auth/enrollments/{enrollment.id}'
    assert todo_payload['workflow_target_label'] == '打开报名流程'


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
