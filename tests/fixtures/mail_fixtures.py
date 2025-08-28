"""Mail and messaging test fixtures.

This module provides fixtures for testing mail functionality including:
- Mock Graph API mail responses
- Test mail folder structures  
- Sample message data
- Voice attachment fixtures
- Shared mailbox data
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock


@pytest.fixture
def mock_mail_folders():
    """Mock mail folders from Microsoft Graph API."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/mailFolders",
        "value": [
            {
                "id": "inbox-folder-id",
                "displayName": "Inbox",
                "parentFolderId": "msgfolderroot",
                "childFolderCount": 3,
                "unreadItemCount": 12,
                "totalItemCount": 145,
                "sizeInBytes": 52341234,
                "isHidden": False
            },
            {
                "id": "sent-items-folder-id", 
                "displayName": "Sent Items",
                "parentFolderId": "msgfolderroot",
                "childFolderCount": 0,
                "unreadItemCount": 0,
                "totalItemCount": 87,
                "sizeInBytes": 12487532,
                "isHidden": False
            },
            {
                "id": "drafts-folder-id",
                "displayName": "Drafts", 
                "parentFolderId": "msgfolderroot",
                "childFolderCount": 0,
                "unreadItemCount": 3,
                "totalItemCount": 5,
                "sizeInBytes": 234567,
                "isHidden": False
            },
            {
                "id": "voice-folder-id",
                "displayName": "Voice Messages",
                "parentFolderId": "inbox-folder-id",
                "childFolderCount": 0,
                "unreadItemCount": 8,
                "totalItemCount": 23,
                "sizeInBytes": 45678912,
                "isHidden": False
            }
        ]
    }


