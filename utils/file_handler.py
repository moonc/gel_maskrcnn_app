import os
import shutil
from pathlib import Path
from werkzeug.utils import secure_filename

class FileHandler:
    def __init__(self, upload_folder):
        self.upload_folder = Path(upload_folder)
        self.upload_folder.mkdir(exist_ok=True)
    
    def save_file(self, file, filename=None):
        """Save uploaded file"""
        if filename is None:
            filename = secure_filename(file.filename)
        
        file_path = self.upload_folder / filename
        file.save(str(file_path))
        return str(file_path)
    
    def delete_file(self, filename):
        """Delete a file"""
        file_path = self.upload_folder / filename
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def cleanup_old_files(self, max_age_hours=24):
        """Clean up old uploaded files"""
        import time
        current_time = time.time()
        
        for file_path in self.upload_folder.iterdir():
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > (max_age_hours * 3600):
                    file_path.unlink()