"""
Authentication Manager - Factory and orchestration for authentication providers
Implements Factory pattern for provider creation and management
Production-ready implementation with proper error handling and thread safety
"""

import os
import logging
import threading
from typing import Optional, Dict, Any
from enum import Enum
import requests

from .auth_providers import (
    AuthProvider, 
    CertificateAuthProvider, 
    OAuthProvider,
    KeyVaultTokenStorage,
    EnvironmentTokenStorage,
    FileTokenStorage
)

logger = logging.getLogger(__name__)


class AuthMethod(Enum):
    """Supported authentication methods"""
    CERTIFICATE = "certificate"
    PERSONAL_OAUTH = "personal_oauth"


class AuthProviderFactory:
    """Factory for creating authentication providers"""
    
    @staticmethod
    def create_provider(auth_method: AuthMethod) -> Optional[AuthProvider]:
        """Create authentication provider based on method"""
        
        if auth_method == AuthMethod.CERTIFICATE:
            return CertificateAuthProvider()
        
        elif auth_method == AuthMethod.PERSONAL_OAUTH:
            # Determine storage strategy based on environment
            storage_strategy = AuthProviderFactory._create_storage_strategy()
            return OAuthProvider(storage_strategy)
        
        else:
            logger.error(f"Unsupported authentication method: {auth_method}")
            return None
    
    @staticmethod
    def _create_storage_strategy():
        """Create appropriate token storage strategy based on environment"""
        # Priority order: Key Vault -> Environment -> File
        if os.getenv('KEY_VAULT_URL'):
            logger.info("🔐 Using Key Vault token storage strategy")
            return KeyVaultTokenStorage()
        elif os.getenv('OAUTH_REFRESH_TOKEN'):
            logger.info("🔐 Using environment variable token storage strategy")
            return EnvironmentTokenStorage()
        else:
            logger.info("🔐 Using file-based token storage strategy (development)")
            return FileTokenStorage()


