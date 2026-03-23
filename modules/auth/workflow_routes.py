from flask import jsonify, request
from flask_login import current_user, login_required

from modules.auth import auth_bp
from modules.auth.decorators import role_required
from modules.auth.workflow_services import (
    admin_return_workflow_to_teacher,
    admin_send_workflow_to_student,
    build_workflow_todo_payload,
    get_workflow_todo,
    list_workflow_todos_for_user,
    preview_teacher_workflow_proposal,
    student_confirm_workflow_todo,
    student_reject_workflow_todo,
    submit_teacher_workflow_proposal,
    user_can_access_workflow_todo,
)


@auth_bp.route('/api/workflow-todos', methods=['GET'])
@login_required
def api_list_workflow_todos():
    status = request.args.get('status', 'open')
    todo_type = request.args.get('todo_type')
    enrollment_id = request.args.get('enrollment_id', type=int)
    todos = list_workflow_todos_for_user(
        current_user,
        status=status,
        todo_type=todo_type,
        enrollment_id=enrollment_id,
    )
    return jsonify({
        'success': True,
        'data': [build_workflow_todo_payload(todo, current_user) for todo in todos],
        'total': len(todos),
    })


@auth_bp.route('/api/workflow-todos/<int:todo_id>', methods=['GET'])
@login_required
def api_get_workflow_todo(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404
    if not user_can_access_workflow_todo(current_user, todo):
        return jsonify({'success': False, 'error': '无权查看该工作流待办'}), 403
    return jsonify({'success': True, 'data': build_workflow_todo_payload(todo, current_user)})


@auth_bp.route('/api/workflow-todos/<int:todo_id>/teacher-proposal', methods=['POST'])
@role_required('teacher', 'admin')
def api_teacher_workflow_proposal(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404

    data = request.get_json(silent=True) or {}
    result = submit_teacher_workflow_proposal(
        todo,
        current_user,
        data.get('session_dates') or [],
        note=data.get('note', ''),
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@auth_bp.route('/api/workflow-todos/<int:todo_id>/proposal-preview', methods=['POST'])
@role_required('teacher', 'admin')
def api_teacher_workflow_proposal_preview(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404

    data = request.get_json(silent=True) or {}
    result = preview_teacher_workflow_proposal(
        todo,
        current_user,
        data.get('session_dates') or [],
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@auth_bp.route('/api/workflow-todos/<int:todo_id>/admin-send-to-student', methods=['POST'])
@role_required('admin')
def api_admin_send_workflow_to_student(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404

    data = request.get_json(silent=True) or {}
    session_dates = data.get('session_dates')
    result = admin_send_workflow_to_student(
        todo,
        current_user,
        session_dates=session_dates,
        note=data.get('note', ''),
        force_save=bool(data.get('force_save')),
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@auth_bp.route('/api/workflow-todos/<int:todo_id>/admin-return-to-teacher', methods=['POST'])
@role_required('admin')
def api_admin_return_workflow_to_teacher(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404

    data = request.get_json(silent=True) or {}
    result = admin_return_workflow_to_teacher(
        todo,
        current_user,
        data.get('message', ''),
    )
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@auth_bp.route('/api/workflow-todos/<int:todo_id>/student-confirm', methods=['POST'])
@role_required('student')
def api_student_confirm_workflow(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404

    result = student_confirm_workflow_todo(todo, current_user)
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code


@auth_bp.route('/api/workflow-todos/<int:todo_id>/student-reject', methods=['POST'])
@role_required('student')
def api_student_reject_workflow(todo_id):
    todo = get_workflow_todo(todo_id)
    if not todo:
        return jsonify({'success': False, 'error': '工作流待办不存在'}), 404

    data = request.get_json(silent=True) or {}
    result = student_reject_workflow_todo(todo, current_user, data.get('message', ''))
    status_code = result.pop('status_code', 200)
    return jsonify(result), status_code
