"""
Request configuration constants for consistent timeout and retry behavior
Centralized configuration for all HTTP requests across the application
"""

from typing import Dict, Any
from dataclasses import dataclass
from ..helpers.retry_helpers import RetryConfig


@dataclass
class RequestTimeouts:
    """Standard timeout values for different request types"""
    
    # Authentication requests (usually fast)
    AUTH: int = 30
    
    # Standard API requests
    API_STANDARD: int = 60
    
    # File upload/download operations
    FILE_TRANSFER: int = 300  # 5 minutes
    
    # Large data operations (Excel updates, AI processing)
    HEAVY_PROCESSING: int = 600  # 10 minutes
    
    # Quick health checks and lightweight operations
    HEALTH_CHECK: int = 10


@dataclass
class RequestRetryConfigs:
    """Standard retry configurations for different operation types"""
    
    # Authentication operations
    AUTH = RetryConfig(
        max_attempts=3,
        base_delay=2.0,
        max_delay=30.0,
        exponential_base=2.0
    )
    
    # Network/API operations
    NETWORK = RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=60.0,
        exponential_base=2.0
    )
    
    # Storage operations
    STORAGE = RetryConfig(
        max_attempts=3,
        base_delay=1.5,
        max_delay=45.0,
        exponential_base=2.0
    )
    
    # Processing operations (transcription, AI analysis)
    PROCESSING = RetryConfig(
        max_attempts=2,
        base_delay=3.0,
        max_delay=60.0,
        exponential_base=2.0
    )
    
    # Critical operations (should fail fast)
    CRITICAL = RetryConfig(
        max_attempts=1,
        base_delay=0.0,
        max_delay=0.0,
        exponential_base=1.0
    )


class RequestConfig:
    """Centralized request configuration manager"""
    
    # Timeout constants
    TIMEOUTS = RequestTimeouts()
    
    # Retry configurations
    RETRY = RequestRetryConfigs()
    
    # Standard headers for different services
    HEADERS = {
        'graph': {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        'ai_foundry': {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
        'storage': {
            'Content-Type': 'application/octet-stream'
        }
    }
    
    # API endpoints
    ENDPOINTS = {
        'graph_base': 'https://graph.microsoft.com/v1.0',
        'graph_me': 'https://graph.microsoft.com/v1.0/me',
        'graph_messages': 'https://graph.microsoft.com/v1.0/me/messages',
        'graph_drive': 'https://graph.microsoft.com/v1.0/me/drive',
        'graph_files': 'https://graph.microsoft.com/v1.0/me/drive/root/search'
    }
    
    @classmethod
    def get_timeout_for_operation(cls, operation_type: str) -> int:
        """
        Get appropriate timeout for operation type
        
        Args:
            operation_type: Type of operation (auth, api, file_transfer, etc.)
            
        Returns:
            int: Timeout in seconds
        """
        timeout_map = {
            'auth': cls.TIMEOUTS.AUTH,
            'api': cls.TIMEOUTS.API_STANDARD,
            'file_transfer': cls.TIMEOUTS.FILE_TRANSFER,
            'processing': cls.TIMEOUTS.HEAVY_PROCESSING,
            'health': cls.TIMEOUTS.HEALTH_CHECK
        }
        
        return timeout_map.get(operation_type, cls.TIMEOUTS.API_STANDARD)
    
    @classmethod
    def get_retry_for_operation(cls, operation_type: str) -> RetryConfig:
        """
        Get appropriate retry config for operation type
        
        Args:
            operation_type: Type of operation (auth, network, storage, etc.)
            
        Returns:
            RetryConfig: Retry configuration
        """
        retry_map = {
            'auth': cls.RETRY.AUTH,
            'network': cls.RETRY.NETWORK,
            'storage': cls.RETRY.STORAGE,
            'processing': cls.RETRY.PROCESSING,
            'critical': cls.RETRY.CRITICAL
        }
        
        return retry_map.get(operation_type, cls.RETRY.NETWORK)
    
    @classmethod
    def get_headers_for_service(cls, service_type: str, auth_token: str = None) -> Dict[str, str]:
        """
        Get standard headers for service type
        
        Args:
            service_type: Type of service (graph, ai_foundry, storage)
            auth_token: Optional authentication token
            
        Returns:
            Dict[str, str]: Request headers
        """
        headers = cls.HEADERS.get(service_type, {}).copy()
        
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        
        return headers