class AuthManager:
    """
    Main authentication manager with thread-safe singleton pattern
    Provides unified interface for all authentication methods
    """
    
    _instance = None
    _lock = threading.RLock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self.provider: Optional[AuthProvider] = None
                    self.auth_method: Optional[AuthMethod] = None
                    self._provider_lock = threading.RLock()
                    self._initialized = True
    
    def initialize(self, auth_method: Optional[str] = None) -> bool:
        """
        Initialize authentication with specified or auto-detected method
        
        Args:
            auth_method: Override auth method ('certificate' or 'personal_oauth')
            
        Returns:
            bool: True if initialization successful
        """
        with self._provider_lock:
            # Determine authentication method
            method_str = auth_method or os.getenv('AUTH_METHOD', 'certificate').lower()
            
            try:
                if method_str == 'personal_oauth':
                    self.auth_method = AuthMethod.PERSONAL_OAUTH
                else:
                    self.auth_method = AuthMethod.CERTIFICATE
                
                logger.info(f"🔐 Initializing authentication with method: {self.auth_method.value}")
                
                # Create provider using factory
                self.provider = AuthProviderFactory.create_provider(self.auth_method)
                
                if not self.provider:
                    logger.error("❌ Failed to create authentication provider")
                    return False
                
                # Initialize the provider
                if not self.provider.initialize():
                    logger.error("❌ Failed to initialize authentication provider")
                    self.provider = None
                    return False
                
                logger.info(f"✅ Authentication initialized with method: {self.auth_method.value}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Authentication initialization failed: {e}")
                self.provider = None
                return False
    
    def get_access_token(self) -> Optional[str]:
        """
        Get access token from current provider
        Thread-safe access with provider validation
        """
        with self._provider_lock:
            if not self.provider:
                logger.error("❌ Authentication not initialized")
                return None
            return self.provider.get_access_token()
    
    def make_graph_request(self, url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
        """
        Make Microsoft Graph API request
        
        Args:
            url: Graph API URL
            method: HTTP method (GET, POST, PATCH)
            data: Request data for POST/PATCH
            
        Returns:
            requests.Response or None if failed
        """
        with self._provider_lock:
            if not self.provider:
                logger.error("❌ Authentication not initialized")
                return None
            return self.provider.make_graph_request(url, method, data)
    
    def test_authentication(self) -> Dict[str, Any]:
        """
        Test current authentication
        
        Returns:
            Dict with validation results and provider info
        """
        with self._provider_lock:
            if not self.provider:
                return {
                    'valid': False, 
                    'error': 'Authentication not initialized',
                    'method': 'none'
                }
            
            result = self.provider.test_authentication()
            result['method'] = self.auth_method.value if self.auth_method else 'unknown'
            return result
    
    def is_authenticated(self) -> bool:
        """
        Check if authentication is working
        
        Returns:
            bool: True if authenticated and working
        """
        result = self.test_authentication()
        return result.get('valid', False)
    
    def get_auth_info(self) -> Dict[str, Any]:
        """
        Get comprehensive authentication information
        
        Returns:
            Dict with authentication details and status
        """
        with self._provider_lock:
            if not self.provider:
                return {
                    'method': 'none', 
                    'initialized': False,
                    'provider': None
                }
            
            info = self.provider.get_auth_info()
            info.update({
                'method': self.auth_method.value if self.auth_method else 'unknown',
                'initialized': True,
                'manager_initialized': self._initialized
            })
            return info
    
    def reset(self):
        """
        Reset authentication manager (useful for testing)
        Thread-safe reset operation
        """
        with self._provider_lock:
            self.provider = None
            self.auth_method = None
            logger.info("🔄 Authentication manager reset")
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status for monitoring
        
        Returns:
            Dict with health information
        """
        try:
            auth_info = self.get_auth_info()
            test_result = self.test_authentication()
            
            return {
                'healthy': test_result.get('valid', False),
                'method': auth_info.get('method', 'unknown'),
                'provider': auth_info.get('provider', 'unknown'),
                'initialized': auth_info.get('initialized', False),
                'last_test': test_result,
                'thread_safe': True
            }
        except Exception as e:
            logger.error(f"❌ Health status check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'thread_safe': True
            }


# Global instance for convenient access
_auth_manager = AuthManager()


def initialize_authentication(auth_method: Optional[str] = None) -> bool:
    """
    Initialize authentication - main entry point for function_app.py
    
    Args:
        auth_method: Override auth method ('certificate' or 'personal_oauth')
        
    Returns:
        bool: True if initialization successful
    """
    return _auth_manager.initialize(auth_method)


def get_access_token() -> Optional[str]:
    """
    Get access token from initialized provider
    
    Returns:
        str: Access token or None if not available
    """
    return _auth_manager.get_access_token()


def make_graph_request(url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
    """
    Make Microsoft Graph API request
    
    Args:
        url: Graph API URL
        method: HTTP method (GET, POST, PATCH)
        data: Request data for POST/PATCH
        
    Returns:
        requests.Response or None if failed
    """
    return _auth_manager.make_graph_request(url, method, data)


def test_authentication() -> Dict[str, Any]:
    """
    Test authentication and return results
    
    Returns:
        Dict with validation results
    """
    return _auth_manager.test_authentication()


def is_authenticated() -> bool:
    """
    Check if authentication is working
    
    Returns:
        bool: True if authenticated and working
    """
    return _auth_manager.is_authenticated()


def get_auth_info() -> Dict[str, Any]:
    """
    Get authentication information
    
    Returns:
        Dict with authentication details
    """
    return _auth_manager.get_auth_info()


def get_auth_health_status() -> Dict[str, Any]:
    """
    Get authentication health status for monitoring
    
    Returns:
        Dict with health information
    """
    return _auth_manager.get_health_status()


def reset_authentication():
    """
    Reset authentication manager (useful for testing)
    """
    _auth_manager.reset()


# Legacy compatibility functions for existing code
def get_oauth_manager():
    """Legacy compatibility - returns auth manager"""
    return _auth_manager


def get_keyvault_oauth_manager():
    """Legacy compatibility - returns auth manager"""
    return _auth_manager


def get_production_oauth_manager():
    """Legacy compatibility - returns auth manager"""
    return _auth_manager


def get_auth_method() -> str:
    """
    Legacy compatibility function - get configured authentication method
    
    Returns:
        str: Authentication method ('certificate' or 'personal_oauth')
    """
    return os.getenv('AUTH_METHOD', 'certificate').lower()