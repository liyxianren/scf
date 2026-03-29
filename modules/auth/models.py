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
    teacher_work_mode = db.Column(db.String(20), nullable=False, default='part_time')
    default_working_template_json = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    teacher_slots = db.relationship('TeacherAvailability', backref='user', lazy=True,
                                    cascade='all, delete-orphan')
    student_profile = db.relationship('StudentProfile', backref='user', uselist=False, lazy=True)
    external_identities = db.relationship(
        'ExternalIdentity',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan',
    )
    reminder_events = db.relationship(
        'ReminderEvent',
        back_populates='target_user',
        lazy=True,
        cascade='all, delete-orphan',
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        default_working_template = []
        if self.default_working_template_json:
            try:
                default_working_template = json.loads(self.default_working_template_json)
            except (json.JSONDecodeError, TypeError):
                default_working_template = []
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'role': self.role,
            'phone': self.phone,
            'teacher_work_mode': self.teacher_work_mode or 'part_time',
            'default_working_template': (
                default_working_template if isinstance(default_working_template, list) else []
            ),
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
    delivery_urgency = db.Column(db.String(20), default='normal')
    target_finish_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default='pending_info')
    # pending_info → pending_schedule → pending_student_confirm → confirmed → active → completed
    intake_token = db.Column(db.String(64), unique=True)
    token_expires_at = db.Column(db.DateTime)
    student_profile_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=True)
    delivery_preference = db.Column(db.String(20), default='unknown')
    proposed_slots = db.Column(db.Text)   # JSON: 自动匹配结果
    confirmed_slot = db.Column(db.Text)   # JSON: 教务确认的时段
    availability_intake = db.Column(db.Text)  # JSON: 学生自然语言 / 截图解析后的可上课输入
    candidate_slot_pool = db.Column(db.Text)  # JSON: AI 生成的可选时间池
    recommended_bundle = db.Column(db.Text)   # JSON: AI 推荐的完整方案
    risk_assessment = db.Column(db.Text)      # JSON: 排课风险评估
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher = db.relationship('User', foreign_keys=[teacher_id])
    student_profile = db.relationship('StudentProfile', backref='enrollment', foreign_keys=[student_profile_id])
    schedules = db.relationship('CourseSchedule', back_populates='enrollment', lazy=True)
    feedback_share_links = db.relationship(
        'FeedbackShareLink',
        back_populates='enrollment',
        lazy=True,
        cascade='all, delete-orphan',
    )

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
        availability_intake = None
        if self.availability_intake:
            try:
                availability_intake = json.loads(self.availability_intake)
            except (json.JSONDecodeError, TypeError):
                pass
        candidate_slot_pool = []
        if self.candidate_slot_pool:
            try:
                candidate_slot_pool = json.loads(self.candidate_slot_pool)
            except (json.JSONDecodeError, TypeError):
                pass
        recommended_bundle = None
        if self.recommended_bundle:
            try:
                recommended_bundle = json.loads(self.recommended_bundle)
            except (json.JSONDecodeError, TypeError):
                pass
        risk_assessment = None
        if self.risk_assessment:
            try:
                risk_assessment = json.loads(self.risk_assessment)
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
            'delivery_urgency': self.delivery_urgency,
            'target_finish_date': self.target_finish_date.isoformat() if self.target_finish_date else None,
            'status': self.status,
            'intake_token': self.intake_token,
            'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
            'student_profile_id': self.student_profile_id,
            'delivery_preference': self.delivery_preference,
            'student_profile': self.student_profile.to_dict() if self.student_profile else None,
            'proposed_slots': proposed,
            'confirmed_slot': confirmed,
            'availability_intake': availability_intake,
            'candidate_slot_pool': candidate_slot_pool,
            'recommended_bundle': recommended_bundle,
            'risk_assessment': risk_assessment,
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


