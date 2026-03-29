import json
from calendar import monthrange
from datetime import date, datetime, timedelta

from flask import jsonify, redirect, render_template, request
from flask_login import current_user, login_user, login_required, logout_user

from extensions import db
from modules.auth import auth_bp
from modules.auth.decorators import role_required
from modules.auth.models import Enrollment, LeaveRequest, TeacherAvailability, User
from modules.auth.services import (
    _actor_can_manage_schedule_feedback,
    _latest_leave_request,
    _normalize_teacher_work_mode,
    _profile_constraint_meta,
    _teacher_work_context,
    _schedule_has_started,
    student_schedule_profile_clause,
    _teacher_identity_names,
    _teacher_schedule_identity_filter,
    _validate_available_slot_entries,
    build_enrollment_payload,
    build_feedback_payload,
    build_leave_request_payload,
    build_schedule_payload,
    delete_student_user_hard,
    get_accessible_enrollment_query,
    get_business_today,
    reject_enrollment_schedule,
    schedule_requires_course_feedback,
    save_course_feedback,
    seed_staff_accounts,
    student_confirm_schedule,
    teacher_availability_ready,
    user_can_access_schedule,
)
from modules.oa.models import CourseFeedback, CourseSchedule, OATodo


def _resolve_date_range(range_param):
    today = get_business_today()
    if range_param == 'month':
        _, last_day = monthrange(today.year, today.month)
        return today.replace(day=1), today.replace(day=last_day)
    if range_param == 'all':
        return today, today + timedelta(days=365)
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def _parse_calendar_range():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        return None, None, jsonify({'success': False, 'error': '请提供 start 和 end 日期参数'}), 400
    try:
        return date.fromisoformat(start_str), date.fromisoformat(end_str), None, None
    except ValueError:
        return None, None, jsonify({'success': False, 'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400


def _teacher_can_manage_availability(teacher_id):
    return current_user.role == 'admin' or current_user.id == teacher_id


def _feedback_permission_error(schedule):
    if not schedule or not _actor_can_manage_schedule_feedback(current_user, schedule):
        return jsonify({'success': False, 'error': '无权提交该课程反馈'}), 403
    if getattr(schedule, 'feedback', None) and schedule.feedback.status == 'submitted':
        return jsonify({'success': False, 'error': '该课程反馈已提交'}), 400
    latest_leave = _latest_leave_request(schedule)
    if latest_leave and latest_leave.status == 'approved':
        return jsonify({'success': False, 'error': '该课程已批准请假，不能提交反馈'}), 400
    if not _schedule_has_started(schedule):
        return jsonify({'success': False, 'error': '课程尚未开始，暂不能提交反馈'}), 400
    return None


def _teacher_schedule_query(user, start=None, end=None):
    query = CourseSchedule.query.filter(
        _teacher_schedule_identity_filter(CourseSchedule, user),
        CourseSchedule.is_cancelled == False,
    )
    if start is not None:
        query = query.filter(CourseSchedule.date >= start)
    if end is not None:
        query = query.filter(CourseSchedule.date <= end)
    return query.order_by(CourseSchedule.date, CourseSchedule.time_start)


def _student_schedule_query(user, start=None, end=None):
    profile = user.student_profile
    if not profile:
        return CourseSchedule.query.filter(False)

    query = CourseSchedule.query.filter(
        student_schedule_profile_clause(profile.id, schedule_model=CourseSchedule),
        CourseSchedule.is_cancelled == False,
    )

    if start is not None:
        query = query.filter(CourseSchedule.date >= start)
    if end is not None:
        query = query.filter(CourseSchedule.date <= end)
    return query.order_by(CourseSchedule.date, CourseSchedule.time_start)


def _parse_iso_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _parse_iso_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _action_sort_key(item):
    overdue_rank = 0 if item.get('is_overdue') else 1
    priority = int(item.get('priority') or 9)
    due_date = _parse_iso_date(item.get('due_date') or item.get('date')) or date.max
    waiting_since = (
        _parse_iso_datetime(item.get('waiting_since'))
        or _parse_iso_datetime(item.get('updated_at'))
        or _parse_iso_datetime(item.get('created_at'))
        or datetime.max
    )
    time_start = item.get('time_start') or '99:99'
    return (overdue_rank, priority, due_date, waiting_since, time_start)


def _sort_action_items(items):
    return sorted(items, key=_action_sort_key)


def _workflow_matches_teacher_actor(item, actor):
    if not actor or not item:
        return False
    teacher_id = item.get('teacher_id')
    if teacher_id is not None:
        return teacher_id == actor.id
    teacher_name = str(item.get('teacher_name') or '').strip()
    return bool(teacher_name and teacher_name in _teacher_identity_names(actor))


def _student_profile_payload(profile):
    if not profile:
        return None
    payload = profile.to_dict()
    meta = _profile_constraint_meta(profile)
    payload.update({
        'available_times_summary': meta['available_times_summary'],
        'excluded_dates_summary': meta['excluded_dates_summary'],
    })
    return payload


SCHEDULING_CASE_TYPE_DIRECT_PASS = 'direct_pass_case'
SCHEDULING_CASE_TYPE_TEACHER_EXCEPTION = 'teacher_exception_case'
SCHEDULING_CASE_TYPE_STUDENT_CLARIFICATION = 'student_clarification_case'
SCHEDULING_CASE_TYPE_ADMIN_RISK = 'admin_risk_case'


def _scheduling_case_id(kind, entity_id):
    return f'{kind}-{entity_id}'


def _scheduling_case_type_from_recommended_action(recommended_action):
    return {
        'direct_to_student': SCHEDULING_CASE_TYPE_DIRECT_PASS,
        'needs_teacher_confirmation': SCHEDULING_CASE_TYPE_TEACHER_EXCEPTION,
        'needs_student_clarification': SCHEDULING_CASE_TYPE_STUDENT_CLARIFICATION,
        'needs_admin_intervention': SCHEDULING_CASE_TYPE_ADMIN_RISK,
        'needs_admin_review': SCHEDULING_CASE_TYPE_ADMIN_RISK,
    }.get(recommended_action, SCHEDULING_CASE_TYPE_ADMIN_RISK)


def _student_action_item_from_clarification_enrollment(item):
    risk = item.get('risk_assessment') or {}
    clarification_reasons = risk.get('clarification_reasons') or []
    return {
        'title': item.get('course_name') or '补充可上课时间',
        'status_label': '待补充时间',
        'next_step': item.get('next_step_hint') or '请补充或确认可上课时间，系统再继续排课。',
        'primary_action': {'label': '补充可上课时间', 'action': 'clarify'},
        'secondary_action': None,
        'detail_preview': (
            clarification_reasons[0]
            if clarification_reasons
            else (risk.get('summary') or item.get('availability_intake_summary') or '请补充你的可上课时间')
        ),
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'entity_ref': {'kind': 'enrollment', 'id': item.get('id')},
        'current_plan_summary': item.get('availability_intake_summary'),
        'session_preview_lines': [],
        'waiting_since': item.get('waiting_since'),
        'updated_at': item.get('updated_at'),
        'priority': item.get('priority'),
        'edit_url': item.get('edit_intake_url'),
        'kind': 'student_clarification',
    }


def _student_action_item_from_enrollment(item):
    return {
        'title': item.get('course_name') or '待确认课程',
        'status_label': '待确认课程',
        'next_step': item.get('next_step_hint') or '确认后系统会生成正式课表',
        'primary_action': {'label': '确认当前方案', 'action': 'confirm'},
        'secondary_action': {'label': '有问题', 'action': 'reject', 'requires_message': True},
        'detail_preview': item.get('current_plan_summary') or '请查看当前推荐方案',
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'entity_ref': {'kind': 'enrollment', 'id': item.get('id')},
        'current_plan_summary': item.get('current_plan_summary'),
        'session_preview_lines': item.get('session_preview_lines') or [],
        'waiting_since': item.get('waiting_since'),
        'updated_at': item.get('updated_at'),
        'priority': item.get('priority'),
        'kind': 'pending_enrollment',
    }


def _student_action_item_from_workflow(item):
    requires_action = item.get('next_action_role') == 'student'
    todo_type = item.get('todo_type')
    status_label = '待确认补课' if todo_type == 'leave_makeup' and requires_action else (
        '待确认课程' if requires_action else '进行中的安排'
    )
    next_step = item.get('next_step_hint') or (
        '确认后补课时间会正式生效。' if todo_type == 'leave_makeup' and requires_action else '系统正在继续推进该事项。'
    )
    action_item = {
        'title': item.get('title') or item.get('course_name') or item.get('todo_type_label') or '学生事项',
        'status_label': status_label,
        'next_step': next_step,
        'primary_action': {'label': '确认当前方案', 'action': 'confirm'} if requires_action else None,
        'secondary_action': {'label': '有问题', 'action': 'reject', 'requires_message': True} if requires_action else None,
        'detail_preview': item.get('current_plan_summary') or item.get('context_summary') or item.get('description'),
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'entity_ref': {'kind': 'workflow_todo', 'id': item.get('id')},
        'current_plan_summary': item.get('current_plan_summary'),
        'session_preview_lines': item.get('session_preview_lines') or [],
        'waiting_since': item.get('waiting_since'),
        'updated_at': item.get('updated_at'),
        'priority': item.get('priority'),
        'kind': 'workflow_todo',
    }
    return action_item


def _build_student_action_items(*, action_required_workflows, pending_enrollments, tracking_workflows):
    clarification_items = [
        _student_action_item_from_clarification_enrollment(item)
        for item in pending_enrollments
        if item.get('next_action_status') == 'waiting_student_clarification'
    ]
    confirmation_items = [
        _student_action_item_from_enrollment(item)
        for item in pending_enrollments
        if item.get('next_action_status') != 'waiting_student_clarification'
    ] + [
        _student_action_item_from_workflow(item)
        for item in action_required_workflows
    ]
    action_items = clarification_items + confirmation_items
    tracking_items = [
        _student_action_item_from_workflow(item)
        for item in tracking_workflows
    ]
    return _sort_action_items(action_items), _sort_action_items(tracking_items)


def _teacher_action_item_from_workflow(item):
    risk = item.get('risk_assessment') or {}
    full_time_exception = (
        item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and item.get('teacher_work_mode') == 'full_time'
        and (
            risk.get('teacher_confirmation_required')
            or (risk.get('recommended_action') or '') == 'needs_teacher_confirmation'
        )
    )
    return {
        'title': item.get('title') or item.get('course_name') or '待处理排课事项',
        'status_label': '待确认例外时段' if full_time_exception else (item.get('workflow_status_label') or '待我处理'),
        'next_step': (
            item.get('next_step_hint')
            or ('确认模板外时段后系统会继续推进。' if full_time_exception else '提交方案后系统会继续推进。')
        ),
        'primary_action': {
            'label': '确认例外时段' if full_time_exception else '处理安排',
            'action': 'propose',
        },
        'secondary_action': None,
        'detail_preview': item.get('context_summary') or item.get('current_plan_summary') or item.get('description'),
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'entity_ref': {'kind': 'workflow_todo', 'id': item.get('id')},
        'quota_required': item.get('quota_required'),
        'risk_assessment': item.get('risk_assessment') or {},
        'teacher_work_mode': item.get('teacher_work_mode'),
        'teacher_work_mode_label': item.get('teacher_work_mode_label'),
        'kind': 'teacher_exception_workflow' if full_time_exception else 'teacher_workflow',
    }


def _build_admin_scheduling_risk_cases(*, pending_schedule_enrollments, pending_admin_send_workflows):
    cases = []
    for item in pending_schedule_enrollments:
        risk = item.get('risk_assessment') or {}
        if not (risk.get('hard_errors') or risk.get('warnings')):
            continue
        cases.append({
            'title': f'{item.get("student_name") or "学生"} · {item.get("course_name") or "课程"}',
            'summary': risk.get('summary') or item.get('scheduling_complexity_hint'),
            'severity': risk.get('severity') or ('warning' if risk.get('warnings') else 'hard'),
            'recommended_action': risk.get('recommended_action') or 'needs_admin_intervention',
            'entity_ref': {'kind': 'enrollment', 'id': item.get('id')},
            'hard_errors': risk.get('hard_errors') or [],
            'warnings': risk.get('warnings') or [],
            'due_hint': item.get('waiting_since') or item.get('updated_at'),
        })
    for item in pending_admin_send_workflows:
        risk = item.get('risk_assessment') or {}
        if not (risk.get('hard_errors') or risk.get('warnings') or item.get('proposal_warnings')):
            continue
        cases.append({
            'title': item.get('title') or item.get('course_name') or '排课风险',
            'summary': risk.get('summary') or item.get('proposal_warning_summary') or item.get('context_summary'),
            'severity': risk.get('severity') or ('warning' if (risk.get('warnings') or item.get('proposal_warnings')) else 'hard'),
            'recommended_action': risk.get('recommended_action') or 'needs_admin_review',
            'entity_ref': {'kind': 'workflow_todo', 'id': item.get('id')},
            'hard_errors': risk.get('hard_errors') or [],
            'warnings': list(dict.fromkeys((risk.get('warnings') or []) + (item.get('proposal_warnings') or []))),
            'due_hint': item.get('waiting_since') or item.get('updated_at'),
        })
    return _sort_action_items(cases)


def _build_admin_case_view(item, entity_ref, *, status_label, next_step, detail_preview=None, action='review'):
    return {
        'title': f'{item.get("student_name") or "学生"} · {item.get("course_name") or item.get("title") or "排课事项"}',
        'status_label': status_label,
        'next_step': next_step,
        'primary_action': {'label': '查看并处理', 'action': action},
        'secondary_action': None,
        'detail_preview': detail_preview,
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'entity_ref': entity_ref,
        'priority': item.get('priority'),
        'kind': 'admin_scheduling_case',
    }


def _build_scheduling_case_from_enrollment(item):
    risk = item.get('risk_assessment') or {}
    recommended_action = (
        risk.get('recommended_action')
        or ('direct_to_student' if item.get('status') == 'pending_student_confirm' else None)
    )
    case_type = _scheduling_case_type_from_recommended_action(recommended_action)
    status = item.get('next_action_status') or item.get('status')
    status_label = item.get('current_stage_label') or item.get('next_action_label') or '排课处理中'
    current_blocker = risk.get('summary') or item.get('scheduling_complexity_hint') or item.get('context_summary')
    next_actor = item.get('next_action_role') or 'admin'
    next_step = item.get('next_step_hint') or '系统会继续推进该排课事项。'
    entity_ref = {'kind': 'enrollment', 'id': item.get('id')}

    if case_type == SCHEDULING_CASE_TYPE_STUDENT_CLARIFICATION:
        student_view = _student_action_item_from_clarification_enrollment(item)
    elif item.get('status') == 'pending_student_confirm':
        student_view = _student_action_item_from_enrollment(item)
    else:
        student_view = None

    if case_type == SCHEDULING_CASE_TYPE_STUDENT_CLARIFICATION:
        admin_status_label = '待学生补充时间'
    elif case_type == SCHEDULING_CASE_TYPE_TEACHER_EXCEPTION:
        admin_status_label = '待老师确认例外时段'
    elif case_type == SCHEDULING_CASE_TYPE_ADMIN_RISK:
        admin_status_label = '待教务处理风险'
    elif item.get('status') == 'pending_student_confirm':
        admin_status_label = '待学生确认'
    else:
        admin_status_label = '待教务复核'

    admin_view = _build_admin_case_view(
        item,
        entity_ref,
        status_label=admin_status_label,
        next_step=next_step,
        detail_preview=current_blocker,
        action='review',
    )

    return {
        'id': _scheduling_case_id('enrollment', item.get('id')),
        'case_type': case_type,
        'status': status,
        'status_label': status_label,
        'current_blocker': current_blocker,
        'next_actor': next_actor,
        'next_step': next_step,
        'entity_refs': [entity_ref],
        'risk_assessment': risk,
        'recommended_bundle': item.get('recommended_bundle'),
        'candidate_slot_pool': item.get('candidate_slot_pool') or [],
        'student_view': student_view,
        'teacher_view': None,
        'admin_view': admin_view,
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'waiting_since': item.get('waiting_since'),
        'updated_at': item.get('updated_at'),
        'priority': item.get('priority'),
        'student_name': item.get('student_name'),
        'course_name': item.get('course_name'),
        'teacher_name': item.get('teacher_name'),
        'entity_ref': entity_ref,
    }


def _build_scheduling_case_from_workflow(item):
    if item.get('todo_type') != OATodo.TODO_TYPE_ENROLLMENT_REPLAN:
        return None

    risk = item.get('risk_assessment') or {}
    proposal_warnings = item.get('proposal_warnings') or []
    if item.get('workflow_status') == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL:
        case_type = SCHEDULING_CASE_TYPE_TEACHER_EXCEPTION
    elif item.get('workflow_status') == OATodo.WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM:
        case_type = SCHEDULING_CASE_TYPE_DIRECT_PASS
    else:
        case_type = _scheduling_case_type_from_recommended_action(
            risk.get('recommended_action') or (
                'needs_admin_review' if proposal_warnings else 'direct_to_student'
            )
        )

    full_time_exception = (
        case_type == SCHEDULING_CASE_TYPE_TEACHER_EXCEPTION
        and item.get('teacher_work_mode') == 'full_time'
    )
    status_label = (
        '待老师确认例外时段'
        if full_time_exception and item.get('workflow_status') == OATodo.WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL
        else (item.get('workflow_status_label') or '排课处理中')
    )
    current_blocker = (
        risk.get('summary')
        or item.get('proposal_warning_summary')
        or item.get('latest_rejection_text')
        or item.get('context_summary')
        or item.get('description')
    )
    next_step = item.get('next_step_hint') or '系统会继续推进该排课事项。'
    entity_refs = [{'kind': 'workflow_todo', 'id': item.get('id')}]
    if item.get('enrollment_id'):
        entity_refs.append({'kind': 'enrollment', 'id': item.get('enrollment_id')})

    teacher_view = (
        _teacher_action_item_from_workflow(item)
        if item.get('next_action_role') == 'teacher'
        else None
    )
    student_view = (
        _student_action_item_from_workflow(item)
        if item.get('next_action_role') == 'student'
        else None
    )
    admin_view = _build_admin_case_view(
        item,
        {'kind': 'workflow_todo', 'id': item.get('id')},
        status_label=(
            '待老师确认例外时段'
            if case_type == SCHEDULING_CASE_TYPE_TEACHER_EXCEPTION
            else ('待教务处理风险' if case_type == SCHEDULING_CASE_TYPE_ADMIN_RISK else '待教务复核')
        ),
        next_step=next_step,
        detail_preview=current_blocker,
        action='review',
    )

    return {
        'id': _scheduling_case_id('workflow', item.get('id')),
        'case_type': case_type,
        'status': item.get('workflow_status'),
        'status_label': status_label,
        'current_blocker': current_blocker,
        'next_actor': item.get('next_action_role') or 'admin',
        'next_step': next_step,
        'entity_refs': entity_refs,
        'risk_assessment': risk,
        'recommended_bundle': item.get('recommended_bundle'),
        'candidate_slot_pool': item.get('candidate_slot_pool') or [],
        'student_view': student_view,
        'teacher_view': teacher_view,
        'admin_view': admin_view,
        'due_hint': item.get('waiting_since') or item.get('updated_at'),
        'waiting_since': item.get('waiting_since'),
        'updated_at': item.get('updated_at'),
        'priority': item.get('priority'),
        'student_name': item.get('student_name'),
        'course_name': item.get('course_name') or item.get('title'),
        'teacher_name': item.get('teacher_name'),
        'entity_ref': {'kind': 'workflow_todo', 'id': item.get('id')},
    }


def _dedupe_scheduling_cases(items):
    deduped = {}
    for item in items or []:
        if not item:
            continue
        deduped[item['id']] = item
    return _sort_action_items(list(deduped.values()))


def _rename_slot_validation_errors(errors, label):
    return [str(item).replace('可补课时段', label) for item in (errors or [])]


def _annotate_pending_feedback_risk(payloads):
    if not payloads:
        return []

    teacher_counts = {}
    for item in payloads:
        teacher_id = item.get('teacher_id')
        if teacher_id is None:
            continue
        teacher_counts[teacher_id] = teacher_counts.get(teacher_id, 0) + 1

    for item in payloads:
        teacher_id = item.get('teacher_id')
        item['missing_feedback_count_for_teacher_recent'] = teacher_counts.get(teacher_id, 0)
        item['is_repeat_late_teacher'] = teacher_counts.get(teacher_id, 0) >= 2
        item['feedback_delay_days'] = max(int(item.get('feedback_delay_days') or 0), 0)
    return payloads


def _exclude_approved_leave(payloads):
    return [item for item in (payloads or []) if item.get('leave_status') != 'approved']


def _build_leave_case_payloads(actor):
    items = [
        build_leave_request_payload(item, actor)
        for item in LeaveRequest.query.order_by(
            LeaveRequest.created_at.desc(),
            LeaveRequest.id.desc(),
        ).all()
    ]
    return _sort_action_items(items)


def _teacher_students_summary(user):
    enrollments = get_accessible_enrollment_query(user).filter(
        Enrollment.status.in_(['confirmed', 'active', 'pending_student_confirm', 'pending_schedule'])
    ).all()

    students = []
    for enrollment in enrollments:
        info = {
            'name': enrollment.student_name,
            'course': enrollment.course_name,
            'status': enrollment.status,
            'user_id': enrollment.student_profile.user_id if enrollment.student_profile else None,
            'student_profile_id': enrollment.student_profile_id,
        }
        if enrollment.student_profile:
            info['phone'] = enrollment.student_profile.phone
            info['parent_phone'] = enrollment.student_profile.parent_phone
        students.append(info)
    return students


# ========== 登录/登出 ==========


@auth_bp.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    if not username or not password:
        return render_template('auth/login.html', error='请输入用户名和密码')

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return render_template('auth/login.html', error='用户名或密码错误')

    if not user.is_active:
        return render_template('auth/login.html', error='该账号已被禁用')

    login_user(user)
    return _redirect_by_role(user)


def _redirect_by_role(user):
    if user.role == 'admin':
        return redirect('/auth/admin/dashboard')
    if user.role == 'teacher':
        return redirect('/auth/teacher/dashboard')
    if user.role == 'student':
        return redirect('/auth/student/dashboard')
    return redirect('/oa/')


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect('/auth/login')


# ========== 管理员面板 ==========


@auth_bp.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    has_availability = TeacherAvailability.query.filter_by(user_id=current_user.id).count() > 0
    return render_template('auth/admin_dashboard.html', has_availability=has_availability)


@auth_bp.route('/api/admin/stats')
@role_required('admin')
def api_admin_stats():
    from modules.auth.models import StudentProfile

    today = get_business_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    total_users = User.query.count()
    pending_enrollments = Enrollment.query.filter(
        Enrollment.status.in_(['pending_info', 'pending_schedule', 'pending_student_confirm'])
    ).count()
    confirmed_enrollments = Enrollment.query.filter(
        Enrollment.status.in_(['confirmed', 'active', 'completed'])
    ).count()
    week_courses = CourseSchedule.query.filter(
        CourseSchedule.date >= week_start,
        CourseSchedule.date <= week_end,
        CourseSchedule.is_cancelled == False,
    ).count()
    active_students = StudentProfile.query.count()

    return jsonify({
        'success': True,
        'data': {
            'total_users': total_users,
            'pending_enrollments': pending_enrollments,
            'confirmed_enrollments': confirmed_enrollments,
            'week_courses': week_courses,
            'active_students': active_students,
        }
    })


@auth_bp.route('/admin/users')
@role_required('admin')
def manage_users():
    return render_template('auth/manage_users.html')


# ========== 老师面板 ==========


@auth_bp.route('/teacher/dashboard')
@role_required('teacher', 'admin')
def teacher_dashboard():
    teacher_context = _teacher_work_context(current_user)
    return render_template(
        'auth/teacher_dashboard.html',
        has_availability=teacher_context['availability_ready'],
        teacher_work_context=teacher_context,
    )


@auth_bp.route('/api/teacher/my-schedule')
@role_required('teacher', 'admin')
def api_teacher_my_schedule():
    start, end = _resolve_date_range(request.args.get('range', 'week'))
    schedules = _teacher_schedule_query(current_user, start, end).all()
    payload_schedules = [build_schedule_payload(schedule, current_user) for schedule in schedules]

    enrollments = get_accessible_enrollment_query(current_user).filter(
        Enrollment.status.in_(['confirmed', 'active', 'pending_student_confirm', 'pending_schedule'])
    ).all()

    students = []
    for enrollment in enrollments:
        info = {
            'name': enrollment.student_name,
            'course': enrollment.course_name,
            'status': enrollment.status,
            'user_id': enrollment.student_profile.user_id if enrollment.student_profile else None,
            'student_profile_id': enrollment.student_profile_id,
        }
        if enrollment.student_profile:
            info['phone'] = enrollment.student_profile.phone
            info['parent_phone'] = enrollment.student_profile.parent_phone
        students.append(info)

    today = get_business_today()
    upcoming_end = today + timedelta(days=7)
    upcoming = _exclude_approved_leave([
        build_schedule_payload(schedule, current_user)
        for schedule in _teacher_schedule_query(current_user, today, upcoming_end).all()
        if schedule.date and today <= schedule.date <= upcoming_end
    ])
    pending_feedback = [
        payload for payload in [
            build_schedule_payload(schedule, current_user)
            for schedule in _teacher_schedule_query(current_user, end=today).all()
        ]
        if payload.get('next_action_status') == 'waiting_teacher_feedback'
    ]

    return jsonify({
        'success': True,
        'data': {
            'schedules': payload_schedules,
            'students': students,
            'total': len(payload_schedules),
            'upcoming_schedules': upcoming[:10],
            'pending_feedback_schedules': pending_feedback[:10],
            'pending_feedback_count': len(pending_feedback),
        }
    })


@auth_bp.route('/api/teacher/action-center')
@role_required('teacher', 'admin')
def api_teacher_action_center():
    from modules.auth.workflow_services import (
        build_workflow_todo_payload,
        ensure_leave_makeup_workflow,
        list_workflow_todos_for_user,
    )

    today = get_business_today()
    upcoming_end = today + timedelta(days=7)

    orphan_makeup_leaves = LeaveRequest.query.join(
        CourseSchedule, LeaveRequest.schedule_id == CourseSchedule.id
    ).filter(
        LeaveRequest.status == 'approved',
        LeaveRequest.makeup_schedule_id.is_(None),
        _teacher_schedule_identity_filter(CourseSchedule, current_user),
    ).order_by(LeaveRequest.created_at.desc()).all()
    healed_workflows = 0
    for leave_request in orphan_makeup_leaves:
        workflow = ensure_leave_makeup_workflow(leave_request)
        if workflow:
            healed_workflows += 1
    if healed_workflows:
        db.session.commit()

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    workflow_todos_all = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status=None)
    ]
    proposal_workflows = _sort_action_items([
        item for item in workflow_todos
        if item.get('next_action_role') == 'teacher'
        and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
        and _workflow_matches_teacher_actor(item, current_user)
    ])
    tracking_recent_cutoff = today - timedelta(days=14)
    tracking_workflows = _sort_action_items([
        item for item in workflow_todos_all
        if item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
        and _workflow_matches_teacher_actor(item, current_user)
        and item.get('workflow_status') in {
            'waiting_admin_review',
            'waiting_student_confirm',
            'completed',
            'cancelled',
        }
        and (
            item.get('workflow_status') in {'waiting_admin_review', 'waiting_student_confirm'}
            or (
                (
                    _parse_iso_datetime(item.get('updated_at'))
                    or _parse_iso_datetime(item.get('created_at'))
                    or datetime.min
                ).date() >= tracking_recent_cutoff
            )
        )
    ])

    feedback_schedule_payloads = [
        build_schedule_payload(schedule, current_user)
        for schedule in _teacher_schedule_query(current_user, end=today).all()
    ]
    pending_feedback = _sort_action_items([
        item for item in feedback_schedule_payloads
        if item.get('next_action_status') == 'waiting_teacher_feedback'
    ])
    upcoming_schedule_payloads = [
        build_schedule_payload(schedule, current_user)
        for schedule in _teacher_schedule_query(current_user, today, upcoming_end).all()
    ]
    upcoming_schedules = sorted(
        _exclude_approved_leave([
            item for item in upcoming_schedule_payloads
            if item.get('date')
            and today <= date.fromisoformat(item['date']) <= upcoming_end
        ]),
        key=lambda item: (item['date'], item.get('time_start') or '99:99'),
    )

    leave_requests = _sort_action_items([
        build_leave_request_payload(item, current_user)
        for item in LeaveRequest.query.join(
            CourseSchedule, LeaveRequest.schedule_id == CourseSchedule.id
        ).filter(
            LeaveRequest.status == 'pending',
            _teacher_schedule_identity_filter(CourseSchedule, current_user),
        ).order_by(LeaveRequest.created_at.desc()).all()
    ])
    teacher_context = _teacher_work_context(current_user)
    teacher_action_items = _sort_action_items([
        _teacher_action_item_from_workflow(item)
        for item in proposal_workflows
    ])
    scheduling_cases = _dedupe_scheduling_cases(
        [_build_scheduling_case_from_workflow(item) for item in proposal_workflows]
        + [_build_scheduling_case_from_workflow(item) for item in tracking_workflows]
    )

    return jsonify({
        'success': True,
        'data': {
            **teacher_context,
            'availability_ready': teacher_context['availability_ready'],
            'teacher_action_items': teacher_action_items,
            'scheduling_cases': scheduling_cases,
            'proposal_workflows': proposal_workflows,
            'tracking_workflows': tracking_workflows,
            'pending_feedback_schedules': pending_feedback,
            'leave_requests': leave_requests,
            'upcoming_schedules': upcoming_schedules[:10],
            'students': _teacher_students_summary(current_user),
            'counts': {
                'teacher_action_items': len(teacher_action_items),
                'scheduling_cases': len(scheduling_cases),
                'proposal_workflows': len(proposal_workflows),
                'tracking_workflows': len(tracking_workflows),
                'pending_feedback_schedules': len(pending_feedback),
                'leave_requests': len(leave_requests),
                'upcoming_schedules': len(upcoming_schedules),
            },
        },
    })


