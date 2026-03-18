import json
from datetime import datetime, timedelta, date
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from modules.auth import auth_bp
from modules.auth.models import User, StudentProfile, Enrollment, LeaveRequest
from modules.auth.services import (generate_intake_token, find_matching_slots,
                                    propose_enrollment_schedule, student_confirm_schedule,
                                    export_enrollment_schedule_xlsx)
from modules.auth.decorators import role_required


# ========== 页面路由 ==========

@auth_bp.route('/enrollments')
@login_required
def enrollments_page():
    teachers = User.query.filter(User.role.in_(['teacher', 'admin'])).all()
    return render_template('auth/enrollments.html', teachers=teachers)


@auth_bp.route('/enrollments/<int:enrollment_id>')
@login_required
def enrollment_detail_page(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    data = enrollment.to_dict()
    data['intake_url'] = f'/auth/intake/{enrollment.intake_token}' if enrollment.intake_token else ''
    return render_template('auth/enrollment_detail.html', enrollment=data)


@auth_bp.route('/intake/<token>')
def intake_form_page(token):
    enrollment = Enrollment.query.filter_by(intake_token=token).first()
    if not enrollment:
        return render_template('auth/intake_error.html', message='链接无效，报名记录不存在。'), 404

    if enrollment.token_expires_at and enrollment.token_expires_at < datetime.utcnow():
        return render_template('auth/intake_error.html', message='链接已过期，请联系教务重新发送。'), 410

    if enrollment.status != 'pending_info':
        return render_template('auth/intake_error.html', message='该报名信息已提交，无需重复填写。'), 400

    enrollment_data = enrollment.to_dict()
    return render_template('auth/intake_form.html', enrollment=enrollment_data, token=token)


# ========== 报名 API ==========

@auth_bp.route('/api/enrollments', methods=['GET'])
@login_required
def api_list_enrollments():
    status = request.args.get('status')
    query = Enrollment.query
    if status:
        query = query.filter_by(status=status)
    enrollments = query.order_by(Enrollment.created_at.desc()).all()
    return jsonify({'success': True, 'data': [e.to_dict() for e in enrollments]})


@auth_bp.route('/api/enrollments', methods=['POST'])
@role_required('admin')
def api_create_enrollment():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    for field in ['student_name', 'course_name', 'teacher_id']:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400

    try:
        token = generate_intake_token()
        enrollment = Enrollment(
            student_name=data['student_name'],
            course_name=data['course_name'],
            teacher_id=data['teacher_id'],
            total_hours=data.get('total_hours'),
            hours_per_session=data.get('hours_per_session', 2.0),
            sessions_per_week=data.get('sessions_per_week', 1),
            notes=data.get('notes'),
            intake_token=token,
            token_expires_at=datetime.utcnow() + timedelta(days=7),
            status='pending_info',
        )
        db.session.add(enrollment)
        db.session.commit()

        result = enrollment.to_dict()
        result['intake_url'] = f'/auth/intake/{token}'
        return jsonify({'success': True, 'data': result}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'创建失败: {str(e)}'}), 500


