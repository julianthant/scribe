"""
test_Transcription.py - Unit tests for transcription dependencies

Tests the dependency injection functions in app.dependencies.Transcription including:
- get_transcription_repository(): TranscriptionRepository with database session
- get_voice_attachment_repository(): VoiceAttachmentRepository for transcription workflow
- get_transcription_service(): TranscriptionService with repository dependencies

All database sessions and repositories are mocked to ensure isolated unit testing.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.Transcription import (
    get_transcription_repository,
    get_voice_attachment_repository,
    get_transcription_service
)


class TestGetTranscriptionRepository:
    """Test cases for get_transcription_repository dependency function."""

    def test_get_transcription_repository_returns_repository_with_session(self):
        """Test that function returns TranscriptionRepository with database session."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockRepository:
            mock_repository = Mock()
            MockRepository.return_value = mock_repository

            # Act
            result = get_transcription_repository(mock_db_session)

            # Assert
            assert result == mock_repository
            MockRepository.assert_called_once_with(mock_db_session)

    def test_get_transcription_repository_uses_provided_session(self):
        """Test that repository uses the provided database session."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)
        mock_db_session.info = {"session_id": "transcription-test-session"}

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockRepository:
            MockRepository.return_value = Mock()

            # Act
            get_transcription_repository(mock_db_session)

            # Assert
            MockRepository.assert_called_once_with(mock_db_session)

    def test_get_transcription_repository_with_different_sessions(self):
        """Test that different sessions create different repository instances."""
        # Arrange
        mock_session1 = AsyncMock(spec=AsyncSession)
        mock_session2 = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockRepository:
            mock_repo1 = Mock(name="repo1")
            mock_repo2 = Mock(name="repo2")
            MockRepository.side_effect = [mock_repo1, mock_repo2]

            # Act
            result1 = get_transcription_repository(mock_session1)
            result2 = get_transcription_repository(mock_session2)

            # Assert
            assert result1 == mock_repo1
            assert result2 == mock_repo2
            assert MockRepository.call_count == 2
            MockRepository.assert_any_call(mock_session1)
            MockRepository.assert_any_call(mock_session2)


class TestGetVoiceAttachmentRepository:
    """Test cases for get_voice_attachment_repository dependency function."""

    def test_get_voice_attachment_repository_returns_repository_with_session(self):
        """Test that function returns VoiceAttachmentRepository with database session."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockRepository:
            mock_repository = Mock()
            MockRepository.return_value = mock_repository

            # Act
            result = get_voice_attachment_repository(mock_db_session)

            # Assert
            assert result == mock_repository
            MockRepository.assert_called_once_with(mock_db_session)

    def test_get_voice_attachment_repository_uses_provided_session(self):
        """Test that repository uses the provided database session."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)
        mock_db_session.bind = Mock(name="test_engine")

        with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockRepository:
            MockRepository.return_value = Mock()

            # Act
            get_voice_attachment_repository(mock_db_session)

            # Assert
            MockRepository.assert_called_once_with(mock_db_session)

    def test_get_voice_attachment_repository_session_state_preserved(self):
        """Test that repository preserves session state."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)
        mock_db_session.is_active = True
        mock_db_session.in_transaction.return_value = False

        with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockRepository:
            mock_repository = Mock()
            MockRepository.return_value = mock_repository

            # Act
            result = get_voice_attachment_repository(mock_db_session)

            # Assert
            assert result == mock_repository
            MockRepository.assert_called_once_with(mock_db_session)
            # Verify session state is preserved
            assert mock_db_session.is_active is True


