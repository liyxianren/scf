from datetime import date

from extensions import db
from modules.auth.models import IntegrationActionLog
from modules.auth.workflow_services import ensure_schedule_feedback_todo
from modules.oa.models import CourseFeedback, OATodo
from tests.factories import (
    create_enrollment,
    create_external_identity,
    create_leave_request,
    create_schedule,
    create_student_profile,
    create_teacher_availability,
    create_todo,
    create_user,
)


def _headers(app):
    return {'X-Integration-Token': app.config['OPENCLAW_INTEGRATION_TOKEN']}


def _external_headers(app):
    return {'X-OA-API-Key': app.config['OA_EXTERNAL_API_KEY']}


def _identity_params(identity):
    return {
        'provider': identity.provider,
        'external_user_id': identity.external_user_id,
    }


def _command(identity, request_id, action, payload):
    return {
        'provider': identity.provider,
        'external_user_id': identity.external_user_id,
        'request_id': request_id,
        'action': action,
        'payload': payload,
    }


def _single_session(session_date='2026-03-16', *, day_of_week=0, time_start='10:00', time_end='12:00'):
    return [{
        'date': session_date,
        'day_of_week': day_of_week,
        'time_start': time_start,
        'time_end': time_end,
    }]


def test_openclaw_summary_requires_identity_mapping(client, app):
    response = client.get(
        '/oa/api/integration/openclaw/me/summary',
        query_string={'provider': 'feishu', 'external_user_id': 'missing-user'},
        headers=_headers(app),
    )

    assert response.status_code == 401
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['code'] == 'identity_not_found'


def test_openclaw_summary_returns_admin_and_teacher_specific_counts(client, app):
    admin = create_user(role='admin', username='admin-openclaw')
    teacher = create_user(role='teacher', username='teacher-openclaw')
    student_user = create_user(role='student', username='student-openclaw')
    admin_identity = create_external_identity(user=admin, external_user_id='ou_admin')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_teacher')
    create_teacher_availability(user=teacher)
    profile = create_student_profile(user=student_user, name='Student OpenClaw')

    past_enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Student OpenClaw',
        course_name='History',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    past_schedule = create_schedule(
        teacher=teacher,
        course_name='History',
        students='Student OpenClaw',
        enrollment=past_enrollment,
        schedule_date=date(2026, 3, 15),
    )

    leave_enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Student OpenClaw',
        course_name='Chemistry',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    leave_schedule = create_schedule(
        teacher=teacher,
        course_name='Chemistry',
        students='Student OpenClaw',
        enrollment=leave_enrollment,
        schedule_date=date(2026, 3, 20),
    )
    create_leave_request(
        schedule=leave_schedule,
        enrollment=leave_enrollment,
        student_name='Student OpenClaw',
        status='pending',
    )

    teacher_todo = create_todo(
        title='Teacher Proposal',
        responsible_person=teacher.display_name,
        enrollment=past_enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
        payload={},
    )
    create_todo(
        title='Admin Send',
        responsible_person='教务',
        enrollment=past_enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW,
        payload={},
    )

    teacher_response = client.get(
        '/oa/api/integration/openclaw/me/summary',
        query_string=_identity_params(teacher_identity),
        headers=_headers(app),
    )
    assert teacher_response.status_code == 200
    teacher_payload = teacher_response.get_json()['data']
    assert teacher_payload['counts']['proposal_workflows'] >= 1
    assert teacher_payload['counts']['pending_feedback_schedules'] == 1
    assert teacher_payload['counts']['pending_leave_requests'] == 1
    assert teacher_payload['primary_action'] == 'workflow.teacher_proposal.submit'
    assert any(item['id'] == teacher_todo.id for item in teacher_payload['cards'][0]['items'])

    admin_response = client.get(
        '/oa/api/integration/openclaw/me/summary',
        query_string=_identity_params(admin_identity),
        headers=_headers(app),
    )
    assert admin_response.status_code == 200
    admin_payload = admin_response.get_json()['data']
    assert admin_payload['counts']['pending_admin_send_workflows'] == 1
    assert admin_payload['counts']['pending_leave_requests'] == 1
    assert admin_payload['counts']['pending_feedback_schedules'] == 1
    assert admin_payload['primary_action'] == 'workflow.admin_send_to_student'


