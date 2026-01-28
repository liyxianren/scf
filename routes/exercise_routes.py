from flask import Blueprint, request, jsonify
from models import db, Exercise, Submission
from services import ExerciseChecker

exercise_bp = Blueprint('exercises', __name__)


@exercise_bp.route('', methods=['GET'])
def get_exercises():
    """获取练习题列表（支持按语言和课程筛选）"""
    lesson_id = request.args.get('lesson_id', type=int)
    language = request.args.get('language', 'python')

    query = Exercise.query.filter_by(language=language)
    if lesson_id:
        query = query.filter_by(lesson_id=lesson_id)

    exercises = query.order_by(Exercise.lesson_id, Exercise.difficulty).all()

    return jsonify({
        'success': True,
        'data': [ex.to_dict() for ex in exercises]
    })


@exercise_bp.route('/<int:exercise_id>', methods=['GET'])
def get_exercise(exercise_id):
    """获取练习题详情"""
    exercise = Exercise.query.get_or_404(exercise_id)

    return jsonify({
        'success': True,
        'data': exercise.to_dict()
    })


@exercise_bp.route('/<int:exercise_id>/submit', methods=['POST'])
def submit_answer(exercise_id):
    """提交答案并判题"""
    exercise = Exercise.query.get_or_404(exercise_id)

    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({
            'success': False,
            'error': '请提供代码'
        }), 400

    code = data.get('code', '')
    student_name = data.get('student_name', '匿名')

    # 根据练习题的语言创建对应的判题器
    checker = ExerciseChecker(language=exercise.language)

    # 判题
    result = checker.check_submission(code, exercise.test_cases)

    # 保存提交记录
    submission = Submission(
        exercise_id=exercise_id,
        student_name=student_name,
        code=code,
        is_correct=result.get('is_correct', False),
        result=str(result)
    )
    db.session.add(submission)
    db.session.commit()

    return jsonify(result)


@exercise_bp.route('/<int:exercise_id>/solution', methods=['GET'])
def get_solution(exercise_id):
    """获取参考答案"""
    exercise = Exercise.query.get_or_404(exercise_id)

    return jsonify({
        'success': True,
        'data': {
            'solution': exercise.solution,
            'hint': exercise.hint
        }
    })