@auth_bp.route('/api/teacher/my-schedules/by-date')
@role_required('teacher', 'admin')
def api_teacher_my_schedules_by_date():
    start, end, error_response, status_code = _parse_calendar_range()
    if error_response:
        return error_response, status_code

    schedules = _teacher_schedule_query(current_user, start, end).all()
    payloads = _exclude_approved_leave([
        build_schedule_payload(schedule, current_user) for schedule in schedules
    ])
    return jsonify({
        'success': True,
        'data': payloads,
        'total': len(payloads),
    })


# ========== 学生面板 ==========


@auth_bp.route('/student/dashboard')
@role_required('student')
def student_dashboard():
    return render_template('auth/student_dashboard.html')


@auth_bp.route('/api/student/my-info')
@role_required('student')
def api_student_my_info():
    profile = current_user.student_profile
    enrollments = []
    schedules = []
    upcoming_schedules = []
    recent_feedbacks = []
    today = get_business_today()

    if profile:
        enrollments = Enrollment.query.filter(
            Enrollment.student_profile_id == profile.id
        ).order_by(Enrollment.created_at.desc()).all()
        schedules = _student_schedule_query(current_user).order_by(None).order_by(
            CourseSchedule.date.desc(),
            CourseSchedule.time_start.desc(),
        ).limit(50).all()
        upcoming_schedules = _student_schedule_query(
            current_user,
            today,
            today + timedelta(days=90),
        ).limit(20).all()
        recent_feedback_rows = CourseFeedback.query.join(
            CourseSchedule,
            CourseFeedback.schedule_id == CourseSchedule.id,
        ).filter(
            student_schedule_profile_clause(profile.id, schedule_model=CourseSchedule),
            CourseFeedback.status == 'submitted',
        ).order_by(
            CourseFeedback.submitted_at.desc(),
            CourseFeedback.updated_at.desc(),
        ).limit(3).all()
        recent_feedbacks = [
            build_schedule_payload(feedback.schedule, current_user)
            for feedback in recent_feedback_rows
            if feedback.schedule
        ]

    return jsonify({
        'success': True,
        'data': {
            'profile': _student_profile_payload(profile),
            'schedules': [build_schedule_payload(schedule, current_user) for schedule in schedules],
            'upcoming_schedules': [build_schedule_payload(schedule, current_user) for schedule in upcoming_schedules],
            'recent_feedbacks': recent_feedbacks,
            'enrollments': [build_enrollment_payload(enrollment, current_user) for enrollment in enrollments],
        }
    })


