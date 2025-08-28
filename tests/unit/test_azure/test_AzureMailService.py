"""
Unit tests for AzureMailService.

Tests Azure Mail Service functionality including:
- Shared mailbox discovery and permissions
- Shared mailbox message operations
- Mail sending from shared accounts
- Folder synchronization and management
- Message filtering and search
- Delegation and access management
- Error handling for mail operations
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import httpx

from app.azure.AzureMailService import AzureMailService
from app.core.Exceptions import ValidationError, AuthenticationError
from tests.fixtures.mock_responses import GRAPH_API_RESPONSES, ERROR_RESPONSES


class TestAzureMailService:
    """Test suite for AzureMailService."""

    @pytest.fixture
    def mail_service(self):
        """Create AzureMailService instance.""" 
        return AzureMailService()

    @pytest.fixture
    def mock_access_token(self):
        """Mock access token for testing."""
        return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test-mail-token"

    @pytest.fixture
    def mock_shared_mailboxes_response(self):
        """Mock shared mailboxes response."""
        return {
            "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users",
            "value": [
                {
                    "id": "shared-mailbox-1",
                    "displayName": "Support Team",
                    "mail": "support@example.com",
                    "userPrincipalName": "support@example.com",
                    "userType": "Member",
                    "accountEnabled": True,
                    "mailboxSettings": {
                        "timeZone": "UTC",
                        "language": {"locale": "en-US"}
                    }
                },
                {
                    "id": "shared-mailbox-2", 
                    "displayName": "Sales Team",
                    "mail": "sales@example.com",
                    "userPrincipalName": "sales@example.com",
                    "userType": "Member",
                    "accountEnabled": True,
                    "mailboxSettings": {
                        "timeZone": "Pacific Standard Time",
                        "language": {"locale": "en-US"}
                    }
                }
            ]
        }

    @pytest.fixture
    def mock_shared_mailbox_messages_response(self):
        """Mock shared mailbox messages response."""
        return {
            "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('shared-mailbox-1')/messages",
            "value": [
                {
                    "id": "shared-msg-1",
                    "createdDateTime": "2025-01-15T10:30:00Z",
                    "lastModifiedDateTime": "2025-01-15T10:30:00Z",
                    "receivedDateTime": "2025-01-15T10:30:00Z",
                    "sentDateTime": "2025-01-15T10:29:45Z",
                    "hasAttachments": True,
                    "subject": "Customer Support Inquiry",
                    "bodyPreview": "Hi, I need help with my account...",
                    "importance": "normal",
                    "parentFolderId": "shared-inbox",
                    "isRead": False,
                    "from": {
                        "emailAddress": {
                            "name": "Customer Name",
                            "address": "customer@external.com"
                        }
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "name": "Support Team",
                                "address": "support@example.com"
                            }
                        }
                    ]
                },
                {
                    "id": "shared-msg-2",
                    "createdDateTime": "2025-01-15T09:15:00Z",
                    "receivedDateTime": "2025-01-15T09:15:00Z",
                    "hasAttachments": False,
                    "subject": "Sales Follow-up Required",
                    "bodyPreview": "Please follow up on the proposal...",
                    "importance": "high",
                    "isRead": True,
                    "from": {
                        "emailAddress": {
                            "name": "Sales Manager",
                            "address": "manager@example.com"
                        }
                    }
                }
            ]
        }

    # ==========================================================================
    # INITIALIZATION TESTS
    # ==========================================================================

    def test_service_initialization(self, mail_service):
        """Test service initialization."""
        assert mail_service is not None

    @patch('app.azure.AzureMailService.AzureGraphService')
    def test_service_initialization_with_graph_service(self, mock_graph_service, mail_service):
        """Test service initialization with Graph service dependency."""
        mock_graph_instance = Mock()
        mock_graph_service.return_value = mock_graph_instance
        
        # Re-initialize to test dependency injection
        service = AzureMailService()
        
        assert service is not None

    # ==========================================================================
    # SHARED MAILBOX DISCOVERY TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_shared_mailboxes_success(self, mail_service, mock_access_token,
                                               mock_shared_mailboxes_response):
        """Test successful shared mailbox discovery."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_shared_mailboxes_response
            mock_request.return_value = mock_response

            result = await mail_service.get_shared_mailboxes(mock_access_token)

            assert "value" in result
            assert len(result["value"]) == 2
            mailbox_emails = [mb["mail"] for mb in result["value"]]
            assert "support@example.com" in mailbox_emails
            assert "sales@example.com" in mailbox_emails

    @pytest.mark.asyncio
    async def test_get_shared_mailboxes_with_filter(self, mail_service, mock_access_token,
                                                   mock_shared_mailboxes_response):
        """Test shared mailbox discovery with department filter."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            # Filter response to only support team
            filtered_response = mock_shared_mailboxes_response.copy()
            filtered_response["value"] = [mock_shared_mailboxes_response["value"][0]]
            mock_response.json.return_value = filtered_response
            mock_request.return_value = mock_response

            result = await mail_service.get_shared_mailboxes(
                mock_access_token, 
                filter_department="Support"
            )

            assert len(result["value"]) == 1
            assert result["value"][0]["displayName"] == "Support Team"

    @pytest.mark.asyncio
    async def test_get_shared_mailboxes_unauthorized(self, mail_service, mock_access_token):
        """Test shared mailbox discovery with unauthorized access."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.json.return_value = ERROR_RESPONSES["forbidden"]
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError):
                await mail_service.get_shared_mailboxes(mock_access_token)

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_permissions(self, mail_service, mock_access_token):
        """Test retrieving shared mailbox permissions."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            permissions_response = {
                "value": [
                    {
                        "id": "permission-1",
                        "emailAddress": {
                            "address": "user1@example.com",
                            "name": "User One"
                        },
                        "roles": ["fullaccess", "sendas"]
                    },
                    {
                        "id": "permission-2",
                        "emailAddress": {
                            "address": "user2@example.com", 
                            "name": "User Two"
                        },
                        "roles": ["readpermission"]
                    }
                ]
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = permissions_response
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            result = await mail_service.get_shared_mailbox_permissions(
                mock_access_token, mailbox_email
            )

            assert "value" in result
            assert len(result["value"]) == 2
            user_permissions = {perm["emailAddress"]["address"]: perm["roles"] for perm in result["value"]}
            assert "fullaccess" in user_permissions["user1@example.com"]
            assert "sendas" in user_permissions["user1@example.com"]
            assert "readpermission" in user_permissions["user2@example.com"]

    # ==========================================================================
    # SHARED MAILBOX MESSAGE OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_messages_success(self, mail_service, mock_access_token,
                                                      mock_shared_mailbox_messages_response):
        """Test successful shared mailbox message retrieval."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_shared_mailbox_messages_response
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            result = await mail_service.get_shared_mailbox_messages(
                mock_access_token, mailbox_email
            )

            assert "value" in result
            assert len(result["value"]) == 2
            
            first_message = result["value"][0]
            assert first_message["subject"] == "Customer Support Inquiry"
            assert first_message["isRead"] is False
            assert first_message["hasAttachments"] is True

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_messages_with_filters(self, mail_service, mock_access_token,
                                                           mock_shared_mailbox_messages_response):
        """Test shared mailbox message retrieval with filters."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            # Filter for unread messages only
            filtered_response = mock_shared_mailbox_messages_response.copy()
            filtered_response["value"] = [msg for msg in filtered_response["value"] if not msg.get("isRead", True)]
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = filtered_response
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            result = await mail_service.get_shared_mailbox_messages(
                mock_access_token,
                mailbox_email,
                filter_unread=True
            )

            assert len(result["value"]) == 1
            assert result["value"][0]["isRead"] is False

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_messages_with_pagination(self, mail_service, mock_access_token):
        """Test shared mailbox message retrieval with pagination."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"value": [], "@odata.nextLink": "next_page_url"}
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            result = await mail_service.get_shared_mailbox_messages(
                mock_access_token,
                mailbox_email,
                top=25,
                skip=50
            )

            # Verify pagination parameters were passed
            call_args = mock_request.call_args
            assert "$top=25" in str(call_args) or call_args[1].get("params", {}).get("$top") == 25
            assert "$skip=50" in str(call_args) or call_args[1].get("params", {}).get("$skip") == 50

    @pytest.mark.asyncio
    async def test_get_shared_mailbox_message_by_id(self, mail_service, mock_access_token):
        """Test retrieving specific message from shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            message_data = {
                "id": "shared-msg-1",
                "subject": "Specific Message",
                "bodyPreview": "Message body preview...",
                "hasAttachments": True,
                "isRead": False
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = message_data
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            message_id = "shared-msg-1"
            
            result = await mail_service.get_shared_mailbox_message(
                mock_access_token, mailbox_email, message_id
            )

            assert result["id"] == message_id
            assert result["subject"] == "Specific Message"
            assert result["hasAttachments"] is True

    @pytest.mark.asyncio
    async def test_search_shared_mailbox_messages(self, mail_service, mock_access_token):
        """Test searching messages in shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            search_results = {
                "value": [
                    {
                        "id": "search-result-1",
                        "subject": "Voice Message: Customer Inquiry",
                        "hasAttachments": True,
                        "bodyPreview": "Customer left a voice message...",
                        "from": {
                            "emailAddress": {
                                "address": "customer@example.com",
                                "name": "Customer"
                            }
                        }
                    }
                ]
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = search_results
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            search_query = "voice message"
            
            result = await mail_service.search_shared_mailbox_messages(
                mock_access_token, mailbox_email, search_query
            )

            assert len(result["value"]) == 1
            assert "Voice Message" in result["value"][0]["subject"]

    # ==========================================================================
    # MAIL SENDING TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_send_mail_from_shared_mailbox_success(self, mail_service, mock_access_token):
        """Test successful mail sending from shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 202  # Accepted for send operation
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            message_data = {
                "subject": "Response from Support Team",
                "body": {
                    "contentType": "html",
                    "content": "<p>Thank you for contacting us...</p>"
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": "customer@example.com",
                            "name": "Customer"
                        }
                    }
                ]
            }

            result = await mail_service.send_mail_from_shared_mailbox(
                mock_access_token, mailbox_email, message_data
            )

            assert result is True
            # Verify send endpoint was called
            call_args = mock_request.call_args
            assert "sendMail" in str(call_args)

    @pytest.mark.asyncio
    async def test_send_mail_from_shared_mailbox_with_attachments(self, mail_service, mock_access_token):
        """Test mail sending from shared mailbox with attachments."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 202
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            message_data = {
                "subject": "Response with Attachment",
                "body": {
                    "contentType": "text",
                    "content": "Please see attached file."
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": "customer@example.com"
                        }
                    }
                ],
                "attachments": [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": "response.pdf",
                        "contentType": "application/pdf",
                        "contentBytes": "base64encodeddata=="
                    }
                ]
            }

            result = await mail_service.send_mail_from_shared_mailbox(
                mock_access_token, mailbox_email, message_data
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_mail_validation_error(self, mail_service, mock_access_token):
        """Test mail sending with validation errors."""
        # Missing required fields
        invalid_message = {
            "subject": "Test",
            # Missing body and recipients
        }

        with pytest.raises(ValidationError):
            await mail_service.send_mail_from_shared_mailbox(
                mock_access_token, "support@example.com", invalid_message
            )

    @pytest.mark.asyncio
    async def test_send_mail_permission_denied(self, mail_service, mock_access_token):
        """Test mail sending with insufficient permissions."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.json.return_value = ERROR_RESPONSES["forbidden"]
            mock_request.return_value = mock_response

            message_data = {
                "subject": "Test Message",
                "body": {"contentType": "text", "content": "Test content"},
                "toRecipients": [{"emailAddress": {"address": "test@example.com"}}]
            }

            with pytest.raises(AuthenticationError):
                await mail_service.send_mail_from_shared_mailbox(
                    mock_access_token, "support@example.com", message_data
                )

    # ==========================================================================
    # FOLDER SYNCHRONIZATION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_sync_shared_mailbox_folders(self, mail_service, mock_access_token):
        """Test synchronizing shared mailbox folders."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            folders_response = {
                "value": [
                    {
                        "id": "shared-inbox",
                        "displayName": "Inbox",
                        "parentFolderId": "shared-root",
                        "unreadItemCount": 5,
                        "totalItemCount": 25
                    },
                    {
                        "id": "shared-sent",
                        "displayName": "Sent Items", 
                        "parentFolderId": "shared-root",
                        "unreadItemCount": 0,
                        "totalItemCount": 15
                    }
                ]
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = folders_response
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            result = await mail_service.sync_shared_mailbox_folders(
                mock_access_token, mailbox_email
            )

            assert "value" in result
            assert len(result["value"]) == 2
            folder_names = [f["displayName"] for f in result["value"]]
            assert "Inbox" in folder_names
            assert "Sent Items" in folder_names

    @pytest.mark.asyncio
    async def test_create_shared_mailbox_folder(self, mail_service, mock_access_token):
        """Test creating folder in shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            created_folder = {
                "id": "new-voice-folder",
                "displayName": "Voice Messages",
                "parentFolderId": "shared-inbox",
                "unreadItemCount": 0,
                "totalItemCount": 0
            }
            
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = created_folder
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            folder_name = "Voice Messages"
            parent_folder_id = "shared-inbox"

            result = await mail_service.create_shared_mailbox_folder(
                mock_access_token, mailbox_email, folder_name, parent_folder_id
            )

            assert result["displayName"] == folder_name
            assert result["parentFolderId"] == parent_folder_id

    # ==========================================================================
    # MESSAGE OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_move_shared_mailbox_message(self, mail_service, mock_access_token):
        """Test moving message in shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            moved_message = {
                "id": "shared-msg-1",
                "parentFolderId": "voice-folder-id",
                "subject": "Moved Message"
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = moved_message
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            message_id = "shared-msg-1"
            destination_folder_id = "voice-folder-id"

            result = await mail_service.move_shared_mailbox_message(
                mock_access_token, mailbox_email, message_id, destination_folder_id
            )

            assert result["parentFolderId"] == destination_folder_id

    @pytest.mark.asyncio
    async def test_update_shared_mailbox_message_read_status(self, mail_service, mock_access_token):
        """Test updating message read status in shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            updated_message = {
                "id": "shared-msg-1",
                "isRead": True,
                "subject": "Updated Message"
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = updated_message
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            message_id = "shared-msg-1"

            result = await mail_service.update_shared_mailbox_message(
                mock_access_token, mailbox_email, message_id, is_read=True
            )

            assert result["isRead"] is True

    # ==========================================================================
    # DELEGATION AND ACCESS MANAGEMENT TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_grant_shared_mailbox_access(self, mail_service, mock_access_token):
        """Test granting access to shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "id": "new-permission",
                "emailAddress": {
                    "address": "newuser@example.com",
                    "name": "New User"
                },
                "roles": ["fullaccess"]
            }
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            user_email = "newuser@example.com"
            permissions = ["fullaccess", "sendas"]

            result = await mail_service.grant_shared_mailbox_access(
                mock_access_token, mailbox_email, user_email, permissions
            )

            assert result["emailAddress"]["address"] == user_email

    @pytest.mark.asyncio
    async def test_revoke_shared_mailbox_access(self, mail_service, mock_access_token):
        """Test revoking access to shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 204  # No content for deletion
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            user_email = "user@example.com"

            result = await mail_service.revoke_shared_mailbox_access(
                mock_access_token, mailbox_email, user_email
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_check_shared_mailbox_access(self, mail_service, mock_access_token):
        """Test checking user access to shared mailbox."""
        with patch.object(mail_service, 'get_shared_mailbox_permissions') as mock_get_perms:
            permissions_response = {
                "value": [
                    {
                        "emailAddress": {"address": "user@example.com"},
                        "roles": ["fullaccess", "sendas"]
                    }
                ]
            }
            mock_get_perms.return_value = permissions_response

            mailbox_email = "support@example.com"
            user_email = "user@example.com"

            access_info = await mail_service.check_shared_mailbox_access(
                mock_access_token, mailbox_email, user_email
            )

            assert access_info["has_access"] is True
            assert "fullaccess" in access_info["roles"]
            assert "sendas" in access_info["roles"]

    # ==========================================================================
    # BATCH OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_batch_update_shared_messages(self, mail_service, mock_access_token):
        """Test batch updating multiple messages in shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            batch_response = {
                "responses": [
                    {"id": "1", "status": 200, "body": {"isRead": True}},
                    {"id": "2", "status": 200, "body": {"isRead": True}},
                    {"id": "3", "status": 200, "body": {"isRead": True}}
                ]
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = batch_response
            mock_request.return_value = mock_response

            mailbox_email = "support@example.com"
            message_ids = ["msg-1", "msg-2", "msg-3"]
            update_data = {"isRead": True}

            results = await mail_service.batch_update_shared_messages(
                mock_access_token, mailbox_email, message_ids, update_data
            )

            assert len(results["responses"]) == 3
            assert all(resp["status"] == 200 for resp in results["responses"])

    # ==========================================================================
    # ERROR HANDLING TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_handle_shared_mailbox_not_found(self, mail_service, mock_access_token):
        """Test handling of non-existent shared mailbox."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = ERROR_RESPONSES["not_found"]
            mock_request.return_value = mock_response

            with pytest.raises(ValidationError):
                await mail_service.get_shared_mailbox_messages(
                    mock_access_token, "nonexistent@example.com"
                )

    @pytest.mark.asyncio
    async def test_handle_rate_limiting(self, mail_service, mock_access_token):
        """Test handling of rate limiting for shared mailbox operations."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            # First call returns rate limit, second succeeds
            rate_limit_response = Mock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {"Retry-After": "60"}

            success_response = Mock()
            success_response.status_code = 200
            success_response.json.return_value = {"value": []}

            mock_request.side_effect = [rate_limit_response, success_response]

            with patch('asyncio.sleep') as mock_sleep:
                result = await mail_service.get_shared_mailboxes(mock_access_token)

                assert result is not None
                mock_sleep.assert_called_once_with(60)
                assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_network_timeout(self, mail_service, mock_access_token):
        """Test handling of network timeouts."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(AuthenticationError):
                await mail_service.get_shared_mailboxes(mock_access_token)

    # ==========================================================================
    # UTILITY AND HELPER TESTS
    # ==========================================================================

    def test_validate_mailbox_email_valid(self, mail_service):
        """Test validation of valid mailbox email addresses."""
        valid_emails = [
            "support@example.com",
            "sales.team@company.org",
            "info+dept@domain.co.uk"
        ]
        
        for email in valid_emails:
            # Should not raise exception
            mail_service._validate_mailbox_email(email)

    def test_validate_mailbox_email_invalid(self, mail_service):
        """Test validation of invalid mailbox email addresses."""
        invalid_emails = [
            "",
            "invalid-email",
            "@example.com",
            "user@",
            "user@domain"
        ]
        
        for email in invalid_emails:
            with pytest.raises(ValidationError):
                mail_service._validate_mailbox_email(email)

    def test_build_shared_mailbox_endpoint(self, mail_service):
        """Test building shared mailbox API endpoints."""
        mailbox_email = "support@example.com"
        
        # Test messages endpoint
        messages_endpoint = mail_service._build_shared_mailbox_endpoint(
            mailbox_email, "messages"
        )
        expected = f"/users/{mailbox_email}/messages"
        assert messages_endpoint == expected
        
        # Test folders endpoint
        folders_endpoint = mail_service._build_shared_mailbox_endpoint(
            mailbox_email, "mailFolders"
        )
        expected = f"/users/{mailbox_email}/mailFolders"
        assert folders_endpoint == expected

    def test_format_message_filters(self, mail_service):
        """Test formatting message filter parameters."""
        filters = {
            "unread_only": True,
            "has_attachments": True,
            "from_date": "2025-01-01",
            "to_date": "2025-01-31"
        }
        
        formatted_filters = mail_service._format_message_filters(filters)
        
        assert "$filter" in formatted_filters
        filter_str = formatted_filters["$filter"]
        assert "isRead eq false" in filter_str
        assert "hasAttachments eq true" in filter_str
        assert "receivedDateTime ge" in filter_str

    @pytest.mark.asyncio
    async def test_pagination_handling(self, mail_service, mock_access_token):
        """Test handling of paginated responses."""
        with patch.object(mail_service, '_make_graph_request') as mock_request:
            # First page
            first_page = {
                "value": [{"id": "msg-1"}, {"id": "msg-2"}],
                "@odata.nextLink": "https://graph.microsoft.com/v1.0/next-page"
            }
            
            # Second page (last page)
            second_page = {
                "value": [{"id": "msg-3"}, {"id": "msg-4"}]
            }
            
            mock_request.side_effect = [
                Mock(status_code=200, json=Mock(return_value=first_page)),
                Mock(status_code=200, json=Mock(return_value=second_page))
            ]
            
            all_messages = await mail_service.get_all_shared_mailbox_messages(
                mock_access_token, "support@example.com"
            )
            
            assert len(all_messages) == 4
            message_ids = [msg["id"] for msg in all_messages]
            assert "msg-1" in message_ids
            assert "msg-4" in message_ids