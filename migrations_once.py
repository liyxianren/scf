"""
一次性数据迁移脚本 —— 修复教师姓名 + 课表颜色标记
在 create_app() 启动时调用，通过数据库标记确保只执行一次。
"""
from extensions import db


def run_once_migrations():
    """入口：检查并执行所有一次性迁移"""
    _ensure_migration_table()

    if not _is_applied('fix_teacher_names_and_colors_v1'):
        _fix_teacher_names()
        _fix_color_tags()
        _mark_applied('fix_teacher_names_and_colors_v1')
        print('[migration] 教师姓名 + 课表颜色修复完成')


# ========== 基础设施 ==========

def _ensure_migration_table():
    db.session.execute(db.text(
        "CREATE TABLE IF NOT EXISTS _applied_migrations "
        "(name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    ))
    db.session.commit()


def _is_applied(name):
    row = db.session.execute(
        db.text("SELECT 1 FROM _applied_migrations WHERE name = :n"),
        {'n': name}
    ).fetchone()
    return row is not None


def _mark_applied(name):
    db.session.execute(
        db.text("INSERT INTO _applied_migrations (name) VALUES (:n)"),
        {'n': name}
    )
    db.session.commit()


# ========== 教师姓名修复 ==========

_TEACHER_RENAMES = {
    '田老师': '田鹏',
    '范老师': '范晓东',
    '刘、范老师': '刘硕、范晓东',
}


def _fix_teacher_names():
    for old, new in _TEACHER_RENAMES.items():
        db.session.execute(
            db.text("UPDATE course_schedules SET teacher = :new WHERE teacher = :old"),
            {'old': old, 'new': new}
        )
    db.session.commit()


# ========== 课表颜色修复 ==========

# 从 Excel「2026年总课表」提取的 (月-日 -> 开始时间 -> 颜色) 映射
# 蓝色=线上课, 橙色=线下课, teal=社团课, purple=特殊
_COLOR_MAP = {
    "01-01": {"16:00": "orange", "14:00": "orange", "18:00": "orange", "19:30": "blue"},
    "01-02": {"10:00": "orange"},
    "01-03": {"10:00": "blue", "14:00": "orange", "16:30": "blue", "15:30": "orange", "18:00": "orange", "20:00": "blue", "09:00": "orange", "18:30": "blue"},
    "01-04": {"10:30": "orange"},
    "01-05": {"09:30": "blue", "18:00": "blue"},
    "01-06": {"10:00": "blue", "18:30": "blue", "19:00": "teal"},
    "01-07": {"09:00": "blue", "17:00": "blue", "18:00": "blue"},
    "01-08": {"17:00": "blue"},
    "01-09": {"09:00": "blue"},
    "01-10": {"09:00": "orange", "10:00": "blue", "10:30": "orange", "14:30": "blue", "14:00": "orange", "18:00": "orange", "20:00": "blue"},
    "01-11": {"10:30": "orange", "15:30": "blue"},
    "01-12": {"17:00": "blue", "18:00": "blue"},
    "01-13": {"09:30": "blue", "17:00": "blue", "19:00": "teal"},
    "01-14": {"09:30": "blue", "18:30": "blue", "18:00": "blue"},
    "01-15": {"17:00": "blue"},
    "01-16": {"09:30": "blue", "18:30": "orange"},
    "01-17": {"09:00": "orange", "20:00": "blue", "10:30": "orange", "14:00": "orange", "14:30": "blue", "15:30": "orange", "16:30": "blue"},
    "01-18": {"10:30": "orange", "13:00": "blue"},
    "01-19": {"18:00": "blue"},
    "01-20": {"10:00": "blue", "18:30": "blue", "18:00": "blue"},
    "01-21": {"09:30": "blue", "17:30": "blue", "17:00": "blue", "18:00": "blue"},
    "01-22": {"17:00": "blue"},
    "01-23": {"18:30": "orange"},
    "01-24": {"09:00": "orange", "10:00": "blue", "14:00": "orange", "14:30": "blue", "15:30": "orange", "18:00": "orange"},
    "01-25": {"10:30": "orange", "13:00": "orange", "15:30": "orange", "19:00": "blue"},
    "01-26": {"09:00": "blue", "18:00": "blue"},
    "01-27": {"09:30": "blue", "17:00": "blue"},
    "01-28": {"09:30": "blue", "17:00": "blue", "18:00": "blue", "19:30": "blue"},
    "01-29": {"14:00": "orange", "17:00": "blue"},
    "01-30": {"18:30": "orange"},
    "01-31": {"09:00": "orange", "10:30": "orange", "10:00": "orange", "14:00": "orange", "14:30": "blue", "20:00": "blue"},
    "02-01": {"10:30": "orange", "09:00": "orange", "14:00": "orange", "15:00": "orange", "17:30": "orange"},
    "02-02": {"09:30": "blue", "18:00": "blue"},
    "02-03": {"14:00": "orange", "13:30": "blue"},
    "02-04": {"18:00": "blue", "19:30": "blue"},
    "02-05": {"14:00": "orange", "17:00": "blue"},
    "02-06": {"18:30": "orange"},
    "02-07": {"09:00": "orange", "10:30": "orange", "15:30": "orange", "20:00": "blue"},
    "02-08": {"10:00": "orange", "19:00": "blue"},
    "02-09": {"10:00": "orange", "09:30": "blue", "18:00": "blue", "19:00": "blue"},
    "02-10": {"10:00": "orange", "14:00": "orange", "20:00": "blue", "19:00": "blue"},
    "02-11": {"10:00": "orange", "18:00": "blue", "19:00": "blue"},
    "02-12": {"10:00": "orange", "17:00": "blue", "19:00": "blue", "18:00": "orange"},
    "02-15": {"15:00": "blue", "16:00": "blue"},
    "02-23": {"09:30": "blue"},
    "02-24": {"19:00": "blue", "20:00": "blue"},
    "02-25": {"18:00": "blue", "19:00": "blue"},
    "02-27": {"10:00": "orange", "16:00": "blue", "20:00": "blue"},
    "03-01": {"13:00": "orange", "14:00": "orange", "18:30": "orange"},
    "03-02": {"09:30": "blue"},
    "03-04": {"17:00": "orange", "19:00": "blue"},
    "03-05": {"19:00": "blue", "17:30": "orange"},
    "03-06": {"20:00": "blue", "19:00": "blue"},
    "03-07": {"10:00": "orange", "14:00": "orange", "14:30": "blue", "15:00": "orange", "15:30": "orange", "19:00": "blue", "21:30": "blue"},
    "03-08": {"13:00": "orange", "09:30": "blue", "13:30": "orange", "14:00": "blue", "18:30": "orange", "19:00": "blue"},
    "03-09": {"09:30": "blue", "18:00": "blue"},
    "03-10": {"18:00": "blue", "17:00": "blue", "19:00": "blue"},
    "03-11": {"18:00": "blue", "17:00": "orange", "19:00": "blue"},
    "03-12": {"17:30": "blue"},
    "03-14": {"09:00": "orange", "10:00": "orange", "15:00": "orange", "14:00": "blue", "14:30": "blue", "15:30": "orange", "20:00": "blue"},
    "03-15": {"10:00": "blue", "13:00": "orange", "13:30": "orange", "15:30": "orange", "14:00": "orange", "18:30": "orange", "20:00": "blue"},
    "03-16": {"09:30": "blue", "18:00": "blue"},
    "03-17": {"09:30": "blue", "17:00": "blue"},
    "03-18": {"18:00": "blue"},
    "03-19": {"17:30": "blue"},
    "03-21": {"09:00": "orange", "14:00": "orange", "14:30": "blue", "15:30": "orange"},
    "03-22": {"14:00": "orange", "13:00": "orange", "13:30": "orange"},
    "03-23": {"18:00": "blue"},
    "03-25": {"18:00": "blue"},
    "03-26": {"17:30": "blue"},
    "03-28": {"09:00": "orange", "14:00": "orange", "14:30": "blue", "15:30": "orange"},
    "03-29": {"13:00": "orange", "13:30": "orange", "14:00": "orange"},
    "03-30": {"18:00": "blue"},
    "04-01": {"18:00": "blue"},
    "04-02": {"17:30": "blue"},
    "04-04": {"09:00": "orange", "14:30": "blue"},
    "04-05": {"13:00": "orange", "13:30": "orange", "14:00": "orange"},
    "04-06": {"18:00": "blue"},
    "04-08": {"18:00": "blue"},
    "04-09": {"17:30": "blue"},
    "04-11": {"14:00": "blue", "15:30": "blue"},
    "04-12": {"13:00": "orange", "13:30": "orange", "14:00": "orange"},
    "04-13": {"18:00": "blue"},
    "04-14": {"19:00": "blue"},
    "04-15": {"18:00": "blue"},
    "04-16": {"17:30": "blue"},
    "04-18": {"09:30": "blue", "14:00": "blue", "15:30": "blue"},
    "04-19": {"13:00": "orange", "13:30": "orange", "14:00": "orange"},
    "04-20": {"18:00": "blue"},
    "04-21": {"19:00": "blue"},
    "04-22": {"18:00": "blue"},
    "04-25": {"14:00": "blue", "15:30": "blue"},
    "04-26": {"13:00": "orange", "13:30": "orange"},
    "04-27": {"18:00": "blue"},
    "05-02": {"14:00": "blue", "15:30": "blue"},
    "05-03": {"13:00": "orange", "13:30": "orange"},
    "05-05": {"18:30": "blue"},
    "05-10": {"13:30": "orange"},
    "05-16": {"14:00": "blue", "15:30": "blue"},
    "05-17": {"13:30": "orange"},
    "05-18": {"18:30": "orange"},
    "05-19": {"18:30": "blue"},
    "05-23": {"14:00": "blue", "15:30": "blue"},
    "05-24": {"13:30": "orange"},
    "05-30": {"14:00": "blue", "15:30": "blue"},
    "05-31": {"13:30": "orange"},
    "06-06": {"14:00": "blue", "15:30": "blue"},
    "06-07": {"13:30": "orange"},
    "06-13": {"14:00": "blue", "15:30": "blue"},
    "06-14": {"13:30": "orange"},
    "06-20": {"14:00": "blue", "15:30": "blue"},
    "06-21": {"13:30": "orange"},
    "06-27": {"14:00": "blue", "15:30": "blue"},
    "06-28": {"13:30": "orange"},
    "07-04": {"14:00": "blue", "15:30": "blue"},
    "07-05": {"13:30": "orange"},
    "07-11": {"14:00": "blue", "15:30": "blue"},
    "07-12": {"13:30": "orange"},
    "07-18": {"14:00": "blue", "15:30": "blue"},
    "07-19": {"13:30": "orange"},
    "07-25": {"15:30": "blue"},
    "07-26": {"13:30": "orange"},
    "08-01": {"15:30": "blue"},
    "08-02": {"13:30": "orange"},
    "08-08": {"15:30": "blue"},
    "08-09": {"13:30": "orange"},
    "08-16": {"13:30": "orange"},
    "08-23": {"13:30": "orange"},
    "08-30": {"13:30": "orange"},
    "09-06": {"13:30": "orange"},
    "09-13": {"13:30": "orange"},
    "09-27": {"13:30": "orange"},
    "11-03": {"18:00": "blue"},
    "11-04": {"18:30": "blue", "19:00": "teal", "20:00": "blue"},
    "11-05": {"17:00": "blue", "18:00": "blue", "14:00": "orange", "19:30": "blue", "20:00": "blue"},
    "11-06": {"17:00": "blue", "13:00": "orange", "19:00": "blue"},
    "11-07": {"16:00": "orange", "18:00": "orange", "19:00": "orange"},
    "11-08": {"09:00": "orange", "10:00": "blue", "10:15": "blue", "14:00": "orange", "15:00": "orange", "15:30": "orange", "16:00": "orange", "16:30": "blue", "16:45": "blue", "18:30": "orange", "20:00": "blue", "21:00": "blue"},
    "11-09": {"10:00": "orange", "10:30": "orange", "13:00": "orange", "15:30": "blue", "20:00": "blue", "19:00": "blue"},
    "11-10": {"18:00": "blue"},
    "11-11": {"18:30": "blue", "19:00": "teal", "20:00": "blue"},
    "11-12": {"17:00": "blue", "18:00": "blue", "19:30": "blue"},
    "11-13": {"17:00": "blue"},
    "11-14": {"09:00": "orange", "14:00": "orange", "19:00": "orange"},
    "11-15": {"10:00": "blue", "14:00": "orange", "15:30": "orange", "16:00": "orange", "16:30": "blue", "18:30": "orange", "20:00": "blue"},
    "11-16": {"08:30": "blue", "09:00": "orange", "10:00": "orange", "10:30": "orange", "13:00": "orange", "15:30": "orange", "19:00": "blue", "18:00": "orange"},
    "11-17": {"18:00": "blue"},
    "11-18": {"19:00": "teal", "18:30": "blue", "20:00": "blue"},
    "11-19": {"17:00": "blue", "19:30": "blue", "18:00": "blue"},
    "11-20": {"17:00": "blue"},
    "11-21": {"19:00": "blue", "18:00": "orange"},
    "11-22": {"09:00": "blue", "10:00": "orange", "14:00": "orange", "15:30": "orange", "16:30": "blue", "17:00": "blue", "16:00": "blue", "18:00": "blue", "19:00": "blue", "20:00": "blue"},
    "11-23": {"10:00": "orange", "10:30": "orange", "13:00": "orange", "14:00": "orange", "20:00": "blue", "19:00": "blue"},
    "11-24": {"18:00": "blue"},
    "11-25": {"19:00": "teal", "18:30": "blue", "20:00": "blue"},
    "11-26": {"17:00": "blue", "19:30": "blue", "18:00": "blue"},
    "11-27": {"17:00": "blue"},
    "11-28": {"20:00": "blue", "18:00": "orange"},
    "11-29": {"09:00": "orange", "10:00": "blue", "14:00": "orange", "16:30": "blue", "15:30": "orange", "16:00": "orange", "17:00": "blue", "18:00": "orange", "20:00": "blue"},
    "11-30": {"10:00": "orange", "10:30": "orange", "13:00": "orange", "17:00": "blue", "19:00": "blue", "20:00": "blue"},
    "12-01": {"18:00": "blue"},
    "12-02": {"19:00": "teal", "18:30": "blue"},
    "12-03": {"17:00": "blue", "18:00": "blue", "19:30": "blue"},
    "12-04": {"16:00": "orange", "17:00": "blue"},
    "12-06": {"09:00": "orange", "10:00": "blue", "13:00": "orange", "14:00": "orange", "15:30": "orange", "16:00": "orange", "16:30": "blue", "18:00": "orange", "17:30": "blue", "20:00": "blue"},
    "12-07": {"10:00": "blue", "10:30": "orange", "13:00": "orange", "14:00": "orange", "20:00": "blue", "19:00": "blue", "21:00": "blue"},
    "12-08": {"18:00": "blue"},
    "12-09": {"19:00": "teal", "18:30": "blue"},
    "12-10": {"17:00": "blue", "18:00": "blue", "18:30": "blue"},
    "12-11": {"16:00": "orange", "17:00": "blue"},
    "12-12": {"16:30": "purple"},
    "12-13": {"09:00": "orange", "10:00": "blue", "12:30": "orange", "14:00": "purple", "15:30": "orange", "16:00": "blue", "16:30": "blue", "18:00": "orange", "20:00": "blue"},
    "12-14": {"10:00": "orange", "10:30": "orange", "20:00": "blue"},
    "12-15": {"18:00": "blue"},
    "12-16": {"19:00": "teal", "18:30": "blue"},
    "12-17": {"17:00": "blue", "18:00": "blue", "19:30": "blue"},
    "12-18": {"16:00": "orange", "17:00": "blue"},
    "12-19": {"19:00": "orange"},
    "12-20": {"10:00": "blue", "11:00": "orange", "13:00": "blue", "14:00": "orange", "15:30": "orange", "16:00": "orange", "16:30": "blue", "18:00": "orange", "20:00": "blue"},
    "12-21": {"10:00": "blue", "10:30": "orange", "12:30": "orange", "20:00": "blue"},
    "12-22": {"10:40": "blue", "14:00": "orange", "18:00": "blue"},
    "12-23": {"08:30": "blue", "10:40": "blue", "14:00": "orange", "19:00": "blue"},
    "12-24": {"10:40": "blue", "14:00": "orange", "18:00": "blue", "19:00": "blue", "19:30": "blue"},
    "12-25": {"16:00": "orange", "19:00": "blue"},
    "12-26": {"10:00": "orange", "19:00": "blue"},
    "12-27": {"10:00": "blue", "09:00": "orange", "11:00": "orange", "14:00": "orange", "16:00": "orange", "16:30": "blue", "15:30": "orange", "20:00": "blue"},
    "12-28": {"10:00": "blue", "10:30": "orange", "14:30": "orange"},
    "12-29": {"09:00": "blue", "10:40": "blue", "18:00": "blue", "19:30": "blue"},
    "12-30": {"10:40": "blue", "19:00": "orange", "11:00": "blue"},
    "12-31": {"10:00": "blue", "09:00": "blue", "18:00": "blue", "19:30": "blue", "14:30": "orange"},
}


def _fix_color_tags():
    from modules.oa.models import CourseSchedule
    schedules = CourseSchedule.query.all()
    updated = 0
    for s in schedules:
        md_key = s.date.strftime('%m-%d')
        time_map = _COLOR_MAP.get(md_key)
        if not time_map:
            continue
        color = time_map.get(s.time_start)
        if not color:
            # 尝试不带前导零
            color = time_map.get(s.time_start.lstrip('0'))
        if color and color != s.color_tag:
            s.color_tag = color
            updated += 1
    db.session.commit()
    print(f'[migration] 更新了 {updated} 条课表颜色')