@auth_bp.route('/api/student/action-center')
@role_required('student')
def api_student_action_center():
    from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user

    today = get_business_today()
    profile = current_user.student_profile
    if not profile:
        return jsonify({'success': True, 'data': {
            'action_required_workflows': [],
            'tracking_workflows': [],
            'pending_workflows': [],
            'pending_enrollments': [],
            'student_action_items': [],
            'student_tracking_items': [],
            'scheduling_cases': [],
            'upcoming_schedules': [],
            'leave_requests': [],
            'counts': {
                'action_required_workflows': 0,
                'tracking_workflows': 0,
                'action_required_items': 0,
                'pending_workflows': 0,
                'pending_enrollments': 0,
                'student_action_items': 0,
                'scheduling_cases': 0,
                'leave_requests': 0,
                'upcoming_schedules': 0,
            },
        }})

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    pending_workflows = _sort_action_items(workflow_todos)
    action_required_workflows = _sort_action_items([
        item for item in pending_workflows if item.get('next_action_role') == 'student'
    ])
    tracking_workflows = _sort_action_items([
        item for item in pending_workflows if item.get('next_action_role') != 'student'
    ])
    workflow_enrollment_ids = {
        item.get('enrollment_id')
        for item in action_required_workflows
        if item.get('todo_type') == 'enrollment_replan'
        and item.get('next_action_role') == 'student'
        and item.get('enrollment_id')
    }
    enrollments = [
        build_enrollment_payload(enrollment, current_user)
        for enrollment in Enrollment.query.filter(
            Enrollment.student_profile_id == profile.id
        ).order_by(Enrollment.created_at.desc()).all()
    ]
    pending_enrollments = _sort_action_items([
        item for item in enrollments
        if (
            item.get('status') == 'pending_student_confirm'
            or item.get('next_action_status') == 'waiting_student_clarification'
        )
        and item.get('id') not in workflow_enrollment_ids
    ])
    student_action_items, student_tracking_items = _build_student_action_items(
        action_required_workflows=action_required_workflows,
        pending_enrollments=pending_enrollments,
        tracking_workflows=tracking_workflows,
    )
    scheduling_cases = _dedupe_scheduling_cases(
        [_build_scheduling_case_from_workflow(item) for item in pending_workflows]
        + [_build_scheduling_case_from_enrollment(item) for item in pending_enrollments]
    )

    upcoming_schedules = [
        build_schedule_payload(schedule, current_user)
        for schedule in _student_schedule_query(current_user, today, today + timedelta(days=30)).limit(20).all()
    ]
    leave_requests = _sort_action_items([
        build_leave_request_payload(item, current_user)
        for item in LeaveRequest.query.join(
            Enrollment, LeaveRequest.enrollment_id == Enrollment.id
        ).filter(
            Enrollment.student_profile_id == profile.id
        ).order_by(LeaveRequest.created_at.desc()).all()
    ])

    return jsonify({
        'success': True,
        'data': {
            'action_required_workflows': action_required_workflows,
            'tracking_workflows': tracking_workflows,
            'pending_workflows': pending_workflows,
            'pending_enrollments': pending_enrollments,
            'student_action_items': student_action_items,
            'student_tracking_items': student_tracking_items,
            'scheduling_cases': scheduling_cases,
            'upcoming_schedules': upcoming_schedules,
            'leave_requests': leave_requests,
            'counts': {
                'action_required_workflows': len(action_required_workflows),
                'tracking_workflows': len(tracking_workflows),
                'action_required_items': len(action_required_workflows) + len(pending_enrollments),
                'pending_workflows': len(pending_workflows),
                'pending_enrollments': len(pending_enrollments),
                'student_action_items': len(student_action_items),
                'scheduling_cases': len(scheduling_cases),
                'leave_requests': len(leave_requests),
                'upcoming_schedules': len(upcoming_schedules),
            },
        },
    })


