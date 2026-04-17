"""External auth-domain API routes (enrollments, student profiles, leave requests, teacher availability)."""
import json
from datetime import date

from flask import request, send_file

from extensions import db
from modules.auth import auth_bp
from modules.auth.models import Enrollment, LeaveRequest, StudentProfile, TeacherAvailability, User
from modules.auth.services import (
    build_enrollment_payload,
    create_enrollment_record,
    delete_enrollment_hard,
    export_enrollment_schedule_xlsx,
    find_matching_slots,
    process_leave_request_decision,
    propose_enrollment_schedule,
    reject_enrollment_schedule,
    save_student_profile_record,
    student_confirm_schedule,
    submit_enrollment_intake,
)
from modules.oa.external_api import external_api_required, external_error, external_success
from modules.oa.models import CourseSchedule


def _get_json_payload():
    data = request.get_json(silent=True)
    if not data:
        return None, external_error('请提供 JSON 数据')
    return data, None


def _serialize_enrollment(enrollment):
    payload = build_enrollment_payload(enrollment)
    payload['intake_url'] = f'/auth/intake/{enrollment.intake_token}' if enrollment.intake_token else None
    return payload


def _serialize_teacher_availability(slots):
    available = []
    preferred = []
    for slot in slots:
        item = {'day': slot.day_of_week, 'start': slot.time_start, 'end': slot.time_end}
        if slot.is_preferred:
            preferred.append(item)
        else:
            available.append(item)
    return {'available': available, 'preferred': preferred}


@auth_bp.route('/api/external/teachers/<int:teacher_id>/availability', methods=['GET'])
@external_api_required
def external_get_teacher_availability(teacher_id):
    user = User.query.get(teacher_id)
    if not user:
        return external_error('用户不存在', status=404)

    slots = TeacherAvailability.query.filter_by(user_id=teacher_id).all()
    return external_success(_serialize_teacher_availability(slots))


@auth_bp.route('/api/external/teachers/<int:teacher_id>/availability', methods=['POST'])
@external_api_required
def external_set_teacher_availability(teacher_id):
    user = User.query.get(teacher_id)
    if not user:
        return external_error('用户不存在', status=404)

    data, error = _get_json_payload()
    if error:
        return error

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
    slots = TeacherAvailability.query.filter_by(user_id=teacher_id).all()
    return external_success(_serialize_teacher_availability(slots), message='保存成功')


@auth_bp.route('/api/external/enrollments', methods=['GET'])
@external_api_required
def external_list_enrollments():
    query = Enrollment.query

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    teacher_id = request.args.get('teacher_id', type=int)
    if teacher_id:
        query = query.filter_by(teacher_id=teacher_id)
    student_name = request.args.get('student_name')
    if student_name:
        query = query.filter(Enrollment.student_name.contains(student_name))
    course_name = request.args.get('course_name')
    if course_name:
        query = query.filter(Enrollment.course_name.contains(course_name))

    enrollments = query.order_by(Enrollment.created_at.desc()).all()
    return external_success({
        'items': [_serialize_enrollment(enrollment) for enrollment in enrollments],
        'total': len(enrollments),
    })


@auth_bp.route('/api/external/enrollments', methods=['POST'])
@auth_bp.route('/api/external/enrollments/create', methods=['POST'])
@external_api_required
def external_create_enrollment():
    data, error = _get_json_payload()
    if error:
        return error

    try:
        enrollment, intake_url, error_message = create_enrollment_record(data)
        if error_message:
            return external_error(error_message)
        payload = _serialize_enrollment(enrollment)
        payload['intake_url'] = intake_url
        return external_success(payload, status=201)
    except Exception as exc:
        db.session.rollback()
        return external_error(f'创建失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>', methods=['GET'])
@external_api_required
def external_get_enrollment(enrollment_id):
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return external_error('报名记录不存在', status=404)
    return external_success(_serialize_enrollment(enrollment))


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/intake-submit', methods=['POST'])
@external_api_required
def external_submit_intake(enrollment_id):
    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return external_error('报名记录不存在', status=404)

    data, error = _get_json_payload()
    if error:
        return error

    try:
        result, error_message = submit_enrollment_intake(enrollment, data)
        if error_message:
            status = 400
            if error_message == '链接已过期':
                status = 410
            return external_error(error_message, status=status)
        return external_success(result, message='信息提交成功')
    except Exception as exc:
        db.session.rollback()
        return external_error(f'提交失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/match', methods=['POST'])