def test_openclaw_me_schedules_and_work_items_are_actor_scoped(client, app):
    admin = create_user(role='admin', username='admin-schedules')
    teacher = create_user(role='teacher', username='teacher-schedules')
    other_teacher = create_user(role='teacher', username='teacher-other')
    student_user = create_user(role='student', username='student-schedules')
    admin_identity = create_external_identity(user=admin, external_user_id='ou_admin_schedules')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_teacher_schedules')
    create_teacher_availability(user=teacher)
    create_teacher_availability(user=other_teacher)
    profile = create_student_profile(user=student_user, name='Scoped Student')

    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Scoped Student',
        course_name='Physics',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    teacher_schedule = create_schedule(
        teacher=teacher,
        course_name='Physics',
        students='Scoped Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 15),
    )
    future_schedule = create_schedule(
        teacher=teacher,
        course_name='Physics',
        students='Scoped Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 21),
    )
    create_schedule(
        teacher=other_teacher,
        course_name='Biology',
        students='Other Student',
        schedule_date=date(2026, 3, 21),
    )
    create_todo(
        title='Need Proposal',
        responsible_person=teacher.display_name,
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
        payload={},
    )
    create_leave_request(
        schedule=future_schedule,
        enrollment=enrollment,
        student_name='Scoped Student',
        status='pending',
    )

    schedule_response = client.get(
        '/oa/api/integration/openclaw/me/schedules',
        query_string=_identity_params(teacher_identity),
        headers=_headers(app),
    )
    assert schedule_response.status_code == 200
    schedule_payload = schedule_response.get_json()['data']
    returned_ids = {item['id'] for item in schedule_payload['items']}
    assert returned_ids == {teacher_schedule.id, future_schedule.id}
    assert schedule_payload['total'] == 2

    admin_schedule_response = client.get(
        '/oa/api/integration/openclaw/me/schedules',
        query_string=_identity_params(admin_identity),
        headers=_headers(app),
    )
    assert admin_schedule_response.status_code == 200
    assert admin_schedule_response.get_json()['data']['total'] == 3

    work_items_response = client.get(
        '/oa/api/integration/openclaw/me/work-items',
        query_string=_identity_params(teacher_identity),
        headers=_headers(app),
    )
    assert work_items_response.status_code == 200
    work_items = work_items_response.get_json()['data']
    assert work_items['counts']['workflow_todos'] == 1
    assert work_items['counts']['pending_feedback_schedules'] == 1
    assert work_items['counts']['pending_leave_requests'] == 1


def test_openclaw_manual_plan_is_idempotent(client, app):
    admin = create_user(role='admin', username='admin-manual-plan')
    teacher = create_user(role='teacher', username='teacher-manual-plan')
    student_user = create_user(role='student', username='student-manual-plan')
    identity = create_external_identity(user=admin, external_user_id='ou_admin_manual_plan')
    create_teacher_availability(user=teacher)
    profile = create_student_profile(user=student_user, name='Manual Plan Student')
    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Manual Plan Student',
        course_name='Writing',
        status='pending_schedule',
        total_hours=2,
        hours_per_session=2,
    )

    payload = _command(
        identity,
        'req-manual-plan-1',
        'enrollment.manual_plan.save',
        {
            'enrollment_id': enrollment.id,
            'session_dates': _single_session(),
        },
    )
    first_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=payload,
        headers=_headers(app),
    )
    assert first_response.status_code == 200
    assert first_response.get_json()['success'] is True
    db.session.refresh(enrollment)
    assert enrollment.status == 'pending_student_confirm'

    second_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=payload,
        headers=_headers(app),
    )
    assert second_response.status_code == 200
    assert second_response.get_json()['success'] is True
    assert second_response.get_json()['data']['integration_meta']['replayed'] is True
    assert IntegrationActionLog.query.filter_by(request_id='req-manual-plan-1').count() == 1


