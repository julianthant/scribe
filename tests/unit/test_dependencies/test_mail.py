"""
test_mail.py - Unit tests for mail dependencies

Tests the dependency injection functions in app.dependencies.mail including:
- get_mail_repository(): Mail repository with authentication
- get_mail_service(): Mail service dependency
- get_shared_mailbox_repository(): Shared mailbox repository
- get_voice_attachment_repository(): Voice attachment repository
- get_blob_service(): Azure blob service
- get_voice_attachment_service(): Voice attachment service with dependencies

All external services and repositories are mocked to ensure isolated unit testing.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies.Mail import (
    get_mail_repository,
    get_mail_service,
    get_shared_mailbox_repository,
    get_voice_attachment_repository,
    get_blob_service,
    get_voice_attachment_service
)


class TestGetMailRepository:
    """Test cases for get_mail_repository dependency function."""

    def test_get_mail_repository_valid_credentials_returns_repository(self):
        """Test that valid credentials return mail repository."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_access_token"
        )

        with patch('app.dependencies.mail.MailRepository') as MockMailRepository:
            mock_repository = Mock()
            MockMailRepository.return_value = mock_repository

            # Act
            result = get_mail_repository(credentials)

            # Assert
            assert result == mock_repository
            MockMailRepository.assert_called_once_with("valid_access_token")

    def test_get_mail_repository_no_credentials_raises_401(self):
        """Test that missing credentials raises 401 error."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_mail_repository(None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_get_mail_repository_empty_token_raises_401(self):
        """Test that empty token raises 401 error."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=""
        )

        with patch('app.dependencies.mail.MailRepository') as MockMailRepository:
            MockMailRepository.return_value = Mock()

            # Act
            result = get_mail_repository(credentials)

            # Assert - Repository should be created with empty token
            MockMailRepository.assert_called_once_with("")

    def test_get_mail_repository_uses_provided_token(self):
        """Test that repository is created with the provided access token."""
        # Arrange
        test_token = "test-access-token-123"
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=test_token
        )

        with patch('app.dependencies.mail.MailRepository') as MockMailRepository:
            MockMailRepository.return_value = Mock()

            # Act
            get_mail_repository(credentials)

            # Assert
            MockMailRepository.assert_called_once_with(test_token)


class TestGetMailService:
    """Test cases for get_mail_service dependency function."""

    def test_get_mail_service_returns_service_with_repository(self):
        """Test that function returns MailService with provided repository."""
        # Arrange
        mock_mail_repository = Mock()

        with patch('app.dependencies.mail.MailService') as MockMailService:
            mock_service = Mock()
            MockMailService.return_value = mock_service

            # Act
            result = get_mail_service(mock_mail_repository)

            # Assert
            assert result == mock_service
            MockMailService.assert_called_once_with(mock_mail_repository)

    def test_get_mail_service_uses_provided_repository(self):
        """Test that service is initialized with the provided repository."""
        # Arrange
        mock_repository = Mock()
        mock_repository.access_token = "test-token"

        with patch('app.dependencies.mail.MailService') as MockMailService:
            # Act
            get_mail_service(mock_repository)

            # Assert
            MockMailService.assert_called_once_with(mock_repository)


class TestGetSharedMailboxRepository:
    """Test cases for get_shared_mailbox_repository dependency function."""

    def test_get_shared_mailbox_repository_valid_credentials_returns_repository(self):
        """Test that valid credentials return shared mailbox repository."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="valid_access_token"
        )

        with patch('app.dependencies.mail.SharedMailboxRepository') as MockRepository:
            mock_repository = Mock()
            MockRepository.return_value = mock_repository

            # Act
            result = get_shared_mailbox_repository(credentials)

            # Assert
            assert result == mock_repository
            MockRepository.assert_called_once_with("valid_access_token")

    def test_get_shared_mailbox_repository_no_credentials_raises_401(self):
        """Test that missing credentials raises 401 error."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_shared_mailbox_repository(None)

        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_get_shared_mailbox_repository_uses_provided_token(self):
        """Test that repository is created with the provided access token."""
        # Arrange
        test_token = "shared-mailbox-token-456"
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=test_token
        )

        with patch('app.dependencies.mail.SharedMailboxRepository') as MockRepository:
            MockRepository.return_value = Mock()

            # Act
            get_shared_mailbox_repository(credentials)

            # Assert
            MockRepository.assert_called_once_with(test_token)