@external_api_required
def external_match_enrollment(enrollment_id):
    try:
        proposed, error_message = find_matching_slots(enrollment_id)
        if error_message:
            return external_error(error_message)

        enrollment = Enrollment.query.get(enrollment_id)
        enrollment.proposed_slots = json.dumps(proposed, ensure_ascii=False)
        db.session.commit()
        return external_success({'proposed_slots': proposed, 'count': len(proposed)})
    except Exception as exc:
        db.session.rollback()
        return external_error(f'匹配失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/confirm-slot', methods=['POST'])
@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/confirm', methods=['POST'])
@external_api_required
def external_confirm_enrollment_slot(enrollment_id):
    data, error = _get_json_payload()
    if error:
        return error
    if 'slot_index' not in data:
        return external_error('缺少 slot_index 参数')

    try:
        success, message, dates = propose_enrollment_schedule(enrollment_id, data['slot_index'])
        if not success:
            return external_error(message)
        return external_success({'dates': dates}, message=message)
    except Exception as exc:
        db.session.rollback()
        return external_error(f'确认失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/student-confirm', methods=['POST'])
@external_api_required
def external_student_confirm_enrollment(enrollment_id):
    try:
        success, message, created_count = student_confirm_schedule(enrollment_id)
        if not success:
            return external_error(message)
        return external_success({'created_count': created_count}, message=message)
    except Exception as exc:
        db.session.rollback()
        return external_error(f'确认失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/student-reject', methods=['POST'])
@external_api_required
def external_student_reject_enrollment(enrollment_id):
    data = request.get_json(silent=True) or {}
    try:
        success, message = reject_enrollment_schedule(
            enrollment_id,
            data.get('message', '学生对排课方案有疑问，请查看。'),
            actor_user_id=data.get('actor_user_id'),
        )
        if not success:
            status = 404 if message == '报名记录不存在' else 400
            return external_error(message, status=status)
        return external_success(message=message)
    except Exception as exc:
        db.session.rollback()
        return external_error(f'退回失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>/export', methods=['GET'])
@external_api_required
def external_export_enrollment(enrollment_id):
    output, filename, error_message = export_enrollment_schedule_xlsx(enrollment_id)
    if error_message:
        return external_error(error_message)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@auth_bp.route('/api/external/enrollments/<int:enrollment_id>', methods=['DELETE'])
@external_api_required
def external_delete_enrollment(enrollment_id):
    success, message = delete_enrollment_hard(enrollment_id)
    if not success:
        status = 404 if message == '报名记录不存在' else 400
        return external_error(message, status=status)
    return external_success(message=message)


