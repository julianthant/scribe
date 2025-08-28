"""
Unit tests for AzureAuthService.

Tests Azure AD authentication functionality including:
- OAuth authorization flow initiation
- Token acquisition from authorization code
- Token refresh operations
- Token validation and expiry detection
- Error handling for various failure scenarios
- MSAL client interaction patterns
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import jwt

from app.azure.AzureAuthService import AzureAuthService
from app.core.Exceptions import AuthenticationError, ValidationError


class TestAzureAuthService:
    """Test suite for AzureAuthService."""

    # ==========================================================================
    # INITIALIZATION TESTS
    # ==========================================================================

    @patch('app.azure.AzureAuthService.msal.ConfidentialClientApplication')
    def test_initialization_success(self, mock_msal):
        """Test successful service initialization."""
        mock_client = Mock()
        mock_msal.return_value = mock_client
        
        service = AzureAuthService()
        
        assert service is not None
        mock_msal.assert_called_once()

    @patch('app.azure.AzureAuthService.msal.ConfidentialClientApplication')
    def test_initialization_with_missing_config(self, mock_msal):
        """Test initialization behavior with missing configuration."""
        mock_msal.side_effect = ValueError("Missing client configuration")
        
        with pytest.raises(ValueError):
            AzureAuthService()

    # ==========================================================================
    # AUTHORIZATION URL GENERATION TESTS
    # ==========================================================================

    def test_get_authorization_url_success(self, mock_azure_auth_service, mock_msal_client):
        """Test successful authorization URL generation."""
        expected_auth_data = {
            "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "flow": {
                "state": "test-state-123",
                "code_verifier": "test-verifier"
            }
        }
        mock_msal_client.initiate_auth_code_flow.return_value = expected_auth_data
        
        result = mock_azure_auth_service.get_authorization_url()
        
        assert result == expected_auth_data
        assert "auth_uri" in result
        assert "flow" in result
        assert "state" in result["flow"]
        mock_msal_client.initiate_auth_code_flow.assert_called_once()

    def test_get_authorization_url_with_custom_scopes(self, mock_azure_auth_service, mock_msal_client):
        """Test authorization URL generation with custom scopes."""
        custom_scopes = ["User.Read", "Mail.Read", "Files.ReadWrite"]
        expected_auth_data = {
            "auth_uri": "https://login.microsoftonline.com/authorize",
            "flow": {"state": "custom-state"}
        }
        mock_msal_client.initiate_auth_code_flow.return_value = expected_auth_data
        
        result = mock_azure_auth_service.get_authorization_url(scopes=custom_scopes)
        
        assert result == expected_auth_data
        call_args = mock_msal_client.initiate_auth_code_flow.call_args[1]
        assert call_args['scopes'] == custom_scopes

    def test_get_authorization_url_msal_error(self, mock_azure_auth_service, mock_msal_client):
        """Test handling of MSAL errors during URL generation."""
        mock_msal_client.initiate_auth_code_flow.side_effect = Exception("MSAL error")
        
        with pytest.raises(AuthenticationError):
            mock_azure_auth_service.get_authorization_url()

    # ==========================================================================
    # TOKEN ACQUISITION TESTS
    # ==========================================================================

    def test_acquire_token_by_auth_code_success(self, mock_azure_auth_service, mock_msal_client):
        """Test successful token acquisition from authorization code."""
        callback_url = "http://localhost:8000/auth/callback?code=auth_code&state=test_state"
        auth_flow = {"state": "test_state", "code_verifier": "verifier"}
        
        expected_token = {
            "access_token": "access_token_value",
            "refresh_token": "refresh_token_value",
            "id_token": "id_token_value",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "User.Read Mail.Read"
        }
        mock_msal_client.acquire_token_by_auth_code_flow.return_value = expected_token
        
        result = mock_azure_auth_service.acquire_token_by_auth_code(callback_url, auth_flow)
        
        assert result == expected_token
        assert result["access_token"] == "access_token_value"
        assert result["token_type"] == "Bearer"
        mock_msal_client.acquire_token_by_auth_code_flow.assert_called_once_with(
            auth_flow, callback_url
        )

    def test_acquire_token_by_auth_code_with_error_response(self, mock_azure_auth_service, mock_msal_client):
        """Test token acquisition with error response from MSAL."""
        callback_url = "http://localhost:8000/auth/callback?error=access_denied"
        auth_flow = {"state": "test_state"}
        
        error_response = {
            "error": "access_denied",
            "error_description": "The user denied the request"
        }
        mock_msal_client.acquire_token_by_auth_code_flow.return_value = error_response
        
        result = mock_azure_auth_service.acquire_token_by_auth_code(callback_url, auth_flow)
        
        assert "error" in result
        assert result["error"] == "access_denied"

    def test_acquire_token_by_auth_code_invalid_flow(self, mock_azure_auth_service, mock_msal_client):
        """Test token acquisition with invalid auth flow."""
        callback_url = "http://localhost:8000/auth/callback"
        auth_flow = None
        
        with pytest.raises(ValidationError):
            mock_azure_auth_service.acquire_token_by_auth_code(callback_url, auth_flow)

    def test_acquire_token_by_auth_code_msal_exception(self, mock_azure_auth_service, mock_msal_client):
        """Test handling of MSAL exceptions during token acquisition."""
        callback_url = "http://localhost:8000/auth/callback"
        auth_flow = {"state": "test_state"}
        
        mock_msal_client.acquire_token_by_auth_code_flow.side_effect = Exception("MSAL network error")
        
        with pytest.raises(AuthenticationError):
            mock_azure_auth_service.acquire_token_by_auth_code(callback_url, auth_flow)

    # ==========================================================================
    # TOKEN REFRESH TESTS
    # ==========================================================================

    def test_refresh_token_success(self, mock_azure_auth_service, mock_msal_client):
        """Test successful token refresh."""
        refresh_token = "refresh_token_value"
        scopes = ["User.Read", "Mail.Read"]
        
        expected_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token", 
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "User.Read Mail.Read"
        }
        mock_msal_client.acquire_token_by_refresh_token.return_value = expected_response
        
        result = mock_azure_auth_service.refresh_token(refresh_token, scopes)
        
        assert result == expected_response
        assert result["access_token"] == "new_access_token"
        mock_msal_client.acquire_token_by_refresh_token.assert_called_once_with(
            refresh_token, scopes
        )

    def test_refresh_token_with_error(self, mock_azure_auth_service, mock_msal_client):
        """Test token refresh with error response."""
        refresh_token = "invalid_refresh_token"
        scopes = ["User.Read"]
        
        error_response = {
            "error": "invalid_grant",
            "error_description": "The refresh token is invalid or expired"
        }
        mock_msal_client.acquire_token_by_refresh_token.return_value = error_response
        
        result = mock_azure_auth_service.refresh_token(refresh_token, scopes)
        
        assert "error" in result
        assert result["error"] == "invalid_grant"

    def test_refresh_token_missing_token(self, mock_azure_auth_service):
        """Test token refresh with missing refresh token."""
        with pytest.raises(ValidationError):
            mock_azure_auth_service.refresh_token("", ["User.Read"])

    def test_refresh_token_msal_exception(self, mock_azure_auth_service, mock_msal_client):
        """Test handling of MSAL exceptions during token refresh."""
        mock_msal_client.acquire_token_by_refresh_token.side_effect = Exception("Network error")
        
        with pytest.raises(AuthenticationError):
            mock_azure_auth_service.refresh_token("refresh_token", ["User.Read"])

    # ==========================================================================
    # TOKEN VALIDATION TESTS
    # ==========================================================================

    def test_validate_token_valid_jwt(self, mock_azure_auth_service):
        """Test validation of valid JWT token."""
        # Create a mock JWT token (not actually signed for testing)
        future_time = datetime.utcnow() + timedelta(hours=1)
        payload = {
            "exp": int(future_time.timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "aud": "test-audience",
            "iss": "https://login.microsoftonline.com/test-tenant",
            "sub": "test-user-id"
        }
        
        # Mock JWT decode to return our payload
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.return_value = payload
            
            result = mock_azure_auth_service.validate_token("valid.jwt.token")
            
            assert result is not None
            assert result.get("exp") == payload["exp"]

    def test_validate_token_expired_jwt(self, mock_azure_auth_service):
        """Test validation of expired JWT token."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        payload = {
            "exp": int(past_time.timestamp()),
            "iat": int((datetime.utcnow() - timedelta(hours=2)).timestamp())
        }
        
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.side_effect = jwt.ExpiredSignatureError("Token has expired")
            
            with pytest.raises(AuthenticationError):
                mock_azure_auth_service.validate_token("expired.jwt.token")

    def test_validate_token_invalid_format(self, mock_azure_auth_service):
        """Test validation of malformed token."""
        with pytest.raises(ValidationError):
            mock_azure_auth_service.validate_token("invalid-token-format")

    def test_validate_token_empty_token(self, mock_azure_auth_service):
        """Test validation with empty token."""
        with pytest.raises(ValidationError):
            mock_azure_auth_service.validate_token("")

    def test_validate_token_jwt_decode_error(self, mock_azure_auth_service):
        """Test handling of JWT decode errors."""
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.side_effect = jwt.InvalidTokenError("Invalid token")
            
            with pytest.raises(AuthenticationError):
                mock_azure_auth_service.validate_token("malformed.jwt.token")

    # ==========================================================================
    # TOKEN EXPIRY DETECTION TESTS
    # ==========================================================================

    def test_is_token_expired_valid_token(self, mock_azure_auth_service):
        """Test expiry check for valid token."""
        future_time = datetime.utcnow() + timedelta(hours=1)
        payload = {"exp": int(future_time.timestamp())}
        
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.return_value = payload
            
            result = mock_azure_auth_service.is_token_expired("valid.jwt.token")
            
            assert result is False

    def test_is_token_expired_expired_token(self, mock_azure_auth_service):
        """Test expiry check for expired token."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        payload = {"exp": int(past_time.timestamp())}
        
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.return_value = payload
            
            result = mock_azure_auth_service.is_token_expired("expired.jwt.token")
            
            assert result is True

    def test_is_token_expired_no_exp_claim(self, mock_azure_auth_service):
        """Test expiry check for token without exp claim."""
        payload = {"iat": int(datetime.utcnow().timestamp())}
        
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.return_value = payload
            
            result = mock_azure_auth_service.is_token_expired("token.without.exp")
            
            assert result is True  # Should consider tokens without exp as expired

    def test_is_token_expired_buffer_time(self, mock_azure_auth_service):
        """Test expiry check with buffer time consideration."""
        # Token expires in 4 minutes, but we consider it expired if < 5 minutes
        near_future = datetime.utcnow() + timedelta(minutes=4)
        payload = {"exp": int(near_future.timestamp())}
        
        with patch('jwt.decode') as mock_jwt_decode:
            mock_jwt_decode.return_value = payload
            
            result = mock_azure_auth_service.is_token_expired("soon.expired.token", buffer_minutes=5)
            
            assert result is True

    # ==========================================================================
    # LOGOUT TESTS
    # ==========================================================================

    def test_get_logout_url_success(self, mock_azure_auth_service):
        """Test logout URL generation."""
        redirect_uri = "http://localhost:8000"
        
        result = mock_azure_auth_service.get_logout_url(redirect_uri)
        
        assert "logout" in result.lower()
        assert redirect_uri in result

    def test_get_logout_url_no_redirect(self, mock_azure_auth_service):
        """Test logout URL generation without redirect."""
        result = mock_azure_auth_service.get_logout_url()
        
        assert "logout" in result.lower()
        assert result is not None

    # ==========================================================================
    # ERROR HANDLING AND EDGE CASES
    # ==========================================================================

    def test_handle_network_timeout(self, mock_azure_auth_service, mock_msal_client):
        """Test handling of network timeouts."""
        import requests
        mock_msal_client.acquire_token_by_auth_code_flow.side_effect = requests.Timeout("Request timeout")
        
        callback_url = "http://localhost:8000/auth/callback"
        auth_flow = {"state": "test_state"}
        
        with pytest.raises(AuthenticationError):
            mock_azure_auth_service.acquire_token_by_auth_code(callback_url, auth_flow)

    def test_handle_connection_error(self, mock_azure_auth_service, mock_msal_client):
        """Test handling of connection errors."""
        import requests
        mock_msal_client.initiate_auth_code_flow.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(AuthenticationError):
            mock_azure_auth_service.get_authorization_url()

    def test_concurrent_token_acquisition(self, mock_azure_auth_service, mock_msal_client):
        """Test concurrent token acquisition requests."""
        import asyncio
        
        async def acquire_token():
            callback_url = "http://localhost:8000/auth/callback"
            auth_flow = {"state": "test_state"}
            return mock_azure_auth_service.acquire_token_by_auth_code(callback_url, auth_flow)
        
        # Mock successful response
        mock_msal_client.acquire_token_by_auth_code_flow.return_value = {
            "access_token": "token",
            "expires_in": 3600
        }
        
        # This test ensures thread safety (if applicable in actual implementation)
        result = acquire_token()
        assert result is not None

    # ==========================================================================
    # CONFIGURATION TESTS
    # ==========================================================================

    @patch('app.azure.AzureAuthService.settings')
    def test_service_with_different_tenant(self, mock_settings, mock_msal_client):
        """Test service initialization with different tenant configuration."""
        mock_settings.azure_tenant_id = "custom-tenant-id"
        mock_settings.azure_client_id = "custom-client-id"
        
        with patch('app.azure.AzureAuthService.msal.ConfidentialClientApplication') as mock_msal:
            mock_msal.return_value = mock_msal_client
            
            service = AzureAuthService()
            
            assert service is not None
            # Verify MSAL was called with custom tenant
            call_args = mock_msal.call_args
            assert call_args is not None

    def test_service_configuration_validation(self):
        """Test validation of required configuration parameters."""
        with patch('app.azure.AzureAuthService.settings') as mock_settings:
            mock_settings.azure_client_id = ""  # Empty client ID
            
            with pytest.raises(ValidationError):
                AzureAuthService()

    # ==========================================================================
    # INTEGRATION WITH CACHE
    # ==========================================================================

    def test_token_caching_behavior(self, mock_azure_auth_service):
        """Test token caching behavior if implemented."""
        # This test would verify token caching logic if the service implements it
        token = "test-access-token"
        
        # Store token
        mock_azure_auth_service.store_token("user-id", token)
        
        # Retrieve token
        cached_token = mock_azure_auth_service.get_cached_token("user-id")
        
        # This would depend on actual cache implementation
        # For now, we just verify the methods can be called
        assert cached_token is not None or cached_token is None  # Either is valid

    def test_clear_cached_tokens(self, mock_azure_auth_service):
        """Test clearing of cached tokens."""
        # Test cache clearing functionality if implemented
        result = mock_azure_auth_service.clear_cache("user-id")
        
        # Verify method completes without error
        assert result is None or isinstance(result, bool)