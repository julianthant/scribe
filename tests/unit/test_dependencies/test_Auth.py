"""
test_Auth.py - Unit tests for authentication dependencies

Tests the dependency injection functions in app.dependencies.Auth including:
- get_current_user(): Bearer token authentication
- get_current_user_optional(): Optional authentication
- validate_token(): Token validation
- get_user_repository(): Repository dependency injection

All external services are mocked to ensure isolated unit testing.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies.Auth import (
    get_current_user,
    get_current_user_optional,
    validate_token,
    get_user_repository
)
from app.models.AuthModel import UserInfo
from app.core.Exceptions import AuthenticationError
from app.db.models.User import UserRole


class TestGetCurrentUser:
    """Test cases for get_current_user dependency function."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token_returns_user_info(self):
        """Test that valid token returns user information."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_access_token"
        )
        expected_user = UserInfo(
            id="test-user-id",
            display_name="Test User",
            email="test@example.com",
            given_name="Test",
            surname="User",
            role=UserRole.USER
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.return_value = expected_user

            # Act
            result = await get_current_user(credentials)

            # Assert
            assert result == expected_user
            mock_oauth.get_current_user.assert_called_once_with("valid_access_token")

    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials_raises_401(self):
        """Test that missing credentials raises 401 error."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token_raises_401(self):
        """Test that invalid token raises 401 error."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = AuthenticationError("Invalid token")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 401
            assert "Invalid or expired token" in exc_info.value.detail
            assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_get_current_user_service_error_raises_500(self):
        """Test that service errors raise 500 error."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = ValueError("Unexpected error")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == 500
            assert "Authentication service error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_logs_authentication_error(self, caplog):
        """Test that authentication errors are logged."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = AuthenticationError("Token expired")

            # Act
            with pytest.raises(HTTPException):
                await get_current_user(credentials)

            # Assert
            assert "Authentication failed: Token expired" in caplog.text

    @pytest.mark.asyncio
    async def test_get_current_user_logs_unexpected_error(self, caplog):
        """Test that unexpected errors are logged."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = RuntimeError("Service down")

            # Act
            with pytest.raises(HTTPException):
                await get_current_user(credentials)

            # Assert
            assert "Unexpected authentication error: Service down" in caplog.text


class TestGetCurrentUserOptional:
    """Test cases for get_current_user_optional dependency function."""

    @pytest.mark.asyncio
    async def test_get_current_user_optional_valid_token_returns_user_info(self):
        """Test that valid token returns user information."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_access_token"
        )
        expected_user = UserInfo(
            id="test-user-id",
            display_name="Test User",
            email="test@example.com",
            given_name="Test",
            surname="User",
            role=UserRole.USER
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.return_value = expected_user

            # Act
            result = await get_current_user_optional(credentials)

            # Assert
            assert result == expected_user
            mock_oauth.get_current_user.assert_called_once_with("valid_access_token")

    @pytest.mark.asyncio
    async def test_get_current_user_optional_no_credentials_returns_none(self):
        """Test that missing credentials returns None."""
        # Act
        result = await get_current_user_optional(None)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_invalid_token_returns_none(self):
        """Test that invalid token returns None instead of raising error."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = AuthenticationError("Invalid token")

            # Act
            result = await get_current_user_optional(credentials)

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_service_error_returns_none(self):
        """Test that service errors return None."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = ValueError("Service error")

            # Act
            result = await get_current_user_optional(credentials)

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_logs_authentication_failure(self, caplog):
        """Test that authentication failures are logged as warnings."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = AuthenticationError("Token expired")

            # Act
            await get_current_user_optional(credentials)

            # Assert
            assert "Optional authentication failed: Token expired" in caplog.text


