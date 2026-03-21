import json

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from extensions import db
from modules.auth import auth_bp
from modules.auth.decorators import role_required
from modules.auth.models import Enrollment, LeaveRequest, User
from modules.auth.services import (
    _normalize_available_slot_entries,
    _normalize_excluded_dates_entries,
    _linked_schedule_query,
    build_enrollment_payload,
    build_leave_request_payload,
    create_enrollment_record,
    delete_enrollment_hard,
    export_enrollment_schedule_xlsx,
    find_matching_slots,
    get_accessible_enrollment_query,
    get_business_now,
    get_business_today,
    propose_enrollment_schedule,
    reject_enrollment_schedule,
    save_manual_enrollment_plan,
    send_leave_status_notification,
    sync_enrollment_status,
    student_confirm_schedule,
    submit_enrollment_intake,
    update_enrollment_intake,
    user_can_access_enrollment,
    user_can_approve_leave,
    user_can_edit_enrollment_intake,
    user_can_request_leave,
)
from modules.oa.models import CourseSchedule


def _render_intake_form(enrollment, *, token='', is_edit_mode=False, return_url=''):
    enrollment_data = build_enrollment_payload(enrollment, current_user if current_user.is_authenticated else None)
    submit_url = f'/auth/api/enrollments/{enrollment.id}/intake' if is_edit_mode else f'/auth/intake/{token}'
    return render_template(
        'auth/intake_form.html',
        enrollment=enrollment_data,
        token=token,
        is_edit_mode=is_edit_mode,
        submit_url=submit_url,
        return_url=return_url,
    )


# ========== 页面路由 ==========


@auth_bp.route('/enrollments')
@role_required('admin', 'teacher')
def enrollments_page():
    teachers = User.query.filter(User.role.in_(['teacher', 'admin'])).all()
    return render_template('auth/enrollments.html', teachers=teachers)