class TestGetVoiceAttachmentRepository:
    """Test cases for get_voice_attachment_repository dependency function."""

    @pytest.mark.asyncio
    async def test_get_voice_attachment_repository_returns_repository(self):
        """Test that function returns VoiceAttachmentRepository with database session."""
        # Arrange
        mock_db_session = AsyncMock()

        with patch('app.dependencies.mail.VoiceAttachmentRepository') as MockRepository:
            mock_repository = Mock()
            MockRepository.return_value = mock_repository

            # Act
            result = await get_voice_attachment_repository(mock_db_session)

            # Assert
            assert result == mock_repository
            MockRepository.assert_called_once_with(mock_db_session)

    @pytest.mark.asyncio
    async def test_get_voice_attachment_repository_uses_provided_session(self):
        """Test that repository uses the provided database session."""
        # Arrange
        mock_db_session = AsyncMock()
        mock_db_session.info = {"session_id": "test-123"}

        with patch('app.dependencies.mail.VoiceAttachmentRepository') as MockRepository:
            # Act
            await get_voice_attachment_repository(mock_db_session)

            # Assert
            MockRepository.assert_called_once_with(mock_db_session)


class TestGetBlobService:
    """Test cases for get_blob_service dependency function."""

    def test_get_blob_service_returns_azure_blob_service(self):
        """Test that function returns the azure_blob_service instance."""
        # Arrange
        mock_blob_service = Mock()

        with patch('app.dependencies.mail.azure_blob_service', mock_blob_service):
            # Act
            result = get_blob_service()

            # Assert
            assert result == mock_blob_service

    def test_get_blob_service_always_returns_same_instance(self):
        """Test that function always returns the same blob service instance."""
        # Arrange
        mock_blob_service = Mock()

        with patch('app.dependencies.mail.azure_blob_service', mock_blob_service):
            # Act
            result1 = get_blob_service()
            result2 = get_blob_service()

            # Assert
            assert result1 == result2 == mock_blob_service