class ExternalIdentity(db.Model):
    __tablename__ = 'external_identities'
    __table_args__ = (
        db.UniqueConstraint('provider', 'external_user_id', name='uq_external_identity_provider_user'),
    )

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    external_user_id = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'provider': self.provider,
            'external_user_id': self.external_user_id,
            'user_id': self.user_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class IntegrationActionLog(db.Model):
    __tablename__ = 'integration_action_logs'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(120), unique=True, nullable=False)
    client_name = db.Column(db.String(50), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    payload_json = db.Column(db.Text)
    result_json = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='processing')
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actor = db.relationship('User', foreign_keys=[actor_user_id])

    def get_payload_data(self):
        if not self.payload_json:
            return {}
        try:
            data = json.loads(self.payload_json)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_payload_data(self, value):
        if value is None:
            self.payload_json = None
            return
        self.payload_json = json.dumps(value, ensure_ascii=False)

    def get_result_data(self):
        if not self.result_json:
            return {}
        try:
            data = json.loads(self.result_json)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_result_data(self, value):
        if value is None:
            self.result_json = None
            return
        self.result_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'client_name': self.client_name,
            'provider': self.provider,
            'actor_user_id': self.actor_user_id,
            'action': self.action,
            'payload': self.get_payload_data(),
            'result': self.get_result_data(),
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ReminderEvent(db.Model):
    __tablename__ = 'reminder_events'

    id = db.Column(db.Integer, primary_key=True)
    event_key = db.Column(db.String(255), unique=True, nullable=False)
    event_type = db.Column(db.String(120), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_role = db.Column(db.String(20), nullable=False)
    scope_type = db.Column(db.String(50), nullable=False)
    scope_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text)
    action_key = db.Column(db.String(120))
    payload_json = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='pending')
    due_at = db.Column(db.DateTime)
    source_request_id = db.Column(db.String(120))
    source_action = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    target_user = db.relationship('User', foreign_keys=[target_user_id], back_populates='reminder_events')
    deliveries = db.relationship(
        'ReminderDelivery',
        back_populates='event',
        lazy=True,
        cascade='all, delete-orphan',
    )

    def get_payload_data(self):
        if not self.payload_json:
            return {}
        try:
            data = json.loads(self.payload_json)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_payload_data(self, value):
        if value is None:
            self.payload_json = None
            return
        self.payload_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'event_key': self.event_key,
            'event_type': self.event_type,
            'target_user_id': self.target_user_id,
            'target_role': self.target_role,
            'scope_type': self.scope_type,
            'scope_id': self.scope_id,
            'title': self.title,
            'summary': self.summary,
            'action_key': self.action_key,
            'payload': self.get_payload_data(),
            'status': self.status,
            'due_at': self.due_at.isoformat() if self.due_at else None,
            'source_request_id': self.source_request_id,
            'source_action': self.source_action,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ReminderDelivery(db.Model):
    __tablename__ = 'reminder_deliveries'
    __table_args__ = (
        db.UniqueConstraint('event_id', 'channel', 'receiver_external_id', name='uq_reminder_delivery_event_channel_receiver'),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('reminder_events.id'), nullable=False)
    channel = db.Column(db.String(50), nullable=False, default='openclaw_feed')
    receiver_external_id = db.Column(db.String(255), nullable=False)
    delivery_status = db.Column(db.String(20), nullable=False, default='pending')
    fetched_at = db.Column(db.DateTime)
    acked_at = db.Column(db.DateTime)
    provider_message_id = db.Column(db.String(255))
    provider_response_json = db.Column(db.Text)
    last_attempt_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = db.relationship('ReminderEvent', foreign_keys=[event_id], back_populates='deliveries')

    def get_provider_response_data(self):
        if not self.provider_response_json:
            return {}
        try:
            data = json.loads(self.provider_response_json)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_provider_response_data(self, value):
        if value is None:
            self.provider_response_json = None
            return
        self.provider_response_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'channel': self.channel,
            'receiver_external_id': self.receiver_external_id,
            'delivery_status': self.delivery_status,
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None,
            'acked_at': self.acked_at.isoformat() if self.acked_at else None,
            'provider_message_id': self.provider_message_id,
            'provider_response': self.get_provider_response_data(),
            'last_attempt_at': self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class FeedbackShareLink(db.Model):
    __tablename__ = 'feedback_share_links'

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=False)
    token = db.Column(db.String(120), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_accessed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    enrollment = db.relationship('Enrollment', foreign_keys=[enrollment_id], back_populates='feedback_share_links')
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'enrollment_id': self.enrollment_id,
            'token': self.token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'created_by': self.created_by,
            'last_accessed_at': self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
