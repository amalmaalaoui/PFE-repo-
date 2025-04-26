from flask import render_template
from flask_login import login_required
from . import admin_required, main_bp

@main_bp.route('/configuration/system')
@login_required
@admin_required
def system_config():
    return render_template('configuration/system.html')

@main_bp.route('/configuration/account')
@login_required
def account_config():
    return render_template('configuration/account.html')