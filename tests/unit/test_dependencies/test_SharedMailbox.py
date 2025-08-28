"""
test_SharedMailbox.py - Unit tests for shared mailbox dependencies

Tests the dependency injection functions in app.dependencies.SharedMailbox including:
- get_shared_mailbox_repository(): Repository creation with authentication
- get_shared_mailbox_service(): Service creation with repository
- validate_shared_mailbox_access(): Access validation logic
- get_shared_mailbox_with_access_check(): Mailbox access validation
- Permission-specific access validators (read, write, send, manage)
- get_accessible_shared_mailbox_addresses(): List accessible mailboxes

All external services are mocked to ensure isolated unit testing.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies.SharedMailbox import (
    get_shared_mailbox_repository,
    get_shared_mailbox_service,
    validate_shared_mailbox_access,
    get_shared_mailbox_with_access_check,
    get_shared_mailbox_read_access,
    get_shared_mailbox_write_access,
    get_shared_mailbox_send_access,
    get_shared_mailbox_manage_access,
    get_accessible_shared_mailbox_addresses
)
from app.models.AuthModel import UserInfo
from app.core.Exceptions import AuthenticationError
from app.db.models.User import UserRole


class TestGetSharedMailboxRepository:
    """Test cases for get_shared_mailbox_repository dependency function."""

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_repository_valid_credentials_returns_repository(self):
        """Test that valid credentials return shared mailbox repository."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_access_token"
        )

        with patch('app.dependencies.SharedMailbox.SharedMailboxRepository') as MockRepository:
            mock_repository = Mock()
            MockRepository.return_value = mock_repository

            # Act
            result = await get_shared_mailbox_repository(credentials)

            # Assert
            assert result == mock_repository
            MockRepository.assert_called_once_with("valid_access_token")

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_repository_no_credentials_raises_401(self):
        """Test that missing credentials raises 401 error."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_shared_mailbox_repository(None)

        assert exc_info.value.status_code == 401
        assert "Authentication required for shared mailbox operations" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_repository_empty_token_raises_401(self):
        """Test that empty token raises 401 error."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=""
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_shared_mailbox_repository(credentials)

        assert exc_info.value.status_code == 401
        assert "Access token required for shared mailbox operations" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_repository_exception_raises_500(self):
        """Test that repository creation exception raises 500 error."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_token"
        )

        with patch('app.dependencies.SharedMailbox.SharedMailboxRepository') as MockRepository:
            MockRepository.side_effect = ValueError("Repository creation failed")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_shared_mailbox_repository(credentials)

            assert exc_info.value.status_code == 500
            assert "Failed to initialize shared mailbox repository" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_repository_logs_token_info(self, caplog):
        """Test that repository creation logs appropriate information."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="test_token_123"
        )

        with patch('app.dependencies.SharedMailbox.SharedMailboxRepository') as MockRepository:
            MockRepository.return_value = Mock()

            # Act
            await get_shared_mailbox_repository(credentials)

            # Assert
            assert "Shared mailbox dependency - credentials: True" in caplog.text
            assert "Shared mailbox dependency - access_token length: 14" in caplog.text


