
import platform
from sched import scheduler
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app.models import User, Migration, UserFile
from app import db, create_app
import os
import pandas as pd
from datetime import datetime
from datetime import timedelta
from functools import wraps
from .forms import UserForm, EditUserForm  # Assuming you have a UserForm class

import datetime as dt

from scheduler import Scheduler
from scheduler.trigger import Monday, Tuesday
import time
import threading
from app.extensions import scheduler
import time
import psutil
import platform
from datetime import datetime
from sqlalchemy.sql import text

# Create blueprint
main_bp = Blueprint('main', __name__)

# Custom decorators
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Authentication routes
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('auth/login.html')

#add_user route
@main_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    print("Add user route accessed")
    form = UserForm()  # Instantiate your form
    if form.validate_on_submit():
        try:
            # Create a new user
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                is_admin=form.is_admin.data
            )
            new_user.set_password(form.password.data)  # Set the user's password
            db.session.add(new_user)
            db.session.commit()
            flash('User added successfully!', 'success')
            print("User added successfully")
            return redirect(url_for('main.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding user: {str(e)}', 'danger')
            print(f"Error adding user: {str(e)}")
    return render_template('auth/add_user.html', form=form)  # Pass form to template

#edit user route
@main_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)  # Populate form with user data
    
    if request.method == 'GET':
        # Pre-populate the form for GET requests
        form.is_admin.data = user.is_admin
    
    if form.validate_on_submit():
        try:
            # Update user data
            user.username = form.username.data
            user.email = form.email.data
            user.is_admin = form.is_admin.data
            
            # Handle password change if provided
            if form.new_password.data:
                user.set_password(form.new_password.data)
                flash('Password has been updated', 'success')
            
            db.session.commit()
            flash('User updated successfully!', 'success')
            print("User updated successfully")
            return redirect(url_for('main.manage_users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
            print(f"Error updating user: {str(e)}")
            return render_template('auth/edit_user.html', 
                                   form=form, 
                                   user=user,
                                   title='Edit User', 
                                   error=str(e))
    else:
        print(form.errors)
        if request.method == 'POST':
            flash('Form validation failed. Please check your input.', 'danger')
            print("Form validation failed.")
    
    # For GET requests or failed validation
    return render_template('auth/edit_user.html', 
                         form=form, 
                         user=user,
                         title='Edit User')

#delte user route
@main_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('main.manage_users'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('main.manage_users'))


@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        # Get user_id from form data instead of query args
        user_id = request.form.get('user_id', type=int)
        print(f"User ID: {user_id}")
        
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([user_id, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('auth/reset_password.html', 
                                user_id=request.args.get('user_id'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html',
                                user_id=request.args.get('user_id'))
            
        user = User.query.get(user_id)
        if not user:
            flash('User not found', 'error')
            return render_template('auth/reset_password.html',
                                user_id=request.args.get('user_id'))

        try:
            user.set_password(password)
            db.session.commit()
            flash('Password has been reset successfully', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error resetting password: {str(e)}', 'danger')
    
    # For GET requests, pass the user_id to the template
    return render_template('auth/reset_password.html',
                         user_id=request.args.get('user_id'))
# Dashboard and main routes
@main_bp.route('/')
@login_required
def dashboard():
    if current_user.is_admin:
        # redirect to admin dashboard if user is admin
        return redirect(url_for('main.admin_dashboard'))
    # Check if the user is an admin
    if False:
        # Get data for all users
        files = UserFile.query.order_by(UserFile.upload_date.desc()).limit(5).all()
        migrations = Migration.query.order_by(Migration.created_at.desc()).limit(5).all()
        
        # Calculate stats for all users
        total_files = UserFile.query.count()
        total_sheets = db.session.query(db.func.sum(UserFile.sheet_count)).scalar() or 0
        
        # Calculate change_percent: compare files uploaded in last 7 days vs previous 7 days
        from datetime import datetime, timedelta
        now = datetime.now()
        seven_days_ago = now - datetime.timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)
        
        recent_count = UserFile.query.filter(UserFile.upload_date >= seven_days_ago).count()
        previous_count = UserFile.query.filter(
            UserFile.upload_date >= fourteen_days_ago,
            UserFile.upload_date < seven_days_ago
        ).count()
        
        if previous_count == 0:
            change_percent = 0
        else:
            change_percent = ((recent_count - previous_count) / previous_count) * 100
        
        file_stats = {
            'total_files': total_files,
            'total_sheets': total_sheets,
            'change_percent': round(change_percent, 2)
        }
        
        # Get recent files for all users
        recent_files = UserFile.query.filter(UserFile.upload_date >= seven_days_ago).all()
    else:
        # Get user-specific data
        files = UserFile.query.filter_by(user_id=current_user.id).order_by(UserFile.upload_date.desc()).limit(5).all()
        migrations = Migration.query.filter_by(user_id=current_user.id).order_by(Migration.created_at.desc()).limit(5).all()
        
        # Calculate stats for the current user
        total_files = UserFile.query.filter_by(user_id=current_user.id).count()
        total_sheets = sum(file.sheet_count for file in files)
        
        # Calculate change_percent: compare files uploaded in last 7 days vs previous 7 days

        now = dt.datetime.now()
        seven_days_ago = now.replace(day=now.day - 7)
        fourteen_days_ago = now.replace(day=now.day - 14)
        
        recent_count = UserFile.query.filter(
            UserFile.user_id == current_user.id,
            UserFile.upload_date >= seven_days_ago
        ).count()
        
        previous_count = UserFile.query.filter(
            UserFile.user_id == current_user.id,
            UserFile.upload_date >= fourteen_days_ago,
            UserFile.upload_date < seven_days_ago
        ).count()
        
        if previous_count == 0:
            change_percent = 0
        else:
            change_percent = ((recent_count - previous_count) / previous_count) * 100
        
        file_stats = {
            'total_files': total_files,
            'total_sheets': total_sheets,
            'change_percent': round(change_percent, 2)
        }
        
        # Get recent files for the current user
        recent_files = UserFile.query.filter(
            UserFile.user_id == current_user.id,
            UserFile.upload_date >= seven_days_ago
        ).all()
    
    return render_template('dashboard.html',
                           files=files,
                           migrations=migrations,
                           file_stats=file_stats,
                           recent_files=recent_files)

# Workstation routes
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

# Admin routes
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
    
    return render_template('admin/files.html', 
                         files=files.items,
                         all_users=all_users,
                         page=page,
                         total_pages=files.pages,
                         total_files=files.total)

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
    # Implement bulk actions logic here
    return jsonify({'success': True})


@main_bp.route('/admin/logs')
@login_required
@admin_required
def logs():
    migrations = Migration.query.order_by(Migration.created_at.desc()).all()
    return render_template('admin/logs.html', migrations=migrations)

# File operations
@main_bp.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('main.manage_files'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('main.manage_files'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(create_app().config['UPLOAD_FOLDER'], f'user_{current_user.id}', filename)
        print(f"File path: {filepath}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        # Get file info
        try:
            xls = pd.ExcelFile(filepath)
            sheet_count = len(xls.sheet_names)
            sheet_names = ','.join(xls.sheet_names)
        except Exception as e:
            sheet_count = 0
            sheet_names = ''

        # Save to database
        user_file = UserFile(
            user_id=current_user.id,
            filename=filename,
            filepath=filepath,
            size=os.path.getsize(filepath),
            sheet_count=sheet_count,
            sheet_names=sheet_names
        )
        db.session.add(user_file)
        db.session.commit()
        
        flash('File successfully uploaded', 'success')
    else:
        flash('Allowed file types are .xlsx, .xls', 'error')
    
    return redirect(url_for('main.manage_files'))

@main_bp.route('/delete_file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file = UserFile.query.filter_by(id=file_id, user_id=current_user.id).first()
    if not file:
        flash('File not found or access denied', 'error')
        return redirect(url_for('main.manage_files'))
    
    try:
        os.remove(file.filepath)
        db.session.delete(file)
        db.session.commit()
        flash('File deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')
    
    return redirect(url_for('main.manage_files'))
    # Migration API
@main_bp.route('/api/start_migration', methods=['POST'])
@login_required
def start_migration():
    data = request.json
    file_id = data['file_id']
    user_file = UserFile.query.filter_by(id=file_id, user_id=current_user.id).first()
    print("user file", user_file.filename)
    if not user_file:
        return jsonify({'error': 'File not found or access denied'}), 404
    scheduled_time = data.get('schedule_time')
    if scheduled_time:
        try:
            scheduled_time = datetime.strptime(data['schedule_time'], '%Y-%m-%dT%H:%M')
            print("scheduled time", scheduled_time)
            if scheduled_time < datetime.now():
                return jsonify({'error': 'Scheduled time must be in the future'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DDTHH:MM'}), 400

    # Create migration record
    migration = Migration(
        user_id=current_user.id,
        source_file=user_file.filename,
        target_file=user_file.filename + "_safal",
        status='pending',
        created_at=datetime.strptime(data.get('schedule_time'), '%Y-%m-%dT%H:%M') if data.get('schedule_time') else None
        )
    db.session.add(migration)
    db.session.commit()
    
    # Create user-specific output folder
    output_folder = os.path.join(create_app().config['MIGRATION_FOLDER'], f'user_{current_user.id}', f'migration_{user_file.filename}')
    os.makedirs(output_folder, exist_ok=True)
    run_date = datetime.strptime(data.get('schedule_time'), '%Y-%m-%dT%H:%M') if data.get('schedule_time') else None

    # Prepare migration data
    migration_data = {
        'filepath': user_file.filepath,
        'email_notification': data.get('email_notification', False),
        'generate_report': data.get('generate_report', False),
        'ignore_errors': data.get('ignore_errors', False),
        'output_folder': output_folder,
        'migration_id': migration.id
    }
    if scheduled_time:
        try:
            job = scheduler.scheduler.add_job(
                run_migration_task,
                'date',
                run_date=scheduled_time,
                kwargs=migration_data,
                id=f"migration_{migration.id}"
            )
        except Exception as e:
            current_app.logger.error(f"Error scheduling job: {str(e)}", exc_info=True)
            return jsonify({'error': f"Failed to schedule migration: {str(e)}"}), 500
        print("job", job.id)
        
        return jsonify({
            'status': 'scheduled',
            'job_id': job.id,
            'scheduled_time': run_date.isoformat(),
            'countdown': (run_date - datetime.now()).total_seconds()
        })
    else:
        # Run immediately
        results = run_migration_task(**migration_data)
        results['job_id'] = f"migration_{migration.id}"
        return jsonify(results)

def shutdown_scheduler():
    scheduler.scheduler.shutdown()

#update profile
@main_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        
        if not username or not email:
            flash('All fields are required', 'error')
            return redirect(url_for('main.account_config'))
        
        current_user.username = username
        current_user.email = email
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
    
    return redirect(url_for('main.account_config'))


@main_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # Migration statistics
    total_migrations = Migration.query.count()
    completed_migrations = Migration.query.filter_by(status='completed').count()
    failed_migrations = Migration.query.filter_by(status='failed').count()
    pending_migrations = Migration.query.filter_by(status='pending').count()
    in_progress_migrations = Migration.query.filter_by(status='in_progress').count()
    
    # Calculate changes from last week
    last_week = datetime.utcnow() - timedelta(days=7)
    last_week_count = Migration.query.filter(Migration.created_at >= last_week).count()
    change_percent = 0
    if last_week_count > 0:
        change_percent = ((total_migrations - last_week_count) / last_week_count) * 100
    
    # Calculate average blocks per migration
    avg_blocks = db.session.query(db.func.avg(Migration.block_count)).scalar() or 0
    total_blocks = db.session.query(db.func.sum(Migration.block_count)).scalar() or 0
    
    # Get migration volume for last 30 days
    migration_volume = get_migration_volume(30)
    
    # Get recent migrations
    recent_migrations = Migration.query.order_by(Migration.created_at.desc()).limit(10).all()
    
    # System health data
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

def get_migration_volume(days=30):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Generate all dates in the range
    date_range = [start_date + timedelta(days=x) for x in range(days + 1)]
    date_labels = [date.strftime('%Y-%m-%d') for date in date_range]
    
    # Query database for migration counts per day
    results = db.session.query(
        db.func.date(Migration.created_at).label('date'),
        db.func.count(Migration.id).label('count')
    ).filter(
        Migration.created_at >= start_date,
        Migration.created_at <= end_date
    ).group_by(
        db.func.date(Migration.created_at)
    ).all()
    
    # Create a dictionary of date:count
    counts_dict = {result.date.strftime('%Y-%m-%d'): result.count for result in results}
    
    # Fill in missing dates with 0
    counts = [counts_dict.get(date, 0) for date in date_labels]
    
    return {
        'dates': date_labels,
        'counts': counts
    }

def get_storage_usage():
    # Implement actual storage calculation
    # This is a placeholder - replace with real implementation
    uploads_size = sum(os.path.getsize(os.path.join(create_app().config['UPLOAD_FOLDER'], f)) 
                      for f in os.listdir(create_app().config['UPLOAD_FOLDER']) 
                      if os.path.isfile(os.path.join(create_app().config['UPLOAD_FOLDER'], f)))
    total_space = 100 * 1024 * 1024 * 1024  # 100GB example
    return min(100, (uploads_size / total_space) * 100)




@main_bp.route('/admin/system_info')
@admin_required
def get_system_info():
    system_info = {
        'flask_version': '1.1.2',
        'python_version': platform.python_version(),
        'database': 'SQLite',
        'server': platform.node(),
        'uptime': str(datetime.now() ),
        'cpu_usage': psutil.cpu_percent(),
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'success': True
    }
    return jsonify(system_info)
@main_bp.route('/api/migration_progress', methods=['GET'])
@login_required
def migration_progress():
    job_id = request.args.get('job_id')
    
    if not job_id or job_id == 'undefined':
        return jsonify({'error': 'Invalid job ID'}), 400
    
    try:
        # Check if it's a scheduled job
        #print all jobs in the scheduler
        print("all jobs", scheduler.scheduler.get_jobs())
        job = scheduler.scheduler.get_job(job_id)
        print("job", job, job_id)
        if job:
            time_remaining = int((job.next_run_time - datetime.now(job.next_run_time.tzinfo)).total_seconds())

            
            return jsonify({
                'status': 'scheduled',
                'progress': 0,
                'time_remaining': max(0, time_remaining),
                'job_id': job_id
            })
        
        # Check database for completed/failed migrations
        try:
            migration_id = int(job_id.replace('migration_', ''))
            migration = Migration.query.get(migration_id)
            
            if migration:
                return jsonify({
                    'status': migration.status,
                    'progress': 100,
                    'block_count': migration.block_count or 0,
                    'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
                })
        except ValueError:
            pass
        
        return jsonify({'error': 'Job not found'}), 404
        
    except Exception as e:
        current_app.logger.error(f"Error checking migration progress: {str(e)}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


    
def run_migration_task(filepath, output_folder, migration_id, **kwargs):
    try:
        # Run migration
        dict_QTP, dict_safal, listblock = excel_to_Dict(filepath)
        
                # Get the generated files
        generated_files = []
        for filename in os.listdir(output_folder):
            if filename.endswith('_Dictionnary.xlsx'):
                filepath = os.path.join(output_folder, filename)
                df = pd.read_excel(filepath, sheet_name='QTP')
                generated_files.append({
                    'filename': filename,
                    'block_id': filename.split('_')[0],
                    'row_count': len(df),
                    'migrated': False
                })


        
        # Save results to user-specific folder
        for idlist in listblock:
            output_path = os.path.join(output_folder, f'{idlist}_Dictionary.xlsx')
            with pd.ExcelWriter(output_path) as writer:
                dict_QTP[idlist].to_excel(writer, sheet_name='QTP', index=False)
                dict_safal[idlist].to_excel(writer, sheet_name='Safal', index=False)
        
        # Update migration status
        migration = Migration.query.get(migration_id)
        migration.status = 'completed'
        migration.completed_at = datetime.now()
        migration.block_count = len(listblock)
        db.session.commit()
        
        return {
            'status': 'completed',
            'block_count': len(listblock),
            'output_folder': output_folder
        }
    except Exception as e:
        migration = Migration.query.get(migration_id)
        migration.status = 'failed'
        migration.error_message = str(e)
        db.session.commit()
        
        if kwargs.get('ignore_errors'):
            return {
                'status': 'completed_with_errors',
                'error': str(e),
                'block_count': len(listblock) if 'listblock' in locals() else 0
            }
        return {
            'status': 'failed',
            'error': str(e)
        }

    # Helper functions
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in create_app().config['ALLOWED_EXTENSIONS']

def excel_to_Dict(excel_file):
    excel_data = pd.ExcelFile(excel_file)
    table = []
    dict_QTP = {}
    dict_safal = {}
    for sheet_name in excel_data.sheet_names:
        df = excel_data.parse(sheet_name)
        if sheet_name == 'QTP':
            listblock = set(df['TestCaseID'].tolist())
            for listid in listblock:
                dfblock = df[df['TestCaseID'] == listid]
                if pd.isna(listid):
                    dict_QTP[0] = dfblock
                else:
                    dict_QTP[int(listid)] = dfblock
        if sheet_name == 'Safal':
            listblock1 = set(df['RowID'].tolist())
            for listid in listblock1:
                dfblock = df[df['RowID'] == listid]
                if pd.isna(listid):
                    dict_safal[0] = dfblock
                else:
                    dict_safal[int(listid)] = dfblock
    listblock = {int(x) for x in listblock if not pd.isna(x)}
    listblock1 = {int(x) for x in listblock1 if not pd.isna(x)} if 'listblock1' in locals() else set()
    for aint in listblock:
        if aint not in listblock1:
            raise ValueError(f'Error: {aint} not in Safal sheet')
    return dict_QTP, dict_safal, list(listblock)

# Configuration routes
@main_bp.route('/configuration/system')
@login_required
@admin_required
def system_config():
    return render_template('configuration/system.html')

@main_bp.route('/configuration/account')
@login_required
def account_config():
    return render_template('configuration/account.html')

# Dictionary routes
@main_bp.route('/dictionary/view')
@login_required
def view_dictionaries():
    return render_template('dictionary/view.html')

@main_bp.route('/dictionary/add')
@login_required
@admin_required
def add_dictionary():
    return render_template('dictionary/add_dictionary.html')

@main_bp.route('/dictionary/add_item')
@login_required
def add_dictionary_item():
    return render_template('dictionary/add_item.html')