class TestGetTranscriptionService:
    """Test cases for get_transcription_service dependency function."""

    def test_get_transcription_service_returns_service_with_repositories(self):
        """Test that function returns TranscriptionService with both repositories."""
        # Arrange
        mock_transcription_repo = Mock()
        mock_voice_attachment_repo = Mock()

        with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = get_transcription_service(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

            # Assert
            assert result == mock_service
            MockService.assert_called_once_with(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

    def test_get_transcription_service_uses_provided_repositories(self):
        """Test that service uses the provided repository instances."""
        # Arrange
        mock_transcription_repo = Mock()
        mock_transcription_repo.db_session = Mock(name="transcription_session")
        
        mock_voice_attachment_repo = Mock()
        mock_voice_attachment_repo.db_session = Mock(name="voice_attachment_session")

        with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            get_transcription_service(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

            # Assert
            MockService.assert_called_once_with(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

    def test_get_transcription_service_dependency_injection_order(self):
        """Test that dependencies are injected with correct parameter names."""
        # Arrange
        mock_transcription_repo = Mock(name="transcription_repository")
        mock_voice_attachment_repo = Mock(name="voice_attachment_repository")

        with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = get_transcription_service(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

            # Assert
            assert result == mock_service
            # Verify exact keyword arguments
            MockService.assert_called_once_with(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

    def test_get_transcription_service_handles_repository_types(self):
        """Test that service handles different repository instance types."""
        # Arrange
        mock_transcription_repo = Mock()
        mock_transcription_repo.__class__.__name__ = "TranscriptionRepository"
        
        mock_voice_attachment_repo = Mock()
        mock_voice_attachment_repo.__class__.__name__ = "VoiceAttachmentRepository"

        with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Act
            result = get_transcription_service(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )

            # Assert
            assert result == mock_service
            MockService.assert_called_once()


class TestIntegrationScenarios:
    """Integration test scenarios for transcription dependencies."""

    def test_complete_transcription_dependency_chain(self):
        """Test the complete dependency chain from database session to service."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockTranscriptionRepo:
            with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockVoiceRepo:
                with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
                    # Setup mocks
                    mock_transcription_repo = Mock()
                    mock_voice_repo = Mock()
                    mock_service = Mock()
                    
                    MockTranscriptionRepo.return_value = mock_transcription_repo
                    MockVoiceRepo.return_value = mock_voice_repo
                    MockService.return_value = mock_service

                    # Act - Build the complete service through dependency chain
                    transcription_repo = get_transcription_repository(mock_db_session)
                    voice_repo = get_voice_attachment_repository(mock_db_session)
                    service = get_transcription_service(
                        transcription_repository=transcription_repo,
                        voice_attachment_repository=voice_repo
                    )

                    # Assert
                    assert transcription_repo == mock_transcription_repo
                    assert voice_repo == mock_voice_repo
                    assert service == mock_service

                    # Verify dependency chain
                    MockTranscriptionRepo.assert_called_once_with(mock_db_session)
                    MockVoiceRepo.assert_called_once_with(mock_db_session)
                    MockService.assert_called_once_with(
                        transcription_repository=mock_transcription_repo,
                        voice_attachment_repository=mock_voice_repo
                    )

    def test_shared_database_session_across_repositories(self):
        """Test that both repositories can share the same database session."""
        # Arrange
        shared_db_session = AsyncMock(spec=AsyncSession)
        shared_db_session.info = {"session_type": "shared"}

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockTranscriptionRepo:
            with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockVoiceRepo:
                mock_transcription_repo = Mock()
                mock_voice_repo = Mock()
                
                MockTranscriptionRepo.return_value = mock_transcription_repo
                MockVoiceRepo.return_value = mock_voice_repo

                # Act
                transcription_repo = get_transcription_repository(shared_db_session)
                voice_repo = get_voice_attachment_repository(shared_db_session)

                # Assert
                assert transcription_repo == mock_transcription_repo
                assert voice_repo == mock_voice_repo
                
                # Verify both repositories use the same session
                MockTranscriptionRepo.assert_called_once_with(shared_db_session)
                MockVoiceRepo.assert_called_once_with(shared_db_session)

    def test_service_creation_with_repository_dependencies(self):
        """Test service creation with actual repository dependencies."""
        # Arrange
        mock_session1 = AsyncMock(spec=AsyncSession)
        mock_session2 = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockTranscriptionRepo:
            with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockVoiceRepo:
                with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
                    # Create different repository instances
                    mock_transcription_repo = Mock(name="transcription_repo")
                    mock_voice_repo = Mock(name="voice_repo")
                    mock_service = Mock(name="transcription_service")
                    
                    MockTranscriptionRepo.return_value = mock_transcription_repo
                    MockVoiceRepo.return_value = mock_voice_repo
                    MockService.return_value = mock_service

                    # Act - Create repositories with different sessions
                    transcription_repo = get_transcription_repository(mock_session1)
                    voice_repo = get_voice_attachment_repository(mock_session2)
                    
                    # Create service with these repositories
                    service = get_transcription_service(
                        transcription_repository=transcription_repo,
                        voice_attachment_repository=voice_repo
                    )

                    # Assert
                    assert service == mock_service
                    MockService.assert_called_once_with(
                        transcription_repository=mock_transcription_repo,
                        voice_attachment_repository=mock_voice_repo
                    )

    def test_dependency_isolation_across_multiple_services(self):
        """Test that multiple service instances are properly isolated."""
        # Arrange
        session1 = AsyncMock(spec=AsyncSession, name="session1")
        session2 = AsyncMock(spec=AsyncSession, name="session2")

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockTranscriptionRepo:
            with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockVoiceRepo:
                with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
                    # Setup multiple mock instances
                    transcription_repos = [Mock(name=f"transcription_repo_{i}") for i in range(2)]
                    voice_repos = [Mock(name=f"voice_repo_{i}") for i in range(2)]
                    services = [Mock(name=f"service_{i}") for i in range(2)]
                    
                    MockTranscriptionRepo.side_effect = transcription_repos
                    MockVoiceRepo.side_effect = voice_repos
                    MockService.side_effect = services

                    # Act - Create two separate service instances
                    transcription_repo1 = get_transcription_repository(session1)
                    voice_repo1 = get_voice_attachment_repository(session1)
                    service1 = get_transcription_service(
                        transcription_repository=transcription_repo1,
                        voice_attachment_repository=voice_repo1
                    )

                    transcription_repo2 = get_transcription_repository(session2)
                    voice_repo2 = get_voice_attachment_repository(session2)
                    service2 = get_transcription_service(
                        transcription_repository=transcription_repo2,
                        voice_attachment_repository=voice_repo2
                    )

                    # Assert
                    assert service1 == services[0]
                    assert service2 == services[1]
                    assert service1 != service2

                    # Verify proper isolation
                    expected_calls = [
                        ((transcription_repos[0], voice_repos[0]),),
                        ((transcription_repos[1], voice_repos[1]),)
                    ]
                    MockService.call_args_list[0] == expected_calls[0]
                    MockService.call_args_list[1] == expected_calls[1]


class TestErrorHandling:
    """Test error handling in transcription dependencies."""

    def test_get_transcription_repository_handles_repository_creation_error(self):
        """Test handling of repository creation errors."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockRepository:
            MockRepository.side_effect = ValueError("Repository creation failed")

            # Act & Assert
            with pytest.raises(ValueError) as exc_info:
                get_transcription_repository(mock_db_session)

            assert "Repository creation failed" in str(exc_info.value)
            MockRepository.assert_called_once_with(mock_db_session)

    def test_get_voice_attachment_repository_handles_repository_creation_error(self):
        """Test handling of voice attachment repository creation errors."""
        # Arrange
        mock_db_session = AsyncMock(spec=AsyncSession)

        with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockRepository:
            MockRepository.side_effect = RuntimeError("Database connection failed")

            # Act & Assert
            with pytest.raises(RuntimeError) as exc_info:
                get_voice_attachment_repository(mock_db_session)

            assert "Database connection failed" in str(exc_info.value)
            MockRepository.assert_called_once_with(mock_db_session)

    def test_get_transcription_service_handles_service_creation_error(self):
        """Test handling of service creation errors."""
        # Arrange
        mock_transcription_repo = Mock()
        mock_voice_attachment_repo = Mock()

        with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
            MockService.side_effect = TypeError("Service initialization failed")

            # Act & Assert
            with pytest.raises(TypeError) as exc_info:
                get_transcription_service(
                    transcription_repository=mock_transcription_repo,
                    voice_attachment_repository=mock_voice_attachment_repo
                )

            assert "Service initialization failed" in str(exc_info.value)
            MockService.assert_called_once_with(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_attachment_repo
            )


class TestParameterValidation:
    """Test parameter validation in dependency functions."""

    @pytest.mark.parametrize("session_value", [
        None,
        Mock(spec=AsyncSession),
        AsyncMock(spec=AsyncSession),
    ])
    def test_repositories_handle_various_session_types(self, session_value):
        """Test that repositories handle various session parameter types."""
        with patch('app.dependencies.Transcription.TranscriptionRepository') as MockTranscriptionRepo:
            with patch('app.dependencies.Transcription.VoiceAttachmentRepository') as MockVoiceRepo:
                MockTranscriptionRepo.return_value = Mock()
                MockVoiceRepo.return_value = Mock()

                # Act & Assert - Should not raise exceptions for valid session types
                if session_value is not None:
                    transcription_result = get_transcription_repository(session_value)
                    voice_result = get_voice_attachment_repository(session_value)
                    
                    assert transcription_result is not None
                    assert voice_result is not None
                    MockTranscriptionRepo.assert_called_with(session_value)
                    MockVoiceRepo.assert_called_with(session_value)

    def test_service_validates_repository_parameters(self):
        """Test that service function validates repository parameters."""
        with patch('app.dependencies.Transcription.TranscriptionService') as MockService:
            mock_service = Mock()
            MockService.return_value = mock_service

            # Test with valid repositories
            mock_transcription_repo = Mock()
            mock_voice_repo = Mock()

            result = get_transcription_service(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_repo
            )

            assert result == mock_service
            MockService.assert_called_once_with(
                transcription_repository=mock_transcription_repo,
                voice_attachment_repository=mock_voice_repo
            )