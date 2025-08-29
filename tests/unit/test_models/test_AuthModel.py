"""
test_AuthModel.py - Unit tests for authentication Pydantic models

Tests all authentication models in app.models.AuthModel including:
- UserInfo: Azure AD user information model
- TokenResponse: OAuth token response model
- AuthStatus: Authentication status model
- LoginResponse: Login initiation response model
- LogoutResponse: Logout confirmation response model
- RefreshTokenRequest: Token refresh request model

Tests include validation, serialization, field constraints, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from pydantic import ValidationError

from app.models.AuthModel import (
    UserInfo,
    TokenResponse,
    AuthStatus,
    LoginResponse,
    LogoutResponse,
    RefreshTokenRequest
)
from app.db.models.User import UserRole


class TestUserInfo:
    """Test cases for UserInfo model."""

    def test_user_info_valid_data_creates_instance(self):
        """Test that valid data creates UserInfo instance."""
        # Arrange
        user_data = {
            "id": "test-user-123",
            "display_name": "John Doe",
            "email": "john.doe@example.com",
            "given_name": "John",
            "surname": "Doe",
            "role": UserRole.USER,
            "is_superuser": False
        }

        # Act
        user_info = UserInfo(**user_data)

        # Assert
        assert user_info.id == "test-user-123"
        assert user_info.display_name == "John Doe"
        assert user_info.email == "john.doe@example.com"
        assert user_info.given_name == "John"
        assert user_info.surname == "Doe"
        assert user_info.role == UserRole.USER
        assert user_info.is_superuser is False

    def test_user_info_minimal_required_data(self):
        """Test UserInfo with only required fields."""
        # Arrange
        minimal_data = {
            "id": "minimal-user",
            "email": "minimal@example.com"
        }

        # Act
        user_info = UserInfo(**minimal_data)

        # Assert
        assert user_info.id == "minimal-user"
        assert user_info.email == "minimal@example.com"
        assert user_info.display_name == ""  # Default value
        assert user_info.given_name == ""    # Default value
        assert user_info.surname == ""       # Default value
        assert user_info.role == UserRole.USER  # Default value
        assert user_info.is_superuser is False  # Default value

    def test_user_info_invalid_email_raises_validation_error(self):
        """Test that invalid email raises ValidationError."""
        # Arrange
        invalid_data = {
            "id": "test-user",
            "email": "invalid-email-format"
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            UserInfo(**invalid_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("email",)
        assert "value is not a valid email address" in errors[0]["msg"]

    def test_user_info_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing id
        with pytest.raises(ValidationError) as exc_info:
            UserInfo(email="test@example.com")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)

        # Test missing email
        with pytest.raises(ValidationError) as exc_info:
            UserInfo(id="test-user")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)

    def test_user_info_admin_role_and_superuser(self):
        """Test UserInfo with admin role and superuser privileges."""
        # Arrange
        admin_data = {
            "id": "admin-user-456",
            "email": "admin@example.com",
            "display_name": "Admin User",
            "role": UserRole.SUPERUSER,
            "is_superuser": True
        }

        # Act
        user_info = UserInfo(**admin_data)

        # Assert
        assert user_info.role == UserRole.SUPERUSER
        assert user_info.is_superuser is True
        assert user_info.email == "admin@example.com"

    @pytest.mark.parametrize("role", [UserRole.USER, UserRole.SUPERUSER])
    def test_user_info_various_roles(self, role):
        """Test UserInfo with various role types."""
        # Arrange
        user_data = {
            "id": f"user-{role.value}",
            "email": f"{role.value}@example.com",
            "role": role
        }

        # Act
        user_info = UserInfo(**user_data)

        # Assert
        assert user_info.role == role

    def test_user_info_serialization(self):
        """Test UserInfo serialization to dict."""
        # Arrange
        user_data = {
            "id": "serialize-test",
            "email": "serialize@example.com",
            "display_name": "Serialize Test",
            "role": UserRole.USER
        }
        user_info = UserInfo(**user_data)

        # Act
        serialized = user_info.model_dump()

        # Assert
        assert serialized["id"] == "serialize-test"
        assert serialized["email"] == "serialize@example.com"
        assert serialized["display_name"] == "Serialize Test"
        assert serialized["role"] == UserRole.USER

    def test_user_info_json_serialization(self):
        """Test UserInfo JSON serialization."""
        # Arrange
        user_data = {
            "id": "json-test",
            "email": "json@example.com",
            "role": UserRole.SUPERUSER
        }
        user_info = UserInfo(**user_data)

        # Act
        json_str = user_info.model_dump_json()

        # Assert
        assert '"id":"json-test"' in json_str
        assert '"email":"json@example.com"' in json_str


class TestTokenResponse:
    """Test cases for TokenResponse model."""

    def test_token_response_valid_data_creates_instance(self):
        """Test that valid data creates TokenResponse instance."""
        # Arrange
        user_info = UserInfo(id="test-user", email="test@example.com")
        token_data = {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test",
            "refresh_token": "refresh_token_value",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "User.Read Mail.Read",
            "user_info": user_info,
            "session_id": "session-123"
        }

        # Act
        token_response = TokenResponse(**token_data)

        # Assert
        assert token_response.access_token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test"
        assert token_response.refresh_token == "refresh_token_value"
        assert token_response.token_type == "Bearer"
        assert token_response.expires_in == 3600
        assert token_response.scope == "User.Read Mail.Read"
        assert token_response.user_info == user_info
        assert token_response.session_id == "session-123"

    def test_token_response_minimal_required_data(self):
        """Test TokenResponse with only required fields."""
        # Arrange
        user_info = UserInfo(id="minimal-user", email="minimal@example.com")
        minimal_data = {
            "access_token": "test_access_token",
            "expires_in": 1800,
            "user_info": user_info
        }

        # Act
        token_response = TokenResponse(**minimal_data)

        # Assert
        assert token_response.access_token == "test_access_token"
        assert token_response.expires_in == 1800
        assert token_response.user_info == user_info
        assert token_response.refresh_token is None  # Default
        assert token_response.token_type == "Bearer"  # Default
        assert token_response.scope == ""  # Default
        assert token_response.session_id is None  # Default

    def test_token_response_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing access_token
        user_info = UserInfo(id="test-user", email="test@example.com")
        
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(expires_in=3600, user_info=user_info)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("access_token",) for error in errors)

        # Test missing expires_in
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(access_token="token", user_info=user_info)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("expires_in",) for error in errors)

        # Test missing user_info
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(access_token="token", expires_in=3600)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("user_info",) for error in errors)

    def test_token_response_invalid_expires_in_type(self):
        """Test that invalid expires_in type raises ValidationError."""
        # Arrange
        user_info = UserInfo(id="test-user", email="test@example.com")
        invalid_data = {
            "access_token": "test_token",
            "expires_in": "invalid_string",  # Should be int
            "user_info": user_info
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(**invalid_data)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("expires_in",) for error in errors)

    def test_token_response_with_nested_user_info_validation(self):
        """Test TokenResponse validation with invalid nested UserInfo."""
        # Arrange
        invalid_token_data = {
            "access_token": "test_token",
            "expires_in": 3600,
            "user_info": {
                "id": "test-user",
                "email": "invalid-email"  # Invalid email format
            }
        }

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(**invalid_token_data)

        errors = exc_info.value.errors()
        assert any("user_info" in error["loc"] for error in errors)


class TestAuthStatus:
    """Test cases for AuthStatus model."""

    def test_auth_status_authenticated_user(self):
        """Test AuthStatus with authenticated user."""
        # Arrange
        user_info = UserInfo(id="auth-user", email="auth@example.com")
        expires_at = datetime.utcnow() + timedelta(hours=1)
        auth_data = {
            "is_authenticated": True,
            "user_info": user_info,
            "expires_at": expires_at
        }

        # Act
        auth_status = AuthStatus(**auth_data)

        # Assert
        assert auth_status.is_authenticated is True
        assert auth_status.user_info == user_info
        assert auth_status.expires_at == expires_at

    def test_auth_status_unauthenticated_user(self):
        """Test AuthStatus with unauthenticated user."""
        # Arrange
        auth_data = {
            "is_authenticated": False
        }

        # Act
        auth_status = AuthStatus(**auth_data)

        # Assert
        assert auth_status.is_authenticated is False
        assert auth_status.user_info is None  # Default
        assert auth_status.expires_at is None  # Default

    def test_auth_status_missing_required_field_raises_validation_error(self):
        """Test that missing is_authenticated raises ValidationError."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            AuthStatus()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("is_authenticated",) for error in errors)


