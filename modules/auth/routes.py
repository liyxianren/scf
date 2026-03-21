from calendar import monthrange
from datetime import date, datetime, timedelta

from flask import jsonify, redirect, render_template, request
from flask_login import current_user, login_user, login_required, logout_user

from extensions import db
from modules.auth import auth_bp
from modules.auth.decorators import role_required
from modules.auth.models import Enrollment, LeaveRequest, TeacherAvailability, User
from modules.auth.services import (
    _latest_leave_request,
    _schedule_has_started,
    build_enrollment_payload,
    build_feedback_payload,
    build_leave_request_payload,
    build_schedule_payload,
    delete_student_user_hard,
    get_accessible_enrollment_query,
    get_business_today,
    save_course_feedback,
    seed_staff_accounts,
    user_can_access_schedule,
)
from modules.oa.models import CourseSchedule


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
    if not schedule or schedule.teacher_id != current_user.id:
        return jsonify({'success': False, 'error': '无权提交该课程反馈'}), 403
    if getattr(schedule, 'feedback', None) and schedule.feedback.status == 'submitted':
        return jsonify({'success': False, 'error': '该课程反馈已提交'}), 400
    latest_leave = _latest_leave_request(schedule)
    if latest_leave and latest_leave.status == 'approved':
        return jsonify({'success': False, 'error': '该课程已批准请假，不能提交反馈'}), 400
    if not _schedule_has_started(schedule):
        return jsonify({'success': False, 'error': '课程尚未开始，暂不能提交反馈'}), 400
    return None


def _teacher_schedule_query(user, start, end):
    return CourseSchedule.query.filter(
        CourseSchedule.teacher_id == user.id,
        CourseSchedule.date >= start,
        CourseSchedule.date <= end,
    ).order_by(CourseSchedule.date, CourseSchedule.time_start)


