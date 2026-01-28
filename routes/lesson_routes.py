import os
import markdown
from flask import Blueprint, jsonify, current_app, request
from models import Lesson

lesson_bp = Blueprint('lessons', __name__)


@lesson_bp.route('', methods=['GET'])
def get_lessons():
    """获取教案列表（支持按语言筛选）"""
    language = request.args.get('language', 'python')

    lessons = Lesson.query.filter_by(language=language).order_by(Lesson.chapter_num).all()
    return jsonify({
        'success': True,
        'data': [lesson.to_dict() for lesson in lessons]
    })


@lesson_bp.route('/<int:lesson_id>', methods=['GET'])
def get_lesson(lesson_id):
    """获取单个教案详情"""
    lesson = Lesson.query.get_or_404(lesson_id)

    # 读取Markdown文件内容
    content = ''
    content_html = ''

    if lesson.content_file:
        file_path = os.path.join(
            current_app.root_path,
            'data', 'lessons',
            lesson.content_file
        )
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 转换Markdown为HTML
            md = markdown.Markdown(extensions=[
                'fenced_code',
                'codehilite',
                'tables',
                'toc'
            ])
            content_html = md.convert(content)

    data = lesson.to_dict()
    data['content'] = content
    data['content_html'] = content_html

    return jsonify({
        'success': True,
        'data': data
    })
