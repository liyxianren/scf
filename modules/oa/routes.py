from flask import render_template, jsonify, request
from datetime import datetime, date, timedelta
from calendar import monthrange
from extensions import db
from modules.oa.models import CourseSchedule, OATodo
from modules.oa.services import import_schedule_from_excel, deduplicate_todo_payloads

from modules.oa import oa_bp


OA_STAFF_OPTIONS = [
    '李宇',
    '范晓东',
    '周行',
    '包睿旻',
    '黎怡君',
    '张渝',
    '陈冠如',
    '王艳龙',
    '卢老师',
    '田鹏',
    '陈东豪',
]


# ========== 页面路由 ==========

@oa_bp.route('/')
def oa_dashboard():
    """OA 系统仪表盘"""
    return render_template('oa/dashboard.html')


@oa_bp.route('/schedule')
def oa_schedule():
    """课程排课日历视图"""
    return render_template('oa/schedule.html')


@oa_bp.route('/todos')
def oa_todos():
    """待办事项管理页"""
    return render_template('oa/todos.html', staff_options=OA_STAFF_OPTIONS)


@oa_bp.route('/painpoints')
def oa_painpoints():
    """痛点提交页"""
    return render_template('oa/painpoints.html', staff_options=OA_STAFF_OPTIONS)


# ========== 课程排课 API ==========

@oa_bp.route('/api/schedules', methods=['GET'])
def api_list_schedules():
    """按月查询课程，支持 ?year=&month= 参数"""
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int, default=datetime.utcnow().month)

    _, last_day = monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    schedules = CourseSchedule.query.filter(
        CourseSchedule.date >= start_date,
        CourseSchedule.date <= end_date
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': [s.to_dict() for s in schedules],
        'total': len(schedules)
    })


@oa_bp.route('/api/schedules/date-range', methods=['GET'])
def api_schedules_date_range():
    """获取课程数据的最早和最晚日期"""
    from sqlalchemy import func
    result = db.session.query(
        func.min(CourseSchedule.date),
        func.max(CourseSchedule.date),
        func.count(CourseSchedule.id)
    ).first()
    if result and result[0]:
        return jsonify({
            'success': True,
            'data': {
                'min_date': result[0].isoformat() if result[0] else None,
                'max_date': result[1].isoformat() if result[1] else None,
                'total': result[2]
            }
        })
    return jsonify({'success': True, 'data': {'min_date': None, 'max_date': None, 'total': 0}})


@oa_bp.route('/api/schedules/by-date', methods=['GET'])
def api_schedules_by_date():
    """按日期范围查询课程，支持 ?start=YYYY-MM-DD&end=YYYY-MM-DD"""
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
        CourseSchedule.date <= end_date
    ).order_by(CourseSchedule.date, CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': [s.to_dict() for s in schedules],
        'total': len(schedules)
    })


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['GET'])
def api_get_schedule(schedule_id):
    """获取单条课程详情"""
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404
    return jsonify({'success': True, 'data': schedule.to_dict()})


@oa_bp.route('/api/schedules', methods=['POST'])
def api_create_schedule():
    """新增课程"""
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

    # 自动计算 day_of_week (Python: 0=Monday)
    day_of_week = course_date.weekday()

    schedule = CourseSchedule(
        date=course_date,
        day_of_week=day_of_week,
        time_start=data['time_start'],
        time_end=data['time_end'],
        teacher=data['teacher'],
        course_name=data['course_name'],
        students=data.get('students', ''),
        location=data.get('location', ''),
        notes=data.get('notes', ''),
        color_tag=data.get('color_tag', 'blue')
    )
    db.session.add(schedule)
    db.session.commit()

    return jsonify({'success': True, 'data': schedule.to_dict()}), 201


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['PUT'])
def api_update_schedule(schedule_id):
    """编辑课程"""
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请提供 JSON 数据'}), 400

    if 'date' in data:
        try:
            schedule.date = date.fromisoformat(data['date'])
            schedule.day_of_week = schedule.date.weekday()
        except ValueError:
            return jsonify({'success': False, 'error': '日期格式错误'}), 400

    for field in ['time_start', 'time_end', 'teacher', 'course_name', 'students', 'location', 'notes', 'color_tag']:
        if field in data:
            setattr(schedule, field, data[field])

    db.session.commit()
    return jsonify({'success': True, 'data': schedule.to_dict()})


@oa_bp.route('/api/schedules/<int:schedule_id>', methods=['DELETE'])
def api_delete_schedule(schedule_id):
    """删除课程"""
    schedule = CourseSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({'success': False, 'error': '课程不存在'}), 404

    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'success': True, 'data': {'id': schedule_id}})


@oa_bp.route('/api/schedules/teachers', methods=['GET'])
def api_list_teachers():
    """获取教师去重列表"""
    teachers = db.session.query(CourseSchedule.teacher).distinct().all()
    return jsonify({
        'success': True,
        'data': sorted([t[0] for t in teachers if t[0]])
    })


