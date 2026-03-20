"""自动排课、删除清理和账号初始化服务。"""
import io
import json
import re
import secrets
import unicodedata
from datetime import datetime, date, timedelta, time, timezone
from itertools import product
from math import ceil
from zoneinfo import ZoneInfo

from sqlalchemy import or_

from extensions import db


FEEDBACK_PREFIX = "[排课反馈]"
SCHEDULE_PREFIX = "[排课方案]"
BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def get_business_now():
    """返回系统当前使用的本地业务时间。"""
    return datetime.now(BUSINESS_TIMEZONE).replace(tzinfo=None)


def serialize_business_datetime(value, *, assume_utc=True):
    """把数据库中的时间值格式化成带业务时区偏移的 ISO 字符串。"""
    if value is None:
        return None

    if value.tzinfo is None:
        source_tz = UTC if assume_utc else BUSINESS_TIMEZONE
        aware_value = value.replace(tzinfo=source_tz)
    else:
        aware_value = value

    return aware_value.astimezone(BUSINESS_TIMEZONE).isoformat()


def get_business_today():
    return get_business_now().date()


def generate_intake_token():
    """生成学生填表链接的 token。"""
    return secrets.token_urlsafe(32)


def _coerce_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'n', 'off'}:
            return False
    return bool(value)


def _serialize_json_field(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _resolve_teacher_user(teacher_id=None, teacher_name=None):
    from modules.auth.models import User
    from modules.oa.services import resolve_schedule_teacher_reference

    if teacher_id:
        teacher = db.session.get(User, teacher_id)
        if not teacher:
            return None, '授课老师不存在'
        return teacher, None

    if teacher_name:
        teacher, _, _, error = resolve_schedule_teacher_reference(teacher_name)
        if error or not teacher:
            return None, error or f'未找到老师: {teacher_name}'
        return teacher, None

    return None, '缺少 teacher_id 或 teacher_name'


def create_enrollment_record(data):
    """创建报名记录并生成 intake 链接。"""
    from modules.auth.models import Enrollment

    student_name = (data.get('student_name') or '').strip()
    course_name = (data.get('course_name') or '').strip()
    teacher_name = (data.get('teacher_name') or data.get('teacher') or '').strip()
    teacher_id = data.get('teacher_id')

    if not student_name:
        return None, None, '缺少必填字段: student_name'
    if not course_name:
        return None, None, '缺少必填字段: course_name'

    teacher, error = _resolve_teacher_user(teacher_id=teacher_id, teacher_name=teacher_name)
    if error:
        return None, None, error

    token_days = data.get('token_ttl_days', 7)
    try:
        token_days = int(token_days)
    except (TypeError, ValueError):
        token_days = 7

    token = generate_intake_token()
    enrollment = Enrollment(
        student_name=student_name,
        course_name=course_name,
        teacher_id=teacher.id,
        total_hours=data.get('total_hours'),
        hours_per_session=data.get('hours_per_session', 2.0),
        sessions_per_week=data.get('sessions_per_week', 1),
        notes=data.get('notes'),
        intake_token=token,
        token_expires_at=get_business_now() + timedelta(days=max(token_days, 1)),
        status='pending_info',
    )
    db.session.add(enrollment)
    db.session.commit()
    return enrollment, f'/auth/intake/{token}', None


def _normalize_username_base(student_name):
    normalized = unicodedata.normalize('NFKC', str(student_name or '').strip())
    normalized = re.sub(r'\s+', '', normalized)
    normalized = ''.join(
        char for char in normalized
        if char.isalnum() or char in {'-', '_', '.'}
    )
    return normalized[:100] or 'student'


def _build_student_username(student_name):
    from modules.auth.models import User

    base_username = _normalize_username_base(student_name)
    username = base_username
    suffix = 2
    while User.query.filter_by(username=username).first():
        suffix_text = str(suffix)
        username = f'{base_username[:100-len(suffix_text)]}{suffix_text}'
        suffix += 1
    return username


def _sync_student_user(user, student_name, phone):
    if not user:
        return
    user.display_name = student_name
    if phone:
        user.phone = phone


def _resolve_or_create_student_account(enrollment, student_name, phone):
    from modules.auth.models import User

    if not enrollment:
        return None, None

    linked_profile = enrollment.student_profile
    linked_user = linked_profile.user if linked_profile and linked_profile.user_id else None

    if linked_user:
        _sync_student_user(linked_user, student_name, phone)
        account_info = {
            'username': linked_user.username,
            'password': None,
            'user_id': linked_user.id,
        }
        return linked_user, account_info

    username = _build_student_username(student_name)
    student_user = User(
        username=username,
        display_name=student_name,
        role='student',
        phone=phone,
    )
    student_user.set_password('scf123')
    db.session.add(student_user)
    db.session.flush()
    if linked_profile and linked_profile.user_id is None:
        linked_profile.user_id = student_user.id
    account_info = {
        'username': username,
        'password': 'scf123',
        'user_id': student_user.id,
    }
    return student_user, account_info


def _apply_student_profile_fields(profile, data, *, preserve_missing=False):
    slots = data.get('available_slots')
    if slots is None and 'available_times' in data:
        slots = data.get('available_times')

    excluded_dates = data.get('excluded_dates')
    if 'name' in data or not preserve_missing:
        profile.name = data.get('name', profile.name)
    if 'grade' in data or not preserve_missing:
        profile.grade = data.get('grade', profile.grade if preserve_missing else None)
    if 'school' in data or not preserve_missing:
        profile.school = data.get('school', profile.school if preserve_missing else None)
    if 'phone' in data or not preserve_missing:
        profile.phone = data.get('phone', profile.phone)
    if 'parent_phone' in data or not preserve_missing:
        profile.parent_phone = data.get('parent_phone', profile.parent_phone if preserve_missing else None)
    if 'has_experience' in data or not preserve_missing:
        profile.has_experience = _coerce_bool(
            data.get('has_experience'),
            default=profile.has_experience if preserve_missing else False,
        )
    if 'experience_detail' in data or not preserve_missing:
        profile.experience_detail = data.get(
            'experience_detail',
            profile.experience_detail if preserve_missing else None,
        )
    if slots is not None:
        profile.available_slots = _serialize_json_field(slots)
    elif not preserve_missing:
        profile.available_slots = None
    if excluded_dates is not None:
        serialized = _serialize_json_field(excluded_dates)
        profile.excluded_dates = None if serialized in (None, '[]', '') else serialized
    elif not preserve_missing:
        profile.excluded_dates = None
    if 'notes' in data or not preserve_missing:
        profile.notes = data.get('notes', profile.notes if preserve_missing else None)


def submit_enrollment_intake(enrollment, data):
    """提交报名对应的学生信息表。"""
    from modules.auth.models import StudentProfile

    if not enrollment:
        return None, '报名记录不存在'
    if enrollment.token_expires_at and enrollment.token_expires_at < get_business_now():
        return None, '链接已过期'
    if enrollment.status != 'pending_info':
        return None, '该报名信息已提交，无需重复填写'

    student_name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    if not student_name:
        return None, '姓名为必填项'
    if not phone:
        return None, '手机号为必填项'

    student_user, account_info = _resolve_or_create_student_account(enrollment, student_name, phone)
    profile = student_user.student_profile if student_user and student_user.student_profile else None
    if not profile:
        profile = StudentProfile(user_id=student_user.id if student_user else None, name=student_name, phone=phone)
        db.session.add(profile)

    _apply_student_profile_fields(profile, data, preserve_missing=True)
    db.session.flush()
    _sync_student_user(student_user, student_name, phone)

    if student_name != enrollment.student_name:
        enrollment.student_name = student_name
    enrollment.student_profile_id = profile.id
    enrollment.status = 'pending_schedule'
    db.session.commit()

    return {
        'account': account_info,
        'profile': profile.to_dict(),
        'enrollment': build_enrollment_payload(enrollment),
    }, None


def update_enrollment_intake(enrollment, data):
    """学生本人或教务修改已提交的 intake 信息，并强制回到待排课。"""
    from modules.auth.models import StudentProfile

    if not enrollment:
        return None, '报名记录不存在'
    if enrollment.status not in {'pending_schedule', 'pending_student_confirm'}:
        return None, '当前状态不允许修改学生信息'

    student_name = (data.get('name') or enrollment.student_name or '').strip()
    phone = (data.get('phone') or '').strip()
    if not student_name:
        return None, '姓名为必填项'
    if not phone:
        return None, '手机号为必填项'

    student_user, account_info = _resolve_or_create_student_account(enrollment, student_name, phone)
    profile = enrollment.student_profile or (student_user.student_profile if student_user else None)
    if not profile:
        profile = StudentProfile(user_id=student_user.id if student_user else None, name=student_name, phone=phone)
        db.session.add(profile)

    _apply_student_profile_fields(profile, data, preserve_missing=True)
    db.session.flush()
    _sync_student_user(student_user, student_name, phone)

    enrollment.student_name = student_name
    enrollment.student_profile_id = profile.id
    enrollment.proposed_slots = None
    enrollment.confirmed_slot = None
    enrollment.status = 'pending_schedule'
    db.session.commit()

    return {
        'account': account_info,
        'profile': profile.to_dict(),
        'enrollment': build_enrollment_payload(enrollment),
    }, None


def save_student_profile_record(data, profile=None):
    """创建或更新学生档案。"""
    from modules.auth.models import Enrollment, StudentProfile, User

    student_name = (data.get('name') or (profile.name if profile else '') or '').strip()
    if not student_name:
        return None, None, '缺少必填字段: name'

    phone = (data.get('phone') or '').strip() or None
    linked_user = None
    account_info = None

    user_id = data.get('user_id')
    username = (data.get('username') or '').strip()
    create_user_if_missing = _coerce_bool(data.get('create_user_if_missing'))

    if user_id:
        linked_user = db.session.get(User, user_id)
        if not linked_user:
            return None, None, '用户不存在'
    elif username:
        linked_user = User.query.filter_by(username=username).first()
        if not linked_user and create_user_if_missing:
            linked_user = User(
                username=username,
                display_name=student_name,
                role='student',
                phone=phone,
            )
            linked_user.set_password(data.get('password') or 'scf123')
            db.session.add(linked_user)
            db.session.flush()
            account_info = {
                'username': linked_user.username,
                'password': data.get('password') or 'scf123',
                'user_id': linked_user.id,
            }

    if profile is None:
        existing_profile = linked_user.student_profile if linked_user and linked_user.student_profile else None
        profile = existing_profile or StudentProfile(user_id=linked_user.id if linked_user else None, name=student_name)
        if existing_profile is None:
            db.session.add(profile)
    elif linked_user and profile.user_id not in (None, linked_user.id):
        return None, None, '该档案已绑定其他用户'

    if linked_user and profile.user_id is None:
        profile.user_id = linked_user.id

    _apply_student_profile_fields(profile, data, preserve_missing=profile.id is not None)
    db.session.flush()

    enrollment_id = data.get('enrollment_id')
    if enrollment_id:
        enrollment = db.session.get(Enrollment, enrollment_id)
        if not enrollment:
            return None, None, '报名记录不存在'
        enrollment.student_profile_id = profile.id
        if student_name:
            enrollment.student_name = student_name

    db.session.commit()
    return profile, account_info, None


def reject_enrollment_schedule(enrollment_id, message_text, actor_user_id=None):
    """外部接口或脚本退回排课方案。"""
    from modules.auth.models import ChatMessage, Enrollment, User
    from modules.auth.workflow_services import ensure_enrollment_replan_workflow

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return False, '报名记录不存在'
    if enrollment.status != 'pending_student_confirm':
        return False, '当前没有待退回的排课方案'

    sender_id = actor_user_id
    if sender_id is None and enrollment.student_profile:
        sender_id = enrollment.student_profile.user_id
    if sender_id is None:
        return False, '无法确定反馈发送人'

    msg = ChatMessage(
        sender_id=sender_id,
        receiver_id=enrollment.teacher_id,
        enrollment_id=enrollment.id,
        content=f'{FEEDBACK_PREFIX}[{enrollment.course_name}] {message_text or "学生对排课方案有疑问，请查看。"}',
        is_read=False,
    )
    db.session.add(msg)
    ensure_enrollment_replan_workflow(
        enrollment,
        rejection_text=message_text,
        actor_user=db.session.get(User, sender_id),
    )
    enrollment.confirmed_slot = None
    enrollment.status = 'pending_schedule'
    db.session.commit()
    return True, '已发送消息给老师'


def _time_to_minutes(t):
    """'14:00' -> 840"""
    h, m = t.split(':')
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes):
    """840 -> '14:00'"""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _compute_overlap(a_start, a_end, b_start, b_end, min_duration_minutes):
    """计算两个时间段的重叠区间，重叠时长必须 >= min_duration_minutes。"""
    start = max(_time_to_minutes(a_start), _time_to_minutes(b_start))
    end = min(_time_to_minutes(a_end), _time_to_minutes(b_end))
    if end - start >= min_duration_minutes:
        return (_minutes_to_time(start), _minutes_to_time(end))
    return None


