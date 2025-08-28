"""
Integration test fixtures for comprehensive API and database testing.

This module provides fixtures specifically designed for integration tests, including:
- Database session management with realistic data
- Mock Azure Graph API responses for complex scenarios
- Test data factories for creating realistic test scenarios
- HTTP client configurations for endpoint testing
- Transaction management for test isolation
"""

import asyncio
import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Import after setting test environment
import os
os.environ["ENV_FOR_DYNACONF"] = "testing"

from app.main import app
from app.core.config import settings
from app.db.models.User import User
from app.db.models.MailAccount import MailAccount
from app.db.models.MailData import MailData
from app.db.models.VoiceAttachment import VoiceAttachment


# =============================================================================
# DATABASE INTEGRATION FIXTURES
# =============================================================================

@pytest_asyncio.fixture
async def integration_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create database session for integration tests with transaction management.
    
    This fixture provides a fresh database session for each test with:
    - Automatic rollback after each test
    - Isolated transactions
    - Realistic constraint checking
    """
    async_session_factory = async_sessionmaker(
        test_db_engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        # Start a transaction
        transaction = await session.begin()
        
        try:
            yield session
        finally:
            # Always rollback to ensure test isolation
            await transaction.rollback()


@pytest_asyncio.fixture
async def db_with_test_data(integration_db_session):
    """Database session pre-populated with realistic test data."""
    session = integration_db_session
    
    # Create test users
    users = [
        User(
            user_id="test-user-1",
            email="user1@example.com",
            display_name="John Doe",
            given_name="John",
            surname="Doe",
            is_active=True
        ),
        User(
            user_id="test-user-2", 
            email="user2@example.com",
            display_name="Jane Smith",
            given_name="Jane",
            surname="Smith",
            is_active=True
        ),
        User(
            user_id="inactive-user",
            email="inactive@example.com", 
            display_name="Inactive User",
            given_name="Inactive",
            surname="User",
            is_active=False
        )
    ]
    
    for user in users:
        session.add(user)
    
    # Create mail accounts
    mail_accounts = [
        MailAccount(
            user_id="test-user-1",
            email_address="user1@example.com",
            account_type="personal",
            is_shared_mailbox=False,
            display_name="John's Account",
            is_active=True
        ),
        MailAccount(
            user_id="test-user-2",
            email_address="shared@example.com",
            account_type="shared", 
            is_shared_mailbox=True,
            display_name="Team Shared Mailbox",
            is_active=True
        )
    ]
    
    for account in mail_accounts:
        session.add(account)
    
    # Create mail data
    mail_data = [
        MailData(
            message_id="msg-001",
            thread_id="thread-001",
            user_id="test-user-1",
            folder_id="inbox",
            subject="Welcome Email",
            sender_email="welcome@example.com",
            sender_name="Welcome Bot",
            received_datetime=datetime.utcnow() - timedelta(hours=1),
            is_read=False,
            has_attachments=False
        ),
        MailData(
            message_id="msg-002", 
            thread_id="thread-002",
            user_id="test-user-1",
            folder_id="inbox",
            subject="Voicemail from Client",
            sender_email="client@business.com",
            sender_name="Important Client",
            received_datetime=datetime.utcnow() - timedelta(minutes=30),
            is_read=False,
            has_attachments=True
        ),
        MailData(
            message_id="msg-003",
            thread_id="thread-003", 
            user_id="test-user-2",
            folder_id="inbox",
            subject="Team Meeting Recording",
            sender_email="meetings@example.com",
            sender_name="Meeting System",
            received_datetime=datetime.utcnow() - timedelta(hours=2),
            is_read=True,
            has_attachments=True
        )
    ]
    
    for message in mail_data:
        session.add(message)
    
    # Create voice attachments
    voice_attachments = [
        VoiceAttachment(
            attachment_id="att-voice-001",
            message_id="msg-002",
            user_id="test-user-1",
            file_name="client-voicemail.wav",
            content_type="audio/wav",
            size_bytes=2048000,
            blob_name="voice-001.wav",
            storage_account="testaccount",
            container_name="voice-attachments",
            download_count=0
        ),
        VoiceAttachment(
            attachment_id="att-voice-002",
            message_id="msg-003", 
            user_id="test-user-2",
            file_name="meeting-recording.mp3",
            content_type="audio/mpeg",
            size_bytes=5120000,
            blob_name="voice-002.mp3",
            storage_account="testaccount", 
            container_name="voice-attachments",
            download_count=3
        )
    ]
    
    for attachment in voice_attachments:
        session.add(attachment)
    
    await session.commit()
    
    return session


# =============================================================================
# HTTP CLIENT FIXTURES
# =============================================================================

@pytest_asyncio.fixture
async def authenticated_async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async HTTP client with authentication headers pre-configured.
    
    This client can be used to test authenticated endpoints without
    manually adding auth headers to each request.
    """
    headers = {
        "Authorization": "Bearer test-access-token",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(
        app=app, 
        base_url="http://test",
        headers=headers
    ) as client:
        yield client


@pytest.fixture
def authenticated_test_client() -> TestClient:
    """Sync test client with authentication for simple endpoint tests."""
    client = TestClient(app)
    client.headers.update({
        "Authorization": "Bearer test-access-token",
        "Content-Type": "application/json"
    })
    return client


# =============================================================================
# GRAPH API MOCK FIXTURES
# =============================================================================

@pytest.fixture
def comprehensive_graph_responses():
    """
    Comprehensive mock responses for Microsoft Graph API endpoints.
    
    Includes realistic data structures and edge cases for:
    - User profiles with various field combinations
    - Mail folders with nested hierarchies
    - Messages with different attachment types
    - Shared mailbox structures
    - Error scenarios
    """
    return {
        "user_profiles": [
            {
                "id": "test-user-1",
                "displayName": "John Doe",
                "givenName": "John", 
                "surname": "Doe",
                "mail": "user1@example.com",
                "userPrincipalName": "user1@example.com",
                "jobTitle": "Software Engineer",
                "officeLocation": "Seattle",
                "businessPhones": ["+1-206-555-0100"],
                "mobilePhone": "+1-425-555-0101"
            },
            {
                "id": "test-user-2",
                "displayName": "Jane Smith", 
                "givenName": "Jane",
                "surname": "Smith",
                "mail": "user2@example.com",
                "userPrincipalName": "user2@example.com",
                "jobTitle": "Product Manager",
                "officeLocation": "New York"
            }
        ],
        "mail_folders": {
            "value": [
                {
                    "id": "inbox",
                    "displayName": "Inbox",
                    "parentFolderId": "root",
                    "childFolderCount": 2,
                    "unreadItemCount": 5,
                    "totalItemCount": 50,
                    "wellKnownName": "inbox"
                },
                {
                    "id": "sentitems",
                    "displayName": "Sent Items",
                    "parentFolderId": "root", 
                    "childFolderCount": 0,
                    "unreadItemCount": 0,
                    "totalItemCount": 25,
                    "wellKnownName": "sentitems"
                },
                {
                    "id": "voice-messages",
                    "displayName": "Voice Messages",
                    "parentFolderId": "inbox",
                    "childFolderCount": 0,
                    "unreadItemCount": 2,
                    "totalItemCount": 10,
                    "wellKnownName": None
                },
                {
                    "id": "archive",
                    "displayName": "Archive", 
                    "parentFolderId": "root",
                    "childFolderCount": 5,
                    "unreadItemCount": 0,
                    "totalItemCount": 1000,
                    "wellKnownName": "archive"
                }
            ]
        },
        "inbox_messages": {
            "value": [
                {
                    "id": "msg-001",
                    "subject": "Welcome to our service",
                    "bodyPreview": "Thank you for signing up...",
                    "importance": "normal",
                    "isRead": False,
                    "receivedDateTime": "2024-01-15T10:00:00Z",
                    "sentDateTime": "2024-01-15T09:58:00Z",
                    "hasAttachments": False,
                    "internetMessageId": "<msg-001@example.com>",
                    "from": {
                        "emailAddress": {
                            "address": "welcome@example.com",
                            "name": "Welcome Team"
                        }
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": "user1@example.com",
                                "name": "John Doe"
                            }
                        }
                    ]
                },
                {
                    "id": "msg-002",
                    "subject": "Voicemail from Important Client",
                    "bodyPreview": "You have received a new voicemail...",
                    "importance": "high", 
                    "isRead": False,
                    "receivedDateTime": "2024-01-15T14:30:00Z",
                    "sentDateTime": "2024-01-15T14:28:00Z", 
                    "hasAttachments": True,
                    "internetMessageId": "<msg-002@business.com>",
                    "from": {
                        "emailAddress": {
                            "address": "client@business.com",
                            "name": "Important Client"
                        }
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": "user1@example.com",
                                "name": "John Doe"  
                            }
                        }
                    ]
                },
                {
                    "id": "msg-003",
                    "subject": "Meeting Recording - Q1 Planning",
                    "bodyPreview": "Recording of today's Q1 planning meeting...",
                    "importance": "normal",
                    "isRead": True,
                    "receivedDateTime": "2024-01-15T12:00:00Z",
                    "sentDateTime": "2024-01-15T11:58:00Z",
                    "hasAttachments": True,
                    "internetMessageId": "<msg-003@example.com>",
                    "from": {
                        "emailAddress": {
                            "address": "meetings@example.com", 
                            "name": "Meeting Bot"
                        }
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": "team@example.com",
                                "name": "Development Team"
                            }
                        }
                    ]
                }
            ],
            "@odata.nextLink": None
        },
        "voice_attachments": {
            "value": [
                {
                    "id": "att-voice-001",
                    "name": "client-voicemail.wav",
                    "contentType": "audio/wav",
                    "size": 2048000,
                    "isInline": False,
                    "lastModifiedDateTime": "2024-01-15T14:28:00Z"
                },
                {
                    "id": "att-voice-002", 
                    "name": "meeting-recording.mp3",
                    "contentType": "audio/mpeg",
                    "size": 5120000,
                    "isInline": False,
                    "lastModifiedDateTime": "2024-01-15T11:58:00Z"
                }
            ]
        },
        "shared_mailboxes": {
            "value": [
                {
                    "id": "shared-mb-001",
                    "displayName": "Customer Support",
                    "mail": "support@example.com",
                    "mailboxSettings": {
                        "automaticRepliesSetting": {
                            "status": "disabled"
                        }
                    }
                },
                {
                    "id": "shared-mb-002",
                    "displayName": "Sales Team", 
                    "mail": "sales@example.com",
                    "mailboxSettings": {
                        "automaticRepliesSetting": {
                            "status": "scheduled"
                        }
                    }
                }
            ]
        },
        "error_responses": {
            "insufficient_privileges": {
                "error": {
                    "code": "Forbidden",
                    "message": "Insufficient privileges to complete the operation.",
                    "innerError": {
                        "date": "2024-01-15T10:30:00",
                        "request-id": "test-request-id"
                    }
                }
            },
            "item_not_found": {
                "error": {
                    "code": "ItemNotFound", 
                    "message": "The specified object was not found in the store.",
                    "innerError": {
                        "date": "2024-01-15T10:30:00",
                        "request-id": "test-request-id"
                    }
                }
            },
            "throttled": {
                "error": {
                    "code": "TooManyRequests",
                    "message": "The request has been throttled. Retry after {delay} seconds.",
                    "innerError": {
                        "date": "2024-01-15T10:30:00",
                        "request-id": "test-request-id"
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_graph_api(respx_mock, comprehensive_graph_responses):
    """
    Set up comprehensive Graph API mocks for integration testing.
    
    This fixture configures realistic Graph API responses for:
    - User profile endpoints
    - Mail folder operations  
    - Message retrieval and operations
    - Attachment handling
    - Shared mailbox operations
    - Error scenarios
    """
    base_url = "https://graph.microsoft.com/v1.0"
    
    # User profile endpoints
    for user_profile in comprehensive_graph_responses["user_profiles"]:
        user_id = user_profile["id"]
        respx_mock.get(f"{base_url}/users/{user_id}").mock(
            return_value=httpx.Response(200, json=user_profile)
        )
    
    # Current user endpoint
    respx_mock.get(f"{base_url}/me").mock(
        return_value=httpx.Response(200, json=comprehensive_graph_responses["user_profiles"][0])
    )
    
    # Mail folders endpoint
    respx_mock.get(f"{base_url}/me/mailFolders").mock(
        return_value=httpx.Response(200, json=comprehensive_graph_responses["mail_folders"])
    )
    
    # Inbox messages endpoint 
    respx_mock.get(f"{base_url}/me/messages").mock(
        return_value=httpx.Response(200, json=comprehensive_graph_responses["inbox_messages"])
    )
    
    # Messages with attachments filter
    respx_mock.get(
        f"{base_url}/me/messages",
        params={"$filter": "hasAttachments eq true"}
    ).mock(
        return_value=httpx.Response(200, json={
            "value": [msg for msg in comprehensive_graph_responses["inbox_messages"]["value"] 
                     if msg["hasAttachments"]]
        })
    )
    
    # Individual message endpoints
    for message in comprehensive_graph_responses["inbox_messages"]["value"]:
        msg_id = message["id"]
        respx_mock.get(f"{base_url}/me/messages/{msg_id}").mock(
            return_value=httpx.Response(200, json=message)
        )
        
        # Message attachments
        if message["hasAttachments"]:
            voice_attachments = [att for att in comprehensive_graph_responses["voice_attachments"]["value"]]
            respx_mock.get(f"{base_url}/me/messages/{msg_id}/attachments").mock(
                return_value=httpx.Response(200, json={"value": voice_attachments})
            )
    
    # Shared mailboxes
    respx_mock.get(f"{base_url}/me/mailboxes").mock(
        return_value=httpx.Response(200, json=comprehensive_graph_responses["shared_mailboxes"])
    )
    
    # Error scenarios
    respx_mock.get(f"{base_url}/me/messages/non-existent").mock(
        return_value=httpx.Response(404, json=comprehensive_graph_responses["error_responses"]["item_not_found"])
    )
    
    respx_mock.get(f"{base_url}/unauthorized").mock(
        return_value=httpx.Response(403, json=comprehensive_graph_responses["error_responses"]["insufficient_privileges"])
    )
    
    return respx_mock


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================

@pytest.fixture
def mock_authenticated_user():
    """Mock authenticated user for dependency injection in tests."""
    return {
        "id": "test-user-1",
        "email": "user1@example.com",
        "display_name": "John Doe",
        "given_name": "John",
        "surname": "Doe",
        "access_token": "test-access-token",
        "scopes": ["User.Read", "Mail.Read", "Mail.ReadWrite"]
    }


@pytest.fixture
def override_auth_dependency(mock_authenticated_user):
    """Override authentication dependency for testing protected endpoints."""
    from app.dependencies.Auth import get_current_user
    from app.models.AuthModel import UserInfo
    
    def mock_get_current_user():
        return UserInfo(**mock_authenticated_user)
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    yield mock_get_current_user
    
    # Cleanup
    app.dependency_overrides.clear()


# =============================================================================
# AZURE SERVICES FIXTURES 
# =============================================================================

@pytest.fixture
def mock_azure_blob_service():
    """Mock Azure Blob Storage service with realistic operations."""
    service = Mock()
    
    # Mock blob operations
    blob_client = Mock()
    blob_client.exists.return_value = True
    blob_client.upload_blob.return_value = None
    blob_client.download_blob.return_value = Mock(
        readall=Mock(return_value=b"mock audio data" * 1000)
    )
    blob_client.delete_blob.return_value = None
    blob_client.get_blob_properties.return_value = Mock(
        size=5120000,
        last_modified=datetime.utcnow(),
        content_settings=Mock(content_type="audio/wav")
    )
    
    service.get_blob_client.return_value = blob_client
    
    # Mock container operations
    container_client = Mock()
    container_client.list_blobs.return_value = [
        Mock(name="voice-001.wav", size=2048000),
        Mock(name="voice-002.mp3", size=5120000),
        Mock(name="voice-003.wav", size=1024000)
    ]
    
    service.get_container_client.return_value = container_client
    
    return service


@pytest.fixture 
def mock_oauth_flow_success():
    """Mock successful OAuth flow for integration testing."""
    return {
        "authorization_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "state": "test-state-value",
        "token_response": {
            "access_token": "test-access-token-value",
            "refresh_token": "test-refresh-token-value", 
            "id_token": "test-id-token-value",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "User.Read Mail.Read Mail.ReadWrite"
        },
        "user_profile": {
            "id": "test-user-1",
            "displayName": "John Doe",
            "mail": "user1@example.com",
            "givenName": "John",
            "surname": "Doe"
        }
    }


# =============================================================================
# TEST DATA FACTORIES
# =============================================================================

class IntegrationDataFactory:
    """Factory for creating realistic test data for integration tests."""
    
    @staticmethod
    def create_realistic_user(**overrides):
        """Create a realistic user with all fields populated."""
        base_data = {
            "user_id": str(uuid4()),
            "email": f"user{uuid4().hex[:8]}@example.com",
            "display_name": "Test User",
            "given_name": "Test", 
            "surname": "User",
            "is_active": True,
            "job_title": "Software Engineer",
            "office_location": "Seattle",
            "business_phones": ["+1-206-555-0100"],
            "mobile_phone": "+1-425-555-0101"
        }
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def create_mail_message_with_voice(**overrides):
        """Create a mail message with voice attachment."""
        base_data = {
            "id": f"msg-{uuid4().hex[:8]}",
            "subject": "Voicemail Message",
            "bodyPreview": "You have received a new voicemail...",
            "importance": "normal",
            "isRead": False,
            "receivedDateTime": datetime.utcnow().isoformat() + "Z",
            "hasAttachments": True,
            "from": {
                "emailAddress": {
                    "address": "caller@example.com", 
                    "name": "Caller Name"
                }
            }
        }
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def create_voice_attachment(**overrides):
        """Create a realistic voice attachment."""
        base_data = {
            "id": f"att-{uuid4().hex[:8]}",
            "name": "voicemail.wav",
            "contentType": "audio/wav",
            "size": 2048000,
            "isInline": False,
            "lastModifiedDateTime": datetime.utcnow().isoformat() + "Z"
        }
        base_data.update(overrides)
        return base_data
    
    @staticmethod
    def create_shared_mailbox(**overrides):
        """Create a realistic shared mailbox."""
        base_data = {
            "id": f"mb-{uuid4().hex[:8]}",
            "displayName": "Team Shared Mailbox",
            "mail": f"shared{uuid4().hex[:6]}@example.com",
            "mailboxSettings": {
                "automaticRepliesSetting": {"status": "disabled"}
            }
        }
        base_data.update(overrides)
        return base_data


@pytest.fixture
def integration_data_factory():
    """Provide access to the integration data factory."""
    return IntegrationDataFactory


# =============================================================================
# PERFORMANCE AND MONITORING FIXTURES
# =============================================================================

@pytest.fixture
def response_time_monitor():
    """Monitor API response times during integration tests."""
    response_times = []
    
    def record_response_time(start_time: float, endpoint: str):
        end_time = datetime.now().timestamp() 
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        response_times.append({
            "endpoint": endpoint,
            "response_time_ms": response_time,
            "timestamp": datetime.now()
        })
    
    yield record_response_time
    
    # Log slow responses for analysis
    slow_responses = [r for r in response_times if r["response_time_ms"] > 1000]
    if slow_responses:
        print(f"\n[PERFORMANCE] Slow responses detected: {len(slow_responses)} endpoints > 1000ms")
        for response in slow_responses:
            print(f"  {response['endpoint']}: {response['response_time_ms']:.2f}ms")


@pytest.fixture
def database_query_monitor(integration_db_session):
    """Monitor database queries during integration tests."""
    queries = []
    
    def log_query(conn, cursor, statement, parameters, context, executemany):
        queries.append({
            "statement": statement,
            "parameters": parameters,
            "timestamp": datetime.now()
        })
    
    # Add query logging to the database session
    event.listen(integration_db_session.bind, 'before_cursor_execute', log_query)
    
    yield queries
    
    # Remove listener
    event.remove(integration_db_session.bind, 'before_cursor_execute', log_query)
    
    # Log query statistics
    if queries:
        print(f"\n[DATABASE] Executed {len(queries)} queries during test")
        complex_queries = [q for q in queries if len(q["statement"]) > 500]
        if complex_queries:
            print(f"[DATABASE] Complex queries detected: {len(complex_queries)}")