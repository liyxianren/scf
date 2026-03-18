import json
from datetime import date, timedelta
from flask import render_template, jsonify, request, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from modules.auth.models import User, TeacherAvailability
from modules.auth.services import seed_staff_accounts
from modules.auth.decorators import role_required

from modules.auth import auth_bp


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
    elif user.role == 'teacher':
        return redirect('/auth/teacher/dashboard')
    elif user.role == 'student':
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
    from modules.auth.models import Enrollment, StudentProfile
    from modules.oa.models import CourseSchedule

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    total_users = User.query.count()
    pending_enrollments = Enrollment.query.filter(
        Enrollment.status.in_(['pending_info', 'pending_schedule', 'pending_student_confirm'])).count()
    confirmed_enrollments = Enrollment.query.filter_by(status='confirmed').count()
    week_courses = CourseSchedule.query.filter(
        CourseSchedule.date >= week_start,
        CourseSchedule.date <= week_end).count()
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
@login_required
def teacher_dashboard():
    has_availability = TeacherAvailability.query.filter_by(user_id=current_user.id).count() > 0
    return render_template('auth/teacher_dashboard.html', has_availability=has_availability)


@auth_bp.route('/api/teacher/my-schedule')
@login_required
def api_teacher_my_schedule():
    from modules.oa.models import CourseSchedule
    from modules.auth.models import Enrollment, StudentProfile

    teacher_name = current_user.display_name
    today = date.today()
    range_param = request.args.get('range', 'week')

    if range_param == 'month':
        import calendar
        _, last_day = calendar.monthrange(today.year, today.month)
        start = today.replace(day=1)
        end = today.replace(day=last_day)
    elif range_param == 'all':
        start = today
        end = today + timedelta(days=365)
    else:  # week
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

    schedules = CourseSchedule.query.filter(
        CourseSchedule.teacher == teacher_name,
        CourseSchedule.date >= start,
        CourseSchedule.date <= end
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    enrollments = Enrollment.query.filter_by(teacher_id=current_user.id).filter(
        Enrollment.status.in_(['confirmed', 'active'])).all()

    # 学生联系方式
    students = []
    for e in enrollments:
        info = {'name': e.student_name, 'course': e.course_name, 'status': e.status}
        if e.student_profile:
            info['phone'] = e.student_profile.phone
            info['parent_phone'] = e.student_profile.parent_phone
        students.append(info)

    return jsonify({
        'success': True,
        'data': {
            'schedules': [s.to_dict() for s in schedules],
            'students': students,
            'total': len(schedules),
        }
    })


# ========== 学生面板 ==========

@auth_bp.route('/student/dashboard')
@login_required
def student_dashboard():
    return render_template('auth/student_dashboard.html')


@auth_bp.route('/api/student/my-info')
@login_required
def api_student_my_info():
    from modules.oa.models import CourseSchedule
    from modules.auth.models import Enrollment

    profile = current_user.student_profile
    student_name = current_user.display_name

    # 查课表
    schedules = CourseSchedule.query.filter(
        CourseSchedule.students.contains(student_name)
    ).order_by(CourseSchedule.date.desc()).limit(50).all()

    # 查报名
    enrollments = Enrollment.query.filter(
        Enrollment.student_name == student_name
    ).all()

    return jsonify({
        'success': True,
        'data': {
            'profile': profile.to_dict() if profile else None,
            'schedules': [s.to_dict() for s in schedules],
            'enrollments': [{
                'id': e.id,
                'course_name': e.course_name,
                'teacher_name': e.teacher.display_name if e.teacher else '',
                'total_hours': e.total_hours,
                'hours_per_session': e.hours_per_session,
                'status': e.status,
                'confirmed_slot': json.loads(e.confirmed_slot) if e.confirmed_slot else None,
            } for e in enrollments],
        }
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
    user = User.query.get(user_id)
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
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404
    user.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': '用户已停用'})


@auth_bp.route('/api/users/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def api_toggle_user(user_id):
    user = User.query.get(user_id)
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
@login_required
def teacher_availability_page():
    teachers = User.query.filter(User.role.in_(['teacher', 'admin'])).all()
    return render_template('auth/teacher_availability.html', teachers=teachers)


@auth_bp.route('/api/teacher/<int:teacher_id>/availability', methods=['GET'])
@login_required
def api_get_teacher_availability(teacher_id):
    user = User.query.get(teacher_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    slots = TeacherAvailability.query.filter_by(user_id=teacher_id).all()
    available = []
    preferred = []
    for s in slots:
        item = {'day': s.day_of_week, 'start': s.time_start, 'end': s.time_end}
        if s.is_preferred:
            preferred.append(item)
        else:
            available.append(item)
    return jsonify({'success': True, 'data': {'available': available, 'preferred': preferred}})


@auth_bp.route('/api/teacher/<int:teacher_id>/availability', methods=['POST'])
@login_required
def api_set_teacher_availability(teacher_id):
    user = User.query.get(teacher_id)
    if not user:
        return jsonify({'success': False, 'error': '用户不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    TeacherAvailability.query.filter_by(user_id=teacher_id).delete()

    for slot_data in data.get('available', []):
        db.session.add(TeacherAvailability(
            user_id=teacher_id, day_of_week=slot_data['day'],
            time_start=slot_data['start'], time_end=slot_data['end'],
            is_preferred=False))
    for slot_data in data.get('preferred', []):
        db.session.add(TeacherAvailability(
            user_id=teacher_id, day_of_week=slot_data['day'],
            time_start=slot_data['start'], time_end=slot_data['end'],
            is_preferred=True))

    db.session.commit()
    return jsonify({'success': True, 'message': '保存成功'})
