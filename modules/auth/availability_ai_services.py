import re
from datetime import date, datetime, timedelta

import requests
from flask import current_app, has_app_context


DAY_NAME_MAP = {
    '一': 0,
    '二': 1,
    '三': 2,
    '四': 3,
    '五': 4,
    '六': 5,
    '日': 6,
    '天': 6,
}

DEFAULT_PERIODS = {
    '上午': ('08:00', '12:00'),
    '早上': ('08:00', '12:00'),
    '中午': ('11:00', '14:00'),
    '下午': ('13:00', '18:00'),
    '傍晚': ('17:00', '19:00'),
    '晚上': ('18:00', '21:00'),
    '晚自习': ('18:00', '21:00'),
    '全天': ('09:00', '21:00'),
}

WEEKDAY_PATTERN = re.compile(r'周([一二三四五六日天])')
TIME_RANGE_PATTERN = re.compile(
    r'(?P<start_hour>\d{1,2})(?:[:：](?P<start_minute>\d{2}))?\s*(?:-|到|至)\s*'
    r'(?P<end_hour>\d{1,2})(?:[:：](?P<end_minute>\d{2}))?'
)
AFTER_TIME_PATTERN = re.compile(r'(?P<hour>\d{1,2})(?:[:：](?P<minute>\d{2}))?\s*点?后')
ISO_DATE_PATTERN = re.compile(r'20\d{2}-\d{2}-\d{2}')
CN_DATE_PATTERN = re.compile(r'(?P<month>\d{1,2})月(?P<day>\d{1,2})日')
IMAGE_EVIDENCE_TYPES = {'image_url', 'image', 'image_data_url', 'image_base64'}


def _normalize_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _normalize_time(hour, minute='00'):
    return f'{int(hour):02d}:{int(minute or 0):02d}'


def _dedupe_weekly_slots(slots):
    seen = set()
    deduped = []
    for slot in slots:
        key = (slot['day'], slot['start'], slot['end'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(slot)
    return sorted(deduped, key=lambda item: (item['day'], item['start'], item['end']))


def _normalize_evidence_items(evidence_items):
    normalized = []
    for item in evidence_items or []:
        if isinstance(item, dict):
            content = _normalize_text(item.get('content') or item.get('text'))
            source_type = _normalize_text(item.get('type') or 'text') or 'text'
        else:
            content = _normalize_text(item)
            source_type = 'text'
        if not content:
            continue
        normalized.append({
            'type': source_type,
            'content': content,
        })
    return normalized


def _doubao_vision_config():
    if not has_app_context():
        return {}
    return {
        'enabled': bool(
            current_app.config.get('DOUBAO_VISION_ENABLED')
            or current_app.config.get('DOUBAO_VISION_API_KEY')
        ),
        'api_key': str(current_app.config.get('DOUBAO_VISION_API_KEY') or '').strip(),
        'model': str(current_app.config.get('DOUBAO_VISION_MODEL') or '').strip(),
        'url': str(current_app.config.get('DOUBAO_VISION_RESPONSES_URL') or '').strip(),
        'timeout': int(current_app.config.get('DOUBAO_VISION_TIMEOUT_SECONDS') or 20),
    }


def _image_item_to_url(item):
    source_type = str(item.get('type') or '').strip().lower()
    content = str(item.get('content') or item.get('image_url') or '').strip()
    if not content:
        return ''
    if source_type in {'image_url', 'image'}:
        return content
    if source_type == 'image_data_url':
        return content
    if source_type == 'image_base64':
        mime_type = str(item.get('mime_type') or 'image/png').strip() or 'image/png'
        return f'data:{mime_type};base64,{content}'
    return ''


def _extract_text_from_doubao_response(payload):
    if not isinstance(payload, dict):
        return ''
    if isinstance(payload.get('output_text'), str) and payload.get('output_text').strip():
        return payload.get('output_text').strip()

    texts = []
    for output_item in payload.get('output') or []:
        if isinstance(output_item, dict):
            if isinstance(output_item.get('text'), str) and output_item.get('text').strip():
                texts.append(output_item.get('text').strip())
            for content_item in output_item.get('content') or []:
                if not isinstance(content_item, dict):
                    continue
                text = (
                    content_item.get('text')
                    or content_item.get('output_text')
                    or content_item.get('content')
                )
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    if texts:
        return '\n'.join(texts)

    choices = payload.get('choices') or []
    if choices:
        message = choices[0].get('message') if isinstance(choices[0], dict) else None
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get('text'), str) and item.get('text').strip():
                    text_parts.append(item.get('text').strip())
            if text_parts:
                return '\n'.join(text_parts)
    return ''


def extract_text_from_image_evidence(item):
    config = _doubao_vision_config()
    if not config.get('enabled') or not config.get('api_key') or not config.get('model') or not config.get('url'):
        return '', 'doubao_vision_not_configured'

    image_url = _image_item_to_url(item or {})
    if not image_url:
        return '', 'invalid_image_evidence'

    prompt = (
        '请只做图片文字与时间信息提取，不要做排课决策。'
        '输出纯文本，尽量保留原始时间、星期、日期、备注和禁排信息。'
    )
    request_payload = {
        'model': config['model'],
        'input': [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_image',
                        'image_url': image_url,
                    },
                    {
                        'type': 'input_text',
                        'text': prompt,
                    },
                ],
            }
        ],
    }
    try:
        response = requests.post(
            config['url'],
            headers={
                'Authorization': f'Bearer {config["api_key"]}',
                'Content-Type': 'application/json',
            },
            json=request_payload,
            timeout=config['timeout'],
        )
        response.raise_for_status()
        extracted_text = _extract_text_from_doubao_response(response.json())
        return extracted_text.strip(), None if extracted_text.strip() else 'empty_vision_text'
    except requests.RequestException:
        return '', 'doubao_vision_request_failed'
    except ValueError:
        return '', 'doubao_vision_invalid_response'


