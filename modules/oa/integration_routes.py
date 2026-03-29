"""OpenClaw integration routes."""

from datetime import date

from flask import jsonify, request

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import IntegrationActionLog, LeaveRequest
from modules.auth.workflow_services import (
    admin_send_workflow_to_student,
    get_workflow_todo,
    preview_teacher_workflow_proposal,
    submit_teacher_workflow_proposal,
)
from modules.oa import oa_bp, schedule_actions
from modules.oa.external_api import (
    external_error,
    external_success,
    integration_api_required,
    resolve_external_actor,
)
from modules.oa.integration_services import (
    actor_supported_for_openclaw,
    build_openclaw_summary,
    list_openclaw_schedules,
    list_openclaw_work_items,
)
from modules.oa.models import CourseSchedule
from modules.oa.reminder_services import (
    ack_openclaw_reminders,
    list_openclaw_reminders,
    record_schedule_action_reminders,
)


def _resolve_openclaw_actor(provider, external_user_id):
    actor, error = resolve_external_actor(provider, external_user_id)
    if error:
        return None, error
    if not actor_supported_for_openclaw(actor):
        return None, external_error(
            'Current phase only supports internal admin / teacher actors',
            status=403,
            code='unsupported_actor',
        )
    return actor, None


def _parse_optional_date_arg(name):
    raw_value = (request.args.get(name) or '').strip()
    if not raw_value:
        return None, None
    try:
        return date.fromisoformat(raw_value), None
    except ValueError:
        return None, external_error(
            f'{name} must use YYYY-MM-DD',
            status=400,
            code='invalid_date',
        )


def _merge_result_payload(result):
    payload = result.get('data')
    extras = {
        key: value
        for key, value in result.items()
        if key not in {'success', 'status_code', 'error', 'message', 'data'}
    }
    if payload is None:
        payload = {}
    elif not isinstance(payload, dict):
        payload = {'result': payload}
    if extras:
        payload.update(extras)
    return payload or None


def _command_response(result, *, request_id=None, replayed=False):
    payload = _merge_result_payload(result)
    if isinstance(payload, dict):
        payload['integration_meta'] = {
            'request_id': request_id,
            'replayed': bool(replayed),
        }

    if result.get('success'):
        return external_success(
            payload,
            message=result.get('message'),
            status=result.get('status_code', 200),
        )

    response_payload = {
        'success': False,
        'error': result.get('error') or 'Integration command failed',
    }
    if result.get('code'):
        response_payload['code'] = result.get('code')
    if payload is not None:
        response_payload['data'] = payload
    return jsonify(response_payload), int(result.get('status_code') or 400)


def _dispatch_feedback_action(actor, payload, *, submit):
    schedule_id = payload.get('schedule_id')
    if not schedule_id:
        return {
            'success': False,
            'status_code': 400,
            'error': 'Missing schedule_id',
            'code': 'missing_schedule_id',
        }

    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return {
            'success': False,
            'status_code': 404,
            'error': 'Schedule not found',
            'code': 'schedule_not_found',
        }

    permission_error = auth_services.get_schedule_feedback_permission_error(actor, schedule)
    if permission_error:
        return {
            'success': False,
            'status_code': 403,
            'error': permission_error,
            'code': 'feedback_forbidden',
        }

    success, message, feedback = auth_services.save_course_feedback(
        schedule,
        actor.id,
        payload,
        submit=submit,
    )
    if not success:
        return {
            'success': False,
            'status_code': 400,
            'error': message,
            'code': 'feedback_invalid',
        }
    return {
        'success': True,
        'status_code': 200,
        'message': message,
        'data': {'feedback': feedback.to_dict() if feedback else None},
    }


def _load_schedule_or_error(schedule_id):
    if not schedule_id:
        return None, {
            'success': False,
            'status_code': 400,
            'error': 'Missing schedule_id',
            'code': 'missing_schedule_id',
        }
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return None, {
            'success': False,
            'status_code': 404,
            'error': 'Schedule not found',
            'code': 'schedule_not_found',
        }
    return schedule, None


