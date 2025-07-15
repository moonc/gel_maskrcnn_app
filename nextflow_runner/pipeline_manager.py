import os
import subprocess
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
import psutil
import copy

class NextflowPipelineManager:
    def __init__(self, pipeline_dir, results_dir='results', work_dir='work'):
        self.pipeline_dir = Path(pipeline_dir)
        self.results_dir = Path(results_dir)
        self.work_dir = Path(work_dir)
        self.running_jobs = {}
    
    def get_job_status(self, job_id):
        """Get current status of a job"""
        
        if job_id not in self.running_jobs:
            return {'status': 'not_found'}
        
        job_info = self.running_jobs[job_id]
        
        if job_info['status'] == 'running':
            process = job_info['process']
            
            # Check if process is still running
            if process and process.poll() is None:
                # Still running - try to get progress
                progress = self._estimate_progress(job_id)
                job_info['progress'] = progress
            else:
                # Process finished
                if process:
                    return_code = process.returncode
                    stdout, stderr = process.communicate()
                    
                    job_info['end_time'] = datetime.now().isoformat()
                    job_info['stdout'] = stdout
                    job_info['stderr'] = stderr
                    job_info['return_code'] = return_code
                    
                    if return_code == 0:
                        job_info['status'] = 'completed'
                        job_info['results'] = self._parse_results(job_id)
                    else:
                        job_info['status'] = 'failed'
                        job_info['error'] = stderr
                else:
                    job_info['status'] = 'failed'
                    job_info['error'] = 'Process object not found'
        
        # Return a JSON-serializable copy of job_info
        return self._make_json_serializable(job_info)
    
    def _make_json_serializable(self, job_info):
        """Create a JSON-serializable copy of job_info by excluding non-serializable objects"""
        
        # Create a deep copy to avoid modifying the original
        serializable_info = {}
        
        for key, value in job_info.items():
            # Exclude non-serializable objects
            if key == 'process':
                continue  # Skip the Popen process object
            elif isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                serializable_info[key] = value
            else:
                # Convert other objects to string representation
                serializable_info[key] = str(value)
        
        return serializable_info
    
    def _estimate_progress(self, job_id):
        """Estimate progress based on Nextflow output"""
        
        job_info = self.running_jobs[job_id]
        results_dir = Path(job_info['results_dir'])
        
        # Check for various progress indicators
        progress = 0
        
        try:
            # Check if model loading started (20%)
            if (results_dir / 'pipeline_info').exists():
                progress = 20
            
            # Check if prediction started (50%)
            predictions_dir = results_dir / 'predictions'
            if predictions_dir.exists():
                progress = 50
                
                # Check if prediction files exist (80%)
                prediction_files = list(predictions_dir.glob('prediction_*.png'))
                if prediction_files:
                    progress = 80
                    
                    # Check if results file exists (100%)
                    if (predictions_dir / 'test_results.txt').exists():
                        progress = 100
        except Exception as e:
            print(f"Error estimating progress: {e}")
            # Return current progress if error occurs
        
        return progress
    
    def _parse_results(self, job_id):
        """Parse results from completed job"""
        
        job_info = self.running_jobs[job_id]
        results_dir = Path(job_info['results_dir'])
        
        results = {
            'prediction_images': [],
            'results_file': None,
            'detected_objects': 0,
            'processing_time': None
        }
        
        try:
            # Find prediction images
            predictions_dir = results_dir / 'predictions'
            if predictions_dir.exists():
                prediction_files = list(predictions_dir.glob('prediction_*.png'))
                results['prediction_images'] = [str(f) for f in prediction_files]
                
                # Parse results file
                results_file = predictions_dir / 'test_results.txt'
                if results_file.exists():
                    results['results_file'] = str(results_file)
                    
                    # Extract detected objects count
                    with open(results_file, 'r') as f:
                        content = f.read()
                        if 'Detected objects:' in content:
                            for line in content.split('\n'):
                                if 'Detected objects:' in line:
                                    try:
                                        results['detected_objects'] = int(line.split(':')[1].strip())
                                    except (ValueError, IndexError):
                                        results['detected_objects'] = 0
                                    break
            
            # Calculate processing time
            if 'start_time' in job_info and 'end_time' in job_info:
                try:
                    start = datetime.fromisoformat(job_info['start_time'])
                    end = datetime.fromisoformat(job_info['end_time'])
                    duration = end - start
                    results['processing_time'] = str(duration)
                except Exception as e:
                    results['processing_time'] = 'Unknown'
            
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def cancel_job(self, job_id):
        """Cancel a running job"""
        
        if job_id not in self.running_jobs:
            return False
        
        job_info = self.running_jobs[job_id]
        
        if job_info['status'] == 'running' and job_info.get('process'):
            try:
                process = job_info['process']
                if process and process.poll() is None:
                    # Kill the process and its children
                    try:
                        parent = psutil.Process(process.pid)
                        for child in parent.children(recursive=True):
                            child.kill()
                        parent.kill()
                    except psutil.NoSuchProcess:
                        pass  # Process already terminated
                
                job_info['status'] = 'cancelled'
                job_info['end_time'] = datetime.now().isoformat()
                return True
                
            except Exception as e:
                job_info['error'] = str(e)
                job_info['status'] = 'failed'
                return False
        
        return False
    
    def cleanup_job(self, job_id):
        """Clean up job files and data"""
        
        if job_id in self.running_jobs:
            job_info = self.running_jobs[job_id]
            
            # Clean up results directory
            results_dir = Path(job_info['results_dir'])
            if results_dir.exists():
                import shutil
                try:
                    shutil.rmtree(results_dir)
                except Exception as e:
                    print(f"Error cleaning up results directory: {e}")
            
            # Remove from running jobs
            del self.running_jobs[job_id]
            
            return True
        
        return False
    
    def list_jobs(self):
        """List all jobs with JSON-serializable info"""
        jobs = {}
        for job_id, job_info in self.running_jobs.items():
            jobs[job_id] = self._make_json_serializable(job_info)
        return jobs
    
    def get_system_status(self):
        """Get system resource usage"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'active_jobs': len([j for j in self.running_jobs.values() if j['status'] == 'running'])
            }
        except Exception as e:
            return {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_usage': 0,
                'active_jobs': 0,
                'error': str(e)
            }
    def run_prediction(self, image_path, job_id=None, **kwargs):
        """Run Nextflow pipeline for single image prediction"""
    
        if job_id is None:
            job_id = str(uuid.uuid4())
    
        # Validate inputs first
        if not os.path.exists(image_path):
            return job_id, {
                'job_id': job_id,
                'status': 'failed',
                'error': f'Input image not found: {image_path}',
                'start_time': datetime.now().isoformat()
            }
    
        if not os.path.exists(self.pipeline_dir / 'main.nf'):
            return job_id, {
                'job_id': job_id,
                'status': 'failed',
                'error': f'Pipeline main.nf not found in: {self.pipeline_dir}',
                'start_time': datetime.now().isoformat()
            }
    
        # Check if nextflow is available
        try:
            subprocess.run(['nextflow', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return job_id, {
                'job_id': job_id,
                'status': 'failed',
                'error': f'Nextflow not available: {str(e)}',
                'start_time': datetime.now().isoformat()
            }
    
        # Prepare command
        cmd = [
            'nextflow', 'run', 'main.nf',
            '-profile', 'conda,monitor',
            '--mode', 'test',
            '--test_image', str(image_path),
            '--outdir', f'results_{job_id}',
            '--score_threshold', str(kwargs.get('score_threshold', 0.8)),
            '--mask_threshold', str(kwargs.get('mask_threshold', 0.8)),
            '--num_classes', str(kwargs.get('num_classes', 2))
        ]
    
        # Create job info
        job_info = {
            'job_id': job_id,
            'status': 'starting',
            'command': ' '.join(cmd),
            'start_time': datetime.now().isoformat(),
            'image_path': str(image_path),
            'results_dir': f'results_{job_id}',
            'process': None,
            'progress': 0,
            'pipeline_dir': str(self.pipeline_dir)
        }
    
        try:
            print(f"Starting Nextflow command: {' '.join(cmd)}")
            print(f"Working directory: {self.pipeline_dir}")
        
            # Start the process
            process = subprocess.Popen(
                cmd,
                cwd=self.pipeline_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
        
            job_info['process'] = process
            job_info['status'] = 'running'
            job_info['pid'] = process.pid
        
            self.running_jobs[job_id] = job_info
        
            print(f"Job {job_id} started with PID {process.pid}")
            return job_id, job_info
        
        except Exception as e:
            error_msg = f"Failed to start Nextflow process: {str(e)}"
            print(f"Error: {error_msg}")
        
            job_info['status'] = 'failed'
            job_info['error'] = error_msg
            job_info['end_time'] = datetime.now().isoformat()
            return job_id, job_info