def _student_schedule_query(user, start=None, end=None):
    profile = user.student_profile
    if not profile:
        return CourseSchedule.query.filter(False)

    query = CourseSchedule.query.join(
        Enrollment, CourseSchedule.enrollment_id == Enrollment.id
    ).filter(Enrollment.student_profile_id == profile.id)

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
    has_availability = TeacherAvailability.query.filter_by(user_id=current_user.id).count() > 0
    return render_template('auth/teacher_dashboard.html', has_availability=has_availability)


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
    upcoming = [
        payload for payload in payload_schedules
        if today <= date.fromisoformat(payload['date']) <= upcoming_end
    ]
    pending_feedback = [
        payload for payload in payload_schedules
        if payload.get('can_submit_feedback')
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
    from modules.auth.workflow_services import build_workflow_todo_payload, list_workflow_todos_for_user

    today = get_business_today()
    upcoming_end = today + timedelta(days=7)

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    proposal_workflows = _sort_action_items([
        item for item in workflow_todos
        if item.get('next_action_role') == 'teacher'
        and item.get('todo_type') in {'enrollment_replan', 'leave_makeup'}
    ])

    schedule_payloads = [
        build_schedule_payload(schedule, current_user)
        for schedule in _teacher_schedule_query(current_user, today - timedelta(days=30), upcoming_end).all()
    ]
    pending_feedback = _sort_action_items([
        item for item in schedule_payloads
        if item.get('next_action_status') == 'waiting_teacher_feedback'
    ])
    upcoming_schedules = sorted(
        [
            item for item in schedule_payloads
            if item.get('date')
            and today <= date.fromisoformat(item['date']) <= upcoming_end
        ],
        key=lambda item: (item['date'], item.get('time_start') or '99:99'),
    )

    leave_requests = _sort_action_items([
        build_leave_request_payload(item, current_user)
        for item in LeaveRequest.query.join(
            CourseSchedule, LeaveRequest.schedule_id == CourseSchedule.id
        ).filter(
            CourseSchedule.teacher_id == current_user.id,
            LeaveRequest.status == 'pending',
        ).order_by(LeaveRequest.created_at.desc()).all()
    ])

    return jsonify({
        'success': True,
        'data': {
            'availability_ready': TeacherAvailability.query.filter_by(user_id=current_user.id).count() > 0,
            'proposal_workflows': proposal_workflows,
            'pending_feedback_schedules': pending_feedback,
            'leave_requests': leave_requests,
            'upcoming_schedules': upcoming_schedules[:10],
            'students': _teacher_students_summary(current_user),
            'counts': {
                'proposal_workflows': len(proposal_workflows),
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
    return jsonify({
        'success': True,
        'data': [build_schedule_payload(schedule, current_user) for schedule in schedules],
        'total': len(schedules),
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

    if profile:
        enrollments = Enrollment.query.filter(
            Enrollment.student_profile_id == profile.id
        ).order_by(Enrollment.created_at.desc()).all()
        schedules = _student_schedule_query(current_user).order_by(
            CourseSchedule.date.desc(),
            CourseSchedule.time_start.desc(),
        ).limit(50).all()

    return jsonify({
        'success': True,
        'data': {
            'profile': profile.to_dict() if profile else None,
            'schedules': [build_schedule_payload(schedule, current_user) for schedule in schedules],
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
            'pending_workflows': [],
            'pending_enrollments': [],
            'upcoming_schedules': [],
            'leave_requests': [],
            'counts': {
                'pending_workflows': 0,
                'pending_enrollments': 0,
                'leave_requests': 0,
                'upcoming_schedules': 0,
            },
        }})

    workflow_todos = [
        build_workflow_todo_payload(todo, current_user)
        for todo in list_workflow_todos_for_user(current_user, status='open')
    ]
    pending_workflows = _sort_action_items([
        item for item in workflow_todos if item.get('next_action_role') == 'student'
    ])
    workflow_enrollment_ids = {
        item.get('enrollment_id')
        for item in pending_workflows
        if item.get('todo_type') == 'enrollment_replan' and item.get('enrollment_id')
    }

    enrollments = [
        build_enrollment_payload(enrollment, current_user)
        for enrollment in Enrollment.query.filter(
            Enrollment.student_profile_id == profile.id
        ).order_by(Enrollment.created_at.desc()).all()
    ]
    pending_enrollments = _sort_action_items([
        item for item in enrollments
        if item.get('status') == 'pending_student_confirm' and item.get('id') not in workflow_enrollment_ids
    ])

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
            'pending_workflows': pending_workflows,
            'pending_enrollments': pending_enrollments,
            'upcoming_schedules': upcoming_schedules,
            'leave_requests': leave_requests,
            'counts': {
                'pending_workflows': len(pending_workflows),
                'pending_enrollments': len(pending_enrollments),
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
    pending_leave_requests = _sort_action_items([
        build_leave_request_payload(item, current_user)
        for item in LeaveRequest.query.filter(
            LeaveRequest.status == 'pending'
        ).order_by(LeaveRequest.created_at.desc()).all()
    ])
    pending_feedback_schedules = _sort_action_items([
        build_schedule_payload(schedule, current_user)
        for schedule in CourseSchedule.query.filter(
            CourseSchedule.date <= today
        ).order_by(CourseSchedule.date.desc(), CourseSchedule.time_start.asc()).all()
        if _schedule_has_started(schedule)
        and not (schedule.feedback and schedule.feedback.status == 'submitted')
        and not (_latest_leave_request(schedule) and _latest_leave_request(schedule).status == 'approved')
    ])

    return jsonify({
        'success': True,
        'data': {
            'pending_schedule_enrollments': pending_schedule_enrollments,
            'waiting_teacher_proposal_workflows': waiting_teacher_proposal_workflows,
            'pending_admin_send_workflows': pending_admin_send,
            'waiting_student_confirm_workflows': waiting_student_confirm_workflows,
            'waiting_student_confirm_enrollments': waiting_student_confirm_enrollments,
            'pending_leave_requests': pending_leave_requests,
            'pending_feedback_schedules': pending_feedback_schedules,
            'counts': {
                'pending_schedule_enrollments': len(pending_schedule_enrollments),
                'waiting_teacher_proposal_workflows': len(waiting_teacher_proposal_workflows),
                'pending_admin_send_workflows': len(pending_admin_send),
                'waiting_student_confirm_workflows': len(waiting_student_confirm_workflows),
                'waiting_student_confirm_enrollments': len(waiting_student_confirm_enrollments),
                'pending_leave_requests': len(pending_leave_requests),
                'pending_feedback_schedules': len(pending_feedback_schedules),
            },
        },
    })


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

    if not username or not display_name:
        return jsonify({'success': False, 'error': '用户名和显示名称为必填项'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': '用户名已存在'}), 409

    user = User(username=username, display_name=display_name, role=role, phone=phone or None)
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

    slots = TeacherAvailability.query.filter_by(user_id=teacher_id).all()
    available = []
    preferred = []
    for slot in slots:
        item = {'day': slot.day_of_week, 'start': slot.time_start, 'end': slot.time_end}
        if slot.is_preferred:
            preferred.append(item)
        else:
            available.append(item)
    return jsonify({'success': True, 'data': {'available': available, 'preferred': preferred}})


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

    TeacherAvailability.query.filter_by(user_id=teacher_id).delete()

    for slot_data in data.get('available', []):
        db.session.add(TeacherAvailability(
            user_id=teacher_id,
            day_of_week=slot_data['day'],
            time_start=slot_data['start'],
            time_end=slot_data['end'],
            is_preferred=False,
        ))
    for slot_data in data.get('preferred', []):
        db.session.add(TeacherAvailability(
            user_id=teacher_id,
            day_of_week=slot_data['day'],
            time_start=slot_data['start'],
            time_end=slot_data['end'],
            is_preferred=True,
        ))

    db.session.commit()
    return jsonify({'success': True, 'message': '保存成功'})


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
