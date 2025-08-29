"""
Integration tests for Transcription API endpoints.

Tests all transcription endpoints including:
- POST /transcriptions/voice/{voice_attachment_id} - Create transcription
- GET /transcriptions/voice/{voice_attachment_id} - Get transcription by voice attachment
- GET /transcriptions/{transcription_id} - Get transcription by ID
- POST /transcriptions/batch - Batch transcribe multiple attachments
- GET /transcriptions - List transcriptions with filtering
- DELETE /transcriptions/{transcription_id} - Delete transcription
- GET /transcriptions/statistics/summary - Get transcription statistics
- GET /transcriptions/errors/list - List transcription errors
- POST /transcriptions/errors/{error_id}/resolve - Resolve transcription error
- POST /transcriptions/voice/{voice_attachment_id}/retry - Retry failed transcription
- GET /transcriptions/models/supported - Get supported AI models
- GET /transcriptions/health/status - Health check for transcription service
"""

import pytest
import httpx
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from tests.integration.utils import (
    IntegrationAPIClient,
    ResponseAssertions,
    DatabaseAssertions,
    TestWorkflows
)

class TestTranscriptionEndpoints:
    """Integration tests for transcription endpoints."""

    @pytest.fixture
    async def api_client(self, async_client):
        """Create API client for transcription operations."""
        return IntegrationAPIClient(async_client)

    @pytest.fixture
    async def db_assertions(self, test_db):
        """Create database assertions helper."""
        return DatabaseAssertions(test_db)

    @pytest.fixture
    def mock_transcription_response(self):
        """Mock transcription response data."""
        return {
            "id": "trans_12345",
            "voice_attachment_id": "attachment_67890",
            "transcript": "Hello, this is a test voice message. Please call me back when you get this.",
            "confidence_score": 0.95,
            "language": "en-US",
            "model_used": "azure-speech-to-text-v2",
            "status": "completed",
            "processing_time_ms": 1250,
            "created_at": "2024-08-28T10:00:00Z",
            "completed_at": "2024-08-28T10:00:01.250Z",
            "error_message": None,
            "word_count": 16,
            "character_count": 78
        }

    @pytest.fixture
    def mock_batch_transcribe_response(self):
        """Mock batch transcription response."""
        return {
            "batch_id": "batch_abc123",
            "total_attachments": 3,
            "successful": 2,
            "failed": 1,
            "processing_time_ms": 3750,
            "results": [
                {
                    "voice_attachment_id": "attachment1",
                    "transcription_id": "trans_1",
                    "status": "completed",
                    "transcript": "First voice message transcript."
                },
                {
                    "voice_attachment_id": "attachment2", 
                    "transcription_id": "trans_2",
                    "status": "completed",
                    "transcript": "Second voice message transcript."
                },
                {
                    "voice_attachment_id": "attachment3",
                    "transcription_id": None,
                    "status": "failed",
                    "error": "Audio format not supported"
                }
            ]
        }

    @pytest.fixture
    def mock_transcription_list(self):
        """Mock transcription list response."""
        return {
            "transcriptions": [
                {
                    "id": "trans_1",
                    "voice_attachment_id": "attachment_1",
                    "transcript": "First transcript text",
                    "confidence_score": 0.92,
                    "status": "completed",
                    "created_at": "2024-08-28T09:00:00Z"
                },
                {
                    "id": "trans_2",
                    "voice_attachment_id": "attachment_2", 
                    "transcript": "Second transcript text",
                    "confidence_score": 0.88,
                    "status": "completed",
                    "created_at": "2024-08-28T08:30:00Z"
                }
            ],
            "total_count": 2,
            "has_next": False,
            "next_offset": None
        }

    # =====================================================================
    # POST /transcriptions/voice/{voice_attachment_id} - Create transcription
    # =====================================================================

    async def test_create_transcription_success(self, api_client, mock_transcription_response, authenticated_user):
        """Test creating transcription for voice attachment."""
        with patch('app.services.TranscriptionService.TranscriptionService.transcribe_voice_attachment') as mock_service:
            mock_service.return_value = mock_transcription_response
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/voice/attachment_67890",
                json={"model": "azure-speech-to-text-v2", "language": "en-US"},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["id"] == "trans_12345"
            assert data["transcript"] == "Hello, this is a test voice message. Please call me back when you get this."
            assert data["confidence_score"] == 0.95
            assert data["status"] == "completed"
            assert data["model_used"] == "azure-speech-to-text-v2"

    async def test_create_transcription_invalid_attachment(self, api_client, authenticated_user):
        """Test creating transcription with invalid voice attachment ID."""
        with patch('app.services.TranscriptionService.TranscriptionService.transcribe_voice_attachment') as mock_service:
            mock_service.side_effect = Exception("Voice attachment not found")
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/voice/invalid_attachment",
                json={"model": "azure-speech-to-text-v2"},
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    async def test_create_transcription_unauthenticated(self, api_client):
        """Test creating transcription without authentication."""
        response = await api_client.client.post(
            "/api/v1/transcriptions/voice/attachment_123",
            json={"model": "azure-speech-to-text-v2"}
        )
        ResponseAssertions.assert_authentication_error(response)

    # =====================================================================
    # GET /transcriptions/voice/{voice_attachment_id} - Get by voice attachment
    # =====================================================================

    async def test_get_transcription_by_voice_attachment_success(self, api_client, mock_transcription_response, authenticated_user):
        """Test getting transcription by voice attachment ID."""
        with patch('app.services.TranscriptionService.TranscriptionService.get_transcription_by_voice_attachment') as mock_service:
            mock_service.return_value = mock_transcription_response
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/voice/attachment_67890",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["voice_attachment_id"] == "attachment_67890"
            assert data["transcript"] is not None
            assert data["status"] == "completed"

    async def test_get_transcription_by_voice_attachment_not_found(self, api_client, authenticated_user):
        """Test getting transcription for non-existent voice attachment."""
        with patch('app.services.TranscriptionService.TranscriptionService.get_transcription_by_voice_attachment') as mock_service:
            mock_service.return_value = None
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/voice/nonexistent",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_not_found_error(response)

    # =====================================================================
    # GET /transcriptions/{transcription_id} - Get transcription by ID
    # =====================================================================

    async def test_get_transcription_by_id_success(self, api_client, mock_transcription_response, authenticated_user):
        """Test getting transcription by transcription ID."""
        with patch('app.services.TranscriptionService.TranscriptionService.get_transcription_by_id') as mock_service:
            mock_service.return_value = mock_transcription_response
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/trans_12345",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["id"] == "trans_12345"
            assert data["transcript"] is not None

    async def test_get_transcription_by_id_not_found(self, api_client, authenticated_user):
        """Test getting non-existent transcription by ID."""
        with patch('app.services.TranscriptionService.TranscriptionService.get_transcription_by_id') as mock_service:
            mock_service.return_value = None
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/invalid_id",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_not_found_error(response)

    # =====================================================================
    # POST /transcriptions/batch - Batch transcribe multiple attachments
    # =====================================================================

    async def test_batch_transcribe_success(self, api_client, mock_batch_transcribe_response, authenticated_user):
        """Test batch transcribing multiple voice attachments."""
        with patch('app.services.TranscriptionService.TranscriptionService.batch_transcribe_attachments') as mock_service:
            mock_service.return_value = mock_batch_transcribe_response
            
            request_data = {
                "voice_attachment_ids": ["attachment1", "attachment2", "attachment3"],
                "model": "azure-speech-to-text-v2",
                "language": "en-US",
                "batch_name": "Daily Voice Messages"
            }
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/batch",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["batch_id"] == "batch_abc123"
            assert data["total_attachments"] == 3
            assert data["successful"] == 2
            assert data["failed"] == 1
            assert len(data["results"]) == 3

    async def test_batch_transcribe_empty_list(self, api_client, authenticated_user):
        """Test batch transcribing with empty attachment list."""
        response = await api_client.client.post(
            "/api/v1/transcriptions/batch",
            json={"voice_attachment_ids": [], "model": "azure-speech-to-text-v2"},
            headers=authenticated_user["headers"]
        )
        
        ResponseAssertions.assert_validation_error(response)

    # =====================================================================
    # GET /transcriptions - List transcriptions with filtering
    # =====================================================================

    async def test_list_transcriptions_success(self, api_client, mock_transcription_list, authenticated_user):
        """Test listing transcriptions with default parameters."""
        with patch('app.services.TranscriptionService.TranscriptionService.list_transcriptions') as mock_service:
            mock_service.return_value = mock_transcription_list
            
            response = await api_client.client.get(
                "/api/v1/transcriptions",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert "transcriptions" in data
            assert len(data["transcriptions"]) == 2
            assert data["total_count"] == 2
            assert data["has_next"] is False

    async def test_list_transcriptions_with_filters(self, api_client, mock_transcription_list, authenticated_user):
        """Test listing transcriptions with filters."""
        with patch('app.services.TranscriptionService.TranscriptionService.list_transcriptions') as mock_service:
            mock_service.return_value = {
                "transcriptions": [mock_transcription_list["transcriptions"][0]],
                "total_count": 1,
                "has_next": False,
                "next_offset": None
            }
            
            response = await api_client.client.get(
                "/api/v1/transcriptions",
                params={
                    "status": "completed",
                    "language": "en-US",
                    "search": "voice message",
                    "limit": 10
                },
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data["transcriptions"]) == 1
            mock_service.assert_called_once()

    async def test_list_transcriptions_with_pagination(self, api_client, authenticated_user):
        """Test listing transcriptions with pagination."""
        with patch('app.services.TranscriptionService.TranscriptionService.list_transcriptions') as mock_service:
            mock_service.return_value = {
                "transcriptions": [],
                "total_count": 100,
                "has_next": True,
                "next_offset": 50
            }
            
            response = await api_client.client.get(
                "/api/v1/transcriptions",
                params={"limit": 50, "offset": 0},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["has_next"] is True
            assert data["next_offset"] == 50
            assert data["total_count"] == 100

    # =====================================================================
    # DELETE /transcriptions/{transcription_id} - Delete transcription
    # =====================================================================

    async def test_delete_transcription_success(self, api_client, authenticated_user):
        """Test deleting transcription successfully."""
        mock_result = {"status": "deleted", "transcription_id": "trans_12345"}
        
        with patch('app.services.TranscriptionService.TranscriptionService.delete_transcription') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.delete(
                "/api/v1/transcriptions/trans_12345",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response, expected_status=200)
            data = response.json()
            
            assert data["status"] == "deleted"
            assert data["transcription_id"] == "trans_12345"

    async def test_delete_transcription_not_found(self, api_client, authenticated_user):
        """Test deleting non-existent transcription."""
        with patch('app.services.TranscriptionService.TranscriptionService.delete_transcription') as mock_service:
            mock_service.side_effect = Exception("Transcription not found")
            
            response = await api_client.client.delete(
                "/api/v1/transcriptions/invalid_id",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    # =====================================================================
    # GET /transcriptions/statistics/summary - Get transcription statistics
    # =====================================================================

    async def test_get_transcription_statistics_success(self, api_client, authenticated_user):
        """Test getting transcription statistics."""
        mock_stats = {
            "total_transcriptions": 150,
            "completed": 142,
            "failed": 5,
            "processing": 3,
            "average_confidence": 0.91,
            "most_common_language": "en-US",
            "total_processing_time_ms": 125000,
            "average_processing_time_ms": 833,
            "transcriptions_by_model": {
                "azure-speech-to-text-v2": 120,
                "whisper-large": 30
            },
            "transcriptions_by_month": [
                {"month": "2024-08", "count": 45},
                {"month": "2024-07", "count": 52}
            ]
        }
        
        with patch('app.services.TranscriptionService.TranscriptionService.get_transcription_statistics') as mock_service:
            mock_service.return_value = mock_stats
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/statistics/summary",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["total_transcriptions"] == 150
            assert data["completed"] == 142
            assert data["average_confidence"] == 0.91
            assert "transcriptions_by_model" in data
            assert len(data["transcriptions_by_month"]) == 2

    # =====================================================================
    # GET /transcriptions/errors/list - List transcription errors
    # =====================================================================

    async def test_list_transcription_errors_success(self, api_client, authenticated_user):
        """Test listing transcription errors."""
        mock_errors = [
            {
                "id": "error_1",
                "transcription_id": "trans_fail_1",
                "voice_attachment_id": "attachment_fail_1",
                "error_type": "audio_format_unsupported",
                "error_message": "Audio format not supported by transcription service",
                "occurred_at": "2024-08-28T09:00:00Z",
                "resolved": False,
                "retry_count": 2
            },
            {
                "id": "error_2", 
                "transcription_id": "trans_fail_2",
                "voice_attachment_id": "attachment_fail_2",
                "error_type": "service_timeout",
                "error_message": "Transcription service timed out",
                "occurred_at": "2024-08-28T08:30:00Z",
                "resolved": True,
                "retry_count": 1
            }
        ]
        
        with patch('app.services.TranscriptionService.TranscriptionService.list_transcription_errors') as mock_service:
            mock_service.return_value = mock_errors
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/errors/list",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 2
            assert data[0]["id"] == "error_1"
            assert data[0]["resolved"] is False
            assert data[1]["resolved"] is True

    async def test_list_transcription_errors_filtered(self, api_client, authenticated_user):
        """Test listing transcription errors with filters."""
        mock_errors = [
            {
                "id": "error_1",
                "error_type": "audio_format_unsupported",
                "resolved": False,
                "occurred_at": "2024-08-28T09:00:00Z"
            }
        ]
        
        with patch('app.services.TranscriptionService.TranscriptionService.list_transcription_errors') as mock_service:
            mock_service.return_value = mock_errors
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/errors/list",
                params={"resolved": False, "error_type": "audio_format_unsupported"},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 1
            assert data[0]["resolved"] is False

    # =====================================================================
    # POST /transcriptions/errors/{error_id}/resolve - Resolve error
    # =====================================================================

    async def test_resolve_transcription_error_success(self, api_client, authenticated_user):
        """Test resolving transcription error."""
        mock_result = {
            "status": "resolved",
            "error_id": "error_1",
            "resolved_at": "2024-08-28T10:00:00Z",
            "resolution_notes": "Error resolved by user action"
        }
        
        with patch('app.services.TranscriptionService.TranscriptionService.resolve_transcription_error') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/errors/error_1/resolve",
                json={"resolution_notes": "Error resolved by user action"},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "resolved"
            assert data["error_id"] == "error_1"
            assert "resolved_at" in data

    # =====================================================================
    # POST /transcriptions/voice/{voice_attachment_id}/retry - Retry failed transcription
    # =====================================================================

    async def test_retry_failed_transcription_success(self, api_client, mock_transcription_response, authenticated_user):
        """Test retrying failed transcription."""
        with patch('app.services.TranscriptionService.TranscriptionService.retry_failed_transcription') as mock_service:
            mock_service.return_value = mock_transcription_response
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/voice/attachment_67890/retry",
                json={"model": "whisper-large", "force_retry": True},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "completed"
            assert data["voice_attachment_id"] == "attachment_67890"

    async def test_retry_transcription_not_failed(self, api_client, authenticated_user):
        """Test retrying transcription that hasn't failed."""
        with patch('app.services.TranscriptionService.TranscriptionService.retry_failed_transcription') as mock_service:
            mock_service.side_effect = Exception("Transcription is not in failed state")
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/voice/attachment_completed/retry",
                json={"model": "azure-speech-to-text-v2"},
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [400, 500]

    # =====================================================================
    # GET /transcriptions/models/supported - Get supported AI models
    # =====================================================================

    async def test_get_supported_models_success(self, api_client, authenticated_user):
        """Test getting list of supported transcription models."""
        mock_models = [
            {
                "id": "azure-speech-to-text-v2",
                "name": "Azure Speech-to-Text v2",
                "description": "Microsoft Azure Speech Services v2 with improved accuracy",
                "supported_languages": ["en-US", "en-GB", "es-ES", "fr-FR"],
                "max_audio_length_seconds": 3600,
                "supported_formats": ["wav", "mp3", "m4a", "ogg"],
                "average_processing_time_factor": 0.1
            },
            {
                "id": "whisper-large",
                "name": "OpenAI Whisper Large",
                "description": "OpenAI Whisper large model with multilingual support", 
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "zh"],
                "max_audio_length_seconds": 1800,
                "supported_formats": ["wav", "mp3", "m4a"],
                "average_processing_time_factor": 0.25
            }
        ]
        
        with patch('app.services.TranscriptionService.TranscriptionService.get_supported_models') as mock_service:
            mock_service.return_value = mock_models
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/models/supported",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 2
            assert data[0]["id"] == "azure-speech-to-text-v2"
            assert "supported_languages" in data[0]
            assert data[1]["id"] == "whisper-large"

    # =====================================================================
    # GET /transcriptions/health/status - Health check for transcription service
    # =====================================================================

    async def test_transcription_health_check_healthy(self, api_client, authenticated_user):
        """Test transcription service health check when healthy."""
        mock_health = {
            "status": "healthy",
            "service_available": True,
            "models_accessible": True,
            "queue_size": 3,
            "active_transcriptions": 2,
            "average_response_time_ms": 1250,
            "last_successful_transcription": "2024-08-28T09:55:00Z",
            "error_rate_percentage": 2.1,
            "uptime_seconds": 86400
        }
        
        with patch('app.services.TranscriptionService.TranscriptionService.health_check') as mock_service:
            mock_service.return_value = mock_health
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/health/status",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "healthy"
            assert data["service_available"] is True
            assert data["models_accessible"] is True
            assert data["queue_size"] == 3

    async def test_transcription_health_check_unhealthy(self, api_client, authenticated_user):
        """Test transcription service health check when unhealthy."""
        mock_health = {
            "status": "unhealthy",
            "service_available": False,
            "models_accessible": False,
            "error_message": "Transcription service is temporarily unavailable",
            "last_error": "Connection timeout to Azure Speech Services"
        }
        
        with patch('app.services.TranscriptionService.TranscriptionService.health_check') as mock_service:
            mock_service.return_value = mock_health
            
            response = await api_client.client.get(
                "/api/v1/transcriptions/health/status",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "unhealthy"
            assert data["service_available"] is False
            assert "error_message" in data

    # =====================================================================
    # Error Handling Tests
    # =====================================================================

    async def test_invalid_model_parameter(self, api_client, authenticated_user):
        """Test handling invalid model parameter."""
        response = await api_client.client.post(
            "/api/v1/transcriptions/voice/attachment_123",
            json={"model": "invalid_model"},
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code in [400, 422]

    async def test_service_timeout_handling(self, api_client, authenticated_user):
        """Test handling of transcription service timeouts."""
        with patch('app.services.TranscriptionService.TranscriptionService.transcribe_voice_attachment') as mock_service:
            mock_service.side_effect = Exception("Service timeout")
            
            response = await api_client.client.post(
                "/api/v1/transcriptions/voice/attachment_123",
                json={"model": "azure-speech-to-text-v2"},
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code == 500

    async def test_large_batch_size_limit(self, api_client, authenticated_user):
        """Test batch transcription with too many attachments."""
        large_attachment_list = [f"attachment_{i}" for i in range(101)]  # Exceeding limit
        
        response = await api_client.client.post(
            "/api/v1/transcriptions/batch",
            json={
                "voice_attachment_ids": large_attachment_list,
                "model": "azure-speech-to-text-v2"
            },
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code in [400, 422]  # Should validate batch size limit

    async def test_concurrent_transcriptions_handling(self, api_client, mock_transcription_response, authenticated_user):
        """Test handling multiple concurrent transcription requests."""
        with patch('app.services.TranscriptionService.TranscriptionService.transcribe_voice_attachment') as mock_service:
            mock_service.return_value = mock_transcription_response
            
            # Send multiple concurrent requests
            tasks = []
            for i in range(5):
                task = api_client.client.post(
                    f"/api/v1/transcriptions/voice/attachment_{i}",
                    json={"model": "azure-speech-to-text-v2"},
                    headers=authenticated_user["headers"]
                )
                tasks.append(task)
            
            # All should complete successfully
            import asyncio
            responses = await asyncio.gather(*tasks)
            
            for response in responses:
                assert response.status_code in [200, 202]  # Either completed or accepted for processing