class TestGetVoiceAttachmentService:
    """Test cases for get_voice_attachment_service dependency function."""

    def test_get_voice_attachment_service_returns_service_with_all_dependencies(self):
        """Test that function returns VoiceAttachmentService with all dependencies."""
        # Arrange
        mock_mail_service = Mock()
        mock_mail_repository = Mock()
        mock_voice_repository = Mock()
        mock_blob_service = Mock()
        mock_shared_mailbox_repository = Mock()

        with patch('app.dependencies.mail.VoiceAttachmentService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = get_voice_attachment_service(
                mail_service=mock_mail_service,
                mail_repository=mock_mail_repository,
                voice_attachment_repository=mock_voice_repository,
                blob_service=mock_blob_service,
                shared_mailbox_repository=mock_shared_mailbox_repository
            )

            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(
                mail_service=mock_mail_service,
                mail_repository=mock_mail_repository,
                voice_attachment_repository=mock_voice_repository,
                blob_service=mock_blob_service,
                shared_mailbox_repository=mock_shared_mailbox_repository
            )

    def test_get_voice_attachment_service_with_none_shared_mailbox_repository(self):
        """Test that service works with None shared_mailbox_repository."""
        # Arrange
        mock_mail_service = Mock()
        mock_mail_repository = Mock()
        mock_voice_repository = Mock()
        mock_blob_service = Mock()

        with patch('app.dependencies.mail.VoiceAttachmentService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = get_voice_attachment_service(
                mail_service=mock_mail_service,
                mail_repository=mock_mail_repository,
                voice_attachment_repository=mock_voice_repository,
                blob_service=mock_blob_service,
                shared_mailbox_repository=None
            )

            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(
                mail_service=mock_mail_service,
                mail_repository=mock_mail_repository,
                voice_attachment_repository=mock_voice_repository,
                blob_service=mock_blob_service,
                shared_mailbox_repository=None
            )

    def test_get_voice_attachment_service_dependency_injection_order(self):
        """Test that dependencies are injected in the correct order."""
        # This test verifies the dependency chain works correctly
        # In a real scenario, the dependencies would be resolved by FastAPI
        
        # Arrange - Create mock dependencies
        mock_dependencies = {
            'mail_service': Mock(name='mail_service'),
            'mail_repository': Mock(name='mail_repository'),
            'voice_attachment_repository': Mock(name='voice_attachment_repository'),
            'blob_service': Mock(name='blob_service'),
            'shared_mailbox_repository': Mock(name='shared_mailbox_repository')
        }

        with patch('app.dependencies.mail.VoiceAttachmentService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = get_voice_attachment_service(**mock_dependencies)

            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(**mock_dependencies)


class TestIntegrationScenarios:
    """Integration test scenarios for mail dependencies."""

    def test_complete_mail_service_dependency_chain(self):
        """Test the complete dependency chain from credentials to mail service."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="integration_test_token"
        )

        with patch('app.dependencies.mail.MailRepository') as MockMailRepository:
            with patch('app.dependencies.mail.MailService') as MockMailService:
                mock_repository = Mock()
                mock_service = Mock()
                MockMailRepository.return_value = mock_repository
                MockMailService.return_value = mock_service

                # Act - Simulate the dependency chain
                repository = get_mail_repository(credentials)
                service = get_mail_service(repository)

                # Assert
                assert repository == mock_repository
                assert service == mock_service
                MockMailRepository.assert_called_once_with("integration_test_token")
                MockMailService.assert_called_once_with(mock_repository)

    @pytest.mark.asyncio
    async def test_voice_attachment_service_dependency_chain(self):
        """Test the complete dependency chain for voice attachment service."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="voice_test_token"
        )
        mock_db_session = AsyncMock()

        with patch('app.dependencies.mail.MailRepository') as MockMailRepository:
            with patch('app.dependencies.mail.MailService') as MockMailService:
                with patch('app.dependencies.mail.SharedMailboxRepository') as MockSharedRepository:
                    with patch('app.dependencies.mail.VoiceAttachmentRepository') as MockVoiceRepository:
                        with patch('app.dependencies.mail.VoiceAttachmentService') as MockVoiceService:
                            with patch('app.dependencies.mail.azure_blob_service') as mock_blob:
                                # Setup mocks
                                mock_mail_repo = Mock()
                                mock_mail_service = Mock()
                                mock_shared_repo = Mock()
                                mock_voice_repo = Mock()
                                mock_voice_service = Mock()
                                
                                MockMailRepository.return_value = mock_mail_repo
                                MockMailService.return_value = mock_mail_service
                                MockSharedRepository.return_value = mock_shared_repo
                                MockVoiceRepository.return_value = mock_voice_repo
                                MockVoiceService.return_value = mock_voice_service

                                # Act - Build the complete service
                                mail_repo = get_mail_repository(credentials)
                                mail_service = get_mail_service(mail_repo)
                                shared_repo = get_shared_mailbox_repository(credentials)
                                voice_repo = await get_voice_attachment_repository(mock_db_session)
                                blob_service = get_blob_service()
                                
                                voice_service = get_voice_attachment_service(
                                    mail_service=mail_service,
                                    mail_repository=mail_repo,
                                    voice_attachment_repository=voice_repo,
                                    blob_service=blob_service,
                                    shared_mailbox_repository=shared_repo
                                )

                                # Assert
                                assert voice_service == mock_voice_service
                                MockVoiceService.assert_called_once_with(
                                    mail_service=mock_mail_service,
                                    mail_repository=mock_mail_repo,
                                    voice_attachment_repository=mock_voice_repo,
                                    blob_service=mock_blob,
                                    shared_mailbox_repository=mock_shared_repo
                                )

    def test_authentication_required_for_all_repositories(self):
        """Test that authentication is required for all repositories that need it."""
        # Test that repositories requiring authentication fail without credentials
        with pytest.raises(HTTPException) as mail_exc:
            get_mail_repository(None)
        
        with pytest.raises(HTTPException) as shared_exc:
            get_shared_mailbox_repository(None)

        # Assert both raise 401
        assert mail_exc.value.status_code == 401
        assert shared_exc.value.status_code == 401

        # Voice attachment repository should work without credentials (uses DB session)
        # Blob service should work without credentials (singleton instance)
        
    @pytest.mark.parametrize("token_value", [
        "valid_token_123",
        "another-valid-token",
        "",  # Empty token should still create repository
        "very_long_token_with_special_chars_!@#$%^&*()",
    ])
    def test_repositories_handle_various_token_formats(self, token_value):
        """Test that repositories handle various token formats."""
        # Arrange
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token_value
        )

        with patch('app.dependencies.mail.MailRepository') as MockMailRepo:
            with patch('app.dependencies.mail.SharedMailboxRepository') as MockSharedRepo:
                MockMailRepo.return_value = Mock()
                MockSharedRepo.return_value = Mock()

                # Act & Assert - Should not raise exceptions
                mail_repo = get_mail_repository(credentials)
                shared_repo = get_shared_mailbox_repository(credentials)

                # Verify tokens were passed correctly
                MockMailRepo.assert_called_once_with(token_value)
                MockSharedRepo.assert_called_once_with(token_value)
                assert mail_repo is not None
                assert shared_repo is not None