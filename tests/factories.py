import json
from datetime import date, datetime, timedelta
from itertools import count

from extensions import db
from modules.auth.models import (
    ChatMessage,
    Enrollment,
    LeaveRequest,
    StudentProfile,
    TeacherAvailability,
    User,
)
from modules.auth.services import generate_intake_token
from modules.oa.models import CourseFeedback, CourseSchedule, OATodo


_sequence = count(1)


def _persist(model):
    db.session.add(model)
    db.session.commit()
    return model


def _next_name(prefix):
    return f'{prefix}-{next(_sequence)}'


def create_user(
    *,
    username=None,
    display_name=None,
    role='admin',
    password='scf123',
    phone='13000000000',
    is_active=True,
):
    username = username or _next_name(role)
    display_name = display_name or username
    user = User(
        username=username,
        display_name=display_name,
        role=role,
        phone=phone,
        is_active=is_active,
    )
    user.set_password(password)
    return _persist(user)


def create_teacher_availability(
    user,
    *,
    day_of_week=0,
    time_start='10:00',
    time_end='12:00',
    is_preferred=False,
):
    slot = TeacherAvailability(
        user_id=user.id,
        day_of_week=day_of_week,
        time_start=time_start,
        time_end=time_end,
        is_preferred=is_preferred,
    )
    return _persist(slot)


def create_student_profile(
    *,
    user=None,
    name=None,
    phone='13000000000',
    available_slots=None,
    excluded_dates=None,
    parent_phone=None,
    notes=None,
):
    if available_slots is None:
        available_slots = [{'day': 0, 'start': '10:00', 'end': '12:00'}]
    profile = StudentProfile(
        user_id=user.id if user else None,
        name=name or (user.display_name if user else _next_name('student')),
        phone=phone,
        parent_phone=parent_phone,
        available_slots=json.dumps(available_slots, ensure_ascii=False),
        excluded_dates=json.dumps(excluded_dates, ensure_ascii=False) if excluded_dates else None,
        notes=notes,
    )
    return _persist(profile)


def create_enrollment(
    *,
    teacher,
    student_name='测试学生',
    course_name='Python 入门',
    status='pending_info',
    student_profile=None,
    total_hours=20,
    hours_per_session=2.0,
    sessions_per_week=1,
    intake_token=None,
    token_expires_at=None,
    proposed_slots=None,
    confirmed_slot=None,
    notes=None,
):
    enrollment = Enrollment(
        student_name=student_name,
        course_name=course_name,
        teacher_id=teacher.id,
        total_hours=total_hours,
        hours_per_session=hours_per_session,
        sessions_per_week=sessions_per_week,
        status=status,
        intake_token=intake_token or generate_intake_token(),
        token_expires_at=token_expires_at or (datetime.utcnow() + timedelta(days=7)),
        student_profile_id=student_profile.id if student_profile else None,
        proposed_slots=json.dumps(proposed_slots, ensure_ascii=False) if proposed_slots is not None else None,
        confirmed_slot=json.dumps(confirmed_slot, ensure_ascii=False) if confirmed_slot is not None else None,
        notes=notes,
    )
    return _persist(enrollment)


def create_chat_message(
    *,
    sender,
    receiver,
    content='测试消息',
    enrollment=None,
    is_read=False,
):
    msg = ChatMessage(
        sender_id=sender.id,
        receiver_id=receiver.id,
        enrollment_id=enrollment.id if enrollment else None,
        content=content,
        is_read=is_read,
    )
    return _persist(msg)


def create_schedule(
    *,
    teacher,
    course_name='Python 入门',
    students='测试学生',
    schedule_date=None,
    day_of_week=None,
    time_start='10:00',
    time_end='12:00',
    enrollment=None,
    location='线上',
    notes='',
    color_tag='blue',
):
    schedule_date = schedule_date or date.today()
    schedule = CourseSchedule(
        date=schedule_date,
        day_of_week=schedule_date.weekday() if day_of_week is None else day_of_week,
        time_start=time_start,
        time_end=time_end,
        teacher=teacher.display_name if hasattr(teacher, 'display_name') else str(teacher),
        teacher_id=getattr(teacher, 'id', None),
        course_name=course_name,
        enrollment_id=enrollment.id if enrollment else None,
        students=students,
        location=location,
        notes=notes,
        color_tag=color_tag,
    )
    return _persist(schedule)


def create_todo(
    *,
    title='测试待办',
    responsible_person='管理员',
    due_date=None,
    priority=2,
    schedule=None,
    enrollment=None,
    leave_request=None,
    is_completed=False,
    notes='',
    todo_type=OATodo.TODO_TYPE_GENERIC,
    workflow_status=None,
    created_by=None,
    completed_at=None,
    payload=None,
):
    todo = OATodo(
        title=title,
        responsible_person=responsible_person,
        due_date=due_date,
        priority=priority,
        schedule_id=schedule.id if schedule else None,
        enrollment_id=enrollment.id if enrollment else None,
        leave_request_id=leave_request.id if leave_request else None,
        is_completed=is_completed,
        notes=notes,
        todo_type=todo_type,
        workflow_status=workflow_status,
        created_by=created_by.id if hasattr(created_by, 'id') else created_by,
        completed_at=completed_at,
        payload=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
    )
    return _persist(todo)


def create_feedback(
    *,
    schedule,
    teacher,
    summary='课程总结',
    homework='课后作业',
    next_focus='下次重点',
    status='draft',
    submitted_at=None,
):
    feedback = CourseFeedback(
        schedule_id=schedule.id,
        teacher_id=teacher.id,
        summary=summary,
        homework=homework,
        next_focus=next_focus,
        status=status,
        submitted_at=submitted_at,
    )
    return _persist(feedback)


def create_leave_request(
    *,
    schedule,
    student_name='测试学生',
    enrollment=None,
    reason='临时有事',
    status='pending',
    approved_by=None,
):
    leave = LeaveRequest(
        enrollment_id=enrollment.id if enrollment else None,
        student_name=student_name,
        schedule_id=schedule.id,
        leave_date=schedule.date,
        reason=reason,
        status=status,
        approved_by=approved_by.id if approved_by else None,
    )
    return _persist(leave)