@auth_bp.route('/enrollments/<int:enrollment_id>')
@role_required('admin', 'teacher')
def enrollment_detail_page(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if not user_can_access_enrollment(current_user, enrollment):
        return render_template('auth/intake_error.html', message='无权查看该报名详情。'), 403

    data = build_enrollment_payload(enrollment, current_user)
    data['intake_url'] = f'/auth/intake/{enrollment.intake_token}' if enrollment.intake_token else ''
    return render_template('auth/enrollment_detail.html', enrollment=data)


@auth_bp.route('/enrollments/<int:enrollment_id>/intake-edit')
@login_required
def enrollment_intake_edit_page(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if not user_can_edit_enrollment_intake(current_user, enrollment):
        return render_template('auth/intake_error.html', message='当前无权修改该学生信息。'), 403

    return_url = '/auth/student/dashboard' if current_user.role == 'student' else f'/auth/enrollments/{enrollment.id}'
    return _render_intake_form(
        enrollment,
        is_edit_mode=True,
        return_url=return_url,
    )


@auth_bp.route('/intake/<token>')
def intake_form_page(token):
    enrollment = Enrollment.query.filter_by(intake_token=token).first()
    if not enrollment:
        return render_template('auth/intake_error.html', message='链接无效，报名记录不存在。'), 404

    if enrollment.token_expires_at and enrollment.token_expires_at < get_business_now():
        return render_template('auth/intake_error.html', message='链接已过期，请联系教务重新发送。'), 410

    if enrollment.status != 'pending_info':
        return render_template('auth/intake_error.html', message='该报名信息已提交，无需重复填写。'), 400

    return _render_intake_form(enrollment, token=token, is_edit_mode=False)


# ========== 报名 API ==========


@auth_bp.route('/api/enrollments', methods=['GET'])
@login_required
def api_list_enrollments():
    status = request.args.get('status')
    query = get_accessible_enrollment_query(current_user)
    if status:
        query = query.filter_by(status=status)
    enrollments = query.order_by(Enrollment.created_at.desc()).all()
    return jsonify({
        'success': True,
        'data': [build_enrollment_payload(enrollment, current_user) for enrollment in enrollments],
    })


@auth_bp.route('/api/enrollments', methods=['POST'])
@role_required('admin')
def api_create_enrollment():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    try:
        enrollment, intake_url, error = create_enrollment_record(data)
        if error:
            return jsonify({'success': False, 'error': error}), 400

        result = build_enrollment_payload(enrollment, current_user)
        result['intake_url'] = intake_url
        return jsonify({'success': True, 'data': result}), 201
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'创建失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>', methods=['GET'])
@login_required
def api_get_enrollment(enrollment_id):
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404
    if not user_can_access_enrollment(current_user, enrollment):
        return jsonify({'success': False, 'error': '无权查看该报名记录'}), 403
    return jsonify({'success': True, 'data': build_enrollment_payload(enrollment, current_user)})


@auth_bp.route('/intake/<token>', methods=['POST'])
def api_submit_intake(token):
    enrollment = Enrollment.query.filter_by(intake_token=token).first()
    if not enrollment:
        return jsonify({'success': False, 'error': '链接无效'}), 404

    if enrollment.token_expires_at and enrollment.token_expires_at < get_business_now():
        return jsonify({'success': False, 'error': '链接已过期'}), 410

    if enrollment.status != 'pending_info':
        return jsonify({'success': False, 'error': '该报名信息已提交，无需重复填写'}), 400

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    try:
        result, error = submit_enrollment_intake(enrollment, data)
        if error:
            status_code = 400
            if error == '链接已过期':
                status_code = 410
            elif error == '报名记录不存在':
                status_code = 404
            return jsonify({'success': False, 'error': error}), status_code

        response = {'success': True, 'message': '信息提交成功', 'data': result}
        if result.get('account'):
            response['account'] = result['account']
        return jsonify(response)
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'提交失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>/intake', methods=['PUT'])
@login_required
def api_update_enrollment_intake(enrollment_id):
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404
    if not user_can_edit_enrollment_intake(current_user, enrollment):
        return jsonify({'success': False, 'error': '当前无权修改该学生信息'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    try:
        result, error = update_enrollment_intake(enrollment, data)
        if error:
            return jsonify({'success': False, 'error': error}), 400
        response = {'success': True, 'message': '学生信息已更新，请重新匹配排课方案', 'data': result}
        if result.get('account'):
            response['account'] = result['account']
        return jsonify(response)
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'更新失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>/match', methods=['POST'])
@role_required('admin')
def api_match_slots(enrollment_id):
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404

    try:
        proposed, error = find_matching_slots(enrollment_id)
        if error:
            return jsonify({'success': False, 'error': error}), 400

        enrollment.proposed_slots = json.dumps(proposed, ensure_ascii=False)
        db.session.commit()
        return jsonify({'success': True, 'proposed_slots': proposed})
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'匹配失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>/confirm', methods=['POST'])
@role_required('admin')
def api_confirm_slot(enrollment_id):
    data = request.get_json()
    if not data or 'slot_index' not in data:
        return jsonify({'success': False, 'error': '缺少 slot_index 参数'}), 400

    try:
        success, message, dates = propose_enrollment_schedule(enrollment_id, data['slot_index'])
        if success:
            return jsonify({'success': True, 'message': message, 'dates': dates})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'确认失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>/manual-plan', methods=['POST'])
@role_required('admin')
def api_save_manual_plan(enrollment_id):
    data = request.get_json() or {}
    try:
        result = save_manual_enrollment_plan(
            enrollment_id,
            data.get('session_dates') or [],
            force_save=bool(data.get('force_save')),
        )
        status_code = result.pop('status_code', 200)
        return jsonify(result), status_code
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'保存失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>/student-confirm', methods=['POST'])
@role_required('student')
def api_student_confirm(enrollment_id):
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404
    if not user_can_access_enrollment(current_user, enrollment):
        return jsonify({'success': False, 'error': '无权操作'}), 403

    try:
        success, message, created_count = student_confirm_schedule(enrollment_id)
        if success:
            return jsonify({'success': True, 'message': message, 'created_count': created_count})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'确认失败: {str(exc)}'}), 500


