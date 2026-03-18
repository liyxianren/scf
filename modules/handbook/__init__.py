from flask import Blueprint

handbook_bp = Blueprint('handbook', __name__, template_folder='templates')

from . import routes  # noqa: E402