@auth_bp.route('/api/admin/action-center')
@role_required('admin')
def api_admin_action_center():
    from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user

    today = get_business_today()

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    waiting_teacher_proposal_workflows = _sort_action_items([
        item for item in workflow_todos
        if item.get('next_action_role') == 'teacher'
        and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
    ])
    pending_admin_send = _sort_action_items([
        item for item in workflow_todos
        if item.get('next_action_role') == 'admin'
        and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
    ])
    waiting_student_confirm_workflows = _sort_action_items([
        item for item in workflow_todos
        if item.get('next_action_role') == 'student'
        and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
    ])
    workflow_enrollment_ids = {
        item.get('enrollment_id')
        for item in waiting_student_confirm_workflows
        if item.get('todo_type') == 'enrollment_replan' and item.get('enrollment_id')
    }
    scheduling_workflow_enrollment_ids = {
        item.get('enrollment_id')
        for item in workflow_todos
        if item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and item.get('enrollment_id')
    }

    pending_schedule_enrollments = _sort_action_items([
        build_enrollment_payload(enrollment, current_user)
        for enrollment in get_accessible_enrollment_query(current_user).filter(
            Enrollment.status.in_(['pending_info', 'pending_schedule'])
        ).order_by(Enrollment.updated_at.desc(), Enrollment.created_at.desc()).all()
    ])
    waiting_student_confirm_enrollments = _sort_action_items([
        build_enrollment_payload(enrollment, current_user)
        for enrollment in get_accessible_enrollment_query(current_user).filter(
            Enrollment.status == 'pending_student_confirm'
        ).order_by(Enrollment.updated_at.desc(), Enrollment.created_at.desc()).all()
        if enrollment.id not in workflow_enrollment_ids
    ])
    waiting_student_confirm_items = _sort_action_items(
        [
            {**item, 'kind': 'workflow_waiting_confirm'}
            for item in waiting_student_confirm_workflows
        ]
        + [
            {**item, 'kind': 'pending_enrollment'}
            for item in waiting_student_confirm_enrollments
        ]
    )
    pending_leave_requests = _sort_action_items([
        build_leave_request_payload(item, current_user)
        for item in LeaveRequest.query.filter(
            LeaveRequest.status == 'pending'
        ).order_by(LeaveRequest.created_at.desc()).all()
    ])
    pending_feedback_schedules = _sort_action_items(_annotate_pending_feedback_risk([
        build_schedule_payload(schedule, current_user)
        for schedule in CourseSchedule.query.filter(
            CourseSchedule.date <= today,
            CourseSchedule.is_cancelled == False,
        ).order_by(CourseSchedule.date.desc(), CourseSchedule.time_start.asc()).all()
        if schedule_requires_course_feedback(schedule)
        and _schedule_has_started(schedule)
        and not (schedule.feedback and schedule.feedback.status == 'submitted')
        and not (_latest_leave_request(schedule) and _latest_leave_request(schedule).status == 'approved')
    ]))
    leave_cases = _build_leave_case_payloads(current_user)
    scheduling_risk_cases = _build_admin_scheduling_risk_cases(
        pending_schedule_enrollments=pending_schedule_enrollments,
        pending_admin_send_workflows=pending_admin_send,
    )
    scheduling_cases = _dedupe_scheduling_cases(
        [
            _build_scheduling_case_from_enrollment(item)
            for item in pending_schedule_enrollments
            if item.get('id') not in scheduling_workflow_enrollment_ids
        ]
        + [
            _build_scheduling_case_from_workflow(item)
            for item in workflow_todos
            if item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        ]
        + [
            _build_scheduling_case_from_enrollment(item)
            for item in waiting_student_confirm_enrollments
            if item.get('id') not in scheduling_workflow_enrollment_ids
        ]
    )

    return jsonify({
        'success': True,
        'data': {
            'pending_schedule_enrollments': pending_schedule_enrollments,
            'waiting_teacher_proposal_workflows': waiting_teacher_proposal_workflows,
            'pending_admin_send_workflows': pending_admin_send,
            'waiting_student_confirm_workflows': waiting_student_confirm_workflows,
            'waiting_student_confirm_enrollments': waiting_student_confirm_enrollments,
            'waiting_student_confirm_items': waiting_student_confirm_items,
            'pending_leave_requests': pending_leave_requests,
            'leave_cases': leave_cases,
            'scheduling_risk_cases': scheduling_risk_cases,
            'scheduling_cases': scheduling_cases,
            'pending_feedback_schedules': pending_feedback_schedules,
            'counts': {
                'pending_schedule_enrollments': len(pending_schedule_enrollments),
                'waiting_teacher_proposal_workflows': len(waiting_teacher_proposal_workflows),
                'pending_admin_send_workflows': len(pending_admin_send),
                'waiting_student_confirm_workflows': len(waiting_student_confirm_workflows),
                'waiting_student_confirm_enrollments': len(waiting_student_confirm_enrollments),
                'waiting_student_confirm_items': len(waiting_student_confirm_items),
                'pending_leave_requests': len(pending_leave_requests),
                'leave_cases': len(leave_cases),
                'scheduling_risk_cases': len(scheduling_risk_cases),
                'scheduling_cases': len(scheduling_cases),
                'pending_feedback_schedules': len(pending_feedback_schedules),
            },
        },
    })


def _student_scheduling_cases_for_current_user():
    from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user

    profile = current_user.student_profile
    if not profile:
        return []

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    pending_workflows = _sort_action_items(workflow_todos)
    workflow_enrollment_ids = {
        item.get('enrollment_id')
        for item in pending_workflows
        if item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and item.get('enrollment_id')
    }
    enrollments = [
        build_enrollment_payload(enrollment, current_user)
        for enrollment in Enrollment.query.filter(
            Enrollment.student_profile_id == profile.id
        ).order_by(Enrollment.created_at.desc()).all()
    ]
    pending_enrollments = _sort_action_items([
        item for item in enrollments
        if (
            item.get('status') == 'pending_student_confirm'
            or item.get('next_action_status') == 'waiting_student_clarification'
        )
        and item.get('id') not in workflow_enrollment_ids
    ])
    return _dedupe_scheduling_cases(
        [_build_scheduling_case_from_workflow(item) for item in pending_workflows]
        + [_build_scheduling_case_from_enrollment(item) for item in pending_enrollments]
    )


def _teacher_scheduling_cases_for_current_user():
    from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    relevant = _sort_action_items([
        item for item in workflow_todos
        if item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        and (
            item.get('next_action_role') == 'teacher'
            and _workflow_matches_teacher_actor(item, current_user)
            or item.get('next_action_role') != 'teacher'
        )
    ])
    return _dedupe_scheduling_cases([
        _build_scheduling_case_from_workflow(item)
        for item in relevant
    ])