def _slot_signature(slot):
    return (slot['day_of_week'], slot['time_start'], slot['time_end'])


def _slot_sort_key(slot):
    return (
        slot['day_of_week'],
        _time_to_minutes(slot['time_start']),
        _time_to_minutes(slot['time_end']),
    )


def _first_occurrence_on_or_after(day_of_week, start_date):
    days_ahead = day_of_week - start_date.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return start_date + timedelta(days=days_ahead)


def _get_total_sessions(enrollment):
    if enrollment.total_hours and enrollment.hours_per_session:
        return max(1, int(enrollment.total_hours / enrollment.hours_per_session))
    return 16


def _load_student_excluded_dates(student_profile):
    excluded_set = set()
    if student_profile and student_profile.excluded_dates:
        try:
            excluded_set = set(json.loads(student_profile.excluded_dates) or [])
        except (json.JSONDecodeError, TypeError):
            excluded_set = set()
    return excluded_set


def _build_session_dates(weekly_slots, total_sessions, excluded_set):
    """按周轮转生成具体课次，遇到不可上课日期则跳过并顺延到下周。"""
    if not weekly_slots:
        return [], []

    sorted_slots = sorted(weekly_slots, key=_slot_sort_key)
    today = get_business_today()
    first_dates = [
        _first_occurrence_on_or_after(slot['day_of_week'], today)
        for slot in sorted_slots
    ]

    session_dates = []
    skipped_dates = []
    week_idx = 0
    max_weeks = total_sessions + len(excluded_set) + 52

    while len(session_dates) < total_sessions and week_idx < max_weeks:
        for slot, first_date in zip(sorted_slots, first_dates):
            current_date = first_date + timedelta(weeks=week_idx)
            payload = {
                'date': current_date.isoformat(),
                'day_of_week': slot['day_of_week'],
                'time_start': slot['time_start'],
                'time_end': slot['time_end'],
            }
            if payload['date'] in excluded_set:
                skipped_dates.append(payload)
                continue
            session_dates.append(payload)
            if len(session_dates) >= total_sessions:
                break
        week_idx += 1

    return session_dates, skipped_dates


