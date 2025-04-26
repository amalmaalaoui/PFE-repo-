from flask import render_template
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import datetime as dt
from app.models import UserFile, Migration
from app import db
from . import main_bp

@main_bp.route('/')
@login_required
def dashboard():
    # Get user-specific data
    files = UserFile.query.filter_by(user_id=current_user.id)\
                        .order_by(UserFile.upload_date.desc())\
                        .limit(5).all()
    migrations = Migration.query.filter_by(user_id=current_user.id)\
                              .order_by(Migration.created_at.desc())\
                              .limit(5).all()
    
    # Calculate stats for current user
    total_files = UserFile.query.filter_by(user_id=current_user.id).count()
    total_sheets = sum(file.sheet_count for file in files)
    
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
    
    # Get recent files
    recent_files = UserFile.query.filter(
        UserFile.user_id == current_user.id,
        UserFile.upload_date >= seven_days_ago
    ).all()
    
    return render_template('dashboard.html',
                         files=files,
                         migrations=migrations,
                         file_stats=file_stats,
                         recent_files=recent_files)