def resolve_availability_evidence_items(evidence_items):
    resolved = []
    for item in evidence_items or []:
        if isinstance(item, dict):
            source_type = str(item.get('type') or 'text').strip().lower() or 'text'
            content = item.get('content') or item.get('text') or ''
        else:
            source_type = 'text'
            content = item

        if source_type in IMAGE_EVIDENCE_TYPES:
            ocr_text = str((item or {}).get('ocr_text') or '').strip() if isinstance(item, dict) else ''
            if not ocr_text:
                ocr_text, _ = extract_text_from_image_evidence(item if isinstance(item, dict) else {'type': source_type, 'content': content})
            if ocr_text:
                resolved.append({
                    'type': 'image_ocr',
                    'content': ocr_text,
                })
            continue

        if str(content or '').strip():
            resolved.append({
                'type': source_type,
                'content': str(content).strip(),
            })
    return resolved


def _extract_days(segment):
    days = {DAY_NAME_MAP[match] for match in WEEKDAY_PATTERN.findall(segment)}
    if '周末' in segment:
        days.update({5, 6})
    return sorted(days)


def _extract_time_window(segment):
    range_match = TIME_RANGE_PATTERN.search(segment)
    if range_match:
        start = _normalize_time(range_match.group('start_hour'), range_match.group('start_minute') or '00')
        end = _normalize_time(range_match.group('end_hour'), range_match.group('end_minute') or '00')
        if end > start:
            return start, end, 'explicit_range'

    after_match = AFTER_TIME_PATTERN.search(segment)
    if after_match:
        start = _normalize_time(after_match.group('hour'), after_match.group('minute') or '00')
        end = '21:00'
        if end > start:
            return start, end, 'after_time'

    for keyword, window in DEFAULT_PERIODS.items():
        if keyword in segment:
            return window[0], window[1], keyword

    return None, None, None


def _extract_dates(segment, reference_date):
    results = []
    for match in ISO_DATE_PATTERN.findall(segment):
        results.append(match)

    current_year = reference_date.year
    for match in CN_DATE_PATTERN.finditer(segment):
        try:
            parsed = date(current_year, int(match.group('month')), int(match.group('day')))
        except ValueError:
            continue
        if parsed < reference_date - timedelta(days=30):
            try:
                parsed = date(current_year + 1, parsed.month, parsed.day)
            except ValueError:
                continue
        results.append(parsed.isoformat())
    return sorted(dict.fromkeys(results))


def _is_negative_segment(segment):
    negative_keywords = [
        '不行',
        '不能',
        '没空',
        '不方便',
        '不可以',
        '冲突',
        '考试',
        '比赛',
        '晚自习',
        '旅游',
        '旅行',
        '有事',
        '请假',
    ]
    return any(keyword in segment for keyword in negative_keywords)


def _build_segment_slot(day, start, end, source_text):
    return {
        'day': day,
        'start': start,
        'end': end,
        'source_text': source_text,
    }