class TestGetSharedMailboxService:
    """Test cases for get_shared_mailbox_service dependency function."""

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_service_returns_service_with_repository(self):
        """Test that function returns SharedMailboxService with repository."""
        # Arrange
        mock_repository = Mock()

        with patch('app.dependencies.SharedMailbox.SharedMailboxService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = await get_shared_mailbox_service(mock_repository)

            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(mock_repository)

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_service_exception_raises_500(self):
        """Test that service creation exception raises 500 error."""
        # Arrange
        mock_repository = Mock()

        with patch('app.dependencies.SharedMailbox.SharedMailboxService') as MockService:
            MockService.side_effect = RuntimeError("Service creation failed")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_shared_mailbox_service(mock_repository)

            assert exc_info.value.status_code == 500
            assert "Failed to initialize shared mailbox service" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_service_uses_provided_repository(self):
        """Test that service is created with the provided repository."""
        # Arrange
        mock_repository = Mock()
        mock_repository.access_token = "test_token"

        with patch('app.dependencies.SharedMailbox.SharedMailboxService') as MockService:
            MockService.return_value = Mock()

            # Act
            await get_shared_mailbox_service(mock_repository)

            # Assert
            MockService.assert_called_once_with(mock_repository)


class TestValidateSharedMailboxAccess:
    """Test cases for validate_shared_mailbox_access dependency function."""

    @pytest.mark.asyncio
    async def test_validate_shared_mailbox_access_success_returns_true(self):
        """Test successful access validation returns True."""
        # Arrange
        email_address = "shared@example.com"
        operation = "read"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service._validate_mailbox_access = AsyncMock()

        # Act
        result = await validate_shared_mailbox_access(
            email_address, operation, current_user, mock_service
        )

        # Assert
        assert result is True
        mock_service._validate_mailbox_access.assert_called_once_with(email_address, operation)

    @pytest.mark.asyncio
    async def test_validate_shared_mailbox_access_auth_error_raises_401(self):
        """Test that authentication error raises 401."""
        # Arrange
        email_address = "shared@example.com"
        operation = "write"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service._validate_mailbox_access.side_effect = AuthenticationError("Access denied")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await validate_shared_mailbox_access(
                email_address, operation, current_user, mock_service
            )

        assert exc_info.value.status_code == 401
        assert "Access denied" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_validate_shared_mailbox_access_general_error_raises_403(self):
        """Test that general error raises 403."""
        # Arrange
        email_address = "shared@example.com"
        operation = "manage"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service._validate_mailbox_access.side_effect = ValueError("Unexpected error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await validate_shared_mailbox_access(
                email_address, operation, current_user, mock_service
            )

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail

    @pytest.mark.parametrize("operation", ["read", "write", "send", "manage"])
    @pytest.mark.asyncio
    async def test_validate_shared_mailbox_access_various_operations(self, operation):
        """Test access validation with various operation types."""
        # Arrange
        email_address = "shared@example.com"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service._validate_mailbox_access = AsyncMock()

        # Act
        result = await validate_shared_mailbox_access(
            email_address, operation, current_user, mock_service
        )

        # Assert
        assert result is True
        mock_service._validate_mailbox_access.assert_called_once_with(email_address, operation)


class TestGetSharedMailboxWithAccessCheck:
    """Test cases for get_shared_mailbox_with_access_check dependency function."""

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_with_access_check_success_returns_email(self):
        """Test successful access check returns email address."""
        # Arrange
        email_address = "shared@example.com"
        operation = "read"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service.get_shared_mailbox_details = AsyncMock()
        mock_service._validate_mailbox_access = AsyncMock()

        # Mock validate_shared_mailbox_access function
        with patch('app.dependencies.SharedMailbox.validate_shared_mailbox_access') as mock_validate:
            mock_validate.return_value = True

            # Act
            result = await get_shared_mailbox_with_access_check(
                email_address, operation, current_user, mock_service
            )

            # Assert
            assert result == email_address
            mock_service.get_shared_mailbox_details.assert_called_once_with(email_address)
            mock_validate.assert_called_once_with(email_address, operation, current_user, mock_service)

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_with_access_check_mailbox_not_found_raises_exception(self):
        """Test that mailbox not found raises exception."""
        # Arrange
        email_address = "nonexistent@example.com"
        operation = "read"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service.get_shared_mailbox_details.side_effect = ValueError("Mailbox not found")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_shared_mailbox_with_access_check(
                email_address, operation, current_user, mock_service
            )

        assert exc_info.value.status_code == 403
        assert "Mailbox access denied" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_with_access_check_validation_fails_raises_exception(self):
        """Test that validation failure raises exception."""
        # Arrange
        email_address = "shared@example.com"
        operation = "manage"
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        mock_service = AsyncMock()
        mock_service.get_shared_mailbox_details = AsyncMock()

        # Mock validate_shared_mailbox_access to raise exception
        with patch('app.dependencies.SharedMailbox.validate_shared_mailbox_access') as mock_validate:
            mock_validate.side_effect = HTTPException(status_code=403, detail="Access denied")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await get_shared_mailbox_with_access_check(
                    email_address, operation, current_user, mock_service
                )

            assert exc_info.value.status_code == 403


class TestPermissionSpecificAccessValidators:
    """Test cases for permission-specific access validator functions."""

    @pytest.fixture
    def current_user(self):
        """Create a test user fixture."""
        return UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )

    @pytest.fixture
    def mock_service(self):
        """Create a mock shared mailbox service."""
        service = AsyncMock()
        service.get_shared_mailbox_details = AsyncMock()
        service._validate_mailbox_access = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_read_access_success(self, current_user, mock_service):
        """Test successful read access validation."""
        email_address = "shared@example.com"

        with patch('app.dependencies.SharedMailbox.get_shared_mailbox_with_access_check') as mock_check:
            mock_check.return_value = email_address

            # Act
            result = await get_shared_mailbox_read_access(email_address, current_user, mock_service)

            # Assert
            assert result == email_address
            mock_check.assert_called_once_with(email_address, "read", current_user, mock_service)

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_write_access_success(self, current_user, mock_service):
        """Test successful write access validation."""
        email_address = "shared@example.com"

        with patch('app.dependencies.SharedMailbox.get_shared_mailbox_with_access_check') as mock_check:
            mock_check.return_value = email_address

            # Act
            result = await get_shared_mailbox_write_access(email_address, current_user, mock_service)

            # Assert
            assert result == email_address
            mock_check.assert_called_once_with(email_address, "write", current_user, mock_service)

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_send_access_success(self, current_user, mock_service):
        """Test successful send access validation."""
        email_address = "shared@example.com"

        with patch('app.dependencies.SharedMailbox.get_shared_mailbox_with_access_check') as mock_check:
            mock_check.return_value = email_address

            # Act
            result = await get_shared_mailbox_send_access(email_address, current_user, mock_service)

            # Assert
            assert result == email_address
            mock_check.assert_called_once_with(email_address, "send", current_user, mock_service)

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_manage_access_success(self, current_user, mock_service):
        """Test successful manage access validation."""
        email_address = "shared@example.com"

        with patch('app.dependencies.SharedMailbox.get_shared_mailbox_with_access_check') as mock_check:
            mock_check.return_value = email_address

            # Act
            result = await get_shared_mailbox_manage_access(email_address, current_user, mock_service)

            # Assert
            assert result == email_address
            mock_check.assert_called_once_with(email_address, "manage", current_user, mock_service)

    @pytest.mark.parametrize("access_function,operation", [
        (get_shared_mailbox_read_access, "read"),
        (get_shared_mailbox_write_access, "write"),
        (get_shared_mailbox_send_access, "send"),
        (get_shared_mailbox_manage_access, "manage"),
    ])
    @pytest.mark.asyncio
    async def test_permission_specific_validators_call_correct_operation(
        self, access_function, operation, current_user, mock_service
    ):
        """Test that each validator calls the correct operation type."""
        email_address = "shared@example.com"

        with patch('app.dependencies.SharedMailbox.get_shared_mailbox_with_access_check') as mock_check:
            mock_check.return_value = email_address

            # Act
            await access_function(email_address, current_user, mock_service)

            # Assert
            mock_check.assert_called_once_with(email_address, operation, current_user, mock_service)


