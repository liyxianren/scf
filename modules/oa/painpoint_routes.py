"""API endpoints for the pain point submission system."""
import json
import re

from flask import request, jsonify, Response, stream_with_context, current_app

from extensions import db
from modules.oa import oa_bp
from modules.oa.models import PainPoint
from modules.oa.painpoint_prompts import PAINPOINT_SYSTEM_PROMPT, TITLE_GENERATION_PROMPT
from core.ai.minimax import MiniMaxClient


@oa_bp.route('/api/painpoint-chat', methods=['POST'])
def painpoint_chat():
    """AI conversation endpoint for pain point analysis. Streams plain text via NDJSON.

    Request body:
        {"message": "...", "history": [...]}

    Response: NDJSON stream with events:
        {"type": "content", "data": "..."}
        {"type": "done", "data": ""}
        {"type": "error", "data": "..."}
    """
    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    history = data.get('history') or []

    if not user_message:
        return jsonify({'error': '请输入消息'}), 400

    # Build full conversation for the AI
    messages = [{"role": "system", "content": PAINPOINT_SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            client = MiniMaxClient()
            params = {
                "model": client.model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.7,
                "stream": True,
            }
            response = client.client.chat.completions.create(**params)
            in_think = False
            buf = ''
            for chunk in response:
                if not chunk or not getattr(chunk, "choices", None):
                    continue
                delta = getattr(chunk.choices[0], "delta", None)
                if not delta:
                    continue
                content = getattr(delta, "content", None)
                if not content:
                    continue
                buf += content
                # Skip content inside <think>...</think>
                while True:
                    if in_think:
                        end = buf.find('</think>')
                        if end == -1:
                            buf = ''  # still inside think, discard
                            break
                        buf = buf[end + 8:]  # skip past </think>
                        in_think = False
                    else:
                        start = buf.find('<think>')
                        if start == -1:
                            # No think tag — flush buffer (keep last 7 chars in case of partial tag)
                            if len(buf) > 7:
                                out = buf[:-7]
                                buf = buf[-7:]
                                yield json.dumps({"type": "content", "data": out}, ensure_ascii=False) + "\n"
                            break
                        else:
                            # Flush content before <think>
                            if start > 0:
                                yield json.dumps({"type": "content", "data": buf[:start]}, ensure_ascii=False) + "\n"
                            buf = buf[start + 7:]  # skip past <think>
                            in_think = True
            # Flush remaining buffer
            if buf and not in_think:
                yield json.dumps({"type": "content", "data": buf}, ensure_ascii=False) + "\n"
            yield json.dumps({"type": "done", "data": ""}, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "data": str(e)}, ensure_ascii=False) + "\n"

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Content-Type': 'application/x-ndjson',
    }
    return Response(stream_with_context(generate()), headers=headers)


@oa_bp.route('/api/painpoints', methods=['GET'])
def list_painpoints():
    """List all pain point submissions."""
    status = request.args.get('status')
    query = PainPoint.query

    if status and status != 'all':
        query = query.filter(PainPoint.status == status)

    items = query.order_by(PainPoint.created_at.desc()).all()
    return jsonify([p.to_dict() for p in items])


@oa_bp.route('/api/painpoints', methods=['POST'])
def create_painpoint():
    """Save a new pain point submission."""
    data = request.get_json(silent=True) or {}
    submitter = (data.get('submitter') or '').strip()
    title = (data.get('title') or '').strip()
    problem = (data.get('problem') or '').strip()
    ai_summary = (data.get('ai_summary') or '').strip()
    conversation = data.get('conversation') or '[]'

    if not submitter:
        return jsonify({'success': False, 'error': '请选择提交人'}), 400
    if not title:
        return jsonify({'success': False, 'error': '缺少标题'}), 400

    pp = PainPoint(
        submitter=submitter,
        title=title,
        problem=problem,
        ai_summary=ai_summary,
        conversation=json.dumps(conversation, ensure_ascii=False) if isinstance(conversation, list) else conversation,
    )
    db.session.add(pp)
    db.session.commit()

    return jsonify({'success': True, 'painpoint': pp.to_dict()})


@oa_bp.route('/api/painpoints/<int:pid>', methods=['DELETE'])
def delete_painpoint(pid):
    """Delete a pain point."""
    pp = PainPoint.query.get_or_404(pid)
    db.session.delete(pp)
    db.session.commit()
    return jsonify({'success': True})


@oa_bp.route('/api/painpoints/<int:pid>/status', methods=['PUT'])
def update_painpoint_status(pid):
    """Update the status of a pain point."""
    pp = PainPoint.query.get_or_404(pid)
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')

    valid = ('new', 'reviewed', 'in_progress', 'resolved', 'rejected')
    if new_status not in valid:
        return jsonify({'success': False, 'error': f'无效状态，可选: {", ".join(valid)}'}), 400

    pp.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'painpoint': pp.to_dict()})


@oa_bp.route('/api/painpoint-title', methods=['POST'])
def generate_painpoint_title():
    """Use AI to generate a short title from conversation."""
    data = request.get_json(silent=True) or {}
    conversation = data.get('conversation', [])

    conv_text = "\n".join(
        f"{'员工' if m['role']=='user' else 'AI'}: {m['content']}"
        for m in conversation if m.get('content')
    )

    try:
        client = MiniMaxClient()
        prompt = TITLE_GENERATION_PROMPT.format(conversation=conv_text[:2000])
        title = client.generate_chat("你是一个标题生成器。", prompt, temperature=0.3)
        title = title or '工作痛点'
        # Strip <think>...</think> tags from MiniMax
        title = re.sub(r'<think>[\s\S]*?</think>', '', title).strip().strip('"\'')
        if not title:
            title = '工作痛点'
        if len(title) > 50:
            title = title[:50]
        return jsonify({'success': True, 'title': title})
    except Exception as e:
        return jsonify({'success': False, 'title': '工作痛点', 'error': str(e)})
