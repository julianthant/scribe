"""
conftest.py - Global pytest configuration and fixtures.

This module provides global pytest configuration and fixtures that are
shared across all test modules. It includes:
- Database fixtures for unit and integration tests
- Mock Azure services fixtures
- Authentication fixtures
- Test client fixtures
- Cleanup fixtures
"""

import asyncio
import os
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set test environment before importing app modules
os.environ["ENV_FOR_DYNACONF"] = "testing"

from app.main import app
from app.core.config import settings
from app.db.Database import DatabaseManager
from app.models.DatabaseModel import Base
from app.db.models.User import User
from app.db.models.MailAccount import MailAccount
from app.db.models.MailData import MailFolder
from app.db.models.VoiceAttachment import VoiceAttachment


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )

def pytest_asyncio_config():
    """Configure pytest-asyncio settings."""
    return {
        "asyncio_mode": "auto",
        "asyncio_default_fixture_loop_scope": "function"
    }


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location."""
    for item in items:
        # Auto-mark unit tests
        if "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        
        # Auto-mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest_asyncio.fixture
async def test_db_engine():
    """Create async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={
            "check_same_thread": False,
        },
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session_factory = async_sessionmaker(
        test_db_engine, 
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def sync_test_db():
    """Create synchronous SQLite engine for sync tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()


# =============================================================================
# HTTP CLIENT FIXTURES
# =============================================================================

@pytest.fixture
def test_client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for testing."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================

@pytest.fixture
def mock_access_token() -> str:
    """Generate mock access token for testing."""
    return "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6InU0T2ZORlo0THpYc"


@pytest.fixture
def auth_headers(mock_access_token) -> Dict[str, str]:
    """Create authorization headers for testing."""
    return {"Authorization": f"Bearer {mock_access_token}"}


@pytest.fixture
def test_user_data() -> Dict[str, Any]:
    """Test user data for creating users."""
    return {
        "user_id": "test-user-123",
        "email": "test@example.com",
        "display_name": "Test User",
        "given_name": "Test",
        "surname": "User",
        "is_active": True,
    }


@pytest_asyncio.fixture
async def test_user(test_db_session, test_user_data) -> User:
    """Create test user in database."""
    user = User(**test_user_data)
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


# =============================================================================
# AZURE SERVICES MOCKS
# =============================================================================

@pytest.fixture
def mock_msal_client():
    """Mock MSAL ConfidentialClientApplication."""
    client = Mock()
    
    # Mock auth flow initiation
    client.initiate_auth_code_flow.return_value = {
        "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=test",
        "flow": {
            "state": "test-state-value",
            "code_verifier": "test-verifier",
            "code_challenge": "test-challenge",
        }
    }
    
    # Mock token acquisition
    client.acquire_token_by_auth_code_flow.return_value = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "id_token": "test-id-token",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "User.Read Mail.Read Mail.ReadWrite"
    }
    
    # Mock token refresh
    client.acquire_token_by_refresh_token.return_value = {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
        "expires_in": 3600,
    }
    
    return client


@pytest.fixture
def mock_azure_auth_service(mock_msal_client):
    """Mock AzureAuthService with mocked MSAL client."""
    with patch('app.azure.AzureAuthService.msal.ConfidentialClientApplication', return_value=mock_msal_client):
        from app.azure.AzureAuthService import AzureAuthService
        yield AzureAuthService()


@pytest.fixture
def mock_blob_service():
    """Mock Azure BlobServiceClient."""
    service = Mock()
    
    # Mock blob client
    blob_client = Mock()
    blob_client.upload_blob.return_value = None
    blob_client.download_blob.return_value = Mock(
        readall=Mock(return_value=b"test audio data")
    )
    blob_client.exists.return_value = True
    blob_client.delete_blob.return_value = None
    
    service.get_blob_client.return_value = blob_client
    
    # Mock container client
    container_client = Mock()
    container_client.list_blobs.return_value = [
        Mock(name="test-blob-1.wav"),
        Mock(name="test-blob-2.mp3"),
    ]
    
    service.get_container_client.return_value = container_client
    
    return service


@pytest.fixture
def mock_graph_api_responses():
    """Mock Graph API response data."""
    return {
        "user_profile": {
            "id": "test-user-123",
            "displayName": "Test User",
            "givenName": "Test",
            "surname": "User",
            "mail": "test@example.com",
            "userPrincipalName": "test@example.com"
        },
        "mail_folders": {
            "value": [
                {
                    "id": "inbox",
                    "displayName": "Inbox",
                    "parentFolderId": "root",
                    "unreadItemCount": 5,
                    "totalItemCount": 25
                },
                {
                    "id": "sent",
                    "displayName": "Sent Items", 
                    "parentFolderId": "root",
                    "unreadItemCount": 0,
                    "totalItemCount": 10
                }
            ]
        },
        "messages": {
            "value": [
                {
                    "id": "message-123",
                    "subject": "Test Email",
                    "from": {
                        "emailAddress": {
                            "address": "sender@example.com",
                            "name": "Sender Name"
                        }
                    },
                    "receivedDateTime": "2024-01-01T12:00:00Z",
                    "isRead": False,
                    "hasAttachments": True
                }
            ]
        },
        "attachments": {
            "value": [
                {
                    "id": "attachment-123",
                    "name": "voicemail.wav",
                    "contentType": "audio/wav",
                    "size": 1024,
                    "isInline": False
                }
            ]
        }
    }


# =============================================================================
# HTTPX MOCKING FIXTURES
# =============================================================================

@pytest.fixture
def mock_httpx_responses(respx_mock, mock_graph_api_responses):
    """Set up common HTTPX response mocks."""
    base_url = "https://graph.microsoft.com/v1.0"
    
    # Mock user profile endpoint
    respx_mock.get(f"{base_url}/me").mock(
        return_value=httpx.Response(200, json=mock_graph_api_responses["user_profile"])
    )
    
    # Mock mail folders endpoint
    respx_mock.get(f"{base_url}/me/mailFolders").mock(
        return_value=httpx.Response(200, json=mock_graph_api_responses["mail_folders"])
    )
    
    # Mock messages endpoint
    respx_mock.get(f"{base_url}/me/messages").mock(
        return_value=httpx.Response(200, json=mock_graph_api_responses["messages"])
    )
    
    return respx_mock


# =============================================================================
# TEST DATA FACTORIES
# =============================================================================

class UserFactory:
    """Factory for creating test users."""
    
    @staticmethod
    def create(**kwargs) -> Dict[str, Any]:
        defaults = {
            "user_id": "test-user-123",
            "email": "test@example.com",
            "display_name": "Test User",
            "given_name": "Test",
            "surname": "User",
            "is_active": True,
        }
        defaults.update(kwargs)
        return defaults


class MailAccountFactory:
    """Factory for creating test mail accounts."""
    
    @staticmethod
    def create(**kwargs) -> Dict[str, Any]:
        defaults = {
            "user_id": "test-user-123",
            "email_address": "test@example.com",
            "account_type": "personal",
            "is_shared_mailbox": False,
            "display_name": "Test Account",
            "is_active": True,
        }
        defaults.update(kwargs)
        return defaults


class MailDataFactory:
    """Factory for creating test mail data."""
    
    @staticmethod
    def create(**kwargs) -> Dict[str, Any]:
        defaults = {
            "message_id": "test-message-123",
            "thread_id": "test-thread-123",
            "user_id": "test-user-123",
            "folder_id": "inbox",
            "subject": "Test Email Subject",
            "sender_email": "sender@example.com",
            "sender_name": "Test Sender",
            "received_datetime": datetime.utcnow(),
            "is_read": False,
            "has_attachments": False,
        }
        defaults.update(kwargs)
        return defaults


class VoiceAttachmentFactory:
    """Factory for creating test voice attachments."""
    
    @staticmethod
    def create(**kwargs) -> Dict[str, Any]:
        defaults = {
            "attachment_id": "test-attachment-123",
            "message_id": "test-message-123",
            "user_id": "test-user-123",
            "file_name": "voicemail.wav",
            "content_type": "audio/wav",
            "size_bytes": 1024,
            "blob_name": "test-blob-123.wav",
            "storage_account": "test-storage",
            "container_name": "voice-attachments",
        }
        defaults.update(kwargs)
        return defaults


# =============================================================================
# CLEANUP FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_environment():
    """Ensure clean environment for each test."""
    # Set test environment
    os.environ["ENV_FOR_DYNACONF"] = "testing"
    
    yield
    
    # Cleanup any environment changes
    # Reset any global state if needed


@pytest_asyncio.fixture
async def cleanup_database(test_db_session):
    """Clean up database after each test."""
    yield
    
    # Clean up test data
    await test_db_session.rollback()
    
    # Clear all tables
    for table in reversed(Base.metadata.sorted_tables):
        await test_db_session.execute(table.delete())
    await test_db_session.commit()


# =============================================================================
# TEST UTILITIES
# =============================================================================

@pytest.fixture
def assert_response_success():
    """Utility for asserting successful API responses."""
    def _assert_success(response: httpx.Response, expected_status: int = 200):
        assert response.status_code == expected_status
        if response.headers.get("content-type", "").startswith("application/json"):
            assert response.json() is not None
    return _assert_success


@pytest.fixture
def assert_response_error():
    """Utility for asserting API error responses."""
    def _assert_error(response: httpx.Response, expected_status: int, expected_message: Optional[str] = None):
        assert response.status_code == expected_status
        if expected_message and response.headers.get("content-type", "").startswith("application/json"):
            error_data = response.json()
            assert expected_message in error_data.get("message", "")
    return _assert_error


# =============================================================================
# ASYNC EVENT LOOP CONFIGURATION
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()