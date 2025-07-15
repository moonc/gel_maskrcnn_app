# config.py (updated)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # File upload settings
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}
    
    # Nextflow pipeline settings
    NEXTFLOW_PIPELINE_DIR = os.environ.get('NEXTFLOW_PIPELINE_DIR') or '/home/moon/mask_rcnn_gel'
    NEXTFLOW_RESULTS_DIR = 'results'
    NEXTFLOW_WORK_DIR = 'work'
    
    # Model settings
    MODEL_PATH = 'results/models/maskrcnn_gel_spots.pth'
    SCORE_THRESHOLD = 0.8
    MASK_THRESHOLD = 0.8
    NUM_CLASSES = 2
    
    # Redis settings (optional - for job queue)
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}