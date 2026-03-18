"""自动排课算法、token生成、员工账号初始化"""
import io
import json
import secrets
from datetime import datetime, timedelta, date
from extensions import db


def generate_intake_token():
    """生成学生填表链接的 token"""
    return secrets.token_urlsafe(32)


def _time_to_minutes(t):
    """'14:00' → 840"""
    h, m = t.split(':')
    return int(h) * 60 + int(m)


def _minutes_to_time(minutes):
    """840 → '14:00'"""
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _compute_overlap(a_start, a_end, b_start, b_end, min_duration_minutes):
    """计算两个时间段的重叠区间，重叠时长必须 >= min_duration_minutes"""
    start = max(_time_to_minutes(a_start), _time_to_minutes(b_start))
    end = min(_time_to_minutes(a_end), _time_to_minutes(b_end))
    if end - start >= min_duration_minutes:
        return (_minutes_to_time(start), _minutes_to_time(end))
    return None


def _generate_date_preview(day_of_week, total_sessions, excluded_set):
    """生成具体上课日期列表，跳过排除日期，从本周开始"""
    today = date.today()
    days_ahead = day_of_week - today.weekday()
    if days_ahead < 0:
        days_ahead += 7
    next_date = today + timedelta(days=days_ahead)

    dates = []
    skipped = []
    week_idx = 0
    while len(dates) < total_sessions and week_idx < total_sessions + 52:
        d = next_date + timedelta(weeks=week_idx)
        week_idx += 1
        if d.isoformat() in excluded_set:
            skipped.append(d.isoformat())
            continue
        dates.append(d.isoformat())
    return dates, skipped


def find_matching_slots(enrollment_id):
    """自动匹配排课，返回最多 3 个候选方案（含具体日期预览）

    Returns:
        (candidates: list, error: str|None)
    """
    from modules.auth.models import Enrollment, TeacherAvailability, StudentProfile
    from modules.oa.models import CourseSchedule

    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return [], '报名记录不存在'

    min_minutes = int(enrollment.hours_per_session * 60)

    # 总节数
    if enrollment.total_hours and enrollment.hours_per_session:
        total_sessions = int(enrollment.total_hours / enrollment.hours_per_session)
    else:
        total_sessions = 16

    # 老师可用时间
    teacher_name = enrollment.teacher.display_name if enrollment.teacher else '该教师'
    teacher_slots = TeacherAvailability.query.filter_by(user_id=enrollment.teacher_id).all()
    if not teacher_slots:
        return [], f'{teacher_name} 尚未设置可用时间，请先在面板中设置'

    # 学生可用时间
    student_profile = enrollment.student_profile
    if not student_profile or not student_profile.available_slots:
        return [], '学生尚未提交可用时间信息'

    try:
        student_slots = json.loads(student_profile.available_slots)
    except (json.JSONDecodeError, TypeError):
        return [], '学生可用时间数据异常'

    # 学生排除日期
    excluded_set = set()
    if student_profile.excluded_dates:
        try:
            for d_str in json.loads(student_profile.excluded_dates):
                excluded_set.add(d_str)
        except (json.JSONDecodeError, TypeError):
            pass

    # 查询老师现有课程（检测冲突）
    existing_schedules = CourseSchedule.query.filter_by(
        teacher=enrollment.teacher.display_name).all()
    existing_by_day = {}
    for s in existing_schedules:
        existing_by_day.setdefault(s.day_of_week, []).append(s)

    # 学生原始时段按 day 索引（用于偏好加分）
    student_by_day = {}
    for s_slot in student_slots:
        student_by_day.setdefault(s_slot.get('day'), []).append(s_slot)

    candidates = []

    for t_slot in teacher_slots:
        for s_slot in student_slots:
            if t_slot.day_of_week != s_slot.get('day'):
                continue

            overlap = _compute_overlap(
                t_slot.time_start, t_slot.time_end,
                s_slot.get('start', ''), s_slot.get('end', ''),
                min_minutes
            )
            if not overlap:
                continue

            overlap_start_min = _time_to_minutes(overlap[0])
            overlap_end_min = _time_to_minutes(overlap[1])

            # 在重叠区间内按 hours_per_session 切出具体时间块
            cursor = overlap_start_min
            while cursor + min_minutes <= overlap_end_min:
                block_start = _minutes_to_time(cursor)
                block_end = _minutes_to_time(cursor + min_minutes)

                # 冲突检测：这个具体时间块是否和老师已有课冲突
                conflicts = []
                for existing in existing_by_day.get(t_slot.day_of_week, []):
                    if _compute_overlap(block_start, block_end,
                                        existing.time_start, existing.time_end, 1):
                        conflicts.append({
                            'course_name': existing.course_name,
                            'time': f'{existing.time_start}-{existing.time_end}',
                            'students': existing.students,
                        })

                # 打分（偏向学生 + 老师偏好）
                score = 0
                if not conflicts:
                    score += 3  # 无冲突
                if t_slot.is_preferred:
                    score += 1  # 老师偏好

                # 学生精确匹配加分：块完全落在学生某段可用时间内
                s_start_min = _time_to_minutes(s_slot.get('start', ''))
                s_end_min = _time_to_minutes(s_slot.get('end', ''))
                if cursor >= s_start_min and cursor + min_minutes <= s_end_min:
                    score += 2  # 完全匹配学生意向

                candidates.append({
                    'day_of_week': t_slot.day_of_week,
                    'time_start': block_start,
                    'time_end': block_end,
                    'score': score,
                    'is_preferred': t_slot.is_preferred,
                    'conflicts': conflicts,
                })

                cursor += 60  # 每小时步进

    # 去重（同天同时段只保留最高分）
    seen = {}
    for c in candidates:
        key = (c['day_of_week'], c['time_start'], c['time_end'])
        if key not in seen or c['score'] > seen[key]['score']:
            seen[key] = c
    candidates = list(seen.values())

    # 按分数排序，取 top 3
    candidates.sort(key=lambda x: (-x['score'], x['day_of_week'],
                                    _time_to_minutes(x['time_start'])))
    result = candidates[:3]

    if not result:
        return [], '老师和学生的可用时间没有重叠，无法自动匹配'

    # 为每个方案生成具体日期预览
    for slot in result:
        dates, skipped = _generate_date_preview(
            slot['day_of_week'], total_sessions, excluded_set)
        slot['dates'] = dates
        slot['skipped_dates'] = skipped
        slot['total_sessions'] = total_sessions

    return result, None


