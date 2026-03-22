import json
from datetime import datetime
from extensions import db


class CourseSchedule(db.Model):
    """课程排课模型 - 对应2026年总课表"""
    __tablename__ = 'course_schedules'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=周一 ... 6=周日
    time_start = db.Column(db.String(10), nullable=False)
    time_end = db.Column(db.String(10), nullable=False)
    teacher = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    course_name = db.Column(db.String(200), nullable=False)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=True)
    student_profile_id_snapshot = db.Column(db.Integer, db.ForeignKey('student_profiles.id'), nullable=True)
    students = db.Column(db.Text)
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    color_tag = db.Column(db.String(20), default='blue')
    delivery_mode = db.Column(db.String(20), default='unknown')
    import_run_id = db.Column(db.Integer, db.ForeignKey('schedule_import_runs.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    todos = db.relationship('OATodo', backref='schedule', lazy=True)
    feedback = db.relationship(
        'CourseFeedback',
        backref='schedule',
        uselist=False,
        lazy=True,
        cascade='all, delete-orphan',
    )
    leave_requests = db.relationship(
        'LeaveRequest',
        foreign_keys='LeaveRequest.schedule_id',
        backref='schedule_record',
        lazy=True,
        cascade='all, delete-orphan',
    )
    enrollment = db.relationship('Enrollment', foreign_keys=[enrollment_id], lazy=True, back_populates='schedules')

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'day_of_week': self.day_of_week,
            'time_start': self.time_start,
            'time_end': self.time_end,
            'teacher': self.teacher,
            'teacher_id': self.teacher_id,
            'course_name': self.course_name,
            'enrollment_id': self.enrollment_id,
            'student_profile_id_snapshot': self.student_profile_id_snapshot,
            'students': self.students,
            'location': self.location,
            'notes': self.notes,
            'color_tag': self.color_tag,
            'delivery_mode': self.delivery_mode,
            'import_run_id': self.import_run_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ScheduleImportRun(db.Model):
    """课表导入记录，用于保存原始 Excel 与导入摘要。"""
    __tablename__ = 'schedule_import_runs'

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(30), default='pending', nullable=False)
    summary_json = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    schedules = db.relationship('CourseSchedule', backref='import_run', lazy=True)

    def get_summary_data(self):
        if not self.summary_json:
            return {}
        try:
            data = json.loads(self.summary_json)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_summary_data(self, value):
        if value is None:
            self.summary_json = None
            return
        self.summary_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'stored_path': self.stored_path,
            'uploaded_by': self.uploaded_by,
            'uploader_name': self.uploader.display_name if self.uploader else None,
            'status': self.status,
            'summary': self.get_summary_data(),
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class CourseFeedback(db.Model):
    """课后反馈，一节课一条。"""
    __tablename__ = 'course_feedback'
    __table_args__ = (
        db.UniqueConstraint('schedule_id', 'teacher_id', name='uq_course_feedback_schedule_teacher'),
    )

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('course_schedules.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    summary = db.Column(db.Text)
    homework = db.Column(db.Text)
    next_focus = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft / submitted
    submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher = db.relationship('User', foreign_keys=[teacher_id])

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.display_name if self.teacher else None,
            'summary': self.summary,
            'homework': self.homework,
            'next_focus': self.next_focus,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class OATodo(db.Model):
    """OA待办事项模型"""
    __tablename__ = 'oa_todos'

    TODO_TYPE_GENERIC = 'generic'
    TODO_TYPE_EXCEL_IMPORT = 'excel_import'
    TODO_TYPE_ENROLLMENT_REPLAN = 'enrollment_replan'
    TODO_TYPE_LEAVE_MAKEUP = 'leave_makeup'
    TODO_TYPE_SCHEDULE_FEEDBACK = 'schedule_feedback'

    WORKFLOW_STATUS_WAITING_TEACHER_PROPOSAL = 'waiting_teacher_proposal'
    WORKFLOW_STATUS_WAITING_ADMIN_REVIEW = 'waiting_admin_review'
    WORKFLOW_STATUS_WAITING_STUDENT_CONFIRM = 'waiting_student_confirm'
    WORKFLOW_STATUS_COMPLETED = 'completed'
    WORKFLOW_STATUS_CANCELLED = 'cancelled'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    responsible_person = db.Column(db.String(255))
    is_completed = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date)
    priority = db.Column(db.Integer, default=2)  # 1=高 2=中 3=低
    notes = db.Column(db.Text)
    schedule_id = db.Column(db.Integer, db.ForeignKey('course_schedules.id'), nullable=True)
    todo_type = db.Column(db.String(50), default=TODO_TYPE_GENERIC, nullable=False)
    workflow_status = db.Column(db.String(50))
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=True)
    leave_request_id = db.Column(db.Integer, db.ForeignKey('leave_requests.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_at = db.Column(db.DateTime)
    payload = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    enrollment = db.relationship('Enrollment', foreign_keys=[enrollment_id], lazy=True)
    leave_request = db.relationship('LeaveRequest', foreign_keys=[leave_request_id], lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], lazy=True)

    @classmethod
    def workflow_types(cls):
        return {
            cls.TODO_TYPE_ENROLLMENT_REPLAN,
            cls.TODO_TYPE_LEAVE_MAKEUP,
            cls.TODO_TYPE_SCHEDULE_FEEDBACK,
        }

    @property
    def is_workflow(self):
        return (self.todo_type or self.TODO_TYPE_GENERIC) in self.workflow_types()

    @property
    def is_open_workflow(self):
        return self.is_workflow and not self.is_completed and self.workflow_status not in {
            self.WORKFLOW_STATUS_COMPLETED,
            self.WORKFLOW_STATUS_CANCELLED,
        }

    def get_payload_data(self):
        if not self.payload:
            return {}
        try:
            data = json.loads(self.payload)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def set_payload_data(self, value):
        if value is None:
            self.payload = None
            return
        self.payload = json.dumps(value, ensure_ascii=False)

    @staticmethod
    def parse_responsible_people(value):
        if not value:
            return []
        if isinstance(value, (list, tuple, set)):
            raw_items = value
        else:
            normalized = str(value).replace('，', ',').replace('、', ',').replace(';', ',').replace('；', ',')
            raw_items = normalized.split(',')

        people = []
        seen = set()
        for item in raw_items:
            name = str(item).strip()
            if not name:
                continue
            dedup_key = name.casefold()
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            people.append(name)
        return people

    @classmethod
    def normalize_responsible_people(cls, value):
        return ', '.join(cls.parse_responsible_people(value))

    def to_dict(self):
        responsible_people = self.parse_responsible_people(self.responsible_person)
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'responsible_person': self.responsible_person,
            'responsible_people': responsible_people,
            'is_completed': self.is_completed,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'priority': self.priority,
            'notes': self.notes,
            'schedule_id': self.schedule_id,
            'todo_type': self.todo_type or self.TODO_TYPE_GENERIC,
            'workflow_status': self.workflow_status,
            'enrollment_id': self.enrollment_id,
            'leave_request_id': self.leave_request_id,
            'created_by': self.created_by,
            'creator_name': self.creator.display_name if self.creator else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'payload': self.get_payload_data(),
            'is_workflow': self.is_workflow,
            'is_open_workflow': self.is_open_workflow,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class PainPoint(db.Model):
    """痛点提交模型 — 员工通过 AI 对话描述工作痛点"""
    __tablename__ = 'pain_points'

    id = db.Column(db.Integer, primary_key=True)
    submitter = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    problem = db.Column(db.Text)
    ai_summary = db.Column(db.Text)
    conversation = db.Column(db.Text)  # JSON string of chat history
    status = db.Column(db.String(20), default='new')  # new/reviewed/in_progress/resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'submitter': self.submitter,
            'title': self.title,
            'problem': self.problem,
            'ai_summary': self.ai_summary,
            'conversation': self.conversation,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
