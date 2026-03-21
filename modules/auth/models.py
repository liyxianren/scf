import json
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db


class User(UserMixin, db.Model):
    """用户表 — 管理员/老师/学生"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' | 'teacher' | 'student'
    phone = db.Column(db.String(30))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    teacher_slots = db.relationship('TeacherAvailability', backref='user', lazy=True,
                                    cascade='all, delete-orphan')
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False, lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'role': self.role,
            'phone': self.phone,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class StudentProfile(db.Model):
    """学生档案"""
    __tablename__ = 'student_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.String(50))
    school = db.Column(db.String(200))
    phone = db.Column(db.String(30))
    parent_phone = db.Column(db.String(30))
    has_experience = db.Column(db.Boolean, default=False)
    experience_detail = db.Column(db.Text)
    available_slots = db.Column(db.Text)  # JSON: [{"day":1,"start":"14:00","end":"16:00"}]
    excluded_dates = db.Column(db.Text)   # JSON: ["2026-05-01","2026-05-02"] 学生不可上课的具体日期
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        slots = []
        if self.available_slots:
            try:
                slots = json.loads(self.available_slots)
            except (json.JSONDecodeError, TypeError):
                pass
        excl = []
        if self.excluded_dates:
            try:
                excl = json.loads(self.excluded_dates)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'grade': self.grade,
            'school': self.school,
            'phone': self.phone,
            'parent_phone': self.parent_phone,
            'has_experience': self.has_experience,
            'experience_detail': self.experience_detail,
            'available_slots': slots,
            'excluded_dates': excl,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TeacherAvailability(db.Model):
    """老师每周可用时间段"""
    __tablename__ = 'teacher_availability'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=周一..6=周日
    time_start = db.Column(db.String(10), nullable=False)  # "14:00"
    time_end = db.Column(db.String(10), nullable=False)    # "18:00"
    is_preferred = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'day_of_week': self.day_of_week,
            'time_start': self.time_start,
            'time_end': self.time_end,
            'is_preferred': self.is_preferred,
        }


class Enrollment(db.Model):
    """报名/签约记录"""
    __tablename__ = 'enrollments'

    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    course_name = db.Column(db.String(200), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_hours = db.Column(db.Integer)
    hours_per_session = db.Column(db.Float, default=2.0)
    sessions_per_week = db.Column(db.Integer, default=1)
    status = db.Column(db.String(30), default='pending_info')
    # pending_info → pending_schedule → pending_student_confirm → confirmed → active → completed
    intake_token = db.Column(db.String(64), unique=True)
    token_expires_at = db.Column(db.DateTime)
    student_profile_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=True)
    proposed_slots = db.Column(db.Text)   # JSON: 自动匹配结果
    confirmed_slot = db.Column(db.Text)   # JSON: 教务确认的时段
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher = db.relationship('User', foreign_keys=[teacher_id])
    student_profile = db.relationship('StudentProfile', backref='enrollment', foreign_keys=[student_profile_id])
    schedules = db.relationship('CourseSchedule', back_populates='enrollment', lazy=True)

    def to_dict(self):
        import json
        proposed = []
        if self.proposed_slots:
            try:
                proposed = json.loads(self.proposed_slots)
            except (json.JSONDecodeError, TypeError):
                pass
        confirmed = None
        if self.confirmed_slot:
            try:
                confirmed = json.loads(self.confirmed_slot)
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            'id': self.id,
            'student_name': self.student_name,
            'course_name': self.course_name,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.display_name if self.teacher else None,
            'total_hours': self.total_hours,
            'hours_per_session': self.hours_per_session,
            'sessions_per_week': self.sessions_per_week,
            'status': self.status,
            'intake_token': self.intake_token,
            'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
            'student_profile_id': self.student_profile_id,
            'student_profile': self.student_profile.to_dict() if self.student_profile else None,
            'proposed_slots': proposed,
            'confirmed_slot': confirmed,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LeaveRequest(db.Model):
    """请假申请"""
    __tablename__ = 'leave_requests'

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=True)
    student_name = db.Column(db.String(100), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('course_schedules.id'), nullable=False)
    makeup_schedule_id = db.Column(db.Integer, db.ForeignKey('course_schedules.id'), nullable=True)
    makeup_available_slots_json = db.Column(db.Text)
    makeup_excluded_dates_json = db.Column(db.Text)
    makeup_preference_note = db.Column(db.Text)
    leave_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    decision_comment = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending / approved / rejected
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    schedule = db.relationship('CourseSchedule', foreign_keys=[schedule_id], overlaps='leave_requests,schedule_record')
    makeup_schedule = db.relationship('CourseSchedule', foreign_keys=[makeup_schedule_id])
    enrollment = db.relationship('Enrollment', foreign_keys=[enrollment_id])
    approver = db.relationship('User', foreign_keys=[approved_by])

    def to_dict(self):
        makeup_available_slots = []
        if self.makeup_available_slots_json:
            try:
                makeup_available_slots = json.loads(self.makeup_available_slots_json)
            except (json.JSONDecodeError, TypeError):
                makeup_available_slots = []
        makeup_excluded_dates = []
        if self.makeup_excluded_dates_json:
            try:
                makeup_excluded_dates = json.loads(self.makeup_excluded_dates_json)
            except (json.JSONDecodeError, TypeError):
                makeup_excluded_dates = []
        return {
            'id': self.id,
            'enrollment_id': self.enrollment_id,
            'student_name': self.student_name,
            'schedule_id': self.schedule_id,
            'makeup_schedule_id': self.makeup_schedule_id,
            'makeup_available_slots': makeup_available_slots,
            'makeup_excluded_dates': makeup_excluded_dates,
            'makeup_preference_note': self.makeup_preference_note,
            'leave_date': self.leave_date.isoformat() if self.leave_date else None,
            'date': self.leave_date.isoformat() if self.leave_date else None,
            'course_name': self.schedule.course_name if self.schedule else '',
            'teacher_id': self.schedule.teacher_id if self.schedule else None,
            'teacher_name': self.schedule.teacher if self.schedule else '',
            'reason': self.reason,
            'decision_comment': self.decision_comment,
            'status': self.status,
            'approved_by': self.approved_by,
            'approver_name': self.approver.display_name if self.approver else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ChatMessage(db.Model):
    """聊天消息"""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.display_name if self.sender else None,
            'receiver_id': self.receiver_id,
            'receiver_name': self.receiver.display_name if self.receiver else None,
            'content': self.content,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
