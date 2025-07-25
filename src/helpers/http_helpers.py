"""
HTTP request helper functions for consistent API interactions
Centralizes request patterns, timeouts, and error handling
"""

import requests
import logging
from typing import Dict, Any, Optional, Union
from ..helpers.retry_helpers import retry_with_exponential_backoff, RetryConfig


class HttpClient:
    """Centralized HTTP client with consistent patterns"""
    
    def __init__(self, default_timeout: int = 60):
        """
        Initialize HTTP client
        
        Args:
            default_timeout: Default request timeout in seconds
        """
        self.default_timeout = default_timeout
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get(self, 
            url: str, 
            headers: Optional[Dict[str, str]] = None,
            params: Optional[Dict[str, Any]] = None,
            timeout: Optional[int] = None,
            retry_config: Optional[RetryConfig] = None) -> requests.Response:
        """
        Make GET request with retry logic
        
        Args:
            url: Request URL
            headers: Request headers
            params: Query parameters
            timeout: Request timeout (uses default if None)
            retry_config: Retry configuration
            
        Returns:
            requests.Response: HTTP response
            
        Raises:
            requests.RequestException: If request fails after retries
        """
        timeout = timeout or self.default_timeout
        
        def make_request():
            response = requests.get(
                url, 
                headers=headers or {},
                params=params or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        
        if retry_config:
            return retry_with_exponential_backoff(
                make_request,
                retry_config,
                f"GET {url}"
            )
        else:
            return make_request()
    
    def post(self, 
             url: str, 
             data: Optional[Union[Dict[str, Any], str]] = None,
             json_data: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None,
             timeout: Optional[int] = None,
             retry_config: Optional[RetryConfig] = None) -> requests.Response:
        """
        Make POST request with retry logic
        
        Args:
            url: Request URL
            data: Form data
            json_data: JSON data
            headers: Request headers
            timeout: Request timeout
            retry_config: Retry configuration
            
        Returns:
            requests.Response: HTTP response
        """
        timeout = timeout or self.default_timeout
        
        def make_request():
            response = requests.post(
                url,
                data=data,
                json=json_data,
                headers=headers or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        
        if retry_config:
            return retry_with_exponential_backoff(
                make_request,
                retry_config,
                f"POST {url}"
            )
        else:
            return make_request()
    
    def put(self, 
            url: str, 
            data: Optional[Union[Dict[str, Any], str]] = None,
            json_data: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: Optional[int] = None,
            retry_config: Optional[RetryConfig] = None) -> requests.Response:
        """
        Make PUT request with retry logic
        """
        timeout = timeout or self.default_timeout
        
        def make_request():
            response = requests.put(
                url,
                data=data,
                json=json_data,
                headers=headers or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        
        if retry_config:
            return retry_with_exponential_backoff(
                make_request,
                retry_config,
                f"PUT {url}"
            )
        else:
            return make_request()
    
    def patch(self, 
              url: str, 
              data: Optional[Union[Dict[str, Any], str]] = None,
              json_data: Optional[Dict[str, Any]] = None,
              headers: Optional[Dict[str, str]] = None,
              timeout: Optional[int] = None,
              retry_config: Optional[RetryConfig] = None) -> requests.Response:
        """
        Make PATCH request with retry logic
        """
        timeout = timeout or self.default_timeout
        
        def make_request():
            response = requests.patch(
                url,
                data=data,
                json=json_data,
                headers=headers or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        
        if retry_config:
            return retry_with_exponential_backoff(
                make_request,
                retry_config,
                f"PATCH {url}"
            )
        else:
            return make_request()
    
    def delete(self, 
               url: str, 
               headers: Optional[Dict[str, str]] = None,
               timeout: Optional[int] = None,
               retry_config: Optional[RetryConfig] = None) -> requests.Response:
        """
        Make DELETE request with retry logic
        """
        timeout = timeout or self.default_timeout
        
        def make_request():
            response = requests.delete(
                url,
                headers=headers or {},
                timeout=timeout
            )
            response.raise_for_status()
            return response
        
        if retry_config:
            return retry_with_exponential_backoff(
                make_request,
                retry_config,
                f"DELETE {url}"
            )
        else:
            return make_request()


# Global HTTP client instance
_http_client: Optional[HttpClient] = None


def get_http_client(timeout: int = 60) -> HttpClient:
    """
    Get or create global HTTP client instance
    
    Args:
        timeout: Default timeout for requests
        
    Returns:
        HttpClient: Global HTTP client
    """
    global _http_client
    if _http_client is None:
        _http_client = HttpClient(timeout)
    return _http_client
