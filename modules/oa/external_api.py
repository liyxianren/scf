"""External OA API helpers."""
from functools import wraps

from flask import current_app, jsonify, request

from modules.auth.models import ExternalIdentity


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


def integration_api_required(func):
    """Protect OpenClaw integration endpoints with a dedicated token."""
    @wraps(func)
    def wrapped(*args, **kwargs):
        configured_token = (current_app.config.get('OPENCLAW_INTEGRATION_TOKEN') or '').strip()
        if not configured_token:
            return external_error('未配置 OPENCLAW_INTEGRATION_TOKEN', status=503, code='integration_disabled')

        request_token = (request.headers.get('X-Integration-Token') or '').strip()
        if request_token != configured_token:
            return external_error('无效的 Integration Token', status=401, code='invalid_integration_token')

        return func(*args, **kwargs)

    return wrapped


def resolve_external_actor(provider, external_user_id):
    normalized_provider = (provider or '').strip().lower()
    normalized_external_user_id = (external_user_id or '').strip()

    if not normalized_provider:
        return None, external_error('缺少 provider', status=400, code='missing_provider')
    if normalized_provider != 'feishu':
        return None, external_error('当前仅支持 feishu provider', status=400, code='unsupported_provider')
    if not normalized_external_user_id:
        return None, external_error('缺少 external_user_id', status=400, code='missing_external_user_id')

    identity = ExternalIdentity.query.filter_by(
        provider=normalized_provider,
        external_user_id=normalized_external_user_id,
    ).first()
    if not identity or identity.status != 'active':
        return None, external_error('未找到可用的外部身份映射', status=401, code='identity_not_found')

    actor = identity.user
    if not actor or not actor.is_active:
        return None, external_error('映射用户不可用', status=403, code='actor_inactive')

    return actor, None
