from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
import pandas as pd
from datetime import datetime
from app.models import UserFile
from app import db, create_app
from . import main_bp
from .helpers import allowed_file

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
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        filepath = os.path.join(create_app().config['UPLOAD_FOLDER'], f'user_{current_user.id}', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        try:
            xls = pd.ExcelFile(filepath)
            sheet_count = len(xls.sheet_names)
            sheet_names = ','.join(xls.sheet_names)
        except Exception as e:
            sheet_count = 0
            sheet_names = ''

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


@main_bp.route('/preview_file/<int:file_id>')
@login_required
def preview_file(file_id):
    # Verify the file belongs to current user
    file = UserFile.query.filter_by(id=file_id, user_id=current_user.id).first()
    
    if not file:
        return jsonify({'error': 'File not found or access denied'}), 404
    
    try:
        df = pd.read_excel(file.filepath, sheet_name=0, nrows=10)
        return jsonify({
            'filename': file.filename,
            'preview_html': df.to_html(classes='table-auto w-full', index=False)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500