def parse_availability_intake(
    *,
    input_text='',
    evidence_items=None,
    manual_slots=None,
    manual_excluded_dates=None,
    reference_date=None,
):
    reference_date = reference_date or date.today()
    normalized_evidence = _normalize_evidence_items(evidence_items)
    normalized_input = _normalize_text(input_text)
    source_texts = [normalized_input] if normalized_input else []
    source_texts.extend(item['content'] for item in normalized_evidence)
    combined_text = '\n'.join(source_texts).strip()

    if manual_slots:
        weekly_slots = _dedupe_weekly_slots([
            {
                'day': int(slot.get('day', slot.get('day_of_week'))),
                'start': str(slot.get('start', slot.get('time_start'))).strip(),
                'end': str(slot.get('end', slot.get('time_end'))).strip(),
                'source_text': 'manual',
            }
            for slot in manual_slots
        ])
        excluded_dates = sorted(dict.fromkeys(str(item).strip() for item in (manual_excluded_dates or []) if str(item).strip()))
        confidence = 0.99
        needs_review = False
        source_evidence = ['学生手工确认结构化时段']
        temporary_constraints = []
    else:
        segments = [
            _normalize_text(part)
            for part in re.split(r'[。\n；;]+', combined_text)
            if _normalize_text(part)
        ]
        weekly_slots = []
        excluded_dates = []
        temporary_constraints = []
        confidence = 0.25
        source_evidence = []

        for segment in segments:
            days = _extract_days(segment)
            segment_dates = _extract_dates(segment, reference_date)
            if segment_dates and _is_negative_segment(segment):
                excluded_dates.extend(segment_dates)
                source_evidence.append(segment)
                confidence += 0.1
                continue

            start, end, evidence_tag = _extract_time_window(segment)
            if days and start and end and not _is_negative_segment(segment):
                weekly_slots.extend([
                    _build_segment_slot(day, start, end, segment)
                    for day in days
                ])
                source_evidence.append(segment)
                confidence += 0.25 if evidence_tag == 'explicit_range' else 0.18
                continue

            if _is_negative_segment(segment):
                temporary_constraints.append(segment)
                source_evidence.append(segment)
                confidence += 0.05
                continue

            if days:
                default_start, default_end = DEFAULT_PERIODS['晚上']
                weekly_slots.extend([
                    _build_segment_slot(day, default_start, default_end, segment)
                    for day in days
                ])
                source_evidence.append(segment)
                confidence += 0.12
                continue

        weekly_slots = _dedupe_weekly_slots(weekly_slots)
        excluded_dates = sorted(dict.fromkeys(excluded_dates + [
            str(item).strip()
            for item in (manual_excluded_dates or [])
            if str(item).strip()
        ]))
        if normalized_evidence:
            confidence -= 0.05
        confidence = min(max(confidence, 0.25), 0.95)
        needs_review = confidence < 0.75 or not weekly_slots

    return {
        'raw_input_text': normalized_input,
        'source_evidence_items': normalized_evidence,
        'source_evidence': source_evidence[:6],
        'weekly_slots': [
            {
                'day': slot['day'],
                'start': slot['start'],
                'end': slot['end'],
            }
            for slot in weekly_slots
        ],
        'excluded_dates': excluded_dates,
        'temporary_constraints': temporary_constraints[:6],
        'confidence': round(confidence, 2),
        'needs_review': bool(needs_review),
        'summary': build_availability_intake_summary(
            {
                'weekly_slots': weekly_slots,
                'excluded_dates': excluded_dates,
                'temporary_constraints': temporary_constraints,
            }
        ),
    }


def build_availability_intake_summary(intake):
    intake = intake or {}
    weekly_slots = intake.get('weekly_slots') or []
    excluded_dates = intake.get('excluded_dates') or []
    temporary_constraints = intake.get('temporary_constraints') or []

    parts = []
    if weekly_slots:
        day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        slot_text = '；'.join(
            f'{day_names[item["day"]]} {item["start"]}-{item["end"]}'
            for item in weekly_slots
            if 0 <= int(item.get('day', -1)) <= 6
        )
        if slot_text:
            parts.append(f'可上课：{slot_text}')
    if excluded_dates:
        parts.append(f'禁排日期：{"、".join(excluded_dates[:3])}' + (f' 等 {len(excluded_dates)} 天' if len(excluded_dates) > 3 else ''))
    if temporary_constraints:
        parts.append(f'临时限制：{temporary_constraints[0]}')
    return ' · '.join(parts) or None
