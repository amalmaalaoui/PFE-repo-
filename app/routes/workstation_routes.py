from flask import render_template
from flask_login import login_required, current_user
from app.models import UserFile, Migration
from . import main_bp

@main_bp.route('/workstation/manage_files')
@login_required
def manage_files():
    files = UserFile.query.filter_by(user_id=current_user.id).all()
    return render_template('workstation/manage_files.html', files=files)

@main_bp.route('/workstation/migrator')
@login_required
def migrator():
    files = UserFile.query.filter_by(user_id=current_user.id).all()
    return render_template('workstation/migrator.html', files=files)

@main_bp.route('/workstation/migration_track')
@login_required
def migration_track():
    migrations = Migration.query.filter_by(user_id=current_user.id)\
                              .order_by(Migration.created_at.desc())\
                              .all()
    return render_template('workstation/migration_track.html', migrations=migrations)