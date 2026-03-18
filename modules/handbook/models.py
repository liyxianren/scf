from datetime import datetime
from extensions import db


class EngineeringHandbook(db.Model):
    """工程手册模型 - 支持多体系版本与后台生成"""
    __tablename__ = 'engineering_handbooks'

    id = db.Column(db.Integer, primary_key=True)
    project_name_cn = db.Column(db.String(200), nullable=False)  # 项目中文名
    project_name_en = db.Column(db.String(200))  # 项目英文名
    author_name = db.Column(db.String(100))  # 学生姓名
    version = db.Column(db.String(20), default='v1.0.0')  # 版本号
    completion_date = db.Column(db.Date)  # 完成日期

    # 目标体系 (JSON数组: ["US", "UK", "HK-SG"])
    target_systems = db.Column(db.Text)

    # 生成状态
    status = db.Column(db.String(20), default='pending')  # pending/generating/completed/failed
    content_versions = db.Column(db.Text)  # JSON: {"US": "...", "UK": "...", "HK-SG": "..."}

    # 输入材料
    project_description = db.Column(db.Text)  # 项目说明文档内容
    project_description_file = db.Column(db.String(500))  # 上传文件路径
    source_code_url = db.Column(db.String(500))  # GitHub URL
    source_code_file = db.Column(db.String(500))  # 代码ZIP路径
    process_materials = db.Column(db.Text)  # JSON数组: 素材文件路径列表

    # 管理字段
    is_favorited = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)  # 30天过期(未收藏)

    def to_dict(self, include_content=True):
        data = {
            'id': self.id,
            'project_name_cn': self.project_name_cn,
            'project_name_en': self.project_name_en,
            'author_name': self.author_name,
            'version': self.version,
            'completion_date': self.completion_date.isoformat() if self.completion_date else None,
            'target_systems': self.target_systems,
            'status': self.status,
            'source_code_url': self.source_code_url,
            'is_favorited': self.is_favorited,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
        if include_content:
            data['content_versions'] = self.content_versions
        return data