def _admin_only(actor, error_message):
    if actor.role != 'admin':
        return {
            'success': False,
            'status_code': 403,
            'error': error_message,
            'code': 'admin_only',
        }
    return None


def _extract_reschedule_payload(payload):
    required_fields = ('date', 'time_start', 'time_end')
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return None, {
            'success': False,
            'status_code': 400,
            'error': f'Missing reschedule fields: {", ".join(missing)}',
            'code': 'missing_reschedule_fields',
        }
    return {
        'date': payload.get('date'),
        'time_start': payload.get('time_start'),
        'time_end': payload.get('time_end'),
        'location': payload.get('location'),
        'notes': payload.get('notes'),
        'delivery_mode': payload.get('delivery_mode'),
        'color_tag': payload.get('color_tag'),
    }, None


def _bound_reassign_preview(schedule):
    before_payload = schedule_actions.build_schedule_preview_payload(schedule)
    return {
        'success': True,
        'status_code': 200,
        'code': 'reassign_teacher_requires_unbound_schedule',
        'data': {
            'before': before_payload,
            'after': before_payload,
            'can_apply': False,
            'block_reason': 'Current Phase 2A only supports unbound legacy schedules',
            'conflict_summary': None,
        },
    }


def _dispatch_schedule_action(action, payload, actor, request_id):
    role_error = _admin_only(actor, 'Schedule actions are admin only in Phase 2A')
    if role_error:
        return role_error

    schedule, error = _load_schedule_or_error(payload.get('schedule_id'))
    if error:
        return error

    before_payload = schedule_actions.build_schedule_preview_payload(schedule)

    if action == 'schedule.quick_shift':
        result = schedule_actions.quick_shift_schedule(
            schedule,
            date_shift_days=payload.get('date_shift_days', 0),
            time_shift_minutes=payload.get('time_shift_minutes', 0),
            allow_admin_override=True,
        )
        if result.get('success'):
            record_schedule_action_reminders(
                schedule,
                actor=actor,
                action_key='schedule.quick_shift.apply',
                before_payload=before_payload,
                source_request_id=request_id,
                extra_payload=(result.get('data') or {}).get('meta'),
            )
        return result

    if action in {'schedule.reschedule.preview', 'schedule.reschedule.apply'}:
        update_payload, error = _extract_reschedule_payload(payload)
        if error:
            return error
        if action.endswith('.preview'):
            return schedule_actions.preview_schedule_update(
                schedule,
                update_payload,
                allow_admin_override=True,
            )
        result = schedule_actions.apply_schedule_update(
            schedule,
            update_payload,
            allow_admin_override=True,
        )
        if result.get('success'):
            record_schedule_action_reminders(
                schedule,
                actor=actor,
                action_key='schedule.reschedule.apply',
                before_payload=before_payload,
                source_request_id=request_id,
            )
        return result

    if action in {'schedule.reassign_teacher.preview', 'schedule.reassign_teacher.apply'}:
        if schedule.enrollment_id:
            if action.endswith('.preview'):
                return _bound_reassign_preview(schedule)
            return {
                'success': False,
                'status_code': 400,
                'error': 'Current Phase 2A only supports unbound legacy schedules',
                'code': 'reassign_teacher_requires_unbound_schedule',
            }
        if action.endswith('.preview'):
            return schedule_actions.preview_schedule_reassign_teacher(
                schedule,
                payload,
                allow_admin_override=True,
            )
        result = schedule_actions.apply_schedule_reassign_teacher(
            schedule,
            payload,
            allow_admin_override=True,
        )
        if result.get('success'):
            record_schedule_action_reminders(
                schedule,
                actor=actor,
                action_key='schedule.reassign_teacher.apply',
                before_payload=before_payload,
                source_request_id=request_id,
            )
        return result

    return {
        'success': False,
        'status_code': 400,
        'error': f'Unsupported action: {action}',
        'code': 'unsupported_action',
    }