def _admin_scheduling_cases_for_current_user():
    from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    scheduling_workflow_enrollment_ids = {
        item.get('enrollment_id')
        for item in workflow_todos
        if item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN and item.get('enrollment_id')
    }
    pending_schedule_enrollments = _sort_action_items([
        build_enrollment_payload(enrollment, current_user)
        for enrollment in get_accessible_enrollment_query(current_user).filter(
            Enrollment.status.in_(['pending_info', 'pending_schedule'])
        ).order_by(Enrollment.updated_at.desc(), Enrollment.created_at.desc()).all()
    ])
    waiting_student_confirm_enrollments = _sort_action_items([
        build_enrollment_payload(enrollment, current_user)
        for enrollment in get_accessible_enrollment_query(current_user).filter(
            Enrollment.status == 'pending_student_confirm'
        ).order_by(Enrollment.updated_at.desc(), Enrollment.created_at.desc()).all()
        if enrollment.id not in scheduling_workflow_enrollment_ids
    ])
    return _dedupe_scheduling_cases(
        [
            _build_scheduling_case_from_enrollment(item)
            for item in pending_schedule_enrollments
            if item.get('id') not in scheduling_workflow_enrollment_ids
        ]
        + [
            _build_scheduling_case_from_workflow(item)
            for item in workflow_todos
            if item.get('todo_type') == OATodo.TODO_TYPE_ENROLLMENT_REPLAN
        ]
        + [
            _build_scheduling_case_from_enrollment(item)
            for item in waiting_student_confirm_enrollments
            if item.get('id') not in scheduling_workflow_enrollment_ids
        ]
    )


