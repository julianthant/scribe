"""
Unit tests for SharedMailboxService.

Tests the shared mailbox operations service including:
- Shared mailbox discovery and access
- Shared mailbox message operations
- Permission management
- Folder operations in shared mailboxes
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.SharedMailboxService import SharedMailboxService
from app.core.Exceptions import ValidationError, AuthenticationError, NotFoundError


class TestSharedMailboxService:
    """Unit tests for SharedMailboxService class."""

    @pytest.fixture
    def mock_azure_mail_service(self):
        """Mock AzureMailService dependency."""
        mock_service = Mock()
        mock_service.get_shared_mailboxes = AsyncMock()
        mock_service.get_shared_mailbox_details = AsyncMock()
        mock_service.get_shared_mailbox_folders = AsyncMock()
        mock_service.get_shared_mailbox_messages = AsyncMock()
        mock_service.send_from_shared_mailbox = AsyncMock()
        return mock_service

    @pytest.fixture
    def shared_mailbox_service(self, mock_azure_mail_service):
        """Create SharedMailboxService with mocked dependencies."""
        with patch('app.services.SharedMailboxService.azure_mail_service', mock_azure_mail_service):
            return SharedMailboxService()

    @pytest.fixture
    def mock_shared_mailboxes(self):
        """Mock shared mailboxes response."""
        return [
            {
                "id": "mailbox1@company.com",
                "displayName": "Customer Support",
                "emailAddress": "support@company.com",
                "permissions": ["read", "write", "send"],
                "description": "Customer support shared mailbox"
            },
            {
                "id": "mailbox2@company.com", 
                "displayName": "Sales Team",
                "emailAddress": "sales@company.com",
                "permissions": ["read", "write"],
                "description": "Sales team communications"
            }
        ]

    # =====================================================================
    # Shared Mailbox Discovery Tests
    # =====================================================================

    async def test_get_shared_mailboxes_success(self, shared_mailbox_service, mock_azure_mail_service, mock_shared_mailboxes):
        """Test getting accessible shared mailboxes."""
        mock_azure_mail_service.get_shared_mailboxes.return_value = mock_shared_mailboxes
        
        result = await shared_mailbox_service.get_shared_mailboxes("test_token")
        
        assert len(result) == 2
        assert result[0]["displayName"] == "Customer Support"
        assert result[1]["emailAddress"] == "sales@company.com"
        mock_azure_mail_service.get_shared_mailboxes.assert_called_once_with("test_token")

    async def test_get_shared_mailboxes_no_access(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting shared mailboxes when user has no access."""
        mock_azure_mail_service.get_shared_mailboxes.return_value = []
        
        result = await shared_mailbox_service.get_shared_mailboxes("test_token")
        
        assert result == []

    async def test_get_shared_mailboxes_auth_error(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting shared mailboxes with authentication error."""
        mock_azure_mail_service.get_shared_mailboxes.side_effect = AuthenticationError("Invalid token")
        
        with pytest.raises(AuthenticationError):
            await shared_mailbox_service.get_shared_mailboxes("invalid_token")

    # =====================================================================
    # Shared Mailbox Details Tests
    # =====================================================================

    async def test_get_shared_mailbox_details_success(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting shared mailbox details."""
        mock_details = {
            "id": "support@company.com",
            "displayName": "Customer Support",
            "emailAddress": "support@company.com",
            "permissions": ["read", "write", "send"],
            "folderCount": 15,
            "totalMessages": 2543,
            "unreadMessages": 47,
            "lastActivity": "2024-08-28T09:30:00Z"
        }
        mock_azure_mail_service.get_shared_mailbox_details.return_value = mock_details
        
        result = await shared_mailbox_service.get_shared_mailbox_details(
            access_token="test_token",
            email_address="support@company.com"
        )
        
        assert result == mock_details
        assert result["displayName"] == "Customer Support"
        assert result["unreadMessages"] == 47
        mock_azure_mail_service.get_shared_mailbox_details.assert_called_once_with(
            "test_token", "support@company.com"
        )

    async def test_get_shared_mailbox_details_not_found(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting details for non-existent shared mailbox."""
        mock_azure_mail_service.get_shared_mailbox_details.side_effect = NotFoundError("Mailbox not found")
        
        with pytest.raises(NotFoundError):
            await shared_mailbox_service.get_shared_mailbox_details(
                "test_token", "nonexistent@company.com"
            )

    async def test_get_shared_mailbox_details_invalid_email(self, shared_mailbox_service):
        """Test getting details with invalid email format."""
        with pytest.raises(ValidationError):
            await shared_mailbox_service.get_shared_mailbox_details(
                "test_token", "invalid-email-format"
            )

    # =====================================================================
    # Shared Mailbox Folder Tests
    # =====================================================================

    async def test_get_shared_mailbox_folders_success(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting folders from shared mailbox."""
        mock_folders = [
            {
                "id": "inbox",
                "displayName": "Inbox",
                "parentFolderId": None,
                "unreadItemCount": 25,
                "totalItemCount": 150
            },
            {
                "id": "processed",
                "displayName": "Processed",
                "parentFolderId": None,
                "unreadItemCount": 0,
                "totalItemCount": 300
            }
        ]
        mock_azure_mail_service.get_shared_mailbox_folders.return_value = mock_folders
        
        result = await shared_mailbox_service.get_shared_mailbox_folders(
            access_token="test_token",
            email_address="support@company.com"
        )
        
        assert len(result) == 2
        assert result[0]["displayName"] == "Inbox"
        assert result[0]["unreadItemCount"] == 25
        mock_azure_mail_service.get_shared_mailbox_folders.assert_called_once_with(
            "test_token", "support@company.com"
        )

    async def test_get_shared_mailbox_folders_no_access(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting folders without proper permissions."""
        mock_azure_mail_service.get_shared_mailbox_folders.side_effect = AuthenticationError("Insufficient permissions")
        
        with pytest.raises(AuthenticationError):
            await shared_mailbox_service.get_shared_mailbox_folders(
                "test_token", "restricted@company.com"
            )

    # =====================================================================
    # Shared Mailbox Message Tests
    # =====================================================================

    async def test_get_shared_mailbox_messages_success(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting messages from shared mailbox."""
        mock_messages = {
            "value": [
                {
                    "id": "message1",
                    "subject": "Customer inquiry",
                    "from": {
                        "emailAddress": {
                            "name": "Customer",
                            "address": "customer@example.com"
                        }
                    },
                    "receivedDateTime": "2024-08-28T10:00:00Z",
                    "isRead": False,
                    "hasAttachments": False
                }
            ],
            "@odata.nextLink": None
        }
        mock_azure_mail_service.get_shared_mailbox_messages.return_value = mock_messages
        
        result = await shared_mailbox_service.get_shared_mailbox_messages(
            access_token="test_token",
            email_address="support@company.com",
            folder_id="inbox",
            top=25,
            skip=0
        )
        
        assert result == mock_messages
        assert len(result["value"]) == 1
        assert result["value"][0]["subject"] == "Customer inquiry"
        mock_azure_mail_service.get_shared_mailbox_messages.assert_called_once_with(
            "test_token", "support@company.com", "inbox", 25, 0, None
        )

    async def test_get_shared_mailbox_messages_with_filter(self, shared_mailbox_service, mock_azure_mail_service):
        """Test getting messages with attachment filter."""
        mock_messages = {"value": []}
        mock_azure_mail_service.get_shared_mailbox_messages.return_value = mock_messages
        
        result = await shared_mailbox_service.get_shared_mailbox_messages(
            access_token="test_token",
            email_address="support@company.com",
            folder_id="inbox",
            has_attachments=True
        )
        
        mock_azure_mail_service.get_shared_mailbox_messages.assert_called_once_with(
            "test_token", "support@company.com", "inbox", 25, 0, True
        )

    async def test_get_shared_mailbox_messages_invalid_email(self, shared_mailbox_service):
        """Test getting messages with invalid email address."""
        with pytest.raises(ValidationError):
            await shared_mailbox_service.get_shared_mailbox_messages(
                "test_token", "invalid-email", "inbox"
            )

    # =====================================================================
    # Message Sending Tests
    # =====================================================================

    async def test_send_from_shared_mailbox_success(self, shared_mailbox_service, mock_azure_mail_service):
        """Test sending message from shared mailbox."""
        mock_response = {
            "id": "sent_message_123",
            "status": "sent",
            "sentDateTime": "2024-08-28T10:00:00Z"
        }
        mock_azure_mail_service.send_from_shared_mailbox.return_value = mock_response
        
        message_data = {
            "to": ["recipient@example.com"],
            "subject": "Response from support",
            "body": "Thank you for your inquiry.",
            "bodyType": "text"
        }
        
        result = await shared_mailbox_service.send_from_shared_mailbox(
            access_token="test_token",
            shared_mailbox_email="support@company.com",
            message_data=message_data
        )
        
        assert result == mock_response
        assert result["status"] == "sent"
        mock_azure_mail_service.send_from_shared_mailbox.assert_called_once_with(
            "test_token", "support@company.com", message_data
        )

    async def test_send_from_shared_mailbox_no_permission(self, shared_mailbox_service, mock_azure_mail_service):
        """Test sending message without send permission."""
        mock_azure_mail_service.send_from_shared_mailbox.side_effect = AuthenticationError("Send permission required")
        
        message_data = {
            "to": ["recipient@example.com"],
            "subject": "Test message",
            "body": "Test content"
        }
        
        with pytest.raises(AuthenticationError):
            await shared_mailbox_service.send_from_shared_mailbox(
                "test_token", "restricted@company.com", message_data
            )

    async def test_send_from_shared_mailbox_validation_error(self, shared_mailbox_service):
        """Test sending message with invalid data."""
        # Missing required fields
        invalid_message_data = {
            "subject": "Test message"
            # Missing 'to' and 'body'
        }
        
        with pytest.raises(ValidationError):
            await shared_mailbox_service.send_from_shared_mailbox(
                "test_token", "support@company.com", invalid_message_data
            )

    # =====================================================================
    # Permission Management Tests
    # =====================================================================

    async def test_check_shared_mailbox_permissions_success(self, shared_mailbox_service, mock_azure_mail_service):
        """Test checking permissions for shared mailbox."""
        mock_details = {
            "permissions": ["read", "write", "send"]
        }
        mock_azure_mail_service.get_shared_mailbox_details.return_value = mock_details
        
        result = await shared_mailbox_service.check_shared_mailbox_permissions(
            access_token="test_token",
            email_address="support@company.com"
        )
        
        assert result == ["read", "write", "send"]
        assert "send" in result

    async def test_has_permission_read_only(self, shared_mailbox_service, mock_azure_mail_service):
        """Test checking specific permission (read-only access)."""
        mock_details = {
            "permissions": ["read"]
        }
        mock_azure_mail_service.get_shared_mailbox_details.return_value = mock_details
        
        has_read = await shared_mailbox_service.has_permission(
            "test_token", "readonly@company.com", "read"
        )
        has_write = await shared_mailbox_service.has_permission(
            "test_token", "readonly@company.com", "write"
        )
        
        assert has_read is True
        assert has_write is False

    async def test_has_permission_full_access(self, shared_mailbox_service, mock_azure_mail_service):
        """Test checking permissions for full access mailbox."""
        mock_details = {
            "permissions": ["read", "write", "send", "manage"]
        }
        mock_azure_mail_service.get_shared_mailbox_details.return_value = mock_details
        
        permissions_to_check = ["read", "write", "send", "manage", "delete"]
        results = []
        
        for permission in permissions_to_check:
            has_permission = await shared_mailbox_service.has_permission(
                "test_token", "admin@company.com", permission
            )
            results.append(has_permission)
        
        assert results == [True, True, True, True, False]  # All except 'delete'

    # =====================================================================
    # Utility Method Tests
    # =====================================================================

    async def test_validate_email_address_valid(self, shared_mailbox_service):
        """Test validating valid email addresses."""
        valid_emails = [
            "support@company.com",
            "sales.team@example.org",
            "info@test-domain.co.uk"
        ]
        
        for email in valid_emails:
            # Should not raise exception
            shared_mailbox_service._validate_email_address(email)

    async def test_validate_email_address_invalid(self, shared_mailbox_service):
        """Test validating invalid email addresses."""
        invalid_emails = [
            "",
            "invalid-email",
            "@company.com",
            "support@",
            "support company.com"
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                shared_mailbox_service._validate_email_address(email)

    async def test_validate_message_data_valid(self, shared_mailbox_service):
        """Test validating valid message data."""
        valid_message = {
            "to": ["recipient@example.com"],
            "subject": "Test subject",
            "body": "Test message body"
        }
        
        # Should not raise exception
        shared_mailbox_service._validate_message_data(valid_message)

    async def test_validate_message_data_missing_fields(self, shared_mailbox_service):
        """Test validating message data with missing required fields."""
        invalid_messages = [
            {},  # Empty
            {"subject": "Test"},  # Missing 'to' and 'body'
            {"to": ["test@example.com"]},  # Missing 'subject' and 'body'
            {"to": [], "subject": "Test", "body": "Content"},  # Empty 'to' list
        ]
        
        for message_data in invalid_messages:
            with pytest.raises(ValidationError):
                shared_mailbox_service._validate_message_data(message_data)

    async def test_extract_error_message_graph_error(self, shared_mailbox_service):
        """Test extracting error message from Graph API error."""
        mock_error = Exception("Graph API Error: Mailbox not found")
        
        result = shared_mailbox_service._extract_error_message(mock_error)
        
        assert "Mailbox not found" in result

    # =====================================================================
    # Error Handling Tests
    # =====================================================================

    async def test_network_timeout_handling(self, shared_mailbox_service, mock_azure_mail_service):
        """Test handling network timeout errors."""
        mock_azure_mail_service.get_shared_mailboxes.side_effect = Exception("Request timeout")
        
        with pytest.raises(Exception) as exc_info:
            await shared_mailbox_service.get_shared_mailboxes("test_token")
        
        assert "Request timeout" in str(exc_info.value)

    async def test_service_unavailable_handling(self, shared_mailbox_service, mock_azure_mail_service):
        """Test handling service unavailable errors."""
        mock_azure_mail_service.get_shared_mailbox_details.side_effect = Exception("Service temporarily unavailable")
        
        with pytest.raises(Exception) as exc_info:
            await shared_mailbox_service.get_shared_mailbox_details("test_token", "support@company.com")
        
        assert "Service temporarily unavailable" in str(exc_info.value)

    async def test_rate_limit_handling(self, shared_mailbox_service, mock_azure_mail_service):
        """Test handling rate limit errors."""
        mock_azure_mail_service.get_shared_mailbox_messages.side_effect = Exception("Rate limit exceeded")
        
        with pytest.raises(Exception) as exc_info:
            await shared_mailbox_service.get_shared_mailbox_messages("test_token", "support@company.com", "inbox")
        
        assert "Rate limit exceeded" in str(exc_info.value)

    # =====================================================================
    # Integration Pattern Tests
    # =====================================================================

    async def test_shared_mailbox_workflow_success(self, shared_mailbox_service, mock_azure_mail_service):
        """Test complete shared mailbox workflow."""
        # Mock workflow: discover mailboxes -> get details -> get messages -> send reply
        
        # 1. Get available mailboxes
        mock_azure_mail_service.get_shared_mailboxes.return_value = [
            {"emailAddress": "support@company.com", "displayName": "Support"}
        ]
        
        # 2. Get mailbox details
        mock_azure_mail_service.get_shared_mailbox_details.return_value = {
            "emailAddress": "support@company.com",
            "permissions": ["read", "write", "send"]
        }
        
        # 3. Get messages
        mock_azure_mail_service.get_shared_mailbox_messages.return_value = {
            "value": [{"id": "message1", "subject": "Need help"}]
        }
        
        # 4. Send reply
        mock_azure_mail_service.send_from_shared_mailbox.return_value = {
            "id": "reply1", "status": "sent"
        }
        
        # Execute workflow
        mailboxes = await shared_mailbox_service.get_shared_mailboxes("test_token")
        details = await shared_mailbox_service.get_shared_mailbox_details("test_token", "support@company.com")
        messages = await shared_mailbox_service.get_shared_mailbox_messages("test_token", "support@company.com", "inbox")
        reply = await shared_mailbox_service.send_from_shared_mailbox(
            "test_token", "support@company.com", 
            {"to": ["customer@example.com"], "subject": "Re: Need help", "body": "We can help!"}
        )
        
        # Verify workflow completed successfully
        assert len(mailboxes) == 1
        assert "send" in details["permissions"]
        assert len(messages["value"]) == 1
        assert reply["status"] == "sent"

    async def test_concurrent_shared_mailbox_operations(self, shared_mailbox_service, mock_azure_mail_service):
        """Test handling concurrent shared mailbox operations."""
        mock_azure_mail_service.get_shared_mailbox_messages.return_value = {"value": []}
        
        # Send multiple concurrent requests to different mailboxes
        import asyncio
        
        mailboxes = ["support@company.com", "sales@company.com", "info@company.com"]
        
        tasks = [
            shared_mailbox_service.get_shared_mailbox_messages("test_token", mailbox, "inbox")
            for mailbox in mailboxes
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 3
        assert all("value" in result for result in results)