class TestLoginResponse:
    """Test cases for LoginResponse model."""

    def test_login_response_valid_data_creates_instance(self):
        """Test that valid data creates LoginResponse instance."""
        # Arrange
        login_data = {
            "auth_url": "https://login.microsoftonline.com/oauth2/v2.0/authorize",
            "state": "csrf-protection-state-123"
        }

        # Act
        login_response = LoginResponse(**login_data)

        # Assert
        assert login_response.auth_url == "https://login.microsoftonline.com/oauth2/v2.0/authorize"
        assert login_response.state == "csrf-protection-state-123"

    def test_login_response_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing auth_url
        with pytest.raises(ValidationError) as exc_info:
            LoginResponse(state="test-state")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("auth_url",) for error in errors)

        # Test missing state
        with pytest.raises(ValidationError) as exc_info:
            LoginResponse(auth_url="https://example.com")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("state",) for error in errors)

    def test_login_response_empty_string_validation(self):
        """Test LoginResponse with empty string values."""
        # Arrange
        login_data = {
            "auth_url": "",
            "state": ""
        }

        # Act - Should create instance with empty strings
        login_response = LoginResponse(**login_data)

        # Assert
        assert login_response.auth_url == ""
        assert login_response.state == ""


class TestLogoutResponse:
    """Test cases for LogoutResponse model."""

    def test_logout_response_valid_data_creates_instance(self):
        """Test that valid data creates LogoutResponse instance."""
        # Arrange
        logout_data = {
            "success": True,
            "message": "User logged out successfully"
        }

        # Act
        logout_response = LogoutResponse(**logout_data)

        # Assert
        assert logout_response.success is True
        assert logout_response.message == "User logged out successfully"

    def test_logout_response_with_default_message(self):
        """Test LogoutResponse with default message."""
        # Arrange
        logout_data = {
            "success": True
        }

        # Act
        logout_response = LogoutResponse(**logout_data)

        # Assert
        assert logout_response.success is True
        assert logout_response.message == "Successfully logged out"  # Default value

    def test_logout_response_failure_case(self):
        """Test LogoutResponse for failure case."""
        # Arrange
        logout_data = {
            "success": False,
            "message": "Logout failed: session expired"
        }

        # Act
        logout_response = LogoutResponse(**logout_data)

        # Assert
        assert logout_response.success is False
        assert logout_response.message == "Logout failed: session expired"

    def test_logout_response_missing_required_field_raises_validation_error(self):
        """Test that missing success field raises ValidationError."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            LogoutResponse(message="Test message")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("success",) for error in errors)


class TestRefreshTokenRequest:
    """Test cases for RefreshTokenRequest model."""

    def test_refresh_token_request_valid_data_creates_instance(self):
        """Test that valid data creates RefreshTokenRequest instance."""
        # Arrange
        request_data = {
            "refresh_token": "valid_refresh_token_123",
            "session_id": "session-456"
        }

        # Act
        refresh_request = RefreshTokenRequest(**request_data)

        # Assert
        assert refresh_request.refresh_token == "valid_refresh_token_123"
        assert refresh_request.session_id == "session-456"

    def test_refresh_token_request_minimal_data(self):
        """Test RefreshTokenRequest with only required field."""
        # Arrange
        request_data = {
            "refresh_token": "minimal_refresh_token"
        }

        # Act
        refresh_request = RefreshTokenRequest(**request_data)

        # Assert
        assert refresh_request.refresh_token == "minimal_refresh_token"
        assert refresh_request.session_id is None  # Default

    def test_refresh_token_request_missing_required_field_raises_validation_error(self):
        """Test that missing refresh_token raises ValidationError."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            RefreshTokenRequest(session_id="test-session")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("refresh_token",) for error in errors)

    def test_refresh_token_request_empty_token_validation(self):
        """Test RefreshTokenRequest with empty refresh_token."""
        # Arrange
        request_data = {
            "refresh_token": ""
        }

        # Act - Should create instance with empty string
        refresh_request = RefreshTokenRequest(**request_data)

        # Assert
        assert refresh_request.refresh_token == ""


