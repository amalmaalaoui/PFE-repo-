from datetime import datetime, timedelta
from functools import wraps
from flask import current_app, redirect, flash, url_for
from flask_login import current_user
import os
import pandas as pd
from sqlalchemy.sql import func
from app.models import Migration

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ['xlsx', 'xls']

def get_migration_volume(days=30):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    date_range = [start_date + timedelta(days=x) for x in range(days + 1)]
    date_labels = [date.strftime('%Y-%m-%d') for date in date_range]
    
    results = Migration.query.with_entities(
        func.date(Migration.created_at).label('date'),
        func.count(Migration.id).label('count')
    ).filter(
        Migration.created_at >= start_date,
        Migration.created_at <= end_date
    ).group_by(
        func.date(Migration.created_at)
    ).all()
    
    counts_dict = {result.date.strftime('%Y-%m-%d'): result.count for result in results}
    counts = [counts_dict.get(date, 0) for date in date_labels]
    
    return {
        'dates': date_labels,
        'counts': counts
    }

def get_storage_usage():
    uploads_size = sum(os.path.getsize(os.path.join(current_app.config['UPLOAD_FOLDER'], f)) 
                     for f in os.listdir(current_app.config['UPLOAD_FOLDER']) 
                     if os.path.isfile(os.path.join(current_app.config['UPLOAD_FOLDER'], f)))
    total_space = 100 * 1024 * 1024 * 1024  # 100GB example
    return min(100, (uploads_size / total_space) * 100)

def excel_to_Dict(excel_file):
    excel_data = pd.ExcelFile(excel_file)
    dict_QTP = {}
    dict_safal = {}
    
    for sheet_name in excel_data.sheet_names:
        df = excel_data.parse(sheet_name)
        if sheet_name == 'QTP':
            listblock = set(df['TestCaseID'].tolist())
            for listid in listblock:
                dfblock = df[df['TestCaseID'] == listid]
                dict_QTP[int(listid) if not pd.isna(listid) else 0] = dfblock
        if sheet_name == 'Safal':
            listblock1 = set(df['RowID'].tolist())
            for listid in listblock1:
                dfblock = df[df['RowID'] == listid]
                dict_safal[int(listid) if not pd.isna(listid) else 0] = dfblock
    
    listblock = {int(x) for x in listblock if not pd.isna(x)}
    listblock1 = {int(x) for x in listblock1 if not pd.isna(x)} if 'listblock1' in locals() else set()
    
    for aint in listblock:
        if aint not in listblock1:
            raise ValueError(f'Error: {aint} not in Safal sheet')
    
    return dict_QTP, dict_safal, list(listblock)