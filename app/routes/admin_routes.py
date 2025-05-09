import os
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.sql import func
from app.models import Migration, UserFile, User
from app import db
from . import admin_required, main_bp
from .helpers import get_migration_volume, get_storage_usage
import psutil
import platform

@main_bp.route('/admin/manage_users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=10, error_out=False)
    return render_template('admin/manage_users.html', users=users)

@main_bp.route('/admin/files')
@admin_required
def admin_files():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    files = UserFile.query.order_by(UserFile.upload_date.desc()).paginate(page=page, per_page=per_page)
    all_users = User.query.all()
    return render_template('admin/files.html', files=files.items, all_users=all_users, page=page, total_pages=files.pages, total_files=files.total)

@main_bp.route('/admin/preview_file/<int:file_id>')
@admin_required
def admin_preview_file(file_id):
    file = UserFile.query.get_or_404(file_id)
    try:
        df = pd.read_excel(file.filepath, sheet_name=0, nrows=10)
        return jsonify({
            'filename': file.filename,
            'preview_html': df.to_html(classes='table-auto w-full', index=False)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/admin/delete_file/<int:file_id>', methods=['DELETE'])
@admin_required
def admin_delete_file(file_id):
    file = UserFile.query.get_or_404(file_id)
    try:
        os.remove(file.filepath)
        db.session.delete(file)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/admin/bulk_action', methods=['POST'])
@admin_required
def admin_bulk_action():
    data = request.json
    return jsonify({'success': True})


@main_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_migrations = Migration.query.count()
    completed_migrations = Migration.query.filter_by(status='COMPLETED').count()
    failed_migrations = Migration.query.filter_by(status='FAILED').count()
    pending_migrations = Migration.query.filter_by(status='PENDING').count()
    in_progress_migrations = Migration.query.filter_by(status='IN_PROGRESS').count()
    
    
    last_week = datetime.utcnow() - timedelta(days=7)
    last_week_count = Migration.query.filter(Migration.created_at >= last_week).count()
    change_percent = 0
    if last_week_count > 0:
        change_percent = ((total_migrations - last_week_count) / last_week_count) * 100
    
    avg_blocks = db.session.query(func.avg(Migration.block_count)).scalar() or 0
    total_blocks = db.session.query(func.sum(Migration.block_count)).scalar() or 0
    
    migration_volume = get_migration_volume(30)
    recent_migrations = Migration.query.order_by(Migration.created_at.desc()).limit(10).all()
    
    system_health = {
        'storage_used': get_storage_usage(),
        'db_size': 'TBC',
        'active_migrations': Migration.query.filter_by(status='in_progress').count()
    }
    
    return render_template('admin/dashboard.html',
        migration_stats={
            'total': total_migrations,
            'completed': completed_migrations,
            'failed': failed_migrations,
            'pending': pending_migrations,
            'in_progress': in_progress_migrations,
            'change_percent': change_percent,
            'avg_blocks': float(avg_blocks),
            'total_blocks': total_blocks
        },
        migration_volume=migration_volume,
        recent_migrations=recent_migrations,
        system_health=system_health
    )

@main_bp.route('/admin/system_info')
@admin_required
def get_system_info():
    system_info = {
        'flask_version': '1.1.2',
        'python_version': platform.python_version(),
        'database': 'SQLite',
        'server': platform.node(),
        'uptime': str(datetime.now()),
        'cpu_usage': psutil.cpu_percent(),
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'success': True
    }
    return jsonify(system_info)


from flask import jsonify, send_file, abort
from datetime import datetime
from sqlalchemy import or_

@main_bp.route('/api/migrations')
@login_required
@admin_required
def api_migrations():
    # Get filter parameters from request
    status_filter = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    user_id = request.args.get('user_id')
    
    # Base query
    query = Migration.query.order_by(Migration.created_at.desc())
    
    # Apply filters
    if status_filter:
        query = query.filter(Migration.status == status_filter)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Migration.created_at >= date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
            # Include the entire day by adding 1 day
            query = query.filter(Migration.created_at < date_to + timedelta(days=1))
        except ValueError:
            pass
    
    if user_id:
        query = query.filter(Migration.user_id == user_id)
    
    # Execute query and prepare response
    migrations = query.all()
    
    # Convert migrations to dictionary format for JSON response
    migrations_data = []
    for migration in migrations:
        migration_data = {
            'id': migration.id,
            'user_id': migration.user_id,
            'user': {
                'id': migration.user.id,
                'username': migration.user.username
            },
            'source_file': migration.source_file,
            'target_file': migration.target_file,
            'status': migration.status,
            'created_at': migration.created_at.isoformat() if migration.created_at else None,
            'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
            'block_count': migration.block_count,
            'error_message': migration.error_message
        }
        migrations_data.append(migration_data)
    
    return jsonify(migrations_data)

@main_bp.route('/api/migration/<int:migration_id>')
@login_required
@admin_required
def api_migration_details(migration_id):
    migration = Migration.query.get_or_404(migration_id)
    
    migration_data = {
        'id': migration.id,
        'user_id': migration.user_id,
        'user': {
            'id': migration.user.id,
            'username': migration.user.username
        },
        'source_file': migration.source_file,
        'target_file': migration.target_file,
        'status': migration.status,
        'created_at': migration.created_at.isoformat() if migration.created_at else None,
        'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
        'block_count': migration.block_count,
        'error_message': migration.error_message,
        'log_file_path': migration.log_file_path,
        'result_file_path': migration.result_file_path
    }
    
    return jsonify(migration_data)



@main_bp.route('/api/users')
@login_required
@admin_required
def api_users():
    # This endpoint provides user data for the user filter dropdown
    users = User.query.order_by(User.username).all()
    users_data = [{'id': user.id, 'username': user.username} for user in users]
    return jsonify(users_data)

@main_bp.route('/admin/logs')
@login_required
@admin_required
def logs():
    all_users = User.query.order_by(User.username).all()
    return render_template('admin/logs.html', all_users=all_users)