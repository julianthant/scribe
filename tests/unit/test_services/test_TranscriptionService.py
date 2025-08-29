"""
Unit tests for TranscriptionService.

Tests the AI transcription service including:
- Voice transcription operations
- Batch transcription processing
- Transcription management and retrieval
- Error handling and retry logic
- Statistics and analytics
- Model management
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.TranscriptionService import TranscriptionService
from app.core.Exceptions import ValidationError, NotFoundError


class TestTranscriptionService:
    """Unit tests for TranscriptionService class."""

    @pytest.fixture
    def mock_azure_ai_service(self):
        """Mock Azure AI service dependency."""
        mock_service = Mock()
        mock_service.transcribe_audio = AsyncMock()
        mock_service.get_supported_models = AsyncMock()
        mock_service.health_check = AsyncMock()
        return mock_service

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.add = Mock()
        mock_session.delete = Mock()
        return mock_session

    @pytest.fixture
    def mock_voice_attachment_service(self):
        """Mock VoiceAttachmentService dependency."""
        mock_service = Mock()
        mock_service.download_attachment = AsyncMock()
        mock_service.get_attachment_metadata = AsyncMock()
        return mock_service

    @pytest.fixture
    def transcription_service(self, mock_azure_ai_service, mock_db_session, mock_voice_attachment_service):
        """Create TranscriptionService with mocked dependencies."""
        with patch('app.services.TranscriptionService.azure_ai_service', mock_azure_ai_service):
            with patch('app.services.TranscriptionService.voice_attachment_service', mock_voice_attachment_service):
                with patch('app.services.TranscriptionService.get_db_session') as mock_get_db:
                    mock_get_db.return_value.__aenter__.return_value = mock_db_session
                    return TranscriptionService()

    @pytest.fixture
    def mock_transcription_response(self):
        """Mock AI transcription response."""
        return {
            "transcript": "Hello, this is a test voice message. Please call me back when you get this.",
            "confidence": 0.95,
            "language": "en-US",
            "duration": 45.2,
            "word_count": 16,
            "processing_time_ms": 1250
        }

    @pytest.fixture
    def mock_transcription_record(self):
        """Mock database transcription record."""
        return Mock(
            id="trans_12345",
            voice_attachment_id="attachment_67890",
            transcript="Test transcript text",
            confidence_score=0.92,
            language="en-US",
            model_used="azure-speech-to-text-v2",
            status="completed",
            processing_time_ms=1500,
            created_at=datetime(2024, 8, 28, 10, 0),
            completed_at=datetime(2024, 8, 28, 10, 0, 1, 500000),
            error_message=None,
            word_count=14,
            character_count=65
        )

    # =====================================================================
    # Voice Transcription Tests
    # =====================================================================

    async def test_transcribe_voice_attachment_success(self, transcription_service, mock_azure_ai_service, 
                                                      mock_voice_attachment_service, mock_transcription_response, mock_db_session):
        """Test transcribing voice attachment successfully."""
        # Mock attachment download
        mock_audio_data = b"fake audio content"
        mock_voice_attachment_service.download_attachment.return_value = (
            mock_audio_data, "audio/wav", "voicemail.wav"
        )
        
        # Mock AI transcription
        mock_azure_ai_service.transcribe_audio.return_value = mock_transcription_response
        
        # Mock database save
        mock_db_session.add = Mock()
        mock_db_session.commit = AsyncMock()
        
        result = await transcription_service.transcribe_voice_attachment(
            access_token="test_token",
            voice_attachment_id="attachment_67890",
            model="azure-speech-to-text-v2",
            language="en-US"
        )
        
        assert result["transcript"] == "Hello, this is a test voice message. Please call me back when you get this."
        assert result["confidence_score"] == 0.95
        assert result["status"] == "completed"
        assert result["model_used"] == "azure-speech-to-text-v2"
        
        mock_azure_ai_service.transcribe_audio.assert_called_once()
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    async def test_transcribe_voice_attachment_not_found(self, transcription_service, mock_voice_attachment_service):
        """Test transcribing non-existent voice attachment."""
        mock_voice_attachment_service.download_attachment.side_effect = NotFoundError("Attachment not found")
        
        with pytest.raises(NotFoundError):
            await transcription_service.transcribe_voice_attachment(
                "test_token", "invalid_attachment", "azure-speech-to-text-v2"
            )

    async def test_transcribe_voice_attachment_ai_error(self, transcription_service, mock_azure_ai_service,
                                                        mock_voice_attachment_service, mock_db_session):
        """Test transcription with AI service error."""
        # Mock successful download
        mock_voice_attachment_service.download_attachment.return_value = (
            b"audio_data", "audio/wav", "test.wav"
        )
        
        # Mock AI service error
        mock_azure_ai_service.transcribe_audio.side_effect = Exception("AI service unavailable")
        
        result = await transcription_service.transcribe_voice_attachment(
            "test_token", "attachment_123", "azure-speech-to-text-v2"
        )
        
        assert result["status"] == "failed"
        assert "AI service unavailable" in result["error_message"]
        
        # Should still save failed record to database
        mock_db_session.add.assert_called_once()

    async def test_transcribe_voice_attachment_invalid_model(self, transcription_service):
        """Test transcription with invalid model."""
        with pytest.raises(ValidationError):
            await transcription_service.transcribe_voice_attachment(
                "test_token", "attachment_123", "invalid_model"
            )

    # =====================================================================
    # Transcription Retrieval Tests
    # =====================================================================

    async def test_get_transcription_by_id_success(self, transcription_service, mock_db_session, mock_transcription_record):
        """Test getting transcription by ID successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_transcription_record
        mock_db_session.execute.return_value = mock_result
        
        result = await transcription_service.get_transcription_by_id("trans_12345")
        
        assert result["id"] == "trans_12345"
        assert result["transcript"] == "Test transcript text"
        assert result["status"] == "completed"

    async def test_get_transcription_by_id_not_found(self, transcription_service, mock_db_session):
        """Test getting non-existent transcription."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await transcription_service.get_transcription_by_id("invalid_id")
        
        assert result is None

    async def test_get_transcription_by_voice_attachment_success(self, transcription_service, mock_db_session, 
                                                                 mock_transcription_record):
        """Test getting transcription by voice attachment ID."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_transcription_record
        mock_db_session.execute.return_value = mock_result
        
        result = await transcription_service.get_transcription_by_voice_attachment("attachment_67890")
        
        assert result["voice_attachment_id"] == "attachment_67890"
        assert result["transcript"] == "Test transcript text"

    # =====================================================================
    # Batch Transcription Tests
    # =====================================================================

    async def test_batch_transcribe_attachments_success(self, transcription_service, mock_azure_ai_service,
                                                        mock_voice_attachment_service, mock_transcription_response):
        """Test batch transcribing multiple attachments."""
        # Mock successful downloads
        mock_voice_attachment_service.download_attachment.return_value = (
            b"audio_data", "audio/wav", "test.wav"
        )
        
        # Mock successful transcriptions
        mock_azure_ai_service.transcribe_audio.return_value = mock_transcription_response
        
        attachment_ids = ["attachment1", "attachment2", "attachment3"]
        
        result = await transcription_service.batch_transcribe_attachments(
            access_token="test_token",
            voice_attachment_ids=attachment_ids,
            model="azure-speech-to-text-v2",
            language="en-US",
            batch_name="Test Batch"
        )
        
        assert result["total_attachments"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0
        assert len(result["results"]) == 3
        assert all(r["status"] == "completed" for r in result["results"])

    async def test_batch_transcribe_partial_success(self, transcription_service, mock_azure_ai_service,
                                                     mock_voice_attachment_service, mock_transcription_response):
        """Test batch transcription with some failures."""
        # Mock mixed download results
        def mock_download_side_effect(token, message_id, attachment_id):
            if attachment_id == "attachment2":
                raise NotFoundError("Attachment not found")
            return (b"audio_data", "audio/wav", "test.wav")
        
        mock_voice_attachment_service.download_attachment.side_effect = mock_download_side_effect
        mock_azure_ai_service.transcribe_audio.return_value = mock_transcription_response
        
        attachment_ids = ["attachment1", "attachment2", "attachment3"]
        
        result = await transcription_service.batch_transcribe_attachments(
            "test_token", attachment_ids, "azure-speech-to-text-v2"
        )
        
        assert result["total_attachments"] == 3
        assert result["successful"] == 2
        assert result["failed"] == 1
        
        # Check that failed attachment is properly recorded
        failed_results = [r for r in result["results"] if r["status"] == "failed"]
        assert len(failed_results) == 1
        assert failed_results[0]["voice_attachment_id"] == "attachment2"

    async def test_batch_transcribe_empty_list(self, transcription_service):
        """Test batch transcription with empty attachment list."""
        with pytest.raises(ValidationError):
            await transcription_service.batch_transcribe_attachments(
                "test_token", [], "azure-speech-to-text-v2"
            )

    # =====================================================================
    # Transcription List and Search Tests
    # =====================================================================

    async def test_list_transcriptions_success(self, transcription_service, mock_db_session):
        """Test listing transcriptions with default parameters."""
        mock_transcriptions = [
            Mock(
                id="trans_1",
                voice_attachment_id="att_1",
                transcript="First transcript",
                confidence_score=0.92,
                status="completed",
                created_at=datetime.now()
            ),
            Mock(
                id="trans_2",
                voice_attachment_id="att_2", 
                transcript="Second transcript",
                confidence_score=0.88,
                status="completed",
                created_at=datetime.now() - timedelta(hours=1)
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_transcriptions
        
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 2
        
        mock_db_session.execute.side_effect = [mock_result, mock_count_result]
        
        result = await transcription_service.list_transcriptions(
            user_id="user_123",
            limit=50,
            offset=0
        )
        
        assert len(result["transcriptions"]) == 2
        assert result["total_count"] == 2
        assert result["has_next"] is False
        assert result["transcriptions"][0]["id"] == "trans_1"

    async def test_list_transcriptions_with_filters(self, transcription_service, mock_db_session):
        """Test listing transcriptions with filters."""
        mock_filtered_results = [Mock(id="trans_1", status="completed")]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_filtered_results
        
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 1
        
        mock_db_session.execute.side_effect = [mock_result, mock_count_result]
        
        result = await transcription_service.list_transcriptions(
            user_id="user_123",
            status="completed",
            language="en-US",
            search="test query",
            limit=10
        )
        
        assert len(result["transcriptions"]) == 1
        assert result["transcriptions"][0]["status"] == "completed"

    async def test_list_transcriptions_pagination(self, transcription_service, mock_db_session):
        """Test listing transcriptions with pagination."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []  # Empty page
        
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 100  # Total count
        
        mock_db_session.execute.side_effect = [mock_result, mock_count_result]
        
        result = await transcription_service.list_transcriptions(
            user_id="user_123",
            limit=25,
            offset=75
        )
        
        assert result["has_next"] is True
        assert result["next_offset"] == 100
        assert result["total_count"] == 100

    # =====================================================================
    # Transcription Management Tests
    # =====================================================================

    async def test_delete_transcription_success(self, transcription_service, mock_db_session, mock_transcription_record):
        """Test deleting transcription successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_transcription_record
        mock_db_session.execute.return_value = mock_result
        
        result = await transcription_service.delete_transcription("trans_12345")
        
        assert result["status"] == "deleted"
        assert result["transcription_id"] == "trans_12345"
        
        mock_db_session.delete.assert_called_once_with(mock_transcription_record)
        mock_db_session.commit.assert_called_once()

    async def test_delete_transcription_not_found(self, transcription_service, mock_db_session):
        """Test deleting non-existent transcription."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(NotFoundError):
            await transcription_service.delete_transcription("invalid_id")

    async def test_retry_failed_transcription_success(self, transcription_service, mock_db_session,
                                                      mock_azure_ai_service, mock_transcription_response):
        """Test retrying failed transcription."""
        # Mock failed transcription record
        failed_record = Mock(
            id="trans_failed",
            voice_attachment_id="attachment_123",
            status="failed",
            retry_count=1,
            error_message="Previous error"
        )
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = failed_record
        mock_db_session.execute.return_value = mock_result
        
        # Mock successful retry
        mock_azure_ai_service.transcribe_audio.return_value = mock_transcription_response
        
        result = await transcription_service.retry_failed_transcription(
            access_token="test_token",
            voice_attachment_id="attachment_123",
            model="whisper-large"
        )
        
        assert result["status"] == "completed"
        assert result["voice_attachment_id"] == "attachment_123"
        
        # Should update the existing record
        assert failed_record.status == "completed"
        assert failed_record.retry_count == 2

    async def test_retry_transcription_not_failed(self, transcription_service, mock_db_session):
        """Test retrying transcription that's not in failed state."""
        completed_record = Mock(status="completed")
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = completed_record
        mock_db_session.execute.return_value = mock_result
        
        with pytest.raises(ValidationError):
            await transcription_service.retry_failed_transcription(
                "test_token", "attachment_123", "azure-speech-to-text-v2"
            )

    # =====================================================================
    # Statistics Tests
    # =====================================================================

    async def test_get_transcription_statistics_success(self, transcription_service, mock_db_session):
        """Test getting transcription statistics."""
        # Mock various statistic queries
        mock_total_result = Mock()
        mock_total_result.scalar.return_value = 150
        
        mock_status_results = Mock()
        mock_status_results.fetchall.return_value = [
            ("completed", 142),
            ("failed", 5),
            ("processing", 3)
        ]
        
        mock_model_results = Mock()
        mock_model_results.fetchall.return_value = [
            ("azure-speech-to-text-v2", 120),
            ("whisper-large", 30)
        ]
        
        mock_monthly_results = Mock()
        mock_monthly_results.fetchall.return_value = [
            ("2024-08", 45),
            ("2024-07", 52)
        ]
        
        mock_avg_confidence = Mock()
        mock_avg_confidence.scalar.return_value = 0.91
        
        mock_processing_time = Mock()
        mock_processing_time.scalar.return_value = 125000
        
        mock_db_session.execute.side_effect = [
            mock_total_result,
            mock_status_results,
            mock_model_results,
            mock_monthly_results,
            mock_avg_confidence,
            mock_processing_time
        ]
        
        result = await transcription_service.get_transcription_statistics("user_123")
        
        assert result["total_transcriptions"] == 150
        assert result["completed"] == 142
        assert result["failed"] == 5
        assert result["processing"] == 3
        assert result["average_confidence"] == 0.91
        assert result["total_processing_time_ms"] == 125000

    # =====================================================================
    # Error Handling Tests
    # =====================================================================

    async def test_list_transcription_errors_success(self, transcription_service, mock_db_session):
        """Test listing transcription errors."""
        mock_error_records = [
            Mock(
                id="error_1",
                transcription_id="trans_fail_1",
                voice_attachment_id="att_fail_1",
                error_type="audio_format_unsupported",
                error_message="Audio format not supported",
                occurred_at=datetime.now(),
                resolved=False,
                retry_count=2
            )
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_error_records
        mock_db_session.execute.return_value = mock_result
        
        result = await transcription_service.list_transcription_errors(
            user_id="user_123",
            resolved=False
        )
        
        assert len(result) == 1
        assert result[0]["id"] == "error_1"
        assert result[0]["resolved"] is False

    async def test_resolve_transcription_error_success(self, transcription_service, mock_db_session):
        """Test resolving transcription error."""
        mock_error_record = Mock(
            id="error_1",
            resolved=False,
            resolution_notes=None,
            resolved_at=None
        )
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_error_record
        mock_db_session.execute.return_value = mock_result
        
        result = await transcription_service.resolve_transcription_error(
            error_id="error_1",
            resolution_notes="Resolved by user action"
        )
        
        assert result["status"] == "resolved"
        assert result["error_id"] == "error_1"
        
        # Should update the error record
        assert mock_error_record.resolved is True
        assert mock_error_record.resolution_notes == "Resolved by user action"
        assert mock_error_record.resolved_at is not None

    # =====================================================================
    # Model Management Tests
    # =====================================================================

    async def test_get_supported_models_success(self, transcription_service, mock_azure_ai_service):
        """Test getting supported AI models."""
        mock_models = [
            {
                "id": "azure-speech-to-text-v2",
                "name": "Azure Speech-to-Text v2",
                "supported_languages": ["en-US", "en-GB", "es-ES"],
                "max_audio_length_seconds": 3600
            },
            {
                "id": "whisper-large",
                "name": "OpenAI Whisper Large",
                "supported_languages": ["en", "es", "fr", "de"],
                "max_audio_length_seconds": 1800
            }
        ]
        mock_azure_ai_service.get_supported_models.return_value = mock_models
        
        result = await transcription_service.get_supported_models()
        
        assert len(result) == 2
        assert result[0]["id"] == "azure-speech-to-text-v2"
        assert result[1]["id"] == "whisper-large"

    async def test_health_check_healthy(self, transcription_service, mock_azure_ai_service):
        """Test transcription service health check when healthy."""
        mock_health = {
            "status": "healthy",
            "service_available": True,
            "models_accessible": True,
            "queue_size": 3,
            "active_transcriptions": 2,
            "average_response_time_ms": 1250
        }
        mock_azure_ai_service.health_check.return_value = mock_health
        
        result = await transcription_service.health_check()
        
        assert result["status"] == "healthy"
        assert result["service_available"] is True
        assert result["queue_size"] == 3

    async def test_health_check_unhealthy(self, transcription_service, mock_azure_ai_service):
        """Test transcription service health check when unhealthy."""
        mock_azure_ai_service.health_check.side_effect = Exception("AI service connection failed")
        
        result = await transcription_service.health_check()
        
        assert result["status"] == "unhealthy"
        assert result["service_available"] is False
        assert "AI service connection failed" in result["error_message"]

    # =====================================================================
    # Utility Method Tests
    # =====================================================================

    async def test_validate_model_name_valid(self, transcription_service):
        """Test validating valid model names."""
        valid_models = [
            "azure-speech-to-text-v2",
            "whisper-large",
            "whisper-medium",
            "azure-speech-to-text-v1"
        ]
        
        for model in valid_models:
            # Should not raise exception
            transcription_service._validate_model_name(model)

    async def test_validate_model_name_invalid(self, transcription_service):
        """Test validating invalid model names."""
        invalid_models = [
            "",
            "invalid-model",
            "unknown-ai-model",
            None
        ]
        
        for model in invalid_models:
            with pytest.raises(ValidationError):
                transcription_service._validate_model_name(model)

    async def test_extract_text_statistics(self, transcription_service):
        """Test extracting text statistics from transcript."""
        transcript = "Hello, this is a test voice message. Please call me back when you get this."
        
        stats = transcription_service._extract_text_statistics(transcript)
        
        assert stats["word_count"] == 16
        assert stats["character_count"] == len(transcript)
        assert stats["sentence_count"] == 2  # Two sentences

    async def test_extract_text_statistics_empty(self, transcription_service):
        """Test extracting statistics from empty transcript."""
        stats = transcription_service._extract_text_statistics("")
        
        assert stats["word_count"] == 0
        assert stats["character_count"] == 0
        assert stats["sentence_count"] == 0

    async def test_generate_transcription_id(self, transcription_service):
        """Test generating unique transcription ID."""
        transcription_id = transcription_service._generate_transcription_id()
        
        assert transcription_id.startswith("trans_")
        assert len(transcription_id) > 10  # Should have sufficient length

    # =====================================================================
    # Concurrent Processing Tests
    # =====================================================================

    async def test_concurrent_transcriptions_handling(self, transcription_service, mock_azure_ai_service,
                                                      mock_voice_attachment_service, mock_transcription_response):
        """Test handling multiple concurrent transcription requests."""
        mock_voice_attachment_service.download_attachment.return_value = (
            b"audio_data", "audio/wav", "test.wav"
        )
        mock_azure_ai_service.transcribe_audio.return_value = mock_transcription_response
        
        # Send multiple concurrent transcription requests
        import asyncio
        
        tasks = [
            transcription_service.transcribe_voice_attachment(
                "test_token", f"attachment_{i}", "azure-speech-to-text-v2"
            )
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 5
        assert all(result["status"] == "completed" for result in results)