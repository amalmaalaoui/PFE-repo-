from sched import scheduler
import shutil
from flask import current_app, request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime
import os
import pandas as pd
from app.models import Migration, UserFile
from app import db, create_app
from . import main_bp
from .helpers import excel_to_Dict
from enum import Enum
from app import scheduler  # Import from your package
from datetime import datetime, timezone
from pytz import timezone
tunis_tz = timezone('Africa/Tunis')
class MigrationStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SCHEDULED = 'scheduled'

    def __str__(self):
        return self.value

@main_bp.route('/scheduler/status')
def scheduler_status():
    jobs = scheduler.get_jobs()
    return jsonify({
        'running': scheduler.running,
        'job_count': len(jobs),
        'next_run': min(job.next_run_time for job in jobs).isoformat() if jobs else None
    })
@main_bp.route('/api/start_migration', methods=['POST'])
@login_required
def start_migration():
    data = request.get_json()
    file_id = data.get('file_id')
    user_file = UserFile.query.filter_by(id=file_id, user_id=current_user.id).first()
    
    if not user_file:
        return jsonify({'error': 'File not found or access denied'}), 404
        
    scheduled_time = None
    if data.get('schedule_time'):
        try:
            scheduled_time = datetime.strptime(data['schedule_time'], '%Y-%m-%dT%H:%M')
            if scheduled_time < datetime.now():
                return jsonify({'error': 'Scheduled time must be in the future'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DDTHH:MM'}), 400

    migration = Migration(
        user_id=current_user.id,
        source_file=user_file.filename,
        target_file=f"{user_file.filename}_safal",
        status='pending',
        created_at=datetime.utcnow(),
        scheduled_time=scheduled_time
    )
    db.session.add(migration)
    db.session.commit()
    
    output_folder = os.path.join(current_app.config['MIGRATION_FOLDER'], 
                               f'user_{current_user.id}', 
                               f'migration_{migration.id}')
    os.makedirs(output_folder, exist_ok=True)

    migration_data = {
        'filepath': user_file.filepath,
        'output_folder': output_folder,
        'migration_id': migration.id,
        'email_notification': data.get('email_notification', False),
        'generate_report': data.get('generate_report', False),
        'ignore_errors': data.get('ignore_errors', False)
    }
    
    if scheduled_time:
        try:
            # Schedule the job with kwargs only (no args)
            job = scheduler.add_job(
                    func= run_migration_task,  # String reference
                    trigger='date',
                    run_date=scheduled_time,
                    kwargs=migration_data,
                    id=f"migration_{migration.id}",
                    replace_existing=True
                )
            
            migration.job_id = job.id
            db.session.commit()
            
            return jsonify({
                'status': 'scheduled',
                'job_id': job.id,
                'scheduled_time': scheduled_time.isoformat(),
                'countdown': (scheduled_time - datetime.now()).total_seconds(),
                'migration_id': migration.id
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to schedule migration: {str(e)}")
            return jsonify({'error': f"Failed to schedule migration: {str(e)}"}), 500
    else:
        try:
            results = run_migration_task(**migration_data)
            results['job_id'] = f"migration_{migration.id}"
            return jsonify(results)
        except Exception as e:
            migration.status = 'failed'
            migration.error_message = str(e)
            db.session.commit()
            return jsonify({
                'status': 'failed',
                'error': str(e),
                'job_id': f"migration_{migration.id}"
            }), 500

@main_bp.route('/api/cancel_migration', methods=['POST'])
@login_required
def cancel_migration():
    job_id = request.json.get('job_id')
    
    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400

    try:
        # First check if it's a scheduled job
        job = scheduler.get_job(job_id)
        if job:
            scheduler.remove_job(job_id)
            return jsonify({'status': 'cancelled', 'job_id': job_id})
        
        # Then check database for migration status
        migration = Migration.query.filter_by(
            id=int(job_id.split('_')[-1]),
            user_id=current_user.id
        ).first()
        
        if not migration:
            return jsonify({'error': 'Migration not found'}), 404
        
        # Update migration status to cancelled
        migration.status = 'cancelled'
        db.session.commit()
        
        return jsonify({'status': 'cancelled', 'job_id': job_id})
        
    except Exception as e:
        current_app.logger.error(f"Error cancelling migration: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@main_bp.route('/api/validate_migration', methods=['POST'])
@login_required
def validate_migration():
    data = request.get_json()
    file_id = data.get('file_id')
    
    if not file_id:
        return jsonify({'error': 'File ID required'}), 400
    
    user_file = UserFile.query.filter_by(id=file_id, user_id=current_user.id).first()
    
    if not user_file:
        return jsonify({'error': 'File not found or access denied'}), 404
    
    try:
        # Check if a migration exists for the file
        migration = Migration.query.filter_by(
            source_file=user_file.filename,
            user_id=current_user.id
        ).order_by(Migration.created_at.desc()).first()
        
        if migration:
            response = {
                'status': migration.status,
                'migration_id': migration.id,
                'block_count': migration.block_count or 0,
                'validation_errors': migration.error_message.split('\n') if migration.error_message else []
            }
            return jsonify(response), 200
        else:
            return jsonify({'error': 'No migration found for the specified file'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error validating migration: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@main_bp.route('/api/migration_progress', methods=['GET'])
@login_required
def migration_progress():
    job_id = request.args.get('job_id')
    
    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400

    try:
        # First check if it's a scheduled job
        job = scheduler.get_job(job_id)
        #print(job)
        if job:
            now = datetime.now(tunis_tz)
            job_time = job.next_run_time.astimezone(tunis_tz)
            
            time_remaining = (job_time - now).total_seconds()
            if time_remaining < 0:
                time_remaining = 0
            return jsonify({
                'status': 'scheduled',
                'progress': 0,
                'time_remaining': max(0, time_remaining),
                'job_id': job_id
            })

        # Then check database for migration status
        try:
            print(job_id.split('_')[-1])
            migration_id = int(job_id.split('_')[-1])
            migration = Migration.query.filter_by(
                id=migration_id,
                user_id=current_user.id
            ).first()
            
            if not migration:
                return jsonify({'error': 'Migration not found'}), 404
            
            # Calculate progress based on status
            progress = 100 if migration.status == 'completed' else (
                75 if migration.status == 'in_progress' else 0)
            
            return jsonify({
                'status': migration.status,
                'progress': progress,
                'block_count': migration.block_count or 0,
                'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
                'error_message': migration.error_message
            })
            
        except ValueError:
            return jsonify({'error': 'Invalid job ID format'}), 400
            
    except Exception as e:
        current_app.logger.error(f"Error checking migration progress: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def run_migration_task(**kwargs):
    """Run migration with its own Flask application context"""
    from app import db, create_app
    from app.models import Migration

    app = create_app(start_scheduler=False) # <--- create a fresh Flask app instance
    with app.app_context():  # <--- now you have an active app context
        print("Starting migration task", kwargs)
        migration_id = kwargs.get('migration_id')
        print("Migration ID:", migration_id)
        
        try:
            migration = Migration.query.get(migration_id)
            if not migration:
                print("Migration record not found")
                return {'status': 'failed', 'error': 'Migration record not found'}
            
            # Update status to in_progress
            migration.status = 'in_progress'
            db.session.commit()
            
            # Perform the migration
            try:
                dict_QTP, dict_safal, listblock = excel_to_Dict(kwargs['filepath'])
                
                # Create output files
                for idlist in listblock:
                    output_path = os.path.join(
                        kwargs['output_folder'], 
                        f'{idlist}_Dictionary.xlsx'
                    )
                    with pd.ExcelWriter(output_path) as writer:
                        dict_QTP[idlist].to_excel(writer, sheet_name='QTP', index=False)
                        dict_safal[idlist].to_excel(writer, sheet_name='Safal', index=False)
                
                # Update status to completed
                migration.status = 'completed'
                migration.completed_at = datetime.utcnow()
                migration.block_count = len(listblock)
                db.session.commit()
                
                print("Migration completed successfully")
                return {
                    'status': 'completed',
                    'block_count': len(listblock),
                    'output_folder': kwargs['output_folder']
                }
                
            except Exception as e:
                print(f"Migration failed: {str(e)}")
                migration.status = 'failed'
                migration.error_message = str(e)
                db.session.commit()
                return {
                    'status': 'failed',
                    'error': str(e)
                }
                
        except Exception as e:
            print(f"Database error: {str(e)}")
            return {
                'status': 'failed',
                'error': f"Database error: {str(e)}"
            }


#migrations crud
@main_bp.route('/api/migrations', methods=['GET'])
@login_required
def get_migrations():
    migrations = Migration.query.filter_by(user_id=current_user.id).all()
    migration_list = []
    
    for migration in migrations:
        migration_list.append({
            'id': migration.id,
            'source_file': migration.source_file,
            'target_file': migration.target_file,
            'status': migration.status,
            'created_at': migration.created_at.isoformat(),
            'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
            'block_count': migration.block_count or 0,
            'error_message': migration.error_message
        })
    
    return jsonify(migration_list), 200

@main_bp.route('/api/migration/<int:migration_id>', methods=['GET'])
@login_required
def get_migration(migration_id):
    migration = Migration.query.filter_by(id=migration_id, user_id=current_user.id).first()
    
    if not migration:
        return jsonify({'error': 'Migration not found'}), 404
    
    migration_data = {
        'id': migration.id,
        'source_file': migration.source_file,
        'target_file': migration.target_file,
        'status': migration.status,
        'created_at': migration.created_at.isoformat(),
        'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
        'block_count': migration.block_count or 0,
        'error_message': migration.error_message
    }
    
    return jsonify(migration_data), 200

@main_bp.route('/api/migration/<int:migration_id>', methods=['DELETE'])
@login_required
def delete_migration(migration_id):
    migration = Migration.query.filter_by(id=migration_id, user_id=current_user.id).first()
    
    if not migration:
        return jsonify({'error': 'Migration not found'}), 404
    
    try:
        db.session.delete(migration)
        db.session.commit()
        return jsonify({'message': 'Migration deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    

@main_bp.route('/api/migration/<int:migration_id>/download', methods=['GET'])
@login_required
def download_migration(migration_id):
    migration = Migration.query.filter_by(id=migration_id, user_id=current_user.id).first()
    
    if not migration:
        return jsonify({'error': 'Migration not found'}), 404
    
    output_folder = output_folder = os.path.join(current_app.config['MIGRATION_FOLDER'], 
                               f'user_{current_user.id}')
    if not os.path.exists(output_folder):
        return jsonify({'error': 'Output folder not found'}), 404
    
    # Combine all the Excel files into one Excel file
    combined_excel_path = os.path.join(output_folder, f'output', f'migration_{migration.id}.xlsx')
    os.makedirs(os.path.dirname(combined_excel_path), exist_ok=True)
    with pd.ExcelWriter(combined_excel_path) as writer:
        for idlist in os.listdir(output_folder):
            if idlist.endswith('_Dictionary.xlsx'):
                file_path = os.path.join(output_folder, idlist)
                sheet_name = os.path.splitext(idlist)[0]
                data = pd.read_excel(file_path, sheet_name=None)  # Read all sheets
                for sheet, df in data.items():
                    df.to_excel(writer, sheet_name=f"{sheet_name}_{sheet}", index=False)
    
    zip_filename = f"migration_{migration.id}.zip"
    zip_filepath = os.path.join(output_folder, f'output', zip_filename)
    os.makedirs(os.path.dirname(zip_filepath), exist_ok=True)
    download_folder = os.path.join(current_app.config['MIGRATION_FOLDER'], 
                               f'user_{current_user.id}', 
                               f'migration_{migration.id}')
    if not os.path.exists(download_folder):
        return jsonify({'error': 'Download folder not found'}), 404
    # Create a zip file of the output folder
    shutil.make_archive(zip_filepath.replace('.zip', ''), 'zip', download_folder)
    
    return send_file(zip_filepath, as_attachment=True, download_name=zip_filename)