def _current_user_scheduling_cases():
    if current_user.role == 'student':
        return _student_scheduling_cases_for_current_user()
    if current_user.role == 'teacher':
        return _teacher_scheduling_cases_for_current_user()
    if current_user.role == 'admin':
        return _admin_scheduling_cases_for_current_user()
    return []


def _find_current_scheduling_case(case_id):
    for item in _current_user_scheduling_cases():
        if item.get('id') == case_id:
            return item
    return None


@auth_bp.route('/api/scheduling-cases')
@login_required
def api_list_scheduling_cases():
    cases = _current_user_scheduling_cases()
    return jsonify({
        'success': True,
        'data': cases,
        'total': len(cases),
    })


@auth_bp.route('/api/scheduling-cases/<case_id>')
@login_required
def api_get_scheduling_case(case_id):
    payload = _find_current_scheduling_case(case_id)
    if not payload:
        return jsonify({'success': False, 'error': '排课事项不存在或你无权查看'}), 404
    return jsonify({'success': True, 'data': payload})


@auth_bp.route('/api/scheduling-cases/<case_id>/actions/<action>', methods=['POST'])
@login_required
def api_execute_scheduling_case_action(case_id, action):
    from modules.auth.workflow_services import (
        get_workflow_todo,
        student_confirm_workflow_todo,
        student_reject_workflow_todo,
    )

    case_payload = _find_current_scheduling_case(case_id)
    if not case_payload:
        return jsonify({'success': False, 'error': '排课事项不存在或你无权操作'}), 404

    data = request.get_json(silent=True) or {}
    entity_ref = case_payload.get('entity_ref') or {}
    kind = entity_ref.get('kind')
    entity_id = entity_ref.get('id')

    if current_user.role == 'student' and action == 'confirm':
        if kind == 'workflow_todo':
            todo = get_workflow_todo(entity_id)
            if not todo:
                return jsonify({'success': False, 'error': '当前方案已失效，请查看最新安排'}), 404
            result = student_confirm_workflow_todo(todo, current_user)
            status_code = result.pop('status_code', 200)
            return jsonify(result), status_code
        if kind == 'enrollment':
            success, message, created_count = student_confirm_schedule(entity_id)
            if success:
                return jsonify({'success': True, 'message': message, 'created_count': created_count})
            return jsonify({'success': False, 'error': message}), 400

    if current_user.role == 'student' and action == 'reject':
        message = data.get('message', '')
        if kind == 'workflow_todo':
            todo = get_workflow_todo(entity_id)
            if not todo:
                return jsonify({'success': False, 'error': '当前方案已失效，请查看最新安排'}), 404
            result = student_reject_workflow_todo(todo, current_user, message)
            status_code = result.pop('status_code', 200)
            return jsonify(result), status_code
        if kind == 'enrollment':
            success, error_message = reject_enrollment_schedule(
                entity_id,
                message or '学生对排课方案有疑问，请查看。',
                actor_user_id=current_user.id,
            )
            if success:
                return jsonify({'success': True, 'message': error_message})
            return jsonify({'success': False, 'error': error_message}), 400

    return jsonify({'success': False, 'error': '当前排课事项暂不支持该动作'}), 400


@auth_bp.route('/api/student/my-schedules/by-date')
@role_required('student')
def api_student_my_schedules_by_date():
    start, end, error_response, status_code = _parse_calendar_range()
    if error_response:
        return error_response, status_code

    schedules = _student_schedule_query(current_user, start, end).all()
    return jsonify({
        'success': True,
        'data': [build_schedule_payload(schedule, current_user) for schedule in schedules],
        'total': len(schedules),
    })


# ========== 用户管理 API ==========


@auth_bp.route('/api/users', methods=['GET'])
@role_required('admin')
def api_list_users():
    role = request.args.get('role')
    query = User.query
    if role:
        query = query.filter_by(role=role)
    users = query.order_by(User.created_at.desc()).all()
    return jsonify({'success': True, 'data': [u.to_dict() for u in users]})