def test_openclaw_workflow_commands_cover_preview_submit_and_admin_send(client, app):
    admin = create_user(role='admin', username='admin-workflow')
    teacher = create_user(role='teacher', username='teacher-workflow')
    student_user = create_user(role='student', username='student-workflow')
    admin_identity = create_external_identity(user=admin, external_user_id='ou_admin_workflow')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_teacher_workflow')
    create_teacher_availability(user=teacher)
    profile = create_student_profile(user=student_user, name='Workflow Student')
    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Workflow Student',
        course_name='Economics',
        status='pending_schedule',
        total_hours=2,
        hours_per_session=2,
    )
    todo = create_todo(
        title='Replan Workflow',
        responsible_person=teacher.display_name,
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
        payload={},
    )

    role_mismatch = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            teacher_identity,
            'req-admin-send-blocked',
            'workflow.admin_send_to_student',
            {'todo_id': todo.id},
        ),
        headers=_headers(app),
    )
    assert role_mismatch.status_code == 403

    preview_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            teacher_identity,
            'req-preview-workflow',
            'workflow.teacher_proposal.preview',
            {
                'todo_id': todo.id,
                'session_dates': _single_session(),
            },
        ),
        headers=_headers(app),
    )
    assert preview_response.status_code == 200
    assert preview_response.get_json()['success'] is True
    assert preview_response.get_json()['data']['current_plan_session_dates'][0]['date'] == '2026-03-16'

    submit_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            teacher_identity,
            'req-submit-workflow',
            'workflow.teacher_proposal.submit',
            {
                'todo_id': todo.id,
                'session_dates': _single_session(),
                'note': 'teacher proposal note',
            },
        ),
        headers=_headers(app),
    )
    assert submit_response.status_code == 200
    db.session.refresh(todo)
    assert todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_ADMIN_REVIEW

    send_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            admin_identity,
            'req-admin-send-workflow',
            'workflow.admin_send_to_student',
            {'todo_id': todo.id},
        ),
        headers=_headers(app),
    )
    assert send_response.status_code == 200
    db.session.refresh(todo)
    db.session.refresh(enrollment)
    assert todo.workflow_status == OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM
    assert enrollment.status == 'pending_student_confirm'


def test_openclaw_feedback_submit_enforces_scope_and_completes_feedback_flow(client, app):
    teacher = create_user(role='teacher', username='teacher-feedback-1')
    other_teacher = create_user(role='teacher', username='teacher-feedback-2')
    student_user = create_user(role='student', username='student-feedback')
    teacher_identity = create_external_identity(user=teacher, external_user_id='ou_teacher_feedback_1')
    other_identity = create_external_identity(user=other_teacher, external_user_id='ou_teacher_feedback_2')
    create_teacher_availability(user=teacher)
    profile = create_student_profile(user=student_user, name='Feedback Student')
    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Feedback Student',
        course_name='Literature',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='Literature',
        students='Feedback Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 15),
    )
    todo = ensure_schedule_feedback_todo(schedule, created_by=teacher.id)
    db.session.commit()

    forbidden_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            other_identity,
            'req-feedback-forbidden',
            'feedback.submit',
            {
                'schedule_id': schedule.id,
                'summary': 'forbidden',
                'homework': 'forbidden',
                'next_focus': 'forbidden',
            },
        ),
        headers=_headers(app),
    )
    assert forbidden_response.status_code == 403

    success_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            teacher_identity,
            'req-feedback-success',
            'feedback.submit',
            {
                'schedule_id': schedule.id,
                'summary': 'Great progress',
                'homework': 'Essay outline',
                'next_focus': 'Polish thesis',
            },
        ),
        headers=_headers(app),
    )
    assert success_response.status_code == 200
    feedback = CourseFeedback.query.filter_by(schedule_id=schedule.id, teacher_id=teacher.id).first()
    assert feedback is not None
    assert feedback.status == 'submitted'
    db.session.refresh(todo)
    assert todo.is_completed is True
    assert todo.workflow_status == OATodo.WORKFLOW_STATUS_COMPLETED


