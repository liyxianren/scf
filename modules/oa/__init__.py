from flask import Blueprint

oa_bp = Blueprint('oa', __name__, template_folder='templates')

from . import routes  # noqa: E402
from . import external_routes  # noqa: E402
from . import agent_routes  # noqa: E402
from . import painpoint_routes  # noqa: E402
