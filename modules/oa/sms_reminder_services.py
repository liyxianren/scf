"""SMS reminder services for schedule starting-soon notifications."""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote, urlsplit

import requests
from flask import current_app

from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import ReminderDelivery, ReminderEvent
from modules.oa.models import CourseSchedule
from modules.oa.services import delivery_mode_label, normalize_delivery_mode


SMS_CHANNEL = 'aliyun_sms'
SMS_EVENT_TYPE = 'schedule.starting_soon.sms'
SMS_EVENT_KEY_PREFIX = 'schedule.starting_soon.2h'
ALIYUN_API_VERSION = '2017-05-25'
ALIYUN_SIGNATURE_ALGORITHM = 'ACS3-HMAC-SHA256'
DELIVERY_STATUS_SUBMITTED = 'submitted'
DELIVERY_STATUS_DELIVERED = 'delivered'
DELIVERY_STATUS_FAILED = 'failed'


class AliyunSmsError(RuntimeError):
    def __init__(self, message, *, response_data=None):
        super().__init__(message)
        self.response_data = response_data or {}


def _parse_time_value(time_str):
    hour, minute = str(time_str or '').split(':', 1)
    return int(hour), int(minute)


def _schedule_start_at(schedule):
    hour, minute = _parse_time_value(schedule.time_start)
    return datetime.combine(schedule.date, datetime.min.time()).replace(hour=hour, minute=minute)


def _schedule_end_at(schedule):
    hour, minute = _parse_time_value(schedule.time_end)
    return datetime.combine(schedule.date, datetime.min.time()).replace(hour=hour, minute=minute)


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def _normalize_phone(phone):
    return str(phone or '').strip()


def _delivery_template_kind(schedule):
    mode = normalize_delivery_mode(schedule.delivery_mode, allow_unknown=True)
    if mode == 'online':
        return 'online'
    if mode == 'offline':
        return 'offline'
    return None


def _schedule_sms_event_key(schedule_id):
    return f'{SMS_EVENT_KEY_PREFIX}:{schedule_id}'


def _build_schedule_summary_line(schedule):
    return (
        f'{schedule.course_name or "课程"} '
        f'{schedule.date.isoformat()} {schedule.time_start}-{schedule.time_end}'
    )


def _resolve_sms_target(schedule):
    enrollment = schedule.enrollment
    profile = enrollment.student_profile if enrollment else None
    phone = _normalize_phone(profile.phone if profile else '')
    if not enrollment:
        return None, 'missing_enrollment'
    if not profile:
        return None, 'missing_student_profile'
    if not phone:
        return None, 'missing_phone'
    if not profile.user_id:
        return None, 'missing_student_user'
    return {
        'enrollment': enrollment,
        'profile': profile,
        'phone': phone,
        'target_user_id': profile.user_id,
        'target_role': 'student',
    }, None


def _build_template_params(schedule, target):
    meeting_join_url = (schedule.meeting_join_url or '').strip()
    return {
        'student_name': target['enrollment'].student_name or target['profile'].name or '',
        'course_name': schedule.course_name or '',
        'class_date': schedule.date.isoformat() if schedule.date else '',
        'class_time': f'{schedule.time_start}-{schedule.time_end}',
        'teacher_name': schedule.teacher or '',
        'location': schedule.location or '',
        'meeting_notice': meeting_join_url or '会议链接稍后发送',
        'meeting_join_url': meeting_join_url or '会议链接稍后发送',
    }


def build_schedule_sms_context(schedule, *, now=None):
    now = now or auth_services.get_business_now()
    if not schedule or getattr(schedule, 'is_cancelled', False):
        return None, 'cancelled'

    template_kind = _delivery_template_kind(schedule)
    if not template_kind:
        return None, 'unsupported_delivery_mode'

    target, error = _resolve_sms_target(schedule)
    if error:
        return None, error

    lead_minutes = int(current_app.config.get('SMS_REMINDER_LEAD_MINUTES', 120) or 120)
    start_at = _schedule_start_at(schedule)
    due_at = start_at - timedelta(minutes=lead_minutes)
    return {
        'schedule': schedule,
        'target': target,
        'template_kind': template_kind,
        'template_params': _build_template_params(schedule, target),
        'start_at': start_at,
        'end_at': _schedule_end_at(schedule),
        'due_at': due_at,
        'event_key': _schedule_sms_event_key(schedule.id),
        'summary': _build_schedule_summary_line(schedule),
        'delivery_mode_label': delivery_mode_label(schedule.delivery_mode),
        'now': now,
    }, None


