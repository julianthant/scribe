"""
Production Configuration Manager for Scribe Voice Email Processor
Centralizes environment variable management and validation
Follows Azure Functions best practices for configuration handling
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ScribeConfiguration:
    """
    Data class to hold all Scribe configuration values
    Provides type safety and validation for environment variables
    """
    # Azure Authentication (required fields)
    azure_client_id: str
    azure_tenant_id: str
    key_vault_url: str
    
    # AI Foundry Configuration (required field)
    ai_foundry_project_url: str
    target_user_email: str
    
    # Optional fields with defaults
    ai_foundry_speech_endpoint: Optional[str] = None
    excel_file_name: str = 'Scribe.xlsx'
    azure_functions_environment: str = 'Development'
    
    # Performance Configuration
    max_concurrent_emails: int = 5
    audio_processing_timeout: int = 300  # 5 minutes
    api_retry_count: int = 3
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_required_fields()
        self._configure_derived_settings()
    
    def _validate_required_fields(self) -> None:
        """Validate that all required configuration fields are present"""
        required_fields = [
            ('azure_client_id', self.azure_client_id),
            ('azure_tenant_id', self.azure_tenant_id), 
            ('key_vault_url', self.key_vault_url),
            ('ai_foundry_project_url', self.ai_foundry_project_url),
            ('target_user_email', self.target_user_email)
        ]
        
        missing_fields = [name for name, value in required_fields if not value]
        if missing_fields:
            raise ValueError(f"Missing required configuration: {', '.join(missing_fields)}")
    
    def _configure_derived_settings(self) -> None:
        """Configure derived settings based on primary configuration"""
        if not self.ai_foundry_speech_endpoint:
            # Extract region from AI Foundry URL for Speech API endpoint
            if 'eastus.api.azureml.ms' in self.ai_foundry_project_url:
                self.ai_foundry_speech_endpoint = "https://eastus.api.cognitive.microsoft.com"
            else:
                self.ai_foundry_speech_endpoint = "https://eastus.api.cognitive.microsoft.com"  # Default


class ScribeConfigurationManager:
    """
    Production-ready configuration manager for Scribe application
    Handles environment variable loading, validation, and type conversion
    """
    
    def __init__(self):
        """Initialize configuration manager with logging"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._config: Optional[ScribeConfiguration] = None
    
    def get_configuration(self) -> ScribeConfiguration:
        """
        Get validated configuration instance
        Loads and validates environment variables on first call, then caches result
        
        Returns:
            ScribeConfiguration: Validated configuration object
            
        Raises:
            ValueError: If required environment variables are missing
        """
        if self._config is None:
            self._config = self._load_configuration()
        return self._config
    
    def _load_configuration(self) -> ScribeConfiguration:
        """
        Load configuration from environment variables with validation
        
        Returns:
            ScribeConfiguration: Populated and validated configuration
        """
        try:
            self.logger.info("🔧 Loading Scribe configuration from environment variables...")
            
            config = ScribeConfiguration(
                # Azure Authentication
                azure_client_id=self._get_required_env('CLIENT_ID'),  # Matches local.settings.json
                azure_tenant_id=self._get_required_env('TENANT_ID'),  # Matches local.settings.json  
                key_vault_url=self._get_required_env('KEY_VAULT_URL'),
                
                # AI Foundry Configuration
                ai_foundry_project_url=self._get_required_env('AI_FOUNDRY_PROJECT_URL'),
                ai_foundry_speech_endpoint=os.environ.get('AI_FOUNDRY_SPEECH_ENDPOINT'),
                
                # Application Configuration
                excel_file_name=os.environ.get('EXCEL_FILE_NAME', 'Scribe.xlsx'),
                target_user_email=self._get_required_env('TARGET_USER_EMAIL'),
                azure_functions_environment=os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT', 'Development'),
                
                # Performance Configuration
                max_concurrent_emails=self._get_int_env('MAX_CONCURRENT_EMAILS', 5),
                audio_processing_timeout=self._get_int_env('AUDIO_PROCESSING_TIMEOUT', 300),
                api_retry_count=self._get_int_env('API_RETRY_COUNT', 3)
            )
            
            self.logger.info("✅ Configuration loaded and validated successfully")
            self._log_configuration_summary(config)
            
            return config
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load configuration: {str(e)}")
            raise
    
    def _get_required_env(self, key: str) -> str:
        """
        Get required environment variable with validation
        
        Args:
            key: Environment variable name
            
        Returns:
            str: Environment variable value
            
        Raises:
            ValueError: If environment variable is missing or empty
        """
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Required environment variable '{key}' is missing or empty")
        return value
    
    def _get_int_env(self, key: str, default: int) -> int:
        """
        Get integer environment variable with default fallback
        
        Args:
            key: Environment variable name
            default: Default value if not set
            
        Returns:
            int: Environment variable value as integer
        """
        value = os.environ.get(key)
        if not value:
            return default
        
        try:
            return int(value)
        except ValueError:
            self.logger.warning(f"⚠️ Invalid integer value for {key}: {value}, using default: {default}")
            return default
    
    def _log_configuration_summary(self, config: ScribeConfiguration) -> None:
        """
        Log configuration summary for debugging (without sensitive values)
        
        Args:
            config: Configuration object to summarize
        """
        summary = {
            'environment': config.azure_functions_environment,
            'excel_file': config.excel_file_name,
            'target_email': config.target_user_email,
            'ai_foundry_endpoint': config.ai_foundry_speech_endpoint,
            'max_concurrent_emails': config.max_concurrent_emails,
            'audio_timeout': config.audio_processing_timeout,
            'retry_count': config.api_retry_count
        }
        
        self.logger.info(f"📋 Configuration Summary: {summary}")
    
    def validate_runtime_environment(self) -> Dict[str, Any]:
        """
        Validate that the runtime environment is properly configured
        
        Returns:
            Dict[str, Any]: Environment validation results
        """
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        try:
            config = self.get_configuration()
            
            # Check environment type
            if config.azure_functions_environment not in ['Development', 'Production']:
                validation_results['warnings'].append(
                    f"Unknown environment: {config.azure_functions_environment}"
                )
            
            # Validate URLs
            if not config.key_vault_url.startswith('https://'):
                validation_results['errors'].append("Key Vault URL must use HTTPS")
                validation_results['valid'] = False
            
            if not config.ai_foundry_project_url.startswith('https://'):
                validation_results['errors'].append("AI Foundry URL must use HTTPS")
                validation_results['valid'] = False
            
            # Check performance settings
            if config.max_concurrent_emails > 10:
                validation_results['warnings'].append(
                    f"High concurrent email count: {config.max_concurrent_emails}"
                )
            
            if config.audio_processing_timeout < 60:
                validation_results['warnings'].append(
                    f"Low audio processing timeout: {config.audio_processing_timeout}s"
                )
                
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Configuration validation failed: {str(e)}")
        
        return validation_results