class TestValidateToken:
    """Test cases for validate_token function."""

    def test_validate_token_valid_token_returns_true(self):
        """Test that valid token returns True."""
        # Arrange
        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.validate_access_token.return_value = True

            # Act
            result = validate_token("valid_token")

            # Assert
            assert result is True
            mock_oauth.validate_access_token.assert_called_once_with("valid_token")

    def test_validate_token_invalid_token_returns_false(self):
        """Test that invalid token returns False."""
        # Arrange
        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.validate_access_token.return_value = False

            # Act
            result = validate_token("invalid_token")

            # Assert
            assert result is False

    def test_validate_token_service_error_returns_false(self):
        """Test that service errors return False."""
        # Arrange
        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.validate_access_token.side_effect = ValueError("Service error")

            # Act
            result = validate_token("token")

            # Assert
            assert result is False

    def test_validate_token_logs_error_on_exception(self, caplog):
        """Test that validation errors are logged."""
        # Arrange
        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.validate_access_token.side_effect = RuntimeError("Connection failed")

            # Act
            result = validate_token("token")

            # Assert
            assert result is False
            assert "Token validation error: Connection failed" in caplog.text

    @pytest.mark.parametrize("token,expected", [
        ("", False),
        ("   ", False),
        (None, False),
        ("valid_token_string", True),
    ])
    def test_validate_token_various_inputs(self, token, expected):
        """Test token validation with various input types."""
        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            if token and token.strip():
                mock_oauth.validate_access_token.return_value = expected
            else:
                mock_oauth.validate_access_token.side_effect = ValueError("Invalid input")

            result = validate_token(token)
            assert result == expected


class TestGetUserRepository:
    """Test cases for get_user_repository dependency function."""

    @pytest.mark.asyncio
    async def test_get_user_repository_returns_repository_instance(self):
        """Test that function returns UserRepository instance."""
        # Arrange
        mock_db_session = AsyncMock()

        with patch('app.dependencies.Auth.UserRepository') as MockUserRepository:
            mock_repository = Mock()
            MockUserRepository.return_value = mock_repository

            # Act
            result = await get_user_repository(mock_db_session)

            # Assert
            assert result == mock_repository
            MockUserRepository.assert_called_once_with(mock_db_session)

    @pytest.mark.asyncio
    async def test_get_user_repository_uses_provided_session(self):
        """Test that function uses the provided database session."""
        # Arrange
        mock_db_session = AsyncMock()
        mock_db_session.info = {"test": "session"}

        with patch('app.dependencies.Auth.UserRepository') as MockUserRepository:
            # Act
            await get_user_repository(mock_db_session)

            # Assert
            MockUserRepository.assert_called_once_with(mock_db_session)


class TestIntegrationScenarios:
    """Integration test scenarios combining multiple dependency functions."""

    @pytest.mark.asyncio
    async def test_authentication_flow_success(self):
        """Test successful authentication flow."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )
        expected_user = UserInfo(
            id="user-123",
            display_name="John Doe",
            email="john@example.com",
            given_name="John",
            surname="Doe",
            role=UserRole.USER
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.return_value = expected_user
            mock_oauth.validate_access_token.return_value = True

            # Act - Test both required and optional authentication
            required_result = await get_current_user(credentials)
            optional_result = await get_current_user_optional(credentials)
            validation_result = validate_token("valid_token")

            # Assert
            assert required_result == expected_user
            assert optional_result == expected_user
            assert validation_result is True

    @pytest.mark.asyncio
    async def test_authentication_flow_failure(self):
        """Test failed authentication flow."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.side_effect = AuthenticationError("Invalid token")
            mock_oauth.validate_access_token.return_value = False

            # Act & Assert
            # Required auth should raise exception
            with pytest.raises(HTTPException):
                await get_current_user(credentials)

            # Optional auth should return None
            optional_result = await get_current_user_optional(credentials)
            assert optional_result is None

            # Validation should return False
            validation_result = validate_token("invalid_token")
            assert validation_result is False

    @pytest.mark.asyncio
    async def test_superuser_authentication(self):
        """Test authentication with superuser privileges."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="admin_token"
        )
        expected_user = UserInfo(
            id="admin-123",
            display_name="Admin User",
            email="admin@example.com",
            given_name="Admin",
            surname="User",
            role=UserRole.SUPERUSER,
            is_superuser=True
        )

        with patch('app.dependencies.Auth.oauth_service') as mock_oauth:
            mock_oauth.get_current_user.return_value = expected_user

            # Act
            result = await get_current_user(credentials)

            # Assert
            assert result.is_superuser is True
            assert result.role == UserRole.SUPERUSER
            assert result.email == "admin@example.com"