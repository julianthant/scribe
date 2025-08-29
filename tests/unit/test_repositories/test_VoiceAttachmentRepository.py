"""
Unit tests for VoiceAttachmentRepository.

Tests the voice attachment data access layer including:
- Voice attachment CRUD operations
- Blob storage metadata management
- Query operations and filtering
- Statistics and analytics
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from app.repositories.VoiceAttachmentRepository import VoiceAttachmentRepository
from app.db.models.VoiceAttachment import VoiceAttachment, VoiceAttachmentBlob
from app.core.Exceptions import ValidationError, NotFoundError


class TestVoiceAttachmentRepository:
    """Unit tests for VoiceAttachmentRepository class."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.add = Mock()
        mock_session.delete = Mock()
        mock_session.merge = Mock()
        return mock_session

    @pytest.fixture
    def voice_attachment_repository(self, mock_db_session):
        """Create VoiceAttachmentRepository with mocked database session."""
        return VoiceAttachmentRepository(mock_db_session)

    @pytest.fixture
    def mock_voice_attachment(self):
        """Mock VoiceAttachment model instance."""
        return VoiceAttachment(
            id="attachment_12345",
            message_id="message_67890",
            attachment_id="graph_attachment_123",
            user_id="user_456",
            filename="voicemail.wav",
            content_type="audio/wav",
            size_bytes=52428,
            duration_seconds=45.2,
            sender_email="sender@example.com",
            sender_name="Test Sender",
            received_at=datetime(2024, 8, 28, 10, 0),
            processed_at=datetime(2024, 8, 28, 10, 5),
            is_transcribed=False
        )

    @pytest.fixture
    def mock_voice_attachment_blob(self):
        """Mock VoiceAttachmentBlob model instance."""
        return VoiceAttachmentBlob(
            id="blob_12345",
            voice_attachment_id="attachment_12345",
            blob_name="message_67890_attachment_123.wav",
            blob_url="https://storage.blob.core.windows.net/voice-attachments/message_67890_attachment_123.wav",
            original_name="voicemail.wav",
            content_type="audio/wav",
            size_bytes=52428,
            stored_at=datetime(2024, 8, 28, 10, 10),
            expires_at=datetime(2024, 8, 28, 10, 10) + timedelta(days=90)
        )

    # =====================================================================
    # Voice Attachment CRUD Tests
    # =====================================================================

    async def test_create_voice_attachment_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment):
        """Test creating voice attachment successfully."""
        result = await voice_attachment_repository.create_voice_attachment(mock_voice_attachment)
        
        assert result == mock_voice_attachment
        mock_db_session.add.assert_called_once_with(mock_voice_attachment)
        mock_db_session.commit.assert_called_once()

    async def test_get_voice_attachment_by_id_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment):
        """Test getting voice attachment by ID successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_voice_attachment
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_voice_attachment_by_id("attachment_12345")
        
        assert result == mock_voice_attachment
        assert result.filename == "voicemail.wav"

    async def test_get_voice_attachment_by_id_not_found(self, voice_attachment_repository, mock_db_session):
        """Test getting non-existent voice attachment."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_voice_attachment_by_id("nonexistent")
        
        assert result is None

    async def test_get_voice_attachment_by_graph_id_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment):
        """Test getting voice attachment by Graph API attachment ID."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_voice_attachment
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_voice_attachment_by_graph_id(
            "message_67890", "graph_attachment_123"
        )
        
        assert result == mock_voice_attachment
        assert result.message_id == "message_67890"
        assert result.attachment_id == "graph_attachment_123"

    async def test_update_voice_attachment_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment):
        """Test updating voice attachment successfully."""
        mock_voice_attachment.is_transcribed = True
        mock_voice_attachment.processed_at = datetime.now()
        
        result = await voice_attachment_repository.update_voice_attachment(mock_voice_attachment)
        
        assert result == mock_voice_attachment
        mock_db_session.merge.assert_called_once_with(mock_voice_attachment)
        mock_db_session.commit.assert_called_once()

    async def test_delete_voice_attachment_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment):
        """Test deleting voice attachment successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_voice_attachment
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.delete_voice_attachment("attachment_12345")
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_voice_attachment)
        mock_db_session.commit.assert_called_once()

    # =====================================================================
    # Voice Attachment Query Tests
    # =====================================================================

    async def test_get_voice_attachments_by_user_success(self, voice_attachment_repository, mock_db_session):
        """Test getting voice attachments for specific user."""
        mock_attachments = [
            Mock(id="att1", user_id="user_456", filename="file1.wav"),
            Mock(id="att2", user_id="user_456", filename="file2.wav")
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_attachments
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_voice_attachments_by_user(
            user_id="user_456", 
            limit=10,
            offset=0
        )
        
        assert len(result) == 2
        assert all(att.user_id == "user_456" for att in result)

    async def test_get_voice_attachments_by_date_range(self, voice_attachment_repository, mock_db_session):
        """Test getting voice attachments within date range."""
        start_date = datetime(2024, 8, 1)
        end_date = datetime(2024, 8, 31)
        
        mock_attachments = [
            Mock(received_at=datetime(2024, 8, 15)),
            Mock(received_at=datetime(2024, 8, 20))
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_attachments
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_voice_attachments_by_date_range(
            start_date=start_date,
            end_date=end_date,
            user_id="user_456"
        )
        
        assert len(result) == 2

    async def test_get_untranscribed_attachments(self, voice_attachment_repository, mock_db_session):
        """Test getting untranscribed voice attachments."""
        mock_untranscribed = [
            Mock(id="att1", is_transcribed=False),
            Mock(id="att2", is_transcribed=False)
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_untranscribed
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_untranscribed_attachments(
            user_id="user_456",
            limit=50
        )
        
        assert len(result) == 2
        assert all(not att.is_transcribed for att in result)

    async def test_search_voice_attachments_by_sender(self, voice_attachment_repository, mock_db_session):
        """Test searching voice attachments by sender."""
        mock_attachments = [
            Mock(sender_email="sender@example.com", sender_name="Test Sender")
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_attachments
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.search_voice_attachments_by_sender(
            user_id="user_456",
            sender_query="sender@example.com"
        )
        
        assert len(result) == 1
        assert result[0].sender_email == "sender@example.com"

    # =====================================================================
    # Voice Attachment Statistics Tests
    # =====================================================================

    async def test_get_voice_attachment_count_by_user(self, voice_attachment_repository, mock_db_session):
        """Test getting total count of voice attachments for user."""
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 25
        mock_db_session.execute.return_value = mock_count_result
        
        count = await voice_attachment_repository.get_voice_attachment_count_by_user("user_456")
        
        assert count == 25

    async def test_get_total_size_by_user(self, voice_attachment_repository, mock_db_session):
        """Test getting total size of voice attachments for user."""
        mock_size_result = Mock()
        mock_size_result.scalar.return_value = 1048576  # 1MB
        mock_db_session.execute.return_value = mock_size_result
        
        total_size = await voice_attachment_repository.get_total_size_by_user("user_456")
        
        assert total_size == 1048576

    async def test_get_voice_attachment_statistics(self, voice_attachment_repository, mock_db_session):
        """Test getting comprehensive voice attachment statistics."""
        # Mock multiple query results
        mock_count = Mock()
        mock_count.scalar.return_value = 50
        
        mock_size = Mock()
        mock_size.scalar.return_value = 2097152  # 2MB
        
        mock_avg_duration = Mock()
        mock_avg_duration.scalar.return_value = 35.5
        
        mock_format_stats = Mock()
        mock_format_stats.fetchall.return_value = [
            ("audio/wav", 30),
            ("audio/mp4", 15),
            ("audio/mpeg", 5)
        ]
        
        mock_db_session.execute.side_effect = [
            mock_count,
            mock_size,
            mock_avg_duration,
            mock_format_stats
        ]
        
        stats = await voice_attachment_repository.get_voice_attachment_statistics("user_456")
        
        assert stats["total_attachments"] == 50
        assert stats["total_size_bytes"] == 2097152
        assert stats["average_duration_seconds"] == 35.5
        assert stats["formats"]["audio/wav"] == 30

    async def test_get_monthly_voice_attachment_counts(self, voice_attachment_repository, mock_db_session):
        """Test getting monthly voice attachment counts."""
        mock_monthly_data = Mock()
        mock_monthly_data.fetchall.return_value = [
            ("2024-08", 25),
            ("2024-07", 20),
            ("2024-06", 15)
        ]
        mock_db_session.execute.return_value = mock_monthly_data
        
        monthly_counts = await voice_attachment_repository.get_monthly_voice_attachment_counts("user_456")
        
        assert len(monthly_counts) == 3
        assert monthly_counts[0] == ("2024-08", 25)

    # =====================================================================
    # Blob Storage Management Tests
    # =====================================================================

    async def test_create_voice_attachment_blob_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment_blob):
        """Test creating voice attachment blob record successfully."""
        result = await voice_attachment_repository.create_voice_attachment_blob(mock_voice_attachment_blob)
        
        assert result == mock_voice_attachment_blob
        mock_db_session.add.assert_called_once_with(mock_voice_attachment_blob)
        mock_db_session.commit.assert_called_once()

    async def test_get_voice_attachment_blob_by_name(self, voice_attachment_repository, mock_db_session, mock_voice_attachment_blob):
        """Test getting blob record by blob name."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_voice_attachment_blob
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_voice_attachment_blob_by_name(
            "message_67890_attachment_123.wav"
        )
        
        assert result == mock_voice_attachment_blob
        assert result.blob_name == "message_67890_attachment_123.wav"

    async def test_get_stored_voice_attachments_for_user(self, voice_attachment_repository, mock_db_session):
        """Test getting stored voice attachments for user."""
        mock_blobs = [
            Mock(
                blob_name="file1.wav",
                stored_at=datetime.now(),
                size_bytes=52428,
                voice_attachment=Mock(user_id="user_456")
            ),
            Mock(
                blob_name="file2.wav",
                stored_at=datetime.now(),
                size_bytes=31847,
                voice_attachment=Mock(user_id="user_456")
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_blobs
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_stored_voice_attachments_for_user("user_456")
        
        assert len(result) == 2
        assert all(blob.voice_attachment.user_id == "user_456" for blob in result)

    async def test_get_expired_blob_records(self, voice_attachment_repository, mock_db_session):
        """Test getting expired blob records for cleanup."""
        expired_blobs = [
            Mock(
                blob_name="expired1.wav",
                expires_at=datetime.now() - timedelta(days=1),
                size_bytes=52428
            ),
            Mock(
                blob_name="expired2.wav", 
                expires_at=datetime.now() - timedelta(days=5),
                size_bytes=31847
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = expired_blobs
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.get_expired_blob_records()
        
        assert len(result) == 2
        assert all(blob.expires_at < datetime.now() for blob in result)

    async def test_delete_voice_attachment_blob_success(self, voice_attachment_repository, mock_db_session, mock_voice_attachment_blob):
        """Test deleting voice attachment blob record."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_voice_attachment_blob
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.delete_voice_attachment_blob("blob_12345")
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_voice_attachment_blob)
        mock_db_session.commit.assert_called_once()

    async def test_get_blob_storage_statistics(self, voice_attachment_repository, mock_db_session):
        """Test getting blob storage statistics."""
        mock_count = Mock()
        mock_count.scalar.return_value = 15
        
        mock_size = Mock()
        mock_size.scalar.return_value = 3145728  # 3MB
        
        mock_dates = Mock()
        mock_dates.fetchone.return_value = (
            datetime(2024, 7, 1),   # oldest
            datetime(2024, 8, 28)   # newest
        )
        
        mock_db_session.execute.side_effect = [mock_count, mock_size, mock_dates]
        
        stats = await voice_attachment_repository.get_blob_storage_statistics()
        
        assert stats["total_stored"] == 15
        assert stats["total_size_bytes"] == 3145728
        assert stats["average_size_bytes"] == 3145728 // 15

    # =====================================================================
    # Batch Operations Tests
    # =====================================================================

    async def test_bulk_create_voice_attachments(self, voice_attachment_repository, mock_db_session):
        """Test bulk creating multiple voice attachments."""
        mock_attachments = [
            VoiceAttachment(
                id=f"att_{i}",
                message_id=f"msg_{i}",
                attachment_id=f"graph_{i}",
                user_id="user_456",
                filename=f"voice_{i}.wav",
                content_type="audio/wav",
                size_bytes=52428
            )
            for i in range(5)
        ]
        
        result = await voice_attachment_repository.bulk_create_voice_attachments(mock_attachments)
        
        assert len(result) == 5
        assert mock_db_session.add.call_count == 5
        mock_db_session.commit.assert_called_once()

    async def test_batch_update_transcription_status(self, voice_attachment_repository, mock_db_session):
        """Test batch updating transcription status."""
        attachment_ids = ["att_1", "att_2", "att_3"]
        
        mock_result = Mock()
        mock_result.rowcount = 3
        mock_db_session.execute.return_value = mock_result
        
        updated_count = await voice_attachment_repository.batch_update_transcription_status(
            attachment_ids, is_transcribed=True
        )
        
        assert updated_count == 3
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()

    # =====================================================================
    # Validation and Error Handling Tests
    # =====================================================================

    async def test_validate_voice_attachment_data_success(self, voice_attachment_repository):
        """Test validating valid voice attachment data."""
        valid_data = {
            "message_id": "message_123",
            "attachment_id": "attachment_456",
            "user_id": "user_789",
            "filename": "test.wav",
            "content_type": "audio/wav",
            "size_bytes": 52428
        }
        
        # Should not raise exception
        voice_attachment_repository._validate_voice_attachment_data(valid_data)

    async def test_validate_voice_attachment_data_invalid_content_type(self, voice_attachment_repository):
        """Test validating data with invalid content type."""
        invalid_data = {
            "message_id": "message_123",
            "attachment_id": "attachment_456",
            "user_id": "user_789",
            "filename": "test.pdf",
            "content_type": "application/pdf",  # Not audio
            "size_bytes": 52428
        }
        
        with pytest.raises(ValidationError):
            voice_attachment_repository._validate_voice_attachment_data(invalid_data)

    async def test_validate_voice_attachment_data_missing_fields(self, voice_attachment_repository):
        """Test validating data with missing required fields."""
        incomplete_data = {
            "message_id": "message_123",
            "filename": "test.wav"
            # Missing other required fields
        }
        
        with pytest.raises(ValidationError):
            voice_attachment_repository._validate_voice_attachment_data(incomplete_data)

    async def test_database_constraint_error_handling(self, voice_attachment_repository, mock_db_session, mock_voice_attachment):
        """Test handling database constraint errors."""
        from sqlalchemy.exc import IntegrityError
        mock_db_session.commit.side_effect = IntegrityError("Duplicate key", None, None)
        
        with pytest.raises(ValidationError):
            await voice_attachment_repository.create_voice_attachment(mock_voice_attachment)
        
        mock_db_session.rollback.assert_called_once()

    # =====================================================================
    # Cleanup and Maintenance Tests
    # =====================================================================

    async def test_cleanup_orphaned_attachments(self, voice_attachment_repository, mock_db_session):
        """Test cleaning up orphaned voice attachments."""
        orphaned_attachments = [
            Mock(id="orphan1", message_id="deleted_message1"),
            Mock(id="orphan2", message_id="deleted_message2")
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = orphaned_attachments
        mock_db_session.execute.return_value = mock_result
        
        cleaned_count = await voice_attachment_repository.cleanup_orphaned_attachments()
        
        assert cleaned_count == 2
        assert mock_db_session.delete.call_count == 2
        mock_db_session.commit.assert_called_once()

    async def test_cleanup_old_voice_attachments(self, voice_attachment_repository, mock_db_session):
        """Test cleaning up old voice attachments."""
        days_to_keep = 90
        
        old_attachments = [
            Mock(
                id="old1",
                received_at=datetime.now() - timedelta(days=100),
                size_bytes=52428
            ),
            Mock(
                id="old2",
                received_at=datetime.now() - timedelta(days=120),
                size_bytes=31847
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = old_attachments
        mock_db_session.execute.return_value = mock_result
        
        result = await voice_attachment_repository.cleanup_old_voice_attachments(days_to_keep)
        
        assert result["deleted_count"] == 2
        assert result["space_freed_bytes"] == 84275  # Sum of sizes

    async def test_get_storage_health_metrics(self, voice_attachment_repository, mock_db_session):
        """Test getting storage health metrics."""
        # Mock health data queries
        mock_total_size = Mock()
        mock_total_size.scalar.return_value = 5242880  # 5MB
        
        mock_blob_count = Mock()
        mock_blob_count.scalar.return_value = 100
        
        mock_orphaned_count = Mock()
        mock_orphaned_count.scalar.return_value = 5
        
        mock_expired_count = Mock()
        mock_expired_count.scalar.return_value = 10
        
        mock_db_session.execute.side_effect = [
            mock_total_size,
            mock_blob_count,
            mock_orphaned_count,
            mock_expired_count
        ]
        
        health_metrics = await voice_attachment_repository.get_storage_health_metrics()
        
        assert health_metrics["total_size_bytes"] == 5242880
        assert health_metrics["total_stored_blobs"] == 100
        assert health_metrics["orphaned_attachments"] == 5
        assert health_metrics["expired_blobs"] == 10