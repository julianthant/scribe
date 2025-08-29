"""
Unit tests for MailService.

Tests the core mail operations service including:
- Mail folder operations
- Message retrieval and management
- Message operations (move, update, delete)
- Search functionality
- Voice message detection and organization
- Authentication integration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.MailService import MailService
from app.core.Exceptions import ValidationError, AuthenticationError, NotFoundError


class TestMailService:
    """Unit tests for MailService class."""

    @pytest.fixture
    def mock_azure_graph_service(self):
        """Mock AzureGraphService dependency."""
        mock_service = Mock()
        mock_service.get_mail_folders = AsyncMock()
        mock_service.create_mail_folder = AsyncMock()
        mock_service.get_messages = AsyncMock()
        mock_service.get_message = AsyncMock()
        mock_service.get_attachments = AsyncMock()
        mock_service.download_attachment = AsyncMock()
        mock_service.move_message = AsyncMock()
        mock_service.update_message = AsyncMock()
        mock_service.search_messages = AsyncMock()
        return mock_service

    @pytest.fixture
    def mail_service(self, mock_azure_graph_service):
        """Create MailService instance with mocked dependencies."""
        with patch('app.services.MailService.azure_graph_service', mock_azure_graph_service):
            return MailService()

    @pytest.fixture
    def mock_folders_response(self):
        """Mock folders API response."""
        return {
            "value": [
                {
                    "id": "inbox",
                    "displayName": "Inbox", 
                    "parentFolderId": None,
                    "unreadItemCount": 5,
                    "totalItemCount": 50
                },
                {
                    "id": "sent",
                    "displayName": "Sent Items",
                    "parentFolderId": None, 
                    "unreadItemCount": 0,
                    "totalItemCount": 25
                }
            ]
        }

    @pytest.fixture
    def mock_messages_response(self):
        """Mock messages API response."""
        return {
            "value": [
                {
                    "id": "message1",
                    "subject": "Test Subject",
                    "from": {
                        "emailAddress": {
                            "name": "Test User",
                            "address": "test@example.com"
                        }
                    },
                    "receivedDateTime": "2024-08-28T10:00:00Z",
                    "isRead": False,
                    "hasAttachments": True,
                    "importance": "normal",
                    "body": {
                        "content": "Test email content",
                        "contentType": "html"
                    }
                }
            ],
            "@odata.nextLink": None
        }

    @pytest.fixture
    def mock_message_detail(self):
        """Mock single message detail response."""
        return {
            "id": "message1",
            "subject": "Test Voice Message",
            "from": {
                "emailAddress": {
                    "name": "Test User", 
                    "address": "test@example.com"
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "name": "Recipient",
                        "address": "recipient@example.com"
                    }
                }
            ],
            "receivedDateTime": "2024-08-28T10:00:00Z",
            "isRead": False,
            "hasAttachments": True,
            "attachments": [
                {
                    "id": "attachment1",
                    "name": "voicemail.wav",
                    "contentType": "audio/wav",
                    "size": 52428
                }
            ]
        }

    # =====================================================================
    # Mail Folder Operations Tests
    # =====================================================================

    async def test_get_mail_folders_success(self, mail_service, mock_azure_graph_service, mock_folders_response):
        """Test getting mail folders successfully."""
        mock_azure_graph_service.get_mail_folders.return_value = mock_folders_response
        
        result = await mail_service.get_mail_folders("test_token")
        
        assert result == mock_folders_response
        mock_azure_graph_service.get_mail_folders.assert_called_once_with("test_token")

    async def test_get_mail_folders_auth_error(self, mail_service, mock_azure_graph_service):
        """Test getting mail folders with authentication error."""
        mock_azure_graph_service.get_mail_folders.side_effect = AuthenticationError(
            "Invalid access token"
        )
        
        with pytest.raises(AuthenticationError):
            await mail_service.get_mail_folders("invalid_token")

    async def test_create_mail_folder_success(self, mail_service, mock_azure_graph_service):
        """Test creating mail folder successfully."""
        mock_response = {
            "id": "new_folder",
            "displayName": "Voice Messages",
            "parentFolderId": "inbox"
        }
        mock_azure_graph_service.create_mail_folder.return_value = mock_response
        
        result = await mail_service.create_mail_folder(
            access_token="test_token",
            folder_name="Voice Messages",
            parent_folder_id="inbox"
        )
        
        assert result == mock_response
        mock_azure_graph_service.create_mail_folder.assert_called_once_with(
            "test_token",
            "Voice Messages",
            "inbox"
        )

    async def test_create_mail_folder_validation_error(self, mail_service):
        """Test creating mail folder with invalid name."""
        with pytest.raises(ValidationError):
            await mail_service.create_mail_folder(
                access_token="test_token",
                folder_name="",  # Empty name
                parent_folder_id="inbox"
            )

    # =====================================================================
    # Message Retrieval Tests
    # =====================================================================

    async def test_get_messages_success(self, mail_service, mock_azure_graph_service, mock_messages_response):
        """Test getting messages successfully."""
        mock_azure_graph_service.get_messages.return_value = mock_messages_response
        
        result = await mail_service.get_messages(
            access_token="test_token",
            folder_id="inbox",
            top=25,
            skip=0
        )
        
        assert result == mock_messages_response
        mock_azure_graph_service.get_messages.assert_called_once_with(
            "test_token",
            folder_id="inbox",
            top=25,
            skip=0,
            has_attachments=None,
            filter_query=None
        )

    async def test_get_messages_with_attachments_filter(self, mail_service, mock_azure_graph_service, mock_messages_response):
        """Test getting messages filtered by attachments."""
        mock_azure_graph_service.get_messages.return_value = mock_messages_response
        
        result = await mail_service.get_messages(
            access_token="test_token",
            folder_id="inbox",
            has_attachments=True
        )
        
        assert result == mock_messages_response
        mock_azure_graph_service.get_messages.assert_called_once_with(
            "test_token",
            folder_id="inbox",
            top=25,
            skip=0,
            has_attachments=True,
            filter_query=None
        )

    async def test_get_message_detail_success(self, mail_service, mock_azure_graph_service, mock_message_detail):
        """Test getting single message detail."""
        mock_azure_graph_service.get_message.return_value = mock_message_detail
        
        result = await mail_service.get_message(
            access_token="test_token",
            message_id="message1"
        )
        
        assert result == mock_message_detail
        mock_azure_graph_service.get_message.assert_called_once_with("test_token", "message1")

    async def test_get_message_not_found(self, mail_service, mock_azure_graph_service):
        """Test getting non-existent message."""
        mock_azure_graph_service.get_message.side_effect = NotFoundError("Message not found")
        
        with pytest.raises(NotFoundError):
            await mail_service.get_message("test_token", "nonexistent")

    # =====================================================================
    # Message Attachment Tests
    # =====================================================================

    async def test_get_message_attachments_success(self, mail_service, mock_azure_graph_service):
        """Test getting message attachments successfully."""
        mock_attachments = [
            {
                "id": "attachment1",
                "name": "document.pdf",
                "contentType": "application/pdf",
                "size": 52428
            }
        ]
        mock_azure_graph_service.get_attachments.return_value = mock_attachments
        
        result = await mail_service.get_message_attachments(
            access_token="test_token",
            message_id="message1"
        )
        
        assert result == mock_attachments
        mock_azure_graph_service.get_attachments.assert_called_once_with("test_token", "message1")

    async def test_download_attachment_success(self, mail_service, mock_azure_graph_service):
        """Test downloading attachment successfully."""
        mock_attachment_data = b"fake file content"
        mock_azure_graph_service.download_attachment.return_value = mock_attachment_data
        
        result = await mail_service.download_attachment(
            access_token="test_token",
            message_id="message1",
            attachment_id="attachment1"
        )
        
        assert result == mock_attachment_data
        mock_azure_graph_service.download_attachment.assert_called_once_with(
            "test_token",
            "message1", 
            "attachment1"
        )

    async def test_download_attachment_not_found(self, mail_service, mock_azure_graph_service):
        """Test downloading non-existent attachment."""
        mock_azure_graph_service.download_attachment.side_effect = NotFoundError("Attachment not found")
        
        with pytest.raises(NotFoundError):
            await mail_service.download_attachment("test_token", "message1", "invalid")

    # =====================================================================
    # Message Operations Tests
    # =====================================================================

    async def test_move_message_success(self, mail_service, mock_azure_graph_service):
        """Test moving message to different folder."""
        mock_response = {
            "id": "message1",
            "parentFolderId": "target_folder"
        }
        mock_azure_graph_service.move_message.return_value = mock_response
        
        result = await mail_service.move_message(
            access_token="test_token",
            message_id="message1",
            destination_folder_id="target_folder"
        )
        
        assert result == mock_response
        mock_azure_graph_service.move_message.assert_called_once_with(
            "test_token",
            "message1",
            "target_folder"
        )

    async def test_move_message_validation_error(self, mail_service):
        """Test moving message with invalid destination."""
        with pytest.raises(ValidationError):
            await mail_service.move_message(
                access_token="test_token",
                message_id="message1",
                destination_folder_id=""  # Empty destination
            )

    async def test_update_message_success(self, mail_service, mock_azure_graph_service):
        """Test updating message properties."""
        mock_response = {
            "id": "message1",
            "isRead": True,
            "importance": "high"
        }
        mock_azure_graph_service.update_message.return_value = mock_response
        
        result = await mail_service.update_message(
            access_token="test_token",
            message_id="message1",
            is_read=True,
            importance="high"
        )
        
        assert result == mock_response
        mock_azure_graph_service.update_message.assert_called_once_with(
            "test_token",
            "message1",
            {"isRead": True, "importance": "high"}
        )

    async def test_update_message_no_changes(self, mail_service):
        """Test updating message with no changes specified."""
        with pytest.raises(ValidationError):
            await mail_service.update_message(
                access_token="test_token",
                message_id="message1"
                # No properties to update
            )

    # =====================================================================
    # Search Functionality Tests
    # =====================================================================

    async def test_search_messages_success(self, mail_service, mock_azure_graph_service, mock_messages_response):
        """Test searching messages successfully."""
        mock_azure_graph_service.search_messages.return_value = mock_messages_response
        
        result = await mail_service.search_messages(
            access_token="test_token",
            query="voice message",
            folder_id="inbox",
            top=25
        )
        
        assert result == mock_messages_response
        mock_azure_graph_service.search_messages.assert_called_once_with(
            "test_token",
            "voice message",
            folder_id="inbox",
            top=25
        )

    async def test_search_messages_validation_error(self, mail_service):
        """Test searching with invalid query."""
        with pytest.raises(ValidationError):
            await mail_service.search_messages(
                access_token="test_token",
                query="",  # Empty query
                folder_id="inbox"
            )

    # =====================================================================
    # Voice Message Detection Tests
    # =====================================================================

    async def test_get_messages_with_voice_attachments_success(self, mail_service, mock_azure_graph_service):
        """Test getting messages with voice attachments."""
        mock_voice_messages = {
            "value": [
                {
                    "id": "message1",
                    "subject": "Voice message",
                    "hasAttachments": True,
                    "attachments": [
                        {
                            "id": "attachment1",
                            "name": "voicemail.wav",
                            "contentType": "audio/wav",
                            "size": 52428
                        }
                    ]
                }
            ]
        }
        mock_azure_graph_service.get_messages.return_value = mock_voice_messages
        
        result = await mail_service.get_messages_with_voice_attachments(
            access_token="test_token",
            folder_id="inbox",
            top=100
        )
        
        assert result == mock_voice_messages
        mock_azure_graph_service.get_messages.assert_called_once_with(
            "test_token",
            folder_id="inbox",
            top=100,
            skip=0,
            has_attachments=True,
            filter_query=None
        )

    async def test_is_voice_attachment_audio_wav(self, mail_service):
        """Test identifying WAV audio as voice attachment."""
        attachment = {
            "contentType": "audio/wav",
            "name": "voicemail.wav",
            "size": 52428
        }
        
        result = mail_service._is_voice_attachment(attachment)
        
        assert result is True

    async def test_is_voice_attachment_audio_mp3(self, mail_service):
        """Test identifying MP3 audio as voice attachment."""
        attachment = {
            "contentType": "audio/mpeg",
            "name": "recording.mp3",
            "size": 31847
        }
        
        result = mail_service._is_voice_attachment(attachment)
        
        assert result is True

    async def test_is_voice_attachment_non_audio(self, mail_service):
        """Test non-audio attachment is not voice attachment."""
        attachment = {
            "contentType": "application/pdf",
            "name": "document.pdf",
            "size": 104857
        }
        
        result = mail_service._is_voice_attachment(attachment)
        
        assert result is False

    async def test_is_voice_attachment_unsupported_audio(self, mail_service):
        """Test unsupported audio format."""
        attachment = {
            "contentType": "audio/flac",
            "name": "music.flac",
            "size": 52428000
        }
        
        result = mail_service._is_voice_attachment(attachment)
        
        assert result is False  # FLAC not in supported formats

    # =====================================================================
    # Voice Message Organization Tests
    # =====================================================================

    async def test_organize_voice_messages_success(self, mail_service, mock_azure_graph_service):
        """Test organizing voice messages into folder."""
        # Mock finding voice messages
        mock_voice_messages = {
            "value": [
                {
                    "id": "message1",
                    "subject": "Voice message 1",
                    "hasAttachments": True
                },
                {
                    "id": "message2", 
                    "subject": "Voice message 2",
                    "hasAttachments": True
                }
            ]
        }
        
        # Mock folder operations
        mock_folders = {
            "value": [
                {"id": "inbox", "displayName": "Inbox"}
            ]
        }
        mock_created_folder = {
            "id": "voice_folder",
            "displayName": "Voice Messages"
        }
        
        mock_azure_graph_service.get_messages.return_value = mock_voice_messages
        mock_azure_graph_service.get_mail_folders.return_value = mock_folders
        mock_azure_graph_service.create_mail_folder.return_value = mock_created_folder
        mock_azure_graph_service.move_message.return_value = {"status": "moved"}
        
        result = await mail_service.organize_voice_messages(
            access_token="test_token",
            target_folder_name="Voice Messages"
        )
        
        assert result["status"] == "completed"
        assert result["messages_moved"] == 2
        assert result["target_folder"] == "Voice Messages"
        assert result["created_folder"] is True

    async def test_organize_voice_messages_existing_folder(self, mail_service, mock_azure_graph_service):
        """Test organizing voice messages with existing target folder."""
        # Mock existing folder
        mock_folders = {
            "value": [
                {"id": "inbox", "displayName": "Inbox"},
                {"id": "voice_folder", "displayName": "Voice Messages"}
            ]
        }
        mock_voice_messages = {"value": []}
        
        mock_azure_graph_service.get_mail_folders.return_value = mock_folders
        mock_azure_graph_service.get_messages.return_value = mock_voice_messages
        
        result = await mail_service.organize_voice_messages(
            access_token="test_token", 
            target_folder_name="Voice Messages"
        )
        
        assert result["created_folder"] is False
        # Should not call create_mail_folder
        mock_azure_graph_service.create_mail_folder.assert_not_called()

    # =====================================================================
    # Utility Method Tests
    # =====================================================================

    async def test_validate_access_token_valid(self, mail_service):
        """Test validating valid access token format."""
        token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIwMDAwMDAwMy0wMDAwLTAwMDBhY2MwLWY0ZjQwNzAwMDAwMCJ9.signature"
        
        # Should not raise exception
        mail_service._validate_access_token(token)

    async def test_validate_access_token_invalid(self, mail_service):
        """Test validating invalid access token."""
        with pytest.raises(ValidationError):
            mail_service._validate_access_token("")
        
        with pytest.raises(ValidationError):
            mail_service._validate_access_token(None)

    async def test_extract_error_message_graph_error(self, mail_service):
        """Test extracting error message from Graph API error."""
        mock_error = Exception("Graph API Error: Invalid token")
        
        result = mail_service._extract_error_message(mock_error)
        
        assert "Invalid token" in result

    async def test_extract_error_message_generic_error(self, mail_service):
        """Test extracting error message from generic error."""
        mock_error = Exception("Generic error message")
        
        result = mail_service._extract_error_message(mock_error)
        
        assert result == "Generic error message"

    # =====================================================================
    # Error Handling Tests
    # =====================================================================

    async def test_service_unavailable_handling(self, mail_service, mock_azure_graph_service):
        """Test handling service unavailable errors."""
        mock_azure_graph_service.get_mail_folders.side_effect = Exception("Service temporarily unavailable")
        
        with pytest.raises(Exception) as exc_info:
            await mail_service.get_mail_folders("test_token")
        
        assert "Service temporarily unavailable" in str(exc_info.value)

    async def test_network_timeout_handling(self, mail_service, mock_azure_graph_service):
        """Test handling network timeout errors."""
        mock_azure_graph_service.get_messages.side_effect = Exception("Request timed out")
        
        with pytest.raises(Exception) as exc_info:
            await mail_service.get_messages("test_token", "inbox")
        
        assert "Request timed out" in str(exc_info.value)

    async def test_rate_limit_handling(self, mail_service, mock_azure_graph_service):
        """Test handling rate limit errors."""
        mock_azure_graph_service.search_messages.side_effect = Exception("Rate limit exceeded")
        
        with pytest.raises(Exception) as exc_info:
            await mail_service.search_messages("test_token", "test query")
        
        assert "Rate limit exceeded" in str(exc_info.value)

    # =====================================================================
    # Performance and Edge Case Tests
    # =====================================================================

    async def test_large_message_list_handling(self, mail_service, mock_azure_graph_service):
        """Test handling large message lists."""
        # Mock large response
        large_response = {
            "value": [{"id": f"message_{i}", "subject": f"Subject {i}"} for i in range(1000)],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=1000"
        }
        mock_azure_graph_service.get_messages.return_value = large_response
        
        result = await mail_service.get_messages("test_token", "inbox", top=1000)
        
        assert len(result["value"]) == 1000
        assert "@odata.nextLink" in result

    async def test_concurrent_operations_handling(self, mail_service, mock_azure_graph_service):
        """Test handling concurrent mail operations."""
        mock_azure_graph_service.get_message.return_value = {"id": "message1"}
        mock_azure_graph_service.update_message.return_value = {"id": "message1", "isRead": True}
        
        # Should handle concurrent operations without issues
        import asyncio
        
        tasks = [
            mail_service.get_message("test_token", f"message_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(result["id"] == "message1" for result in results)