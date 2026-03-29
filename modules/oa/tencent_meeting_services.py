"""Tencent Meeting meeting lifecycle, webhook, material sync, and feedback draft services."""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from Crypto.Cipher import AES
from flask import current_app

from core.ai import get_ai_client
from extensions import db
from modules.auth import services as auth_services
from modules.auth.models import IntegrationActionLog
from modules.oa.models import CourseFeedback, CourseSchedule, ScheduleMeetingMaterial
from modules.oa.services import normalize_delivery_mode


TENCENT_MEETING_PROVIDER = 'tencent_meeting'
TENCENT_MEETING_JOB_HEADER = 'X-Tencent-Meeting-Job-Token'
WEBHOOK_CLIENT_NAME = 'tencent_meeting_webhook'
WEBHOOK_SUCCESS_BODY = 'successfully received callback'


class TencentMeetingError(RuntimeError):
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


def _compact_json(value):
    if value is None:
        return ''
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _utc_timestamp_seconds(value):
    aware = value.replace(tzinfo=auth_services.BUSINESS_TIMEZONE)
    return int(aware.timestamp())


def _safe_iso(value):
    return value.isoformat() if value else None


def _meeting_request_id(prefix, unique_value):
    digest = hashlib.sha1(str(unique_value or '').encode('utf-8')).hexdigest()[:24]
    return f'{prefix}:{digest}'


def _parse_json_fragment(text):
    normalized = str(text or '').strip()
    if not normalized:
        return {}
    if normalized.startswith('```'):
        normalized = normalized.strip('`')
        if normalized.startswith('json'):
            normalized = normalized[4:].strip()
    try:
        data = json.loads(normalized)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_webhook_aes_key(raw_key):
    text = str(raw_key or '').strip()
    if not text:
        return None
    raw_bytes = text.encode('utf-8')
    if len(raw_bytes) in {16, 24, 32}:
        return raw_bytes
    padded = text + ('=' * ((4 - len(text) % 4) % 4))
    decoded = base64.b64decode(padded)
    if len(decoded) not in {16, 24, 32}:
        raise TencentMeetingError('Webhook AES key 长度无效，需为 16/24/32 字节')
    return decoded


def _pkcs7_unpad(data):
    if not data:
        return data
    padding = data[-1]
    if padding < 1 or padding > AES.block_size:
        raise TencentMeetingError('Webhook AES 解密填充无效')
    return data[:-padding]


def _decode_webhook_payload(data_value):
    encoded = str(data_value or '').strip()
    if not encoded:
        raise TencentMeetingError('Webhook data 为空')
    padded = encoded + ('=' * ((4 - len(encoded) % 4) % 4))
    decoded = base64.b64decode(padded)
    aes_key = _normalize_webhook_aes_key(current_app.config.get('TENCENT_MEETING_WEBHOOK_AES_KEY'))
    if aes_key:
        cipher = AES.new(aes_key, AES.MODE_ECB)
        decoded = _pkcs7_unpad(cipher.decrypt(decoded))
    text = decoded.decode('utf-8')
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return text
    return parsed


def _webhook_signature(token, timestamp, nonce, data_value):
    parts = [str(token or ''), str(timestamp or ''), str(nonce or ''), str(data_value or '')]
    parts.sort()
    return hashlib.sha1(''.join(parts).encode('utf-8')).hexdigest()


def validate_tencent_meeting_webhook_signature(*, timestamp, nonce, signature, data_value):
    token = str(current_app.config.get('TENCENT_MEETING_WEBHOOK_TOKEN') or '').strip()
    if not token:
        raise TencentMeetingError('腾讯会议 webhook token 未配置')
    expected = _webhook_signature(token, timestamp, nonce, data_value)
    return hmac.compare_digest(expected, str(signature or '').strip())


