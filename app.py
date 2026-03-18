import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from config import Config
from extensions import db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)

    # 注册蓝图
    from modules.education.routes import lesson_bp, exercise_bp, code_runner_bp
    from modules.agents import agent_bp
    from modules.handbook import handbook_bp
    from modules.oa import oa_bp

    app.register_blueprint(lesson_bp, url_prefix='/api/lessons')
    app.register_blueprint(exercise_bp, url_prefix='/api/exercises')
    app.register_blueprint(code_runner_bp, url_prefix='/api/code')
    app.register_blueprint(agent_bp, url_prefix='/company')
    app.register_blueprint(handbook_bp, url_prefix='/company/handbook')
    app.register_blueprint(oa_bp, url_prefix='/oa')

    # 注册页面路由
    _register_page_routes(app)

    # 初始化数据库
    with app.app_context():
        db.create_all()
        _init_data()
        _cleanup_expired()

    return app


def _init_data():
    """检查并初始化种子数据"""
    from modules.education.models import Lesson
    from modules.agents.models import Agent

    if Lesson.query.count() == 0:
        from init_db import init_lessons, init_exercises, init_agents
        init_lessons()
        init_exercises()
        init_agents()
        print("数据库已自动初始化")
    elif Agent.query.count() == 0:
        from init_db import init_agents
        init_agents()


def _cleanup_expired():
    """清理过期且未收藏的计划书和工程手册"""
    from modules.agents.models import ProjectPlan
    from modules.handbook.models import EngineeringHandbook

    expired_plans = ProjectPlan.query.filter(
        ProjectPlan.expires_at < datetime.utcnow(),
        ProjectPlan.is_favorited == False
    ).all()
    if expired_plans:
        for plan in expired_plans:
            db.session.delete(plan)
        db.session.commit()
        print(f"已清理 {len(expired_plans)} 个过期计划书")

    expired_handbooks = EngineeringHandbook.query.filter(
        EngineeringHandbook.expires_at < datetime.utcnow(),
        EngineeringHandbook.is_favorited == False
    ).all()
    if expired_handbooks:
        for handbook in expired_handbooks:
            db.session.delete(handbook)
        db.session.commit()
        print(f"已清理 {len(expired_handbooks)} 个过期工程手册")


def _register_page_routes(app):
    """所有页面路由（render_template）"""

    # ========== 首页 ==========
    @app.route('/')
    def index():
        """首页 - SCF Hub"""
        return render_template('landing.html')

    @app.route('/code')
    def code_lobby():
        """编程学习大厅"""
        return render_template('education/index.html')

    # ========== Python 页面路由 ==========
    @app.route('/python/lessons')
    def python_lessons():
        return render_template('education/lessons.html', language='python')

    @app.route('/python/lessons/<int:lesson_id>')
    def python_lesson_detail(lesson_id):
        return render_template('education/lesson_detail.html', lesson_id=lesson_id, language='python')

    @app.route('/python/playground')
    def python_playground():
        return render_template('education/playground.html', language='python')

    @app.route('/python/exercises')
    def python_exercises():
        return render_template('education/exercises.html', language='python')

    @app.route('/python/exercises/<int:exercise_id>')
    def python_exercise_detail(exercise_id):
        return render_template('education/exercise_detail.html', exercise_id=exercise_id, language='python')

    # ========== C语言 页面路由 ==========
    @app.route('/c/lessons')
    def c_lessons():
        return render_template('education/lessons.html', language='c')

    @app.route('/c/lessons/<int:lesson_id>')
    def c_lesson_detail(lesson_id):
        return render_template('education/lesson_detail.html', lesson_id=lesson_id, language='c')

    @app.route('/c/playground')
    def c_playground():
        return render_template('education/playground.html', language='c')

    @app.route('/c/exercises')
    def c_exercises():
        return render_template('education/exercises.html', language='c')

    @app.route('/c/exercises/<int:exercise_id>')
    def c_exercise_detail(exercise_id):
        return render_template('education/exercise_detail.html', exercise_id=exercise_id, language='c')

    # ========== Vibe Coding 页面路由 ==========
    @app.route('/vibe/lessons')
    def vibe_lessons():
        return render_template('education/lessons.html', language='vibe')

    @app.route('/vibe/lessons/<int:lesson_id>')
    def vibe_lesson_detail(lesson_id):
        return render_template('education/lesson_detail.html', lesson_id=lesson_id, language='vibe')

    @app.route('/vibe/playground')
    def vibe_playground():
        return render_template('education/playground.html', language='vibe')

    @app.route('/vibe/exercises')
    def vibe_exercises():
        return render_template('education/exercises.html', language='vibe')

    @app.route('/vibe/exercises/<int:exercise_id>')
    def vibe_exercise_detail(exercise_id):
        return render_template('education/exercise_detail.html', exercise_id=exercise_id, language='vibe')

    # ========== Vibe API 演示 ==========
    @app.route('/api/vibe/demo', methods=['GET', 'POST'])
    def vibe_demo():
        payload = request.get_json(silent=True) or {}
        return jsonify({
            'success': True,
            'message': '这是一个演示API，用于练习请求与响应。',
            'method': request.method,
            'received': payload,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    # ========== 保留旧路由（重定向到Python） ==========
    @app.route('/lessons')
    def lessons():
        return render_template('education/lessons.html', language='python')

    @app.route('/lessons/<int:lesson_id>')
    def lesson_detail(lesson_id):
        return render_template('education/lesson_detail.html', lesson_id=lesson_id, language='python')

    @app.route('/playground')
    def playground():
        return render_template('education/playground.html', language='python')

    @app.route('/exercises')
    def exercises():
        return render_template('education/exercises.html', language='python')

    @app.route('/exercises/<int:exercise_id>')
    def exercise_detail(exercise_id):
        return render_template('education/exercise_detail.html', exercise_id=exercise_id, language='python')


# 模块级变量，供 gunicorn / Procfile / Zeabur 引用
app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