def _dispatch_command(action, payload, actor, request_id):
    if action == 'enrollment.manual_plan.save':
        role_error = _admin_only(actor, 'Manual planning is admin only')
        if role_error:
            return role_error
        enrollment_id = payload.get('enrollment_id')
        session_dates = payload.get('session_dates') or []
        if not enrollment_id:
            return {
                'success': False,
                'status_code': 400,
                'error': 'Missing enrollment_id',
                'code': 'missing_enrollment_id',
            }
        return auth_services.save_manual_enrollment_plan(
            enrollment_id,
            session_dates,
            force_save=bool(payload.get('force_save')),
        )

    if action == 'workflow.admin_send_to_student':
        role_error = _admin_only(actor, 'Workflow admin send is admin only')
        if role_error:
            return role_error
        todo_id = payload.get('todo_id')
        todo = get_workflow_todo(todo_id)
        if not todo:
            return {
                'success': False,
                'status_code': 404,
                'error': 'Workflow todo not found',
                'code': 'workflow_todo_not_found',
            }
        return admin_send_workflow_to_student(
            todo,
            actor,
            session_dates=payload.get('session_dates'),
            note=payload.get('note', ''),
            force_save=bool(payload.get('force_save')),
        )

    if action in {'workflow.teacher_proposal.preview', 'workflow.teacher_proposal.submit'}:
        todo_id = payload.get('todo_id')
        todo = get_workflow_todo(todo_id)
        if not todo:
            return {
                'success': False,
                'status_code': 404,
                'error': 'Workflow todo not found',
                'code': 'workflow_todo_not_found',
            }
        session_dates = payload.get('session_dates') or []
        if action.endswith('.preview'):
            return preview_teacher_workflow_proposal(todo, actor, session_dates)
        return submit_teacher_workflow_proposal(
            todo,
            actor,
            session_dates,
            note=payload.get('note', ''),
        )

    if action == 'feedback.save':
        return _dispatch_feedback_action(actor, payload, submit=False)

    if action == 'feedback.submit':
        return _dispatch_feedback_action(actor, payload, submit=True)

    if action in {'leave.approve', 'leave.reject'}:
        leave_request_id = payload.get('leave_request_id') or payload.get('request_id')
        leave_request = db.session.get(LeaveRequest, leave_request_id)
        return auth_services.process_leave_request_decision(
            leave_request,
            actor,
            approve=action == 'leave.approve',
            decision_comment=payload.get('comment'),
        )

    if action.startswith('schedule.'):
        return _dispatch_schedule_action(action, payload, actor, request_id)

    return {
        'success': False,
        'status_code': 400,
        'error': f'Unsupported action: {action}',
        'code': 'unsupported_action',
    }


def _load_existing_action_log(request_id):
    return IntegrationActionLog.query.filter_by(request_id=request_id).first()


def _start_action_log(provider, actor, request_id, action, payload):
    log = IntegrationActionLog(
        request_id=request_id,
        client_name='openclaw',
        provider=(provider or '').strip().lower(),
        actor_user_id=actor.id,
        action=action,
        status='processing',
    )
    log.set_payload_data(payload)
    db.session.add(log)
    db.session.commit()
    return log


def _finalize_action_log(provider, actor, request_id, action, payload, result):
    log = _load_existing_action_log(request_id)
    if not log:
        log = IntegrationActionLog(
            request_id=request_id,
            client_name='openclaw',
            provider=(provider or '').strip().lower(),
            actor_user_id=actor.id,
            action=action,
        )
        log.set_payload_data(payload)
        db.session.add(log)
    log.status = 'succeeded' if result.get('success') else 'failed'
    log.error_message = result.get('error')
    log.set_result_data(result)
    db.session.commit()
    return log


def _execute_idempotent_integration_action(*, provider, actor, request_id, action, payload, executor):
    existing = _load_existing_action_log(request_id)
    if existing:
        existing_result = existing.get_result_data()
        if not existing_result:
            return None, external_error(
                'Request is still processing',
                status=409,
                code='request_in_progress',
            )
        return _command_response(existing_result, request_id=request_id, replayed=True), None

    _start_action_log(provider, actor, request_id, action, payload)
    try:
        result = executor()
    except Exception as exc:
        db.session.rollback()
        result = {
            'success': False,
            'status_code': 500,
            'error': f'Integration command failed: {exc}',
            'code': 'integration_command_failed',
        }

    _finalize_action_log(provider, actor, request_id, action, payload, result)
    return _command_response(result, request_id=request_id, replayed=False), None


