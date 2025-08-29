"""
Unit tests for VoiceAttachmentService.

Tests the voice attachment processing service including:
- Voice attachment detection and retrieval
- Voice message organization
- Blob storage operations
- Statistics and analytics
- Metadata extraction
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.services.VoiceAttachmentService import VoiceAttachmentService
from app.core.Exceptions import ValidationError, NotFoundError


class TestVoiceAttachmentService:
    """Unit tests for VoiceAttachmentService class."""

    @pytest.fixture
    def mock_mail_service(self):
        """Mock MailService dependency."""
        mock_service = Mock()
        mock_service.get_messages_with_voice_attachments = AsyncMock()
        mock_service.get_message_attachments = AsyncMock()
        mock_service.download_attachment = AsyncMock()
        mock_service.move_message = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_blob_service(self):
        """Mock Azure Blob Service dependency."""
        mock_service = Mock()
        mock_service.upload_blob = AsyncMock()
        mock_service.download_blob = AsyncMock()
        mock_service.delete_blob = AsyncMock()
        mock_service.list_blobs = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = Mock()
        return mock_session

    @pytest.fixture
    def voice_attachment_service(self, mock_mail_service, mock_blob_service, mock_db_session):
        """Create VoiceAttachmentService with mocked dependencies."""
        with patch('app.services.VoiceAttachmentService.mail_service', mock_mail_service):
            with patch('app.services.VoiceAttachmentService.blob_service', mock_blob_service):
                with patch('app.services.VoiceAttachmentService.get_db_session') as mock_get_db:
                    mock_get_db.return_value.__aenter__.return_value = mock_db_session
                    return VoiceAttachmentService()

    @pytest.fixture
    def mock_voice_attachments(self):
        """Mock voice attachments data."""
        return [
            {
                "id": "attachment1",
                "name": "voicemail.wav",
                "contentType": "audio/wav",
                "size": 52428,
                "message_id": "message1",
                "duration": 45.2,
                "sender": "user@example.com",
                "received_at": "2024-08-28T10:00:00Z"
            },
            {
                "id": "attachment2",
                "name": "audio_message.m4a",
                "contentType": "audio/mp4", 
                "size": 31847,
                "message_id": "message2",
                "duration": 28.7,
                "sender": "colleague@example.com",
                "received_at": "2024-08-28T09:30:00Z"
            }
        ]

    # =====================================================================
    # Voice Attachment Retrieval Tests
    # =====================================================================

    async def test_get_all_voice_attachments_success(self, voice_attachment_service, mock_mail_service, mock_voice_attachments):
        """Test getting all voice attachments successfully."""
        mock_messages = {
            "value": [
                {
                    "id": "message1",
                    "hasAttachments": True,
                    "attachments": [mock_voice_attachments[0]]
                },
                {
                    "id": "message2",
                    "hasAttachments": True,
                    "attachments": [mock_voice_attachments[1]]
                }
            ]
        }
        mock_mail_service.get_messages_with_voice_attachments.return_value = mock_messages
        
        result = await voice_attachment_service.get_all_voice_attachments(
            access_token="test_token",
            folder_id="inbox",
            limit=100
        )
        
        assert len(result) == 2
        assert result[0]["id"] == "attachment1"
        assert result[1]["contentType"] == "audio/mp4"
        mock_mail_service.get_messages_with_voice_attachments.assert_called_once_with(
            "test_token", "inbox", 100
        )

    async def test_get_all_voice_attachments_no_messages(self, voice_attachment_service, mock_mail_service):
        """Test getting voice attachments when no messages exist."""
        mock_mail_service.get_messages_with_voice_attachments.return_value = {"value": []}
        
        result = await voice_attachment_service.get_all_voice_attachments(
            access_token="test_token"
        )
        
        assert result == []

    async def test_get_message_voice_attachments_success(self, voice_attachment_service, mock_mail_service):
        """Test getting voice attachments from specific message."""
        mock_attachments = [
            {
                "id": "attachment1",
                "name": "voicemail.wav",
                "contentType": "audio/wav",
                "size": 52428
            }
        ]
        mock_mail_service.get_message_attachments.return_value = mock_attachments
        
        result = await voice_attachment_service.get_message_voice_attachments(
            access_token="test_token",
            message_id="message1"
        )
        
        assert len(result) == 1
        assert result[0]["contentType"] == "audio/wav"
        mock_mail_service.get_message_attachments.assert_called_once_with(
            "test_token", "message1"
        )

    async def test_get_message_voice_attachments_no_audio(self, voice_attachment_service, mock_mail_service):
        """Test getting voice attachments from message with no audio."""
        mock_attachments = [
            {
                "id": "attachment1",
                "name": "document.pdf",
                "contentType": "application/pdf",
                "size": 104857
            }
        ]
        mock_mail_service.get_message_attachments.return_value = mock_attachments
        
        result = await voice_attachment_service.get_message_voice_attachments(
            access_token="test_token",
            message_id="message1"
        )
        
        assert result == []  # No audio attachments found

    # =====================================================================
    # Voice Attachment Metadata Tests
    # =====================================================================

    async def test_get_attachment_metadata_success(self, voice_attachment_service, mock_mail_service):
        """Test getting voice attachment metadata."""
        mock_attachment = {
            "id": "attachment1",
            "name": "voicemail.wav",
            "contentType": "audio/wav",
            "size": 52428
        }
        mock_mail_service.get_message_attachments.return_value = [mock_attachment]
        
        # Mock audio duration detection
        with patch('app.services.VoiceAttachmentService.AudioAnalyzer') as mock_analyzer:
            mock_analyzer.get_duration.return_value = 45.2
            
            result = await voice_attachment_service.get_attachment_metadata(
                access_token="test_token",
                message_id="message1",
                attachment_id="attachment1"
            )
            
            assert result["id"] == "attachment1"
            assert result["duration"] == 45.2
            assert result["contentType"] == "audio/wav"

    async def test_get_attachment_metadata_not_found(self, voice_attachment_service, mock_mail_service):
        """Test getting metadata for non-existent attachment."""
        mock_mail_service.get_message_attachments.return_value = []
        
        with pytest.raises(NotFoundError):
            await voice_attachment_service.get_attachment_metadata(
                "test_token", "message1", "invalid_attachment"
            )

    async def test_get_attachment_metadata_not_audio(self, voice_attachment_service, mock_mail_service):
        """Test getting metadata for non-audio attachment."""
        mock_attachment = {
            "id": "attachment1",
            "name": "document.pdf",
            "contentType": "application/pdf",
            "size": 104857
        }
        mock_mail_service.get_message_attachments.return_value = [mock_attachment]
        
        with pytest.raises(ValidationError):
            await voice_attachment_service.get_attachment_metadata(
                "test_token", "message1", "attachment1"
            )

    # =====================================================================
    # Voice Attachment Download Tests
    # =====================================================================

    async def test_download_attachment_success(self, voice_attachment_service, mock_mail_service):
        """Test downloading voice attachment successfully."""
        mock_attachment_data = b"fake audio content"
        mock_mail_service.download_attachment.return_value = mock_attachment_data
        mock_mail_service.get_message_attachments.return_value = [
            {
                "id": "attachment1",
                "name": "voicemail.wav",
                "contentType": "audio/wav",
                "size": 52428
            }
        ]
        
        result = await voice_attachment_service.download_attachment(
            access_token="test_token",
            message_id="message1",
            attachment_id="attachment1"
        )
        
        content, content_type, filename = result
        assert content == mock_attachment_data
        assert content_type == "audio/wav"
        assert filename == "voicemail.wav"

    async def test_download_attachment_not_found(self, voice_attachment_service, mock_mail_service):
        """Test downloading non-existent attachment."""
        mock_mail_service.get_message_attachments.return_value = []
        
        with pytest.raises(NotFoundError):
            await voice_attachment_service.download_attachment(
                "test_token", "message1", "invalid_attachment"
            )

    # =====================================================================
    # Voice Message Organization Tests
    # =====================================================================

    async def test_organize_voice_messages_success(self, voice_attachment_service, mock_mail_service):
        """Test organizing voice messages into folder."""
        mock_result = {
            "status": "completed",
            "messages_moved": 5,
            "target_folder": "Voice Messages",
            "created_folder": True
        }
        mock_mail_service.organize_voice_messages.return_value = mock_result
        
        result = await voice_attachment_service.organize_voice_messages(
            access_token="test_token",
            target_folder_name="Voice Messages"
        )
        
        assert result == mock_result
        mock_mail_service.organize_voice_messages.assert_called_once_with(
            "test_token", "Voice Messages"
        )

    async def test_organize_voice_messages_validation_error(self, voice_attachment_service):
        """Test organizing voice messages with invalid folder name."""
        with pytest.raises(ValidationError):
            await voice_attachment_service.organize_voice_messages(
                access_token="test_token",
                target_folder_name=""  # Empty name
            )

    # =====================================================================
    # Voice Statistics Tests
    # =====================================================================

    async def test_get_voice_statistics_success(self, voice_attachment_service, mock_db_session):
        """Test getting voice attachment statistics."""
        # Mock database query results
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 25
        
        mock_size_result = Mock()
        mock_size_result.scalar.return_value = 1048576
        
        mock_format_results = Mock()
        mock_format_results.fetchall.return_value = [
            ("audio/wav", 15),
            ("audio/mp4", 8),
            ("audio/mpeg", 2)
        ]
        
        mock_monthly_results = Mock()
        mock_monthly_results.fetchall.return_value = [
            ("2024-08", 15),
            ("2024-07", 10)
        ]
        
        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_size_result,
            mock_format_results,
            mock_monthly_results
        ]
        
        result = await voice_attachment_service.get_voice_statistics("user_123")
        
        assert result["total_attachments"] == 25
        assert result["total_size_bytes"] == 1048576
        assert result["most_common_format"] == "audio/wav"
        assert len(result["attachments_by_month"]) == 2

    async def test_get_voice_statistics_no_data(self, voice_attachment_service, mock_db_session):
        """Test getting statistics with no voice attachments."""
        mock_result = Mock()
        mock_result.scalar.return_value = 0
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_service.get_voice_statistics("user_123")
        
        assert result["total_attachments"] == 0
        assert result["total_size_bytes"] == 0

    # =====================================================================
    # Blob Storage Operations Tests
    # =====================================================================

    async def test_store_attachment_in_blob_success(self, voice_attachment_service, mock_mail_service, mock_blob_service):
        """Test storing voice attachment in blob storage."""
        mock_attachment_data = b"fake audio content"
        mock_mail_service.download_attachment.return_value = mock_attachment_data
        mock_mail_service.get_message_attachments.return_value = [
            {
                "id": "attachment1",
                "name": "voicemail.wav",
                "contentType": "audio/wav",
                "size": len(mock_attachment_data)
            }
        ]
        
        mock_blob_service.upload_blob.return_value = {
            "blob_name": "message1_attachment1.wav",
            "url": "https://storage.blob.core.windows.net/voice-attachments/message1_attachment1.wav"
        }
        
        result = await voice_attachment_service.store_attachment_in_blob(
            access_token="test_token",
            message_id="message1",
            attachment_id="attachment1"
        )
        
        assert result["status"] == "stored"
        assert result["blob_name"] == "message1_attachment1.wav"
        assert result["size_bytes"] == len(mock_attachment_data)
        mock_blob_service.upload_blob.assert_called_once()

    async def test_store_attachment_in_blob_already_exists(self, voice_attachment_service, mock_db_session):
        """Test storing attachment that's already in blob storage."""
        # Mock existing record in database
        mock_existing_result = Mock()
        mock_existing_result.scalar_one_or_none.return_value = Mock(
            blob_name="message1_attachment1.wav",
            stored_at=datetime.now()
        )
        mock_db_session.execute.return_value = mock_existing_result
        
        result = await voice_attachment_service.store_attachment_in_blob(
            access_token="test_token",
            message_id="message1",
            attachment_id="attachment1"
        )
        
        assert result["status"] == "already_stored"

    async def test_get_stored_attachments_success(self, voice_attachment_service, mock_db_session):
        """Test getting list of stored voice attachments."""
        mock_stored_attachments = [
            Mock(
                blob_name="message1_attachment1.wav",
                original_name="voicemail.wav",
                size_bytes=52428,
                stored_at=datetime(2024, 8, 28, 10, 0),
                message_id="message1",
                attachment_id="attachment1"
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_stored_attachments
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_service.get_stored_attachments("user_123")
        
        assert len(result) == 1
        assert result[0]["blob_name"] == "message1_attachment1.wav"
        assert result[0]["size_bytes"] == 52428

    async def test_download_from_blob_success(self, voice_attachment_service, mock_blob_service, mock_db_session):
        """Test downloading attachment from blob storage."""
        mock_audio_data = b"blob stored audio content"
        mock_blob_service.download_blob.return_value = mock_audio_data
        
        # Mock database record
        mock_record = Mock(
            original_name="voicemail.wav",
            content_type="audio/wav"
        )
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_service.download_from_blob(
            blob_name="message1_attachment1.wav"
        )
        
        content, content_type, filename = result
        assert content == mock_audio_data
        assert content_type == "audio/wav"
        assert filename == "voicemail.wav"

    async def test_download_from_blob_not_found(self, voice_attachment_service, mock_db_session):
        """Test downloading non-existent blob."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(NotFoundError):
            await voice_attachment_service.download_from_blob("invalid_blob.wav")

    async def test_delete_blob_attachment_success(self, voice_attachment_service, mock_blob_service, mock_db_session):
        """Test deleting attachment from blob storage."""
        # Mock database record
        mock_record = Mock(blob_name="message1_attachment1.wav")
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_db_session.execute.return_value = mock_result
        
        mock_blob_service.delete_blob.return_value = {"status": "deleted"}
        
        result = await voice_attachment_service.delete_blob_attachment("message1_attachment1.wav")
        
        assert result["status"] == "deleted"
        assert result["blob_name"] == "message1_attachment1.wav"
        mock_blob_service.delete_blob.assert_called_once_with("message1_attachment1.wav")
        mock_db_session.delete.assert_called_once()

    # =====================================================================
    # Storage Statistics Tests
    # =====================================================================

    async def test_get_storage_statistics_success(self, voice_attachment_service, mock_db_session):
        """Test getting blob storage statistics."""
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 12
        
        mock_size_result = Mock()
        mock_size_result.scalar.return_value = 2097152
        
        mock_dates_result = Mock()
        mock_dates_result.fetchone.return_value = (
            datetime(2024, 7, 1),  # oldest
            datetime(2024, 8, 28)  # newest
        )
        
        mock_db_session.execute.side_effect = [
            mock_count_result,
            mock_size_result,
            mock_dates_result
        ]
        
        result = await voice_attachment_service.get_storage_statistics()
        
        assert result["total_stored"] == 12
        assert result["total_size_bytes"] == 2097152
        assert result["average_size_bytes"] == 2097152 // 12

    # =====================================================================
    # Cleanup Operations Tests
    # =====================================================================

    async def test_cleanup_expired_attachments_success(self, voice_attachment_service, mock_blob_service, mock_db_session):
        """Test cleaning up expired voice attachments."""
        # Mock expired attachments
        mock_expired = [
            Mock(
                blob_name="old_attachment1.wav",
                size_bytes=52428,
                stored_at=datetime.now() - timedelta(days=40)
            ),
            Mock(
                blob_name="old_attachment2.wav",
                size_bytes=31847,
                stored_at=datetime.now() - timedelta(days=35)
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_expired
        mock_db_session.execute.return_value = mock_result
        
        mock_blob_service.delete_blob.return_value = {"status": "deleted"}
        
        result = await voice_attachment_service.cleanup_expired_attachments(days_to_keep=30)
        
        assert result["status"] == "completed"
        assert result["attachments_deleted"] == 2
        assert result["space_freed_bytes"] == 84275  # Sum of sizes
        assert mock_blob_service.delete_blob.call_count == 2

    async def test_cleanup_expired_attachments_no_expired(self, voice_attachment_service, mock_db_session):
        """Test cleanup when no expired attachments exist."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_service.cleanup_expired_attachments(days_to_keep=30)
        
        assert result["attachments_deleted"] == 0
        assert result["space_freed_bytes"] == 0

    # =====================================================================
    # Utility Method Tests
    # =====================================================================

    async def test_is_supported_audio_format_supported(self, voice_attachment_service):
        """Test checking supported audio formats."""
        assert voice_attachment_service._is_supported_audio_format("audio/wav") is True
        assert voice_attachment_service._is_supported_audio_format("audio/mpeg") is True
        assert voice_attachment_service._is_supported_audio_format("audio/mp4") is True
        assert voice_attachment_service._is_supported_audio_format("audio/ogg") is True

    async def test_is_supported_audio_format_unsupported(self, voice_attachment_service):
        """Test checking unsupported audio formats."""
        assert voice_attachment_service._is_supported_audio_format("audio/flac") is False
        assert voice_attachment_service._is_supported_audio_format("video/mp4") is False
        assert voice_attachment_service._is_supported_audio_format("application/pdf") is False

    async def test_generate_blob_name(self, voice_attachment_service):
        """Test generating blob name for attachment."""
        result = voice_attachment_service._generate_blob_name("message123", "attach456", "wav")
        
        assert result == "message123_attach456.wav"

    async def test_extract_audio_duration_wav(self, voice_attachment_service):
        """Test extracting audio duration from WAV file."""
        mock_audio_data = b"RIFF....WAVE...." + b"x" * 1000  # Mock WAV data
        
        with patch('app.services.VoiceAttachmentService.AudioAnalyzer') as mock_analyzer:
            mock_analyzer.get_duration.return_value = 45.2
            
            result = voice_attachment_service._extract_audio_duration(mock_audio_data, "audio/wav")
            
            assert result == 45.2

    async def test_extract_audio_duration_unsupported_format(self, voice_attachment_service):
        """Test extracting duration from unsupported format."""
        result = voice_attachment_service._extract_audio_duration(b"data", "audio/flac")
        
        assert result is None  # Unsupported format returns None

    # =====================================================================
    # Error Handling Tests  
    # =====================================================================

    async def test_blob_storage_connection_error(self, voice_attachment_service, mock_blob_service):
        """Test handling blob storage connection errors."""
        mock_blob_service.upload_blob.side_effect = Exception("Connection to blob storage failed")
        
        with pytest.raises(Exception) as exc_info:
            await voice_attachment_service.store_attachment_in_blob(
                "test_token", "message1", "attachment1"
            )
        
        assert "Connection to blob storage failed" in str(exc_info.value)

    async def test_database_connection_error(self, voice_attachment_service, mock_db_session):
        """Test handling database connection errors."""
        mock_db_session.execute.side_effect = Exception("Database connection lost")
        
        with pytest.raises(Exception) as exc_info:
            await voice_attachment_service.get_voice_statistics("user123")
        
        assert "Database connection lost" in str(exc_info.value)

    async def test_large_attachment_handling(self, voice_attachment_service, mock_mail_service):
        """Test handling very large voice attachments."""
        large_attachment_data = b"x" * (50 * 1024 * 1024)  # 50MB
        mock_mail_service.download_attachment.return_value = large_attachment_data
        
        mock_mail_service.get_message_attachments.return_value = [
            {
                "id": "large_attachment",
                "name": "large_recording.wav",
                "contentType": "audio/wav",
                "size": len(large_attachment_data)
            }
        ]
        
        result = await voice_attachment_service.download_attachment(
            "test_token", "message1", "large_attachment"
        )
        
        content, content_type, filename = result
        assert len(content) == 50 * 1024 * 1024
        assert content_type == "audio/wav"