@auth_bp.route('/api/external/enrollments/progress', methods=['GET'])
@external_api_required
def external_enrollment_progress():
    today = date.today()
    progress_map = {}

    enrollments = Enrollment.query.filter(
        Enrollment.status.in_(['confirmed', 'active'])
    ).all()
    for enrollment in enrollments:
        if not enrollment.total_hours or not enrollment.hours_per_session:
            continue
        total_sessions = int(enrollment.total_hours / enrollment.hours_per_session)
        if total_sessions <= 0:
            continue

        schedules = CourseSchedule.query.filter(
            CourseSchedule.teacher == (enrollment.teacher.display_name if enrollment.teacher else ''),
            CourseSchedule.course_name == enrollment.course_name,
            CourseSchedule.students.contains(enrollment.student_name),
        ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

        for index, schedule in enumerate(schedules, 1):
            progress_map[schedule.id] = {
                'session_number': index,
                'total': total_sessions,
                'is_ending': index > max(total_sessions - 3, 0),
                'completed': schedule.date < today,
                'course_name': enrollment.course_name,
                'student_name': enrollment.student_name,
            }

    return external_success(progress_map)


@auth_bp.route('/api/external/student-profiles', methods=['GET'])
@external_api_required
def external_list_student_profiles():
    query = StudentProfile.query
    name = request.args.get('name')
    if name:
        query = query.filter(StudentProfile.name.contains(name))
    phone = request.args.get('phone')
    if phone:
        query = query.filter(StudentProfile.phone.contains(phone))
    user_id = request.args.get('user_id', type=int)
    if user_id:
        query = query.filter_by(user_id=user_id)

    profiles = query.order_by(StudentProfile.created_at.desc()).all()
    return external_success({'items': [profile.to_dict() for profile in profiles], 'total': len(profiles)})


@auth_bp.route('/api/external/student-profiles/<int:profile_id>', methods=['GET'])
@external_api_required
def external_get_student_profile(profile_id):
    profile = StudentProfile.query.get(profile_id)
    if not profile:
        return external_error('学生档案不存在', status=404)
    return external_success(profile.to_dict())


@auth_bp.route('/api/external/student-profiles', methods=['POST'])
@external_api_required
def external_create_student_profile():
    data, error = _get_json_payload()
    if error:
        return error

    try:
        profile, account_info, error_message = save_student_profile_record(data)
        if error_message:
            status = 404 if error_message in {'用户不存在', '报名记录不存在'} else 400
            return external_error(error_message, status=status)
        return external_success({
            'profile': profile.to_dict(),
            'account': account_info,
        }, status=201)
    except Exception as exc:
        db.session.rollback()
        return external_error(f'保存失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/student-profiles/<int:profile_id>', methods=['PUT'])
@external_api_required
def external_update_student_profile(profile_id):
    profile = StudentProfile.query.get(profile_id)
    if not profile:
        return external_error('学生档案不存在', status=404)

    data, error = _get_json_payload()
    if error:
        return error

    try:
        profile, account_info, error_message = save_student_profile_record(data, profile=profile)
        if error_message:
            status = 404 if error_message in {'用户不存在', '报名记录不存在'} else 400
            return external_error(error_message, status=status)
        return external_success({
            'profile': profile.to_dict(),
            'account': account_info,
        })
    except Exception as exc:
        db.session.rollback()
        return external_error(f'更新失败: {str(exc)}', status=500)


@auth_bp.route('/api/external/leave-requests', methods=['GET'])
@external_api_required
def external_list_leave_requests():
    query = LeaveRequest.query
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    student_name = request.args.get('student_name')
    if student_name:
        query = query.filter(LeaveRequest.student_name.contains(student_name))
    schedule_id = request.args.get('schedule_id', type=int)
    if schedule_id:
        query = query.filter_by(schedule_id=schedule_id)

    items = query.order_by(LeaveRequest.created_at.desc()).all()
    return external_success({'items': [item.to_dict() for item in items], 'total': len(items)})


@auth_bp.route('/api/external/leave-requests', methods=['POST'])
@external_api_required
def external_create_leave_request():
    data, error = _get_json_payload()
    if error:
        return error

    schedule_id = data.get('schedule_id')
    student_name = (data.get('student_name') or '').strip()
    if not schedule_id:
        return external_error('缺少 schedule_id')
    if not student_name:
        return external_error('缺少 student_name')

    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return external_error('课程不存在', status=404)

    leave_request = LeaveRequest(
        enrollment_id=data.get('enrollment_id'),
        student_name=student_name,
        schedule_id=schedule_id,
        leave_date=schedule.date,
        reason=data.get('reason', ''),
        status=data.get('status', 'pending'),
    )
    db.session.add(leave_request)
    db.session.commit()
    return external_success(leave_request.to_dict(), status=201)


@auth_bp.route('/api/external/leave-requests/<int:request_id>/approve', methods=['PUT'])
@external_api_required
def external_approve_leave_request(request_id):
    leave_request = LeaveRequest.query.get(request_id)
    data = request.get_json(silent=True) or {}
    approved_by = data.get('approved_by')
    actor = db.session.get(User, approved_by) if approved_by else None
    if not actor:
        return external_error('缺少有效的 approved_by', status=400, code='missing_approved_by')

    result = process_leave_request_decision(
        leave_request,
        actor,
        approve=True,
        decision_comment=data.get('comment'),
    )
    if not result.get('success'):
        return external_error(result.get('error') or '审批失败', status=result.get('status_code', 400))
    return external_success(result.get('data'))


@auth_bp.route('/api/external/leave-requests/<int:request_id>/reject', methods=['PUT'])
@external_api_required
def external_reject_leave_request(request_id):
    leave_request = LeaveRequest.query.get(request_id)
    data = request.get_json(silent=True) or {}
    approved_by = data.get('approved_by')
    actor = db.session.get(User, approved_by) if approved_by else None
    if not actor:
        return external_error('缺少有效的 approved_by', status=400, code='missing_approved_by')

    result = process_leave_request_decision(
        leave_request,
        actor,
        approve=False,
        decision_comment=data.get('comment'),
    )
    if not result.get('success'):
        return external_error(result.get('error') or '审批失败', status=result.get('status_code', 400))
    return external_success(result.get('data'))
