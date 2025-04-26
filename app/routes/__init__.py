from flask import Blueprint
from functools import wraps
from flask import redirect, flash
from flask_login import current_user

# Create blueprint
main_bp = Blueprint('main', __name__)

# Custom decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Import all route modules after blueprint creation to avoid circular imports
from .auth_routes import *
from .admin_routes import *
from .workstation_routes import *
from .file_routes import *
from .migration_routes import *
from .config_routes import *
from .dictionary_routes import *
from .dashboard_routes import *