def propose_enrollment_schedule(enrollment_id, slot_index):
    """管理员选择方案 → 保存日期 + 通知学生确认（不创建课表记录）

    Returns:
        (success: bool, message: str, dates: list)
    """
    from modules.auth.models import Enrollment

    enrollment = Enrollment.query.get(enrollment_id)
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

    slot = proposed[slot_index]
    day_of_week = slot['day_of_week']

    # 计算总节数
    if enrollment.total_hours and enrollment.hours_per_session:
        total_sessions = int(enrollment.total_hours / enrollment.hours_per_session)
    else:
        total_sessions = 16

    # 获取学生排除日期
    excluded_set = set()
    profile = enrollment.student_profile
    if profile and profile.excluded_dates:
        try:
            for d_str in json.loads(profile.excluded_dates):
                excluded_set.add(d_str)
        except (json.JSONDecodeError, TypeError):
            pass

    # 从本周开始计算日期
    today = date.today()
    days_ahead = day_of_week - today.weekday()
    if days_ahead < 0:
        days_ahead += 7
    next_date = today + timedelta(days=days_ahead)

    dates = []
    skipped = []
    week_idx = 0
    while len(dates) < total_sessions and week_idx < total_sessions + 52:
        d = next_date + timedelta(weeks=week_idx)
        week_idx += 1
        if d.isoformat() in excluded_set:
            skipped.append(d.isoformat())
            continue
        dates.append(d.isoformat())

    # 存入 confirmed_slot（含日期列表）
    slot['dates'] = dates
    slot['skipped_dates'] = skipped
    slot['total_sessions'] = total_sessions
    enrollment.confirmed_slot = json.dumps(slot, ensure_ascii=False)
    enrollment.status = 'pending_student_confirm'

    # 自动发送站内消息通知学生
    _send_schedule_notification(enrollment, slot, dates)

    db.session.commit()

    msg = f'已通知学生确认，共 {len(dates)} 节课'
    if skipped:
        msg += f'（跳过 {len(skipped)} 个不可上课日期）'
    return True, msg, dates


