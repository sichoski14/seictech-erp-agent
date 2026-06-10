import os
from datetime import datetime

class Config:
    # Database
    DATABASE_PATH = 'retail_analytics.db'
    
    # ERP API Configuration
    ERP_API_URL = os.getenv('ERP_API_URL', 'https://api.erp.com/v1')
    ERP_API_KEY = os.getenv('ERP_API_KEY', 'your_api_key')
    
    # Email Configuration
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USER = os.getenv('SMTP_USER', 'your_email@gmail.com')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'your_password')
    
    # Power BI Configuration
    POWER_BI_WORKSPACE_ID = os.getenv('POWER_BI_WORKSPACE_ID', 'workspace_id')
    POWER_BI_DATASET_ID = os.getenv('POWER_BI_DATASET_ID', 'dataset_id')
    
    # ML Model Configuration
    MODEL_PATH = 'ml_models/trained_models/'
    
    # Agent Configuration
    UPDATE_INTERVAL = 300  # 5 minutes
    ALERT_THRESHOLD = 0.8  # 80% stock level