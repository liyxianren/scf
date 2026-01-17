from flask import Blueprint, request, jsonify
from services import CodeExecutor, CExecutor

code_runner_bp = Blueprint('code_runner', __name__)

# 创建代码执行器实例
python_executor = CodeExecutor(timeout=5)
c_executor = CExecutor(compile_timeout=10, run_timeout=5)


@code_runner_bp.route('/run', methods=['POST'])
def run_code():
    """执行代码（支持多语言）"""
    data = request.get_json()

    if not data or 'code' not in data:
        return jsonify({
            'success': False,
            'error': '请提供代码'
        }), 400

    code = data.get('code', '')
    stdin_input = data.get('input', '')
    language = data.get('language', 'python')

    # 根据语言选择执行器
    if language == 'c':
        executor = c_executor
    else:
        executor = python_executor

    # 执行代码
    result = executor.execute(code, stdin_input)

    return jsonify(result)
