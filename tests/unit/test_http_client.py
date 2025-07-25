"""
Unit tests for Centralized HTTP Client
Tests authentication injection, timeout handling, and request patterns
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock
from src.helpers.http_helpers import HttpClient, make_authenticated_request
from src.helpers.request_config import RequestConfig


class TestHttpClient:
    """Test suite for HttpClient"""
    
    def setup_method(self):
        """Setup test environment"""
        self.client = HttpClient()
    
    def test_http_client_initialization(self):
        """Test HttpClient initializes correctly"""
        assert self.client is not None
        assert hasattr(self.client, 'request')
    
    @patch('src.helpers.http_helpers.requests.request')
    def test_http_client_get_request(self, mock_request):
        """Test HttpClient GET request"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response
        
        # Make request
        response = self.client.request(
            'GET', 
            'https://api.example.com/test',
            operation_type='api'
        )
        
        # Verify call
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == 'GET'
        assert call_args[0][1] == 'https://api.example.com/test'
        assert call_args[1]['timeout'] == 60  # API timeout
        
        assert response.status_code == 200
    
    @patch('src.helpers.http_helpers.requests.request')
    def test_http_client_timeout_selection(self, mock_request):
        """Test timeout selection based on operation type"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Test different operation types
        operation_timeouts = [
            ('auth', 30),
            ('api', 60),
            ('file_transfer', 300),
            ('processing', 600),
            ('unknown', 60)  # default
        ]
        
        for operation_type, expected_timeout in operation_timeouts:
            self.client.request(
                'GET',
                'https://api.example.com/test',
                operation_type=operation_type
            )
            
            # Get the last call arguments
            call_args = mock_request.call_args
            assert call_args[1]['timeout'] == expected_timeout
    
    @patch('src.helpers.http_helpers.requests.request')
    def test_http_client_with_headers(self, mock_request):
        """Test HttpClient with custom headers"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        custom_headers = {'Authorization': 'Bearer test-token'}
        
        self.client.request(
            'POST',
            'https://api.example.com/test',
            headers=custom_headers,
            json={'data': 'test'}
        )
        
        call_args = mock_request.call_args
        assert call_args[1]['headers'] == custom_headers
        assert call_args[1]['json'] == {'data': 'test'}
    
    @patch('src.helpers.http_helpers.requests.request')
    def test_http_client_error_handling(self, mock_request):
        """Test HttpClient error handling"""
        # Mock network error
        mock_request.side_effect = requests.exceptions.ConnectionError("Network error")
        
        with pytest.raises(requests.exceptions.ConnectionError):
            self.client.request('GET', 'https://api.example.com/test')


class TestMakeAuthenticatedRequest:
    """Test suite for make_authenticated_request function"""
    
    @patch('src.helpers.http_helpers.get_auth_manager')
    @patch('src.helpers.http_helpers.HttpClient.request')
    def test_make_authenticated_request_basic(self, mock_request, mock_get_auth_manager):
        """Test basic authenticated request"""
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_auth_manager.get_auth_headers.return_value = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        mock_get_auth_manager.return_value = mock_auth_manager
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Make authenticated request
        response = make_authenticated_request(
            'GET',
            'https://graph.microsoft.com/v1.0/me/messages',
            token_type='graph'
        )
        
        # Verify auth manager was called
        mock_auth_manager.get_auth_headers.assert_called_once_with('graph')
        
        # Verify request was made with auth headers
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == 'GET'
        assert call_args[0][1] == 'https://graph.microsoft.com/v1.0/me/messages'
        assert call_args[1]['headers']['Authorization'] == 'Bearer test-token'
    
    @patch('src.helpers.http_helpers.get_auth_manager')
    @patch('src.helpers.http_helpers.HttpClient.request')
    def test_make_authenticated_request_with_operation_type(self, mock_request, mock_get_auth_manager):
        """Test authenticated request with specific operation type"""
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_auth_manager.get_auth_headers.return_value = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        mock_get_auth_manager.return_value = mock_auth_manager
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Make authenticated request with file_transfer operation
        response = make_authenticated_request(
            'GET',
            'https://example.com/file',
            token_type='graph',
            operation_type='file_transfer'
        )
        
        # Verify request was made with correct operation type
        call_args = mock_request.call_args
        assert call_args[1]['operation_type'] == 'file_transfer'
    
    @patch('src.helpers.http_helpers.get_auth_manager')
    @patch('src.helpers.http_helpers.HttpClient.request')
    def test_make_authenticated_request_with_custom_params(self, mock_request, mock_get_auth_manager):
        """Test authenticated request with custom parameters"""
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_auth_manager.get_auth_headers.return_value = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        mock_get_auth_manager.return_value = mock_auth_manager
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Make authenticated request with custom parameters
        response = make_authenticated_request(
            'POST',
            'https://api.example.com/data',
            token_type='ai_foundry',
            operation_type='processing',
            json={'data': 'test'},
            params={'filter': 'active'}
        )
        
        # Verify all parameters were passed through
        call_args = mock_request.call_args
        assert call_args[0][0] == 'POST'
        assert call_args[1]['json'] == {'data': 'test'}
        assert call_args[1]['params'] == {'filter': 'active'}
        assert call_args[1]['operation_type'] == 'processing'
    
    @patch('src.helpers.http_helpers.get_auth_manager')
    @patch('src.helpers.http_helpers.HttpClient.request')
    def test_make_authenticated_request_header_merging(self, mock_request, mock_get_auth_manager):
        """Test that custom headers are merged with auth headers"""
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_auth_manager.get_auth_headers.return_value = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        mock_get_auth_manager.return_value = mock_auth_manager
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Make authenticated request with custom headers
        custom_headers = {'X-Custom-Header': 'custom-value'}
        response = make_authenticated_request(
            'GET',
            'https://api.example.com/test',
            token_type='graph',
            headers=custom_headers
        )
        
        # Verify headers were merged
        call_args = mock_request.call_args
        headers = call_args[1]['headers']
        assert headers['Authorization'] == 'Bearer test-token'
        assert headers['Content-Type'] == 'application/json'
        assert headers['X-Custom-Header'] == 'custom-value'
    
    @patch('src.helpers.http_helpers.get_auth_manager')
    @patch('src.helpers.http_helpers.HttpClient.request')
    def test_make_authenticated_request_different_token_types(self, mock_request, mock_get_auth_manager):
        """Test authenticated request with different token types"""
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_get_auth_manager.return_value = mock_auth_manager
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Test different token types
        token_types = ['graph', 'ai_foundry', 'storage']
        
        for token_type in token_types:
            mock_auth_manager.get_auth_headers.return_value = {
                'Authorization': f'Bearer {token_type}-token'
            }
            
            make_authenticated_request(
                'GET',
                'https://api.example.com/test',
                token_type=token_type
            )
            
            # Verify correct token type was requested
            mock_auth_manager.get_auth_headers.assert_called_with(token_type)
    
    @patch('src.helpers.http_helpers.get_auth_manager')
    def test_make_authenticated_request_auth_manager_error(self, mock_get_auth_manager):
        """Test authenticated request when auth manager fails"""
        # Mock auth manager failure
        mock_get_auth_manager.side_effect = Exception("Auth manager error")
        
        with pytest.raises(Exception) as exc_info:
            make_authenticated_request(
                'GET',
                'https://api.example.com/test',
                token_type='graph'
            )
        
        assert "Auth manager error" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
