"""
Integration tests for shared mailbox endpoints.

Tests complete shared mailbox operations including:
- Shared mailbox discovery and access control
- Folder operations within shared mailboxes  
- Message operations and filtering
- Cross-mailbox search functionality
- Voice message organization in shared contexts
- Analytics and statistics for shared mailboxes
- Permission and authorization handling
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime, timedelta

import httpx

from tests.integration.utils import (
    IntegrationAPIClient, 
    ResponseAssertions, 
    DatabaseAssertions,
    time_operation
)


class TestSharedMailboxEndpoints:
    """Integration tests for shared mailbox endpoints."""

    @pytest_asyncio.fixture
    async def api_client(self, authenticated_async_client):
        """Get API client wrapper for easier testing."""
        return IntegrationAPIClient(authenticated_async_client)
    
    @pytest_asyncio.fixture 
    async def db_assertions(self, integration_db_session):
        """Get database assertions helper."""
        return DatabaseAssertions(integration_db_session)

    # =========================================================================
    # SHARED MAILBOX DISCOVERY TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_accessible_shared_mailboxes_success(self, api_client, override_auth_dependency):
        """Test listing accessible shared mailboxes."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock shared mailboxes response
            mock_response = {
                "value": [
                    {
                        "id": "shared-mb-001",
                        "emailAddress": "support@example.com",
                        "displayName": "Customer Support",
                        "accessLevel": "full",
                        "permissions": ["read", "write", "send"],
                        "messageCount": 150,
                        "unreadCount": 12
                    },
                    {
                        "id": "shared-mb-002", 
                        "emailAddress": "sales@example.com",
                        "displayName": "Sales Team",
                        "accessLevel": "read",
                        "permissions": ["read"],
                        "messageCount": 300,
                        "unreadCount": 45
                    }
                ],
                "totalCount": 2
            }
            
            mock_service.return_value.get_accessible_shared_mailboxes.return_value = mock_response
            
            async with time_operation("list_shared_mailboxes"):
                response = await api_client.get_shared_mailboxes()
            
            ResponseAssertions.assert_success_response(response)
            
            mailboxes_data = response.json()
            assert "value" in mailboxes_data
            assert len(mailboxes_data["value"]) == 2
            
            # Verify mailbox structure
            for mailbox in mailboxes_data["value"]:
                assert "emailAddress" in mailbox
                assert "displayName" in mailbox
                assert "accessLevel" in mailbox
                assert "permissions" in mailbox

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_shared_mailboxes_no_access(self, api_client, override_auth_dependency):
        """Test listing when user has no shared mailbox access."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            mock_response = {"value": [], "totalCount": 0}
            mock_service.return_value.get_accessible_shared_mailboxes.return_value = mock_response
            
            response = await api_client.get_shared_mailboxes()
            
            ResponseAssertions.assert_success_response(response)
            
            mailboxes_data = response.json()
            assert mailboxes_data["value"] == []
            assert mailboxes_data["totalCount"] == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailbox_details_success(self, api_client, override_auth_dependency):
        """Test getting details for a specific shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock detailed mailbox response
            mock_details = {
                "id": "shared-mb-001",
                "emailAddress": "support@example.com",
                "displayName": "Customer Support Mailbox",
                "description": "Primary customer support email",
                "accessLevel": "full",
                "permissions": ["read", "write", "send", "delete"],
                "messageCount": 150,
                "unreadCount": 12,
                "sizeBytes": 52428800,
                "lastActivityDate": "2024-01-15T10:30:00Z",
                "folders": [
                    {"id": "inbox", "displayName": "Inbox", "messageCount": 120},
                    {"id": "sent", "displayName": "Sent Items", "messageCount": 30}
                ]
            }
            
            mock_service.return_value.get_shared_mailbox_details.return_value = mock_details
            
            email_address = "support@example.com"
            response = await api_client.get_shared_mailbox_details(email_address)
            
            ResponseAssertions.assert_success_response(response)
            
            details_data = response.json()
            assert details_data["emailAddress"] == email_address
            assert details_data["accessLevel"] == "full"
            assert "permissions" in details_data
            assert len(details_data["folders"]) == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailbox_details_access_denied(self, api_client, override_auth_dependency):
        """Test getting details when access is denied."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            from app.core.Exceptions import AuthorizationError
            mock_service.return_value.get_shared_mailbox_details.side_effect = AuthorizationError(
                "Access denied to shared mailbox"
            )
            
            response = await api_client.get_shared_mailbox_details("restricted@example.com")
            
            ResponseAssertions.assert_authorization_error(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailbox_details_not_found(self, api_client, override_auth_dependency):
        """Test getting details for non-existent mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            from app.core.Exceptions import ValidationError
            mock_service.return_value.get_shared_mailbox_details.side_effect = ValidationError(
                "Shared mailbox not found"
            )
            
            response = await api_client.get_shared_mailbox_details("nonexistent@example.com")
            
            ResponseAssertions.assert_not_found_error(response)

    # =========================================================================
    # SHARED MAILBOX FOLDER TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_shared_mailbox_folders_success(self, api_client, override_auth_dependency):
        """Test listing folders from a shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock folder list
            mock_folders = [
                {
                    "id": "shared-inbox",
                    "displayName": "Inbox",
                    "parentFolderId": "root",
                    "unreadItemCount": 8,
                    "totalItemCount": 45,
                    "childFolderCount": 2
                },
                {
                    "id": "shared-sent",
                    "displayName": "Sent Items", 
                    "parentFolderId": "root",
                    "unreadItemCount": 0,
                    "totalItemCount": 15,
                    "childFolderCount": 0
                },
                {
                    "id": "shared-voice",
                    "displayName": "Voice Messages",
                    "parentFolderId": "shared-inbox",
                    "unreadItemCount": 3,
                    "totalItemCount": 12,
                    "childFolderCount": 0
                }
            ]
            
            mock_service.return_value.get_shared_mailbox_folders.return_value = mock_folders
            
            email_address = "support@example.com"
            response = await api_client.get_shared_mailbox_folders(email_address)
            
            ResponseAssertions.assert_success_response(response)
            
            folders_data = response.json()
            assert isinstance(folders_data, list)
            assert len(folders_data) == 3
            
            # Verify folder structure
            for folder in folders_data:
                ResponseAssertions.assert_mail_folder_structure(folder)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_shared_mailbox_folder_success(self, api_client, override_auth_dependency):
        """Test creating a folder in a shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock created folder
            mock_created_folder = {
                "id": "new-shared-folder-123",
                "displayName": "New Shared Folder",
                "parentFolderId": "shared-inbox",
                "unreadItemCount": 0,
                "totalItemCount": 0,
                "childFolderCount": 0
            }
            
            mock_service.return_value.create_shared_mailbox_folder.return_value = mock_created_folder
            
            email_address = "support@example.com"
            folder_name = "New Shared Folder"
            parent_id = "shared-inbox"
            
            response = await api_client.client.post(
                f"/api/v1/shared-mailboxes/{email_address}/folders",
                params={"folder_name": folder_name, "parent_id": parent_id}
            )
            
            ResponseAssertions.assert_success_response(response)
            
            folder_data = response.json()
            assert folder_data["displayName"] == folder_name
            assert folder_data["parentFolderId"] == parent_id

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_shared_mailbox_folder_insufficient_permissions(self, api_client, override_auth_dependency):
        """Test creating folder with insufficient permissions."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            from app.core.Exceptions import AuthorizationError
            mock_service.return_value.create_shared_mailbox_folder.side_effect = AuthorizationError(
                "Insufficient permissions to create folder"
            )
            
            response = await api_client.client.post(
                "/api/v1/shared-mailboxes/readonly@example.com/folders",
                params={"folder_name": "Test Folder"}
            )
            
            ResponseAssertions.assert_authorization_error(response)

    # =========================================================================
    # SHARED MAILBOX MESSAGE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailbox_messages_success(self, api_client, override_auth_dependency):
        """Test getting messages from a shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock messages response
            mock_messages = {
                "value": [
                    {
                        "id": "shared-msg-001",
                        "subject": "Customer Support Inquiry",
                        "from": {
                            "emailAddress": {
                                "address": "customer@client.com",
                                "name": "Customer Name"
                            }
                        },
                        "receivedDateTime": "2024-01-15T09:30:00Z",
                        "isRead": False,
                        "hasAttachments": True,
                        "importance": "high"
                    },
                    {
                        "id": "shared-msg-002",
                        "subject": "Follow-up Question",
                        "from": {
                            "emailAddress": {
                                "address": "partner@business.com",
                                "name": "Business Partner"
                            }
                        },
                        "receivedDateTime": "2024-01-15T11:45:00Z",
                        "isRead": True,
                        "hasAttachments": False,
                        "importance": "normal"
                    }
                ],
                "@odata.nextLink": None
            }
            
            mock_service.return_value.get_shared_mailbox_messages.return_value = mock_messages
            
            email_address = "support@example.com"
            response = await api_client.get_shared_mailbox_messages(
                email_address, 
                folder_id="inbox",
                top=25,
                skip=0
            )
            
            ResponseAssertions.assert_success_response(response)
            ResponseAssertions.assert_paginated_response(response)
            
            messages_data = response.json()
            assert len(messages_data["value"]) == 2
            
            # Verify message structure
            for message in messages_data["value"]:
                ResponseAssertions.assert_message_structure(message)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailbox_messages_with_attachments(self, api_client, override_auth_dependency):
        """Test filtering shared mailbox messages by attachments."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock messages with attachments only
            mock_messages = {
                "value": [
                    {
                        "id": "shared-att-msg-001",
                        "subject": "Document Review",
                        "hasAttachments": True,
                        "from": {"emailAddress": {"address": "reviewer@company.com"}},
                        "receivedDateTime": "2024-01-15T10:00:00Z",
                        "isRead": False
                    }
                ]
            }
            
            mock_service.return_value.get_shared_mailbox_messages.return_value = mock_messages
            
            response = await api_client.get_shared_mailbox_messages(
                "support@example.com",
                has_attachments=True
            )
            
            ResponseAssertions.assert_success_response(response)
            
            messages_data = response.json()
            # All messages should have attachments
            for message in messages_data["value"]:
                assert message["hasAttachments"] is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_send_shared_mailbox_message_success(self, api_client, override_auth_dependency):
        """Test sending a message from a shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock send result
            mock_send_result = {
                "success": True,
                "messageId": "sent-shared-msg-123",
                "sentDateTime": "2024-01-15T12:00:00Z",
                "deliveryStatus": "delivered"
            }
            
            mock_service.return_value.send_shared_mailbox_message.return_value = mock_send_result
            
            # Mock send request
            send_request = {
                "to": [{"emailAddress": {"address": "recipient@example.com", "name": "Recipient"}}],
                "subject": "Response from Support Team",
                "body": {"content": "Thank you for your inquiry...", "contentType": "text"},
                "importance": "normal"
            }
            
            email_address = "support@example.com"
            response = await api_client.client.post(
                f"/api/v1/shared-mailboxes/{email_address}/send",
                json=send_request
            )
            
            ResponseAssertions.assert_success_response(response)
            
            send_data = response.json()
            assert send_data["success"] is True
            assert "messageId" in send_data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_send_shared_mailbox_message_no_send_permission(self, api_client, override_auth_dependency):
        """Test sending message without send permission."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            from app.core.Exceptions import AuthorizationError
            mock_service.return_value.send_shared_mailbox_message.side_effect = AuthorizationError(
                "No send permission for shared mailbox"
            )
            
            send_request = {
                "to": [{"emailAddress": {"address": "test@example.com"}}],
                "subject": "Test Message",
                "body": {"content": "Test content"}
            }
            
            response = await api_client.client.post(
                "/api/v1/shared-mailboxes/readonly@example.com/send",
                json=send_request
            )
            
            ResponseAssertions.assert_authorization_error(response)

    # =========================================================================
    # SHARED MAILBOX ORGANIZATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_organize_shared_mailbox_messages_success(self, api_client, override_auth_dependency):
        """Test organizing messages in a shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock organization response
            mock_organize_result = {
                "success": True,
                "targetFolder": "Organized Items",
                "messagesProcessed": 25,
                "messagesOrganized": 18,
                "foldersCreated": 1,
                "processingTimeMs": 2500,
                "organizationCriteria": "voice_attachments"
            }
            
            mock_service.return_value.organize_shared_mailbox_messages.return_value = mock_organize_result
            
            organize_request = {
                "targetFolderName": "Organized Items",
                "createFolder": True,
                "messageType": "voice",
                "includeSubfolders": False,
                "preserveReadStatus": True
            }
            
            email_address = "support@example.com"
            response = await api_client.client.post(
                f"/api/v1/shared-mailboxes/{email_address}/organize",
                json=organize_request
            )
            
            ResponseAssertions.assert_success_response(response)
            
            organize_data = response.json()
            assert organize_data["success"] is True
            assert organize_data["messagesOrganized"] == 18
            assert organize_data["foldersCreated"] == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_organize_voice_messages_in_shared_mailbox(self, api_client, override_auth_dependency):
        """Test organizing voice messages specifically."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            mock_voice_organize_result = {
                "success": True,
                "targetFolder": "Voice Messages", 
                "messagesProcessed": 50,
                "messagesOrganized": 12,
                "voiceAttachmentsFound": 15,
                "foldersCreated": 1,
                "processingTimeMs": 3200
            }
            
            mock_service.return_value.organize_shared_mailbox_messages.return_value = mock_voice_organize_result
            
            email_address = "support@example.com"
            target_folder = "Voice Messages"
            
            response = await api_client.client.post(
                f"/api/v1/shared-mailboxes/{email_address}/organize-voice",
                params={"target_folder": target_folder, "create_folder": True}
            )
            
            ResponseAssertions.assert_success_response(response)
            
            voice_organize_data = response.json()
            assert voice_organize_data["success"] is True
            assert voice_organize_data["voiceAttachmentsFound"] == 15

    # =========================================================================
    # CROSS-MAILBOX SEARCH TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_shared_mailboxes_success(self, api_client, override_auth_dependency):
        """Test searching across multiple shared mailboxes."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock cross-mailbox search results
            mock_search_results = {
                "query": "urgent customer",
                "totalResults": 15,
                "searchedMailboxes": 3,
                "searchTimeMs": 1200,
                "results": [
                    {
                        "mailbox": "support@example.com",
                        "messages": [
                            {
                                "id": "search-msg-001",
                                "subject": "Urgent Customer Issue",
                                "from": {"emailAddress": {"address": "customer@urgent.com"}},
                                "receivedDateTime": "2024-01-15T08:30:00Z",
                                "relevanceScore": 0.95
                            }
                        ],
                        "matchCount": 8
                    },
                    {
                        "mailbox": "sales@example.com", 
                        "messages": [
                            {
                                "id": "search-msg-002",
                                "subject": "Customer Payment Urgent",
                                "from": {"emailAddress": {"address": "billing@client.com"}},
                                "receivedDateTime": "2024-01-15T09:15:00Z",
                                "relevanceScore": 0.87
                            }
                        ],
                        "matchCount": 7
                    }
                ]
            }
            
            mock_service.return_value.search_shared_mailboxes.return_value = mock_search_results
            
            search_request = {
                "query": "urgent customer",
                "mailboxes": ["support@example.com", "sales@example.com"],
                "dateRange": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-01-15T23:59:59Z"
                },
                "includeAttachments": True,
                "maxResults": 50
            }
            
            response = await api_client.client.post(
                "/api/v1/shared-mailboxes/search",
                json=search_request
            )
            
            ResponseAssertions.assert_success_response(response)
            
            search_data = response.json()
            assert search_data["totalResults"] == 15
            assert search_data["searchedMailboxes"] == 3
            assert len(search_data["results"]) == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_shared_mailboxes_no_results(self, api_client, override_auth_dependency):
        """Test searching with no matching results."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            mock_empty_results = {
                "query": "nonexistent term",
                "totalResults": 0,
                "searchedMailboxes": 2,
                "searchTimeMs": 150,
                "results": []
            }
            
            mock_service.return_value.search_shared_mailboxes.return_value = mock_empty_results
            
            search_request = {
                "query": "nonexistent term",
                "mailboxes": ["support@example.com", "sales@example.com"]
            }
            
            response = await api_client.client.post(
                "/api/v1/shared-mailboxes/search",
                json=search_request
            )
            
            ResponseAssertions.assert_success_response(response)
            
            search_data = response.json()
            assert search_data["totalResults"] == 0
            assert len(search_data["results"]) == 0

    # =========================================================================
    # VOICE MESSAGE CROSS-MAILBOX TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_voice_messages_across_mailboxes(self, api_client, override_auth_dependency):
        """Test getting voice messages from multiple shared mailboxes."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock voice messages from multiple mailboxes
            mock_messages_mb1 = {
                "value": [
                    {
                        "id": "voice-shared-001",
                        "subject": "Voicemail from Customer",
                        "hasAttachments": True,
                        "from": {"emailAddress": {"address": "customer@voice.com"}}
                    }
                ]
            }
            
            mock_messages_mb2 = {
                "value": [
                    {
                        "id": "voice-shared-002",
                        "subject": "Sales Call Recording", 
                        "hasAttachments": True,
                        "from": {"emailAddress": {"address": "lead@prospect.com"}}
                    }
                ]
            }
            
            # Mock different responses for different mailboxes
            mock_service.return_value.get_shared_mailbox_messages.side_effect = [
                mock_messages_mb1, mock_messages_mb2
            ]
            
            mailbox_addresses = ["support@example.com", "sales@example.com"]
            
            response = await api_client.client.get(
                "/api/v1/shared-mailboxes/voice-messages/cross-mailbox",
                params={"mailbox_addresses": mailbox_addresses, "top": 50}
            )
            
            ResponseAssertions.assert_success_response(response)
            
            voice_data = response.json()
            assert voice_data["totalVoiceMessages"] >= 2
            assert voice_data["searchedMailboxes"] == 2
            assert voice_data["successfulMailboxes"] >= 2

    # =========================================================================
    # SHARED MAILBOX STATISTICS TESTS  
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailbox_statistics_success(self, api_client, override_auth_dependency):
        """Test getting comprehensive statistics for a shared mailbox."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock detailed statistics
            mock_statistics = {
                "mailbox": "support@example.com",
                "totalMessages": 1250,
                "unreadMessages": 45,
                "messagesWithAttachments": 320,
                "voiceMessages": 89,
                "totalSizeBytes": 524288000,
                "averageMessageSize": 419430,
                "messagesPerDay": {
                    "last7Days": 35,
                    "last30Days": 142,
                    "average": 4.7
                },
                "topSenders": [
                    {"address": "frequent@customer.com", "messageCount": 28},
                    {"address": "partner@business.com", "messageCount": 19}
                ],
                "folderDistribution": {
                    "inbox": 1100,
                    "voice-messages": 89,
                    "resolved": 61
                },
                "responseTime": {
                    "averageHours": 4.2,
                    "medianHours": 2.8
                }
            }
            
            mock_service.return_value.get_shared_mailbox_statistics.return_value = mock_statistics
            
            email_address = "support@example.com"
            response = await api_client.client.get(
                f"/api/v1/shared-mailboxes/{email_address}/statistics"
            )
            
            ResponseAssertions.assert_success_response(response)
            
            stats_data = response.json()
            assert stats_data["totalMessages"] == 1250
            assert stats_data["voiceMessages"] == 89
            assert "topSenders" in stats_data
            assert "folderDistribution" in stats_data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_shared_mailboxes_usage_analytics(self, api_client, override_auth_dependency):
        """Test getting usage analytics across shared mailboxes."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock accessible mailboxes
            mock_accessible = {
                "value": [
                    {"emailAddress": "support@example.com"},
                    {"emailAddress": "sales@example.com"}
                ]
            }
            
            # Mock individual statistics
            mock_stats_support = {"totalMessages": 500, "unreadMessages": 20}
            mock_stats_sales = {"totalMessages": 300, "unreadMessages": 15}
            
            mock_service.return_value.get_accessible_shared_mailboxes.return_value = mock_accessible
            mock_service.return_value.get_shared_mailbox_statistics.side_effect = [
                mock_stats_support, mock_stats_sales
            ]
            
            response = await api_client.client.get(
                "/api/v1/shared-mailboxes/analytics/usage",
                params={"days": 30}
            )
            
            ResponseAssertions.assert_success_response(response)
            
            analytics_data = response.json()
            assert analytics_data["period"]["days"] == 30
            assert analytics_data["mailboxes"]["total"] == 2
            assert analytics_data["activity"]["totalMessages"] == 800

    # =========================================================================
    # PERMISSION AND ACCESS CONTROL TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shared_mailbox_operations_require_authentication(self, authenticated_async_client):
        """Test that shared mailbox operations require authentication."""
        # Create client without auth headers
        async with httpx.AsyncClient(app=authenticated_async_client.app, base_url="http://test") as client:
            api_client = IntegrationAPIClient(client)
            
            # Test various endpoints
            endpoints_to_test = [
                lambda: api_client.get_shared_mailboxes(),
                lambda: api_client.get_shared_mailbox_details("test@example.com"),
                lambda: api_client.get_shared_mailbox_folders("test@example.com"),
                lambda: api_client.get_shared_mailbox_messages("test@example.com")
            ]
            
            for endpoint_test in endpoints_to_test:
                response = await endpoint_test()
                ResponseAssertions.assert_authentication_error(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shared_mailbox_permission_levels(self, api_client, override_auth_dependency):
        """Test different permission levels for shared mailbox operations."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Test read-only access
            mock_service.return_value.get_shared_mailbox_details.return_value = {
                "emailAddress": "readonly@example.com",
                "accessLevel": "read",
                "permissions": ["read"]
            }
            
            # Read operations should work
            response = await api_client.get_shared_mailbox_details("readonly@example.com")
            ResponseAssertions.assert_success_response(response)
            
            # Write operations should fail
            from app.core.Exceptions import AuthorizationError
            mock_service.return_value.send_shared_mailbox_message.side_effect = AuthorizationError(
                "Write permission required"
            )
            
            send_request = {
                "to": [{"emailAddress": {"address": "test@example.com"}}],
                "subject": "Test",
                "body": {"content": "Test"}
            }
            
            send_response = await api_client.client.post(
                "/api/v1/shared-mailboxes/readonly@example.com/send",
                json=send_request
            )
            
            ResponseAssertions.assert_authorization_error(send_response)

    # =========================================================================
    # PERFORMANCE AND CONCURRENCY TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_shared_mailbox_access(self, api_client, override_auth_dependency):
        """Test concurrent access to shared mailboxes."""
        from tests.integration.utils import run_concurrent_requests
        
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock responses for concurrent access
            mock_service.return_value.get_accessible_shared_mailboxes.return_value = {"value": []}
            mock_service.return_value.get_shared_mailbox_details.return_value = {
                "emailAddress": "concurrent@example.com"
            }
            
            # Create concurrent requests
            requests = [
                lambda: api_client.get_shared_mailboxes(),
                lambda: api_client.get_shared_mailbox_details("concurrent@example.com"),
                lambda: api_client.get_shared_mailboxes(),
                lambda: api_client.get_shared_mailbox_details("concurrent@example.com"),
            ]
            
            # Execute concurrently
            responses = await run_concurrent_requests(requests, max_concurrent=2)
            
            # All requests should succeed
            for response in responses:
                if isinstance(response, Exception):
                    pytest.fail(f"Concurrent request failed: {response}")
                ResponseAssertions.assert_success_response(response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shared_mailbox_search_performance(self, api_client, override_auth_dependency):
        """Test performance of shared mailbox search operations."""
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_service:
            # Mock search with performance metrics
            mock_search_results = {
                "query": "performance test",
                "totalResults": 100,
                "searchedMailboxes": 5,
                "searchTimeMs": 850,  # Under 1 second
                "results": []
            }
            
            mock_service.return_value.search_shared_mailboxes.return_value = mock_search_results
            
            search_request = {
                "query": "performance test",
                "maxResults": 100
            }
            
            # Measure actual response time
            import time
            start_time = time.time()
            
            response = await api_client.client.post(
                "/api/v1/shared-mailboxes/search",
                json=search_request
            )
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            ResponseAssertions.assert_success_response(response)
            
            # Response should be reasonably fast (under 2 seconds for integration test)
            assert response_time_ms < 2000, f"Response too slow: {response_time_ms:.2f}ms"
            
            search_data = response.json()
            assert search_data["searchTimeMs"] == 850