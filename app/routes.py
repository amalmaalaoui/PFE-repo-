import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime
from app import app  # ✅ import the one created in __init__.py
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Dictionary to store migration jobs
migration_jobs = {}


app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}
app.secret_key = 'your-secret-key-here'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class ExcelFile:
    def __init__(self, id, filename, upload_date, size, sheet_count, sheet_names):
        self.id = id
        self.filename = filename
        self.upload_date = upload_date
        self.size = size
        self.sheet_count = sheet_count
        self.sheet_names = sheet_names

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/api/migration_status')
def migration_status():
    job_id = request.args.get('job_id')
    if not job_id or job_id not in migration_jobs:
        return jsonify({'error': 'Invalid job ID'}), 400
    
    return jsonify(migration_jobs[job_id])


def get_excel_files():
    files = []
    upload_dir = app.config['UPLOAD_FOLDER']
    
    for idx, filename in enumerate(os.listdir(upload_dir)):
        if filename.endswith(('.xlsx', '.xls')):
            filepath = os.path.join(upload_dir, filename)
            stat = os.stat(filepath)
            
            try:
                # Read Excel file to get sheet info
                xls = pd.ExcelFile(filepath)
                sheet_count = len(xls.sheet_names)
                sheet_names = xls.sheet_names
            except ValueError as ve:
                print(f"ValueError while reading {filename}: {ve}")
                sheet_count = 0
                sheet_names = []
            except Exception as e:
                print(f"Unexpected error while reading {filename}: {e}")
                sheet_count = 0
                sheet_names = []
            
            files.append(ExcelFile(
                id=idx,
                filename=filename,
                upload_date=datetime.fromtimestamp(stat.st_mtime),
                size=f"{stat.st_size / 1024:.1f} KB",
                sheet_count=sheet_count,
                sheet_names=sheet_names
            ))
    
    return files



@app.route('/workstation/migrator')
def migrator():
    files = get_excel_files()  # Reuse your existing function
    return render_template('workstation/migrator.html', files=files)

@app.route('/api/start_migration', methods=['POST'])
def start_migration():
    data = request.json
    file_id = data['file_id']
    schedule_time = data.get('schedule_time')
    email_notification = data.get('email_notification', False)
    generate_report = data.get('generate_report', False)
    ignore_errors = data.get('ignore_errors', False)
    
    files = get_excel_files()
    if file_id < 0 or file_id >= len(files):
        return jsonify({'error': 'Invalid file ID'}), 400
    
    selected_file = files[file_id]
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], selected_file.filename)
    
    if schedule_time:
        # Schedule the job
        run_date = datetime.strptime(schedule_time, '%Y-%m-%dT%H:%M')
        job = scheduler.add_job(
            run_migration,
            'date',
            run_date=run_date,
            args=[filepath, email_notification, generate_report, ignore_errors],
            id=f"migration_{file_id}_{datetime.now().timestamp()}"
        )
        migration_jobs[job.id] = {
            'status': 'scheduled',
            'start_time': run_date,
            'file': selected_file.filename,
            'countdown': (run_date - datetime.now()).total_seconds()
        }
        return jsonify({
            'message': 'Migration scheduled successfully',
            'job_id': job.id,
            'countdown': migration_jobs[job.id]['countdown']
        })
    else:
        # Run immediately
        results = run_migration(filepath, email_notification, generate_report, ignore_errors)
        return jsonify(results)

def run_migration(filepath, email_notification, generate_report, ignore_errors):
    try:
        # Run your migration functions
        #add to C:\Users\amalm\OneDrive\Documents\PFE\qtpmigratorpfe\ to path
      #  filepath = os.path.join(r"C:\Users\amalm\OneDrive\Documents\PFE\qtpmigratorpfe", filepath)
        filename = os.path.basename(filepath)
        print(f"Running migration for {filepath}...")

        dict_QTP, dict_safal, listblock = excel_to_Dict(filepath)
        savedicts(dict_QTP, dict_safal, listblock,filename )
        
        # Get the generated files
        results_dir = os.path.join(app.root_path.split('\\app')[0], 'results', filename)
        print(f"Results directory: {results_dir}")
        generated_files = []
        for filename in os.listdir(results_dir):
            if filename.endswith('_Dictionnary.xlsx'):
                filepath = os.path.join(results_dir, filename)
                df = pd.read_excel(filepath, sheet_name='QTP')
                generated_files.append({
                    'filename': filename,
                    'block_id': filename.split('_')[0],
                    'row_count': len(df),
                    'migrated': False
                })
        
        return {
            'status': 'completed',
            'block_count': len(generated_files),
            'generated_files': generated_files
        }
    except Exception as e:
        if ignore_errors:
            return {'status': 'completed_with_errors', 'error': str(e)}
        else:
            return {'status': 'failed', 'error': str(e)}
        