class TencentMeetingClient:
    def __init__(self):
        self.api_host = str(current_app.config.get('TENCENT_MEETING_API_HOST') or 'https://api.meeting.qq.com').rstrip('/')
        self.app_id = str(current_app.config.get('TENCENT_MEETING_APP_ID') or '').strip()
        self.sdk_id = str(current_app.config.get('TENCENT_MEETING_SDK_ID') or '').strip()
        self.secret_id = str(current_app.config.get('TENCENT_MEETING_SECRET_ID') or '').strip()
        self.secret_key = str(current_app.config.get('TENCENT_MEETING_SECRET_KEY') or '').strip()
        self.creator_userid = str(current_app.config.get('TENCENT_MEETING_CREATOR_USERID') or '').strip()
        self.instance_id = int(current_app.config.get('TENCENT_MEETING_CREATOR_INSTANCE_ID') or 1)
        if not self.app_id or not self.secret_id or not self.secret_key or not self.creator_userid:
            raise TencentMeetingError('腾讯会议 API 关键配置缺失')

    def _sign_headers(self, method, uri, body_text):
        timestamp = str(int(datetime.utcnow().timestamp()))
        nonce = str(secrets.randbelow(90000000) + 10000000)
        sign_header_map = {
            'X-TC-Key': self.secret_id,
            'X-TC-Nonce': nonce,
            'X-TC-Timestamp': timestamp,
        }
        header_string = '&'.join(f'{key}={sign_header_map[key]}' for key in sorted(sign_header_map.keys()))
        string_to_sign = '\n'.join([method.upper(), header_string, uri, body_text])
        signature_hex = hmac.new(
            self.secret_key.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        signature = base64.b64encode(signature_hex.encode('utf-8')).decode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'X-TC-Key': self.secret_id,
            'X-TC-Nonce': nonce,
            'X-TC-Timestamp': timestamp,
            'X-TC-Signature': signature,
            'AppId': self.app_id,
            'X-TC-Registered': '1',
        }
        if self.sdk_id:
            headers['SdkId'] = self.sdk_id
        return headers

    def _request(self, method, path, *, params=None, json_body=None, sts_token=None):
        query_params = {
            str(key): '' if value is None else str(value)
            for key, value in (params or {}).items()
        }
        query_string = urlencode(sorted(query_params.items()), doseq=True)
        uri = path if not query_string else f'{path}?{query_string}'
        body_text = '' if json_body is None else _compact_json(json_body)
        headers = self._sign_headers(method, uri, body_text)
        if sts_token:
            headers['STS-Token'] = sts_token
        response = requests.request(
            method.upper(),
            f'{self.api_host}{uri}',
            headers=headers,
            data=body_text if body_text else None,
            timeout=30,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.status_code >= 400:
            message = payload.get('message') or payload.get('msg') or f'腾讯会议 API 调用失败: HTTP {response.status_code}'
            raise TencentMeetingError(message, response_data=payload)
        return payload

    def create_meeting(self, schedule):
        password = ''.join(secrets.choice('0123456789') for _ in range(4))
        response_data = self._request(
            'POST',
            '/v1/meetings',
            json_body={
                'userid': self.creator_userid,
                'instanceid': self.instance_id,
                'subject': schedule.course_name or 'SCF 在线课程',
                'type': 0,
                'start_time': str(_utc_timestamp_seconds(_schedule_start_at(schedule))),
                'end_time': str(_utc_timestamp_seconds(_schedule_end_at(schedule))),
                'password': password,
                'settings': {
                    'time_zone': 'Asia/Shanghai',
                    'allow_in_before_host': True,
                    'enable_host_key': False,
                },
            },
        )
        meeting_info_list = response_data.get('meeting_info_list') or []
        meeting_info = meeting_info_list[0] if meeting_info_list else (response_data.get('meeting_info') or response_data)
        return {
            'meeting_external_id': str(meeting_info.get('meeting_id') or ''),
            'meeting_code': str(meeting_info.get('meeting_code') or ''),
            'meeting_password': str(meeting_info.get('password') or password or ''),
            'meeting_join_url': (
                meeting_info.get('join_url')
                or meeting_info.get('guest_join_url')
                or meeting_info.get('meeting_join_url')
            ),
            'raw': response_data,
        }

    def cancel_meeting(self, meeting_id, *, reason_detail='课次取消或改期'):
        return self._request(
            'POST',
            f'/v1/meetings/{meeting_id}/cancel',
            json_body={
                'userid': self.creator_userid,
                'instanceid': self.instance_id,
                'reason_code': 1,
                'reason_detail': reason_detail,
            },
        )

    def get_smart_minutes(self, record_id):
        return self._request(
            'GET',
            f'/v1/smart/minutes/{record_id}',
            params={
                'operator_id_type': 1,
                'operator_id': self.creator_userid,
                'minute_type': 1,
                'text_type': 1,
            },
        )

    def export_asr(self, meeting_id, *, sts_token=None):
        payload = self._request(
            'GET',
            '/v1/asr/details',
            params={
                'operator_id_type': 1,
                'operator_id': self.creator_userid,
                'meeting_id': meeting_id,
                'file_type': 0,
            },
            sts_token=sts_token,
        )
        transcript_text = None
        download_urls = payload.get('download_url') or []
        if download_urls:
            file_response = requests.get(download_urls[0], timeout=30)
            file_response.raise_for_status()
            transcript_text = file_response.text
        return {
            'transcript_text': transcript_text,
            'download_url': download_urls,
            'raw': payload,
        }


def get_tencent_meeting_client():
    if not bool(current_app.config.get('TENCENT_MEETING_ENABLED')):
        raise TencentMeetingError('腾讯会议集成未启用')
    return TencentMeetingClient()


def _extract_schedule_meeting_state(schedule):
    return {
        'delivery_mode': normalize_delivery_mode(getattr(schedule, 'delivery_mode', None), allow_unknown=True),
        'date': getattr(schedule, 'date', None),
        'time_start': getattr(schedule, 'time_start', None),
        'time_end': getattr(schedule, 'time_end', None),
        'meeting_status': getattr(schedule, 'meeting_status', None),
        'meeting_provider': getattr(schedule, 'meeting_provider', None),
        'meeting_join_url': getattr(schedule, 'meeting_join_url', None),
        'meeting_external_id': getattr(schedule, 'meeting_external_id', None),
        'meeting_code': getattr(schedule, 'meeting_code', None),
        'meeting_password': getattr(schedule, 'meeting_password', None),
    }


def _clear_schedule_meeting_fields(schedule, *, status='not_required', keep_external=False):
    schedule.meeting_provider = None if status == 'not_required' else TENCENT_MEETING_PROVIDER
    schedule.meeting_status = status
    schedule.meeting_join_url = None
    if not keep_external:
        schedule.meeting_external_id = None
        schedule.meeting_code = None
        schedule.meeting_password = None
        schedule.meeting_created_at = None
    if status in {'cancelled', 'ended'}:
        schedule.meeting_ended_at = auth_services.get_business_now()
    elif status == 'not_required':
        schedule.meeting_ended_at = None


def _reset_schedule_meeting_pending(schedule):
    schedule.meeting_provider = TENCENT_MEETING_PROVIDER
    schedule.meeting_status = 'pending'
    schedule.meeting_join_url = None
    schedule.meeting_external_id = None
    schedule.meeting_code = None
    schedule.meeting_password = None
    schedule.meeting_created_at = None
    schedule.meeting_ended_at = None


def _schedule_requires_meeting_recreate(previous_state, schedule):
    return (
        previous_state.get('meeting_external_id')
        and not getattr(schedule, 'is_cancelled', False)
        and previous_state.get('delivery_mode') == 'online'
        and normalize_delivery_mode(schedule.delivery_mode, allow_unknown=True) == 'online'
        and (
            previous_state.get('date') != schedule.date
            or previous_state.get('time_start') != schedule.time_start
            or previous_state.get('time_end') != schedule.time_end
        )
        and previous_state.get('meeting_status') not in {'ended', 'cancelled'}
    )


def sync_schedule_meeting_after_update(schedule, *, previous_state):
    previous_mode = previous_state.get('delivery_mode')
    next_mode = normalize_delivery_mode(schedule.delivery_mode, allow_unknown=True)

    if previous_mode != 'online' and next_mode == 'online':
        if not schedule.meeting_external_id:
            _reset_schedule_meeting_pending(schedule)
        return {'action': 'pending_create'}

    if previous_mode == 'online' and next_mode != 'online':
        if previous_state.get('meeting_external_id') and previous_state.get('meeting_status') not in {'ended', 'cancelled'}:
            try:
                get_tencent_meeting_client().cancel_meeting(
                    previous_state.get('meeting_external_id'),
                    reason_detail='课次改为线下或不再需要线上会议',
                )
            except Exception as exc:
                schedule.meeting_provider = TENCENT_MEETING_PROVIDER
                schedule.meeting_status = 'failed'
                return {'action': 'cancel_failed', 'error': str(exc)}
        _clear_schedule_meeting_fields(schedule, status='not_required')
        return {'action': 'cleared'}

    if next_mode != 'online':
        return {'action': 'not_required'}

    if _schedule_requires_meeting_recreate(previous_state, schedule):
        try:
            get_tencent_meeting_client().cancel_meeting(
                previous_state.get('meeting_external_id'),
                reason_detail='课次时间调整，原会议已作废',
            )
        except Exception as exc:
            schedule.meeting_provider = TENCENT_MEETING_PROVIDER
            schedule.meeting_status = 'failed'
            return {'action': 'recreate_cancel_failed', 'error': str(exc)}
        _reset_schedule_meeting_pending(schedule)
        return {'action': 'recreate_pending'}

    if schedule.meeting_status in {None, '', 'not_required', 'cancelled'} and not schedule.meeting_external_id:
        _reset_schedule_meeting_pending(schedule)
        return {'action': 'normalize_pending'}

    return {'action': 'unchanged'}


def sync_schedule_meeting_after_cancel(schedule, *, cancel_reason=''):
    if normalize_delivery_mode(schedule.delivery_mode, allow_unknown=True) != 'online':
        schedule.meeting_status = 'not_required'
        return {'action': 'not_required'}
    if schedule.meeting_external_id and schedule.meeting_status not in {'cancelled', 'ended'}:
        try:
            get_tencent_meeting_client().cancel_meeting(
                schedule.meeting_external_id,
                reason_detail=cancel_reason or '课次已取消',
            )
            schedule.meeting_status = 'cancelled'
            schedule.meeting_join_url = None
            schedule.meeting_ended_at = auth_services.get_business_now()
            return {'action': 'cancelled'}
        except Exception as exc:
            schedule.meeting_status = 'failed'
            return {'action': 'cancel_failed', 'error': str(exc)}
    schedule.meeting_status = 'cancelled'
    schedule.meeting_ended_at = auth_services.get_business_now()
    return {'action': 'cancelled_without_external'}


def _schedule_meeting_due_at(schedule, *, lead_minutes=None):
    lead_minutes = int(
        lead_minutes
        if lead_minutes is not None
        else (current_app.config.get('TENCENT_MEETING_CREATE_LEAD_MINUTES') or 120)
    )
    return _schedule_start_at(schedule) - timedelta(minutes=lead_minutes)


def _schedule_in_create_window(schedule, now):
    due_at = _schedule_meeting_due_at(schedule)
    window_minutes = int(current_app.config.get('TENCENT_MEETING_CREATE_WINDOW_MINUTES') or 10)
    return due_at <= now < due_at + timedelta(minutes=window_minutes)


def _serialize_schedule_summary(schedule):
    return {
        'schedule_id': schedule.id,
        'date': schedule.date.isoformat() if schedule.date else None,
        'time_start': schedule.time_start,
        'time_end': schedule.time_end,
        'course_name': schedule.course_name,
        'teacher': schedule.teacher,
        'delivery_mode': schedule.delivery_mode,
        'meeting_status': schedule.meeting_status,
        'meeting_external_id': schedule.meeting_external_id,
    }


def _ensure_meeting_material(schedule):
    material = getattr(schedule, 'meeting_material', None)
    if material:
        if schedule.meeting_external_id and material.meeting_external_id != schedule.meeting_external_id:
            material.meeting_external_id = schedule.meeting_external_id
        return material
    material = ScheduleMeetingMaterial(
        schedule_id=schedule.id,
        meeting_external_id=schedule.meeting_external_id,
    )
    db.session.add(material)
    db.session.flush()
    return material


def _merge_material_raw_payload(material, event_name, event_payload):
    raw_payload = material.get_raw_payload_data()
    events = raw_payload.get('events') or {}
    events[event_name] = event_payload
    raw_payload['events'] = events
    material.set_raw_payload_data(raw_payload)


def _extract_record_id_from_payload(payload):
    if not isinstance(payload, dict):
        return None
    payload_items = payload.get('payload') or []
    for item in payload_items:
        if not isinstance(item, dict):
            continue
        if item.get('record_id'):
            return str(item.get('record_id'))
        for recording_file in item.get('recording_files') or []:
            record_file_id = recording_file.get('record_file_id') or recording_file.get('record_id')
            if record_file_id:
                return str(record_file_id)
    return None


def _material_source_type(material):
    if material and material.minutes_text:
        return 'minutes'
    if material and material.transcript_text:
        return 'transcript'
    return None


def _feedback_ai_provider():
    return str(current_app.config.get('COURSE_FEEDBACK_AI_PROVIDER') or 'zhipu').strip().lower()


def _iter_due_online_schedules(now):
    lead_minutes = int(current_app.config.get('TENCENT_MEETING_CREATE_LEAD_MINUTES') or 120)
    window_minutes = int(current_app.config.get('TENCENT_MEETING_CREATE_WINDOW_MINUTES') or 10)
    start_date = now.date()
    end_date = (now + timedelta(minutes=lead_minutes + window_minutes)).date()
    schedules = CourseSchedule.query.filter(
        CourseSchedule.delivery_mode == 'online',
        CourseSchedule.is_cancelled == False,
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date,
    ).order_by(CourseSchedule.date, CourseSchedule.time_start, CourseSchedule.id).all()
    for schedule in schedules:
        if _schedule_in_create_window(schedule, now):
            yield schedule


def run_due_meeting_creation_job(*, now=None, dry_run=False):
    now = now or auth_services.get_business_now()
    result = {
        'dry_run': bool(dry_run),
        'now': _safe_iso(now),
        'eligible': 0,
        'created': 0,
        'failed': 0,
        'skipped': {
            'existing_meeting': 0,
            'cancelled': 0,
            'not_online': 0,
        },
        'items': [],
    }
    client = None
    if not dry_run:
        client = get_tencent_meeting_client()

    for schedule in _iter_due_online_schedules(now):
        if getattr(schedule, 'is_cancelled', False):
            result['skipped']['cancelled'] += 1
            continue
        if normalize_delivery_mode(schedule.delivery_mode, allow_unknown=True) != 'online':
            result['skipped']['not_online'] += 1
            continue
        if schedule.meeting_external_id or schedule.meeting_status in {'ready', 'creating', 'ended'}:
            result['skipped']['existing_meeting'] += 1
            continue

        result['eligible'] += 1
        item = {
            'schedule_id': schedule.id,
            'due_at': _safe_iso(_schedule_meeting_due_at(schedule)),
            'schedule': _serialize_schedule_summary(schedule),
        }
        result['items'].append(item)
        if dry_run:
            continue

        schedule.meeting_provider = TENCENT_MEETING_PROVIDER
        schedule.meeting_status = 'creating'
        db.session.flush()
        try:
            created = client.create_meeting(schedule)
            schedule.meeting_provider = TENCENT_MEETING_PROVIDER
            schedule.meeting_status = 'ready'
            schedule.meeting_join_url = created.get('meeting_join_url')
            schedule.meeting_external_id = created.get('meeting_external_id')
            schedule.meeting_code = created.get('meeting_code')
            schedule.meeting_password = created.get('meeting_password')
            schedule.meeting_created_at = now
            schedule.meeting_ended_at = None
            db.session.commit()
            item['meeting'] = {
                'meeting_external_id': schedule.meeting_external_id,
                'meeting_code': schedule.meeting_code,
                'meeting_join_url': schedule.meeting_join_url,
            }
            result['created'] += 1
        except Exception as exc:
            db.session.rollback()
            reloaded = db.session.get(CourseSchedule, schedule.id)
            reloaded.meeting_provider = TENCENT_MEETING_PROVIDER
            reloaded.meeting_status = 'failed'
            db.session.commit()
            item['error'] = str(exc)
            result['failed'] += 1
    return result


def _material_sync_candidates():
    schedules = CourseSchedule.query.filter(
        CourseSchedule.delivery_mode == 'online',
        CourseSchedule.meeting_external_id.isnot(None),
    ).order_by(CourseSchedule.date, CourseSchedule.time_start, CourseSchedule.id).all()
    for schedule in schedules:
        material = getattr(schedule, 'meeting_material', None)
        if material and material.material_status == 'ready':
            continue
        if schedule.meeting_status not in {'ended', 'ready', 'failed'} and not (material and material.record_id):
            continue
        yield schedule


def run_material_sync_job(*, now=None, dry_run=False):
    now = now or auth_services.get_business_now()
    result = {
        'dry_run': bool(dry_run),
        'now': _safe_iso(now),
        'eligible': 0,
        'synced': 0,
        'failed': 0,
        'unavailable': 0,
        'items': [],
    }
    client = None
    if not dry_run:
        client = get_tencent_meeting_client()

    for schedule in _material_sync_candidates():
        material = _ensure_meeting_material(schedule)
        item = {
            'schedule_id': schedule.id,
            'meeting_external_id': schedule.meeting_external_id,
            'record_id': material.record_id,
        }
        result['items'].append(item)
        result['eligible'] += 1
        if dry_run:
            continue

        try:
            if material.record_id:
                minutes_payload = client.get_smart_minutes(material.record_id)
                meeting_minute = minutes_payload.get('meeting_minute') or {}
                minute_text = (meeting_minute.get('minute') or '').strip()
                if minute_text:
                    material.minutes_text = minute_text
                    material.minutes_status = 'ready'
                    material.material_status = 'ready'
                    material.last_synced_at = now
                    item['source_type'] = 'minutes'
                    result['synced'] += 1
                    db.session.commit()
                    continue
                material.minutes_status = 'unavailable'

            asr_payload = client.export_asr(schedule.meeting_external_id)
            transcript_text = (asr_payload.get('transcript_text') or '').strip()
            if transcript_text:
                material.transcript_text = transcript_text
                material.transcript_status = 'ready'
                material.material_status = 'ready'
                item['source_type'] = 'transcript'
                result['synced'] += 1
            else:
                material.transcript_status = 'unavailable'
                material.material_status = 'unavailable'
                result['unavailable'] += 1
            raw_payload = material.get_raw_payload_data()
            raw_payload['asr'] = asr_payload.get('raw') or {}
            material.set_raw_payload_data(raw_payload)
            material.last_synced_at = now
            material.error_message = None
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            reloaded = ScheduleMeetingMaterial.query.filter_by(schedule_id=schedule.id).first()
            if not reloaded:
                reloaded = _ensure_meeting_material(db.session.get(CourseSchedule, schedule.id))
            reloaded.material_status = 'failed'
            reloaded.error_message = str(exc)
            reloaded.last_synced_at = now
            db.session.commit()
            item['error'] = str(exc)
            result['failed'] += 1
    return result


def _build_feedback_ai_prompt(schedule, material):
    source_type = _material_source_type(material) or 'unknown'
    source_text = (material.minutes_text or material.transcript_text or '').strip()
    system_prompt = (
        '你是 SCF 内部课程反馈助手。'
        '请根据会议纪要或转写，生成一段适合老师二次确认的课程内容草稿。'
        '不要编造学生表现、作业或下次重点。'
        '只输出 JSON，格式为 {"content_summary":"...","source_type":"minutes|transcript"}。'
    )
    user_content = _compact_json({
        'schedule': {
            'course_name': schedule.course_name,
            'teacher': schedule.teacher,
            'student': schedule.students,
            'date': schedule.date.isoformat() if schedule.date else None,
            'time_start': schedule.time_start,
            'time_end': schedule.time_end,
            'source_type': source_type,
        },
        'meeting_material': source_text,
    })
    return system_prompt, user_content


def generate_feedback_ai_draft(schedule, material):
    provider = _feedback_ai_provider()
    system_prompt, user_content = _build_feedback_ai_prompt(schedule, material)
    client = get_ai_client(provider)
    raw_response = client.generate_chat(system_prompt, user_content, temperature=0.2)
    payload = _parse_json_fragment(raw_response)
    content_summary = str(payload.get('content_summary') or '').strip()
    if not content_summary and raw_response:
        content_summary = str(raw_response).strip()
    if not content_summary:
        raise TencentMeetingError('AI 未返回课程内容草稿')
    return {
        'content_summary': content_summary,
        'source_type': str(payload.get('source_type') or _material_source_type(material) or 'minutes'),
        'provider': provider,
    }


def _feedback_draft_candidates():
    schedules = CourseSchedule.query.join(
        ScheduleMeetingMaterial,
        ScheduleMeetingMaterial.schedule_id == CourseSchedule.id,
    ).filter(
        ScheduleMeetingMaterial.material_status == 'ready',
        CourseSchedule.teacher_id.isnot(None),
    ).order_by(CourseSchedule.date, CourseSchedule.time_start, CourseSchedule.id).all()
    for schedule in schedules:
        feedback = getattr(schedule, 'feedback', None)
        if feedback and feedback.ai_content_draft and feedback.ai_draft_status == 'ready':
            continue
        yield schedule


def run_feedback_draft_job(*, now=None, dry_run=False):
    now = now or auth_services.get_business_now()
    result = {
        'dry_run': bool(dry_run),
        'now': _safe_iso(now),
        'eligible': 0,
        'generated': 0,
        'failed': 0,
        'items': [],
    }
    for schedule in _feedback_draft_candidates():
        material = getattr(schedule, 'meeting_material', None)
        if not material:
            continue
        result['eligible'] += 1
        item = {
            'schedule_id': schedule.id,
            'meeting_external_id': schedule.meeting_external_id,
            'material_status': material.material_status,
        }
        result['items'].append(item)
        if dry_run:
            continue

        feedback = getattr(schedule, 'feedback', None)
        if not feedback:
            feedback = CourseFeedback(schedule_id=schedule.id, teacher_id=schedule.teacher_id)
            db.session.add(feedback)

        try:
            draft = generate_feedback_ai_draft(schedule, material)
            feedback.ai_content_draft = draft['content_summary']
            feedback.ai_draft_status = 'ready'
            feedback.ai_model_provider = draft['provider']
            feedback.ai_generated_at = now
            feedback.ai_source_type = draft['source_type']
            db.session.commit()
            item['provider'] = draft['provider']
            item['source_type'] = draft['source_type']
            result['generated'] += 1
        except Exception as exc:
            db.session.rollback()
            reloaded = CourseFeedback.query.filter_by(
                schedule_id=schedule.id,
                teacher_id=schedule.teacher_id,
            ).first()
            if not reloaded:
                reloaded = CourseFeedback(schedule_id=schedule.id, teacher_id=schedule.teacher_id)
                db.session.add(reloaded)
            reloaded.ai_draft_status = 'failed'
            reloaded.ai_model_provider = _feedback_ai_provider()
            reloaded.ai_generated_at = now
            reloaded.ai_source_type = _material_source_type(material)
            db.session.commit()
            item['error'] = str(exc)
            result['failed'] += 1
    return result


def _parse_webhook_event_operate_time(item):
    raw_value = (item or {}).get('operate_time')
    if raw_value in (None, ''):
        return None
    try:
        timestamp_ms = int(raw_value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=auth_services.BUSINESS_TIMEZONE).replace(tzinfo=None)


def _start_webhook_action_log(request_id, action, payload):
    log = IntegrationActionLog(
        request_id=request_id,
        client_name=WEBHOOK_CLIENT_NAME,
        provider=TENCENT_MEETING_PROVIDER,
        action=action,
        status='processing',
    )
    log.set_payload_data(payload)
    db.session.add(log)
    db.session.commit()
    return log


def _finalize_webhook_action_log(log, result, *, error_message=None):
    log.status = 'failed' if error_message else 'succeeded'
    log.error_message = error_message
    log.set_result_data(result)
    db.session.commit()
    return log


def _find_schedule_by_meeting_id(meeting_id):
    if not meeting_id:
        return None
    return CourseSchedule.query.filter_by(meeting_external_id=str(meeting_id)).first()


def _handle_meeting_end_event(event_payload):
    affected = []
    for item in event_payload.get('payload') or []:
        meeting_info = item.get('meeting_info') or {}
        schedule = _find_schedule_by_meeting_id(meeting_info.get('meeting_id'))
        if not schedule:
            continue
        if not schedule.is_cancelled:
            schedule.meeting_status = 'ended'
        schedule.meeting_ended_at = _parse_webhook_event_operate_time(item) or auth_services.get_business_now()
        material = _ensure_meeting_material(schedule)
        material.meeting_external_id = schedule.meeting_external_id
        _merge_material_raw_payload(material, 'meeting.end', event_payload)
        affected.append(schedule.id)
    db.session.commit()
    return {'affected_schedule_ids': affected}


def _handle_material_event(event_name, event_payload):
    affected = []
    for item in event_payload.get('payload') or []:
        meeting_info = item.get('meeting_info') or {}
        schedule = _find_schedule_by_meeting_id(meeting_info.get('meeting_id'))
        if not schedule:
            continue
        material = _ensure_meeting_material(schedule)
        material.meeting_external_id = schedule.meeting_external_id
        material.record_id = material.record_id or _extract_record_id_from_payload(event_payload)
        _merge_material_raw_payload(material, event_name, event_payload)
        if event_name == 'smart.transcripts':
            material.transcript_status = 'pending'
        affected.append(schedule.id)
    db.session.commit()
    return {'affected_schedule_ids': affected}


def process_tencent_meeting_webhook(event_payload):
    event_name = str(event_payload.get('event') or '').strip()
    trace_id = event_payload.get('trace_id') or event_payload.get('unique_sequence') or event_name
    request_id = _meeting_request_id(f'tm-webhook:{event_name}', trace_id)
    existing = IntegrationActionLog.query.filter_by(request_id=request_id).first()
    if existing and existing.status == 'succeeded':
        return {'replayed': True, 'request_id': request_id, 'result': existing.get_result_data()}
    if not existing:
        existing = _start_webhook_action_log(request_id, f'webhook.{event_name}', event_payload)

    try:
        if event_name == 'meeting.end':
            result = _handle_meeting_end_event(event_payload)
        elif event_name.startswith('smart.') or 'minute' in event_name:
            result = _handle_material_event(event_name, event_payload)
        else:
            result = {'ignored': True, 'event': event_name}
        _finalize_webhook_action_log(existing, result)
        return {'replayed': False, 'request_id': request_id, 'result': result}
    except Exception as exc:
        db.session.rollback()
        existing = IntegrationActionLog.query.filter_by(request_id=request_id).first()
        if existing:
            _finalize_webhook_action_log(existing, {'event': event_name}, error_message=str(exc))
        raise
