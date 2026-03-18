"""权限装饰器"""
from functools import wraps
from flask import jsonify, redirect, url_for, abort
from flask_login import current_user, login_required


def role_required(*roles):
    """页面/API 路由：要求登录且角色匹配"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator
