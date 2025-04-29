from flask import flash, redirect, render_template, url_for
from flask_login import login_required, current_user
from app.models import UserFile, Migration
from . import main_bp
from flask import render_template
from ..forms import ContactForm

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
    if not migrations:
        return render_template('workstation/migration_track.html', migrations=None)
    return render_template('workstation/migration_track.html', migrations=migrations)

@main_bp.route('/help')
def help():
    return render_template('help.html')

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        # Process the form data (send email, save to DB, etc.)
        flash('Your message has been sent! We will get back to you soon.', 'success')
        return redirect(url_for('main.contact'))
    return render_template('contact.html', form=form)