@app.route('/')
def dashboard():
    return render_template('dashboard.html',
        file_stats={
            'total_files': 42,
            'change_percent': 12.5,
            'total_sheets': 156
        },
        recent_activity={
            'count': 7,
            'last_action': "File 'migration_batch_3.xlsx' uploaded"
        },
        system_status={
            'healthy': True,
            'message': "All systems operational"
        },
        recent_files=[...],  # List of recent file objects
        migration_stats={
            'progress': 65,
            'completed': 23,
            'in_progress': 5,
            'pending': 12
        },
        system_health={
            'storage_used': 45,
            'memory_used': 62,
            'last_checked': "2 minutes ago"
        }
    )
@app.route('/workstation/manage_files')
def manage_files():
    files = get_excel_files()
    return render_template('workstation/manage_files.html', files=files)

@app.route('/workstation/manage_users')
def manage_users():
    return render_template('workstation/manage_users.html')

@app.route('/workstation/admin_files')
def admin_files():
    files = get_excel_files()
    return render_template('workstation/admin_files.html', files=files)


@app.route('/workstation/logs')
def logs():
    return render_template('workstation/logs.html')

@app.route('/workstation/migration_track')
def migration_track():
    return render_template('workstation/migration_track.html')

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('manage_files'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('manage_files'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash('File successfully uploaded', 'success')
    else:
        flash('Allowed file types are .xlsx, .xls', 'error')
    
    return redirect(url_for('manage_files'))

@app.route('/preview_file/<int:file_id>')
def preview_file(file_id):
    files = get_excel_files()
    if file_id < 0 or file_id >= len(files):
        return jsonify({'error': 'File not found'}), 404
    
    file = files[file_id]
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    
    try:
        # Read first sheet and get first 10 rows
        df = pd.read_excel(filepath, sheet_name=0, nrows=10)
        preview_html = df.to_html(classes='table-auto w-full', index=False)
        
        return jsonify({
            'filename': file.filename,
            'preview_html': preview_html
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_file/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    files = get_excel_files()
    if file_id < 0 or file_id >= len(files):
        return jsonify({'error': 'File not found'}), 404
    
    file = files[file_id]
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    
    try:
        os.remove(filepath)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add other routes for Configuration and Dictionary sections
@app.route('/configuration/system')
def system_config():
    return render_template('configuration/system.html')

@app.route('/configuration/account')
def account_config():
    return render_template('configuration/account.html')

@app.route('/dictionary/view')
def view_dictionaries():
    return render_template('dictionary/view.html')

@app.route('/dictionary/add')
def add_dictionary():
    return render_template('dictionary/add_dictionary.html')

@app.route('/dictionary/add_item')
def add_dictionary_item():
    return render_template('dictionary/add_item.html')


# Function to read an Excel file and save each sheet as a separate CSV file
def excel_to_Dict(excel_file):
    # Read the Excel file
    print(f'Processing file: {excel_file}')
    excel_data = pd.ExcelFile(excel_file)

    print(f'Excel file {excel_file} has {len(excel_data.sheet_names)} sheets.')
    
    # Ensure the output directory exists
    # os.makedirs(output_dir, exist_ok=True)

    # Iterate through each sheet and save as CSV
    table = []
    order = 0
    dict_QTP = {}
    dict_safal = {}

    for sheet_name in excel_data.sheet_names:
        df = excel_data.parse(sheet_name)

        if sheet_name == 'QTP':
            listblock = set(df['TestCaseID'].tolist())
            for listid in listblock:
                dfblock = df[df['TestCaseID'] == listid]
                if str(listid) == 'nan':
                    dict_QTP[0] = dfblock
                else:
                    dict_QTP[int(listid)] = dfblock

        if sheet_name == 'Safal':
            listblock1 = set(df['RowID'].tolist())
            for listid in listblock1:
                dfblock = df[df['RowID'] == listid]
                if str(listid) == 'nan':
                    dict_safal[0] = dfblock
                else:
                    dict_safal[int(listid)] = dfblock

            # Remove NaN values from the sets
            listblockint = {int(x) for x in listblock if pd.notna(x)}
            listblock1int = {int(x) for x in listblock1 if pd.notna(x)}

    for aint in listblockint:
        if aint not in listblock1int:
            print(f'Error: {aint} not in Safal sheet')
            return {}, {}, []

    return dict_QTP, dict_safal, listblockint


def savedicts(dict_QTP, dict_safal, list, folder):
    # Create a new directory for the results
    print(f'Creating directory: results/{folder}')
    os.makedirs('results', exist_ok=True)
    os.makedirs(f'results/{folder}', exist_ok=True)
    for idlist in list:
        dfqtp = dict_QTP.get(idlist)
        dfsafal = dict_safal.get(idlist)

        # Create a new Excel writer object
        os.makedirs('results', exist_ok=True)
        with pd.ExcelWriter(f'results/{folder}/{idlist}_Dictionnary.xlsx') as writer:
            # Write dfqtp to the first sheet
            dfqtp.to_excel(writer, sheet_name='QTP', index=False)
            # Write dfsafal to the second sheet
            dfsafal.to_excel(writer, sheet_name='Safal', index=False)
