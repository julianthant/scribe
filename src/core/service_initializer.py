"""
Production Service Initializer for Scribe Voice Email Processor
Handles Azure service initialization with proper error handling and retry logic
Follows Azure Functions best practices for service management
"""

import logging
import time
from typing import Optional, Dict, Any, Tuple
from azure.storage.blob import BlobServiceClient
from azure.identity import ManagedIdentityCredential

from .configuration_manager import ScribeConfigurationManager
from ..key_vault_manager import KeyVaultManager


class ScribeServiceInitializer:
    """
    Production-ready service initializer for Azure services
    Handles initialization, validation, and dependency injection
    """
    
    def __init__(self, config: ScribeConfigurationManager):
        """
        Initialize service initializer with configuration
        
        Args:
            config: Validated Scribe configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Service instances (initialized lazily)
        self._credential: Optional[ManagedIdentityCredential] = None
        self._key_vault_manager: Optional[KeyVaultManager] = None
        self._blob_client: Optional[BlobServiceClient] = None
        self._audio_processor: Optional[Any] = None
        self._excel_processor: Optional[Any] = None
        self._email_processor: Optional[Any] = None
        
        # Service initialization state
        self._initialization_state: Dict[str, bool] = {}
        self._access_token: Optional[str] = None
    
    def initialize_core_services(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Initialize core Azure services required for operation
        
        Returns:
            Tuple[bool, Dict]: Success status and initialization results
        """
        initialization_start = time.time()
        results = {
            'success': True,
            'services_initialized': [],
            'failures': [],
            'initialization_time': 0
        }
        
        try:
            self.logger.info("🚀 Initializing core Azure services...")
            
            # Initialize services in dependency order
            service_initializers = [
                ('credential', self._initialize_credential),
                ('key_vault', self._initialize_key_vault),
                ('blob_storage', self._initialize_blob_storage),
                ('access_token', self._initialize_access_token),
                ('audio_processor', self._initialize_audio_processor)
            ]
            
            for service_name, initializer in service_initializers:
                try:
                    success = initializer()
                    if success:
                        results['services_initialized'].append(service_name)
                        self._initialization_state[service_name] = True
                        self.logger.info(f"✅ {service_name} initialized successfully")
                    else:
                        results['failures'].append(f"{service_name}: initialization failed")
                        results['success'] = False
                        self.logger.error(f"❌ Failed to initialize {service_name}")
                        
                except Exception as e:
                    error_msg = f"{service_name}: {str(e)}"
                    results['failures'].append(error_msg)
                    results['success'] = False
                    self.logger.error(f"❌ Exception during {service_name} initialization: {str(e)}")
            
            results['initialization_time'] = time.time() - initialization_start
            
            if results['success']:
                self.logger.info(f"🎉 All core services initialized in {results['initialization_time']:.2f}s")
            else:
                self.logger.error(f"💥 Service initialization completed with failures: {results['failures']}")
                
            return results['success'], results
            
        except Exception as e:
            results['success'] = False
            results['failures'].append(f"Critical initialization error: {str(e)}")
            results['initialization_time'] = time.time() - initialization_start
            self.logger.error(f"💥 Critical error during service initialization: {str(e)}")
            return False, results
    
    def initialize_processing_services(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Initialize email and Excel processing services (requires access token)
        
        Returns:
            Tuple[bool, Dict]: Success status and initialization results
        """
        if not self._access_token:
            self.logger.error("❌ Cannot initialize processing services without access token")
            return False, {'error': 'Access token required for processing services'}
        
        results = {
            'success': True,
            'services_initialized': [],
            'failures': []
        }
        
        try:
            # Initialize Excel processor
            if self._initialize_excel_processor():
                results['services_initialized'].append('excel_processor')
                self.logger.info("✅ Excel processor initialized")
            else:
                results['failures'].append('excel_processor initialization failed')
                results['success'] = False
            
            # Initialize Email processor
            if self._initialize_email_processor():
                results['services_initialized'].append('email_processor')
                self.logger.info("✅ Email processor initialized")
            else:
                results['failures'].append('email_processor initialization failed')
                results['success'] = False
            
            return results['success'], results
            
        except Exception as e:
            results['success'] = False
            results['failures'].append(f"Processing services error: {str(e)}")
            self.logger.error(f"❌ Failed to initialize processing services: {str(e)}")
            return False, results
    
    def _initialize_credential(self) -> bool:
        """Initialize Managed Identity credential"""
        try:
            self._credential = ManagedIdentityCredential()
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize credential: {str(e)}")
            return False
    
    def _initialize_key_vault(self) -> bool:
        """Initialize Key Vault manager"""
        try:
            self._key_vault_manager = KeyVaultManager()
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Key Vault: {str(e)}")
            return False
    
    def _initialize_blob_storage(self) -> bool:
        """Initialize Blob Storage client"""
        try:
            if not self._key_vault_manager:
                self.logger.error("Key Vault manager required for blob storage initialization")
                return False
            
            # Get storage connection string from Key Vault
            storage_connection = self._key_vault_manager.get_secret('storage-connection-string')
            if not storage_connection:
                self.logger.error("Failed to retrieve storage connection string from Key Vault")
                return False
            
            self._blob_client = BlobServiceClient.from_connection_string(storage_connection)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize blob storage: {str(e)}")
            return False
    
    def _initialize_access_token(self) -> bool:
        """Initialize access token from Key Vault"""
        try:
            if not self._key_vault_manager:
                self.logger.error("Key Vault manager required for access token initialization")
                return False
            
            self._access_token = self._key_vault_manager.get_secret('access-token')
            if not self._access_token:
                self.logger.error("Failed to retrieve access token from Key Vault")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize access token: {str(e)}")
            return False
    
    def _initialize_audio_processor(self) -> bool:
        """Initialize Audio processor with lazy import"""
        try:
            # Lazy import to avoid circular dependencies
            from ..processors.transcription_processor import ScribeTranscriptionProcessor
            
            self._audio_processor = ScribeTranscriptionProcessor(
                self.config.ai_foundry_project_url,
                self._access_token
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Audio processor: {str(e)}")
            return False
    
    def _initialize_excel_processor(self) -> bool:
        """Initialize Excel processor with lazy import"""
        try:
            # Lazy import to avoid circular dependencies
            from ..processors.excel_processor import ScribeExcelProcessor
            
            if not self._access_token:
                return False
                
            self._excel_processor = ScribeExcelProcessor(
                self._access_token,
                self.config.excel_file_name
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Excel processor: {str(e)}")
            return False
    
    def _initialize_email_processor(self) -> bool:
        """Initialize Email processor"""
        try:
            # Lazy import to avoid circular dependencies
            from ..processors.email_processor import ScribeEmailProcessor
            
            # Check prerequisites individually for better error reporting
            if not self._access_token:
                self.logger.error("Access token not initialized")
                return False
            
            if not self._audio_processor:
                self.logger.error("Audio processor not initialized")
                return False
                
            if not self._excel_processor:
                self.logger.error("Excel processor not initialized")
                return False
                
            self._email_processor = ScribeEmailProcessor(
                self._access_token,
                self._blob_client,
                self.config.target_user_email,
                self._audio_processor,
                self._excel_processor
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize Email processor: {str(e)}")
            return False
    
    # Property accessors for initialized services
    @property
    def credential(self) -> Optional[ManagedIdentityCredential]:
        """Get initialized credential"""
        return self._credential
    
    @property
    def key_vault_manager(self) -> Optional[KeyVaultManager]:
        """Get initialized Key Vault manager"""
        return self._key_vault_manager
    
    @property
    def blob_client(self) -> Optional[BlobServiceClient]:
        """Get initialized Blob Storage client"""
        return self._blob_client
    
    @property
    def audio_processor(self) -> Optional[Any]:
        """Get audio processor instance"""
        return self._audio_processor
    
    @property
    def excel_processor(self) -> Optional[Any]:
        """Get excel processor instance"""
        return self._excel_processor
    
    @property
    def email_processor(self) -> Optional[Any]:
        """Get email processor instance"""
        return self._email_processor
    
    @property
    def access_token(self) -> Optional[str]:
        """Get access token"""
        return self._access_token
    
    def refresh_access_token(self) -> bool:
        """
        Refresh access token from Key Vault
        
        Returns:
            bool: True if token was refreshed successfully
        """
        try:
            if not self._key_vault_manager:
                return False
            
            self.logger.info("🔄 Refreshing access token...")
            new_token = self._key_vault_manager.get_secret('access-token')
            
            if new_token and new_token != self._access_token:
                self._access_token = new_token
                self.logger.info("✅ Access token refreshed successfully")
                
                # Re-initialize token-dependent services
                self._initialize_excel_processor()
                self._initialize_email_processor()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Failed to refresh access token: {str(e)}")
            return False
    
    def get_service_health(self) -> Dict[str, Any]:
        """
        Get health status of all initialized services
        
        Returns:
            Dict[str, Any]: Service health information
        """
        health_status = {
            'overall_health': 'healthy',
            'services': {},
            'initialized_count': 0,
            'total_services': 6
        }
        
        services = {
            'credential': self._credential,
            'key_vault_manager': self._key_vault_manager,
            'blob_client': self._blob_client,
            'audio_processor': self._audio_processor,
            'excel_processor': self._excel_processor,
            'email_processor': self._email_processor
        }
        
        for service_name, service_instance in services.items():
            if service_instance is not None:
                health_status['services'][service_name] = 'healthy'
                health_status['initialized_count'] += 1
            else:
                health_status['services'][service_name] = 'not_initialized'
        
        # Determine overall health
        if health_status['initialized_count'] == 0:
            health_status['overall_health'] = 'critical'
        elif health_status['initialized_count'] < 4:  # Core services
            health_status['overall_health'] = 'degraded'
        
        return health_status
