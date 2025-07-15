import os
import subprocess
import json
import time
import uuid
from pathlib import Path
from datetime import datetime
import psutil
import threading

class NextflowPipelineManager:
    def __init__(self, pipeline_dir, results_dir='results', work_dir='work'):
        self.pipeline_dir = Path(pipeline_dir)
        self.results_dir = Path(results_dir)
        self.work_dir = Path(work_dir)
        self.running_jobs = {}
        
        # Validate pipeline directory
        if not self.pipeline_dir.exists():
            raise ValueError(f"Pipeline directory does not exist: {pipeline_dir}")
        
        if not (self.pipeline_dir / 'main.nf').exists():
            raise ValueError(f"main.nf not found in: {pipeline_dir}")
    
    def run_prediction(self, image_path, job_id=None, **kwargs):
        """Run Nextflow pipeline for single image prediction"""
    
        if job_id is None:
            job_id = str(uuid.uuid4())
    
        # Validate inputs
        if not os.path.exists(image_path):
            return job_id, {
                'job_id': job_id,
                'status': 'failed',
                'error': f'Input image not found: {image_path}',
                'start_time': datetime.now().isoformat()
            }
    
        # Check if model exists (for test mode)
        model_path = self.pipeline_dir / 'results' / 'models' / 'maskrcnn_gel_spots.pth'
        if not model_path.exists():
            return job_id, {
                'job_id': job_id,
                'status': 'failed',
                'error': f'Trained model not found: {model_path}. Please train the model first.',
                'start_time': datetime.now().isoformat()
            }
    
        # Prepare output directory
        output_dir = self.pipeline_dir / f'results_{job_id}'
        output_dir.mkdir(exist_ok=True)
    
        # Prepare command with low_memory profile included
        cmd = [
            'nextflow', 'run', str(self.pipeline_dir / 'main.nf'),
            '-profile', 'conda,low_memory,monitor',  # Added low_memory profile
            '--mode', 'test',
            '--test_image', os.path.abspath(image_path),
            '--outdir', str(output_dir),
            '--score_threshold', str(kwargs.get('score_threshold', 0.8)),
            '--mask_threshold', str(kwargs.get('mask_threshold', 0.8)),
            '--num_classes', str(kwargs.get('num_classes', 2)),
            '-with-trace', str(output_dir / 'trace.txt'),
            '-with-report', str(output_dir / 'report.html'),
            '-resume'
        ]
    
        # Rest of the method remains the same...
        job_info = {
            'job_id': job_id,
            'status': 'starting',
            'command': ' '.join(cmd),
            'start_time': datetime.now().isoformat(),
            'image_path': str(image_path),
            'results_dir': str(output_dir),
            'process': None,
            'progress': 0,
            'pipeline_dir': str(self.pipeline_dir)
        }
    
        try:
            print(f"[{job_id}] Starting Nextflow with low_memory profile:")
            print(f"[{job_id}] Command: {' '.join(cmd)}")
            print(f"[{job_id}] Working directory: {self.pipeline_dir}")
        
            # Start the process with proper environment
            env = os.environ.copy()
            env['NEXTFLOW_BIN_DIR'] = str(self.pipeline_dir / 'bin')
        
            process = subprocess.Popen(
                cmd,
                cwd=str(self.pipeline_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                env=env
            )
        
            job_info['process'] = process
            job_info['status'] = 'running'
            job_info['pid'] = process.pid
        
            self.running_jobs[job_id] = job_info
        
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitor_process,
                args=(job_id,),
                daemon=True
            )
            monitor_thread.start()
        
            print(f"[{job_id}] Job started with PID {process.pid} using low_memory profile")
            return job_id, job_info
        
        except Exception as e:
            error_msg = f"Failed to start Nextflow process: {str(e)}"
            print(f"[{job_id}] Error: {error_msg}")
        
            job_info['status'] = 'failed'
            job_info['error'] = error_msg
            job_info['end_time'] = datetime.now().isoformat()
            return job_id, job_info
    
    def _monitor_process(self, job_id):
        """Monitor process execution in background thread"""
        
        if job_id not in self.running_jobs:
            return
        
        job_info = self.running_jobs[job_id]
        process = job_info.get('process')
        
        if not process:
            return
        
        output_lines = []
        
        try:
            # Read output line by line
            for line in iter(process.stdout.readline, ''):
                if line:
                    output_lines.append(line.strip())
                    print(f"[{job_id}] {line.strip()}")
                    
                    # Update progress based on output
                    progress = self._parse_progress_from_output(line)
                    if progress > job_info.get('progress', 0):
                        job_info['progress'] = progress
                
                # Check if process finished
                if process.poll() is not None:
                    break
            
            # Process finished
            return_code = process.wait()
            job_info['return_code'] = return_code
            job_info['end_time'] = datetime.now().isoformat()
            job_info['stdout'] = '\n'.join(output_lines)
            
            if return_code == 0:
                job_info['status'] = 'completed'
                job_info['results'] = self._parse_results(job_id)
                print(f"[{job_id}] Job completed successfully")
            else:
                job_info['status'] = 'failed'
                job_info['error'] = f"Process exited with code {return_code}"
                print(f"[{job_id}] Job failed with exit code {return_code}")
                
        except Exception as e:
            job_info['status'] = 'failed'
            job_info['error'] = f"Monitoring error: {str(e)}"
            job_info['end_time'] = datetime.now().isoformat()
            print(f"[{job_id}] Monitoring error: {e}")
    
    def _parse_progress_from_output(self, line):
        """Parse progress from Nextflow output"""
        progress = 0
        
        if 'executor' in line.lower():
            progress = 10
        elif 'process' in line.lower() and 'running' in line.lower():
            progress = 30
        elif 'process' in line.lower() and 'completed' in line.lower():
            progress = 80
        elif 'workflow completed' in line.lower():
            progress = 100
        
        return progress
    
    def get_job_status(self, job_id):
        """Get current status of a job"""
        
        if job_id not in self.running_jobs:
            return {'status': 'not_found'}
        
        job_info = self.running_jobs[job_id]
        
        # Return a JSON-serializable copy
        return self._make_json_serializable(job_info)
    
    def _make_json_serializable(self, job_info):
        """Create a JSON-serializable copy of job_info"""
        
        serializable_info = {}
        
        for key, value in job_info.items():
            if key == 'process':
                continue  # Skip the Popen process object
            elif isinstance(value, (str, int, float, bool, list, dict)) or value is None:
                serializable_info[key] = value
            else:
                serializable_info[key] = str(value)
        
        return serializable_info
    
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
                results['prediction_images'] = [str(f.relative_to(results_dir.parent)) for f in prediction_files]
                
                # Parse results file
                results_file = predictions_dir / 'test_results.txt'
                if results_file.exists():
                    results['results_file'] = str(results_file)
                    
                    # Extract detected objects count
                    with open(results_file, 'r') as f:
                        content = f.read()
                        for line in content.split('\n'):
                            if 'Objects detected:' in line or 'Detected objects:' in line:
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
                except Exception:
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
                    try:
                        parent = psutil.Process(process.pid)
                        for child in parent.children(recursive=True):
                            child.kill()
                        parent.kill()
                    except psutil.NoSuchProcess:
                        pass
                
                job_info['status'] = 'cancelled'
                job_info['end_time'] = datetime.now().isoformat()
                return True
                
            except Exception as e:
                job_info['error'] = str(e)
                job_info['status'] = 'failed'
                return False
        
        return False
    
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