@auth_bp.route('/api/enrollments/<int:enrollment_id>/student-reject', methods=['POST'])
@role_required('student')
def api_student_reject(enrollment_id):
    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404
    if not user_can_access_enrollment(current_user, enrollment):
        return jsonify({'success': False, 'error': '无权操作'}), 403

    data = request.get_json() or {}
    success, message = reject_enrollment_schedule(
        enrollment_id,
        data.get('message', '学生对排课方案有疑问，请查看。'),
        actor_user_id=current_user.id,
    )
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 400


@auth_bp.route('/api/enrollments/<int:enrollment_id>/export', methods=['GET'])
@login_required
def api_export_schedule(enrollment_id):
    from flask import send_file

    enrollment = db.session.get(Enrollment, enrollment_id)
    if not enrollment:
        return jsonify({'success': False, 'error': '报名记录不存在'}), 404
    if not user_can_access_enrollment(current_user, enrollment):
        return jsonify({'success': False, 'error': '无权导出该报名课表'}), 403

    output, filename, error = export_enrollment_schedule_xlsx(enrollment_id)
    if error:
        return jsonify({'success': False, 'error': error}), 400
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@auth_bp.route('/api/enrollments/<int:enrollment_id>', methods=['DELETE'])
@role_required('admin')
def api_delete_enrollment(enrollment_id):
    success, message = delete_enrollment_hard(enrollment_id)
    if success:
        return jsonify({'success': True, 'message': message})
    return jsonify({'success': False, 'error': message}), 404 if message == '报名记录不存在' else 400


# ========== 课程进度 API ==========


@auth_bp.route('/api/enrollments/progress')
@login_required
def api_enrollments_progress():
    enrollments = get_accessible_enrollment_query(current_user).filter(
        Enrollment.status.in_(['confirmed', 'active', 'completed'])
    ).all()

    today = get_business_today()
    progress_map = {}

    for enrollment in enrollments:
        total_sessions = int(enrollment.total_hours / enrollment.hours_per_session) if enrollment.total_hours and enrollment.hours_per_session else 0
        if total_sessions == 0:
            continue

        schedules = _linked_schedule_query(enrollment.id).order_by(
            CourseSchedule.date,
            CourseSchedule.time_start,
        ).all()
        if not schedules:
            continue

        for index, schedule in enumerate(schedules, 1):
            is_ending = index > max(total_sessions - 3, 0)
            progress_map[schedule.id] = {
                'session_number': index,
                'total': total_sessions,
                'is_ending': is_ending,
                'completed': schedule.date < today,
                'delivered': bool(schedule.feedback and schedule.feedback.status == 'submitted'),
                'course_name': enrollment.course_name,
                'student_name': enrollment.student_name,
            }

    return jsonify({'success': True, 'data': progress_map})


# ========== 请假 API ==========


@auth_bp.route('/api/leave-requests', methods=['GET'])
@login_required
def api_list_leave_requests():
    query = LeaveRequest.query
    if current_user.role == 'student':
        profile = current_user.student_profile
        if not profile:
            query = query.filter(False)
        else:
            query = query.join(
                Enrollment, LeaveRequest.enrollment_id == Enrollment.id
            ).filter(Enrollment.student_profile_id == profile.id)
    elif current_user.role == 'teacher':
        query = query.join(
            CourseSchedule, LeaveRequest.schedule_id == CourseSchedule.id
        ).filter(CourseSchedule.teacher_id == current_user.id)

    requests = query.order_by(LeaveRequest.created_at.desc()).all()
    return jsonify({
        'success': True,
        'data': [build_leave_request_payload(item, current_user) for item in requests],
    })


