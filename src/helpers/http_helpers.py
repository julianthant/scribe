"""
HTTP request helper functions for consistent API interactions
Centralizes request patterns, timeouts, and error handling using unified configuration
"""

import requests
import logging
from typing import Dict, Any, Optional, Union
from .retry_helpers import retry_with_exponential_backoff, RetryConfig
from .request_config import RequestConfig


class HttpClient:
    """Centralized HTTP client with consistent patterns and configuration"""
    
    def __init__(self, default_operation_type: str = 'api'):
        """
        Initialize HTTP client
        
        Args:
            default_operation_type: Default operation type for timeouts/retries
        """
        self.default_operation_type = default_operation_type
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def request(self, 
                method: str,
                url: str, 
                operation_type: Optional[str] = None,
                use_retry: bool = True,
                **kwargs) -> requests.Response:
        """
        Make HTTP request with centralized configuration
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            url: Request URL
            operation_type: Type of operation (auth, api, file_transfer, etc.)
            use_retry: Whether to use retry logic
            **kwargs: Additional request parameters
            
        Returns:
            requests.Response: HTTP response
        """
        operation_type = operation_type or self.default_operation_type
        
        # Get centralized configuration
        timeout = RequestConfig.get_timeout_for_operation(operation_type)
        retry_config = RequestConfig.get_retry_for_operation(operation_type) if use_retry else None
        
        # Apply timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = timeout
        
        def make_request():
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        
        if retry_config:
            return retry_with_exponential_backoff(
                make_request,
                retry_config,
                f"{method} {url}"
            )
        else:
            return make_request()
    
    def get(self, url: str, operation_type: Optional[str] = None, **kwargs) -> requests.Response:
        """Make GET request"""
        return self.request('GET', url, operation_type, **kwargs)
    
    def post(self, url: str, operation_type: Optional[str] = None, **kwargs) -> requests.Response:
        """Make POST request"""  
        return self.request('POST', url, operation_type, **kwargs)
    
    def put(self, url: str, operation_type: Optional[str] = None, **kwargs) -> requests.Response:
        """Make PUT request"""
        return self.request('PUT', url, operation_type, **kwargs)
    
    def patch(self, url: str, operation_type: Optional[str] = None, **kwargs) -> requests.Response:
        """Make PATCH request"""
        return self.request('PATCH', url, operation_type, **kwargs)
    
    def delete(self, url: str, operation_type: Optional[str] = None, **kwargs) -> requests.Response:
        """Make DELETE request"""
        return self.request('DELETE', url, operation_type, **kwargs)


# Global HTTP client instance
_http_client: Optional[HttpClient] = None


def get_http_client(default_operation_type: str = 'api') -> HttpClient:
    """
    Get or create global HTTP client instance
    
    Args:
        default_operation_type: Default operation type for timeouts/retries
        
    Returns:
        HttpClient: Global HTTP client
    """
    global _http_client
    if _http_client is None:
        _http_client = HttpClient(default_operation_type)
    return _http_client


def make_authenticated_request(method: str,
                             url: str,
                             token_type: str = 'graph',
                             operation_type: str = 'api',
                             force_token_refresh: bool = False,
                             **kwargs) -> requests.Response:
    """
    Make authenticated HTTP request with automatic token management
    
    Args:
        method: HTTP method
        url: Request URL
        token_type: Type of token to use (graph, ai_foundry, storage)
        operation_type: Type of operation for timeout/retry config
        force_token_refresh: Force token refresh
        **kwargs: Additional request parameters
        
    Returns:
        requests.Response: HTTP response
    """
    from .auth_helpers import get_auth_manager
    
    # Get authentication headers
    auth_manager = get_auth_manager()
    headers = auth_manager.get_auth_headers(token_type, force_token_refresh)
    
    if not headers:
        raise Exception(f"Failed to get authentication headers for {token_type}")
    
    # Merge with existing headers
    if 'headers' in kwargs:
        headers.update(kwargs['headers'])
    kwargs['headers'] = headers
    
    # Make request using HTTP client
    http_client = get_http_client()
    return http_client.request(method, url, operation_type, **kwargs)
