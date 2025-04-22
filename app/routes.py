from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from app.models import User, Migration, UserFile
from app import db
import os
import pandas as pd
from datetime import datetime
from functools import wraps
from .forms import UserForm, EditUserForm  # Assuming you have a UserForm class

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
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            # In production: Send password reset email
            flash('Password reset link has been sent to your email', 'info')
            return redirect(url_for('main.login'))
        flash('Email not found', 'error')
    return render_template('auth/reset_password.html')

# Dashboard and main routes
@main_bp.route('/')
@login_required
def dashboard():
    # Get user-specific data
    files = UserFile.query.filter_by(user_id=current_user.id).order_by(UserFile.upload_date.desc()).limit(5).all()
    migrations = Migration.query.filter_by(user_id=current_user.id).order_by(Migration.created_at.desc()).limit(5).all()
    
    # Calculate stats
    total_files = UserFile.query.filter_by(user_id=current_user.id).count()
    total_sheets = sum(file.sheet_count for file in files)
    
    # Calculate change_percent: compare files uploaded in last 7 days vs previous 7 days
    from datetime import datetime, timedelta
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)
    
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
    
    return render_template('dashboard.html',
                         files=files,
                         migrations=migrations,
                         file_stats=file_stats)

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
@login_required
@admin_required
def admin_files():
    files = UserFile.query.order_by(UserFile.upload_date.desc()).all()
    return render_template('admin/files.html', files=files)

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
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'user_{current_user.id}', filename)
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
    
    if not user_file:
        return jsonify({'error': 'File not found or access denied'}), 404
    
    # Create migration record
    migration = Migration(
        user_id=current_user.id,
        original_filename=user_file.filename,
        status='pending',
        scheduled_time=datetime.strptime(data.get('schedule_time'), '%Y-%m-%dT%H:%M') if data.get('schedule_time') else None
    )
    db.session.add(migration)
    db.session.commit()
    
    # Create user-specific output folder
    output_folder = os.path.join(app.config['MIGRATION_FOLDER'], f'user_{current_user.id}', f'migration_{migration.id}')
    os.makedirs(output_folder, exist_ok=True)
    
    # Prepare migration data
    migration_data = {
        'filepath': user_file.filepath,
        'email_notification': data.get('email_notification', False),
        'generate_report': data.get('generate_report', False),
        'ignore_errors': data.get('ignore_errors', False),
        'output_folder': output_folder,
        'migration_id': migration.id
    }
    
    if data.get('schedule_time'):
        # Schedule the job
        run_date = datetime.strptime(data['schedule_time'], '%Y-%m-%dT%H:%M')
        job = scheduler.add_job(
            run_migration_task,
            'date',
            run_date=run_date,
            kwargs=migration_data,
            id=f"migration_{migration.id}"
        )
        
        return jsonify({
            'status': 'scheduled',
            'job_id': job.id,
            'scheduled_time': run_date.isoformat(),
            'countdown': (run_date - datetime.now()).total_seconds()
        })
    else:
        # Run immediately
        results = run_migration_task(**migration_data)
        return jsonify(results)

def run_migration_task(filepath, output_folder, migration_id, **kwargs):
    try:
        # Run migration
        dict_QTP, dict_safal, listblock = excel_to_Dict(filepath)
        
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
        migration.output_folder = output_folder
        db.session.commit()
        
        return {
            'status': 'completed',
            'block_count': len(listblock),
            'output_folder': output_folder
        }
    except Exception as e:
        migration = Migration.query.get(migration_id)
        migration.status = 'failed'
        migration.output_folder = output_folder
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
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

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