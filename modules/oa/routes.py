from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import jsonify, render_template, request
from flask_login import current_user

from extensions import db
from modules.auth.decorators import role_required
from modules.auth.models import Enrollment, LeaveRequest, User
from modules.auth.services import build_schedule_payload, get_business_today, sync_enrollment_status
from modules.oa import oa_bp
from modules.oa.models import CourseFeedback, CourseSchedule, OATodo
from modules.oa.services import deduplicate_todo_payloads, import_schedule_from_excel


def _get_staff_options():
    """从数据库动态获取员工列表，替代硬编码。"""
    try:
        users = User.query.filter(User.is_active == True).all()
        if users:
            return [user.display_name for user in users]
    except Exception:
        pass
    return ['李宇', '范晓东', '周行', '包睿旻', '黎怡君', '张渝', '陈冠如', '王艳龙', '卢老师', '田鹏', '陈东豪']


def _time_to_minutes(time_str):
    hour, minute = time_str.split(':')
    return int(hour) * 60 + int(minute)


def _time_ranges_overlap(start_a, end_a, start_b, end_b):
    return max(_time_to_minutes(start_a), _time_to_minutes(start_b)) < min(
        _time_to_minutes(end_a),
        _time_to_minutes(end_b),
    )


def _resolve_teacher_or_error(teacher_value):
    teacher_user = User.query.filter(
        (User.display_name == teacher_value) | (User.username == teacher_value)
    ).first()
    if not teacher_user:
        return None, '授课教师不存在，请先创建教师账号'
    return teacher_user, None


def _validate_schedule_conflicts(*, schedule_id=None, course_date=None, time_start=None, time_end=None, teacher_id=None, enrollment_id=None):
    if not course_date or not time_start or not time_end or not teacher_id:
        return '缺少冲突校验所需的日期、时间或教师信息'
    if _time_to_minutes(time_end) <= _time_to_minutes(time_start):
        return '结束时间必须晚于开始时间'

    teacher_query = CourseSchedule.query.filter(
        CourseSchedule.teacher_id == teacher_id,
        CourseSchedule.date == course_date,
    )
    if schedule_id:
        teacher_query = teacher_query.filter(CourseSchedule.id != schedule_id)
    for existing in teacher_query.all():
        if _time_ranges_overlap(time_start, time_end, existing.time_start, existing.time_end):
            return '该老师在相同时段已有课程安排'

    if enrollment_id:
        enrollment_query = CourseSchedule.query.filter(
            CourseSchedule.enrollment_id == enrollment_id,
            CourseSchedule.date == course_date,
        )
        if schedule_id:
            enrollment_query = enrollment_query.filter(CourseSchedule.id != schedule_id)
        for existing in enrollment_query.all():
            if _time_ranges_overlap(time_start, time_end, existing.time_start, existing.time_end):
                return '该报名在相同时段已有课程安排'
    return None


def _schedule_locked_by_leave(schedule, updates):
    if not schedule:
        return False
    if not LeaveRequest.query.filter_by(schedule_id=schedule.id).count():
        return False
    protected_fields = {'date', 'time_start', 'time_end', 'teacher', 'enrollment_id'}
    return any(field in updates for field in protected_fields)


# ========== 页面路由 ==========


@oa_bp.route('/')
@role_required('admin')
def oa_dashboard():
    return render_template('oa/dashboard.html')


@oa_bp.route('/schedule')
@role_required('admin')
def oa_schedule():
    return render_template('oa/schedule.html')


@oa_bp.route('/todos')
@role_required('admin')
def oa_todos():
    return render_template('oa/todos.html', staff_options=_get_staff_options())


@oa_bp.route('/painpoints')
@role_required('admin')
def oa_painpoints():
    return render_template('oa/painpoints.html', staff_options=_get_staff_options())


# ========== 课程排课 API ==========


@oa_bp.route('/api/schedules', methods=['GET'])
@role_required('admin')
def api_list_schedules():
    today = get_business_today()
    year = request.args.get('year', type=int, default=today.year)
    month = request.args.get('month', type=int, default=today.month)

    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    schedules = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date,
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': [build_schedule_payload(schedule, current_user) for schedule in schedules],
        'total': len(schedules),
    })


@oa_bp.route('/api/schedules/date-range', methods=['GET'])
@role_required('admin')
def api_schedules_date_range():
    from sqlalchemy import func

    result = db.session.query(
        func.min(CourseSchedule.date),
        func.max(CourseSchedule.date),
        func.count(CourseSchedule.id),
    ).first()
    if result and result[0]:
        return jsonify({
            'success': True,
            'data': {
                'min_date': result[0].isoformat() if result[0] else None,
                'max_date': result[1].isoformat() if result[1] else None,
                'total': result[2],
            }
        })
    return jsonify({'success': True, 'data': {'min_date': None, 'max_date': None, 'total': 0}})


