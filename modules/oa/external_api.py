"""External OA API helpers."""
from functools import wraps

from flask import current_app, jsonify, request


def external_success(data=None, message=None, status=200):
    payload = {'success': True}
    if data is not None:
        payload['data'] = data
    if message:
        payload['message'] = message
    return jsonify(payload), status


def external_error(error, status=400, code=None):
    payload = {'success': False, 'error': error}
    if code:
        payload['code'] = code
    return jsonify(payload), status


def external_api_required(func):
    """Protect external OA endpoints with a dedicated API key."""
    @wraps(func)
    def wrapped(*args, **kwargs):
        configured_key = (current_app.config.get('OA_EXTERNAL_API_KEY') or '').strip()
        if not configured_key:
            return external_error('未配置 OA_EXTERNAL_API_KEY', status=503, code='external_api_disabled')

        request_key = (request.headers.get('X-OA-API-Key') or '').strip()
        if request_key != configured_key:
            return external_error('无效的 API Key', status=401, code='invalid_api_key')

        return func(*args, **kwargs)

    return wrapped