@auth_bp.route('/api/leave-requests', methods=['POST'])
@role_required('student')
def api_create_leave_request():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    schedule_id = data.get('schedule_id')
    reason = (data.get('reason') or '').strip()
    makeup_available_slots = _normalize_available_slot_entries(data.get('makeup_available_slots'))
    makeup_excluded_dates = _normalize_excluded_dates_entries(data.get('makeup_excluded_dates'))
    makeup_preference_note = (data.get('makeup_preference_note') or '').strip() or None
    if not schedule_id:
        return jsonify({'success': False, 'error': '缺少 schedule_id'}), 400

    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    if not schedule.enrollment_id or not schedule.enrollment:
        return jsonify({'success': False, 'error': '该课程未关联报名，无法发起请假'}), 400
    if not user_can_request_leave(current_user, schedule):
        return jsonify({'success': False, 'error': '当前无权对该课程发起请假'}), 403

    leave_request = LeaveRequest(
        enrollment_id=schedule.enrollment_id,
        student_name=schedule.enrollment.student_name,
        schedule_id=schedule_id,
        makeup_available_slots_json=json.dumps(makeup_available_slots, ensure_ascii=False) if makeup_available_slots else None,
        makeup_excluded_dates_json=json.dumps(makeup_excluded_dates, ensure_ascii=False) if makeup_excluded_dates else None,
        makeup_preference_note=makeup_preference_note,
        leave_date=schedule.date,
        reason=reason,
        status='pending',
    )
    db.session.add(leave_request)
    db.session.commit()
    return jsonify({'success': True, 'data': build_leave_request_payload(leave_request, current_user)}), 201


@auth_bp.route('/api/leave-requests/<int:request_id>/approve', methods=['PUT'])
@role_required('teacher', 'admin')
def api_approve_leave(request_id):
    from modules.auth.workflow_services import cancel_schedule_feedback_todo, ensure_leave_makeup_workflow

    leave_request = db.session.get(LeaveRequest, request_id)
    if not leave_request:
        return jsonify({'success': False, 'error': '请假记录不存在'}), 404
    if not user_can_approve_leave(current_user, leave_request):
        return jsonify({'success': False, 'error': '无权审批该请假申请'}), 403
    if leave_request.status != 'pending':
        return jsonify({'success': False, 'error': '该请假申请已处理'}), 400

    data = request.get_json(silent=True) or {}
    decision_comment = (data.get('comment') or '').strip() or None

    leave_request.status = 'approved'
    leave_request.decision_comment = decision_comment
    leave_request.approved_by = current_user.id
    send_leave_status_notification(leave_request)
    linked_enrollment = leave_request.enrollment or (
        leave_request.schedule.enrollment if leave_request.schedule else None
    )
    if linked_enrollment:
        sync_enrollment_status(linked_enrollment)
    if leave_request.schedule_id:
        cancel_schedule_feedback_todo(leave_request.schedule_id, reason='课程请假已批准')
    ensure_leave_makeup_workflow(leave_request, actor_user=current_user)
    db.session.commit()
    return jsonify({'success': True, 'data': build_leave_request_payload(leave_request, current_user)})


@auth_bp.route('/api/leave-requests/<int:request_id>/reject', methods=['PUT'])
@role_required('teacher', 'admin')
def api_reject_leave(request_id):
    leave_request = db.session.get(LeaveRequest, request_id)
    if not leave_request:
        return jsonify({'success': False, 'error': '请假记录不存在'}), 404
    if not user_can_approve_leave(current_user, leave_request):
        return jsonify({'success': False, 'error': '无权审批该请假申请'}), 403
    if leave_request.status != 'pending':
        return jsonify({'success': False, 'error': '该请假申请已处理'}), 400

    data = request.get_json(silent=True) or {}
    decision_comment = (data.get('comment') or '').strip()
    if not decision_comment:
        return jsonify({'success': False, 'error': '请先填写处理说明'}), 400

    leave_request.status = 'rejected'
    leave_request.decision_comment = decision_comment
    leave_request.approved_by = current_user.id
    send_leave_status_notification(leave_request)
    linked_enrollment = leave_request.enrollment or (
        leave_request.schedule.enrollment if leave_request.schedule else None
    )
    if linked_enrollment:
        sync_enrollment_status(linked_enrollment)
    db.session.commit()
    return jsonify({'success': True, 'data': build_leave_request_payload(leave_request, current_user)})
