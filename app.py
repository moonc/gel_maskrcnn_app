from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime

from config import config
from nextflow_runner.pipeline_manager import NextflowPipelineManager
from utils.file_handler import FileHandler
from utils.result_parser import ResultParser

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(config['development'])

@app.template_filter('basename')
def basename_filter(path):
    """Extract basename from file path"""
    return os.path.basename(path)

@app.template_filter('strptime')
def strptime_filter(date_string, format_string='%Y-%m-%dT%H:%M:%S.%f'):
    """Parse datetime string"""
    try:
        # Handle ISO format with or without microseconds
        if '.' in date_string:
            return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S.%f')
        else:
            return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        # Fallback for different formats
        try:
            return datetime.strptime(date_string, format_string)
        except ValueError:
            return datetime.now()  # Fallback to current time

@app.template_filter('strftime')
def strftime_filter(datetime_obj, format_string='%Y-%m-%d %H:%M:%S'):
    """Format datetime object"""
    if isinstance(datetime_obj, str):
        # If it's a string, parse it first
        datetime_obj = strptime_filter(datetime_obj)
    return datetime_obj.strftime(format_string)
# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize components
pipeline_manager = NextflowPipelineManager(
    pipeline_dir=app.config['NEXTFLOW_PIPELINE_DIR'],
    results_dir=app.config['NEXTFLOW_RESULTS_DIR'],
    work_dir=app.config['NEXTFLOW_WORK_DIR']
)

file_handler = FileHandler(app.config['UPLOAD_FOLDER'])
result_parser = ResultParser()

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    """Main upload page"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start prediction"""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Get prediction parameters
        score_threshold = float(request.form.get('score_threshold', 0.8))
        mask_threshold = float(request.form.get('mask_threshold', 0.8))
        
        # Start prediction job
        job_id, job_info = pipeline_manager.run_prediction(
            image_path=file_path,
            score_threshold=score_threshold,
            mask_threshold=mask_threshold,
            num_classes=app.config['NUM_CLASSES']
        )
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=monitor_job_progress,
            args=(job_id,)
        )
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return jsonify({
            'job_id': job_id,
            'status': 'started',
            'redirect_url': url_for('job_status', job_id=job_id)
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/status/<job_id>')
def job_status(job_id):
    """Job status page"""
    job_info = pipeline_manager.get_job_status(job_id)
    
    if job_info['status'] == 'not_found':
        return render_template('error.html', error='Job not found'), 404
    
    return render_template('status.html', job_id=job_id, job_info=job_info)

@app.route('/results/<job_id>')
def view_results(job_id):
    """Results display page"""
    job_info = pipeline_manager.get_job_status(job_id)
    
    if job_info['status'] == 'not_found':
        return render_template('error.html', error='Job not found'), 404
    
    if job_info['status'] != 'completed':
        return redirect(url_for('job_status', job_id=job_id))
    
    return render_template('results.html', job_id=job_id, job_info=job_info)

@app.route('/api/job/<job_id>/status')
def api_job_status(job_id):
    """API endpoint for job status"""
    try:
        job_info = pipeline_manager.get_job_status(job_id)
        return jsonify(job_info)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'job_id': job_id
        }), 500

@app.route('/api/job/<job_id>/cancel', methods=['POST'])
def api_cancel_job(job_id):
    """API endpoint to cancel job"""
    try:
        success = pipeline_manager.cancel_job(job_id)
        return jsonify({'success': success, 'job_id': job_id})
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e),
            'job_id': job_id
        }), 500

@app.route('/api/system/status')
def api_system_status():
    """API endpoint for system status"""
    try:
        status = pipeline_manager.get_system_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_usage': 0,
            'active_jobs': 0,
            'error': str(e)
        }), 500

@app.route('/download/<job_id>/<filename>')
def download_result(job_id, filename):
    """Download result files"""
    job_info = pipeline_manager.get_job_status(job_id)
    
    if job_info['status'] != 'completed':
        return jsonify({'error': 'Job not completed'}), 400
    
    file_path = Path(job_info['results_dir']) / 'predictions' / filename
    
    if file_path.exists():
        return send_file(str(file_path), as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/debug/job/<job_id>')
def debug_job(job_id):
    """Debug endpoint to see full job details"""
    if job_id not in pipeline_manager.running_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job_info = pipeline_manager.running_jobs[job_id]
    
    debug_info = {
        'job_id': job_id,
        'status': job_info.get('status'),
        'command': job_info.get('command'),
        'pipeline_dir': job_info.get('pipeline_dir'),
        'image_path': job_info.get('image_path'),
        'results_dir': job_info.get('results_dir'),
        'error': job_info.get('error'),
        'stdout': job_info.get('stdout'),
        'stderr': job_info.get('stderr'),
        'return_code': job_info.get('return_code'),
        'start_time': job_info.get('start_time'),
        'end_time': job_info.get('end_time')
    }
    
    return jsonify(debug_info)

@app.route('/debug/system')
def debug_system():
    """Debug system configuration"""
    import shutil
    
    debug_info = {
        'nextflow_available': shutil.which('nextflow') is not None,
        'nextflow_path': shutil.which('nextflow'),
        'pipeline_dir': app.config['NEXTFLOW_PIPELINE_DIR'],
        'pipeline_dir_exists': os.path.exists(app.config['NEXTFLOW_PIPELINE_DIR']),
        'main_nf_exists': os.path.exists(os.path.join(app.config['NEXTFLOW_PIPELINE_DIR'], 'main.nf')),
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'upload_folder_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
        'current_working_dir': os.getcwd(),
        'python_path': sys.executable
    }
    
    return jsonify(debug_info)

def monitor_job_progress(job_id):
    """Monitor job progress and emit updates via SocketIO"""
    
    while True:
        job_info = pipeline_manager.get_job_status(job_id)
        
        # Emit progress update
        socketio.emit('job_progress', {
            'job_id': job_id,
            'status': job_info['status'],
            'progress': job_info.get('progress', 0)
        })
        
        # Stop monitoring if job is finished
        if job_info['status'] in ['completed', 'failed', 'cancelled']:
            break
        
        time.sleep(2)  # Update every 2 seconds

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_job')
def handle_join_job(data):
    """Join a job room for updates"""
    job_id = data['job_id']
    # Join room for this specific job
    # (implement room joining if needed)
    emit('joined', {'job_id': job_id})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)