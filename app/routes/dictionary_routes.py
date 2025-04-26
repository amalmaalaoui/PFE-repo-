from flask import render_template
from flask_login import login_required
from . import admin_required, main_bp

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