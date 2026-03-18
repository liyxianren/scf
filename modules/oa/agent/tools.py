"""Tool definitions and execution functions for the scheduling agent."""
import json
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Tool JSON Schemas (ChatGLM function calling format)
# ---------------------------------------------------------------------------

TOOL_GET_TODAY_INFO = {
    "type": "function",
    "function": {
        "name": "get_today_info",
        "description": "获取当前日期信息，包括今天的日期、星期几、本周和下周的起止日期。用于理解'这周'、'下周'、'下个月'等相对时间。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOL_QUERY_SCHEDULES = {
    "type": "function",
    "function": {
        "name": "query_schedules",
        "description": "查询课程安排。可按日期范围、教师、学生、星期几等条件筛选。返回匹配的课程列表（最多100条）。",
        "parameters": {
            "type": "object",
            "properties": {
                "teacher": {
                    "type": "string",
                    "description": "教师姓名，模糊匹配（包含即可）。数据库中教师名格式不统一，可能是'田老师'、'刘硕'、'Barney老师'等，搜索时用姓或名即可",
                },
                "course_name": {
                    "type": "string",
                    "description": "课程名称，模糊匹配（包含即可）",
                },
                "student": {
                    "type": "string",
                    "description": "学生姓名，模糊匹配（包含即可）",
                },
                "date_start": {
                    "type": "string",
                    "description": "起始日期 YYYY-MM-DD",
                },
                "date_end": {
                    "type": "string",
                    "description": "结束日期 YYYY-MM-DD",
                },
                "day_of_week": {
                    "type": "integer",
                    "description": "星期几 (0=周一, 1=周二, ..., 6=周日)",
                },
            },
            "required": [],
        },
    },
}

TOOL_FIND_AVAILABLE_SLOTS = {
    "type": "function",
    "function": {
        "name": "find_available_slots",
        "description": "查找教师的可用空闲时间段。根据教师现有课程和学生的可用时间约束，找出无冲突的空闲时段。返回可用时段列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "teacher": {
                    "type": "string",
                    "description": "教师姓名",
                },
                "date_start": {
                    "type": "string",
                    "description": "搜索起始日期 YYYY-MM-DD",
                },
                "date_end": {
                    "type": "string",
                    "description": "搜索结束日期 YYYY-MM-DD",
                },
                "student_available_slots": {
                    "type": "array",
                    "description": "学生可用时间段列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day_of_week": {
                                "type": "integer",
                                "description": "星期几 (0=周一...6=周日)",
                            },
                            "time_start": {
                                "type": "string",
                                "description": "开始时间 HH:MM",
                            },
                            "time_end": {
                                "type": "string",
                                "description": "结束时间 HH:MM",
                            },
                        },
                        "required": ["day_of_week", "time_start", "time_end"],
                    },
                },
                "duration_hours": {
                    "type": "number",
                    "description": "每节课时长（小时），默认2",
                },
            },
            "required": ["teacher", "date_start", "date_end"],
        },
    },
}

TOOL_PROPOSE_CREATE = {
    "type": "function",
    "function": {
        "name": "propose_create_schedules",
        "description": "提议批量创建课程。生成一个排课方案供用户确认。注意：调用此工具不会直接创建课程，而是生成待确认的方案，用户确认后才会执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "schedules": {
                    "type": "array",
                    "description": "要创建的课程列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "日期 YYYY-MM-DD"},
                            "time_start": {"type": "string", "description": "开始时间 HH:MM"},
                            "time_end": {"type": "string", "description": "结束时间 HH:MM"},
                            "teacher": {"type": "string", "description": "教师姓名"},
                            "course_name": {"type": "string", "description": "课程名称"},
                            "students": {"type": "string", "description": "学生姓名，逗号分隔"},
                            "location": {"type": "string", "description": "上课地点"},
                            "color_tag": {
                                "type": "string",
                                "description": "颜色标签: blue/green/purple/orange/red/teal",
                            },
                        },
                        "required": ["date", "time_start", "time_end", "teacher", "course_name"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "方案摘要说明",
                },
            },
            "required": ["schedules", "summary"],
        },
    },
}

