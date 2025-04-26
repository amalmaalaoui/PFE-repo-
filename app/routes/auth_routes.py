from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..forms import UserForm, EditUserForm
from app.models import User
from app import db
from . import admin_required, main_bp

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('main.admin_dashboard'))
        else:
            return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.is_admin:
                flash('Logged in successfully as admin', 'success')
                return redirect(url_for('main.admin_dashboard'))
            else:
                flash('Logged in successfully', 'success')
                return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('auth/login.html')

@main_bp.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    form = UserForm()
    if form.validate_on_submit():
        try:
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                is_admin=form.is_admin.data
            )
            new_user.set_password(form.password.data)
            db.session.add(new_user)
            db.session.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('main.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding user: {str(e)}', 'danger')
    return render_template('auth/add_user.html', form=form)

@main_bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = EditUserForm(obj=user)
    
    if request.method == 'GET':
        form.is_admin.data = user.is_admin
    
    if form.validate_on_submit():
        try:
            user.username = form.username.data
            user.email = form.email.data
            user.is_admin = form.is_admin.data
            
            if form.new_password.data:
                user.set_password(form.new_password.data)
                flash('Password has been updated', 'success')
            
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('main.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
    return render_template('auth/edit_user.html', form=form, user=user)

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
        user_id = request.form.get('user_id', type=int)
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([user_id, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('auth/reset_password.html', user_id=request.args.get('user_id'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html', user_id=request.args.get('user_id'))
            
        user = User.query.get(user_id)
        if not user:
            flash('User not found', 'error')
            return render_template('auth/reset_password.html', user_id=request.args.get('user_id'))

        try:
            user.set_password(password)
            db.session.commit()
            flash('Password has been reset successfully', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error resetting password: {str(e)}', 'danger')
    
    return render_template('auth/reset_password.html', user_id=request.args.get('user_id'))

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