@oa_bp.route('/api/schedules/students', methods=['GET'])
def api_list_students():
    """获取学生去重列表"""
    rows = db.session.query(CourseSchedule.students).filter(
        CourseSchedule.students.isnot(None),
        CourseSchedule.students != ''
    ).all()

    student_set = set()
    for row in rows:
        for name in row[0].replace('、', ',').replace('，', ',').split(','):
            name = name.strip()
            if name:
                student_set.add(name)

    return jsonify({
        'success': True,
        'data': sorted(student_set)
    })


# ========== 待办事项 API ==========

@oa_bp.route('/api/todos', methods=['GET'])
def api_list_todos():
    """查询待办，支持 ?status=pending|completed|all &person= &priority="""
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

    return jsonify({
        'success': True,
        'data': [t.to_dict() for t in todos],
        'total': len(todos)
    })


@oa_bp.route('/api/todos/<int:todo_id>', methods=['GET'])
def api_get_todo(todo_id):
    """获取单条待办"""
    todo = OATodo.query.get(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos', methods=['POST'])
def api_create_todo():
    """新增待办"""
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
        schedule_id=data.get('schedule_id')
    )
    db.session.add(todo)
    db.session.commit()

    return jsonify({'success': True, 'data': todo.to_dict()}), 201


@oa_bp.route('/api/todos/<int:todo_id>', methods=['PUT'])
def api_update_todo(todo_id):
    """编辑待办"""
    todo = OATodo.query.get(todo_id)
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
                setattr(
                    todo,
                    field,
                    OATodo.normalize_responsible_people(
                        data.get('responsible_people', data.get('responsible_person', ''))
                    )
                )
            else:
                setattr(todo, field, data[field])

    if 'responsible_people' in data and 'responsible_person' not in data:
        todo.responsible_person = OATodo.normalize_responsible_people(data.get('responsible_people', []))

    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def api_delete_todo(todo_id):
    """删除待办"""
    todo = OATodo.query.get(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404

    db.session.delete(todo)
    db.session.commit()
    return jsonify({'success': True, 'data': {'id': todo_id}})


@oa_bp.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
def api_toggle_todo(todo_id):
    """切换待办完成状态"""
    todo = OATodo.query.get(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '待办不存在'}), 404

    todo.is_completed = not todo.is_completed
    db.session.commit()
    return jsonify({'success': True, 'data': todo.to_dict()})


@oa_bp.route('/api/todos/batch', methods=['POST'])
def api_batch_todos():
    """批量操作待办，支持 action: complete/uncomplete/delete"""
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
        for t in todos:
            t.is_completed = True
    elif action == 'uncomplete':
        for t in todos:
            t.is_completed = False
    elif action == 'delete':
        for t in todos:
            db.session.delete(t)
    else:
        return jsonify({'success': False, 'error': f'不支持的操作: {action}'}), 400

    db.session.commit()
    return jsonify({
        'success': True,
        'data': {'action': action, 'affected': len(todos)}
    })


# ========== Excel 导入 API ==========

@oa_bp.route('/api/import-excel', methods=['POST'])
def api_import_excel():
    """上传并导入 Excel 课表数据"""
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': '请上传文件'}), 400

    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'error': '仅支持 .xlsx 或 .xls 文件'}), 400

    import tempfile
    import os
    fd, tmp_path = tempfile.mkstemp(suffix='.xlsx')
    file.save(tmp_path)
    os.close(fd)

    try:
        schedules, todos = import_schedule_from_excel(tmp_path, original_filename=file.filename)
        todos, removed_todo_duplicates = deduplicate_todo_payloads(todos)

        # Clear existing data before reimport to avoid duplicates
        CourseSchedule.query.delete()
        OATodo.query.delete()

        for s in schedules:
            db.session.add(CourseSchedule(**s))

        for t in todos:
            db.session.add(OATodo(**t))

        db.session.commit()
        return jsonify({
            'success': True,
            'data': {
                'schedules_count': len(schedules),
                'todos_count': len(todos),
                'removed_todo_duplicates': removed_todo_duplicates
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'导入失败: {str(e)}'}), 500
    finally:
        os.unlink(tmp_path)


# ========== 仪表盘统计 API ==========

@oa_bp.route('/api/dashboard-stats', methods=['GET'])
def api_dashboard_stats():
    """获取仪表盘统计数据"""
    today = date.today()

    # 今日课程数
    today_count = CourseSchedule.query.filter(CourseSchedule.date == today).count()

    # 待完成待办数
    pending_count = OATodo.query.filter(OATodo.is_completed == False).count()

    # 本周课时（本周一到周日）
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_count = CourseSchedule.query.filter(
        CourseSchedule.date >= monday,
        CourseSchedule.date <= sunday
    ).count()

    # 今日课程列表
    today_schedules = CourseSchedule.query.filter(
        CourseSchedule.date == today
    ).order_by(CourseSchedule.time_start).all()

    return jsonify({
        'success': True,
        'data': {
            'today_count': today_count,
            'pending_todos': pending_count,
            'week_count': week_count,
            'today_schedules': [s.to_dict() for s in today_schedules]
        }
    })