@oa_bp.route('/api/integration/openclaw/me/summary', methods=['GET'])
@integration_api_required
def openclaw_me_summary():
    actor, error = _resolve_openclaw_actor(
        request.args.get('provider'),
        request.args.get('external_user_id'),
    )
    if error:
        return error
    return external_success(build_openclaw_summary(actor))


@oa_bp.route('/api/integration/openclaw/me/schedules', methods=['GET'])
@integration_api_required
def openclaw_me_schedules():
    actor, error = _resolve_openclaw_actor(
        request.args.get('provider'),
        request.args.get('external_user_id'),
    )
    if error:
        return error

    start, error = _parse_optional_date_arg('start')
    if error:
        return error
    end, error = _parse_optional_date_arg('end')
    if error:
        return error

    items = list_openclaw_schedules(actor, start=start, end=end)
    return external_success({
        'actor': actor.to_dict(),
        'items': items,
        'total': len(items),
    })


@oa_bp.route('/api/integration/openclaw/me/work-items', methods=['GET'])
@integration_api_required
def openclaw_me_work_items():
    actor, error = _resolve_openclaw_actor(
        request.args.get('provider'),
        request.args.get('external_user_id'),
    )
    if error:
        return error
    return external_success(list_openclaw_work_items(actor))


@oa_bp.route('/api/integration/openclaw/reminders', methods=['GET'])
@integration_api_required
def openclaw_reminders():
    provider = request.args.get('provider')
    external_user_id = request.args.get('external_user_id')
    actor, error = _resolve_openclaw_actor(provider, external_user_id)
    if error:
        return error

    status = (request.args.get('status') or 'pending').strip().lower()
    if status not in {'pending', 'acked'}:
        return external_error(
            'status only supports pending or acked',
            status=400,
            code='invalid_status',
        )

    limit = request.args.get('limit', type=int) or 20
    cursor = request.args.get('cursor')
    payload = list_openclaw_reminders(
        actor,
        external_user_id,
        status=status,
        limit=max(1, min(limit, 100)),
        cursor=cursor,
    )
    return external_success(payload)


@oa_bp.route('/api/integration/openclaw/reminders/ack', methods=['POST'])
@integration_api_required
def openclaw_ack_reminders():
    data = request.get_json(silent=True) or {}
    provider = data.get('provider')
    external_user_id = data.get('external_user_id')
    actor, error = _resolve_openclaw_actor(provider, external_user_id)
    if error:
        return error

    request_id = (data.get('request_id') or '').strip()
    event_ids = data.get('event_ids') or []
    if not request_id:
        return external_error('Missing request_id', status=400, code='missing_request_id')
    if not isinstance(event_ids, list):
        return external_error('event_ids must be an array', status=400, code='invalid_event_ids')

    response, error_response = _execute_idempotent_integration_action(
        provider=provider,
        actor=actor,
        request_id=request_id,
        action='reminders.ack',
        payload={'event_ids': event_ids},
        executor=lambda: {
            'success': True,
            'status_code': 200,
            'data': ack_openclaw_reminders(actor, external_user_id, event_ids),
        },
    )
    return error_response or response


@oa_bp.route('/api/integration/openclaw/command', methods=['POST'])
@integration_api_required
def openclaw_command():
    data = request.get_json(silent=True) or {}
    actor, error = _resolve_openclaw_actor(
        data.get('provider'),
        data.get('external_user_id'),
    )
    if error:
        return error

    request_id = (data.get('request_id') or '').strip()
    action = (data.get('action') or '').strip()
    payload = data.get('payload') or {}
    if not request_id:
        return external_error('Missing request_id', status=400, code='missing_request_id')
    if not action:
        return external_error('Missing action', status=400, code='missing_action')
    if not isinstance(payload, dict):
        return external_error('payload must be an object', status=400, code='invalid_payload')

    response, error_response = _execute_idempotent_integration_action(
        provider=data.get('provider'),
        actor=actor,
        request_id=request_id,
        action=action,
        payload=payload,
        executor=lambda: _dispatch_command(action, payload, actor, request_id),
    )
    return error_response or response
