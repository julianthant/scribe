"""
Scribe Configuration Management
Simple, clean configuration handling for all components
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ScribeConfig:
    """Configuration container for Scribe Voice Email Processor"""
    
    # OAuth and Microsoft Graph
    client_id: str
    tenant_id: str = "common"
    target_user_email: str = ""
    
    # Azure Storage
    storage_connection_string: str = ""
    storage_container: str = "voice-attachments"
    
    # Azure Speech Services
    speech_api_key: str = ""
    speech_region: str = "eastus"
    speech_endpoint: str = "https://eastus.stt.speech.microsoft.com"
    
    # OneDrive/Excel
    excel_file_name: str = "Scribe.xlsx"
    
    # Processing limits
    max_emails: int = 10
    days_back: int = 7
    max_file_size_mb: int = 50
    
    @classmethod
    def from_environment(cls) -> 'ScribeConfig':
        """Create configuration from environment variables"""
        config = cls(
            client_id=os.getenv('CLIENT_ID', os.getenv('MICROSOFT_GRAPH_CLIENT_ID', '')),
            tenant_id=os.getenv('TENANT_ID', os.getenv('MICROSOFT_GRAPH_TENANT_ID', 'common')),
            target_user_email=os.getenv('TARGET_USER_EMAIL', ''),
            storage_connection_string=os.getenv('AZURE_STORAGE_CONNECTION_STRING', ''),
            storage_container=os.getenv('AZURE_STORAGE_CONTAINER_NAME', 'voice-attachments'),
            speech_api_key=os.getenv('AI_FOUNDRY_API_KEY', ''),
            speech_region=os.getenv('AZURE_AI_SERVICES_REGION', 'eastus'),
            speech_endpoint=os.getenv('AI_FOUNDRY_STT_ENDPOINT', 'https://eastus.stt.speech.microsoft.com'),
            excel_file_name=os.getenv('EXCEL_FILE_NAME', 'Scribe.xlsx'),
            max_emails=int(os.getenv('MAX_EMAILS', '10')),
            days_back=int(os.getenv('DAYS_BACK', '7')),
            max_file_size_mb=int(os.getenv('MAX_FILE_SIZE_MB', '50'))
        )
        
        logger.info(f"✅ Configuration loaded: {config.target_user_email}")
        return config
    
    def validate(self) -> bool:
        """Validate required configuration"""
        required_fields = [
            ('client_id', self.client_id),
            ('target_user_email', self.target_user_email),
            ('speech_api_key', self.speech_api_key),
            ('storage_connection_string', self.storage_connection_string)
        ]
        
        missing = [name for name, value in required_fields if not value]
        
        if missing:
            logger.error(f"❌ Missing required configuration: {missing}")
            return False
        
        logger.info("✅ Configuration validation passed")
        return True