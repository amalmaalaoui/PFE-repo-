from sched import scheduler
import shutil
from flask import abort, current_app, request, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime
import os
import pandas as pd
from app.models import Migration, UserFile
from app import db, create_app
from . import admin_required, main_bp
from .helpers import excel_to_Dict
from enum import Enum
from app import scheduler  # Import from your package
from datetime import datetime, timezone
from pytz import timezone
tunis_tz = timezone('Africa/Tunis')
class MigrationStatus(str, Enum):
    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SCHEDULED = 'SCHEDULED'

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
            print("Scheduled time:", scheduled_time)
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
        'ignore_errors': data.get('ignore_errors', False),
        'scheduled_time': scheduled_time
    }
    
    if scheduled_time:
        try:
            # Schedule the job with kwargs only (no args)
            job = scheduler.add_job(
                    func=run_migration_task,  # String reference
                    trigger='date',
                    run_date=scheduled_time.astimezone(tunis_tz),  # Ensure scheduled_time is in Tunis timezone
                    kwargs=migration_data,
                    id=f"migration_{migration.id}",
                    replace_existing=True,
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
            progress = 100 if migration.status == 'COMPLETED' else (
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
    # Create a log file
    log_file_path = os.path.join(
        kwargs['output_folder'], 
        f"{kwargs['migration_id']}_migration.log"  )
    
    app = create_app(start_scheduler=False) # <--- create a fresh Flask app instance
    with app.app_context():  # <--- now you have an active app context
        print("Starting migration task", kwargs)
        migration_id = kwargs.get('migration_id')
        print("Migration ID:", migration_id)
        with open(log_file_path, 'w') as log_file:
            log_file.write(f"Starting migration task with ID: {migration_id}\n")
            log_file.write(f"Scheduled time: {kwargs['scheduled_time']}\n")
            log_file.write(f"Source file: {kwargs['filepath']}\n")
            log_file.write(f"Output folder: {kwargs['output_folder']}\n")
            log_file.write(f"Email notification: {kwargs['email_notification']}\n")
            log_file.write(f"Generate report: {kwargs['generate_report']}\n")
            log_file.write(f"Ignore errors: {kwargs['ignore_errors']}\n")
            log_file.write("Timestamp: {}\n".format(datetime.now(tunis_tz).isoformat()))
            log_file.write("Starting migration...\n")
        try:
            migration = Migration.query.get(migration_id)
            if not migration:
                print("Migration record not found")
                return {'status': 'failed', 'error': 'Migration record not found'}
            
            # Update status to in_progress
            migration.status = 'in_progress'
            db.session.commit()
          

            
            try:
                dict_QTP, dict_safal, listblock = excel_to_Dict(kwargs['filepath'])
                
                # Create output files for each block
                for idlist in listblock:
                    output_path = os.path.join(
                        kwargs['output_folder'], 
                        f'{idlist}_Dictionary.xlsx'
                    )
                    with pd.ExcelWriter(output_path) as writer:
                        dict_QTP[idlist].to_excel(writer, sheet_name='QTP', index=False)
                        dict_safal[idlist].to_excel(writer, sheet_name='Safal', index=False)
                        with open(log_file_path, 'w') as log_file:
                            log_file.write(f"Created file: {output_path}\n")
                

                # Create a consolidated Safal file
                safal_output_path = os.path.join(
                    kwargs['output_folder'], 
                    f"{kwargs['migration_id']}_safal.xlsx"
                )
                with open(log_file_path, 'w') as log_file:
                    log_file.write(f"Blocks files created successfully\n")
                    log_file.write(f"Starting creating consolidated Safal file: {safal_output_path}\n")
                
                    
                with pd.ExcelWriter(safal_output_path) as writer:
                    combined_safal = pd.concat([dict_safal[idlist] for idlist in listblock], ignore_index=True)
                    combined_safal.to_excel(writer, sheet_name='SAFAL', index=False)
                

                
                with open(log_file_path, 'w') as log_file:
                    log_file.write(f"Consolidated Safal file created successfully: {safal_output_path}\n")
                    log_file.write(f"Migration completed successfully\n")
                    log_file.write(f"Migration ID: {kwargs['migration_id']}\n")
                    log_file.write(f"Source File: {kwargs['filepath']}\n")
                    log_file.write(f"Output Folder: {kwargs['output_folder']}\n")
                    log_file.write(f"Blocks Processed: {len(listblock)}\n")
                    log_file.write("Blocks:\n")
                    for idlist in listblock:
                        log_file.write(f"  - Block ID: {idlist}\n")
                
                # Update migration record with file paths
                migration.result_file_path = safal_output_path
                migration.log_file_path = log_file_path
                db.session.commit()
                
                # Update status to completed
                migration.status = 'COMPLETED'
                migration.completed_at = datetime.utcnow()
                migration.block_count = len(listblock)
                db.session.commit()
                
                print("Migration completed successfully")
                return {
                    'status': 'COMPLETED',
                    'block_count': len(listblock),
                    'output_folder': kwargs['output_folder']
                }
                
            except Exception as e:
                print(f"Migration failed: {str(e)}")
                migration.status = 'failed'
                migration.error_message = str(e)
                with open(log_file_path, 'w') as log_file:
                    log_file.write(f"Migration failed: {str(e)}\n")
                    log_file.write(f"Error message: {str(e)}\n")
                    log_file.write(f"Migration ID: {kwargs['migration_id']}\n")
                    log_file.write(f"Source File: {kwargs['filepath']}\n")
                    log_file.write(f"Output Folder: {kwargs['output_folder']}\n")
                    log_file.write(f"Blocks Processed: {len(listblock)}\n")
                    log_file.write("Timestamp: {}\n".format(datetime.now(tunis_tz).isoformat()))
                db.session.commit()
                return {
                    'status': 'failed',
                    'error': str(e)
                }
                
        except Exception as e:
            print(f"Database error: {str(e)}")
            with open(log_file_path, 'w') as log_file:
                log_file.write(f"Database error: {str(e)}\n")
                log_file.write(f"Migration ID: {kwargs['migration_id']}\n")
                log_file.write(f"Source File: {kwargs['filepath']}\n")
                log_file.write(f"Output Folder: {kwargs['output_folder']}\n")
                log_file.write("Timestamp: {}\n".format(datetime.now(tunis_tz).isoformat()))
            return {
                'status': 'failed',
                'error': f"Database error: {str(e)}"
            }


#migrations crud
@main_bp.route('/api/migrationsdata')
@login_required
def get_migrationsdata():
    try:
        # Get optional status filter from request
        status_filter = request.args.get('status')
        # Base query
        query = Migration.query.filter_by(user_id=current_user.id)
        # Apply status filter if provided
        if status_filter:
            query = query.filter(Migration.status == status_filter)

        # Order by creation date
        query = query.order_by(Migration.created_at.desc())
        
        # Execute query
        migrations = query.all()
        
        # Prepare response data
        migrations_data = []
        for migration in migrations:
            migrations_data.append({
                'id': migration.id,
                'source_file': migration.source_file,
                'target_file': migration.target_file,
                'status': migration.status,
                'created_at': migration.created_at.isoformat() if migration.created_at else None,
                'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
                'block_count': migration.block_count,
                'error_message': migration.error_message,
            })
        print("migrations_data", migrations_data)
        return jsonify({
            'data': migrations_data,  # DataTables expects data in a 'data' property
            'status': 'success'
        })
        
    except Exception as e:
        print(f"Error fetching migrations: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@main_bp.before_request
def log_request():
    create_app().logger.debug(f"Request: {request.url}")

@main_bp.route('/api/migrationinfo/<int:migration_id>')
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
    

    
    zip_filename = f"migration_{migration.id}.zip"
    zip_filepath = os.path.join(output_folder, f'output', zip_filename)
    os.makedirs(os.path.dirname(zip_filepath), exist_ok=True)
    download_folder = os.path.join(current_app.config['MIGRATION_FOLDER'], 
                               f'user_{current_user.id}', 
                               f'migration_{migration.id}')
    if not os.path.exists(download_folder):
        return jsonify({'error': 'Download folder not found'}), 404

    # Ensure the parent directory of zip_filepath exists
    os.makedirs(os.path.dirname(zip_filepath), exist_ok=True)
    
    # Create a zip file of the output folder
    zip_absolute_path = shutil.make_archive(zip_filepath.replace('.zip', ''), 'zip', download_folder)
    current_app.logger.info(f"Created zip file at: {zip_absolute_path}")
    
    return send_file(zip_absolute_path, as_attachment=True, download_name=zip_filename)

@main_bp.route('/api/migration/<int:migration_id>/admin/download')
@login_required
@admin_required
def api_download_migration_results(migration_id):
    migration = Migration.query.get_or_404(migration_id)
    userid = migration.user_id
    
    if not migration:
        return jsonify({'error': 'Migration not found'}), 404
    
    output_folder = output_folder = os.path.join(current_app.config['MIGRATION_FOLDER'], f'user_{userid}')
    zip_filename = f"migration_{migration.id}.zip"
    zip_filepath = os.path.join(output_folder, f'output', zip_filename)

    if os.path.exists(zip_filepath):
        return send_file(zip_filepath, as_attachment=True, download_name=zip_filename)

        # Ensure the parent directory of zip_filepath exists
    os.makedirs(os.path.dirname(zip_filepath), exist_ok=True)

    if not os.path.exists(output_folder):
        return jsonify({'error': 'Output folder not found'}), 404
    

    
    
    os.makedirs(os.path.dirname(zip_filepath), exist_ok=True)
    download_folder = os.path.join(current_app.config['MIGRATION_FOLDER'], 
                               f'user_{userid}', 
                               f'migration_{migration.id}')
    if not os.path.exists(download_folder):
        return jsonify({'error': 'Download folder not found'}), 404


    
    # Create a zip file of the output folder
    zip_absolute_path = shutil.make_archive(zip_filepath.replace('.zip', ''), 'zip', download_folder)
    current_app.logger.info(f"Created zip file at: {zip_absolute_path}")
    
    return send_file(zip_absolute_path, as_attachment=True, download_name=zip_filename)