@oa_bp.route('/api/schedules/by-date', methods=['GET'])
@role_required('admin')
def api_schedules_by_date():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        return jsonify({'success': False, 'error': '请提供 start 和 end 日期参数'}), 400

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return jsonify({'success': False, 'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400

    schedules = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date,
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': [build_schedule_payload(schedule, current_user) for schedule in schedules],
        'total': len(schedules),
    })


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['GET'])
@role_required('admin')
def api_get_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    return jsonify({'success': True, 'data': build_schedule_payload(schedule, current_user)})


@oa_bp.route('/api/schedules', methods=['POST'])
@role_required('admin')
def api_create_schedule():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    required = ['date', 'time_start', 'time_end', 'teacher', 'course_name']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400

    try:
        course_date = date.fromisoformat(data['date'])
    except ValueError:
        return jsonify({'success': False, 'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400

    teacher_user, error = _resolve_teacher_or_error(data['teacher'])
    if error:
        return jsonify({'success': False, 'error': error}), 400

    enrollment_id = data.get('enrollment_id')
    if enrollment_id:
        enrollment = db.session.get(Enrollment, enrollment_id)
        if not enrollment:
            return jsonify({'success': False, 'error': '报名记录不存在'}), 404
        if enrollment.teacher_id != teacher_user.id:
            return jsonify({'success': False, 'error': '所选教师与报名绑定教师不一致'}), 400
    else:
        enrollment = None

    conflict_error = _validate_schedule_conflicts(
        course_date=course_date,
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher_id=teacher_user.id,
        enrollment_id=enrollment_id,
    )
    if conflict_error:
        return jsonify({'success': False, 'error': conflict_error}), 400

    schedule = CourseSchedule(
        date=course_date,
        day_of_week=course_date.weekday(),
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher=teacher_user.display_name,
        teacher_id=teacher_user.id,
        course_name=data['course_name'],
        enrollment_id=enrollment.id if enrollment else None,
        students=data.get('students') or (enrollment.student_name if enrollment else ''),
        location=data.get('location', ''),
        notes=data.get('notes', ''),
        color_tag=data.get('color_tag', 'blue'),
    )
    db.session.add(schedule)
    db.session.flush()
    if enrollment:
        sync_enrollment_status(enrollment)
    db.session.commit()

    return jsonify({'success': True, 'data': build_schedule_payload(schedule, current_user)}), 201


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
@role_required('admin')
def api_update_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    original_enrollment_id = schedule.enrollment_id

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400
    if _schedule_locked_by_leave(schedule, data):
        return jsonify({'success': False, 'error': '该课程已有请假记录，请通过调课流程处理，不能直接覆盖'}), 400

    next_date = schedule.date
    if 'date' in data:
        try:
            next_date = date.fromisoformat(data['date'])
        except ValueError:
            return jsonify({'success': False, 'error': '日期格式错误'}), 400

    next_teacher_name = data.get('teacher', schedule.teacher)
    teacher_user, error = _resolve_teacher_or_error(next_teacher_name)
    if error:
        return jsonify({'success': False, 'error': error}), 400

    next_enrollment_id = data.get('enrollment_id', schedule.enrollment_id)
    if next_enrollment_id:
        enrollment = db.session.get(Enrollment, next_enrollment_id)
        if not enrollment:
            return jsonify({'success': False, 'error': '报名记录不存在'}), 404
        if enrollment.teacher_id != teacher_user.id:
            return jsonify({'success': False, 'error': '所选教师与报名绑定教师不一致'}), 400
    else:
        enrollment = None

    next_time_start = data.get('time_start', schedule.time_start)
    next_time_end = data.get('time_end', schedule.time_end)
    conflict_error = _validate_schedule_conflicts(
        schedule_id=schedule.id,
        course_date=next_date,
        time_start=next_time_start,
        time_end=next_time_end,
        teacher_id=teacher_user.id,
        enrollment_id=next_enrollment_id,
    )
    if conflict_error:
        return jsonify({'success': False, 'error': conflict_error}), 400

    schedule.date = next_date
    schedule.day_of_week = next_date.weekday()
    schedule.time_start = next_time_start
    schedule.time_end = next_time_end
    schedule.teacher = teacher_user.display_name
    schedule.teacher_id = teacher_user.id
    schedule.course_name = data.get('course_name', schedule.course_name)
    schedule.students = data.get('students', schedule.students or (enrollment.student_name if enrollment else ''))
    schedule.location = data.get('location', schedule.location)
    schedule.notes = data.get('notes', schedule.notes)
    schedule.color_tag = data.get('color_tag', schedule.color_tag)
    schedule.enrollment_id = next_enrollment_id
    db.session.flush()
    if original_enrollment_id:
        original_enrollment = db.session.get(Enrollment, original_enrollment_id)
        if original_enrollment and (not enrollment or original_enrollment.id != enrollment.id):
            sync_enrollment_status(original_enrollment)
    if enrollment:
        sync_enrollment_status(enrollment)
    db.session.commit()

    return jsonify({'success': True, 'data': build_schedule_payload(schedule, current_user)})


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
@role_required('admin')
def api_delete_schedule(schedule_id):
    schedule = db.session.get(CourseSchedule, schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    enrollment_id = schedule.enrollment_id

    OATodo.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    LeaveRequest.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    CourseFeedback.query.filter_by(schedule_id=schedule_id).delete(synchronize_session=False)
    db.session.delete(schedule)
    db.session.flush()
    if enrollment_id:
        enrollment = db.session.get(Enrollment, enrollment_id)
        if enrollment:
            sync_enrollment_status(enrollment)
    db.session.commit()
    return jsonify({'success': True, 'data': {'id': schedule_id}})


@oa_bp.route('/api/schedules/teachers', methods=['GET'])
@role_required('admin')
def api_list_teachers():
    teachers = User.query.filter(User.role.in_(['teacher', 'admin']), User.is_active == True).all()
    return jsonify({'success': True, 'data': sorted({teacher.display_name for teacher in teachers})})


@oa_bp.route('/api/schedules/students', methods=['GET'])
@role_required('admin')
def api_list_students():
    names = [
        row[0] for row in db.session.query(Enrollment.student_name).distinct().filter(
            Enrollment.student_name.isnot(None),
            Enrollment.student_name != '',
        ).all()
    ]
    return jsonify({'success': True, 'data': sorted(names)})


# ========== 课程进度（基于课表） ==========


@oa_bp.route('/api/schedules/progress', methods=['GET'])
@role_required('admin')
def api_schedule_progress():
    all_schedules = CourseSchedule.query.order_by(
        CourseSchedule.date,
        CourseSchedule.time_start,
    ).all()

    groups = defaultdict(list)
    for schedule in all_schedules:
        if schedule.enrollment_id:
            key = ('enrollment', schedule.enrollment_id)
        else:
            key = ('legacy', schedule.course_name, schedule.teacher_id or schedule.teacher, schedule.students or '')
        groups[key].append(schedule)

    progress_map = {}
    for schedules in groups.values():
        total = len(schedules)
        if total < 2:
            continue
        for index, schedule in enumerate(schedules, 1):
            progress_map[schedule.id] = {
                'current': index,
                'total': total,
                'is_ending': index > max(total - 3, 0),
            }

    return jsonify({'success': True, 'data': progress_map})


# ========== 待办事项 API ==========


@oa_bp.route('/api/todos', methods=['GET'])
@role_required('admin')
def api_list_todos():
    query = OATodo.query

    status = request.args.get('status')
    if status == 'pending':
        query = query.filter(OATodo.is_completed == False)
    elif status == 'completed':
        query = query.filter(OATodo.is_completed == True)

    person = request.args.get('person')
    if person:
        query = query.filter(OATodo.responsible_person.contains(person))

    priority = request.args.get('priority', type=int)
    if priority:
        query = query.filter(OATodo.priority == priority)

    todos = query.order_by(OATodo.is_completed, OATodo.priority, OATodo.due_date.asc().nullslast()).all()
    return jsonify({'success': True, 'data': [todo.to_dict() for todo in todos], 'total': len(todos)})


@oa_bp.route('/api/todos/<int:todo_id>', methods=['GET'])
@role_required('admin')
def api_get_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos', methods=['POST'])
@role_required('admin')
def api_create_todo():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400
    if not data.get('title'):
        return jsonify({'success': False, 'error': '缺少必填字段: title'}), 400

    due_date = None
    if data.get('due_date'):
        try:
            due_date = date.fromisoformat(data['due_date'])
        except ValueError:
            return jsonify({'success': False, 'error': '日期格式错误'}), 400

    todo = OATodo(
        title=data['title'],
        description=data.get('description', ''),
        responsible_person=OATodo.normalize_responsible_people(
            data.get('responsible_people', data.get('responsible_person', ''))
        ),
        is_completed=data.get('is_completed', False),
        due_date=due_date,
        priority=data.get('priority', 2),
        notes=data.get('notes', ''),
        schedule_id=data.get('schedule_id'),
    )
    db.session.add(todo)
    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()}), 201


@oa_bp.route('/api/todos/<int:todo_id>', methods=['PUT'])
@role_required('admin')
def api_update_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    if 'due_date' in data:
        if data['due_date']:
            try:
                todo.due_date = date.fromisoformat(data['due_date'])
            except ValueError:
                return jsonify({'success': False, 'error': '日期格式错误'}), 400
        else:
            todo.due_date = None

    for field in ['title', 'description', 'responsible_person', 'is_completed', 'priority', 'notes', 'schedule_id']:
        if field in data:
            if field == 'responsible_person':
                todo.responsible_person = OATodo.normalize_responsible_people(
                    data.get('responsible_people', data.get('responsible_person', ''))
                )
            else:
                setattr(todo, field, data[field])

    if 'responsible_people' in data and 'responsible_person' not in data:
        todo.responsible_person = OATodo.normalize_responsible_people(data.get('responsible_people', []))

    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos/<int:todo_id>', methods=['DELETE'])
@role_required('admin')
def api_delete_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404

    db.session.delete(todo)
    db.session.commit()
    return jsonify({'success': True, 'data': {'id': todo_id}})


@oa_bp.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
@role_required('admin')
def api_toggle_todo(todo_id):
    todo = db.session.get(OATodo, todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404

    todo.is_completed = not todo.is_completed
    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos/batch', methods=['POST'])
@role_required('admin')
def api_batch_todos():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    action = data.get('action')
    ids = data.get('ids', [])
    if not action or not ids:
        return jsonify({'success': False, 'error': '缺少 action 或 ids 参数'}), 400

    todos = OATodo.query.filter(OATodo.id.in_(ids)).all()
    if not todos:
        return jsonify({'success': False, 'error': '未找到匹配的待办'}), 404

    if action == 'complete':
        for todo in todos:
            todo.is_completed = True
    elif action == 'uncomplete':
        for todo in todos:
            todo.is_completed = False
    elif action == 'delete':
        for todo in todos:
            db.session.delete(todo)
    else:
        return jsonify({'success': False, 'error': f'不支持的操作: {action}'}), 400

    db.session.commit()
    return jsonify({'success': True, 'data': {'action': action, 'affected': len(todos)}})


# ========== Excel 导入 API ==========


@oa_bp.route('/api/import-excel', methods=['POST'])
@role_required('admin')
def api_import_excel():
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': '请上传文件'}), 400
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': '仅支持 .xlsx 或 .xls 文件'}), 400

    import os
    import tempfile

    fd, tmp_path = tempfile.mkstemp(suffix='.xlsx')
    file.save(tmp_path)
    os.close(fd)

    try:
        schedules, todos = import_schedule_from_excel(tmp_path, original_filename=file.filename)
        todos, removed_todo_duplicates = deduplicate_todo_payloads(todos)

        CourseFeedback.query.delete()
        LeaveRequest.query.delete()
        CourseSchedule.query.delete()
        OATodo.query.delete()

        for payload in schedules:
            db.session.add(CourseSchedule(**payload))
        for payload in todos:
            db.session.add(OATodo(**payload))

        db.session.commit()
        return jsonify({
            'success': True,
            'data': {
                'schedules_count': len(schedules),
                'todos_count': len(todos),
                'removed_todo_duplicates': removed_todo_duplicates,
            }
        })
    except Exception as exc:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'导入失败: {str(exc)}'}), 500
    finally:
        os.unlink(tmp_path)


# ========== 仪表盘统计 API ==========


@oa_bp.route('/api/dashboard-stats', methods=['GET'])
@role_required('admin')
def api_dashboard_stats():
    today = get_business_today()
    today_count = CourseSchedule.query.filter(CourseSchedule.date == today).count()
    pending_count = OATodo.query.filter(OATodo.is_completed == False).count()

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_count = CourseSchedule.query.filter(
        CourseSchedule.date >= monday,
        CourseSchedule.date <= sunday,
    ).count()

    today_schedules = CourseSchedule.query.filter(
        CourseSchedule.date == today
    ).order_by(CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': {
            'today_count': today_count,
            'pending_todos': pending_count,
            'week_count': week_count,
            'today_schedules': [build_schedule_payload(schedule, current_user) for schedule in today_schedules],
        }
    })
