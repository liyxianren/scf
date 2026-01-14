from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Lesson(db.Model):
    """教案模型"""
    __tablename__ = 'lessons'

    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(20), default='python')  # 编程语言
    chapter_num = db.Column(db.Integer, nullable=False)  # 章节号
    title = db.Column(db.String(200), nullable=False)  # 标题
    description = db.Column(db.Text)  # 简介
    content_file = db.Column(db.String(255))  # Markdown文件路径
    order_index = db.Column(db.Integer, default=0)  # 排序
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联练习题
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
    language = db.Column(db.String(20), default='python')  # 编程语言
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)  # 关联章节
    title = db.Column(db.String(200), nullable=False)  # 题目标题
    description = db.Column(db.Text, nullable=False)  # 题目描述（Markdown）
    difficulty = db.Column(db.Integer, default=1)  # 难度：1简单 2中等 3困难
    initial_code = db.Column(db.Text)  # 初始代码模板
    test_cases = db.Column(db.Text, nullable=False)  # 测试用例（JSON）
    hint = db.Column(db.Text)  # 提示
    solution = db.Column(db.Text)  # 参考答案
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
    student_name = db.Column(db.String(100))  # 学生姓名
    code = db.Column(db.Text, nullable=False)  # 提交的代码
    is_correct = db.Column(db.Boolean, default=False)  # 是否正确
    result = db.Column(db.Text)  # 执行结果
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


class Agent(db.Model):
    """公司 Agent/工作流 模型"""
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Agent 名称
    description = db.Column(db.Text)  # 描述
    icon = db.Column(db.String(50), default='robot')  # 图标名称 (用于前端显示)
    status = db.Column(db.String(20), default='active')  # 状态: active, testing, developing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'status': self.status
        }


class CreativeProject(db.Model):
    """创意项目存档"""
    __tablename__ = 'creative_projects'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # 项目名称
    slogan = db.Column(db.String(200))  # 一句话描述
    full_content = db.Column(db.Text)  # 完整 Markdown 报告
    tags = db.Column(db.String(200))  # 标签 (JSON string or comma separated)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'slogan': self.slogan,
            'full_content': self.full_content,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