class TestGetAccessibleSharedMailboxAddresses:
    """Test cases for get_accessible_shared_mailbox_addresses dependency function."""

    @pytest.mark.asyncio
    async def test_get_accessible_shared_mailbox_addresses_success(self):
        """Test successful retrieval of accessible mailbox addresses."""
        # Arrange
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        
        # Mock mailbox objects
        mock_mailbox1 = Mock()
        mock_mailbox1.emailAddress = "shared1@example.com"
        mock_mailbox2 = Mock()
        mock_mailbox2.emailAddress = "shared2@example.com"
        
        mock_response = Mock()
        mock_response.value = [mock_mailbox1, mock_mailbox2]
        
        mock_service = AsyncMock()
        mock_service.get_accessible_shared_mailboxes.return_value = mock_response

        # Act
        result = await get_accessible_shared_mailbox_addresses(current_user, mock_service)

        # Assert
        expected_addresses = ["shared1@example.com", "shared2@example.com"]
        assert result == expected_addresses
        mock_service.get_accessible_shared_mailboxes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_accessible_shared_mailbox_addresses_empty_list(self):
        """Test handling of empty mailbox list."""
        # Arrange
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        
        mock_response = Mock()
        mock_response.value = []
        
        mock_service = AsyncMock()
        mock_service.get_accessible_shared_mailboxes.return_value = mock_response

        # Act
        result = await get_accessible_shared_mailbox_addresses(current_user, mock_service)

        # Assert
        assert result == []
        mock_service.get_accessible_shared_mailboxes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_accessible_shared_mailbox_addresses_service_error_raises_500(self):
        """Test that service error raises 500."""
        # Arrange
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        
        mock_service = AsyncMock()
        mock_service.get_accessible_shared_mailboxes.side_effect = ValueError("Service error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_accessible_shared_mailbox_addresses(current_user, mock_service)

        assert exc_info.value.status_code == 500
        assert "Failed to retrieve accessible mailboxes" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_accessible_shared_mailbox_addresses_logs_error(self, caplog):
        """Test that service errors are logged."""
        # Arrange
        current_user = UserInfo(
            id="user-123",
            display_name="Test User",
            email="test@example.com",
            role=UserRole.USER
        )
        
        mock_service = AsyncMock()
        mock_service.get_accessible_shared_mailboxes.side_effect = RuntimeError("Connection failed")

        # Act
        with pytest.raises(HTTPException):
            await get_accessible_shared_mailbox_addresses(current_user, mock_service)

        # Assert
        assert "Failed to get accessible mailbox addresses: Connection failed" in caplog.text


class TestIntegrationScenarios:
    """Integration test scenarios for shared mailbox dependencies."""

    @pytest.mark.asyncio
    async def test_complete_shared_mailbox_dependency_chain(self):
        """Test the complete dependency chain from credentials to service."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="integration_token"
        )

        with patch('app.dependencies.SharedMailbox.SharedMailboxRepository') as MockRepository:
            with patch('app.dependencies.SharedMailbox.SharedMailboxService') as MockService:
                mock_repository = Mock()
                mock_service = Mock()
                MockRepository.return_value = mock_repository
                MockService.return_value = mock_service

                # Act
                repository = await get_shared_mailbox_repository(credentials)
                service = await get_shared_mailbox_service(repository)

                # Assert
                assert repository == mock_repository
                assert service == mock_service
                MockRepository.assert_called_once_with("integration_token")
                MockService.assert_called_once_with(mock_repository)

    @pytest.mark.asyncio
    async def test_permission_hierarchy_validation(self):
        """Test that different permission levels work correctly."""
        # Arrange
        email_address = "shared@example.com"
        current_user = UserInfo(
            id="admin-123",
            display_name="Admin User",
            email="admin@example.com",
            role=UserRole.ADMIN,
            is_superuser=True
        )
        mock_service = AsyncMock()
        
        # Mock successful validations
        with patch('app.dependencies.SharedMailbox.get_shared_mailbox_with_access_check') as mock_check:
            mock_check.return_value = email_address

            # Act - Test all permission levels
            read_result = await get_shared_mailbox_read_access(email_address, current_user, mock_service)
            write_result = await get_shared_mailbox_write_access(email_address, current_user, mock_service)
            send_result = await get_shared_mailbox_send_access(email_address, current_user, mock_service)
            manage_result = await get_shared_mailbox_manage_access(email_address, current_user, mock_service)

            # Assert
            assert all(result == email_address for result in [read_result, write_result, send_result, manage_result])
            
            # Verify correct operations were called
            expected_calls = [
                ((email_address, "read", current_user, mock_service),),
                ((email_address, "write", current_user, mock_service),),
                ((email_address, "send", current_user, mock_service),),
                ((email_address, "manage", current_user, mock_service),),
            ]
            assert mock_check.call_args_list == expected_calls

    @pytest.mark.asyncio
    async def test_error_propagation_through_dependency_chain(self):
        """Test that errors properly propagate through the dependency chain."""
        # Test repository creation failure
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )

        with patch('app.dependencies.SharedMailbox.SharedMailboxRepository') as MockRepository:
            MockRepository.side_effect = ValueError("Repository failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_shared_mailbox_repository(credentials)

            assert exc_info.value.status_code == 500

        # Test service creation failure
        mock_repository = Mock()
        with patch('app.dependencies.SharedMailbox.SharedMailboxService') as MockService:
            MockService.side_effect = RuntimeError("Service failed")

            with pytest.raises(HTTPException) as exc_info:
                await get_shared_mailbox_service(mock_repository)

            assert exc_info.value.status_code == 500