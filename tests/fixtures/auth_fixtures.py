"""Authentication test fixtures.

This module provides fixtures for testing authentication functionality including:
- Mock MSAL client responses
- Test user data
- Authentication tokens
- OAuth flow responses
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


@pytest.fixture
def mock_msal_client():
    """Mock Microsoft Authentication Library (MSAL) client."""
    client = Mock()
    
    # Mock initiate_auth_code_flow
    client.initiate_auth_code_flow.return_value = {
        "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "flow": {
            "state": "test-auth-state-123",
            "code_verifier": "test-code-verifier"
        }
    }
    
    # Mock successful token acquisition
    client.acquire_token_by_auth_code_flow.return_value = {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test.token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "refresh_token_value",
        "scope": "User.Read Mail.Read Mail.ReadWrite",
        "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.id.token"
    }
    
    # Mock silent token acquisition
    client.acquire_token_silent.return_value = {
        "access_token": "new_access_token_value",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": "User.Read Mail.Read Mail.ReadWrite"
    }
    
    return client


@pytest.fixture
def mock_failed_msal_client():
    """Mock MSAL client that returns authentication failures."""
    client = Mock()
    
    # Mock failed token acquisition
    client.acquire_token_by_auth_code_flow.return_value = {
        "error": "invalid_grant",
        "error_description": "The provided authorization grant is invalid"
    }
    
    client.acquire_token_silent.return_value = None
    
    return client


@pytest.fixture
def oauth_auth_request():
    """Mock OAuth authorization request data."""
    return {
        "code": "test-authorization-code",
        "state": "test-auth-state-123",
        "session_state": "session-state-value"
    }


@pytest.fixture
def oauth_callback_params():
    """Mock OAuth callback query parameters."""
    return {
        "code": "0.AXoA-HtL8FjGkU",
        "state": "test-state-parameter",
        "session_state": "b8c4e8a2-1234-5678-9abc-def012345678"
    }


@pytest.fixture
def access_token():
    """Valid access token for testing."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJhcGkiLCJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vdGVzdCIsInN1YiI6InRlc3QtdXNlci1pZCIsImV4cCI6OTk5OTk5OTk5OX0.test"


@pytest.fixture
def expired_access_token():
    """Expired access token for testing token refresh scenarios."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJhcGkiLCJpc3MiOiJodHRwczovL3NlY3VyZXRva2VuLmdvb2dsZS5jb20vdGVzdCIsInN1YiI6InRlc3QtdXNlci1pZCIsImV4cCI6MTAwMDAwMDAwMH0.expired"


@pytest.fixture
def refresh_token():
    """Valid refresh token for testing."""
    return "refresh_token_test_value_12345"


@pytest.fixture
def test_user_profile():
    """Test user profile data from Microsoft Graph."""
    return {
        "id": "12345678-1234-1234-1234-123456789012",
        "displayName": "Test User",
        "givenName": "Test",
        "surname": "User",
        "userPrincipalName": "testuser@example.com",
        "mail": "testuser@example.com",
        "jobTitle": "Software Engineer",
        "officeLocation": "Seattle",
        "businessPhones": ["+1 206 555 0109"],
        "mobilePhone": "+1 425 555 0201"
    }


@pytest.fixture
def auth_headers(access_token):
    """Authorization headers for API requests."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_jwt_decode():
    """Mock JWT token decoding."""
    return {
        "aud": "test-client-id",
        "iss": "https://login.microsoftonline.com/tenant-id/v2.0",
        "sub": "12345678-1234-1234-1234-123456789012",
        "email": "testuser@example.com",
        "name": "Test User",
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
        "scp": "User.Read Mail.Read Mail.ReadWrite"
    }


@pytest.fixture
def auth_session_data():
    """Mock session data for authenticated user."""
    return {
        "user_id": "12345678-1234-1234-1234-123456789012",
        "email": "testuser@example.com",
        "name": "Test User",
        "access_token": "access_token_value",
        "refresh_token": "refresh_token_value",
        "token_expires_at": datetime.utcnow() + timedelta(hours=1),
        "scopes": ["User.Read", "Mail.Read", "Mail.ReadWrite"]
    }


@pytest.fixture
def mock_azure_auth_service(mock_msal_client):
    """Mock AzureAuthService with pre-configured MSAL client."""
    from unittest.mock import patch
    
    with patch('app.azure.AzureAuthService.msal.ConfidentialClientApplication') as mock_app:
        mock_app.return_value = mock_msal_client
        
        from app.azure.AzureAuthService import AzureAuthService
        return AzureAuthService()


@pytest.fixture
def oauth_error_response():
    """Mock OAuth error response."""
    return {
        "error": "access_denied",
        "error_description": "The user has denied access to the scope requested by the client application.",
        "state": "test-state-parameter"
    }


@pytest.fixture
def token_validation_success():
    """Mock successful token validation response."""
    return {
        "valid": True,
        "user_id": "12345678-1234-1234-1234-123456789012",
        "email": "testuser@example.com",
        "scopes": ["User.Read", "Mail.Read", "Mail.ReadWrite"],
        "expires_at": datetime.utcnow() + timedelta(hours=1)
    }


@pytest.fixture
def token_validation_failure():
    """Mock failed token validation response."""
    return {
        "valid": False,
        "error": "invalid_token",
        "error_description": "The access token is invalid or expired"
    }


@pytest.fixture
def mock_graph_user_response():
    """Mock Microsoft Graph user profile response."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users/$entity",
        "id": "12345678-1234-1234-1234-123456789012",
        "businessPhones": ["+1 206 555 0109"],
        "displayName": "Test User",
        "givenName": "Test",
        "jobTitle": "Software Engineer",
        "mail": "testuser@example.com",
        "mobilePhone": "+1 425 555 0201",
        "officeLocation": "Seattle",
        "preferredLanguage": "en-US",
        "surname": "User",
        "userPrincipalName": "testuser@example.com"
    }


@pytest.fixture
def azure_tenant_config():
    """Azure AD tenant configuration for testing."""
    return {
        "tenant_id": "12345678-1234-1234-1234-123456789012",
        "client_id": "87654321-4321-4321-4321-210987654321",
        "client_secret": "test-client-secret",
        "authority": "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789012",
        "redirect_uri": "http://localhost:8000/api/v1/auth/callback",
        "scopes": ["User.Read", "Mail.Read", "Mail.ReadWrite"]
    }


# Async fixtures for async testing
@pytest.fixture
async def async_mock_auth_service():
    """Async mock authentication service."""
    service = AsyncMock()
    
    service.get_authorization_url.return_value = {
        "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "state": "test-state"
    }
    
    service.acquire_token_by_auth_code.return_value = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "user_profile": {
            "id": "test-user-id",
            "email": "test@example.com",
            "name": "Test User"
        }
    }
    
    return service


@pytest.fixture
def auth_test_config():
    """Test configuration for authentication."""
    return {
        "azure_tenant_id": "test-tenant-id",
        "azure_client_id": "test-client-id",
        "azure_client_secret": "test-client-secret",
        "azure_redirect_uri": "http://localhost:8000/callback",
        "jwt_secret": "test-jwt-secret-key",
        "jwt_algorithm": "HS256",
        "jwt_expiration": 3600,
        "session_timeout": 7200
    }