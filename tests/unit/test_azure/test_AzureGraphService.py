"""
Unit tests for AzureGraphService.

Tests Microsoft Graph API interactions including:
- User profile operations
- Mail folder management (get, create, update, delete)
- Message operations (get, search, move, update)
- Attachment handling and downloads
- Pagination and batching
- Rate limiting and retry logic
- Error handling for various HTTP status codes
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
import httpx
import json
from datetime import datetime, timedelta

from app.azure.AzureGraphService import AzureGraphService
from app.core.Exceptions import AuthenticationError, ValidationError
from tests.fixtures.mock_responses import GRAPH_API_RESPONSES, ERROR_RESPONSES


class TestAzureGraphService:
    """Test suite for AzureGraphService."""

    @pytest.fixture
    def graph_service(self):
        """Create AzureGraphService instance."""
        return AzureGraphService()

    @pytest.fixture
    def mock_access_token(self):
        """Mock access token for testing."""
        return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test-access-token"

    # ==========================================================================
    # USER PROFILE TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, graph_service, mock_access_token):
        """Test successful user profile retrieval."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["user_profile"]
            mock_request.return_value = mock_response

            result = await graph_service.get_user_profile(mock_access_token)

            assert result["id"] == "12345678-1234-1234-1234-123456789012"
            assert result["displayName"] == "Test User"
            assert result["mail"] == "testuser@example.com"
            mock_request.assert_called_once_with("GET", "/me", mock_access_token)

    @pytest.mark.asyncio
    async def test_get_user_profile_unauthorized(self, graph_service, mock_access_token):
        """Test user profile retrieval with unauthorized token."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = ERROR_RESPONSES["unauthorized"]
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError):
                await graph_service.get_user_profile(mock_access_token)

    @pytest.mark.asyncio
    async def test_get_user_profile_empty_token(self, graph_service):
        """Test user profile retrieval with empty token."""
        with pytest.raises(ValidationError):
            await graph_service.get_user_profile("")

    # ==========================================================================
    # MAIL FOLDER TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_mail_folders_success(self, graph_service, mock_access_token):
        """Test successful mail folders retrieval."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["mail_folders"]
            mock_request.return_value = mock_response

            result = await graph_service.get_mail_folders(mock_access_token)

            assert "value" in result
            assert len(result["value"]) == 3
            folder_names = [f["displayName"] for f in result["value"]]
            assert "Inbox" in folder_names
            assert "Sent Items" in folder_names
            mock_request.assert_called_once_with("GET", "/me/mailFolders", mock_access_token)

    @pytest.mark.asyncio
    async def test_get_mail_folders_empty_result(self, graph_service, mock_access_token):
        """Test mail folders retrieval with empty result."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["empty_folders"]
            mock_request.return_value = mock_response

            result = await graph_service.get_mail_folders(mock_access_token)

            assert "value" in result
            assert len(result["value"]) == 0

    @pytest.mark.asyncio
    async def test_create_mail_folder_success(self, graph_service, mock_access_token):
        """Test successful mail folder creation."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = GRAPH_API_RESPONSES["created_folder"]
            mock_request.return_value = mock_response

            folder_name = "Voice Messages"
            parent_folder_id = "inbox"

            result = await graph_service.create_mail_folder(
                mock_access_token, folder_name, parent_folder_id
            )

            assert result["displayName"] == "Voice Messages"
            assert result["parentFolderId"] == "inbox"
            expected_body = {"displayName": folder_name, "parentFolderId": parent_folder_id}
            mock_request.assert_called_once_with(
                "POST", "/me/mailFolders", mock_access_token, json=expected_body
            )

    @pytest.mark.asyncio
    async def test_create_mail_folder_conflict(self, graph_service, mock_access_token):
        """Test mail folder creation with conflict (folder already exists)."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 409
            mock_response.json.return_value = {"error": {"code": "FolderExists"}}
            mock_request.return_value = mock_response

            with pytest.raises(ValidationError):
                await graph_service.create_mail_folder(
                    mock_access_token, "Inbox", "msgfolderroot"
                )

    @pytest.mark.asyncio
    async def test_update_mail_folder_success(self, graph_service, mock_access_token):
        """Test successful mail folder update."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            updated_folder = GRAPH_API_RESPONSES["created_folder"].copy()
            updated_folder["displayName"] = "Updated Voice Messages"
            mock_response.json.return_value = updated_folder
            mock_request.return_value = mock_response

            folder_id = "voice-folder-id"
            new_name = "Updated Voice Messages"

            result = await graph_service.update_mail_folder(
                mock_access_token, folder_id, display_name=new_name
            )

            assert result["displayName"] == new_name
            expected_body = {"displayName": new_name}
            mock_request.assert_called_once_with(
                "PATCH", f"/me/mailFolders/{folder_id}", mock_access_token, json=expected_body
            )

    @pytest.mark.asyncio
    async def test_delete_mail_folder_success(self, graph_service, mock_access_token):
        """Test successful mail folder deletion."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 204
            mock_request.return_value = mock_response

            folder_id = "voice-folder-id"
            
            result = await graph_service.delete_mail_folder(mock_access_token, folder_id)

            assert result is True
            mock_request.assert_called_once_with(
                "DELETE", f"/me/mailFolders/{folder_id}", mock_access_token
            )

    # ==========================================================================
    # MESSAGE TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_messages_success(self, graph_service, mock_access_token):
        """Test successful messages retrieval."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["messages"]
            mock_request.return_value = mock_response

            result = await graph_service.get_messages(mock_access_token)

            assert "value" in result
            assert len(result["value"]) == 1
            message = result["value"][0]
            assert message["id"] == "message-id-1"
            assert message["subject"] == "Important Meeting Follow-up"
            mock_request.assert_called_once_with("GET", "/me/messages", mock_access_token, params=None)

    @pytest.mark.asyncio
    async def test_get_messages_with_folder_filter(self, graph_service, mock_access_token):
        """Test messages retrieval with folder filter."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["messages"]
            mock_request.return_value = mock_response

            folder_id = "inbox"
            result = await graph_service.get_messages(mock_access_token, folder_id=folder_id)

            assert "value" in result
            expected_endpoint = f"/me/mailFolders/{folder_id}/messages"
            mock_request.assert_called_once_with("GET", expected_endpoint, mock_access_token, params=None)

    @pytest.mark.asyncio
    async def test_get_messages_with_pagination(self, graph_service, mock_access_token):
        """Test messages retrieval with pagination parameters."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["messages"]
            mock_request.return_value = mock_response

            top = 10
            skip = 20
            result = await graph_service.get_messages(
                mock_access_token, top=top, skip=skip
            )

            assert "value" in result
            expected_params = {"$top": top, "$skip": skip}
            mock_request.assert_called_once_with(
                "GET", "/me/messages", mock_access_token, params=expected_params
            )

    @pytest.mark.asyncio
    async def test_get_message_by_id_success(self, graph_service, mock_access_token):
        """Test successful single message retrieval."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            message_data = GRAPH_API_RESPONSES["messages"]["value"][0]
            mock_response.json.return_value = message_data
            mock_request.return_value = mock_response

            message_id = "message-id-1"
            result = await graph_service.get_message(mock_access_token, message_id)

            assert result["id"] == message_id
            assert result["subject"] == "Important Meeting Follow-up"
            mock_request.assert_called_once_with(
                "GET", f"/me/messages/{message_id}", mock_access_token
            )

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, graph_service, mock_access_token):
        """Test message retrieval with non-existent message ID."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.json.return_value = ERROR_RESPONSES["not_found"]
            mock_request.return_value = mock_response

            with pytest.raises(ValidationError):
                await graph_service.get_message(mock_access_token, "non-existent-id")

    @pytest.mark.asyncio
    async def test_search_messages_success(self, graph_service, mock_access_token):
        """Test successful message search."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["search_results"]
            mock_request.return_value = mock_response

            search_query = "voice message"
            result = await graph_service.search_messages(mock_access_token, search_query)

            assert "value" in result
            assert len(result["value"]) == 1
            expected_params = {"$search": f'"{search_query}"'}
            mock_request.assert_called_once_with(
                "GET", "/me/messages", mock_access_token, params=expected_params
            )

    @pytest.mark.asyncio
    async def test_move_message_success(self, graph_service, mock_access_token):
        """Test successful message move operation."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["moved_message"]
            mock_request.return_value = mock_response

            message_id = "message-id-1"
            destination_folder_id = "voice-folder-id"

            result = await graph_service.move_message(
                mock_access_token, message_id, destination_folder_id
            )

            assert result["parentFolderId"] == destination_folder_id
            expected_body = {"destinationId": destination_folder_id}
            mock_request.assert_called_once_with(
                "POST", f"/me/messages/{message_id}/move", mock_access_token, json=expected_body
            )

    @pytest.mark.asyncio
    async def test_update_message_read_status(self, graph_service, mock_access_token):
        """Test message read status update."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            updated_message = GRAPH_API_RESPONSES["messages"]["value"][0].copy()
            updated_message["isRead"] = True
            mock_response.json.return_value = updated_message
            mock_request.return_value = mock_response

            message_id = "message-id-1"

            result = await graph_service.update_message(
                mock_access_token, message_id, is_read=True
            )

            assert result["isRead"] is True
            expected_body = {"isRead": True}
            mock_request.assert_called_once_with(
                "PATCH", f"/me/messages/{message_id}", mock_access_token, json=expected_body
            )

    # ==========================================================================
    # ATTACHMENT TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_attachments_success(self, graph_service, mock_access_token):
        """Test successful attachments retrieval."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = GRAPH_API_RESPONSES["attachments"]
            mock_request.return_value = mock_response

            message_id = "message-id-1"
            result = await graph_service.get_attachments(mock_access_token, message_id)

            assert "value" in result
            assert len(result["value"]) == 1
            attachment = result["value"][0]
            assert attachment["name"] == "voice-recording.wav"
            assert attachment["contentType"] == "audio/wav"
            mock_request.assert_called_once_with(
                "GET", f"/me/messages/{message_id}/attachments", mock_access_token
            )

    @pytest.mark.asyncio
    async def test_get_attachment_content_success(self, graph_service, mock_access_token):
        """Test successful attachment content retrieval."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            attachment_data = GRAPH_API_RESPONSES["attachments"]["value"][0]
            mock_response.json.return_value = attachment_data
            mock_request.return_value = mock_response

            message_id = "message-id-1"
            attachment_id = "attachment-id-1"

            result = await graph_service.get_attachment(
                mock_access_token, message_id, attachment_id
            )

            assert result["contentType"] == "audio/wav"
            assert "contentBytes" in result
            mock_request.assert_called_once_with(
                "GET", f"/me/messages/{message_id}/attachments/{attachment_id}", 
                mock_access_token
            )

    @pytest.mark.asyncio
    async def test_download_attachment_content(self, graph_service, mock_access_token):
        """Test attachment content download."""
        import base64
        
        with patch.object(graph_service, 'get_attachment') as mock_get_attachment:
            # Mock base64 encoded content
            test_content = b"test audio content"
            encoded_content = base64.b64encode(test_content).decode()
            
            mock_get_attachment.return_value = {
                "contentBytes": encoded_content,
                "contentType": "audio/wav"
            }

            message_id = "message-id-1"
            attachment_id = "attachment-id-1"

            result = await graph_service.download_attachment_content(
                mock_access_token, message_id, attachment_id
            )

            assert result == test_content
            mock_get_attachment.assert_called_once_with(
                mock_access_token, message_id, attachment_id
            )

    # ==========================================================================
    # PAGINATION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_all_pages_messages(self, graph_service, mock_access_token):
        """Test retrieving all pages of messages."""
        # First page response
        first_page = {
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=10",
            "value": [{"id": "msg-1", "subject": "Message 1"}]
        }
        
        # Second page response (no next link = last page)
        second_page = {
            "value": [{"id": "msg-2", "subject": "Message 2"}]
        }

        with patch.object(graph_service, '_make_graph_request') as mock_request:
            # Mock two successive calls
            first_response = Mock()
            first_response.status_code = 200
            first_response.json.return_value = first_page
            
            second_response = Mock()
            second_response.status_code = 200
            second_response.json.return_value = second_page
            
            mock_request.side_effect = [first_response, second_response]

            result = await graph_service.get_all_messages(mock_access_token)

            assert len(result) == 2
            assert result[0]["id"] == "msg-1"
            assert result[1]["id"] == "msg-2"
            assert mock_request.call_count == 2

    # ==========================================================================
    # RATE LIMITING AND RETRY TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_handle_rate_limiting(self, graph_service, mock_access_token):
        """Test handling of rate limiting (429 status)."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            # First call returns rate limit, second succeeds
            rate_limit_response = Mock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {"Retry-After": "1"}
            rate_limit_response.json.return_value = ERROR_RESPONSES["rate_limited"]

            success_response = Mock()
            success_response.status_code = 200
            success_response.json.return_value = GRAPH_API_RESPONSES["user_profile"]

            mock_request.side_effect = [rate_limit_response, success_response]

            with patch('asyncio.sleep') as mock_sleep:
                result = await graph_service.get_user_profile(mock_access_token)

                assert result["id"] == "12345678-1234-1234-1234-123456789012"
                mock_sleep.assert_called_once_with(1)  # Retry-After value
                assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, graph_service, mock_access_token):
        """Test retry logic on server errors (5xx)."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            # First call fails with server error, second succeeds
            error_response = Mock()
            error_response.status_code = 503
            error_response.json.return_value = {"error": {"message": "Service unavailable"}}

            success_response = Mock()
            success_response.status_code = 200
            success_response.json.return_value = GRAPH_API_RESPONSES["user_profile"]

            mock_request.side_effect = [error_response, success_response]

            with patch('asyncio.sleep') as mock_sleep:
                result = await graph_service.get_user_profile(mock_access_token)

                assert result["id"] == "12345678-1234-1234-1234-123456789012"
                mock_sleep.assert_called_once()
                assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retry_exceeded(self, graph_service, mock_access_token):
        """Test behavior when max retries are exceeded."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            # Always return server error
            error_response = Mock()
            error_response.status_code = 503
            error_response.json.return_value = {"error": {"message": "Service unavailable"}}
            mock_request.return_value = error_response

            with patch('asyncio.sleep'):
                with pytest.raises(AuthenticationError):
                    await graph_service.get_user_profile(mock_access_token)

                # Should retry maximum number of times
                assert mock_request.call_count > 1

    # ==========================================================================
    # BATCH OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_batch_request_success(self, graph_service, mock_access_token):
        """Test successful batch request."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            batch_response = {
                "responses": [
                    {
                        "id": "1",
                        "status": 200,
                        "body": GRAPH_API_RESPONSES["user_profile"]
                    },
                    {
                        "id": "2", 
                        "status": 200,
                        "body": GRAPH_API_RESPONSES["mail_folders"]
                    }
                ]
            }
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = batch_response
            mock_request.return_value = mock_response

            requests = [
                {"id": "1", "method": "GET", "url": "/me"},
                {"id": "2", "method": "GET", "url": "/me/mailFolders"}
            ]

            result = await graph_service.batch_request(mock_access_token, requests)

            assert len(result["responses"]) == 2
            assert result["responses"][0]["status"] == 200
            assert result["responses"][1]["status"] == 200

    # ==========================================================================
    # ERROR HANDLING TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_handle_forbidden_error(self, graph_service, mock_access_token):
        """Test handling of forbidden errors (403)."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.json.return_value = ERROR_RESPONSES["forbidden"]
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError):
                await graph_service.get_user_profile(mock_access_token)

    @pytest.mark.asyncio
    async def test_handle_network_timeout(self, graph_service, mock_access_token):
        """Test handling of network timeouts."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(AuthenticationError):
                await graph_service.get_user_profile(mock_access_token)

    @pytest.mark.asyncio
    async def test_handle_connection_error(self, graph_service, mock_access_token):
        """Test handling of connection errors."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(AuthenticationError):
                await graph_service.get_user_profile(mock_access_token)

    @pytest.mark.asyncio
    async def test_handle_invalid_json_response(self, graph_service, mock_access_token):
        """Test handling of invalid JSON responses."""
        with patch.object(graph_service, '_make_graph_request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_request.return_value = mock_response

            with pytest.raises(AuthenticationError):
                await graph_service.get_user_profile(mock_access_token)

    # ==========================================================================
    # UTILITY METHOD TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_make_graph_request_with_headers(self, graph_service, mock_access_token):
        """Test _make_graph_request with custom headers."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"test": "data"}
            
            mock_client.return_value.__aenter__.return_value.request.return_value = mock_response

            custom_headers = {"X-Custom-Header": "test-value"}
            
            result = await graph_service._make_graph_request(
                "GET", "/test", mock_access_token, headers=custom_headers
            )

            assert result.status_code == 200
            # Verify custom headers were included
            call_args = mock_client.return_value.__aenter__.return_value.request.call_args
            assert "headers" in call_args.kwargs
            headers = call_args.kwargs["headers"]
            assert "X-Custom-Header" in headers
            assert "Authorization" in headers

    def test_build_graph_url(self, graph_service):
        """Test URL building utility method."""
        endpoint = "/me/messages"
        expected_url = f"https://graph.microsoft.com/v1.0{endpoint}"
        
        result = graph_service._build_graph_url(endpoint)
        
        assert result == expected_url

    def test_build_graph_url_with_leading_slash(self, graph_service):
        """Test URL building with endpoint already having leading slash."""
        endpoint = "/me/mailFolders"
        expected_url = f"https://graph.microsoft.com/v1.0{endpoint}"
        
        result = graph_service._build_graph_url(endpoint)
        
        assert result == expected_url

    def test_prepare_auth_headers(self, graph_service, mock_access_token):
        """Test authorization headers preparation."""
        result = graph_service._prepare_auth_headers(mock_access_token)
        
        assert "Authorization" in result
        assert result["Authorization"] == f"Bearer {mock_access_token}"
        assert "Content-Type" in result
        assert result["Content-Type"] == "application/json"