def _build_plan(weekly_slots, total_sessions, excluded_set):
    """把每周 recurring slots 组装成一个可确认的排课 plan。"""
    deduped = {}
    for slot in weekly_slots:
        key = _slot_signature(slot)
        if key not in deduped or slot.get('score', 0) > deduped[key].get('score', 0):
            deduped[key] = dict(slot)

    ordered_slots = sorted(deduped.values(), key=_slot_sort_key)
    session_dates, skipped_dates = _build_session_dates(ordered_slots, total_sessions, excluded_set)
    date_values = [item['date'] for item in session_dates]
    estimated_weeks = 0
    if date_values:
        first_date = date.fromisoformat(date_values[0])
        last_date = date.fromisoformat(date_values[-1])
        estimated_weeks = ((last_date - first_date).days // 7) + 1

    total_conflicts = sum(len(slot.get('conflicts', [])) for slot in ordered_slots)
    plan_score = sum(slot.get('score', 0) for slot in ordered_slots)
    distinct_days = len({slot['day_of_week'] for slot in ordered_slots})

    return {
        'weekly_slots': ordered_slots,
        'total_sessions': total_sessions,
        'sessions_per_week': len(ordered_slots),
        'estimated_weeks': estimated_weeks,
        'session_dates': session_dates,
        'skipped_dates': skipped_dates,
        'plan_score': plan_score,
        'distinct_days': distinct_days,
        'total_conflicts': total_conflicts,
        'date_start': date_values[0] if date_values else None,
        'date_end': date_values[-1] if date_values else None,
    }


def _apply_session_dates_to_plan(plan, session_dates, skipped_dates):
    date_values = [item['date'] for item in session_dates]
    estimated_weeks = 0
    if date_values:
        first_date = date.fromisoformat(date_values[0])
        last_date = date.fromisoformat(date_values[-1])
        estimated_weeks = ((last_date - first_date).days // 7) + 1

    plan['session_dates'] = session_dates
    plan['skipped_dates'] = skipped_dates
    plan['date_start'] = date_values[0] if date_values else None
    plan['date_end'] = date_values[-1] if date_values else None
    plan['estimated_weeks'] = estimated_weeks
    plan['total_sessions'] = len(session_dates) or plan.get('total_sessions', 0)
    plan['sessions_per_week'] = len(plan.get('weekly_slots', []))
    plan['distinct_days'] = len({slot['day_of_week'] for slot in plan.get('weekly_slots', [])})
    plan['total_conflicts'] = sum(len(slot.get('conflicts', [])) for slot in plan.get('weekly_slots', []))
    plan['plan_score'] = sum(slot.get('score', 0) for slot in plan.get('weekly_slots', []))
    return plan


def _merge_plan_metadata(raw_plan, plan):
    if not isinstance(raw_plan, dict):
        return plan

    preserved_keys = {
        'is_manual',
        'manual_note',
        'manual_warnings',
    }
    for key in preserved_keys:
        if key in raw_plan:
            plan[key] = raw_plan[key]
    return plan


def normalize_plan(raw_plan, enrollment=None):
    """兼容旧单时段结构，统一为新的 multi-slot plan 结构。"""
    if not raw_plan:
        return None
    if not isinstance(raw_plan, dict):
        return raw_plan

    excluded_set = _load_student_excluded_dates(enrollment.student_profile) if enrollment else set()
    total_sessions = _get_total_sessions(enrollment) if enrollment else raw_plan.get('total_sessions', 1)

    if raw_plan.get('weekly_slots'):
        plan = _build_plan(raw_plan.get('weekly_slots', []), total_sessions, excluded_set)
        session_dates = raw_plan.get('session_dates')
        skipped_dates = raw_plan.get('skipped_dates')
        if session_dates is not None:
            plan = _apply_session_dates_to_plan(
                plan,
                session_dates,
                skipped_dates or [],
            )
        return _merge_plan_metadata(raw_plan, plan)

    if all(key in raw_plan for key in ('day_of_week', 'time_start', 'time_end')):
        weekly_slots = [{
            'day_of_week': raw_plan['day_of_week'],
            'time_start': raw_plan['time_start'],
            'time_end': raw_plan['time_end'],
            'score': raw_plan.get('score', 0),
            'is_preferred': raw_plan.get('is_preferred', False),
            'conflicts': raw_plan.get('conflicts', []),
        }]
        plan = _build_plan(weekly_slots, total_sessions, excluded_set)
        if raw_plan.get('dates') is not None:
            session_dates = [{
                'date': item,
                'day_of_week': raw_plan['day_of_week'],
                'time_start': raw_plan['time_start'],
                'time_end': raw_plan['time_end'],
            } for item in raw_plan.get('dates', [])]
            skipped_dates = [{
                'date': item,
                'day_of_week': raw_plan['day_of_week'],
                'time_start': raw_plan['time_start'],
                'time_end': raw_plan['time_end'],
            } for item in raw_plan.get('skipped_dates', [])]
            plan = _apply_session_dates_to_plan(plan, session_dates, skipped_dates)
        return _merge_plan_metadata(raw_plan, plan)

    return raw_plan


def _plan_sort_key(plan):
    return (
        plan['estimated_weeks'] or 999,
        -plan['distinct_days'],
        -plan['plan_score'],
        plan['total_conflicts'],
        tuple(_slot_signature(slot) for slot in plan['weekly_slots']),
    )


def _candidate_sort_key(candidate):
    return (
        -candidate.get('score', 0),
        len(candidate.get('conflicts', [])),
        candidate['day_of_week'],
        _time_to_minutes(candidate['time_start']),
    )


def _extend_single_day_plan(selected_blocks, grouped_candidates, total_sessions):
    """只有单一 weekday 时，允许补一个同日的第二个 recurring block。"""
    if len({block['day_of_week'] for block in selected_blocks}) > 1:
        return selected_blocks

    used = {_slot_signature(block) for block in selected_blocks}
    extras = []
    for blocks in grouped_candidates.values():
        for block in blocks:
            if _slot_signature(block) in used:
                continue
            extras.append(block)

    extras.sort(key=_candidate_sort_key)
    if extras and len(selected_blocks) < total_sessions:
        return sorted(list(selected_blocks) + [extras[0]], key=_slot_sort_key)
    return selected_blocks


def _schedule_start_datetime(schedule):
    start_time = datetime.strptime(schedule.time_start, '%H:%M').time()
    return datetime.combine(schedule.date, start_time)


def _schedule_has_started(schedule, reference=None):
    if not schedule or not schedule.date or not schedule.time_start:
        return False
    reference = reference or get_business_now()
    return _schedule_start_datetime(schedule) <= reference


def _parse_session_input(session, index):
    if not isinstance(session, dict):
        return None, f'第 {index} 节课程数据格式不正确'

    session_date = (session.get('date') or '').strip()
    time_start = (session.get('time_start') or '').strip()
    time_end = (session.get('time_end') or '').strip()
    if not session_date or not time_start or not time_end:
        return None, f'第 {index} 节课程缺少日期或时间'

    try:
        session_day = date.fromisoformat(session_date)
    except ValueError:
        return None, f'第 {index} 节课程日期格式无效'

    try:
        start_dt = datetime.strptime(time_start, '%H:%M')
        end_dt = datetime.strptime(time_end, '%H:%M')
    except ValueError:
        return None, f'第 {index} 节课程时间格式无效'

    if end_dt <= start_dt:
        return None, f'第 {index} 节课程结束时间必须晚于开始时间'

    return {
        'date': session_day.isoformat(),
        'day_of_week': session_day.weekday(),
        'time_start': time_start,
        'time_end': time_end,
    }, None


def _normalize_manual_session_dates(session_dates):
    normalized = []
    errors = []
    for index, session in enumerate(session_dates or [], start=1):
        payload, error = _parse_session_input(session, index)
        if error:
            errors.append(error)
            continue
        normalized.append(payload)

    normalized.sort(
        key=lambda item: (
            item['date'],
            _time_to_minutes(item['time_start']),
            _time_to_minutes(item['time_end']),
        )
    )
    return normalized, errors


def _slots_overlap(time_start, time_end, other_start, other_end):
    return _compute_overlap(time_start, time_end, other_start, other_end, 1) is not None


def _session_within_ranges(session, ranges):
    for slot in ranges:
        if slot['day_of_week'] != session['day_of_week']:
            continue
        if (
            session['time_start'] >= slot['time_start']
            and session['time_end'] <= slot['time_end']
        ):
            return True
    return False


def _load_student_available_ranges(student_profile):
    if not student_profile or not student_profile.available_slots:
        return []
    try:
        available_slots = json.loads(student_profile.available_slots) or []
    except (json.JSONDecodeError, TypeError):
        return []

    ranges = []
    for slot in available_slots:
        try:
            day = int(slot.get('day'))
        except (TypeError, ValueError):
            continue
        start = (slot.get('start') or '').strip()
        end = (slot.get('end') or '').strip()
        if not start or not end:
            continue
        ranges.append({
            'day_of_week': day,
            'time_start': start,
            'time_end': end,
        })
    return ranges


def _load_teacher_available_ranges(teacher_id):
    from modules.auth.models import TeacherAvailability

    slots = TeacherAvailability.query.filter_by(user_id=teacher_id).all()
    return [
        {
            'day_of_week': slot.day_of_week,
            'time_start': slot.time_start,
            'time_end': slot.time_end,
        }
        for slot in slots
    ]


def _build_weekly_slots_from_sessions(session_dates):
    weekly_slots = {}
    for session in session_dates:
        key = (
            session['day_of_week'],
            session['time_start'],
            session['time_end'],
        )
        if key not in weekly_slots:
            weekly_slots[key] = {
                'day_of_week': session['day_of_week'],
                'time_start': session['time_start'],
                'time_end': session['time_end'],
                'score': 0,
                'is_preferred': False,
                'conflicts': [],
            }
    return sorted(weekly_slots.values(), key=_slot_sort_key)


def _build_manual_plan(session_dates):
    weekly_slots = _build_weekly_slots_from_sessions(session_dates)
    plan = _build_plan(weekly_slots, len(session_dates), set())
    plan = _apply_session_dates_to_plan(plan, session_dates, [])
    plan['is_manual'] = True
    return plan


def _collect_manual_plan_issues(enrollment, session_dates):
    from modules.oa.models import CourseSchedule

    errors = []
    warnings = []

    expected_sessions = _get_total_sessions(enrollment)
    if len(session_dates) != expected_sessions:
        errors.append(f'课次数量必须为 {expected_sessions} 节，当前为 {len(session_dates)} 节')

    if not session_dates:
        errors.append('至少需要保留一节课程')
        return errors, warnings

    now = get_business_now()
    for session in session_dates:
        start_at = datetime.combine(
            date.fromisoformat(session['date']),
            datetime.strptime(session['time_start'], '%H:%M').time(),
        )
        if start_at < now:
            errors.append(f'{session["date"]} {session["time_start"]}-{session["time_end"]} 已是过去时间，不能保存')

    for current, nxt in zip(session_dates, session_dates[1:]):
        if current['date'] != nxt['date']:
            continue
        if _slots_overlap(
            current['time_start'],
            current['time_end'],
            nxt['time_start'],
            nxt['time_end'],
        ):
            errors.append(
                f'{current["date"]} 存在课次时间重叠：'
                f'{current["time_start"]}-{current["time_end"]} 与 {nxt["time_start"]}-{nxt["time_end"]}'
            )

    teacher_name = enrollment.teacher.display_name if enrollment.teacher else ''
    ignore_ids = [schedule.id for schedule in _linked_schedule_query(enrollment.id).all()]
    session_dates_set = {item['date'] for item in session_dates}
    teacher_conflict_query = CourseSchedule.query.filter(
        CourseSchedule.date.in_(session_dates_set),
        or_(
            CourseSchedule.teacher_id == enrollment.teacher_id,
            CourseSchedule.teacher == teacher_name,
        ),
    )
    if ignore_ids:
        teacher_conflict_query = teacher_conflict_query.filter(~CourseSchedule.id.in_(ignore_ids))

    existing_by_date = {}
    for schedule in teacher_conflict_query.all():
        existing_by_date.setdefault(schedule.date.isoformat(), []).append(schedule)

    for session in session_dates:
        for existing in existing_by_date.get(session['date'], []):
            if _slots_overlap(
                session['time_start'],
                session['time_end'],
                existing.time_start,
                existing.time_end,
            ):
                errors.append(
                    f'{session["date"]} {session["time_start"]}-{session["time_end"]} '
                    f'与老师现有课程冲突：{existing.course_name} {existing.time_start}-{existing.time_end}'
                )

    teacher_ranges = _load_teacher_available_ranges(enrollment.teacher_id)
    student_ranges = _load_student_available_ranges(enrollment.student_profile)
    excluded_dates = _load_student_excluded_dates(enrollment.student_profile)

    for session in session_dates:
        if teacher_ranges and not _session_within_ranges(session, teacher_ranges):
            warnings.append(
                f'{session["date"]} {session["time_start"]}-{session["time_end"]} 超出老师原始可用时间'
            )
        if student_ranges and not _session_within_ranges(session, student_ranges):
            warnings.append(
                f'{session["date"]} {session["time_start"]}-{session["time_end"]} 超出学生填写的可上课时间'
            )
        if session['date'] in excluded_dates:
            warnings.append(f'{session["date"]} 命中学生标记的不可上课日期')

    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _linked_schedule_query(enrollment_id):
    from modules.oa.models import CourseSchedule

    legacy_note = f'报名#{enrollment_id}'
    return CourseSchedule.query.filter(
        or_(
            CourseSchedule.enrollment_id == enrollment_id,
            CourseSchedule.notes.contains(legacy_note),
        )
    )


def get_accessible_enrollment_query(user):
    from modules.auth.models import Enrollment

    query = Enrollment.query
    if not user or not getattr(user, 'is_authenticated', False):
        return query.filter(False)
    if user.role == 'admin':
        return query
    if user.role == 'teacher':
        return query.filter(Enrollment.teacher_id == user.id)
    if user.role == 'student':
        profile = user.student_profile
        if not profile:
            return query.filter(False)
        return query.filter(Enrollment.student_profile_id == profile.id)
    return query.filter(False)


def user_can_access_enrollment(user, enrollment):
    if not user or not enrollment or not getattr(user, 'is_authenticated', False):
        return False
    if user.role == 'admin':
        return True
    if user.role == 'teacher':
        return enrollment.teacher_id == user.id
    if user.role == 'student':
        profile = user.student_profile
        return bool(profile and enrollment.student_profile_id == profile.id)
    return False


def user_can_edit_enrollment_intake(user, enrollment):
    if not user_can_access_enrollment(user, enrollment):
        return False
    if user.role == 'teacher':
        return False
    return enrollment.status in {'pending_schedule', 'pending_student_confirm'}


def user_can_access_schedule(user, schedule):
    if not user or not schedule or not getattr(user, 'is_authenticated', False):
        return False
    if user.role == 'admin':
        return True
    if user.role == 'teacher':
        return schedule.teacher_id == user.id
    if user.role == 'student':
        profile = user.student_profile
        return bool(
            profile
            and schedule.enrollment
            and schedule.enrollment.student_profile_id == profile.id
        )
    return False


def _latest_leave_request(schedule):
    from modules.auth.models import LeaveRequest

    if not schedule:
        return None
    return LeaveRequest.query.filter_by(schedule_id=schedule.id).order_by(
        LeaveRequest.created_at.desc()
    ).first()


def user_can_request_leave(user, schedule):
    latest_leave = _latest_leave_request(schedule)
    if not user_can_access_schedule(user, schedule):
        return False
    if user.role != 'student':
        return False
    if _schedule_has_started(schedule):
        return False
    if latest_leave and latest_leave.status in {'pending', 'approved'}:
        return False
    return True


def user_can_approve_leave(user, leave_request):
    if not user or not leave_request or not getattr(user, 'is_authenticated', False):
        return False
    if user.role == 'admin':
        return True
    if user.role != 'teacher':
        return False
    return bool(leave_request.schedule and leave_request.schedule.teacher_id == user.id)


def user_can_chat_with(user, partner):
    from modules.auth.models import Enrollment

    if not user or not partner or not getattr(user, 'is_authenticated', False):
        return False
    if not getattr(partner, 'is_active', False):
        return False
    if user.id == partner.id:
        return False
    if user.role == 'admin' or partner.role == 'admin':
        return True
    if user.role == 'teacher' and partner.role == 'student':
        partner_profile = partner.student_profile
        if not partner_profile:
            return False
        return Enrollment.query.filter_by(
            teacher_id=user.id,
            student_profile_id=partner_profile.id,
        ).count() > 0
    if user.role == 'student' and partner.role == 'teacher':
        profile = user.student_profile
        if not profile:
            return False
        return Enrollment.query.filter_by(
            teacher_id=partner.id,
            student_profile_id=profile.id,
        ).count() > 0
    return False


def user_can_submit_feedback(user, schedule):
    if not (
        user
        and getattr(user, 'is_authenticated', False)
        and user.role == 'teacher'
        and schedule
        and schedule.teacher_id == user.id
    ):
        return False
    if not _schedule_has_started(schedule):
        return False
    latest_leave = _latest_leave_request(schedule)
    if latest_leave and latest_leave.status == 'approved':
        return False
    feedback = getattr(schedule, 'feedback', None)
    if feedback and feedback.status == 'submitted':
        return False
    return True


def build_feedback_payload(feedback, actor=None):
    if not feedback:
        return None
    payload = feedback.to_dict()
    payload['can_submit_feedback'] = bool(
        actor
        and getattr(actor, 'is_authenticated', False)
        and actor.role == 'teacher'
        and feedback.teacher_id == actor.id
    )
    return payload


def build_schedule_payload(schedule, actor=None):
    from modules.auth.workflow_services import get_schedule_workflow_todos

    payload = schedule.to_dict()
    latest_leave = _latest_leave_request(schedule)
    feedback = getattr(schedule, 'feedback', None)
    if actor and getattr(actor, 'is_authenticated', False) and actor.role == 'student':
        if feedback and feedback.status != 'submitted':
            feedback = None
    payload.update({
        'leave_request': latest_leave.to_dict() if latest_leave else None,
        'leave_status': latest_leave.status if latest_leave else None,
        'feedback': build_feedback_payload(feedback, actor),
        'feedback_status': feedback.status if feedback else None,
        'feedback_submitted_at': feedback.submitted_at.isoformat() if feedback and feedback.submitted_at else None,
        'is_delivered': bool(feedback and feedback.status == 'submitted'),
        'can_edit': bool(actor and getattr(actor, 'is_authenticated', False) and actor.role == 'admin'),
        'can_confirm': False,
        'can_reject': False,
        'can_request_leave': bool(actor and user_can_request_leave(actor, schedule)),
        'can_approve_leave': bool(actor and latest_leave and latest_leave.status == 'pending' and user_can_approve_leave(actor, latest_leave)),
        'can_submit_feedback': bool(actor and user_can_submit_feedback(actor, schedule)),
        'workflow_todos': get_schedule_workflow_todos(schedule.id, actor),
    })
    return payload


def build_leave_request_payload(leave_request, actor=None):
    from modules.auth.workflow_services import get_leave_request_workflow

    payload = leave_request.to_dict()
    payload.update({
        'can_edit': False,
        'can_confirm': False,
        'can_reject': False,
        'can_request_leave': False,
        'can_approve_leave': bool(
            actor
            and leave_request.status == 'pending'
            and user_can_approve_leave(actor, leave_request)
        ),
        'can_submit_feedback': False,
        'makeup_workflow': get_leave_request_workflow(leave_request.id, actor),
    })
    return payload


def _get_enrollment_delivery_meta(enrollment):
    from modules.oa.models import CourseFeedback

    schedules = _linked_schedule_query(enrollment.id).all()
    schedule_ids = [schedule.id for schedule in schedules]
    latest_feedback = None
    completed_count = 0
    pending_feedback_count = 0
    approved_leave_count = 0

    if schedule_ids:
        submitted_feedbacks = CourseFeedback.query.filter(
            CourseFeedback.schedule_id.in_(schedule_ids),
            CourseFeedback.status == 'submitted',
        ).order_by(CourseFeedback.submitted_at.desc(), CourseFeedback.updated_at.desc()).all()
        completed_count = len(submitted_feedbacks)
        latest_feedback = submitted_feedbacks[0] if submitted_feedbacks else None

    now = get_business_now()
    for schedule in schedules:
        latest_leave = _latest_leave_request(schedule)
        if latest_leave and latest_leave.status == 'approved':
            approved_leave_count += 1
        feedback = getattr(schedule, 'feedback', None)
        if _schedule_has_started(schedule, now) and not (feedback and feedback.status == 'submitted'):
            if not latest_leave or latest_leave.status != 'approved':
                pending_feedback_count += 1

    return {
        'scheduled_count': len(schedules),
        'completed_count': completed_count,
        'leave_count': approved_leave_count,
        'pending_feedback_count': pending_feedback_count,
        'latest_teacher_feedback': latest_feedback.summary if latest_feedback and latest_feedback.summary else None,
        'latest_teacher_feedback_at': latest_feedback.submitted_at.isoformat() if latest_feedback and latest_feedback.submitted_at else None,
    }


def get_enrollment_feedback_meta(enrollment):
    """返回报名最近一次学生排课反馈及未读状态。"""
    from modules.auth.models import ChatMessage

    if not enrollment:
        return {
            'latest_feedback': None,
            'latest_feedback_at': None,
            'has_unread_feedback': False,
        }

    query = ChatMessage.query.filter(
        ChatMessage.enrollment_id == enrollment.id,
        ChatMessage.content.startswith(FEEDBACK_PREFIX),
    )
    latest = query.order_by(ChatMessage.created_at.desc()).first()
    if not latest:
        return {
            'latest_feedback': None,
            'latest_feedback_at': None,
            'has_unread_feedback': False,
        }

    feedback_text = latest.content[len(FEEDBACK_PREFIX):].strip()
    if feedback_text.startswith('[') and '] ' in feedback_text:
        feedback_text = feedback_text.split('] ', 1)[1]
    has_unread = query.filter(ChatMessage.is_read == False).count() > 0
    return {
        'latest_feedback': feedback_text,
        'latest_feedback_at': latest.created_at.isoformat() if latest.created_at else None,
        'has_unread_feedback': has_unread,
    }


def build_enrollment_payload(enrollment, actor=None):
    from modules.auth.workflow_services import get_enrollment_workflow_todos

    payload = enrollment.to_dict()
    payload['proposed_slots'] = [
        normalize_plan(plan, enrollment)
        for plan in payload.get('proposed_slots', [])
    ]
    payload['confirmed_slot'] = normalize_plan(payload.get('confirmed_slot'), enrollment)
    payload.update(get_enrollment_feedback_meta(enrollment))
    payload.update(_get_enrollment_delivery_meta(enrollment))
    payload.update({
        'expected_session_count': _get_total_sessions(enrollment),
        'can_edit': bool(actor and user_can_edit_enrollment_intake(actor, enrollment)),
        'can_confirm': bool(
            actor
            and getattr(actor, 'is_authenticated', False)
            and actor.role == 'student'
            and user_can_access_enrollment(actor, enrollment)
            and enrollment.status == 'pending_student_confirm'
        ),
        'can_reject': bool(
            actor
            and getattr(actor, 'is_authenticated', False)
            and actor.role == 'student'
            and user_can_access_enrollment(actor, enrollment)
            and enrollment.status == 'pending_student_confirm'
        ),
        'can_request_leave': False,
        'can_approve_leave': False,
        'can_submit_feedback': False,
        'edit_intake_url': f'/auth/enrollments/{enrollment.id}/intake-edit',
    })
    workflow_todos = get_enrollment_workflow_todos(enrollment.id, actor)
    payload['workflow_todos'] = workflow_todos
    payload['active_workflow_todo'] = workflow_todos[0] if workflow_todos else None
    return payload


def sync_enrollment_status(enrollment):
    """根据课表与交付情况重新计算报名状态。"""
    from modules.oa.models import CourseSchedule

    if not enrollment:
        return None
    if enrollment.status in {'pending_info', 'pending_schedule'}:
        return enrollment.status

    schedules = _linked_schedule_query(enrollment.id).order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()
    if enrollment.status == 'pending_student_confirm' and not schedules:
        return enrollment.status
    if not schedules:
        enrollment.status = 'confirmed' if enrollment.confirmed_slot else 'pending_schedule'
        return enrollment.status

    now = get_business_now()
    started_schedules = [schedule for schedule in schedules if _schedule_has_started(schedule, now)]
    if not started_schedules:
        enrollment.status = 'confirmed'
        return enrollment.status

    has_future_schedule = any(_schedule_start_datetime(schedule) > now for schedule in schedules)
    has_open_delivery = False
    for schedule in started_schedules:
        latest_leave = _latest_leave_request(schedule)
        approved_leave = bool(latest_leave and latest_leave.status == 'approved')
        feedback = getattr(schedule, 'feedback', None)
        delivered = bool(feedback and feedback.status == 'submitted')
        if not delivered and not approved_leave:
            has_open_delivery = True
            break

    enrollment.status = 'active' if has_future_schedule or has_open_delivery else 'completed'
    return enrollment.status


def find_matching_slots(enrollment_id):
    """自动匹配排课，返回最多 3 个效率优先的 plan。"""
    from modules.auth.models import Enrollment, TeacherAvailability
    from modules.oa.models import CourseSchedule

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return [], '报名记录不存在'

    min_minutes = int(enrollment.hours_per_session * 60)
    total_sessions = _get_total_sessions(enrollment)

    teacher_name = enrollment.teacher.display_name if enrollment.teacher else '该教师'
    teacher_slots = TeacherAvailability.query.filter_by(user_id=enrollment.teacher_id).all()
    if not teacher_slots:
        return [], f'{teacher_name} 尚未设置可用时间，请先在面板中设置'

    student_profile = enrollment.student_profile
    if not student_profile or not student_profile.available_slots:
        return [], '学生尚未提交可用时间信息'

    try:
        student_slots = json.loads(student_profile.available_slots)
    except (json.JSONDecodeError, TypeError):
        return [], '学生可用时间数据异常'

    excluded_set = _load_student_excluded_dates(student_profile)

    existing_schedules = CourseSchedule.query.filter(
        or_(
            CourseSchedule.teacher_id == enrollment.teacher_id,
            CourseSchedule.teacher == teacher_name,
        )
    ).all()
    existing_by_day = {}
    for schedule in existing_schedules:
        existing_by_day.setdefault(schedule.day_of_week, []).append(schedule)

    candidates = []
    for teacher_slot in teacher_slots:
        for student_slot in student_slots:
            if teacher_slot.day_of_week != student_slot.get('day'):
                continue

            overlap = _compute_overlap(
                teacher_slot.time_start,
                teacher_slot.time_end,
                student_slot.get('start', ''),
                student_slot.get('end', ''),
                min_minutes,
            )
            if not overlap:
                continue

            overlap_start = _time_to_minutes(overlap[0])
            overlap_end = _time_to_minutes(overlap[1])
            cursor = overlap_start
            while cursor + min_minutes <= overlap_end:
                block_start = _minutes_to_time(cursor)
                block_end = _minutes_to_time(cursor + min_minutes)

                conflicts = []
                for existing in existing_by_day.get(teacher_slot.day_of_week, []):
                    if _compute_overlap(
                        block_start,
                        block_end,
                        existing.time_start,
                        existing.time_end,
                        1,
                    ):
                        conflicts.append({
                            'course_name': existing.course_name,
                            'time': f'{existing.time_start}-{existing.time_end}',
                            'students': existing.students,
                        })

                score = 0
                if not conflicts:
                    score += 4
                if teacher_slot.is_preferred:
                    score += 1
                if block_start >= student_slot.get('start', '') and block_end <= student_slot.get('end', ''):
                    score += 2

                candidates.append({
                    'day_of_week': teacher_slot.day_of_week,
                    'time_start': block_start,
                    'time_end': block_end,
                    'score': score,
                    'is_preferred': teacher_slot.is_preferred,
                    'conflicts': conflicts,
                })
                cursor += 60

    deduped = {}
    for candidate in candidates:
        key = _slot_signature(candidate)
        if key not in deduped or candidate.get('score', 0) > deduped[key].get('score', 0):
            deduped[key] = candidate

    grouped_candidates = {}
    for candidate in deduped.values():
        grouped_candidates.setdefault(candidate['day_of_week'], []).append(candidate)

    if not grouped_candidates:
        return [], '老师和学生的可用时间没有重叠，无法自动匹配'

    for day, blocks in grouped_candidates.items():
        grouped_candidates[day] = sorted(blocks, key=_candidate_sort_key)

    option_lists = []
    for day in sorted(grouped_candidates.keys()):
        option_lists.append(grouped_candidates[day][:2])

    plans_by_signature = {}
    for combo in product(*option_lists):
        selected_blocks = sorted(list(combo), key=_slot_sort_key)
        selected_blocks = _extend_single_day_plan(selected_blocks, grouped_candidates, total_sessions)
        plan = _build_plan(selected_blocks, total_sessions, excluded_set)
        signature = tuple(_slot_signature(slot) for slot in plan['weekly_slots'])
        if signature not in plans_by_signature or _plan_sort_key(plan) < _plan_sort_key(plans_by_signature[signature]):
            plans_by_signature[signature] = plan

    plans = sorted(plans_by_signature.values(), key=_plan_sort_key)
    return plans[:3], None


def propose_enrollment_schedule(enrollment_id, slot_index):
    """管理员选择 plan -> 保存并通知学生确认。"""
    from modules.auth.models import Enrollment

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return False, '报名记录不存在', []

    if not enrollment.proposed_slots:
        return False, '没有可用的排课方案', []

    try:
        proposed = json.loads(enrollment.proposed_slots)
    except (json.JSONDecodeError, TypeError):
        return False, '排课方案数据异常', []

    if slot_index < 0 or slot_index >= len(proposed):
        return False, '方案索引无效', []

    raw_plan = proposed[slot_index]
    plan = normalize_plan(raw_plan, enrollment)
    if not plan or not plan.get('weekly_slots'):
        return False, '排课方案数据异常', []

    enrollment.confirmed_slot = json.dumps(plan, ensure_ascii=False)
    enrollment.status = 'pending_student_confirm'
    _send_schedule_notification(enrollment, plan)
    db.session.commit()

    msg = f'已通知学生确认，共 {len(plan["session_dates"])} 节课'
    if plan['skipped_dates']:
        msg += f'（跳过 {len(plan["skipped_dates"])} 个不可上课日期）'
    return True, msg, plan['session_dates']


def save_manual_enrollment_plan(enrollment_id, session_dates, *, force_save=False):
    from modules.auth.models import Enrollment

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return {
            'success': False,
            'status_code': 404,
            'error': '报名记录不存在',
        }

    if enrollment.status not in {'pending_schedule', 'pending_student_confirm'}:
        return {
            'success': False,
            'status_code': 400,
            'error': '当前状态不允许手动调整排课方案',
        }

    normalized_dates, parse_errors = _normalize_manual_session_dates(session_dates)
    if parse_errors:
        return {
            'success': False,
            'status_code': 400,
            'error': '；'.join(parse_errors),
            'errors': parse_errors,
        }

    errors, warnings = _collect_manual_plan_issues(enrollment, normalized_dates)
    if errors:
        return {
            'success': False,
            'status_code': 400,
            'error': '；'.join(errors),
            'errors': errors,
        }

    if warnings and not force_save:
        return {
            'success': False,
            'status_code': 200,
            'error': '方案存在提示项，请确认是否继续保存',
            'warnings': warnings,
            'can_force_save': True,
        }

    plan = _build_manual_plan(normalized_dates)
    if warnings:
        plan['manual_warnings'] = warnings
    enrollment.confirmed_slot = json.dumps(plan, ensure_ascii=False)
    enrollment.status = 'pending_student_confirm'
    _send_schedule_notification(enrollment, plan)
    db.session.commit()

    return {
        'success': True,
        'status_code': 200,
        'message': '手动排课方案已保存，并已重新通知学生确认',
        'plan': plan,
    }


def _send_schedule_notification(enrollment, plan):
    """通过 ChatMessage 通知学生查看排课方案。"""
    from modules.auth.models import ChatMessage

    profile = enrollment.student_profile
    if not profile or not profile.user_id:
        return

    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekly_text = '；'.join(
        f'{day_names[slot["day_of_week"]]} {slot["time_start"]}-{slot["time_end"]}'
        for slot in plan.get('weekly_slots', [])
    )
    first_date = plan.get('date_start') or '待定'
    last_date = plan.get('date_end') or '待定'

    content = (
        f'{SCHEDULE_PREFIX}[{enrollment.course_name}] '
        f'你的课程排课方案已准备好：\n'
        f'每周安排：{weekly_text or "待定"}\n'
        f'共 {len(plan.get("session_dates", []))} 节，预计 {plan.get("estimated_weeks", 0)} 周完成\n'
        f'首次上课：{first_date}\n'
        f'最后一课：{last_date}\n'
        '请前往「我的课表」页面查看并确认。'
    )

    msg = ChatMessage(
        sender_id=enrollment.teacher_id,
        receiver_id=profile.user_id,
        enrollment_id=enrollment.id,
        content=content,
        is_read=False,
    )
    db.session.add(msg)


def student_confirm_schedule(enrollment_id):
    """学生确认排课 -> 创建全部具体课次。"""
    from modules.auth.models import Enrollment
    from modules.oa.models import CourseFeedback, CourseSchedule, OATodo
    from modules.oa.services import delivery_mode_from_color_tag
    from modules.auth.models import LeaveRequest
    from modules.auth.workflow_services import complete_replan_workflows_for_enrollment, ensure_schedule_feedback_todo

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return False, '报名记录不存在', 0

    if enrollment.status != 'pending_student_confirm':
        return False, '当前状态不允许确认', 0

    if not enrollment.confirmed_slot:
        return False, '没有待确认的排课方案', 0

    try:
        plan = normalize_plan(json.loads(enrollment.confirmed_slot), enrollment)
    except (json.JSONDecodeError, TypeError):
        return False, '排课方案数据异常', 0

    session_dates = plan.get('session_dates', [])
    if not session_dates:
        return False, '排课方案没有具体课次', 0

    teacher_name = enrollment.teacher.display_name if enrollment.teacher else ''
    student_name = enrollment.student_name

    existing_ids = [schedule.id for schedule in _linked_schedule_query(enrollment.id).all()]
    if existing_ids:
        OATodo.query.filter(OATodo.schedule_id.in_(existing_ids)).delete(synchronize_session=False)
        LeaveRequest.query.filter(LeaveRequest.schedule_id.in_(existing_ids)).delete(synchronize_session=False)
        CourseFeedback.query.filter(CourseFeedback.schedule_id.in_(existing_ids)).delete(synchronize_session=False)
        CourseSchedule.query.filter(CourseSchedule.id.in_(existing_ids)).delete(synchronize_session=False)

    created_count = 0
    for session in session_dates:
        course_date = date.fromisoformat(session['date'])
        schedule = CourseSchedule(
            date=course_date,
            day_of_week=session['day_of_week'],
            time_start=session['time_start'],
            time_end=session['time_end'],
            teacher=teacher_name,
            teacher_id=enrollment.teacher_id,
            course_name=enrollment.course_name,
            enrollment_id=enrollment.id,
            students=student_name,
            color_tag='green',
            delivery_mode=delivery_mode_from_color_tag('green'),
            notes=f'自动排课 - 报名#{enrollment.id}',
        )
        db.session.add(schedule)
        db.session.flush()
        ensure_schedule_feedback_todo(schedule, created_by=enrollment.teacher_id)
        created_count += 1

    enrollment.status = 'confirmed'
    db.session.flush()
    sync_enrollment_status(enrollment)
    complete_replan_workflows_for_enrollment(enrollment.id)
    db.session.commit()
    return True, f'已生成 {created_count} 节课程', created_count


def send_leave_status_notification(leave_request):
    from modules.auth.models import ChatMessage

    enrollment = leave_request.enrollment or (leave_request.schedule.enrollment if leave_request.schedule else None)
    profile = enrollment.student_profile if enrollment else None
    if not profile or not profile.user_id:
        return

    status_text = '已批准' if leave_request.status == 'approved' else '已驳回'
    course_name = leave_request.schedule.course_name if leave_request.schedule else ''
    leave_date = leave_request.leave_date.isoformat() if leave_request.leave_date else ''
    content = (
        f'[请假审批][{course_name}] 你在 {leave_date} 的请假申请{status_text}。'
        f'{(" 原因：" + leave_request.reason) if leave_request.reason else ""}'
    )
    db.session.add(ChatMessage(
        sender_id=leave_request.approved_by,
        receiver_id=profile.user_id,
        enrollment_id=enrollment.id if enrollment else None,
        content=content,
        is_read=False,
    ))


def save_course_feedback(schedule, teacher_id, data, *, submit=False):
    from modules.oa.models import CourseFeedback
    from modules.auth.workflow_services import complete_schedule_feedback_todo

    feedback = CourseFeedback.query.filter_by(
        schedule_id=schedule.id,
        teacher_id=teacher_id,
    ).first()
    if not feedback:
        feedback = CourseFeedback(schedule_id=schedule.id, teacher_id=teacher_id)
        db.session.add(feedback)

    feedback.summary = (data.get('summary') or '').strip() or None
    feedback.homework = (data.get('homework') or '').strip() or None
    feedback.next_focus = (data.get('next_focus') or '').strip() or None

    if submit:
        if not feedback.summary:
            return False, '请先填写本次课程总结', None
        feedback.status = 'submitted'
        feedback.submitted_at = get_business_now()
    elif feedback.status != 'submitted':
        feedback.status = 'draft'

    db.session.flush()
    if submit:
        complete_schedule_feedback_todo(schedule.id)
        if schedule.enrollment:
            sync_enrollment_status(schedule.enrollment)
    db.session.commit()
    return True, '反馈已提交' if submit else '反馈草稿已保存', feedback


def export_enrollment_schedule_xlsx(enrollment_id):
    """导出排课课表为 .xlsx 文件。"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    from modules.auth.models import Enrollment
    from modules.oa.models import CourseSchedule

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return None, None, '报名记录不存在'

    if not enrollment.confirmed_slot:
        return None, None, '尚未确认排课方案'

    try:
        plan = normalize_plan(json.loads(enrollment.confirmed_slot), enrollment)
    except (json.JSONDecodeError, TypeError):
        return None, None, '排课数据异常'

    teacher_name = enrollment.teacher.display_name if enrollment.teacher else ''
    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    schedules = _linked_schedule_query(enrollment.id).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    wb = Workbook()
    ws = wb.active
    ws.title = '课程表'

    header_fill = PatternFill(start_color='0EA5E9', end_color='0EA5E9', fill_type='solid')
    header_font = Font(bold=True, size=11, color='FFFFFF')
    headers = ['序号', '日期', '星期', '开始时间', '结束时间', '课程名称', '授课教师', '学生']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    if schedules:
        for index, schedule in enumerate(schedules, 1):
            ws.append([
                index,
                schedule.date.isoformat(),
                day_names[schedule.day_of_week],
                schedule.time_start,
                schedule.time_end,
                schedule.course_name,
                schedule.teacher,
                schedule.students,
            ])
    else:
        for index, session in enumerate(plan.get('session_dates', []), 1):
            ws.append([
                index,
                session['date'],
                day_names[session['day_of_week']],
                session['time_start'],
                session['time_end'],
                enrollment.course_name,
                teacher_name,
                enrollment.student_name,
            ])

    for column in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in column)
        ws.column_dimensions[column[0].column_letter].width = max_len + 4

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f'{enrollment.student_name}_{enrollment.course_name}_课程表.xlsx'
    return output, filename, None


def delete_student_user_hard(user_id):
    """仅允许硬删除学生账号，且需无强关联业务数据。"""
    from modules.auth.models import ChatMessage, Enrollment, LeaveRequest, StudentProfile, User
    from modules.oa.models import CourseSchedule

    user = db.session.get(User, user_id)
    if not user:
        return False, '用户不存在'
    if user.role != 'student':
        return False, '仅学生账号支持删除'

    profiles = StudentProfile.query.filter_by(user_id=user.id).all()
    profile_ids = [profile.id for profile in profiles]
    enrollment_ids = []

    if profile_ids:
        enrollment_ids = [
            row[0] for row in Enrollment.query.with_entities(Enrollment.id).filter(
                Enrollment.student_profile_id.in_(profile_ids)
            ).all()
        ]

    if enrollment_ids:
        return False, '该学生账号仍有关联的报名记录，请先删除相关报名'

    linked_schedule_ids = []
    if profile_ids:
        linked_schedule_ids = [
            row[0] for row in CourseSchedule.query.with_entities(CourseSchedule.id).join(
                Enrollment, CourseSchedule.enrollment_id == Enrollment.id
            ).filter(Enrollment.student_profile_id.in_(profile_ids)).all()
        ]

    if linked_schedule_ids:
        return False, '该学生账号仍有关联的正式课表，请先删除相关报名'

    if linked_schedule_ids and LeaveRequest.query.filter(LeaveRequest.schedule_id.in_(linked_schedule_ids)).count() > 0:
        return False, '该学生账号仍有关联的请假记录，请先删除相关报名'

    ChatMessage.query.filter(
        or_(ChatMessage.sender_id == user.id, ChatMessage.receiver_id == user.id)
    ).delete(synchronize_session=False)

    for profile in profiles:
        db.session.delete(profile)
    db.session.delete(user)
    db.session.commit()
    return True, '学生账号已删除'


def delete_enrollment_hard(enrollment_id):
    """硬删除报名，并联动清理课表、请假、待办和站内消息。"""
    from modules.auth.models import ChatMessage, Enrollment, LeaveRequest
    from modules.oa.models import CourseFeedback, CourseSchedule, OATodo

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return False, '报名记录不存在'

    linked_schedules = _linked_schedule_query(enrollment.id).all()
    schedule_ids = [schedule.id for schedule in linked_schedules]

    if schedule_ids:
        OATodo.query.filter(OATodo.schedule_id.in_(schedule_ids)).delete(synchronize_session=False)
        LeaveRequest.query.filter(LeaveRequest.schedule_id.in_(schedule_ids)).delete(synchronize_session=False)
        CourseFeedback.query.filter(CourseFeedback.schedule_id.in_(schedule_ids)).delete(synchronize_session=False)
        CourseSchedule.query.filter(CourseSchedule.id.in_(schedule_ids)).delete(synchronize_session=False)

    ChatMessage.query.filter(ChatMessage.enrollment_id == enrollment.id).delete(synchronize_session=False)

    profile = enrollment.student_profile
    should_delete_profile = False
    if profile:
        remaining = Enrollment.query.filter(
            Enrollment.student_profile_id == profile.id,
            Enrollment.id != enrollment.id,
        ).count()
        should_delete_profile = remaining == 0
    db.session.delete(enrollment)
    if profile and should_delete_profile:
        db.session.delete(profile)

    db.session.commit()
    return True, f'报名已删除，并清理 {len(schedule_ids)} 节关联课程'


def backfill_schedule_relationships():
    """回填历史自动排课记录的 teacher_id / enrollment_id。"""
    from modules.auth.models import Enrollment, User
    from modules.oa.models import CourseSchedule

    updated = 0
    schedules = CourseSchedule.query.filter(
        or_(CourseSchedule.enrollment_id == None, CourseSchedule.teacher_id == None)
    ).all()
    for schedule in schedules:
        changed = False
        enrollment = None

        if schedule.enrollment_id:
            enrollment = db.session.get(Enrollment, schedule.enrollment_id)

        if not enrollment and schedule.notes:
            match = re.search(r'报名#(\d+)', schedule.notes)
            if match:
                enrollment = db.session.get(Enrollment, int(match.group(1)))
                if enrollment:
                    schedule.enrollment_id = enrollment.id
                    changed = True

        if not schedule.teacher_id:
            if enrollment:
                schedule.teacher_id = enrollment.teacher_id
                changed = True
            elif schedule.teacher:
                teacher = User.query.filter(
                    or_(User.display_name == schedule.teacher, User.username == schedule.teacher)
                ).first()
                if teacher:
                    schedule.teacher_id = teacher.id
                    changed = True

        if changed:
            updated += 1

    if updated:
        db.session.commit()
    return updated


def seed_staff_accounts():
    """将现有硬编码员工初始化为用户账号。"""
    from modules.auth.models import User

    staff_accounts = [
        ('admin', '管理员', 'admin', 'admin'),
        ('liyu', '李宇', 'admin', 'scf123'),
        ('fanxiaodong', '范晓东', 'admin', 'scf123'),
        ('zhouxing', '周行', 'admin', 'scf123'),
        ('baoruimin', '包睿旻', 'teacher', 'scf123'),
        ('liyijun', '黎怡君', 'teacher', 'scf123'),
        ('zhangyu', '张渝', 'teacher', 'scf123'),
        ('chenguanru', '陈冠如', 'teacher', 'scf123'),
        ('wangyanlong', '王艳龙', 'teacher', 'scf123'),
        ('lulaoshi', '卢老师', 'teacher', 'scf123'),
        ('tianpeng', '田鹏', 'teacher', 'scf123'),
        ('chendonghao', '陈东豪', 'teacher', 'scf123'),
    ]

    created = 0
    for username, display_name, role, password in staff_accounts:
        if User.query.filter_by(username=username).first():
            continue
        user = User(username=username, display_name=display_name, role=role)
        user.set_password(password)
        db.session.add(user)
        created += 1

    if created > 0:
        db.session.commit()
    return created
