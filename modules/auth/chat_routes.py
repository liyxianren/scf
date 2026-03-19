from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, func
from extensions import db
from modules.auth import auth_bp
from modules.auth.models import User, ChatMessage
from modules.auth.services import user_can_chat_with


@auth_bp.route('/chat')
@login_required
def chat_page():
    return render_template('auth/chat.html')


@auth_bp.route('/api/chat/conversations')
@login_required
def api_chat_conversations():
    """获取当前用户的会话列表（最近消息的对方用户）"""
    uid = current_user.id

    # 找到所有和当前用户有消息往来的用户
    partner_ids = db.session.query(
        func.distinct(
            db.case(
                (ChatMessage.sender_id == uid, ChatMessage.receiver_id),
                else_=ChatMessage.sender_id
            )
        )
    ).filter(
        or_(ChatMessage.sender_id == uid, ChatMessage.receiver_id == uid)
    ).all()

    conversations = []
    for (pid,) in partner_ids:
        partner = db.session.get(User, pid)
        if not partner or not user_can_chat_with(current_user, partner):
            continue
        # 最新一条消息
        last_msg = ChatMessage.query.filter(
            or_(
                and_(ChatMessage.sender_id == uid, ChatMessage.receiver_id == pid),
                and_(ChatMessage.sender_id == pid, ChatMessage.receiver_id == uid),
            )
        ).order_by(ChatMessage.created_at.desc()).first()
        # 未读数
        unread = ChatMessage.query.filter_by(
            sender_id=pid, receiver_id=uid, is_read=False).count()
        conversations.append({
            'user_id': pid,
            'display_name': partner.display_name,
            'role': partner.role,
            'last_message': last_msg.content[:50] if last_msg else '',
            'last_time': last_msg.created_at.isoformat() if last_msg else None,
            'unread': unread,
            'unread_count': unread,
        })

    conversations.sort(key=lambda c: c['last_time'] or '', reverse=True)
    return jsonify({'success': True, 'data': conversations})


@auth_bp.route('/api/chat/messages')
@login_required
def api_chat_messages():
    """获取与某用户的聊天记录"""
    partner_id = request.args.get('with', type=int)
    if not partner_id:
        return jsonify({'success': False, 'error': '缺少 with 参数'}), 400
    partner = db.session.get(User, partner_id)
    if not partner:
        return jsonify({'success': False, 'error': '联系人不存在'}), 404
    if not user_can_chat_with(current_user, partner):
        return jsonify({'success': False, 'error': '无权查看该会话'}), 403

    uid = current_user.id
    messages = ChatMessage.query.filter(
        or_(
            and_(ChatMessage.sender_id == uid, ChatMessage.receiver_id == partner_id),
            and_(ChatMessage.sender_id == partner_id, ChatMessage.receiver_id == uid),
        )
    ).order_by(ChatMessage.created_at.asc()).limit(200).all()

    # 标记对方发的消息为已读
    ChatMessage.query.filter_by(
        sender_id=partner_id, receiver_id=uid, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    return jsonify({'success': True, 'data': [m.to_dict() for m in messages]})


@auth_bp.route('/api/chat/send', methods=['POST'])
@login_required
def api_chat_send():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '请求数据为空'}), 400

    receiver_id = data.get('receiver_id')
    content = (data.get('content') or '').strip()

    if not receiver_id or not content:
        return jsonify({'success': False, 'error': '缺少接收人或消息内容'}), 400
    if receiver_id == current_user.id:
        return jsonify({'success': False, 'error': '不能给自己发送消息'}), 400

    receiver = db.session.get(User, receiver_id)
    if not receiver:
        return jsonify({'success': False, 'error': '接收人不存在'}), 404
    if not receiver.is_active:
        return jsonify({'success': False, 'error': '接收人已停用'}), 400
    if not user_can_chat_with(current_user, receiver):
        return jsonify({'success': False, 'error': '无权向该用户发消息'}), 403

    msg = ChatMessage(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        content=content,
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'data': msg.to_dict()}), 201


@auth_bp.route('/api/chat/unread-count')
@login_required
def api_chat_unread_count():
    unread_messages = ChatMessage.query.filter_by(
        receiver_id=current_user.id, is_read=False
    ).all()
    count = 0
    for message in unread_messages:
        sender = db.session.get(User, message.sender_id)
        if sender and user_can_chat_with(current_user, sender):
            count += 1
    return jsonify({'success': True, 'count': count})