@pytest.fixture
def mock_mail_messages():
    """Mock mail messages from Microsoft Graph API."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/messages",
        "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=10",
        "value": [
            {
                "id": "message-id-1",
                "createdDateTime": "2025-01-15T14:30:00Z",
                "lastModifiedDateTime": "2025-01-15T14:30:00Z",
                "receivedDateTime": "2025-01-15T14:30:00Z",
                "sentDateTime": "2025-01-15T14:29:45Z",
                "hasAttachments": True,
                "internetMessageId": "<message1@example.com>",
                "subject": "Voice Message: Meeting Follow-up",
                "bodyPreview": "Hi there, I wanted to follow up on our meeting...",
                "importance": "normal",
                "parentFolderId": "inbox-folder-id",
                "conversationId": "conversation-id-1",
                "isDeliveryReceiptRequested": False,
                "isReadReceiptRequested": False,
                "isRead": False,
                "isDraft": False,
                "webLink": "https://outlook.office365.com/owa/?ItemID=message-id-1",
                "body": {
                    "contentType": "html",
                    "content": "<html><body>Hi there,<br><br>I wanted to follow up on our meeting...</body></html>"
                },
                "sender": {
                    "emailAddress": {
                        "name": "John Sender",
                        "address": "john.sender@example.com"
                    }
                },
                "from": {
                    "emailAddress": {
                        "name": "John Sender", 
                        "address": "john.sender@example.com"
                    }
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "name": "Test User",
                            "address": "testuser@example.com"
                        }
                    }
                ]
            },
            {
                "id": "message-id-2",
                "createdDateTime": "2025-01-15T13:15:00Z",
                "lastModifiedDateTime": "2025-01-15T13:15:00Z", 
                "receivedDateTime": "2025-01-15T13:15:00Z",
                "sentDateTime": "2025-01-15T13:14:30Z",
                "hasAttachments": False,
                "internetMessageId": "<message2@example.com>",
                "subject": "Project Update",
                "bodyPreview": "Quick update on the project status...",
                "importance": "high",
                "parentFolderId": "inbox-folder-id",
                "conversationId": "conversation-id-2",
                "isDeliveryReceiptRequested": False,
                "isReadReceiptRequested": True,
                "isRead": True,
                "isDraft": False,
                "webLink": "https://outlook.office365.com/owa/?ItemID=message-id-2",
                "body": {
                    "contentType": "text",
                    "content": "Quick update on the project status. Everything is on track."
                },
                "sender": {
                    "emailAddress": {
                        "name": "Sarah Project Manager",
                        "address": "sarah.pm@example.com"
                    }
                },
                "from": {
                    "emailAddress": {
                        "name": "Sarah Project Manager",
                        "address": "sarah.pm@example.com"
                    }
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "name": "Test User",
                            "address": "testuser@example.com"
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_voice_message():
    """Mock voice message with audio attachment."""
    return {
        "id": "voice-message-id-1",
        "createdDateTime": "2025-01-15T15:45:00Z",
        "receivedDateTime": "2025-01-15T15:45:00Z",
        "sentDateTime": "2025-01-15T15:44:30Z",
        "hasAttachments": True,
        "subject": "Voice Message: Quick Update",
        "bodyPreview": "Voice message attached",
        "parentFolderId": "voice-folder-id",
        "sender": {
            "emailAddress": {
                "name": "Voice Caller",
                "address": "caller@example.com"
            }
        },
        "attachments": [
            {
                "id": "voice-attachment-id-1",
                "name": "voice-message.mp3",
                "contentType": "audio/mpeg",
                "size": 524288,
                "isInline": False,
                "lastModifiedDateTime": "2025-01-15T15:44:30Z"
            }
        ]
    }


@pytest.fixture
def mock_mail_attachments():
    """Mock mail attachments from Microsoft Graph API."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/messages('message-id')/attachments",
        "value": [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "id": "attachment-id-1",
                "lastModifiedDateTime": "2025-01-15T14:30:00Z",
                "name": "voice-recording.wav",
                "contentType": "audio/wav",
                "size": 1048576,
                "isInline": False,
                "contentId": None,
                "contentLocation": None,
                "contentBytes": "base64encodedaudiodata=="
            },
            {
                "@odata.type": "#microsoft.graph.fileAttachment", 
                "id": "attachment-id-2",
                "lastModifiedDateTime": "2025-01-15T14:30:00Z",
                "name": "document.pdf",
                "contentType": "application/pdf",
                "size": 245760,
                "isInline": False,
                "contentId": None,
                "contentLocation": None,
                "contentBytes": "base64encodedpdfdata=="
            }
        ]
    }


@pytest.fixture
def mock_shared_mailboxes():
    """Mock shared mailboxes response."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users",
        "value": [
            {
                "id": "shared-mailbox-id-1",
                "displayName": "Support Team",
                "mail": "support@example.com",
                "userPrincipalName": "support@example.com",
                "mailboxSettings": {
                    "timeZone": "UTC"
                }
            },
            {
                "id": "shared-mailbox-id-2", 
                "displayName": "Sales Team",
                "mail": "sales@example.com",
                "userPrincipalName": "sales@example.com",
                "mailboxSettings": {
                    "timeZone": "Pacific Standard Time"
                }
            }
        ]
    }


@pytest.fixture
def mock_voice_attachment_metadata():
    """Mock voice attachment metadata."""
    return {
        "message_id": "voice-message-id-1",
        "attachment_id": "voice-attachment-id-1",
        "filename": "voice-recording.wav",
        "content_type": "audio/wav",
        "size_bytes": 1048576,
        "duration_seconds": 45.5,
        "sample_rate": 44100,
        "channels": 2,
        "bitrate": 192000,
        "created_at": "2025-01-15T15:44:30Z",
        "sender_email": "caller@example.com",
        "sender_name": "Voice Caller",
        "folder_id": "voice-folder-id",
        "folder_name": "Voice Messages"
    }


@pytest.fixture
def mock_folder_creation_request():
    """Mock request for creating a new mail folder."""
    return {
        "displayName": "New Voice Messages",
        "parentFolderId": "inbox-folder-id"
    }


@pytest.fixture
def mock_folder_creation_response():
    """Mock response for successful folder creation."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/mailFolders/$entity",
        "id": "new-voice-folder-id",
        "displayName": "New Voice Messages",
        "parentFolderId": "inbox-folder-id", 
        "childFolderCount": 0,
        "unreadItemCount": 0,
        "totalItemCount": 0,
        "sizeInBytes": 0,
        "isHidden": False
    }


