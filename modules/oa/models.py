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
    course_name = db.Column(db.String(200), nullable=False)
    students = db.Column(db.Text)
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    color_tag = db.Column(db.String(20), default='blue')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    todos = db.relationship('OATodo', backref='schedule', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'day_of_week': self.day_of_week,
            'time_start': self.time_start,
            'time_end': self.time_end,
            'teacher': self.teacher,
            'course_name': self.course_name,
            'students': self.students,
            'location': self.location,
            'notes': self.notes,
            'color_tag': self.color_tag,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class OATodo(db.Model):
    """OA待办事项模型"""
    __tablename__ = 'oa_todos'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    responsible_person = db.Column(db.String(255))
    is_completed = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date)
    priority = db.Column(db.Integer, default=2)  # 1=高 2=中 3=低
    notes = db.Column(db.Text)
    schedule_id = db.Column(db.Integer, db.ForeignKey('course_schedules.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