TOOL_PROPOSE_DELETE = {
    "type": "function",
    "function": {
        "name": "propose_delete_schedules",
        "description": "提议删除课程。提供要删除的课程ID列表，生成待确认的删除方案。用户确认后才会执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "schedule_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要删除的课程ID列表",
                },
                "summary": {
                    "type": "string",
                    "description": "删除方案摘要说明",
                },
            },
            "required": ["schedule_ids", "summary"],
        },
    },
}

TOOL_PROPOSE_UPDATE = {
    "type": "function",
    "function": {
        "name": "propose_update_schedules",
        "description": "提议修改课程。指定要修改的课程ID和新的字段值，生成待确认的修改方案。用户确认后才会执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "description": "要修改的课程列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "schedule_id": {"type": "integer", "description": "课程ID"},
                            "new_date": {"type": "string", "description": "新日期 YYYY-MM-DD"},
                            "new_time_start": {"type": "string", "description": "新开始时间 HH:MM"},
                            "new_time_end": {"type": "string", "description": "新结束时间 HH:MM"},
                            "new_teacher": {"type": "string", "description": "新教师"},
                            "new_course_name": {"type": "string", "description": "新课程名称"},
                            "new_students": {"type": "string", "description": "新学生列表"},
                            "new_location": {"type": "string", "description": "新地点"},
                        },
                        "required": ["schedule_id"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "修改方案摘要说明",
                },
            },
            "required": ["updates", "summary"],
        },
    },
}

TOOL_QUERY_TODOS = {
    "type": "function",
    "function": {
        "name": "query_todos",
        "description": "查询待办事项。可按完成状态、负责人、优先级等条件筛选。返回匹配的待办列表（最多100条）。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "待办标题关键词，模糊匹配（包含即可）",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "completed", "all"],
                    "description": "完成状态：pending=待完成, completed=已完成, all=全部",
                },
                "person": {
                    "type": "string",
                    "description": "负责人姓名，模糊匹配（包含即可）",
                },
                "priority": {
                    "type": "integer",
                    "description": "优先级: 1=紧急/红色, 2=一般/蓝色, 3=低优先级/绿色",
                },
            },
            "required": [],
        },
    },
}

TOOL_PROPOSE_CREATE_TODOS = {
    "type": "function",
    "function": {
        "name": "propose_create_todos",
        "description": "提议批量创建待办事项。生成待确认的方案，用户确认后才会执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "要创建的待办列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "待办标题"},
                            "description": {"type": "string", "description": "描述"},
                            "responsible_people": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "负责人列表",
                            },
                            "due_date": {"type": "string", "description": "截止日期 YYYY-MM-DD"},
                            "priority": {"type": "integer", "description": "优先级 1/2/3"},
                            "notes": {"type": "string", "description": "备注"},
                        },
                        "required": ["title"],
                    },
                },
                "summary": {"type": "string", "description": "方案摘要说明"},
            },
            "required": ["todos", "summary"],
        },
    },
}

TOOL_PROPOSE_DELETE_TODOS = {
    "type": "function",
    "function": {
        "name": "propose_delete_todos",
        "description": "提议删除待办事项。提供要删除的待办ID列表，生成待确认的删除方案。",
        "parameters": {
            "type": "object",
            "properties": {
                "todo_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要删除的待办ID列表",
                },
                "summary": {"type": "string", "description": "删除方案摘要说明"},
            },
            "required": ["todo_ids", "summary"],
        },
    },
}