class TestModelIntegration:
    """Integration tests for model interactions."""

    def test_token_response_with_admin_user_info(self):
        """Test TokenResponse containing admin UserInfo."""
        # Arrange
        admin_user = UserInfo(
            id="admin-123",
            email="admin@example.com",
            display_name="Admin User",
            role=UserRole.SUPERUSER,
            is_superuser=True
        )
        token_data = {
            "access_token": "admin_access_token",
            "expires_in": 7200,
            "user_info": admin_user
        }

        # Act
        token_response = TokenResponse(**token_data)

        # Assert
        assert token_response.user_info.role == UserRole.SUPERUSER
        assert token_response.user_info.is_superuser is True
        assert token_response.user_info.email == "admin@example.com"

    def test_auth_status_with_expired_token(self):
        """Test AuthStatus with expired token timestamp."""
        # Arrange
        user_info = UserInfo(id="expired-user", email="expired@example.com")
        expired_time = datetime.utcnow() - timedelta(minutes=30)  # 30 minutes ago
        auth_data = {
            "is_authenticated": False,  # Should be False for expired token
            "user_info": user_info,
            "expires_at": expired_time
        }

        # Act
        auth_status = AuthStatus(**auth_data)

        # Assert
        assert auth_status.is_authenticated is False
        assert auth_status.expires_at < datetime.utcnow()

    def test_complete_authentication_flow_models(self):
        """Test complete authentication flow using all models."""
        # 1. Login initiation
        login_response = LoginResponse(
            auth_url="https://login.microsoftonline.com/auth",
            state="flow-state-123"
        )

        # 2. Token response after successful auth
        user_info = UserInfo(
            id="flow-user-123",
            email="flow@example.com",
            display_name="Flow User"
        )
        token_response = TokenResponse(
            access_token="flow_access_token",
            refresh_token="flow_refresh_token",
            expires_in=3600,
            user_info=user_info,
            session_id="flow-session-123"
        )

        # 3. Auth status check
        auth_status = AuthStatus(
            is_authenticated=True,
            user_info=user_info,
            expires_at=datetime.utcnow() + timedelta(seconds=3600)
        )

        # 4. Token refresh
        refresh_request = RefreshTokenRequest(
            refresh_token=token_response.refresh_token,
            session_id=token_response.session_id
        )

        # 5. Logout
        logout_response = LogoutResponse(
            success=True,
            message="User flow@example.com logged out successfully"
        )

        # Assert all models work together
        assert login_response.state == "flow-state-123"
        assert token_response.user_info.email == "flow@example.com"
        assert auth_status.user_info == user_info
        assert refresh_request.refresh_token == "flow_refresh_token"
        assert logout_response.success is True