@auth_bp.route('/api/enrollments/<int:id>', methods=['GET'])
@login_required
def api_get_enrollment(id):
    enrollment = Enrollment.query.get(id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404
    return jsonify({'success': True, 'data': enrollment.to_dict()})


@auth_bp.route('/intake/<token>', methods=['POST'])
def api_submit_intake(token):
    enrollment = Enrollment.query.filter_by(intake_token=token).first()
    if not enrollment:
        return jsonify({'success': False, 'error': '链接无效'}), 404

    if enrollment.token_expires_at and enrollment.token_expires_at < datetime.utcnow():
        return jsonify({'success': False, 'error': '链接已过期'}), 410

    if enrollment.status != 'pending_info':
        return jsonify({'success': False, 'error': '该报名信息已提交，无需重复填写'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    if not data.get('name'):
        return jsonify({'success': False, 'error': '姓名为必填项'}), 400

    if not data.get('phone'):
        return jsonify({'success': False, 'error': '手机号为必填项'}), 400

    try:
        # 前端发送 available_times，统一处理
        slots = data.get('available_slots') or data.get('available_times', [])
        if isinstance(slots, list):
            slots = json.dumps(slots, ensure_ascii=False)

        excl = data.get('excluded_dates', [])
        if isinstance(excl, list):
            excl = json.dumps(excl, ensure_ascii=False)

        student_name = data['name']
        phone = data.get('phone', '')

        # 自动创建学生账号（用姓名作为用户名，默认密码 scf123）
        account_info = None
        username = student_name.strip()
        existing_user = User.query.filter_by(username=username).first()
        if not existing_user and username:
            student_user = User(
                username=username,
                display_name=student_name,
                role='student',
                phone=phone,
            )
            student_user.set_password('scf123')
            db.session.add(student_user)
            db.session.flush()
            account_info = {
                'username': username,
                'password': 'scf123',
                'user_id': student_user.id,
            }
        elif existing_user:
            account_info = {
                'username': existing_user.username,
                'password': None,
                'user_id': existing_user.id,
            }

        profile = StudentProfile(
            user_id=account_info['user_id'] if account_info else None,
            name=student_name,
            phone=phone,
            available_slots=slots,
            excluded_dates=excl if excl != '[]' else None,
            notes=data.get('notes'),
        )
        db.session.add(profile)
        db.session.flush()

        # 学生可能修改了姓名，同步更新报名记录
        if student_name and student_name != enrollment.student_name:
            enrollment.student_name = student_name

        enrollment.student_profile_id = profile.id
        enrollment.status = 'pending_schedule'
        db.session.commit()

        result = {'success': True, 'message': '信息提交成功'}
        if account_info:
            result['account'] = account_info
        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'提交失败: {str(e)}'}), 500


@auth_bp.route('/api/enrollments/<int:id>/match', methods=['POST'])
@role_required('admin')
def api_match_slots(id):
    enrollment = Enrollment.query.get(id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404

    try:
        proposed, error = find_matching_slots(id)
        if error:
            return jsonify({'success': False, 'error': error}), 400

        enrollment.proposed_slots = json.dumps(proposed, ensure_ascii=False)
        db.session.commit()
        return jsonify({'success': True, 'proposed_slots': proposed})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'匹配失败: {str(e)}'}), 500


@auth_bp.route('/api/enrollments/<int:id>/confirm', methods=['POST'])
@role_required('admin')
def api_confirm_slot(id):
    """管理员选择方案 → 通知学生确认（不直接创建课表）"""
    data = request.get_json()
    if not data or 'slot_index' not in data:
        return jsonify({'success': False, 'error': '缺少 slot_index 参数'}), 400

    try:
        success, message, dates = propose_enrollment_schedule(id, data['slot_index'])
        if success:
            return jsonify({'success': True, 'message': message, 'dates': dates})
        else:
            return jsonify({'success': False, 'error': message}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'确认失败: {str(e)}'}), 500


@auth_bp.route('/api/enrollments/<int:id>/student-confirm', methods=['POST'])
@login_required
def api_student_confirm(id):
    """学生确认排课方案 → 正式创建课表"""
    enrollment = Enrollment.query.get(id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404

    if current_user.role == 'student':
        profile = enrollment.student_profile
        if not profile or profile.user_id != current_user.id:
            return jsonify({'success': False, 'error': '无权操作'}), 403

    try:
        success, message, created_count = student_confirm_schedule(id)
        if success:
            return jsonify({'success': True, 'message': message, 'created_count': created_count})
        else:
            return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'确认失败: {str(e)}'}), 500


@auth_bp.route('/api/enrollments/<int:id>/student-reject', methods=['POST'])
@login_required
def api_student_reject(id):
    """学生对排课方案提出异议 → 发消息给老师"""
    enrollment = Enrollment.query.get(id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404

    if current_user.role == 'student':
        profile = enrollment.student_profile
        if not profile or profile.user_id != current_user.id:
            return jsonify({'success': False, 'error': '无权操作'}), 403

    data = request.get_json() or {}
    message_text = data.get('message', '学生对排课方案有疑问，请查看。')

    from modules.auth.models import ChatMessage
    msg = ChatMessage(
        sender_id=current_user.id,
        receiver_id=enrollment.teacher_id,
        enrollment_id=enrollment.id,
        content=f'关于课程「{enrollment.course_name}」的排课：{message_text}',
        is_read=False,
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'success': True, 'message': '已发送消息给老师'})