def _serialize_sms_event_payload(context):
    schedule = context['schedule']
    target = context['target']
    return {
        'schedule': {
            'id': schedule.id,
            'date': schedule.date.isoformat() if schedule.date else None,
            'time_start': schedule.time_start,
            'time_end': schedule.time_end,
            'course_name': schedule.course_name,
            'teacher': schedule.teacher,
            'location': schedule.location,
            'delivery_mode': schedule.delivery_mode,
            'delivery_mode_label': context['delivery_mode_label'],
            'meeting_status': schedule.meeting_status,
            'meeting_join_url': schedule.meeting_join_url,
        },
        'student': {
            'name': target['enrollment'].student_name or target['profile'].name,
            'phone': target['phone'],
            'user_id': target['target_user_id'],
        },
        'sms': {
            'template_kind': context['template_kind'],
            'template_params': context['template_params'],
        },
    }


def _ensure_sms_event(context):
    event = ReminderEvent.query.filter_by(event_key=context['event_key']).first()
    if not event:
        event = ReminderEvent(
            event_key=context['event_key'],
            event_type=SMS_EVENT_TYPE,
            target_user_id=context['target']['target_user_id'],
            target_role=context['target']['target_role'],
            scope_type='schedule',
            scope_id=context['schedule'].id,
            title='课程开课提醒',
            summary=context['summary'],
            action_key=None,
            status='pending',
            due_at=context['due_at'],
            source_action='schedule.sms.starting_soon',
        )
        db.session.add(event)
    event.title = '课程开课提醒'
    event.summary = context['summary']
    event.status = event.status if event.status in {'submitted', 'delivered'} else 'pending'
    event.due_at = context['due_at']
    event.target_user_id = context['target']['target_user_id']
    event.target_role = context['target']['target_role']
    event.scope_type = 'schedule'
    event.scope_id = context['schedule'].id
    event.source_action = 'schedule.sms.starting_soon'
    event.set_payload_data(_serialize_sms_event_payload(context))
    db.session.flush()
    return event


def _get_sms_delivery(event, phone):
    return ReminderDelivery.query.filter_by(
        event_id=event.id,
        channel=SMS_CHANNEL,
        receiver_external_id=phone,
    ).first()


def _aliyun_percent_encode(value):
    return quote(str(value), safe='-_.~')


