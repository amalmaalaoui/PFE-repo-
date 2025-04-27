from datetime import datetime
import os
import pandas as pd
from app.models import Migration
from app import db
from app.routes.helpers import excel_to_Dict

def run_migration_task(app, **kwargs):
    """Run migration with proper Flask application context"""
    with app.app_context():
        print("Starting migration task", kwargs)
        migration_id = kwargs.get('migration_id')
        print("Migration ID:", migration_id)
        
        try:
            migration = Migration.query.get(migration_id)
            if not migration:
                print("Migration record not found")
                return {'status': 'failed', 'error': 'Migration record not found'}
            
            migration.status = 'in_progress'
            db.session.commit()
            
            try:
                dict_QTP, dict_safal, listblock = excel_to_Dict(kwargs['filepath'])
                
                for idlist in listblock:
                    output_path = os.path.join(
                        kwargs['output_folder'], 
                        f'{idlist}_Dictionary.xlsx'
                    )
                    with pd.ExcelWriter(output_path) as writer:
                        dict_QTP[idlist].to_excel(writer, sheet_name='QTP', index=False)
                        dict_safal[idlist].to_excel(writer, sheet_name='Safal', index=False)
                
                migration.status = 'COMPLETED'
                migration.completed_at = datetime.utcnow()
                migration.block_count = len(listblock)
                db.session.commit()
                
                print("Migration COMPLETED successfully")
                return {
                    'status': 'COMPLETED',
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