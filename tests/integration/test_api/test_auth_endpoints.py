"""
Integration tests for authentication endpoints.

Tests complete OAuth authentication flow including:
- Login initiation and Azure AD redirect
- OAuth callback handling and token exchange
- Token refresh mechanisms
- Session management and logout
- User persistence in database
- Error handling for various authentication scenarios
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

import httpx
import respx

from tests.integration.utils import (
    IntegrationAPIClient, 
    ResponseAssertions, 
    DatabaseAssertions,
    TestWorkflows
)


class TestAuthenticationEndpoints:
    """Integration tests for authentication endpoints."""

    @pytest_asyncio.fixture
    async def api_client(self, authenticated_async_client):
        """Get API client wrapper for easier testing."""
        return IntegrationAPIClient(authenticated_async_client)
    
    @pytest_asyncio.fixture 
    async def db_assertions(self, integration_db_session):
        """Get database assertions helper."""
        return DatabaseAssertions(integration_db_session)
    
    @pytest_asyncio.fixture
    async def test_workflows(self, api_client, db_assertions):
        """Get test workflow helper."""
        return TestWorkflows(api_client, db_assertions)

    # =========================================================================
    # LOGIN INITIATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_login_endpoint_redirects_to_azure(self, api_client):
        """Test that login endpoint redirects to Azure AD authorization URL."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # Setup mock OAuth service
            mock_oauth.return_value.initiate_login.return_value = {
                "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=test"
            }
            
            response = await api_client.auth_login()
            
            # Should redirect to Azure AD
            assert response.status_code == 302
            redirect_url = response.headers["location"]
            assert "login.microsoftonline.com" in redirect_url
            assert "oauth2/v2.0/authorize" in redirect_url

    @pytest.mark.asyncio 
    @pytest.mark.integration
    async def test_login_initiation_failure(self, api_client):
        """Test login initiation failure handling."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # Setup mock to raise authentication error
            from app.core.Exceptions import AuthenticationError
            mock_oauth.return_value.initiate_login.side_effect = AuthenticationError(
                "Failed to initialize OAuth flow"
            )
            
            response = await api_client.auth_login()
            
            ResponseAssertions.assert_error_response(
                response, 
                expected_status=400,
                expected_message_contains="Failed to initialize OAuth flow"
            )

    # =========================================================================
    # OAUTH CALLBACK TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_oauth_callback_success(self, api_client, db_assertions):
        """Test successful OAuth callback with code exchange."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # Mock successful token response
            mock_token_response = {
                "access_token": "test-access-token-123",
                "refresh_token": "test-refresh-token-123",
                "user_info": {
                    "id": "test-user-callback-123",
                    "email": "callback@example.com",
                    "display_name": "Callback Test User",
                    "given_name": "Callback",
                    "surname": "User"
                },
                "token_type": "Bearer",
                "expires_in": 3600,
                "scopes": ["User.Read", "Mail.Read"]
            }
            
            mock_oauth.return_value.handle_callback.return_value = mock_token_response
            
            response = await api_client.auth_callback(
                code="test-auth-code-123",
                state="test-state-456"
            )
            
            ResponseAssertions.assert_success_response(response)
            
            response_data = response.json()
            assert response_data["access_token"] == "test-access-token-123"
            assert response_data["refresh_token"] == "test-refresh-token-123"
            assert response_data["user_info"]["email"] == "callback@example.com"
            
            # Verify user was persisted in database
            await db_assertions.assert_user_exists(
                "test-user-callback-123",
                email="callback@example.com",
                display_name="Callback Test User",
                is_active=True
            )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_oauth_callback_missing_code(self, api_client):
        """Test OAuth callback without authorization code."""
        response = await api_client.client.get("/api/v1/auth/callback?state=test-state")
        
        ResponseAssertions.assert_error_response(
            response,
            expected_status=400,
            expected_message_contains="Authorization code is required"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_oauth_callback_with_error(self, api_client):
        """Test OAuth callback when Azure returns error."""
        response = await api_client.client.get(
            "/api/v1/auth/callback",
            params={
                "error": "access_denied",
                "error_description": "The user has denied access",
                "state": "test-state"
            }
        )
        
        ResponseAssertions.assert_error_response(
            response,
            expected_status=400,
            expected_message_contains="The user has denied access"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_oauth_callback_invalid_code(self, api_client):
        """Test OAuth callback with invalid authorization code."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            from app.core.Exceptions import AuthenticationError
            mock_oauth.return_value.handle_callback.side_effect = AuthenticationError(
                "Invalid authorization code"
            )
            
            response = await api_client.auth_callback(
                code="invalid-code",
                state="test-state"
            )
            
            ResponseAssertions.assert_authentication_error(response)

    # =========================================================================
    # TOKEN REFRESH TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_token_refresh_success(self, api_client):
        """Test successful token refresh."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # Mock successful refresh response
            mock_refresh_response = {
                "access_token": "new-access-token-456",
                "refresh_token": "new-refresh-token-456", 
                "user_info": {
                    "id": "test-user-refresh",
                    "email": "refresh@example.com",
                    "display_name": "Refresh User"
                },
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            mock_oauth.return_value.refresh_user_token.return_value = mock_refresh_response
            
            response = await api_client.auth_refresh(
                refresh_token="old-refresh-token",
                session_id="test-session-123"
            )
            
            ResponseAssertions.assert_success_response(response)
            
            response_data = response.json()
            assert response_data["access_token"] == "new-access-token-456"
            assert response_data["refresh_token"] == "new-refresh-token-456"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_token_refresh_invalid_token(self, api_client):
        """Test token refresh with invalid refresh token."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            from app.core.Exceptions import AuthenticationError
            mock_oauth.return_value.refresh_user_token.side_effect = AuthenticationError(
                "Invalid refresh token"
            )
            
            response = await api_client.auth_refresh(
                refresh_token="invalid-refresh-token"
            )
            
            ResponseAssertions.assert_authentication_error(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_token_refresh_expired_token(self, api_client):
        """Test token refresh with expired refresh token."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            from app.core.Exceptions import AuthenticationError
            mock_oauth.return_value.refresh_user_token.side_effect = AuthenticationError(
                "Refresh token has expired"
            )
            
            response = await api_client.auth_refresh(
                refresh_token="expired-refresh-token"
            )
            
            ResponseAssertions.assert_authentication_error(response)

    # =========================================================================
    # LOGOUT TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_logout_success(self, api_client):
        """Test successful user logout."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            mock_oauth.return_value.logout.return_value = True
            
            response = await api_client.auth_logout(session_id="test-session-logout")
            
            ResponseAssertions.assert_success_response(response)
            
            response_data = response.json()
            assert response_data["success"] is True
            assert "Successfully logged out" in response_data["message"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_logout_failure(self, api_client):
        """Test logout failure handling."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            mock_oauth.return_value.logout.return_value = False
            
            response = await api_client.auth_logout(session_id="failing-session")
            
            ResponseAssertions.assert_success_response(response)
            
            response_data = response.json()
            assert response_data["success"] is False
            assert "Logout failed" in response_data["message"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_logout_exception_handling(self, api_client):
        """Test logout with exception in service."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            mock_oauth.return_value.logout.side_effect = Exception("Logout service error")
            
            response = await api_client.auth_logout()
            
            ResponseAssertions.assert_success_response(response)
            
            response_data = response.json()
            assert response_data["success"] is False
            assert "Error during logout" in response_data["message"]

    # =========================================================================
    # USER INFO TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration 
    async def test_get_current_user_authenticated(self, api_client, override_auth_dependency):
        """Test getting current user information when authenticated."""
        response = await api_client.auth_me()
        
        ResponseAssertions.assert_success_response(response)
        
        user_data = response.json()
        assert user_data["email"] == "user1@example.com"
        assert user_data["display_name"] == "John Doe"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_current_user_unauthenticated(self, authenticated_async_client):
        """Test getting current user when not authenticated."""
        # Create client without auth headers
        async with httpx.AsyncClient(app=authenticated_async_client.app, base_url="http://test") as client:
            api_client = IntegrationAPIClient(client)
            response = await api_client.auth_me()
            
            ResponseAssertions.assert_authentication_error(response)

    # =========================================================================
    # AUTHENTICATION STATUS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_auth_status_authenticated(self, api_client, override_auth_dependency):
        """Test authentication status for authenticated user."""
        response = await api_client.auth_status()
        
        ResponseAssertions.assert_success_response(response)
        
        status_data = response.json()
        assert status_data["is_authenticated"] is True
        assert status_data["user_info"] is not None
        assert status_data["user_info"]["email"] == "user1@example.com"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_auth_status_unauthenticated(self, authenticated_async_client):
        """Test authentication status for unauthenticated user."""
        # Create client without auth headers
        async with httpx.AsyncClient(app=authenticated_async_client.app, base_url="http://test") as client:
            api_client = IntegrationAPIClient(client)
            response = await api_client.auth_status()
            
            ResponseAssertions.assert_success_response(response)
            
            status_data = response.json()
            assert status_data["is_authenticated"] is False
            assert status_data["user_info"] is None

    # =========================================================================
    # COMPLETE AUTHENTICATION FLOW TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_authentication_flow(self, test_workflows):
        """Test complete authentication flow from login to logout."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # Setup comprehensive mock
            mock_oauth_instance = mock_oauth.return_value
            
            mock_oauth_instance.initiate_login.return_value = {
                "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            }
            
            mock_oauth_instance.handle_callback.return_value = {
                "access_token": "flow-access-token",
                "refresh_token": "flow-refresh-token",
                "user_info": {
                    "id": "flow-test-user",
                    "email": "flow@example.com",
                    "display_name": "Flow Test User",
                    "given_name": "Flow", 
                    "surname": "User"
                },
                "expires_in": 3600,
                "token_type": "Bearer"
            }
            
            mock_oauth_instance.logout.return_value = True
            
            # Execute complete flow
            login_response, callback_response, token_data = await test_workflows.complete_authentication_flow()
            
            # Verify login redirect
            assert login_response.status_code == 302
            assert "login.microsoftonline.com" in login_response.headers["location"]
            
            # Verify callback success
            ResponseAssertions.assert_success_response(callback_response)
            assert token_data["access_token"] == "flow-access-token"
            
            # Test logout
            logout_response = await test_workflows.api.auth_logout()
            ResponseAssertions.assert_success_response(logout_response)

    # =========================================================================
    # CONCURRENT ACCESS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_authentication_requests(self, api_client):
        """Test concurrent authentication requests."""
        import asyncio
        from tests.integration.utils import run_concurrent_requests
        
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            mock_oauth.return_value.initiate_login.return_value = {
                "auth_uri": "https://login.microsoftonline.com/test"
            }
            
            # Create multiple concurrent login requests
            requests = [
                lambda: api_client.auth_login()
                for _ in range(5)
            ]
            
            responses = await run_concurrent_requests(requests, max_concurrent=3)
            
            # All requests should succeed
            for response in responses:
                if isinstance(response, Exception):
                    pytest.fail(f"Concurrent request failed: {response}")
                assert response.status_code == 302

    # =========================================================================
    # ERROR RECOVERY TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_authentication_after_network_error(self, api_client):
        """Test authentication recovery after network errors."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # First call fails with network error
            mock_oauth.return_value.initiate_login.side_effect = [
                ConnectionError("Network error"),
                {"auth_uri": "https://login.microsoftonline.com/recovered"}
            ]
            
            # First attempt should fail
            try:
                await api_client.auth_login()
                pytest.fail("Expected network error")
            except ConnectionError:
                pass
            
            # Second attempt should succeed
            response = await api_client.auth_login()
            assert response.status_code == 302

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_token_refresh_retry_on_failure(self, api_client):
        """Test token refresh retry mechanism."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            from app.core.Exceptions import AuthenticationError
            
            # Setup retry scenario
            mock_oauth.return_value.refresh_user_token.side_effect = [
                AuthenticationError("Temporary service unavailable"),
                {
                    "access_token": "retry-success-token",
                    "user_info": {"id": "retry-user", "email": "retry@example.com"}
                }
            ]
            
            # First call fails
            response1 = await api_client.auth_refresh("test-refresh-token")
            ResponseAssertions.assert_authentication_error(response1)
            
            # Second call succeeds
            response2 = await api_client.auth_refresh("test-refresh-token")
            ResponseAssertions.assert_success_response(response2)

    # =========================================================================
    # SESSION MANAGEMENT TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_persistence_across_requests(self, api_client, db_assertions):
        """Test that user sessions persist across multiple requests."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            # Setup session data
            session_user = {
                "id": "session-test-user",
                "email": "session@example.com", 
                "display_name": "Session User"
            }
            
            mock_oauth.return_value.handle_callback.return_value = {
                "access_token": "session-token",
                "user_info": session_user
            }
            
            # Authenticate user
            auth_response = await api_client.auth_callback("session-code", "session-state")
            ResponseAssertions.assert_success_response(auth_response)
            
            # Verify user persisted
            await db_assertions.assert_user_exists(
                "session-test-user",
                email="session@example.com",
                is_active=True
            )
            
            # Multiple requests should work with same session
            for _ in range(3):
                status_response = await api_client.auth_status()
                ResponseAssertions.assert_success_response(status_response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_cleanup_on_logout(self, api_client, db_assertions):
        """Test that sessions are properly cleaned up on logout."""
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            mock_oauth.return_value.handle_callback.return_value = {
                "access_token": "cleanup-token",
                "user_info": {
                    "id": "cleanup-user",
                    "email": "cleanup@example.com"
                }
            }
            mock_oauth.return_value.logout.return_value = True
            
            # Authenticate
            await api_client.auth_callback("cleanup-code", "cleanup-state")
            
            # Verify user exists
            await db_assertions.assert_user_exists("cleanup-user")
            
            # Logout
            logout_response = await api_client.auth_logout()
            ResponseAssertions.assert_success_response(logout_response)
            
            # User should still exist but session should be cleared
            await db_assertions.assert_user_exists("cleanup-user", is_active=True)