TOOL_PROPOSE_UPDATE_TODOS = {
    "type": "function",
    "function": {
        "name": "propose_update_todos",
        "description": "提议修改待办事项。指定要修改的待办ID和新的字段值，生成待确认的修改方案。也可用于标记完成/未完成。",
        "parameters": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "description": "要修改的待办列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "todo_id": {"type": "integer", "description": "待办ID"},
                            "new_title": {"type": "string", "description": "新标题"},
                            "new_description": {"type": "string", "description": "新描述"},
                            "new_responsible_people": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "新负责人列表",
                            },
                            "new_due_date": {"type": "string", "description": "新截止日期 YYYY-MM-DD"},
                            "new_priority": {"type": "integer", "description": "新优先级"},
                            "new_notes": {"type": "string", "description": "新备注"},
                            "toggle_completion": {"type": "boolean", "description": "切换完成状态"},
                        },
                        "required": ["todo_id"],
                    },
                },
                "summary": {"type": "string", "description": "修改方案摘要说明"},
            },
            "required": ["updates", "summary"],
        },
    },
}

ALL_TOOLS = [
    TOOL_GET_TODAY_INFO,
    TOOL_QUERY_SCHEDULES,
    TOOL_FIND_AVAILABLE_SLOTS,
    TOOL_PROPOSE_CREATE,
    TOOL_PROPOSE_DELETE,
    TOOL_PROPOSE_UPDATE,
    TOOL_QUERY_TODOS,
    TOOL_PROPOSE_CREATE_TODOS,
    TOOL_PROPOSE_DELETE_TODOS,
    TOOL_PROPOSE_UPDATE_TODOS,
]

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _time_to_minutes(t: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _times_overlap(s1: int, e1: int, s2: int, e2: int) -> bool:
    """Check if [s1, e1) overlaps with [s2, e2). All in minutes."""
    return s1 < e2 and s2 < e1


# ---------------------------------------------------------------------------
# Tool execution functions
# ---------------------------------------------------------------------------


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """Dispatch a tool call to the appropriate handler."""
    handlers = {
        "get_today_info": _exec_get_today_info,
        "query_schedules": _exec_query_schedules,
        "find_available_slots": _exec_find_available_slots,
        "propose_create_schedules": _exec_propose_create,
        "propose_delete_schedules": _exec_propose_delete,
        "propose_update_schedules": _exec_propose_update,
        "query_todos": _exec_query_todos,
        "propose_create_todos": _exec_propose_create_todos,
        "propose_delete_todos": _exec_propose_delete_todos,
        "propose_update_todos": _exec_propose_update_todos,
    }
    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"未知工具: {tool_name}"}
    try:
        return handler(arguments)
    except Exception as e:
        return {"error": f"工具执行错误: {e}"}