@pytest.fixture
def mock_message_move_request():
    """Mock request for moving a message to different folder."""
    return {
        "destinationId": "voice-folder-id"
    }


@pytest.fixture
def mock_mail_search_request():
    """Mock mail search request."""
    return {
        "query": "hasAttachments:true AND subject:voice",
        "folder_id": "inbox-folder-id",
        "top": 25,
        "skip": 0
    }


@pytest.fixture
def mock_mail_search_response():
    """Mock mail search response."""
    return {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/messages",
        "value": [
            {
                "id": "search-result-1",
                "subject": "Voice Message: Important Update",
                "hasAttachments": True,
                "receivedDateTime": "2025-01-15T16:00:00Z",
                "sender": {
                    "emailAddress": {
                        "name": "Important Caller",
                        "address": "important@example.com"  
                    }
                }
            }
        ]
    }


@pytest.fixture
def mock_voice_statistics():
    """Mock voice message statistics."""
    return {
        "total_voice_messages": 23,
        "unread_voice_messages": 8,
        "total_duration_minutes": 125.5,
        "average_duration_seconds": 45.2,
        "storage_used_mb": 43.7,
        "messages_by_sender": {
            "caller@example.com": 15,
            "important@example.com": 5,
            "other@example.com": 3
        },
        "messages_by_date": {
            "2025-01-15": 12,
            "2025-01-14": 7,
            "2025-01-13": 4
        }
    }


@pytest.fixture
def mock_send_message_request():
    """Mock request for sending an email message."""
    return {
        "message": {
            "subject": "Test Email Subject",
            "body": {
                "contentType": "HTML",
                "content": "This is a test email message."
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "address": "recipient@example.com",
                        "name": "Test Recipient"
                    }
                }
            ],
            "ccRecipients": [],
            "bccRecipients": [],
            "attachments": []
        },
        "saveToSentItems": True
    }


@pytest.fixture
def audio_file_bytes():
    """Mock audio file bytes for voice attachment testing."""
    # Minimal WAV header followed by dummy audio data
    return b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00D\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\x00\x08\x00\x00' + b'\x00' * 2048


@pytest.fixture
def mock_blob_storage_response():
    """Mock Azure Blob Storage response for voice attachment storage."""
    return {
        "blob_name": "voice-attachments/2025-01-15/voice-message-id-1_voice-attachment-id-1.wav",
        "url": "https://teststorage.blob.core.windows.net/voice-attachments/2025-01-15/voice-message-id-1_voice-attachment-id-1.wav",
        "size": 1048576,
        "content_type": "audio/wav",
        "last_modified": "2025-01-15T15:45:00Z",
        "etag": "0x8D9A1B2C3D4E5F6"
    }


# Async fixtures for async testing
@pytest.fixture
async def async_mock_mail_service():
    """Async mock mail service."""
    from unittest.mock import AsyncMock
    
    service = AsyncMock()
    
    service.get_mail_folders.return_value = mock_mail_folders()
    service.get_messages.return_value = mock_mail_messages()
    service.get_attachments.return_value = mock_mail_attachments()
    service.download_attachment.return_value = b"mock audio data"
    
    return service


@pytest.fixture
def mail_test_config():
    """Test configuration for mail functionality."""
    return {
        "voice_folder_name": "Voice Messages", 
        "max_attachment_size": 10485760,  # 10MB
        "supported_audio_types": [
            "audio/wav", "audio/mp3", "audio/mpeg", "audio/m4a", "audio/aac"
        ],
        "blob_container_name": "voice-attachments",
        "cleanup_after_days": 30,
        "max_messages_per_request": 50
    }