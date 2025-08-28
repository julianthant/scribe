"""
Integration tests for mail endpoints.

Tests complete mail operations including:
- Mail folder operations (list, create, manage)
- Message retrieval with filtering and pagination
- Attachment handling and downloads
- Message operations (move, update, search)
- Voice attachment organization and management
- Performance and error handling scenarios
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime, timedelta
import json

import httpx
import respx

from tests.integration.utils import (
    IntegrationAPIClient, 
    ResponseAssertions, 
    DatabaseAssertions,
    TestWorkflows,
    time_operation
)


class TestMailEndpoints:
    """Integration tests for mail endpoints."""

    @pytest_asyncio.fixture
    async def api_client(self, authenticated_async_client):
        """Get API client wrapper for easier testing."""
        return IntegrationAPIClient(authenticated_async_client)
    
    @pytest_asyncio.fixture 
    async def db_assertions(self, integration_db_session):
        """Get database assertions helper."""
        return DatabaseAssertions(integration_db_session)
    
    @pytest_asyncio.fixture
    async def test_workflows(self, api_client, db_assertions):
        """Get test workflow helper."""
        return TestWorkflows(api_client, db_assertions)

    # =========================================================================
    # MAIL FOLDER TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_mail_folders_success(self, api_client, mock_graph_api, override_auth_dependency):
        """Test successfully listing mail folders."""
        async with time_operation("list_mail_folders"):
            response = await api_client.get_mail_folders()
        
        ResponseAssertions.assert_success_response(response)
        
        folders_data = response.json()
        assert isinstance(folders_data, list)
        assert len(folders_data) > 0
        
        # Verify folder structure
        for folder in folders_data:
            ResponseAssertions.assert_mail_folder_structure(folder)
            assert "inbox" in folder["id"] or "sent" in folder["id"] or "archive" in folder["id"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_mail_folders_authentication_required(self, authenticated_async_client):
        """Test that listing folders requires authentication."""
        # Create client without auth headers
        async with httpx.AsyncClient(app=authenticated_async_client.app, base_url="http://test") as client:
            api_client = IntegrationAPIClient(client)
            response = await api_client.get_mail_folders()
            
            ResponseAssertions.assert_authentication_error(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_mail_folder_success(self, api_client, override_auth_dependency):
        """Test creating a new mail folder."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Mock successful folder creation
            mock_folder = {
                "id": "new-folder-123",
                "displayName": "Test Folder",
                "parentFolderId": "inbox",
                "childFolderCount": 0,
                "unreadItemCount": 0,
                "totalItemCount": 0
            }
            
            mock_mail_service.return_value.create_mail_folder.return_value = mock_folder
            
            response = await api_client.create_mail_folder("Test Folder", parent_id="inbox")
            
            ResponseAssertions.assert_success_response(response)
            
            folder_data = response.json()
            assert folder_data["displayName"] == "Test Folder"
            assert folder_data["parentFolderId"] == "inbox"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_mail_folder_validation_error(self, api_client, override_auth_dependency):
        """Test folder creation with invalid parameters."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            from app.core.Exceptions import ValidationError
            mock_mail_service.return_value.create_mail_folder.side_effect = ValidationError(
                "Folder name cannot be empty"
            )
            
            response = await api_client.create_mail_folder("")
            
            ResponseAssertions.assert_validation_error(response)

    # =========================================================================
    # MESSAGE RETRIEVAL TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_messages_default_inbox(self, api_client, mock_graph_api, override_auth_dependency):
        """Test getting messages from default inbox."""
        async with time_operation("get_inbox_messages"):
            response = await api_client.get_messages()
        
        ResponseAssertions.assert_success_response(response)
        ResponseAssertions.assert_paginated_response(response)
        
        messages_data = response.json()
        assert isinstance(messages_data["value"], list)
        
        # Verify message structure
        for message in messages_data["value"]:
            ResponseAssertions.assert_message_structure(message)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_messages_with_attachments_filter(self, api_client, mock_graph_api, override_auth_dependency):
        """Test filtering messages by attachment presence."""
        response = await api_client.get_messages(has_attachments=True)
        
        ResponseAssertions.assert_success_response(response)
        
        messages_data = response.json()
        attachment_messages = [msg for msg in messages_data["value"] if msg["hasAttachments"]]
        
        # All returned messages should have attachments
        assert len(attachment_messages) == len(messages_data["value"])

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_messages_with_pagination(self, api_client, mock_graph_api, override_auth_dependency):
        """Test message pagination parameters."""
        # First page
        response_page1 = await api_client.get_messages(top=2, skip=0)
        ResponseAssertions.assert_success_response(response_page1)
        
        page1_data = response_page1.json()
        assert isinstance(page1_data["value"], list)
        
        # Second page
        response_page2 = await api_client.get_messages(top=2, skip=2)
        ResponseAssertions.assert_success_response(response_page2)
        
        page2_data = response_page2.json()
        assert isinstance(page2_data["value"], list)
        
        # Pages should be different (if enough messages exist)
        if len(page1_data["value"]) > 0 and len(page2_data["value"]) > 0:
            page1_ids = {msg["id"] for msg in page1_data["value"]}
            page2_ids = {msg["id"] for msg in page2_data["value"]}
            # Should have some different messages (assuming > 2 total messages)
            assert len(page1_ids.intersection(page2_ids)) < len(page1_ids)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_messages_from_specific_folder(self, api_client, mock_graph_api, override_auth_dependency):
        """Test getting messages from a specific folder."""
        response = await api_client.get_messages(folder_id="sentitems")
        
        ResponseAssertions.assert_success_response(response)
        
        messages_data = response.json()
        assert isinstance(messages_data["value"], list)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_single_message_success(self, api_client, mock_graph_api, override_auth_dependency):
        """Test getting a specific message by ID."""
        message_id = "msg-001"
        response = await api_client.get_message(message_id)
        
        ResponseAssertions.assert_success_response(response)
        
        message_data = response.json()
        ResponseAssertions.assert_message_structure(message_data)
        assert message_data["id"] == message_id

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_single_message_not_found(self, api_client, mock_graph_api, override_auth_dependency):
        """Test getting a non-existent message."""
        response = await api_client.get_message("non-existent-message")
        
        ResponseAssertions.assert_not_found_error(response)

    # =========================================================================
    # ATTACHMENT TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_message_attachments_success(self, api_client, mock_graph_api, override_auth_dependency):
        """Test getting attachments for a message."""
        message_id = "msg-002"  # Message with attachments
        response = await api_client.get_message_attachments(message_id)
        
        ResponseAssertions.assert_success_response(response)
        
        attachments_data = response.json()
        assert isinstance(attachments_data, list)
        assert len(attachments_data) > 0
        
        # Verify attachment structure
        for attachment in attachments_data:
            ResponseAssertions.assert_voice_attachment_structure(attachment)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_download_attachment_success(self, api_client, mock_graph_api, override_auth_dependency):
        """Test downloading an attachment."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Mock attachment download
            mock_mail_service.return_value.mail_repository.download_attachment.return_value = b"test audio data"
            
            message_id = "msg-002"
            attachment_id = "att-voice-001"
            
            response = await api_client.download_attachment(message_id, attachment_id)
            
            # Download endpoint returns binary data, not JSON
            assert response.status_code == 200
            assert len(response.content) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_download_attachment_not_found(self, api_client, override_auth_dependency):
        """Test downloading non-existent attachment."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            from app.core.Exceptions import AuthenticationError
            mock_mail_service.return_value.mail_repository.get_attachments.side_effect = AuthenticationError(
                "Attachment not found"
            )
            
            response = await api_client.download_attachment("msg-999", "att-999")
            
            ResponseAssertions.assert_authentication_error(response)

    # =========================================================================
    # MESSAGE OPERATIONS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_move_message_success(self, api_client, override_auth_dependency):
        """Test moving a message to a different folder."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            mock_mail_service.return_value.move_message_to_folder.return_value = True
            
            message_id = "msg-001"
            destination_id = "archive"
            
            response = await api_client.move_message(message_id, destination_id)
            
            ResponseAssertions.assert_success_response(response)
            
            result_data = response.json()
            assert result_data["success"] is True
            assert destination_id in result_data["message"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_move_message_invalid_destination(self, api_client, override_auth_dependency):
        """Test moving message to invalid destination."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            from app.core.Exceptions import ValidationError
            mock_mail_service.return_value.move_message_to_folder.side_effect = ValidationError(
                "Invalid destination folder"
            )
            
            response = await api_client.move_message("msg-001", "invalid-folder")
            
            ResponseAssertions.assert_validation_error(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_message_read_status(self, api_client, override_auth_dependency):
        """Test updating message read status."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            mock_mail_service.return_value.mark_message_as_read.return_value = True
            
            message_id = "msg-001"
            response = await api_client.update_message(message_id, is_read=True)
            
            ResponseAssertions.assert_success_response(response)
            
            result_data = response.json()
            assert result_data["success"] is True
            assert "marked as read" in result_data["message"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_message_importance(self, api_client, override_auth_dependency):
        """Test updating message importance."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            mock_mail_service.return_value.mark_message_as_read.return_value = True
            
            message_id = "msg-001"
            response = await api_client.update_message(message_id, importance="high")
            
            ResponseAssertions.assert_success_response(response)
            
            result_data = response.json()
            assert result_data["success"] is True
            assert "importance set to high" in result_data["message"]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_message_no_changes(self, api_client, override_auth_dependency):
        """Test updating message with no changes specified."""
        response = await api_client.update_message("msg-001")
        
        ResponseAssertions.assert_success_response(response)
        
        result_data = response.json()
        assert result_data["success"] is True
        assert "No updates specified" in result_data["message"]

    # =========================================================================
    # MESSAGE SEARCH TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_messages_success(self, api_client, override_auth_dependency):
        """Test searching messages with query."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Mock search results
            mock_search_results = {
                "value": [
                    {
                        "id": "search-result-1",
                        "subject": "Voicemail from client",
                        "from": {"emailAddress": {"address": "client@example.com"}},
                        "receivedDateTime": "2024-01-15T10:00:00Z",
                        "isRead": False,
                        "hasAttachments": True
                    }
                ],
                "@odata.nextLink": None
            }
            
            mock_mail_service.return_value.search_messages.return_value = mock_search_results
            
            response = await api_client.search_messages("voicemail", top=10)
            
            ResponseAssertions.assert_success_response(response)
            ResponseAssertions.assert_paginated_response(response)
            
            search_data = response.json()
            assert len(search_data["value"]) > 0
            
            # Verify search results contain relevant messages
            for message in search_data["value"]:
                ResponseAssertions.assert_message_structure(message)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_messages_in_specific_folder(self, api_client, override_auth_dependency):
        """Test searching within a specific folder."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            mock_mail_service.return_value.search_messages.return_value = {"value": []}
            
            response = await api_client.search_messages("test query", folder_id="inbox")
            
            ResponseAssertions.assert_success_response(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_messages_empty_query(self, api_client, override_auth_dependency):
        """Test searching with empty query."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            from app.core.Exceptions import ValidationError
            mock_mail_service.return_value.search_messages.side_effect = ValidationError(
                "Search query cannot be empty"
            )
            
            response = await api_client.search_messages("")
            
            ResponseAssertions.assert_validation_error(response)

    # =========================================================================
    # VOICE ATTACHMENT TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_voice_messages_success(self, api_client, override_auth_dependency):
        """Test getting messages with voice attachments."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Mock voice messages response
            mock_voice_messages = {
                "value": [
                    {
                        "id": "voice-msg-001",
                        "subject": "Voicemail",
                        "from": {"emailAddress": {"address": "caller@example.com"}},
                        "receivedDateTime": "2024-01-15T10:00:00Z",
                        "hasAttachments": True,
                        "isRead": False
                    }
                ]
            }
            
            mock_attachments = [
                {
                    "attachment_id": "voice-att-001",
                    "file_name": "voicemail.wav",
                    "content_type": "audio/wav",
                    "size_bytes": 2048000
                }
            ]
            
            mock_mail_service.return_value.get_messages_with_voice_attachments.return_value = (
                mock_voice_messages, mock_attachments
            )
            
            response = await api_client.get_voice_messages()
            
            ResponseAssertions.assert_success_response(response)
            
            voice_data = response.json()
            assert "value" in voice_data
            assert len(voice_data["value"]) > 0
            
            # All messages should have attachments
            for message in voice_data["value"]:
                assert message["hasAttachments"] is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_voice_attachments_success(self, api_client, override_auth_dependency):
        """Test getting all voice attachments."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
            # Mock voice messages and attachments
            mock_voice_messages = [
                Mock(id="voice-msg-001"),
                Mock(id="voice-msg-002")
            ]
            
            mock_voice_attachments = [
                {
                    "attachment_id": "voice-att-001",
                    "message_id": "voice-msg-001",
                    "file_name": "voicemail1.wav",
                    "content_type": "audio/wav",
                    "size_bytes": 2048000
                },
                {
                    "attachment_id": "voice-att-002", 
                    "message_id": "voice-msg-002",
                    "file_name": "voicemail2.mp3",
                    "content_type": "audio/mpeg",
                    "size_bytes": 3072000
                }
            ]
            
            mock_voice_service.return_value.find_all_voice_messages.return_value = mock_voice_messages
            mock_voice_service.return_value.extract_voice_attachments_from_message.return_value = mock_voice_attachments
            
            response = await api_client.get_voice_attachments(limit=100)
            
            ResponseAssertions.assert_success_response(response)
            
            attachments_data = response.json()
            assert isinstance(attachments_data, list)
            
            # Verify voice attachment structure
            for attachment in attachments_data:
                assert "attachment_id" in attachment
                assert "content_type" in attachment
                assert attachment["content_type"].startswith("audio/")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_organize_voice_messages_success(self, api_client, override_auth_dependency):
        """Test organizing voice messages into a folder."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
            # Mock organization response
            mock_organize_response = {
                "success": True,
                "target_folder": "Voice Messages",
                "messages_moved": 5,
                "messages_processed": 10,
                "folder_created": True,
                "processing_time_ms": 1500
            }
            
            mock_voice_service.return_value.organize_voice_messages.return_value = mock_organize_response
            
            response = await api_client.organize_voice_messages("Voice Messages")
            
            ResponseAssertions.assert_success_response(response)
            
            organize_data = response.json()
            assert organize_data["success"] is True
            assert organize_data["messages_moved"] == 5
            assert organize_data["folder_created"] is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_voice_attachment_metadata(self, api_client, override_auth_dependency):
        """Test getting voice attachment metadata.""" 
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
            # Mock metadata response
            mock_metadata = {
                "attachment_id": "voice-att-001",
                "message_id": "voice-msg-001",
                "file_name": "important-voicemail.wav",
                "content_type": "audio/wav",
                "size_bytes": 2048000,
                "duration_seconds": 45,
                "quality": "high",
                "encoding": "PCM"
            }
            
            mock_voice_service.return_value.get_voice_attachment_metadata.return_value = mock_metadata
            
            message_id = "voice-msg-001"
            attachment_id = "voice-att-001"
            
            response = await api_client.client.get(
                f"/api/v1/mail/voice-attachments/{message_id}/{attachment_id}/metadata"
            )
            
            ResponseAssertions.assert_success_response(response)
            
            metadata = response.json()
            assert metadata["attachment_id"] == "voice-att-001"
            assert metadata["content_type"] == "audio/wav"
            assert metadata["duration_seconds"] == 45

    # =========================================================================
    # MAIL STATISTICS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_mail_statistics_success(self, api_client, override_auth_dependency):
        """Test getting mail statistics."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Mock statistics response
            mock_statistics = {
                "folder_id": "inbox",
                "total_messages": 150,
                "unread_messages": 12,
                "messages_with_attachments": 45,
                "voice_messages": 8,
                "total_size_bytes": 52428800,
                "average_message_size": 349525,
                "oldest_message_date": "2024-01-01T00:00:00Z",
                "newest_message_date": "2024-01-15T15:30:00Z"
            }
            
            mock_mail_service.return_value.get_folder_statistics.return_value = mock_statistics
            
            response = await api_client.client.get("/api/v1/mail/statistics")
            
            ResponseAssertions.assert_success_response(response)
            
            stats_data = response.json()
            assert stats_data["total_messages"] == 150
            assert stats_data["unread_messages"] == 12
            assert stats_data["voice_messages"] == 8

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_voice_statistics_success(self, api_client, override_auth_dependency):
        """Test getting voice attachment statistics."""
        with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
            # Mock voice statistics
            mock_voice_stats = {
                "total_voice_messages": 25,
                "total_voice_attachments": 28,
                "total_size_bytes": 157286400,
                "average_size_bytes": 5616657,
                "content_type_breakdown": {
                    "audio/wav": 15,
                    "audio/mpeg": 10,
                    "audio/mp3": 3
                },
                "messages_by_folder": {
                    "inbox": 20,
                    "voice-messages": 5
                },
                "size_distribution": {
                    "small": 8,  # < 1MB
                    "medium": 12,  # 1-5MB
                    "large": 8   # > 5MB
                }
            }
            
            mock_voice_service.return_value.get_voice_statistics.return_value = mock_voice_stats
            
            response = await api_client.client.get("/api/v1/mail/voice-statistics")
            
            ResponseAssertions.assert_success_response(response)
            
            voice_stats = response.json()
            assert voice_stats["total_voice_messages"] == 25
            assert voice_stats["total_voice_attachments"] == 28
            assert "content_type_breakdown" in voice_stats
            assert "audio/wav" in voice_stats["content_type_breakdown"]

    # =========================================================================
    # COMPLETE WORKFLOW TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_message_workflow(self, test_workflows, override_auth_dependency):
        """Test complete message workflow: get -> attachments -> download -> update."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Setup comprehensive mocks
            mock_message = {
                "id": "workflow-msg-001",
                "subject": "Workflow Test Message",
                "hasAttachments": True,
                "isRead": False
            }
            
            mock_attachments = [
                {
                    "id": "workflow-att-001",
                    "name": "workflow-audio.wav",
                    "contentType": "audio/wav",
                    "size": 1024000
                }
            ]
            
            mock_mail_service.return_value.mail_repository.get_message_by_id.return_value = mock_message
            mock_mail_service.return_value.mail_repository.get_attachments.return_value = mock_attachments
            mock_mail_service.return_value.mail_repository.download_attachment.return_value = b"audio data"
            mock_mail_service.return_value.mark_message_as_read.return_value = True
            
            # Execute complete workflow
            responses = await test_workflows.complete_message_workflow("workflow-msg-001")
            
            # Verify all steps succeeded
            ResponseAssertions.assert_success_response(responses["message"])
            ResponseAssertions.assert_success_response(responses["attachments"])
            if "download" in responses:
                assert responses["download"].status_code == 200
            ResponseAssertions.assert_success_response(responses["update"])

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_voice_organization_workflow(self, test_workflows, override_auth_dependency):
        """Test complete voice organization workflow."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
                # Mock voice messages discovery
                mock_mail_service.return_value.get_messages_with_voice_attachments.return_value = (
                    {"value": [{"id": "voice-msg-1", "hasAttachments": True}]},
                    [{"attachment_id": "voice-att-1", "file_name": "test.wav"}]
                )
                
                # Mock organization
                mock_voice_service.return_value.organize_voice_messages.return_value = {
                    "success": True,
                    "messages_moved": 1,
                    "folder_created": True
                }
                
                # Execute workflow
                voice_response, organize_response = await test_workflows.create_and_organize_voice_messages()
                
                # Verify workflow success
                ResponseAssertions.assert_success_response(voice_response)
                ResponseAssertions.assert_success_response(organize_response)

    # =========================================================================
    # PERFORMANCE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_message_requests(self, api_client, mock_graph_api, override_auth_dependency):
        """Test concurrent message requests for performance."""
        from tests.integration.utils import run_concurrent_requests
        
        # Create multiple concurrent requests
        requests = [
            lambda: api_client.get_messages(top=10),
            lambda: api_client.get_voice_messages(top=20),
            lambda: api_client.get_mail_folders(),
            lambda: api_client.get_messages(has_attachments=True),
        ]
        
        # Run requests concurrently
        responses = await run_concurrent_requests(requests, max_concurrent=3)
        
        # All requests should succeed
        for response in responses:
            if isinstance(response, Exception):
                pytest.fail(f"Concurrent request failed: {response}")
            ResponseAssertions.assert_success_response(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_large_message_list_pagination(self, api_client, override_auth_dependency):
        """Test handling large message lists with pagination."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            # Mock large message set
            large_message_set = {
                "value": [
                    {
                        "id": f"large-msg-{i}",
                        "subject": f"Message {i}",
                        "hasAttachments": i % 3 == 0,
                        "isRead": i % 2 == 0,
                        "from": {"emailAddress": {"address": f"sender{i}@example.com"}},
                        "receivedDateTime": "2024-01-15T10:00:00Z"
                    }
                    for i in range(50)  # Simulate 50 messages
                ]
            }
            
            mock_mail_service.return_value.get_inbox_messages.return_value = large_message_set
            
            # Test different page sizes
            for page_size in [10, 25, 50]:
                response = await api_client.get_messages(top=page_size)
                ResponseAssertions.assert_success_response(response)
                
                data = response.json()
                assert len(data["value"]) <= page_size

    # =========================================================================
    # ERROR HANDLING TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mail_service_unavailable(self, api_client, override_auth_dependency):
        """Test handling when mail service is unavailable."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            mock_mail_service.side_effect = ConnectionError("Mail service unavailable")
            
            response = await api_client.get_mail_folders()
            
            # Should return 500 error for service unavailability
            assert response.status_code == 500

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_authentication_token_expired_during_request(self, api_client, override_auth_dependency):
        """Test handling expired authentication token during request."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            from app.core.Exceptions import AuthenticationError
            mock_mail_service.return_value.list_mail_folders.side_effect = AuthenticationError(
                "Token has expired"
            )
            
            response = await api_client.get_mail_folders()
            
            ResponseAssertions.assert_authentication_error(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limiting_handling(self, api_client, override_auth_dependency):
        """Test handling of rate limiting responses."""
        with patch('app.services.MailService.MailService') as mock_mail_service:
            from app.core.Exceptions import AuthenticationError
            mock_mail_service.return_value.list_mail_folders.side_effect = AuthenticationError(
                "Rate limit exceeded"
            )
            
            response = await api_client.get_mail_folders()
            
            ResponseAssertions.assert_authentication_error(response)