def test_openclaw_leave_commands_trigger_workflow_and_reject_flow(client, app):
    teacher = create_user(role='teacher', username='teacher-leave-command')
    student_user = create_user(role='student', username='student-leave-command')
    identity = create_external_identity(user=teacher, external_user_id='ou_teacher_leave_command')
    create_teacher_availability(user=teacher)
    profile = create_student_profile(user=student_user, name='Leave Student')
    enrollment = create_enrollment(
        teacher=teacher,
        student_profile=profile,
        student_name='Leave Student',
        course_name='Math',
        status='confirmed',
        total_hours=2,
        hours_per_session=2,
    )
    schedule = create_schedule(
        teacher=teacher,
        course_name='Math',
        students='Leave Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 20),
    )
    feedback_todo = ensure_schedule_feedback_todo(schedule, created_by=teacher.id)
    leave_request = create_leave_request(
        schedule=schedule,
        enrollment=enrollment,
        student_name='Leave Student',
        status='pending',
    )
    db.session.commit()

    approve_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-leave-approve',
            'leave.approve',
            {'leave_request_id': leave_request.id, 'comment': 'approve via openclaw'},
        ),
        headers=_headers(app),
    )
    assert approve_response.status_code == 200
    db.session.refresh(leave_request)
    db.session.refresh(feedback_todo)
    assert leave_request.status == 'approved'
    assert feedback_todo.workflow_status == OATodo.WORKFLOW_STATUS_CANCELLED
    assert feedback_todo.is_completed is True
    makeup_todo = OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        leave_request_id=leave_request.id,
    ).first()
    assert makeup_todo is not None

    second_schedule = create_schedule(
        teacher=teacher,
        course_name='Math',
        students='Leave Student',
        enrollment=enrollment,
        schedule_date=date(2026, 3, 22),
    )
    reject_request = create_leave_request(
        schedule=second_schedule,
        enrollment=enrollment,
        student_name='Leave Student',
        status='pending',
    )

    reject_response = client.post(
        '/oa/api/integration/openclaw/command',
        json=_command(
            identity,
            'req-leave-reject',
            'leave.reject',
            {'leave_request_id': reject_request.id, 'comment': 'need more proof'},
        ),
        headers=_headers(app),
    )
    assert reject_response.status_code == 200
    db.session.refresh(reject_request)
    assert reject_request.status == 'rejected'
    assert OATodo.query.filter_by(
        todo_type=OATodo.TODO_TYPE_LEAVE_MAKEUP,
        leave_request_id=reject_request.id,
    ).count() == 0


def test_external_todo_cannot_mutate_workflow_todo(client, app):
    teacher = create_user(role='teacher', username='teacher-guarded-todo')
    enrollment = create_enrollment(
        teacher=teacher,
        student_name='Guarded Student',
        course_name='Geography',
        status='pending_schedule',
        total_hours=2,
        hours_per_session=2,
    )
    workflow_todo = create_todo(
        title='Guarded Workflow Todo',
        responsible_person=teacher.display_name,
        enrollment=enrollment,
        todo_type=OATodo.TODO_TYPE_ENROLLMENT_REPLAN,
        workflow_status=OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL,
        payload={},
    )

    response = client.put(
        f'/oa/api/external/todos/{workflow_todo.id}',
        json={'title': 'Should Not Update'},
        headers=_external_headers(app),
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['success'] is False
    assert payload['code'] == 'workflow_todo_guarded'
