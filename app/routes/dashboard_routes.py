from flask import jsonify, render_template
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import datetime as dt
from app.models import UserFile, Migration
from app import db
from . import main_bp
from sqlalchemy import func

@main_bp.route('/')
@login_required
def dashboard():
    # Get user-specific data
    files = UserFile.query.filter_by(user_id=current_user.id)\
                        .order_by(UserFile.upload_date.desc())\
                        .limit(5).all()
    
    # Get recent migrations for the user
    migrations = Migration.query.filter_by(user_id=current_user.id)\
                              .order_by(Migration.created_at.desc())\
                              .limit(5).all()
    
    # Calculate stats for current user
    total_files = UserFile.query.filter_by(user_id=current_user.id).count()
    total_sheets = db.session.query(func.sum(UserFile.sheet_count))\
                            .filter_by(user_id=current_user.id)\
                            .scalar() or 0
    
    # Calculate change_percent
    now = dt.datetime.now()
    seven_days_ago = now - dt.timedelta(days=7)
    fourteen_days_ago = now - dt.timedelta(days=14)
    
    recent_count = UserFile.query.filter(
        UserFile.user_id == current_user.id,
        UserFile.upload_date >= seven_days_ago
    ).count()
    
    previous_count = UserFile.query.filter(
        UserFile.user_id == current_user.id,
        UserFile.upload_date >= fourteen_days_ago,
        UserFile.upload_date < seven_days_ago
    ).count()
    
    change_percent = 0 if previous_count == 0 else \
        ((recent_count - previous_count) / previous_count) * 100
    
    file_stats = {
        'total_files': total_files,
        'total_sheets': total_sheets,
        'change_percent': round(change_percent, 2)
    }
    
    # Get recent files (last 5)
    recent_files = UserFile.query.filter_by(user_id=current_user.id)\
                               .order_by(UserFile.upload_date.desc())\
                               .limit(5).all()
    
    migration_stats = {
        'total_migrations': Migration.query.filter_by(user_id=current_user.id).count(),
        'completed_count': Migration.query.filter_by(user_id=current_user.id, status='COMPLETED').count(),
        'failed_count': Migration.query.filter_by(user_id=current_user.id, status='FAILED').count(),
        'in_progress_count': Migration.query.filter_by(user_id=current_user.id, status='IN_PROGRESS').count(),
        'scheduled_count': Migration.query.filter_by(user_id=current_user.id, status='SCHEDULED').count(),
    }
    
    # Calculate success rate
    total = migration_stats['total_migrations']
    completed = migration_stats['completed_count']
    migration_stats['success_rate'] = round((completed / total) * 100, 2) if total > 0 else 0
    
    return render_template('dashboard.html',
                         files=files,
                         migrations=migrations,
                         file_stats=file_stats,
                         recent_files=recent_files,
                         migration_stats=migration_stats)  # Add this line
    
@main_bp.route('/api/migration_stats')
@login_required
def get_migration_stats():
    # Filter migrations by current user unless admin
    query = Migration.query
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)

    def calculate_success_rate():
        completed = query.filter_by(status='COMPLETED').count()
        total = query.count()
        return round((completed / total) * 100, 2) if total > 0 else 0

    def calculate_avg_processing_time():
        completed_migrations = query.filter(
            Migration.status == 'COMPLETED',
            Migration.completed_at.isnot(None),
            Migration.created_at.isnot(None)
        ).all()
        
        if not completed_migrations:
            return "0s"
            
        total_seconds = sum(
            (m.completed_at - m.created_at).total_seconds()
            for m in completed_migrations
        )
        avg_seconds = total_seconds / len(completed_migrations)
        
        # Format as human-readable time
        if avg_seconds < 60:
            return f"{int(avg_seconds)}s"
        elif avg_seconds < 3600:
            return f"{int(avg_seconds // 60)}m {int(avg_seconds % 60)}s"
        else:
            hours = avg_seconds // 3600
            minutes = (avg_seconds % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"

    def get_fastest_migration():
        fastest = query.filter(
            Migration.status == 'COMPLETED',
            Migration.completed_at.isnot(None),
            Migration.created_at.isnot(None)
        ).order_by(
            (Migration.completed_at - Migration.created_at)
        ).first()
        
        if not fastest:
            return "N/A"
            
        duration = fastest.completed_at - fastest.created_at
        if duration.total_seconds() < 60:
            return f"{int(duration.total_seconds())}s"
        elif duration.total_seconds() < 3600:
            return f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"
        else:
            hours = duration.total_seconds() // 3600
            minutes = (duration.total_seconds() % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"

    stats = {
        'total_migrations': query.count(),
        'completed_count': query.filter_by(status='COMPLETED').count(),
        'failed_count': query.filter_by(status='FAILED').count(),
        'in_progress_count': query.filter_by(status='IN_PROGRESS').count(),
        'scheduled_count': query.filter_by(status='SCHEDULED').count(),
        'pending_count': query.filter_by(status='PENDING').count(),
        'total_blocks': db.session.query(func.sum(Migration.block_count)).scalar() or 0,
        'success_rate': calculate_success_rate(),
        'avg_processing_time': calculate_avg_processing_time(),
        'fastest_migration': get_fastest_migration()
    }
    return jsonify(stats)

@main_bp.route('/api/recent_migrations')
@login_required
def get_recent_migrations():
    query = Migration.query
    if not current_user.is_admin:
        query = query.filter_by(user_id=current_user.id)
        
    migrations = query.order_by(Migration.created_at.desc()).limit(5).all()
    return jsonify([{
        'id': m.id,
        'source_file': m.source_file,
        'target_file': m.target_file,
        'status': m.status,
        'created_at': m.created_at.isoformat() if m.created_at else None,
        'completed_at': m.completed_at.isoformat() if m.completed_at else None,
        'error_message': m.error_message,
        'block_count': m.block_count,
        'user_id': m.user_id
    } for m in migrations])