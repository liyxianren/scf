from datetime import datetime
from extensions import db


class Lesson(db.Model):
    """教案模型"""
    __tablename__ = 'lessons'

    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(20), default='python')
    chapter_num = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    content_file = db.Column(db.String(255))
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    exercises = db.relationship('Exercise', backref='lesson', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'language': self.language,
            'chapter_num': self.chapter_num,
            'title': self.title,
            'description': self.description,
            'content_file': self.content_file,
            'order_index': self.order_index
        }


class Exercise(db.Model):
    """练习题模型"""
    __tablename__ = 'exercises'

    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(20), default='python')
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.Integer, default=1)
    initial_code = db.Column(db.Text)
    test_cases = db.Column(db.Text, nullable=False)
    hint = db.Column(db.Text)
    solution = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_solution=False):
        data = {
            'id': self.id,
            'language': self.language,
            'lesson_id': self.lesson_id,
            'title': self.title,
            'description': self.description,
            'difficulty': self.difficulty,
            'initial_code': self.initial_code,
            'hint': self.hint
        }
        if include_solution:
            data['solution'] = self.solution
        return data


class Submission(db.Model):
    """学生提交记录"""
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    student_name = db.Column(db.String(100))
    code = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    result = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    exercise = db.relationship('Exercise', backref='submissions')

    def to_dict(self):
        return {
            'id': self.id,
            'exercise_id': self.exercise_id,
            'student_name': self.student_name,
            'is_correct': self.is_correct,
            'submitted_at': self.submitted_at.isoformat()
        }
