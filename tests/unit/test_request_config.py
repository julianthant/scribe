"""
Unit tests for Request Configuration System
Tests timeout constants, retry policies, and endpoint management
"""

import pytest
from src.helpers.request_config import RequestConfig, RequestTimeouts, RequestRetryConfigs
from src.helpers.retry_helpers import RetryConfig


class TestRequestConfiguration:
    """Test suite for RequestConfig system"""
    
    def test_timeout_constants(self):
        """Test that timeout constants are correctly defined"""
        timeouts = RequestConfig.TIMEOUTS
        
        # Verify all expected timeout values
        assert timeouts.AUTH == 30
        assert timeouts.API_STANDARD == 60
        assert timeouts.FILE_TRANSFER == 300
        assert timeouts.HEAVY_PROCESSING == 600
        assert timeouts.HEALTH_CHECK == 10
    
    def test_retry_configurations(self):
        """Test retry configuration objects"""
        retry_configs = RequestConfig.RETRY_CONFIGS
        
        # Test AUTH retry config
        auth_retry = retry_configs.AUTH
        assert isinstance(auth_retry, RetryConfig)
        assert auth_retry.max_attempts == 3
        assert auth_retry.base_delay == 2.0
        assert auth_retry.max_delay == 30.0
        assert auth_retry.exponential_base == 2.0
        
        # Test NETWORK retry config
        network_retry = retry_configs.NETWORK
        assert isinstance(network_retry, RetryConfig)
        assert network_retry.max_attempts == 5
        assert network_retry.base_delay == 1.0
        assert network_retry.max_delay == 60.0
        assert network_retry.exponential_base == 2.0
    
    def test_service_endpoints(self):
        """Test service endpoint definitions"""
        endpoints = RequestConfig.ENDPOINTS
        
        # Verify all expected endpoints exist
        assert 'graph_messages' in endpoints
        assert 'graph_drive' in endpoints
        assert 'ai_foundry_transcription' in endpoints
        assert 'ai_foundry_audio' in endpoints
        assert 'storage_blob' in endpoints
        
        # Verify URLs are properly formed
        assert endpoints['graph_messages'].startswith('https://graph.microsoft.com')
        assert endpoints['graph_drive'].startswith('https://graph.microsoft.com')
        assert 'api.aiservices.azure.com' in endpoints['ai_foundry_transcription']
    
    def test_service_headers(self):
        """Test service-specific headers"""
        headers = RequestConfig.SERVICE_HEADERS
        
        # Test Graph API headers
        graph_headers = headers['graph']
        assert 'Content-Type' in graph_headers
        assert graph_headers['Content-Type'] == 'application/json'
        
        # Test AI Foundry headers
        ai_headers = headers['ai_foundry']
        assert 'Content-Type' in ai_headers
        assert ai_headers['Content-Type'] == 'application/json'
    
    def test_get_timeout_for_operation(self):
        """Test timeout selection by operation type"""
        # Test known operation types
        assert RequestConfig.get_timeout_for_operation('auth') == 30
        assert RequestConfig.get_timeout_for_operation('api') == 60
        assert RequestConfig.get_timeout_for_operation('file_transfer') == 300
        assert RequestConfig.get_timeout_for_operation('processing') == 600
        
        # Test default fallback
        assert RequestConfig.get_timeout_for_operation('unknown') == 60
    
    def test_get_retry_for_operation(self):
        """Test retry configuration selection by operation type"""
        # Test network operations
        network_retry = RequestConfig.get_retry_for_operation('network')
        assert isinstance(network_retry, RetryConfig)
        assert network_retry.max_attempts == 5
        
        # Test auth operations
        auth_retry = RequestConfig.get_retry_for_operation('auth')
        assert isinstance(auth_retry, RetryConfig)
        assert auth_retry.max_attempts == 3
        
        # Test default fallback
        default_retry = RequestConfig.get_retry_for_operation('unknown')
        assert isinstance(default_retry, RetryConfig)
        assert default_retry.max_attempts == 3  # Should default to auth config
    
    def test_get_headers_for_service(self):
        """Test header selection by service type"""
        # Test Graph service headers
        graph_headers = RequestConfig.get_headers_for_service('graph')
        assert 'Content-Type' in graph_headers
        assert graph_headers['Content-Type'] == 'application/json'
        
        # Test AI Foundry service headers
        ai_headers = RequestConfig.get_headers_for_service('ai_foundry')
        assert 'Content-Type' in ai_headers
        
        # Test default fallback
        default_headers = RequestConfig.get_headers_for_service('unknown')
        assert 'Content-Type' in default_headers
        assert default_headers['Content-Type'] == 'application/json'
    
    def test_request_timeouts_dataclass(self):
        """Test RequestTimeouts dataclass"""
        timeouts = RequestTimeouts()
        
        # Test default values
        assert timeouts.AUTH == 30
        assert timeouts.API_STANDARD == 60
        assert timeouts.FILE_TRANSFER == 300
        assert timeouts.HEAVY_PROCESSING == 600
        assert timeouts.HEALTH_CHECK == 10
    
    def test_request_retry_configs_dataclass(self):
        """Test RequestRetryConfigs dataclass"""
        retry_configs = RequestRetryConfigs()
        
        # Test AUTH configuration
        assert isinstance(retry_configs.AUTH, RetryConfig)
        assert retry_configs.AUTH.max_attempts == 3
        
        # Test NETWORK configuration
        assert isinstance(retry_configs.NETWORK, RetryConfig)
        assert retry_configs.NETWORK.max_attempts == 5
        
        # Test FILE_TRANSFER configuration
        assert isinstance(retry_configs.FILE_TRANSFER, RetryConfig)
        assert retry_configs.FILE_TRANSFER.max_attempts == 3
        
        # Test PROCESSING configuration
        assert isinstance(retry_configs.PROCESSING, RetryConfig)
        assert retry_configs.PROCESSING.max_attempts == 2
    
    def test_configuration_immutability(self):
        """Test that configurations are properly structured"""
        # Test that ENDPOINTS is a dictionary
        assert isinstance(RequestConfig.ENDPOINTS, dict)
        
        # Test that SERVICE_HEADERS is a dictionary
        assert isinstance(RequestConfig.SERVICE_HEADERS, dict)
        
        # Test that timeout and retry configs are accessible
        assert hasattr(RequestConfig, 'TIMEOUTS')
        assert hasattr(RequestConfig, 'RETRY_CONFIGS')
    
    def test_endpoint_url_validation(self):
        """Test that all endpoints are valid URLs"""
        endpoints = RequestConfig.ENDPOINTS
        
        for service, url in endpoints.items():
            assert url.startswith('https://'), f"Endpoint {service} should use HTTPS"
            assert '.' in url, f"Endpoint {service} should be a valid domain"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
