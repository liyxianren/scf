import os
from flask import Flask, render_template
from config import Config
from models import db, Lesson, Exercise, Agent

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

# 确保数据库和数据在启动时初始化
with app.app_context():
    db.create_all()
    # 检查是否需要初始化数据
    # 检查是否需要初始化数据
    if Lesson.query.count() == 0:
        from init_db import init_lessons, init_exercises, init_agents
        init_lessons()
        init_exercises()
        init_agents()
        print("数据库已自动初始化")
    elif Agent.query.count() == 0:
         # 单独补充 Agent 数据
        from init_db import init_agents
        init_agents()

# 注册蓝图
from routes import lesson_bp, exercise_bp, code_runner_bp, agent_bp

app.register_blueprint(lesson_bp, url_prefix='/api/lessons')
app.register_blueprint(exercise_bp, url_prefix='/api/exercises')
app.register_blueprint(code_runner_bp, url_prefix='/api/code')
app.register_blueprint(agent_bp, url_prefix='/company')


# ========== 首页 ==========
@app.route('/')
def index():
    """首页 - SCF Hub"""
    return render_template('landing.html')


@app.route('/code')
def code_lobby():
    """编程学习大厅 (原 index.html)"""
    return render_template('index.html')


# ========== Python 页面路由 ==========
@app.route('/python/lessons')
def python_lessons():
    """Python 教案列表页"""
    return render_template('lessons.html', language='python')


@app.route('/python/lessons/<int:lesson_id>')
def python_lesson_detail(lesson_id):
    """Python 教案详情页"""
    return render_template('lesson_detail.html', lesson_id=lesson_id, language='python')


@app.route('/python/playground')
def python_playground():
    """Python 代码练习场"""
    return render_template('playground.html', language='python')


@app.route('/python/exercises')
def python_exercises():
    """Python 练习题列表页"""
    return render_template('exercises.html', language='python')


@app.route('/python/exercises/<int:exercise_id>')
def python_exercise_detail(exercise_id):
    """Python 练习题详情页"""
    return render_template('exercise_detail.html', exercise_id=exercise_id, language='python')


# ========== C语言 页面路由 ==========
@app.route('/c/lessons')
def c_lessons():
    """C语言 教案列表页"""
    return render_template('lessons.html', language='c')


@app.route('/c/lessons/<int:lesson_id>')
def c_lesson_detail(lesson_id):
    """C语言 教案详情页"""
    return render_template('lesson_detail.html', lesson_id=lesson_id, language='c')


@app.route('/c/playground')
def c_playground():
    """C语言 代码练习场"""
    return render_template('playground.html', language='c')


@app.route('/c/exercises')
def c_exercises():
    """C语言 练习题列表页"""
    return render_template('exercises.html', language='c')


@app.route('/c/exercises/<int:exercise_id>')
def c_exercise_detail(exercise_id):
    """C语言 练习题详情页"""
    return render_template('exercise_detail.html', exercise_id=exercise_id, language='c')


# ========== 保留旧路由（重定向到Python） ==========
@app.route('/lessons')
def lessons():
    """教案列表页（重定向到Python）"""
    return render_template('lessons.html', language='python')


@app.route('/lessons/<int:lesson_id>')
def lesson_detail(lesson_id):
    """教案详情页（重定向到Python）"""
    return render_template('lesson_detail.html', lesson_id=lesson_id, language='python')


@app.route('/playground')
def playground():
    """代码练习场（重定向到Python）"""
    return render_template('playground.html', language='python')


@app.route('/exercises')
def exercises():
    """练习题列表页（重定向到Python）"""
    return render_template('exercises.html', language='python')


@app.route('/exercises/<int:exercise_id>')
def exercise_detail(exercise_id):
    """练习题详情页（重定向到Python）"""
    return render_template('exercise_detail.html', exercise_id=exercise_id, language='python')


if __name__ == '__main__':
    # 从环境变量获取端口，Zeabur 会自动设置 PORT
    port = int(os.environ.get('PORT', 5000))
    # 生产环境关闭 debug 模式
    app.run(debug=True, host='0.0.0.0', port=port)
