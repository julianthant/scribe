"""
Integration tests for VoiceAttachment API endpoints.

Tests all voice attachment endpoints including:
- GET /voice-attachments - Get all voice attachments
- GET /voice-attachments/voice-messages - Get messages with voice attachments  
- POST /voice-attachments/organize-voice - Organize voice messages
- GET /voice-attachments/{message_id}/{attachment_id}/metadata - Get attachment metadata
- GET /voice-attachments/{message_id}/{attachment_id}/download - Download attachment
- GET /voice-attachments/messages/{message_id} - Get message voice attachments
- GET /voice-attachments/statistics - Get voice statistics
- POST /voice-attachments/store/{message_id}/{attachment_id} - Store in blob
- GET /voice-attachments/stored - List stored attachments
- GET /voice-attachments/blob/{blob_name} - Download from blob
- DELETE /voice-attachments/blob/{blob_name} - Delete from blob
- GET /voice-attachments/storage-statistics - Storage statistics  
- POST /voice-attachments/cleanup - Cleanup expired attachments
"""

import pytest
import httpx
from unittest.mock import AsyncMock, Mock, patch

from tests.integration.utils import (
    IntegrationAPIClient,
    ResponseAssertions,
    DatabaseAssertions,
    TestWorkflows
)

class TestVoiceAttachmentEndpoints:
    """Integration tests for voice attachment endpoints."""

    @pytest.fixture
    async def api_client(self, async_client):
        """Create API client for voice attachment operations."""
        return IntegrationAPIClient(async_client)

    @pytest.fixture
    async def db_assertions(self, test_db):
        """Create database assertions helper."""
        return DatabaseAssertions(test_db)

    @pytest.fixture
    async def test_workflows(self, api_client, db_assertions):
        """Create test workflows helper."""
        return TestWorkflows(api_client, db_assertions)

    @pytest.fixture
    def mock_voice_attachments(self):
        """Mock voice attachment data."""
        return [
            {
                "id": "attachment1",
                "name": "voicemail.wav",
                "contentType": "audio/wav",
                "size": 52428,
                "message_id": "message1",
                "duration": 45.2,
                "sender": "user@example.com"
            },
            {
                "id": "attachment2", 
                "name": "audio_message.m4a",
                "contentType": "audio/mp4",
                "size": 31847,
                "message_id": "message2",
                "duration": 28.7,
                "sender": "colleague@example.com"
            }
        ]

    @pytest.fixture
    def mock_voice_messages(self):
        """Mock voice messages data."""
        return {
            "value": [
                {
                    "id": "message1",
                    "subject": "Voice message from user",
                    "from": {
                        "emailAddress": {
                            "name": "Test User",
                            "address": "user@example.com"
                        }
                    },
                    "receivedDateTime": "2024-08-28T10:00:00Z",
                    "hasAttachments": True,
                    "attachments": 1
                },
                {
                    "id": "message2",
                    "subject": "Quick voice update",
                    "from": {
                        "emailAddress": {
                            "name": "Colleague",
                            "address": "colleague@example.com"
                        }
                    },
                    "receivedDateTime": "2024-08-28T09:30:00Z",
                    "hasAttachments": True,
                    "attachments": 1
                }
            ]
        }

    # =====================================================================
    # GET /voice-attachments - Get all voice attachments
    # =====================================================================

    async def test_get_voice_attachments_success(self, api_client, mock_voice_attachments, authenticated_user):
        """Test getting all voice attachments successfully."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_all_voice_attachments') as mock_service:
            mock_service.return_value = mock_voice_attachments
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 2
            assert data[0]["id"] == "attachment1"
            assert data[0]["contentType"] == "audio/wav"
            assert data[1]["name"] == "audio_message.m4a"

    async def test_get_voice_attachments_with_folder_filter(self, api_client, mock_voice_attachments, authenticated_user):
        """Test getting voice attachments filtered by folder."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_all_voice_attachments') as mock_service:
            mock_service.return_value = [mock_voice_attachments[0]]
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments",
                params={"folder_id": "inbox"},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 1
            assert data[0]["id"] == "attachment1"
            mock_service.assert_called_once()

    async def test_get_voice_attachments_unauthenticated(self, api_client):
        """Test getting voice attachments without authentication."""
        response = await api_client.client.get("/api/v1/voice-attachments")
        ResponseAssertions.assert_authentication_error(response)

    # =====================================================================
    # GET /voice-attachments/voice-messages - Get messages with voice attachments
    # =====================================================================

    async def test_get_voice_messages_success(self, api_client, mock_voice_messages, authenticated_user):
        """Test getting messages with voice attachments."""
        with patch('app.services.MailService.MailService.get_messages_with_voice_attachments') as mock_service:
            mock_service.return_value = mock_voice_messages
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/voice-messages",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert "value" in data
            assert len(data["value"]) == 2
            assert data["value"][0]["id"] == "message1"
            assert data["value"][0]["hasAttachments"] is True

    async def test_get_voice_messages_with_limit(self, api_client, mock_voice_messages, authenticated_user):
        """Test getting voice messages with limit parameter."""
        with patch('app.services.MailService.MailService.get_messages_with_voice_attachments') as mock_service:
            mock_service.return_value = {"value": [mock_voice_messages["value"][0]]}
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/voice-messages",
                params={"limit": 1},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data["value"]) == 1

    # =====================================================================
    # POST /voice-attachments/organize-voice - Organize voice messages
    # =====================================================================

    async def test_organize_voice_messages_success(self, api_client, authenticated_user):
        """Test organizing voice messages into folder."""
        mock_result = {
            "status": "completed",
            "messages_moved": 5,
            "target_folder": "Voice Messages",
            "created_folder": True
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.organize_voice_messages') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.post(
                "/api/v1/voice-attachments/organize-voice",
                json={"targetFolderName": "Voice Messages"},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "completed"
            assert data["messages_moved"] == 5
            assert data["target_folder"] == "Voice Messages"

    async def test_organize_voice_messages_validation_error(self, api_client, authenticated_user):
        """Test organizing voice messages with invalid data."""
        response = await api_client.client.post(
            "/api/v1/voice-attachments/organize-voice",
            json={},  # Missing required fields
            headers=authenticated_user["headers"]
        )
        
        ResponseAssertions.assert_error_response(response, expected_status=422)

    # =====================================================================
    # GET /voice-attachments/{message_id}/{attachment_id}/metadata
    # =====================================================================

    async def test_get_attachment_metadata_success(self, api_client, authenticated_user):
        """Test getting voice attachment metadata."""
        mock_metadata = {
            "id": "attachment1",
            "name": "voicemail.wav",
            "contentType": "audio/wav",
            "size": 52428,
            "duration": 45.2,
            "message_id": "message1",
            "created_at": "2024-08-28T10:00:00Z"
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_attachment_metadata') as mock_service:
            mock_service.return_value = mock_metadata
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/message1/attachment1/metadata",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["id"] == "attachment1"
            assert data["contentType"] == "audio/wav"
            assert data["duration"] == 45.2

    async def test_get_attachment_metadata_not_found(self, api_client, authenticated_user):
        """Test getting metadata for non-existent attachment."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_attachment_metadata') as mock_service:
            mock_service.side_effect = Exception("Attachment not found")
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/invalid/invalid/metadata",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    # =====================================================================
    # GET /voice-attachments/{message_id}/{attachment_id}/download
    # =====================================================================

    async def test_download_attachment_success(self, api_client, authenticated_user):
        """Test downloading voice attachment."""
        mock_audio_data = b"fake audio content"
        mock_content_type = "audio/wav"
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.download_attachment') as mock_service:
            mock_service.return_value = (mock_audio_data, mock_content_type, "voicemail.wav")
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/message1/attachment1/download",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code == 200
            assert response.content == mock_audio_data
            assert "audio/wav" in response.headers.get("content-type", "")

    async def test_download_attachment_not_found(self, api_client, authenticated_user):
        """Test downloading non-existent attachment."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.download_attachment') as mock_service:
            mock_service.side_effect = Exception("Attachment not found")
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/invalid/invalid/download",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    # =====================================================================
    # GET /voice-attachments/messages/{message_id}
    # =====================================================================

    async def test_get_message_voice_attachments_success(self, api_client, mock_voice_attachments, authenticated_user):
        """Test getting voice attachments from specific message."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_message_voice_attachments') as mock_service:
            mock_service.return_value = [mock_voice_attachments[0]]
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/messages/message1",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 1
            assert data[0]["id"] == "attachment1"
            assert data[0]["message_id"] == "message1"

    # =====================================================================
    # GET /voice-attachments/statistics
    # =====================================================================

    async def test_get_voice_statistics_success(self, api_client, authenticated_user):
        """Test getting voice attachment statistics."""
        mock_stats = {
            "total_attachments": 25,
            "total_size_bytes": 1048576,
            "average_duration": 35.4,
            "most_common_format": "audio/wav",
            "attachments_by_month": [
                {"month": "2024-08", "count": 15},
                {"month": "2024-07", "count": 10}
            ]
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_voice_statistics') as mock_service:
            mock_service.return_value = mock_stats
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/statistics",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["total_attachments"] == 25
            assert data["most_common_format"] == "audio/wav"
            assert len(data["attachments_by_month"]) == 2

    # =====================================================================
    # Blob Storage Operations
    # =====================================================================

    async def test_store_attachment_in_blob_success(self, api_client, authenticated_user):
        """Test storing voice attachment in blob storage."""
        mock_result = {
            "status": "stored",
            "blob_name": "message1_attachment1.wav",
            "blob_url": "https://storage.blob.core.windows.net/voice-attachments/message1_attachment1.wav",
            "size_bytes": 52428
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.store_attachment_in_blob') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.post(
                "/api/v1/voice-attachments/store/message1/attachment1",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "stored"
            assert data["blob_name"] == "message1_attachment1.wav"
            assert data["size_bytes"] == 52428

    async def test_get_stored_attachments_success(self, api_client, authenticated_user):
        """Test getting list of stored voice attachments."""
        mock_stored = [
            {
                "blob_name": "message1_attachment1.wav",
                "original_name": "voicemail.wav",
                "size_bytes": 52428,
                "stored_at": "2024-08-28T10:00:00Z",
                "message_id": "message1",
                "attachment_id": "attachment1"
            }
        ]
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_stored_attachments') as mock_service:
            mock_service.return_value = mock_stored
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/stored",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 1
            assert data[0]["blob_name"] == "message1_attachment1.wav"
            assert data[0]["size_bytes"] == 52428

    async def test_download_from_blob_success(self, api_client, authenticated_user):
        """Test downloading attachment from blob storage."""
        mock_audio_data = b"blob stored audio content"
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.download_from_blob') as mock_service:
            mock_service.return_value = (mock_audio_data, "audio/wav", "voicemail.wav")
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/blob/message1_attachment1.wav",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code == 200
            assert response.content == mock_audio_data

    async def test_delete_blob_attachment_success(self, api_client, authenticated_user):
        """Test deleting attachment from blob storage."""
        mock_result = {
            "status": "deleted",
            "blob_name": "message1_attachment1.wav"
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.delete_blob_attachment') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.delete(
                "/api/v1/voice-attachments/blob/message1_attachment1.wav",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "deleted"
            assert data["blob_name"] == "message1_attachment1.wav"

    async def test_get_storage_statistics_success(self, api_client, authenticated_user):
        """Test getting blob storage statistics."""
        mock_stats = {
            "total_stored": 12,
            "total_size_bytes": 2097152,
            "average_size_bytes": 174762,
            "oldest_stored": "2024-07-01T00:00:00Z",
            "newest_stored": "2024-08-28T10:00:00Z"
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_storage_statistics') as mock_service:
            mock_service.return_value = mock_stats
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/storage-statistics",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["total_stored"] == 12
            assert data["total_size_bytes"] == 2097152

    async def test_cleanup_expired_attachments_success(self, api_client, authenticated_user):
        """Test cleaning up expired voice attachments."""
        mock_result = {
            "status": "completed",
            "attachments_deleted": 5,
            "space_freed_bytes": 524288,
            "cleanup_time": "2024-08-28T10:00:00Z"
        }
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.cleanup_expired_attachments') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.post(
                "/api/v1/voice-attachments/cleanup",
                json={"days_to_keep": 30},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "completed"
            assert data["attachments_deleted"] == 5
            assert data["space_freed_bytes"] == 524288

    # =====================================================================
    # Error Handling Tests
    # =====================================================================

    async def test_service_unavailable_error(self, api_client, authenticated_user):
        """Test handling of service unavailable errors."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.get_all_voice_attachments') as mock_service:
            mock_service.side_effect = Exception("Service temporarily unavailable")
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code == 500

    async def test_invalid_parameters(self, api_client, authenticated_user):
        """Test handling of invalid query parameters."""
        response = await api_client.client.get(
            "/api/v1/voice-attachments",
            params={"limit": -1},  # Invalid limit
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code in [400, 422]  # Validation error

    async def test_large_attachment_handling(self, api_client, authenticated_user):
        """Test handling of large attachment operations."""
        mock_large_data = b"x" * (10 * 1024 * 1024)  # 10MB mock data
        
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService.download_attachment') as mock_service:
            mock_service.return_value = (mock_large_data, "audio/wav", "large_voicemail.wav")
            
            response = await api_client.client.get(
                "/api/v1/voice-attachments/message1/large_attachment/download",
                headers=authenticated_user["headers"]
            )
            
            # Should handle large files without issues
            assert response.status_code == 200
            assert len(response.content) == len(mock_large_data)