@auth_bp.route('/api/enrollments/<int:id>/export', methods=['GET'])
@login_required
def api_export_schedule(id):
    """导出排课课表为 Excel"""
    from flask import send_file
    output, filename, error = export_enrollment_schedule_xlsx(id)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)


@auth_bp.route('/api/enrollments/<int:id>', methods=['DELETE'])
@role_required('admin')
def api_delete_enrollment(id):
    enrollment = Enrollment.query.get(id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404

    enrollment.status = 'cancelled'
    db.session.commit()
    return jsonify({'success': True, 'message': '报名已取消'})


# ========== 课程进度 API ==========

@auth_bp.route('/api/enrollments/progress')
@login_required
def api_enrollments_progress():
    """返回所有课程的进度信息，包括每节课的序号和是否是最后3节"""
    from modules.oa.models import CourseSchedule

    enrollments = Enrollment.query.filter(
        Enrollment.status.in_(['confirmed', 'active'])).all()

    today = date.today()
    progress_map = {}  # schedule_id → {session_number, total, is_ending}

    for e in enrollments:
        total_sessions = int(e.total_hours / e.hours_per_session) if e.total_hours and e.hours_per_session else 0
        if total_sessions == 0:
            continue

        # 查找该报名关联的所有课程
        schedules = CourseSchedule.query.filter(
            CourseSchedule.teacher == (e.teacher.display_name if e.teacher else ''),
            CourseSchedule.course_name == e.course_name,
            CourseSchedule.students.contains(e.student_name)
        ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

        if not schedules:
            continue

        for idx, s in enumerate(schedules):
            session_num = idx + 1
            is_ending = session_num > max(total_sessions - 3, 0)
            progress_map[s.id] = {
                'session_number': session_num,
                'total': total_sessions,
                'is_ending': is_ending,
                'completed': s.date < today,
                'course_name': e.course_name,
                'student_name': e.student_name,
            }

    return jsonify({'success': True, 'data': progress_map})


# ========== 请假 API ==========

@auth_bp.route('/api/leave-requests', methods=['GET'])
@login_required
def api_list_leave_requests():
    query = LeaveRequest.query
    if current_user.role == 'student':
        query = query.filter_by(student_name=current_user.display_name)
    elif current_user.role == 'teacher':
        from modules.oa.models import CourseSchedule
        my_schedule_ids = [s.id for s in CourseSchedule.query.filter_by(
            teacher=current_user.display_name).all()]
        query = query.filter(LeaveRequest.schedule_id.in_(my_schedule_ids)) if my_schedule_ids else query.filter(False)
    # admin sees all
    requests = query.order_by(LeaveRequest.created_at.desc()).all()
    return jsonify({'success': True, 'data': [r.to_dict() for r in requests]})


@auth_bp.route('/api/leave-requests', methods=['POST'])
@login_required
def api_create_leave_request():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    schedule_id = data.get('schedule_id')
    reason = data.get('reason', '')

    if not schedule_id:
        return jsonify({'success': False, 'error': '缺少 schedule_id'}), 400

    from modules.oa.models import CourseSchedule
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404

    lr = LeaveRequest(
        student_name=current_user.display_name,
        schedule_id=schedule_id,
        leave_date=schedule.date,
        reason=reason,
        status='pending',
    )
    db.session.add(lr)
    db.session.commit()
    return jsonify({'success': True, 'data': lr.to_dict()}), 201


@auth_bp.route('/api/leave-requests/<int:id>/approve', methods=['PUT'])
@login_required
def api_approve_leave(id):
    lr = LeaveRequest.query.get(id)
    if not lr:
        return jsonify({'success': False, 'error': '请假记录不存在'}), 404
    lr.status = 'approved'
    lr.approved_by = current_user.id
    db.session.commit()
    return jsonify({'success': True, 'data': lr.to_dict()})


@auth_bp.route('/api/leave-requests/<int:id>/reject', methods=['PUT'])
@login_required
def api_reject_leave(id):
    lr = LeaveRequest.query.get(id)
    if not lr:
        return jsonify({'success': False, 'error': '请假记录不存在'}), 404
    lr.status = 'rejected'
    lr.approved_by = current_user.id
    db.session.commit()
    return jsonify({'success': True, 'data': lr.to_dict()})