class TestModelValidationEdgeCases:
    """Test edge cases and validation scenarios."""

    @pytest.mark.parametrize("email", [
        "test@example.com",
        "user+label@domain.co.uk",
        "a@b.c",  # Minimal valid email
        "very.long.email.address@very.long.domain.name.com"
    ])
    def test_user_info_valid_email_formats(self, email):
        """Test UserInfo with various valid email formats."""
        # Arrange & Act
        user_info = UserInfo(id="test-user", email=email)

        # Assert
        assert user_info.email == email

    @pytest.mark.parametrize("invalid_email", [
        "invalid-email",
        "@domain.com",
        "user@",
        "user space@domain.com",
        "",
    ])
    def test_user_info_invalid_email_formats(self, invalid_email):
        """Test UserInfo with various invalid email formats."""
        # Act & Assert
        with pytest.raises(ValidationError):
            UserInfo(id="test-user", email=invalid_email)

    def test_token_response_negative_expires_in(self):
        """Test TokenResponse with negative expires_in value."""
        # Arrange
        user_info = UserInfo(id="test-user", email="test@example.com")
        token_data = {
            "access_token": "test_token",
            "expires_in": -100,  # Negative value
            "user_info": user_info
        }

        # Act - Should create instance (no validation constraint on negative values)
        token_response = TokenResponse(**token_data)

        # Assert
        assert token_response.expires_in == -100

    def test_model_field_descriptions_present(self):
        """Test that all models have proper field descriptions."""
        # Test UserInfo field descriptions
        user_info_fields = UserInfo.model_fields
        assert "Azure AD user ID" in user_info_fields["id"].description
        assert "User's email address" in user_info_fields["email"].description

        # Test TokenResponse field descriptions
        token_fields = TokenResponse.model_fields
        assert "Access token for API calls" in token_fields["access_token"].description
        assert "Token expiration time in seconds" in token_fields["expires_in"].description

        # Test AuthStatus field descriptions
        auth_fields = AuthStatus.model_fields
        assert "Whether user is authenticated" in auth_fields["is_authenticated"].description