def _exec_get_today_info(_args: dict) -> dict:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    next_monday = monday + timedelta(days=7)
    return {
        "today": today.isoformat(),
        "day_of_week": today.weekday(),
        "day_of_week_name": DAY_NAMES[today.weekday()],
        "this_week_start": monday.isoformat(),
        "this_week_end": (monday + timedelta(days=6)).isoformat(),
        "next_week_start": next_monday.isoformat(),
        "next_week_end": (next_monday + timedelta(days=6)).isoformat(),
        "this_month": today.strftime("%Y-%m"),
        "next_month_start": (today.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat(),
    }


def _exec_query_schedules(args: dict) -> dict:
    from modules.oa.models import CourseSchedule

    query = CourseSchedule.query

    if args.get("teacher"):
        query = query.filter(CourseSchedule.teacher.contains(args["teacher"]))
    if args.get("course_name"):
        query = query.filter(CourseSchedule.course_name.contains(args["course_name"]))
    if args.get("student"):
        query = query.filter(CourseSchedule.students.contains(args["student"]))
    if args.get("date_start"):
        query = query.filter(CourseSchedule.date >= date.fromisoformat(args["date_start"]))
    if args.get("date_end"):
        query = query.filter(CourseSchedule.date <= date.fromisoformat(args["date_end"]))
    if args.get("day_of_week") is not None:
        query = query.filter(CourseSchedule.day_of_week == args["day_of_week"])

    schedules = query.order_by(CourseSchedule.date, CourseSchedule.time_start).limit(100).all()
    return {
        "schedules": [s.to_dict() for s in schedules],
        "count": len(schedules),
    }


def _exec_find_available_slots(args: dict) -> dict:
    from modules.oa.models import CourseSchedule

    teacher = args["teacher"]
    date_start = date.fromisoformat(args["date_start"])
    date_end = date.fromisoformat(args["date_end"])
    student_slots = args.get("student_available_slots", [])
    duration = args.get("duration_hours", 2)

    # Fetch teacher's existing schedules in the range
    existing = CourseSchedule.query.filter(
        CourseSchedule.teacher.contains(teacher),
        CourseSchedule.date >= date_start,
        CourseSchedule.date <= date_end,
    ).all()

    # Build occupied-time map: {date_iso: [(start_min, end_min), ...]}
    occupied = {}
    for s in existing:
        d = s.date.isoformat()
        occupied.setdefault(d, []).append(
            (_time_to_minutes(s.time_start), _time_to_minutes(s.time_end))
        )

    # If no student slots, use full day range
    if not student_slots:
        student_slots = [
            {"day_of_week": dow, "time_start": "08:00", "time_end": "21:00"}
            for dow in range(7)
        ]

    # Index student slots by day_of_week
    slots_by_dow = {}
    for slot in student_slots:
        dow = slot["day_of_week"]
        slots_by_dow.setdefault(dow, []).append(slot)

    # Find available slots
    available = []
    current = date_start
    while current <= date_end:
        dow = current.weekday()
        d_iso = current.isoformat()
        day_occupied = occupied.get(d_iso, [])

        for slot in slots_by_dow.get(dow, []):
            slot_start = _time_to_minutes(slot["time_start"])
            slot_end = _time_to_minutes(slot["time_end"])

            if (slot_end - slot_start) < duration * 60:
                continue

            has_conflict = any(
                _times_overlap(slot_start, slot_end, occ_s, occ_e)
                for occ_s, occ_e in day_occupied
            )

            if not has_conflict:
                available.append({
                    "date": d_iso,
                    "day_of_week": dow,
                    "day_name": DAY_NAMES[dow],
                    "time_start": slot["time_start"],
                    "time_end": slot["time_end"],
                })

        current += timedelta(days=1)

    return {
        "available_slots": available[:80],
        "total_found": len(available),
        "searched_range": f"{date_start.isoformat()} ~ {date_end.isoformat()}",
    }


def _exec_propose_create(args: dict) -> dict:
    from modules.oa.models import CourseSchedule

    schedules = args["schedules"]
    summary = args["summary"]
    conflicts = []

    for i, s in enumerate(schedules):
        d = date.fromisoformat(s["date"])
        s_start = _time_to_minutes(s["time_start"])
        s_end = _time_to_minutes(s["time_end"])

        existing = CourseSchedule.query.filter(
            CourseSchedule.teacher.contains(s["teacher"]),
            CourseSchedule.date == d,
        ).all()

        for ex in existing:
            ex_start = _time_to_minutes(ex.time_start)
            ex_end = _time_to_minutes(ex.time_end)
            if _times_overlap(s_start, s_end, ex_start, ex_end):
                conflicts.append({
                    "index": i,
                    "date": s["date"],
                    "time": f"{s['time_start']}-{s['time_end']}",
                    "existing_course": f"{ex.course_name} ({ex.time_start}-{ex.time_end})",
                })

    return {
        "action": "create",
        "schedules": schedules,
        "total": len(schedules),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "summary": summary,
        "requires_confirmation": True,
    }


def _exec_propose_delete(args: dict) -> dict:
    from modules.oa.models import CourseSchedule

    ids = args["schedule_ids"]
    summary = args["summary"]

    courses = CourseSchedule.query.filter(CourseSchedule.id.in_(ids)).all()
    found_ids = [c.id for c in courses]
    missing_ids = [i for i in ids if i not in found_ids]

    return {
        "action": "delete",
        "schedule_ids": found_ids,
        "schedules": [c.to_dict() for c in courses],
        "total": len(found_ids),
        "missing_ids": missing_ids,
        "summary": summary,
        "requires_confirmation": True,
    }


def _exec_propose_update(args: dict) -> dict:
    from modules.oa.models import CourseSchedule

    updates = args["updates"]
    summary = args["summary"]
    details = []

    for upd in updates:
        sid = upd["schedule_id"]
        course = CourseSchedule.query.get(sid)
        if not course:
            details.append({"schedule_id": sid, "error": "课程不存在"})
            continue

        changes = {}
        for field in ("new_date", "new_time_start", "new_time_end", "new_teacher",
                       "new_course_name", "new_students", "new_location"):
            if field in upd and upd[field] is not None:
                old_field = field[4:]  # strip "new_"
                changes[old_field] = {"old": getattr(course, old_field, None), "new": upd[field]}

        details.append({
            "schedule_id": sid,
            "current": course.to_dict(),
            "changes": changes,
        })

    return {
        "action": "update",
        "updates": updates,
        "details": details,
        "total": len(updates),
        "summary": summary,
        "requires_confirmation": True,
    }


# ---------------------------------------------------------------------------
# Todo tool execution functions
# ---------------------------------------------------------------------------

PRIORITY_NAMES = {1: "紧急", 2: "一般", 3: "低"}


def _exec_query_todos(args: dict) -> dict:
    from modules.oa.models import OATodo

    query = OATodo.query

    if args.get("title"):
        query = query.filter(OATodo.title.contains(args["title"]))

    status = args.get("status")
    if status == "pending":
        query = query.filter(OATodo.is_completed == False)
    elif status == "completed":
        query = query.filter(OATodo.is_completed == True)

    if args.get("person"):
        query = query.filter(OATodo.responsible_person.contains(args["person"]))
    if args.get("priority"):
        query = query.filter(OATodo.priority == args["priority"])

    todos = query.order_by(OATodo.is_completed, OATodo.priority, OATodo.due_date).limit(100).all()
    return {
        "todos": [t.to_dict() for t in todos],
        "count": len(todos),
    }


def _exec_propose_create_todos(args: dict) -> dict:
    return {
        "action": "create_todos",
        "todos": args["todos"],
        "total": len(args["todos"]),
        "summary": args["summary"],
        "requires_confirmation": True,
    }


def _exec_propose_delete_todos(args: dict) -> dict:
    from modules.oa.models import OATodo

    ids = args["todo_ids"]
    todos = OATodo.query.filter(OATodo.id.in_(ids)).all()
    found_ids = [t.id for t in todos]
    missing_ids = [i for i in ids if i not in found_ids]

    return {
        "action": "delete_todos",
        "todo_ids": found_ids,
        "todos": [t.to_dict() for t in todos],
        "total": len(found_ids),
        "missing_ids": missing_ids,
        "summary": args["summary"],
        "requires_confirmation": True,
    }


def _exec_propose_update_todos(args: dict) -> dict:
    from modules.oa.models import OATodo

    updates = args["updates"]
    details = []

    for upd in updates:
        tid = upd["todo_id"]
        todo = OATodo.query.get(tid)
        if not todo:
            details.append({"todo_id": tid, "error": "待办不存在"})
            continue

        changes = {}
        for field in ("new_title", "new_description", "new_responsible_people",
                       "new_due_date", "new_priority", "new_notes"):
            if field in upd and upd[field] is not None:
                old_field = field[4:]
                changes[old_field] = {"old": getattr(todo, old_field, None), "new": upd[field]}
        if upd.get("toggle_completion"):
            changes["is_completed"] = {"old": todo.is_completed, "new": not todo.is_completed}

        details.append({"todo_id": tid, "current": todo.to_dict(), "changes": changes})

    return {
        "action": "update_todos",
        "updates": updates,
        "details": details,
        "total": len(updates),
        "summary": args["summary"],
        "requires_confirmation": True,
    }