def _aliyun_sha256_hex(value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def _aliyun_signed_headers(host, action, body_hash, timestamp, nonce):
    return {
        'host': host,
        'x-acs-action': action,
        'x-acs-content-sha256': body_hash,
        'x-acs-date': timestamp,
        'x-acs-signature-nonce': nonce,
        'x-acs-version': ALIYUN_API_VERSION,
    }


def _aliyun_sign_request(endpoint, action, query_params):
    access_key_id = current_app.config.get('ALIYUN_SMS_ACCESS_KEY_ID', '')
    access_key_secret = current_app.config.get('ALIYUN_SMS_ACCESS_KEY_SECRET', '')
    if not access_key_id or not access_key_secret:
        raise AliyunSmsError('阿里云短信 AccessKey 未配置')

    split = urlsplit(endpoint)
    host = split.netloc
    canonical_uri = split.path or '/'
    body_hash = _aliyun_sha256_hex(b'')
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    nonce = uuid.uuid4().hex

    normalized_params = {
        key: '' if value is None else str(value)
        for key, value in (query_params or {}).items()
    }
    canonical_query_string = '&'.join(
        f'{_aliyun_percent_encode(key)}={_aliyun_percent_encode(value)}'
        for key, value in sorted(normalized_params.items(), key=lambda item: (item[0], item[1]))
    )
    signed_header_map = _aliyun_signed_headers(host, action, body_hash, timestamp, nonce)
    signed_headers = ';'.join(sorted(signed_header_map.keys()))
    canonical_headers = ''.join(
        f'{key}:{signed_header_map[key]}\n'
        for key in sorted(signed_header_map.keys())
    )
    canonical_request = '\n'.join([
        'POST',
        canonical_uri,
        canonical_query_string,
        canonical_headers,
        signed_headers,
        body_hash,
    ])
    string_to_sign = f'{ALIYUN_SIGNATURE_ALGORITHM}\n{_aliyun_sha256_hex(canonical_request)}'
    signature = hmac.new(
        access_key_secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        'Authorization': (
            f'{ALIYUN_SIGNATURE_ALGORITHM} Credential={access_key_id},'
            f'SignedHeaders={signed_headers},Signature={signature}'
        ),
    }
    headers.update({
        'host': host,
        'x-acs-action': action,
        'x-acs-content-sha256': body_hash,
        'x-acs-date': timestamp,
        'x-acs-signature-nonce': nonce,
        'x-acs-version': ALIYUN_API_VERSION,
    })
    return headers, normalized_params


def _aliyun_rpc_request(action, query_params):
    endpoint = current_app.config.get('ALIYUN_SMS_ENDPOINT', 'https://dysmsapi.aliyuncs.com/')
    headers, normalized_params = _aliyun_sign_request(endpoint, action, query_params)
    response = requests.post(
        endpoint,
        params=normalized_params,
        headers=headers,
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get('Code') != 'OK':
        raise AliyunSmsError(
            payload.get('Message') or payload.get('Code') or '阿里云短信请求失败',
            response_data=payload,
        )
    return payload


def send_schedule_sms(context):
    template_kind = context['template_kind']
    template_code = current_app.config.get(
        'ALIYUN_SMS_TEMPLATE_CODE_ONLINE' if template_kind == 'online' else 'ALIYUN_SMS_TEMPLATE_CODE_OFFLINE',
        '',
    )
    sign_name = current_app.config.get('ALIYUN_SMS_SIGN_NAME', '')
    if not sign_name:
        raise AliyunSmsError('阿里云短信签名未配置')
    if not template_code:
        raise AliyunSmsError(f'阿里云短信模板未配置: {template_kind}')

    return _aliyun_rpc_request('SendSms', {
        'PhoneNumbers': context['target']['phone'],
        'SignName': sign_name,
        'TemplateCode': template_code,
        'TemplateParam': json.dumps(context['template_params'], ensure_ascii=False),
        'OutId': context['event_key'],
    })


def _parse_provider_datetime(value):
    normalized = str(value or '').strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace(' ', 'T'))
    except ValueError:
        return None


def query_sms_delivery_status(delivery):
    params = {
        'PhoneNumber': delivery.receiver_external_id,
        'SendDate': (delivery.last_attempt_at or auth_services.get_business_now()).strftime('%Y%m%d'),
        'PageSize': 10,
        'CurrentPage': 1,
    }
    if delivery.provider_message_id:
        params['BizId'] = delivery.provider_message_id
    return _aliyun_rpc_request('QuerySendDetails', params)


def reconcile_recent_sms_deliveries(*, now=None, limit=50):
    now = now or auth_services.get_business_now()
    if not current_app.config.get('ALIYUN_SMS_ENABLED'):
        return {
            'checked': 0,
            'delivered': 0,
            'failed': 0,
            'pending': 0,
            'errors': 0,
        }

    deliveries = ReminderDelivery.query.filter(
        ReminderDelivery.channel == SMS_CHANNEL,
        ReminderDelivery.delivery_status == DELIVERY_STATUS_SUBMITTED,
    ).order_by(ReminderDelivery.last_attempt_at.desc(), ReminderDelivery.id.desc()).limit(limit).all()

    result = {
        'checked': 0,
        'delivered': 0,
        'failed': 0,
        'pending': 0,
        'errors': 0,
    }
    for delivery in deliveries:
        result['checked'] += 1
        try:
            response_data = query_sms_delivery_status(delivery)
        except Exception as exc:
            delivery.error_message = str(exc)
            result['errors'] += 1
            continue

        delivery.set_provider_response_data(response_data)
        details = (((response_data or {}).get('SmsSendDetailDTOs') or {}).get('SmsSendDetailDTO')) or []
        if isinstance(details, dict):
            details = [details]
        if not details:
            result['pending'] += 1
            continue

        latest = details[-1]
        send_status = int(latest.get('SendStatus') or 0)
        receive_date = _parse_provider_datetime(latest.get('ReceiveDate'))
        if send_status == 3:
            delivery.delivery_status = DELIVERY_STATUS_DELIVERED
            delivery.delivered_at = receive_date or now
            delivery.error_message = None
            if delivery.event:
                delivery.event.status = DELIVERY_STATUS_DELIVERED
            result['delivered'] += 1
        elif send_status == 2:
            delivery.delivery_status = DELIVERY_STATUS_FAILED
            delivery.failed_at = now
            delivery.error_message = latest.get('ErrCode') or '短信发送失败'
            if delivery.event:
                delivery.event.status = DELIVERY_STATUS_FAILED
            result['failed'] += 1
        else:
            result['pending'] += 1
    if result['checked']:
        db.session.commit()
    return result


def _iter_candidate_schedules(now):
    lead_minutes = int(current_app.config.get('SMS_REMINDER_LEAD_MINUTES', 120) or 120)
    scan_window_minutes = int(current_app.config.get('SMS_REMINDER_SCAN_WINDOW_MINUTES', 10) or 10)
    latest_start_boundary = now + timedelta(minutes=lead_minutes)
    earliest_start_boundary = latest_start_boundary - timedelta(minutes=scan_window_minutes)

    schedules = CourseSchedule.query.filter(
        CourseSchedule.is_cancelled == False,
        CourseSchedule.date >= earliest_start_boundary.date(),
        CourseSchedule.date <= latest_start_boundary.date(),
    ).order_by(CourseSchedule.date.asc(), CourseSchedule.time_start.asc()).all()
    for schedule in schedules:
        start_at = _schedule_start_at(schedule)
        if start_at <= earliest_start_boundary or start_at > latest_start_boundary:
            continue
        yield schedule


def run_schedule_sms_reminder_job(*, now=None, dry_run=False):
    now = now or auth_services.get_business_now()
    result = {
        'now': _isoformat_or_none(now),
        'dry_run': bool(dry_run),
        'enabled': bool(current_app.config.get('ALIYUN_SMS_ENABLED')),
        'scanned': 0,
        'eligible': 0,
        'sent': 0,
        'skipped': {
            'cancelled': 0,
            'unsupported_delivery_mode': 0,
            'missing_enrollment': 0,
            'missing_student_profile': 0,
            'missing_phone': 0,
            'missing_student_user': 0,
            'existing_delivery': 0,
            'provider_disabled': 0,
        },
        'failed': 0,
        'items': [],
        'reconcile': {
            'checked': 0,
            'delivered': 0,
            'failed': 0,
            'pending': 0,
            'errors': 0,
        },
    }
    if not dry_run:
        result['reconcile'] = reconcile_recent_sms_deliveries(now=now)

    for schedule in _iter_candidate_schedules(now):
        result['scanned'] += 1
        context, error = build_schedule_sms_context(schedule, now=now)
        if error:
            result['skipped'][error] = result['skipped'].get(error, 0) + 1
            continue
        result['eligible'] += 1
        preview_item = {
            'schedule_id': schedule.id,
            'event_key': context['event_key'],
            'phone': context['target']['phone'],
            'template_kind': context['template_kind'],
            'delivery_mode': schedule.delivery_mode,
            'due_at': _isoformat_or_none(context['due_at']),
            'schedule_start_at': _isoformat_or_none(context['start_at']),
            'meeting_join_url': schedule.meeting_join_url,
        }
        if dry_run:
            result['items'].append(preview_item)
            continue

        event = _ensure_sms_event(context)
        delivery = _get_sms_delivery(event, context['target']['phone'])
        if delivery:
            result['skipped']['existing_delivery'] += 1
            result['items'].append({
                **preview_item,
                'delivery_status': delivery.delivery_status,
                'delivery_id': delivery.id,
            })
            continue

        if not current_app.config.get('ALIYUN_SMS_ENABLED'):
            result['skipped']['provider_disabled'] += 1
            result['items'].append(preview_item)
            continue

        delivery = ReminderDelivery(
            event_id=event.id,
            channel=SMS_CHANNEL,
            receiver_external_id=context['target']['phone'],
        )
        db.session.add(delivery)
        try:
            response_data = send_schedule_sms(context)
            delivery.delivery_status = DELIVERY_STATUS_SUBMITTED
            delivery.provider_message_id = response_data.get('BizId')
            delivery.set_provider_response_data(response_data)
            delivery.last_attempt_at = now
            delivery.error_message = None
            event.status = DELIVERY_STATUS_SUBMITTED
            db.session.flush()
            result['sent'] += 1
            result['items'].append({
                **preview_item,
                'delivery_status': delivery.delivery_status,
                'delivery_id': delivery.id,
                'provider_message_id': delivery.provider_message_id,
            })
        except Exception as exc:
            delivery.delivery_status = DELIVERY_STATUS_FAILED
            delivery.last_attempt_at = now
            delivery.failed_at = now
            delivery.error_message = str(exc)
            if isinstance(exc, AliyunSmsError):
                delivery.set_provider_response_data(exc.response_data)
            event.status = DELIVERY_STATUS_FAILED
            db.session.flush()
            result['failed'] += 1
            result['items'].append({
                **preview_item,
                'delivery_status': delivery.delivery_status,
                'error': str(exc),
            })

    if not dry_run:
        db.session.commit()
    return result
