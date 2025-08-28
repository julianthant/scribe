"""Centralized mock responses for external services.

This module provides mock responses for:
- Microsoft Graph API responses
- Azure services responses
- OAuth token responses
- Error responses
- HTTP status codes and headers
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any

# Microsoft Graph API Mock Responses
GRAPH_API_RESPONSES = {
    # User profile responses
    "user_profile": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users/$entity",
        "id": "12345678-1234-1234-1234-123456789012",
        "businessPhones": ["+1 206 555 0109"],
        "displayName": "Test User",
        "givenName": "Test",
        "jobTitle": "Software Engineer",
        "mail": "testuser@example.com",
        "mobilePhone": "+1 425 555 0201",
        "officeLocation": "Seattle",
        "preferredLanguage": "en-US",
        "surname": "User",
        "userPrincipalName": "testuser@example.com"
    },
    
    # Mail folders response
    "mail_folders": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/mailFolders",
        "value": [
            {
                "id": "inbox",
                "displayName": "Inbox",
                "parentFolderId": "msgfolderroot",
                "childFolderCount": 3,
                "unreadItemCount": 12,
                "totalItemCount": 145,
                "sizeInBytes": 52341234,
                "isHidden": False
            },
            {
                "id": "sentitems",
                "displayName": "Sent Items",
                "parentFolderId": "msgfolderroot",
                "childFolderCount": 0,
                "unreadItemCount": 0,
                "totalItemCount": 87,
                "sizeInBytes": 12487532,
                "isHidden": False
            },
            {
                "id": "drafts",
                "displayName": "Drafts",
                "parentFolderId": "msgfolderroot",
                "childFolderCount": 0,
                "unreadItemCount": 3,
                "totalItemCount": 5,
                "sizeInBytes": 234567,
                "isHidden": False
            }
        ]
    },
    
    # Empty folders response
    "empty_folders": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/mailFolders",
        "value": []
    },
    
    # Messages response
    "messages": {
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
                "subject": "Important Meeting Follow-up",
                "bodyPreview": "Hi there, I wanted to follow up on our meeting...",
                "importance": "normal",
                "parentFolderId": "inbox",
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
            }
        ]
    },
    
    # Empty messages response
    "empty_messages": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/messages",
        "value": []
    },
    
    # Attachments response
    "attachments": {
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
                "contentBytes": "UklGRiQIAABXQVZFZm10IBAAAAABAAIAFEABAABA=="
            }
        ]
    },
    
    # Shared mailboxes response
    "shared_mailboxes": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users",
        "value": [
            {
                "id": "shared-mailbox-1",
                "displayName": "Support Team",
                "mail": "support@example.com",
                "userPrincipalName": "support@example.com",
                "mailboxSettings": {
                    "timeZone": "UTC"
                }
            },
            {
                "id": "shared-mailbox-2",
                "displayName": "Sales Team",
                "mail": "sales@example.com", 
                "userPrincipalName": "sales@example.com",
                "mailboxSettings": {
                    "timeZone": "Pacific Standard Time"
                }
            }
        ]
    },
    
    # Folder creation response
    "created_folder": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/mailFolders/$entity",
        "id": "new-folder-id",
        "displayName": "Voice Messages",
        "parentFolderId": "inbox",
        "childFolderCount": 0,
        "unreadItemCount": 0,
        "totalItemCount": 0,
        "sizeInBytes": 0,
        "isHidden": False
    },
    
    # Message move response
    "moved_message": {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('user-id')/messages/$entity",
        "id": "message-id-1",
        "parentFolderId": "voice-folder-id"
    },
    
    # Search results
    "search_results": {
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
}

# OAuth Token Responses
OAUTH_RESPONSES = {
    "token_success": {
        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.test.token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "refresh_token_value",
        "scope": "User.Read Mail.Read Mail.ReadWrite",
        "id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.id.token"
    },
    
    "token_refresh_success": {
        "access_token": "new_access_token_value",
        "token_type": "Bearer", 
        "expires_in": 3600,
        "scope": "User.Read Mail.Read Mail.ReadWrite"
    },
    
    "token_error": {
        "error": "invalid_grant",
        "error_description": "The provided authorization grant is invalid, expired, or revoked"
    },
    
    "auth_flow_initiate": {
        "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "flow": {
            "state": "test-state-123",
            "code_verifier": "test-code-verifier"
        }
    }
}

# Error Responses
ERROR_RESPONSES = {
    "unauthorized": {
        "error": {
            "code": "InvalidAuthenticationToken",
            "message": "Access token is empty.",
            "innerError": {
                "date": "2025-01-15T16:30:00",
                "request-id": "12345678-1234-1234-1234-123456789012"
            }
        }
    },
    
    "forbidden": {
        "error": {
            "code": "Forbidden",
            "message": "Insufficient privileges to complete the operation.",
            "innerError": {
                "date": "2025-01-15T16:30:00",
                "request-id": "12345678-1234-1234-1234-123456789012"
            }
        }
    },
    
    "not_found": {
        "error": {
            "code": "ErrorItemNotFound",
            "message": "The specified object was not found in the store.",
            "innerError": {
                "date": "2025-01-15T16:30:00",
                "request-id": "12345678-1234-1234-1234-123456789012"
            }
        }
    },
    
    "rate_limited": {
        "error": {
            "code": "TooManyRequests",
            "message": "Too many requests. Please retry after some time.",
            "innerError": {
                "date": "2025-01-15T16:30:00",
                "request-id": "12345678-1234-1234-1234-123456789012"
            }
        }
    },
    
    "validation_error": {
        "error": {
            "code": "InvalidRequest",
            "message": "The request is invalid.",
            "details": [
                {
                    "code": "PropertyNotNullable",
                    "target": "displayName",
                    "message": "Property displayName is required but null."
                }
            ],
            "innerError": {
                "date": "2025-01-15T16:30:00",
                "request-id": "12345678-1234-1234-1234-123456789012"
            }
        }
    }
}

# Azure Services Responses
AZURE_RESPONSES = {
    "blob_upload_success": {
        "blob_name": "voice-attachments/2025-01-15/message_attachment.wav",
        "url": "https://teststorage.blob.core.windows.net/voice-attachments/message_attachment.wav",
        "size": 1048576,
        "content_type": "audio/wav",
        "last_modified": "2025-01-15T15:45:00Z",
        "etag": "0x8D9A1B2C3D4E5F6"
    },
    
    "blob_download_success": b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00D\xac\x00\x00",
    
    "blob_list_success": {
        "blobs": [
            {
                "name": "voice-attachments/2025-01-15/message1_attachment1.wav",
                "size": 1048576,
                "last_modified": "2025-01-15T15:45:00Z",
                "content_type": "audio/wav"
            },
            {
                "name": "voice-attachments/2025-01-15/message2_attachment1.mp3",
                "size": 524288,
                "last_modified": "2025-01-15T14:30:00Z",
                "content_type": "audio/mpeg"
            }
        ]
    },
    
    "storage_error": {
        "error": {
            "code": "BlobNotFound",
            "message": "The specified blob does not exist."
        }
    }
}

# HTTP Headers for Mock Responses
MOCK_HEADERS = {
    "success": {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "request-id": "12345678-1234-1234-1234-123456789012"
    },
    
    "auth_required": {
        "Content-Type": "application/json",
        "WWW-Authenticate": 'Bearer realm="microsoftgraph.com", error="invalid_token"'
    },
    
    "rate_limit": {
        "Content-Type": "application/json",
        "Retry-After": "60"
    },
    
    "blob_headers": {
        "Content-Type": "audio/wav",
        "Content-Length": "1048576",
        "Last-Modified": "Tue, 15 Jan 2025 15:45:00 GMT",
        "ETag": '"0x8D9A1B2C3D4E5F6"'
    }
}

# Common Mock Response Functions
def get_paginated_response(data: List[Dict], page_size: int = 10, page: int = 0) -> Dict[str, Any]:
    """Generate a paginated mock response."""
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_data = data[start_idx:end_idx]
    
    response = {
        "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#collection",
        "value": page_data
    }
    
    if end_idx < len(data):
        response["@odata.nextLink"] = f"https://graph.microsoft.com/v1.0/endpoint?$skip={end_idx}"
    
    return response


def get_error_response(error_code: str, message: str, status_code: int = 400) -> Dict[str, Any]:
    """Generate a standardized error response."""
    return {
        "error": {
            "code": error_code,
            "message": message,
            "innerError": {
                "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                "request-id": "test-request-id"
            }
        }
    }


def get_auth_header(token: str = "test-access-token") -> Dict[str, str]:
    """Generate authorization header for mock requests."""
    return {"Authorization": f"Bearer {token}"}


# Mock Response Status Codes
STATUS_CODES = {
    "success": 200,
    "created": 201,
    "accepted": 202,
    "no_content": 204,
    "bad_request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "too_many_requests": 429,
    "internal_server_error": 500,
    "service_unavailable": 503
}

# Mock Response Collections by Service
MOCK_COLLECTIONS = {
    "graph_api": GRAPH_API_RESPONSES,
    "oauth": OAUTH_RESPONSES,
    "errors": ERROR_RESPONSES,
    "azure": AZURE_RESPONSES,
    "headers": MOCK_HEADERS,
    "status_codes": STATUS_CODES
}


def get_mock_response(service: str, response_type: str) -> Dict[str, Any]:
    """Get a mock response by service and type."""
    if service not in MOCK_COLLECTIONS:
        raise ValueError(f"Unknown service: {service}")
    
    service_responses = MOCK_COLLECTIONS[service]
    if response_type not in service_responses:
        raise ValueError(f"Unknown response type '{response_type}' for service '{service}'")
    
    return service_responses[response_type]


def create_voice_message_response(
    message_id: str = "voice-msg-1",
    sender_email: str = "caller@example.com",
    subject: str = "Voice Message",
    has_attachments: bool = True
) -> Dict[str, Any]:
    """Create a customized voice message mock response."""
    return {
        "id": message_id,
        "subject": subject,
        "hasAttachments": has_attachments,
        "receivedDateTime": datetime.utcnow().isoformat() + "Z",
        "sender": {
            "emailAddress": {
                "name": sender_email.split("@")[0].title(),
                "address": sender_email
            }
        },
        "parentFolderId": "voice-folder-id"
    }


def create_attachment_response(
    attachment_id: str = "att-1",
    filename: str = "voice.wav",
    content_type: str = "audio/wav",
    size: int = 1048576
) -> Dict[str, Any]:
    """Create a customized attachment mock response."""
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "id": attachment_id,
        "name": filename,
        "contentType": content_type,
        "size": size,
        "isInline": False,
        "lastModifiedDateTime": datetime.utcnow().isoformat() + "Z",
        "contentBytes": "base64encodeddata=="
    }