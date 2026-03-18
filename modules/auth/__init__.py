from flask import Blueprint

auth_bp = Blueprint('auth', __name__, template_folder='templates')

from . import routes
from . import enrollment_routes
from . import chat_routes