@auth_bp.route('/api/users', methods=['POST'])
@role_required('admin')
def api_create_user():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    username = data.get('username', '').strip()
    display_name = data.get('display_name', '').strip()
    password = data.get('password', '') or 'scf123'
    role = data.get('role', 'teacher')
    phone = data.get('phone', '').strip()
    try:
        teacher_work_mode = _normalize_teacher_work_mode(data.get('teacher_work_mode'))
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    default_working_template, template_errors = _validate_available_slot_entries(data.get('default_working_template'))
    if template_errors:
        return jsonify({'success': False, 'error': '；'.join(template_errors), 'errors': template_errors}), 400

    if not username or not display_name:
        return jsonify({'success': False, 'error': '用户名和显示名称为必填项'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': '用户名已存在'}), 409

    user = User(
        username=username,
        display_name=display_name,
        role=role,
        phone=phone or None,
        teacher_work_mode=teacher_work_mode,
        default_working_template_json=(
            json.dumps(default_working_template, ensure_ascii=False)
            if teacher_work_mode == 'full_time' and default_working_template
            else None
        ),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'data': user.to_dict()}), 201


@auth_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@role_required('admin')
def api_update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    if 'display_name' in data:
        user.display_name = data['display_name']
    if 'role' in data:
        user.role = data['role']
    if 'phone' in data:
        user.phone = data['phone']
    if 'teacher_work_mode' in data:
        try:
            user.teacher_work_mode = _normalize_teacher_work_mode(data.get('teacher_work_mode'))
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
    if 'default_working_template' in data:
        default_working_template, template_errors = _validate_available_slot_entries(data.get('default_working_template'))
        if template_errors:
            return jsonify({'success': False, 'error': '；'.join(template_errors), 'errors': template_errors}), 400
        user.default_working_template_json = (
            json.dumps(default_working_template, ensure_ascii=False)
            if user.teacher_work_mode == 'full_time' and default_working_template
            else None
        )
    if 'is_active' in data:
        user.is_active = data['is_active']
    if data.get('password'):
        user.set_password(data['password'])

    db.session.commit()
    return jsonify({'success': True, 'data': user.to_dict()})


@auth_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def api_delete_user(user_id):
    success, message = delete_student_user_hard(user_id)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 404 if message == '用户不存在' else 400


@auth_bp.route('/api/users/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def api_toggle_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'data': user.to_dict()})


@auth_bp.route('/api/seed-staff', methods=['POST'])
@role_required('admin')
def api_seed_staff():
    count = seed_staff_accounts()
    return jsonify({'success': True, 'message': f'已创建 {count} 个账号', 'created': count})


# ========== 老师可用时间 ==========


@auth_bp.route('/teacher/availability')
@role_required('teacher', 'admin')
def teacher_availability_page():
    if current_user.role == 'admin':
        teachers = User.query.filter(User.role.in_(['teacher', 'admin'])).all()
    else:
        teachers = [current_user]
    return render_template('auth/teacher_availability.html', teachers=teachers)


@auth_bp.route('/api/teacher/<int:teacher_id>/availability', methods=['GET'])
@role_required('teacher', 'admin')
def api_get_teacher_availability(teacher_id):
    user = db.session.get(User, teacher_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404
    if not _teacher_can_manage_availability(teacher_id):
        return jsonify({'success': False, 'error': '无权访问该教师时间设置'}), 403

    teacher_context = _teacher_work_context(user)
    slots = TeacherAvailability.query.filter_by(user_id=teacher_id).all()
    available = []
    preferred = []
    for slot in slots:
        item = {'day': slot.day_of_week, 'start': slot.time_start, 'end': slot.time_end}
        if slot.is_preferred:
            preferred.append(item)
        else:
            available.append(item)
    if teacher_context['teacher_work_mode'] == 'full_time':
        available = teacher_context['default_working_template']
        preferred = []
    return jsonify({
        'success': True,
        'data': {
            'available': available,
            'preferred': preferred,
            **teacher_context,
        },
    })


@auth_bp.route('/api/teacher/<int:teacher_id>/availability', methods=['POST'])
@role_required('teacher', 'admin')
def api_set_teacher_availability(teacher_id):
    user = db.session.get(User, teacher_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404
    if not _teacher_can_manage_availability(teacher_id):
        return jsonify({'success': False, 'error': '无权修改该教师时间设置'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    try:
        teacher_work_mode = _normalize_teacher_work_mode(data.get('teacher_work_mode'))
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    if teacher_work_mode == 'full_time':
        default_working_template, template_errors = _validate_available_slot_entries(data.get('default_working_template'))
        if template_errors:
            errors = _rename_slot_validation_errors(template_errors, '默认工作时段')
            return jsonify({'success': False, 'error': '；'.join(errors), 'errors': errors}), 400

        TeacherAvailability.query.filter_by(user_id=teacher_id).delete()
        user.teacher_work_mode = teacher_work_mode
        user.default_working_template_json = (
            json.dumps(default_working_template, ensure_ascii=False)
            if default_working_template else None
        )
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '已切换为全职老师统一工作模板',
            'data': _teacher_work_context(user),
        })

    available_slots, available_errors = _validate_available_slot_entries(data.get('available'))
    preferred_slots, preferred_errors = _validate_available_slot_entries(data.get('preferred'))
    errors = (
        _rename_slot_validation_errors(available_errors, '可用时间')
        + _rename_slot_validation_errors(preferred_errors, '偏好时间')
    )
    if errors:
        return jsonify({'success': False, 'error': '；'.join(errors), 'errors': errors}), 400

    TeacherAvailability.query.filter_by(user_id=teacher_id).delete()
    user.teacher_work_mode = teacher_work_mode
    user.default_working_template_json = None

    for slot_data in available_slots:
        db.session.add(TeacherAvailability(
            user_id=teacher_id,
            day_of_week=slot_data['day'],
            time_start=slot_data['start'],
            time_end=slot_data['end'],
            is_preferred=False,
        ))
    for slot_data in preferred_slots:
        db.session.add(TeacherAvailability(
            user_id=teacher_id,
            day_of_week=slot_data['day'],
            time_start=slot_data['start'],
            time_end=slot_data['end'],
            is_preferred=True,
        ))

    db.session.commit()
    return jsonify({
        'success': True,
        'message': '保存成功',
        'data': _teacher_work_context(user),
    })


# ========== 课程反馈 API ==========


@auth_bp.route('/api/schedules/<int:schedule_id>/feedback', methods=['GET'])
@login_required
def api_get_schedule_feedback(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    if not user_can_access_schedule(current_user, schedule):
        return jsonify({'success': False, 'error': '无权查看该课程反馈'}), 403

    feedback = schedule.feedback
    if current_user.role == 'student' and (not feedback or feedback.status != 'submitted'):
        return jsonify({'success': True, 'data': None})

    return jsonify({'success': True, 'data': build_feedback_payload(feedback, current_user)})


@auth_bp.route('/api/schedules/<int:schedule_id>/feedback', methods=['POST'])
@role_required('teacher', 'admin')
def api_save_schedule_feedback(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    permission_error = _feedback_permission_error(schedule)
    if permission_error:
        return permission_error

    data = request.get_json() or {}
    success, message, feedback = save_course_feedback(schedule, current_user.id, data, submit=False)
    if not success:
        return jsonify({'success': False, 'error': message}), 400
    return jsonify({'success': True, 'message': message, 'data': build_feedback_payload(feedback, current_user)})


@auth_bp.route('/api/schedules/<int:schedule_id>/feedback/submit', methods=['POST'])
@role_required('teacher', 'admin')
def api_submit_schedule_feedback(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    permission_error = _feedback_permission_error(schedule)
    if permission_error:
        return permission_error

    data = request.get_json() or {}
    success, message, feedback = save_course_feedback(schedule, current_user.id, data, submit=True)
    if not success:
        return jsonify({'success': False, 'error': message}), 400
    return jsonify({'success': True, 'message': message, 'data': build_feedback_payload(feedback, current_user)})
