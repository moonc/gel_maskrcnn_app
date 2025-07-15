import json
import re
from pathlib import Path

class ResultParser:
    def __init__(self):
        pass
    
    def parse_nextflow_log(self, log_content):
        """Parse Nextflow log for progress information"""
        progress_info = {
            'completed_processes': 0,
            'total_processes': 0,
            'current_process': None,
            'errors': []
        }
        
        lines = log_content.split('\n')
        for line in lines:
            # Look for process completion patterns
            if '|' in line and 'of' in line:
                # Example: [ab/123456] PROCESS_NAME (1) | 1 of 1 ✓
                match = re.search(r'\|\s*(\d+)\s*of\s*(\d+)', line)
                if match:
                    completed = int(match.group(1))
                    total = int(match.group(2))
                    progress_info['completed_processes'] += completed
                    progress_info['total_processes'] += total
            
            # Look for current process
            if 'process >' in line:
                match = re.search(r'process > (\w+)', line)
                if match:
                    progress_info['current_process'] = match.group(1)
            
            # Look for errors
            if 'ERROR' in line:
                progress_info['errors'].append(line.strip())
        
        return progress_info
    
    def parse_results_file(self, results_file_path):
        """Parse test results file"""
        results = {}
        
        try:
            with open(results_file_path, 'r') as f:
                content = f.read()
                
                # Extract key information
                for line in content.split('\n'):
                    if 'Detected objects:' in line:
                        results['detected_objects'] = int(line.split(':')[1].strip())
                    elif 'Input image:' in line:
                        results['input_image'] = line.split(':', 1)[1].strip()
                    elif 'Processing time:' in line:
                        results['processing_time'] = line.split(':', 1)[1].strip()
                        
        except Exception as e:
            results['error'] = str(e)
        
        return results