"""
End-to-end workflow integration tests.

Tests complete user journeys and workflows including:
- Complete user authentication and mail access workflow
- Voice attachment discovery, storage, and management workflow
- Shared mailbox collaboration and management workflow
- Cross-system data consistency and error recovery
- Performance characteristics of complete workflows
- Real-world usage scenarios
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, AsyncMock
import uuid

from tests.integration.utils import (
    IntegrationAPIClient, 
    ResponseAssertions, 
    DatabaseAssertions,
    TestWorkflows,
    time_operation
)


class TestEndToEndWorkflows:
    """End-to-end workflow integration tests."""

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
    # COMPLETE USER JOURNEY TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_user_journey_authentication_to_mail_access(self, test_workflows, override_auth_dependency):
        """Test complete journey: login → access mail → read messages → logout."""
        
        with patch('app.services.OAuthService.OAuthService') as mock_oauth_service:
            with patch('app.services.MailService.MailService') as mock_mail_service:
                # Setup comprehensive mocks for the entire workflow
                
                # 1. Authentication setup
                mock_oauth_instance = mock_oauth_service.return_value
                mock_oauth_instance.initiate_login.return_value = {
                    "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=e2e-test"
                }
                
                mock_oauth_instance.handle_callback.return_value = {
                    "access_token": "e2e-access-token",
                    "refresh_token": "e2e-refresh-token",
                    "user_info": {
                        "id": "e2e-user-journey",
                        "email": "e2e@example.com",
                        "display_name": "E2E Test User",
                        "given_name": "E2E",
                        "surname": "User"
                    },
                    "expires_in": 3600,
                    "token_type": "Bearer"
                }
                
                mock_oauth_instance.logout.return_value = True
                
                # 2. Mail service setup
                mock_mail_instance = mock_mail_service.return_value
                
                # Mock folder listing
                mock_mail_instance.list_mail_folders.return_value = [
                    {
                        "id": "inbox", 
                        "displayName": "Inbox",
                        "unreadItemCount": 3,
                        "totalItemCount": 25
                    },
                    {
                        "id": "sent", 
                        "displayName": "Sent Items", 
                        "unreadItemCount": 0,
                        "totalItemCount": 10
                    }
                ]
                
                # Mock message retrieval
                mock_mail_instance.get_inbox_messages.return_value = {
                    "value": [
                        {
                            "id": "e2e-msg-001",
                            "subject": "Welcome E2E User",
                            "from": {"emailAddress": {"address": "welcome@example.com", "name": "Welcome Bot"}},
                            "receivedDateTime": "2024-01-15T10:00:00Z",
                            "isRead": False,
                            "hasAttachments": False
                        },
                        {
                            "id": "e2e-msg-002", 
                            "subject": "Important Voice Message",
                            "from": {"emailAddress": {"address": "caller@business.com", "name": "Important Caller"}},
                            "receivedDateTime": "2024-01-15T11:30:00Z",
                            "isRead": False,
                            "hasAttachments": True
                        }
                    ]
                }
                
                # Mock message marking as read
                mock_mail_instance.mark_message_as_read.return_value = True
                
                # Execute complete workflow
                async with time_operation("complete_user_journey"):
                    
                    # Step 1: Authentication flow
                    login_response, callback_response, token_data = await test_workflows.complete_authentication_flow()
                    
                    # Verify authentication
                    assert login_response.status_code == 302
                    ResponseAssertions.assert_success_response(callback_response)
                    assert token_data["access_token"] == "e2e-access-token"
                    assert token_data["user_info"]["email"] == "e2e@example.com"
                    
                    # Step 2: Access mail folders
                    folders_response = await test_workflows.api.get_mail_folders()
                    ResponseAssertions.assert_success_response(folders_response)
                    
                    folders_data = folders_response.json()
                    assert len(folders_data) == 2
                    assert folders_data[0]["displayName"] == "Inbox"
                    
                    # Step 3: Read inbox messages
                    messages_response = await test_workflows.api.get_messages()
                    ResponseAssertions.assert_success_response(messages_response)
                    
                    messages_data = messages_response.json()
                    assert len(messages_data["value"]) == 2
                    
                    # Step 4: Process individual messages
                    for message in messages_data["value"]:
                        # Mark message as read
                        update_response = await test_workflows.api.update_message(
                            message["id"], 
                            is_read=True
                        )
                        ResponseAssertions.assert_success_response(update_response)
                    
                    # Step 5: Logout
                    logout_response = await test_workflows.api.auth_logout()
                    ResponseAssertions.assert_success_response(logout_response)
                    
                    logout_data = logout_response.json()
                    assert logout_data["success"] is True
                
                # Verify user was persisted in database
                await test_workflows.db.assert_user_exists(
                    "e2e-user-journey",
                    email="e2e@example.com",
                    display_name="E2E Test User"
                )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_voice_attachment_complete_workflow(self, test_workflows, override_auth_dependency):
        """Test complete voice attachment workflow: discover → store → retrieve → organize → delete."""
        
        with patch('app.services.MailService.MailService') as mock_mail_service:
            with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
                with patch('app.services.VoiceAttachmentService.BlobServiceClient') as mock_blob_client:
                    
                    # Setup mocks for voice attachment workflow
                    mock_mail_instance = mock_mail_service.return_value
                    mock_voice_instance = mock_voice_service.return_value
                    
                    # Mock voice message discovery
                    mock_voice_messages = [
                        Mock(
                            id="voice-e2e-001",
                            subject="Client Voicemail",
                            has_attachments=True,
                            received_datetime=datetime.utcnow()
                        ),
                        Mock(
                            id="voice-e2e-002", 
                            subject="Meeting Recording",
                            has_attachments=True,
                            received_datetime=datetime.utcnow() - timedelta(hours=1)
                        )
                    ]
                    
                    mock_voice_attachments = [
                        {
                            "attachment_id": "voice-att-e2e-001",
                            "message_id": "voice-e2e-001",
                            "file_name": "client-voicemail.wav", 
                            "content_type": "audio/wav",
                            "size_bytes": 2048000,
                            "blob_name": "voice-e2e-001.wav"
                        },
                        {
                            "attachment_id": "voice-att-e2e-002",
                            "message_id": "voice-e2e-002",
                            "file_name": "meeting-recording.mp3",
                            "content_type": "audio/mpeg", 
                            "size_bytes": 5120000,
                            "blob_name": "voice-e2e-002.mp3"
                        }
                    ]
                    
                    # Configure voice service mocks
                    mock_voice_instance.find_all_voice_messages.return_value = mock_voice_messages
                    mock_voice_instance.extract_voice_attachments_from_message.return_value = mock_voice_attachments
                    mock_voice_instance.store_voice_attachment_in_blob.return_value = "stored-blob-name.wav"
                    mock_voice_instance.download_voice_attachment_from_blob.return_value = (
                        b"mock audio data" * 1000, 
                        {"content_type": "audio/wav", "filename": "downloaded.wav"}
                    )
                    mock_voice_instance.organize_voice_messages.return_value = {
                        "success": True,
                        "messages_moved": 2,
                        "folder_created": True,
                        "target_folder": "Voice Messages"
                    }
                    mock_voice_instance.delete_stored_voice_attachment.return_value = True
                    
                    # Configure blob service mock
                    mock_blob_service = Mock()
                    mock_blob_client.return_value = mock_blob_service
                    
                    # Execute complete voice attachment workflow
                    async with time_operation("voice_attachment_workflow"):
                        
                        # Step 1: Discover voice messages
                        voice_messages_response = await test_workflows.api.get_voice_messages()
                        ResponseAssertions.assert_success_response(voice_messages_response)
                        
                        # Step 2: Get voice attachments
                        voice_attachments_response = await test_workflows.api.get_voice_attachments()
                        ResponseAssertions.assert_success_response(voice_attachments_response)
                        
                        voice_attachments = voice_attachments_response.json()
                        assert len(voice_attachments) == 2
                        
                        # Step 3: Store voice attachments in blob storage
                        for attachment in voice_attachments:
                            store_response = await test_workflows.api.client.post(
                                f"/api/v1/mail/voice-attachments/store/{attachment['message_id']}/{attachment['attachment_id']}"
                            )
                            ResponseAssertions.assert_success_response(store_response)
                            
                            store_data = store_response.json()
                            assert store_data["success"] is True
                            assert "blob_name" in store_data
                        
                        # Step 4: List stored attachments
                        stored_response = await test_workflows.api.client.get("/api/v1/mail/voice-attachments/stored")
                        ResponseAssertions.assert_success_response(stored_response)
                        
                        # Step 5: Download stored attachment
                        blob_name = "test-blob.wav"
                        download_response = await test_workflows.api.client.get(
                            f"/api/v1/mail/voice-attachments/blob/{blob_name}"
                        )
                        assert download_response.status_code == 200
                        assert len(download_response.content) > 0
                        
                        # Step 6: Organize voice messages
                        organize_response = await test_workflows.api.organize_voice_messages("Voice Messages")
                        ResponseAssertions.assert_success_response(organize_response)
                        
                        organize_data = organize_response.json()
                        assert organize_data["success"] is True
                        assert organize_data["messages_moved"] == 2
                        
                        # Step 7: Get voice statistics
                        stats_response = await test_workflows.api.client.get("/api/v1/mail/voice-statistics")
                        ResponseAssertions.assert_success_response(stats_response)
                        
                        # Step 8: Cleanup - delete stored attachment
                        delete_response = await test_workflows.api.client.delete(
                            f"/api/v1/mail/voice-attachments/blob/{blob_name}"
                        )
                        ResponseAssertions.assert_success_response(delete_response)
                        
                        delete_data = delete_response.json()
                        assert delete_data["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shared_mailbox_collaboration_workflow(self, test_workflows, override_auth_dependency):
        """Test complete shared mailbox collaboration workflow."""
        
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_shared_service:
            
            # Setup shared mailbox collaboration scenario
            mock_shared_instance = mock_shared_service.return_value
            
            # Mock accessible shared mailboxes
            mock_shared_instance.get_accessible_shared_mailboxes.return_value = {
                "value": [
                    {
                        "id": "collab-support-mb",
                        "emailAddress": "support@collaboration.com",
                        "displayName": "Customer Support Team",
                        "accessLevel": "full",
                        "permissions": ["read", "write", "send"],
                        "messageCount": 45,
                        "unreadCount": 8
                    },
                    {
                        "id": "collab-sales-mb", 
                        "emailAddress": "sales@collaboration.com",
                        "displayName": "Sales Team",
                        "accessLevel": "read",
                        "permissions": ["read"],
                        "messageCount": 120,
                        "unreadCount": 23
                    }
                ]
            }
            
            # Mock shared mailbox details
            mock_shared_instance.get_shared_mailbox_details.return_value = {
                "id": "collab-support-mb",
                "emailAddress": "support@collaboration.com",
                "displayName": "Customer Support Team",
                "accessLevel": "full",
                "permissions": ["read", "write", "send"],
                "messageCount": 45,
                "unreadCount": 8,
                "folders": [
                    {"id": "inbox", "displayName": "Inbox", "messageCount": 35},
                    {"id": "voice-messages", "displayName": "Voice Messages", "messageCount": 10}
                ]
            }
            
            # Mock messages from shared mailbox
            mock_shared_instance.get_shared_mailbox_messages.return_value = {
                "value": [
                    {
                        "id": "collab-msg-001",
                        "subject": "Customer Support Request",
                        "from": {"emailAddress": {"address": "customer@example.com", "name": "Customer"}},
                        "receivedDateTime": "2024-01-15T09:00:00Z",
                        "isRead": False,
                        "hasAttachments": True
                    },
                    {
                        "id": "collab-msg-002",
                        "subject": "Follow-up Required",
                        "from": {"emailAddress": {"address": "followup@client.com", "name": "Client"}},
                        "receivedDateTime": "2024-01-15T10:30:00Z", 
                        "isRead": False,
                        "hasAttachments": False
                    }
                ]
            }
            
            # Mock shared mailbox operations
            mock_shared_instance.send_shared_mailbox_message.return_value = {
                "success": True,
                "messageId": "collab-sent-001",
                "sentDateTime": "2024-01-15T12:00:00Z"
            }
            
            mock_shared_instance.organize_shared_mailbox_messages.return_value = {
                "success": True,
                "messagesOrganized": 5,
                "foldersCreated": 0,
                "targetFolder": "Processed"
            }
            
            # Mock cross-mailbox search
            mock_shared_instance.search_shared_mailboxes.return_value = {
                "query": "urgent",
                "totalResults": 8,
                "searchedMailboxes": 2,
                "results": [
                    {
                        "mailbox": "support@collaboration.com",
                        "messages": [{"id": "urgent-001", "subject": "Urgent Support"}],
                        "matchCount": 5
                    },
                    {
                        "mailbox": "sales@collaboration.com", 
                        "messages": [{"id": "urgent-002", "subject": "Urgent Sale"}],
                        "matchCount": 3
                    }
                ]
            }
            
            # Execute complete shared mailbox collaboration workflow
            async with time_operation("shared_mailbox_collaboration"):
                
                # Step 1: Discover accessible shared mailboxes
                mailboxes_response = await test_workflows.api.get_shared_mailboxes()
                ResponseAssertions.assert_success_response(mailboxes_response)
                
                mailboxes_data = mailboxes_response.json()
                assert len(mailboxes_data["value"]) == 2
                
                support_mailbox = mailboxes_data["value"][0]
                assert support_mailbox["emailAddress"] == "support@collaboration.com"
                assert support_mailbox["accessLevel"] == "full"
                
                # Step 2: Get details for primary mailbox
                details_response = await test_workflows.api.get_shared_mailbox_details(
                    "support@collaboration.com"
                )
                ResponseAssertions.assert_success_response(details_response)
                
                details_data = details_response.json()
                assert len(details_data["folders"]) == 2
                
                # Step 3: Access messages from shared mailbox
                messages_response = await test_workflows.api.get_shared_mailbox_messages(
                    "support@collaboration.com",
                    folder_id="inbox"
                )
                ResponseAssertions.assert_success_response(messages_response)
                
                messages_data = messages_response.json()
                assert len(messages_data["value"]) == 2
                
                # Step 4: Send response from shared mailbox
                send_request = {
                    "to": [{"emailAddress": {"address": "customer@example.com", "name": "Customer"}}],
                    "subject": "Re: Customer Support Request",
                    "body": {"content": "Thank you for contacting support.", "contentType": "text"}
                }
                
                send_response = await test_workflows.api.client.post(
                    "/api/v1/shared-mailboxes/support@collaboration.com/send",
                    json=send_request
                )
                ResponseAssertions.assert_success_response(send_response)
                
                send_data = send_response.json()
                assert send_data["success"] is True
                
                # Step 5: Organize messages in shared mailbox
                organize_request = {
                    "targetFolderName": "Processed",
                    "createFolder": True,
                    "messageType": "resolved",
                    "preserveReadStatus": True
                }
                
                organize_response = await test_workflows.api.client.post(
                    "/api/v1/shared-mailboxes/support@collaboration.com/organize",
                    json=organize_request
                )
                ResponseAssertions.assert_success_response(organize_response)
                
                organize_data = organize_response.json()
                assert organize_data["success"] is True
                assert organize_data["messagesOrganized"] == 5
                
                # Step 6: Search across multiple shared mailboxes
                search_request = {
                    "query": "urgent",
                    "mailboxes": ["support@collaboration.com", "sales@collaboration.com"],
                    "maxResults": 20
                }
                
                search_response = await test_workflows.api.client.post(
                    "/api/v1/shared-mailboxes/search",
                    json=search_request
                )
                ResponseAssertions.assert_success_response(search_response)
                
                search_data = search_response.json()
                assert search_data["totalResults"] == 8
                assert len(search_data["results"]) == 2

    # =========================================================================
    # ERROR RECOVERY AND RESILIENCE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_resilience_with_partial_failures(self, test_workflows, override_auth_dependency):
        """Test workflow resilience when some operations fail."""
        
        with patch('app.services.MailService.MailService') as mock_mail_service:
            with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
                
                # Setup scenario with partial failures
                mock_mail_instance = mock_mail_service.return_value
                mock_voice_instance = mock_voice_service.return_value
                
                # Mock successful folder listing
                mock_mail_instance.list_mail_folders.return_value = [
                    {"id": "inbox", "displayName": "Inbox"},
                    {"id": "sent", "displayName": "Sent Items"}
                ]
                
                # Mock message retrieval that fails initially then succeeds
                call_count = 0
                def mock_get_messages(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        raise ConnectionError("Temporary service unavailable")
                    return {
                        "value": [
                            {
                                "id": "resilient-msg-001",
                                "subject": "Resilience Test",
                                "hasAttachments": True,
                                "isRead": False
                            }
                        ]
                    }
                
                mock_mail_instance.get_inbox_messages.side_effect = mock_get_messages
                
                # Mock voice service with intermittent failures
                voice_call_count = 0
                def mock_voice_operations(*args, **kwargs):
                    nonlocal voice_call_count
                    voice_call_count += 1
                    if voice_call_count <= 2:  # First two calls fail
                        raise Exception("Voice service temporarily unavailable")
                    return [{"attachment_id": "voice-resilient-001", "file_name": "resilient.wav"}]
                
                mock_voice_instance.extract_voice_attachments_from_message.side_effect = mock_voice_operations
                
                # Test resilient workflow execution
                async with time_operation("resilient_workflow"):
                    
                    # Step 1: Get folders (should succeed)
                    folders_response = await test_workflows.api.get_mail_folders()
                    ResponseAssertions.assert_success_response(folders_response)
                    
                    # Step 2: Get messages (should fail first time)
                    try:
                        await test_workflows.api.get_messages()
                        pytest.fail("Expected first call to fail")
                    except Exception:
                        pass  # Expected failure
                    
                    # Step 3: Retry messages (should succeed)
                    messages_response = await test_workflows.api.get_messages()
                    ResponseAssertions.assert_success_response(messages_response)
                    
                    # Step 4: Try voice operations (will fail initially)
                    try:
                        await test_workflows.api.get_voice_attachments()
                        pytest.fail("Expected voice service to fail initially")
                    except Exception:
                        pass  # Expected failure
                    
                    # Step 5: Retry voice operations (will still fail)
                    try:
                        await test_workflows.api.get_voice_attachments()
                        pytest.fail("Expected voice service to fail again")
                    except Exception:
                        pass  # Expected failure
                    
                    # Step 6: Final retry (should succeed)
                    voice_response = await test_workflows.api.get_voice_attachments()
                    ResponseAssertions.assert_success_response(voice_response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_data_consistency_across_failures(self, test_workflows, db_assertions, override_auth_dependency):
        """Test data consistency when workflows are interrupted by failures."""
        
        with patch('app.services.OAuthService.OAuthService') as mock_oauth_service:
            with patch('app.services.MailService.MailService') as mock_mail_service:
                
                # Setup workflow that creates data then fails
                mock_oauth_instance = mock_oauth_service.return_value
                mock_oauth_instance.handle_callback.return_value = {
                    "access_token": "consistency-token",
                    "user_info": {
                        "id": "consistency-user",
                        "email": "consistency@example.com",
                        "display_name": "Consistency User"
                    }
                }
                
                # Mock mail service that fails after some operations
                mock_mail_instance = mock_mail_service.return_value
                mock_mail_instance.list_mail_folders.side_effect = Exception("Service failure after auth")
                
                # Test data consistency
                async with time_operation("data_consistency_test"):
                    
                    # Step 1: Complete authentication (creates user data)
                    login_response, callback_response, token_data = await test_workflows.complete_authentication_flow()
                    
                    # Verify user was created
                    await db_assertions.assert_user_exists(
                        "consistency-user",
                        email="consistency@example.com"
                    )
                    
                    # Step 2: Attempt mail operations (will fail)
                    try:
                        await test_workflows.api.get_mail_folders()
                        pytest.fail("Expected mail service to fail")
                    except Exception:
                        pass  # Expected failure
                    
                    # Step 3: Verify user data still exists despite failure
                    await db_assertions.assert_user_exists(
                        "consistency-user",
                        email="consistency@example.com"
                    )
                    
                    # Data consistency maintained even with partial workflow failure

    # =========================================================================
    # PERFORMANCE AND SCALABILITY TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_workflow_performance_under_load(self, test_workflows, override_auth_dependency):
        """Test workflow performance with concurrent execution."""
        
        with patch('app.services.MailService.MailService') as mock_mail_service:
            
            # Setup fast-responding mocks for performance testing
            mock_mail_instance = mock_mail_service.return_value
            mock_mail_instance.list_mail_folders.return_value = [
                {"id": "perf-inbox", "displayName": "Performance Inbox"}
            ]
            mock_mail_instance.get_inbox_messages.return_value = {
                "value": [{"id": f"perf-msg-{i}", "subject": f"Performance Test {i}"} for i in range(10)]
            }
            
            # Execute multiple concurrent workflows
            async def single_mail_workflow():
                folders_response = await test_workflows.api.get_mail_folders()
                messages_response = await test_workflows.api.get_messages(top=10)
                return (folders_response.status_code, messages_response.status_code)
            
            # Run multiple workflows concurrently
            num_concurrent = 5
            start_time = datetime.utcnow()
            
            results = await asyncio.gather(
                *[single_mail_workflow() for _ in range(num_concurrent)],
                return_exceptions=True
            )
            
            end_time = datetime.utcnow()
            total_time = (end_time - start_time).total_seconds()
            
            # Verify performance
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) == num_concurrent
            
            # All workflows should complete within reasonable time
            assert total_time < 10.0  # Under 10 seconds for 5 concurrent workflows
            
            # All workflows should succeed
            for result in successful_results:
                assert result == (200, 200)  # Both API calls successful

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_large_dataset_workflow_performance(self, test_workflows, override_auth_dependency):
        """Test workflow performance with large datasets."""
        
        with patch('app.services.MailService.MailService') as mock_mail_service:
            with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
                
                # Setup mocks with large datasets
                mock_mail_instance = mock_mail_service.return_value
                mock_voice_instance = mock_voice_service.return_value
                
                # Mock large message set
                large_message_set = {
                    "value": [
                        {
                            "id": f"large-msg-{i:04d}",
                            "subject": f"Large Dataset Message {i}",
                            "hasAttachments": i % 5 == 0,
                            "isRead": i % 3 == 0,
                            "from": {"emailAddress": {"address": f"sender{i}@example.com"}},
                            "receivedDateTime": f"2024-01-15T{(10 + i%14):02d}:00:00Z"
                        }
                        for i in range(100)  # 100 messages
                    ]
                }
                
                mock_mail_instance.get_inbox_messages.return_value = large_message_set
                
                # Mock large voice attachment set
                large_voice_set = [
                    {
                        "attachment_id": f"voice-large-{i:04d}",
                        "message_id": f"large-msg-{i*5:04d}",  # Every 5th message has voice
                        "file_name": f"voice{i}.wav",
                        "content_type": "audio/wav",
                        "size_bytes": 1024000 + (i * 50000)
                    }
                    for i in range(20)  # 20 voice attachments
                ]
                
                mock_voice_instance.extract_voice_attachments_from_message.return_value = large_voice_set
                mock_voice_instance.organize_voice_messages.return_value = {
                    "success": True,
                    "messages_moved": 20,
                    "processing_time_ms": 2500
                }
                
                # Test large dataset workflow
                async with time_operation("large_dataset_workflow"):
                    
                    # Step 1: Retrieve large message set (performance test)
                    start_time = datetime.utcnow()
                    messages_response = await test_workflows.api.get_messages(top=100)
                    messages_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    ResponseAssertions.assert_success_response(messages_response)
                    messages_data = messages_response.json()
                    assert len(messages_data["value"]) == 100
                    
                    # Should complete within reasonable time
                    assert messages_time < 5.0  # Under 5 seconds for 100 messages
                    
                    # Step 2: Process voice attachments (performance test)
                    start_time = datetime.utcnow()
                    voice_response = await test_workflows.api.get_voice_attachments(limit=50)
                    voice_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    ResponseAssertions.assert_success_response(voice_response)
                    voice_data = voice_response.json()
                    assert len(voice_data) == 20
                    
                    # Should complete within reasonable time
                    assert voice_time < 3.0  # Under 3 seconds for voice processing
                    
                    # Step 3: Organize large set of voice messages
                    start_time = datetime.utcnow()
                    organize_response = await test_workflows.api.organize_voice_messages("Large Dataset Voices")
                    organize_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    ResponseAssertions.assert_success_response(organize_response)
                    organize_data = organize_response.json()
                    assert organize_data["success"] is True
                    assert organize_data["messages_moved"] == 20
                    
                    # Should complete within reasonable time
                    assert organize_time < 4.0  # Under 4 seconds for organization

    # =========================================================================
    # REAL-WORLD SCENARIO TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_daily_email_processing_scenario(self, test_workflows, override_auth_dependency):
        """Test realistic daily email processing scenario."""
        
        with patch('app.services.MailService.MailService') as mock_mail_service:
            with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice_service:
                
                # Setup realistic daily email scenario
                mock_mail_instance = mock_mail_service.return_value
                mock_voice_instance = mock_voice_service.return_value
                
                # Morning: Check inbox
                morning_messages = {
                    "value": [
                        {
                            "id": "daily-001",
                            "subject": "Daily Report",
                            "importance": "normal",
                            "isRead": False,
                            "hasAttachments": True,
                            "receivedDateTime": "2024-01-15T08:30:00Z"
                        },
                        {
                            "id": "daily-002", 
                            "subject": "Client Voicemail",
                            "importance": "high",
                            "isRead": False,
                            "hasAttachments": True,
                            "receivedDateTime": "2024-01-15T09:15:00Z"
                        },
                        {
                            "id": "daily-003",
                            "subject": "Meeting Reminder", 
                            "importance": "normal",
                            "isRead": False,
                            "hasAttachments": False,
                            "receivedDateTime": "2024-01-15T09:45:00Z"
                        }
                    ]
                }
                
                mock_mail_instance.get_inbox_messages.return_value = morning_messages
                mock_mail_instance.mark_message_as_read.return_value = True
                mock_mail_instance.move_message_to_folder.return_value = True
                
                # Voice messages processing
                mock_voice_instance.extract_voice_attachments_from_message.return_value = [
                    {
                        "attachment_id": "daily-voice-001",
                        "message_id": "daily-002",
                        "file_name": "client-voicemail.wav",
                        "content_type": "audio/wav",
                        "size_bytes": 3072000
                    }
                ]
                
                mock_voice_instance.organize_voice_messages.return_value = {
                    "success": True,
                    "messages_moved": 1,
                    "folder_created": False
                }
                
                # Execute daily processing workflow
                async with time_operation("daily_email_processing"):
                    
                    # Morning routine: Check new messages
                    messages_response = await test_workflows.api.get_messages()
                    ResponseAssertions.assert_success_response(messages_response)
                    
                    messages_data = messages_response.json()
                    assert len(messages_data["value"]) == 3
                    
                    # Process high-priority messages first
                    high_priority_messages = [
                        msg for msg in messages_data["value"] 
                        if msg.get("importance") == "high"
                    ]
                    assert len(high_priority_messages) == 1
                    
                    # Handle voice message
                    voice_message = high_priority_messages[0]
                    voice_attachments_response = await test_workflows.api.client.get(
                        f"/api/v1/mail/messages/{voice_message['id']}/voice-attachments"
                    )
                    ResponseAssertions.assert_success_response(voice_attachments_response)
                    
                    # Mark important messages as read
                    for msg in high_priority_messages:
                        update_response = await test_workflows.api.update_message(
                            msg["id"], 
                            is_read=True
                        )
                        ResponseAssertions.assert_success_response(update_response)
                    
                    # Organize voice messages
                    organize_response = await test_workflows.api.organize_voice_messages("Voice Messages")
                    ResponseAssertions.assert_success_response(organize_response)
                    
                    organize_data = organize_response.json()
                    assert organize_data["success"] is True
                    assert organize_data["messages_moved"] == 1
                    
                    # Move processed messages to appropriate folders
                    for msg in messages_data["value"]:
                        if msg["subject"] == "Daily Report":
                            move_response = await test_workflows.api.move_message(
                                msg["id"], 
                                "reports"
                            )
                            ResponseAssertions.assert_success_response(move_response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_team_collaboration_scenario(self, test_workflows, override_auth_dependency):
        """Test realistic team collaboration scenario with shared mailboxes."""
        
        with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_shared_service:
            
            # Setup team collaboration scenario
            mock_shared_instance = mock_shared_service.return_value
            
            # Team has access to multiple shared mailboxes
            mock_shared_instance.get_accessible_shared_mailboxes.return_value = {
                "value": [
                    {
                        "id": "team-support",
                        "emailAddress": "support@team.com",
                        "displayName": "Customer Support",
                        "accessLevel": "full",
                        "unreadCount": 12
                    },
                    {
                        "id": "team-projects",
                        "emailAddress": "projects@team.com", 
                        "displayName": "Project Communications",
                        "accessLevel": "read",
                        "unreadCount": 5
                    }
                ]
            }
            
            # Mock collaborative work on support tickets
            mock_shared_instance.get_shared_mailbox_messages.return_value = {
                "value": [
                    {
                        "id": "collab-ticket-001",
                        "subject": "Urgent: System Down",
                        "importance": "high",
                        "isRead": False,
                        "from": {"emailAddress": {"address": "crisis@client.com"}},
                        "receivedDateTime": "2024-01-15T14:00:00Z"
                    },
                    {
                        "id": "collab-ticket-002",
                        "subject": "Feature Request Discussion",
                        "importance": "normal", 
                        "isRead": False,
                        "from": {"emailAddress": {"address": "product@client.com"}},
                        "receivedDateTime": "2024-01-15T13:30:00Z"
                    }
                ]
            }
            
            # Mock team response coordination
            mock_shared_instance.send_shared_mailbox_message.return_value = {
                "success": True,
                "messageId": "team-response-001"
            }
            
            # Mock cross-mailbox search for related issues
            mock_shared_instance.search_shared_mailboxes.return_value = {
                "query": "system down", 
                "totalResults": 3,
                "results": [
                    {
                        "mailbox": "support@team.com",
                        "messages": [{"id": "related-001", "subject": "Previous System Issue"}],
                        "matchCount": 2
                    }
                ]
            }
            
            # Execute team collaboration workflow
            async with time_operation("team_collaboration"):
                
                # Step 1: Team member checks shared mailboxes
                mailboxes_response = await test_workflows.api.get_shared_mailboxes()
                ResponseAssertions.assert_success_response(mailboxes_response)
                
                mailboxes_data = mailboxes_response.json()
                support_mailbox = mailboxes_data["value"][0]
                assert support_mailbox["unreadCount"] == 12
                
                # Step 2: Check urgent items in support mailbox
                support_messages_response = await test_workflows.api.get_shared_mailbox_messages(
                    "support@team.com",
                    has_attachments=None
                )
                ResponseAssertions.assert_success_response(support_messages_response)
                
                messages_data = support_messages_response.json()
                urgent_messages = [
                    msg for msg in messages_data["value"]
                    if msg.get("importance") == "high"
                ]
                assert len(urgent_messages) == 1
                
                # Step 3: Search for related previous issues
                search_request = {
                    "query": "system down",
                    "mailboxes": ["support@team.com"],
                    "maxResults": 10
                }
                
                search_response = await test_workflows.api.client.post(
                    "/api/v1/shared-mailboxes/search",
                    json=search_request
                )
                ResponseAssertions.assert_success_response(search_response)
                
                search_data = search_response.json()
                assert search_data["totalResults"] == 3
                
                # Step 4: Coordinate team response
                urgent_message = urgent_messages[0] 
                team_response = {
                    "to": [{"emailAddress": {"address": "crisis@client.com"}}],
                    "subject": f"Re: {urgent_message['subject']}",
                    "body": {
                        "content": "Our team is investigating this urgent issue immediately. We'll update you within 30 minutes.",
                        "contentType": "text"
                    },
                    "importance": "high"
                }
                
                response_sent = await test_workflows.api.client.post(
                    "/api/v1/shared-mailboxes/support@team.com/send",
                    json=team_response
                )
                ResponseAssertions.assert_success_response(response_sent)
                
                sent_data = response_sent.json()
                assert sent_data["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_complete_system_integration(self, test_workflows, db_assertions, override_auth_dependency):
        """Test complete system integration across all components."""
        
        with patch('app.services.OAuthService.OAuthService') as mock_oauth:
            with patch('app.services.MailService.MailService') as mock_mail:
                with patch('app.services.VoiceAttachmentService.VoiceAttachmentService') as mock_voice:
                    with patch('app.services.SharedMailboxService.SharedMailboxService') as mock_shared:
                        
                        # Setup complete system mocks
                        self._setup_complete_system_mocks(
                            mock_oauth, mock_mail, mock_voice, mock_shared
                        )
                        
                        # Execute complete system integration test
                        async with time_operation("complete_system_integration"):
                            
                            # Phase 1: User Authentication and Setup
                            await self._test_authentication_phase(test_workflows, db_assertions)
                            
                            # Phase 2: Mail Operations
                            await self._test_mail_operations_phase(test_workflows)
                            
                            # Phase 3: Voice Processing
                            await self._test_voice_processing_phase(test_workflows)
                            
                            # Phase 4: Shared Mailbox Collaboration
                            await self._test_shared_collaboration_phase(test_workflows)
                            
                            # Phase 5: Cleanup and Logout
                            await self._test_cleanup_phase(test_workflows)

    # =========================================================================
    # HELPER METHODS FOR COMPLETE INTEGRATION TEST
    # =========================================================================

    def _setup_complete_system_mocks(self, mock_oauth, mock_mail, mock_voice, mock_shared):
        """Setup comprehensive mocks for complete system test."""
        
        # OAuth service mocks
        oauth_instance = mock_oauth.return_value
        oauth_instance.initiate_login.return_value = {"auth_uri": "https://login.microsoftonline.com/auth"}
        oauth_instance.handle_callback.return_value = {
            "access_token": "system-integration-token",
            "user_info": {"id": "system-user", "email": "system@integration.com"}
        }
        oauth_instance.logout.return_value = True
        
        # Mail service mocks
        mail_instance = mock_mail.return_value
        mail_instance.list_mail_folders.return_value = [{"id": "inbox", "displayName": "Inbox"}]
        mail_instance.get_inbox_messages.return_value = {
            "value": [{"id": "system-msg-001", "hasAttachments": True}]
        }
        
        # Voice service mocks
        voice_instance = mock_voice.return_value
        voice_instance.find_all_voice_messages.return_value = [Mock(id="voice-msg-001")]
        voice_instance.extract_voice_attachments_from_message.return_value = [
            {"attachment_id": "system-voice-001", "file_name": "system.wav"}
        ]
        voice_instance.organize_voice_messages.return_value = {"success": True, "messages_moved": 1}
        
        # Shared mailbox mocks
        shared_instance = mock_shared.return_value
        shared_instance.get_accessible_shared_mailboxes.return_value = {
            "value": [{"emailAddress": "shared@integration.com"}]
        }
    
    async def _test_authentication_phase(self, test_workflows, db_assertions):
        """Test authentication phase of complete integration."""
        login_response, callback_response, token_data = await test_workflows.complete_authentication_flow()
        assert login_response.status_code == 302
        ResponseAssertions.assert_success_response(callback_response)
        await db_assertions.assert_user_exists("system-user")
    
    async def _test_mail_operations_phase(self, test_workflows):
        """Test mail operations phase of complete integration."""
        folders_response = await test_workflows.api.get_mail_folders()
        ResponseAssertions.assert_success_response(folders_response)
        
        messages_response = await test_workflows.api.get_messages()
        ResponseAssertions.assert_success_response(messages_response)
    
    async def _test_voice_processing_phase(self, test_workflows):
        """Test voice processing phase of complete integration."""
        voice_messages_response = await test_workflows.api.get_voice_messages()
        ResponseAssertions.assert_success_response(voice_messages_response)
        
        organize_response = await test_workflows.api.organize_voice_messages("System Voices")
        ResponseAssertions.assert_success_response(organize_response)
    
    async def _test_shared_collaboration_phase(self, test_workflows):
        """Test shared mailbox collaboration phase of complete integration."""
        mailboxes_response = await test_workflows.api.get_shared_mailboxes()
        ResponseAssertions.assert_success_response(mailboxes_response)
    
    async def _test_cleanup_phase(self, test_workflows):
        """Test cleanup phase of complete integration."""
        logout_response = await test_workflows.api.auth_logout()
        ResponseAssertions.assert_success_response(logout_response)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_system_integration_final_verification(self, test_workflows, db_assertions, override_auth_dependency):
        """Final comprehensive verification of system integration."""
        
        async with time_operation("final_system_verification"):
            
            # Verify all major components are working together
            # This test serves as a final integration checkpoint
            
            # 1. Verify authentication system
            status_response = await test_workflows.api.auth_status()
            ResponseAssertions.assert_success_response(status_response)
            
            # 2. Verify health check endpoints
            health_response = await test_workflows.api.client.get("/health")
            ResponseAssertions.assert_success_response(health_response)
            
            # 3. Verify API documentation is accessible
            docs_response = await test_workflows.api.client.get("/docs")
            assert docs_response.status_code == 200
            
            # Integration test suite completed successfully