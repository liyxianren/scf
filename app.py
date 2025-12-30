import os
from flask import Flask, render_template
from config import Config
from models import db, Lesson, Exercise

app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)

# 确保数据库和数据在启动时初始化
with app.app_context():
    db.create_all()
    # 检查是否需要初始化数据
    if Lesson.query.count() == 0:
        from init_db import init_lessons, init_exercises
        init_lessons()
        init_exercises()
        print("数据库已自动初始化")

# 注册蓝图
from routes import lesson_bp, exercise_bp, code_runner_bp

app.register_blueprint(lesson_bp, url_prefix='/api/lessons')
app.register_blueprint(exercise_bp, url_prefix='/api/exercises')
app.register_blueprint(code_runner_bp, url_prefix='/api/code')


# 页面路由
@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/lessons')
def lessons():
    """教案列表页"""
    return render_template('lessons.html')


@app.route('/lessons/<int:lesson_id>')
def lesson_detail(lesson_id):
    """教案详情页"""
    return render_template('lesson_detail.html', lesson_id=lesson_id)


@app.route('/playground')
def playground():
    """代码练习场"""
    return render_template('playground.html')


@app.route('/exercises')
def exercises():
    """练习题列表页"""
    return render_template('exercises.html')


@app.route('/exercises/<int:exercise_id>')
def exercise_detail(exercise_id):
    """练习题详情页"""
    return render_template('exercise_detail.html', exercise_id=exercise_id)


if __name__ == '__main__':
    # 从环境变量获取端口，Zeabur 会自动设置 PORT
    port = int(os.environ.get('PORT', 5000))
    # 生产环境关闭 debug 模式
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