def _send_schedule_notification(enrollment, slot, dates):
    """通过 ChatMessage 通知学生查看排课方案"""
    from modules.auth.models import ChatMessage

    profile = enrollment.student_profile
    if not profile or not profile.user_id:
        return

    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    day_name = day_names[slot['day_of_week']] if slot['day_of_week'] < len(day_names) else ''

    content = (
        f'你的课程「{enrollment.course_name}」排课方案已准备好，请确认：\n\n'
        f'上课时间：每{day_name} {slot["time_start"]}-{slot["time_end"]}\n'
        f'共 {len(dates)} 节课\n'
        f'首次上课：{dates[0] if dates else "待定"}\n'
        f'最后一课：{dates[-1] if dates else "待定"}\n\n'
        f'请前往「我的课表」页面查看并确认。'
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
    """学生确认排课 → 创建 CourseSchedule 记录

    Returns:
        (success: bool, message: str, created_count: int)
    """
    from modules.auth.models import Enrollment
    from modules.oa.models import CourseSchedule

    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return False, '报名记录不存在', 0

    if enrollment.status != 'pending_student_confirm':
        return False, '当前状态不允许确认', 0

    if not enrollment.confirmed_slot:
        return False, '没有待确认的排课方案', 0

    try:
        slot = json.loads(enrollment.confirmed_slot)
    except (json.JSONDecodeError, TypeError):
        return False, '排课方案数据异常', 0

    day_of_week = slot['day_of_week']
    time_start = slot['time_start']
    time_end = slot['time_end']
    dates = slot.get('dates', [])

    teacher_name = enrollment.teacher.display_name if enrollment.teacher else ''
    student_name = enrollment.student_name

    created_count = 0
    for d_str in dates:
        course_date = date.fromisoformat(d_str)
        schedule = CourseSchedule(
            date=course_date,
            day_of_week=day_of_week,
            time_start=time_start,
            time_end=time_end,
            teacher=teacher_name,
            course_name=enrollment.course_name,
            students=student_name,
            color_tag='green',
            notes=f'自动排课 - 报名#{enrollment.id}',
        )
        db.session.add(schedule)
        created_count += 1

    enrollment.status = 'confirmed'
    db.session.commit()

    return True, f'已生成 {created_count} 节课程', created_count


def export_enrollment_schedule_xlsx(enrollment_id):
    """导出排课课表为 .xlsx 文件

    Returns:
        (BytesIO, filename, error)
    """
    from modules.auth.models import Enrollment
    from modules.oa.models import CourseSchedule
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    enrollment = Enrollment.query.get(enrollment_id)
    if not enrollment:
        return None, None, '报名记录不存在'

    if not enrollment.confirmed_slot:
        return None, None, '尚未确认排课方案'

    try:
        slot = json.loads(enrollment.confirmed_slot)
    except (json.JSONDecodeError, TypeError):
        return None, None, '排课数据异常'

    dates = slot.get('dates', [])
    teacher_name = enrollment.teacher.display_name if enrollment.teacher else ''
    day_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

    # 如果已有 CourseSchedule 记录，优先从 DB 读取
    schedules = CourseSchedule.query.filter(
        CourseSchedule.course_name == enrollment.course_name,
        CourseSchedule.students.contains(enrollment.student_name),
        CourseSchedule.teacher == teacher_name,
    ).order_by(CourseSchedule.date).all()

    wb = Workbook()
    ws = wb.active
    ws.title = '课程表'

    # 标题行
    header_fill = PatternFill(start_color='0EA5E9', end_color='0EA5E9', fill_type='solid')
    header_font = Font(bold=True, size=11, color='FFFFFF')
    headers = ['序号', '日期', '星期', '开始时间', '结束时间', '课程名称', '授课教师', '学生']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    if schedules:
        for i, s in enumerate(schedules, 1):
            ws.append([i, s.date.isoformat(), day_names[s.day_of_week],
                       s.time_start, s.time_end, s.course_name, s.teacher, s.students])
    else:
        for i, d_str in enumerate(dates, 1):
            d = date.fromisoformat(d_str)
            ws.append([i, d_str, day_names[d.weekday()],
                       slot['time_start'], slot['time_end'],
                       enrollment.course_name, teacher_name, enrollment.student_name])

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f'{enrollment.student_name}_{enrollment.course_name}_课程表.xlsx'
    return output, filename, None


def seed_staff_accounts():
    """将现有硬编码员工初始化为用户账号"""
    from modules.auth.models import User

    STAFF = [
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
    for username, display_name, role, password in STAFF:
        if User.query.filter_by(username=username).first():
            continue
        user = User(username=username, display_name=display_name, role=role)
        user.set_password(password)
        db.session.add(user)
        created += 1

    if created > 0:
        db.session.commit()
    return created
