"""Test helper functions and utilities.

This module provides common utilities for testing including:
- HTTP client helpers
- Authentication helpers
- Database helpers
- File and data manipulation helpers
- Async testing utilities
"""

import asyncio
import json
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from contextlib import contextmanager
from pathlib import Path
import httpx
import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class TestHTTPClient:
    """Helper for making HTTP requests in tests."""
    
    def __init__(self, base_url: str = "http://testserver", headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url
        self.headers = headers or {}
    
    def get_auth_headers(self, token: str = "test-access-token") -> Dict[str, str]:
        """Get authorization headers for authenticated requests."""
        return {
            **self.headers,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    async def make_request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        expected_status: int = 200
    ) -> httpx.Response:
        """Make an HTTP request with common test configuration."""
        headers = self.get_auth_headers(token) if token else self.headers
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"{self.base_url}{endpoint}",
                headers=headers,
                json=json_data,
                params=params
            )
            
            if expected_status is not None:
                assert response.status_code == expected_status, (
                    f"Expected status {expected_status}, got {response.status_code}. "
                    f"Response: {response.text}"
                )
            
            return response


class AuthTestHelper:
    """Helper for authentication-related testing."""
    
    @staticmethod
    def create_mock_token(
        user_id: str = "test-user-id",
        email: str = "test@example.com",
        expires_in: int = 3600,
        scopes: List[str] = None
    ) -> str:
        """Create a mock JWT token for testing."""
        import jwt
        
        scopes = scopes or ["User.Read", "Mail.Read", "Mail.ReadWrite"]
        
        payload = {
            "sub": user_id,
            "email": email,
            "name": "Test User",
            "exp": int((datetime.utcnow() + timedelta(seconds=expires_in)).timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "aud": "test-client-id",
            "iss": "https://login.microsoftonline.com/test-tenant/v2.0",
            "scp": " ".join(scopes)
        }
        
        return jwt.encode(payload, "test-secret", algorithm="HS256")
    
    @staticmethod
    def create_oauth_flow_state() -> Dict[str, str]:
        """Create OAuth flow state data for testing."""
        import uuid
        return {
            "state": f"state_{uuid.uuid4().hex[:8]}",
            "code_verifier": f"verifier_{uuid.uuid4().hex[:16]}",
            "nonce": f"nonce_{uuid.uuid4().hex[:8]}"
        }
    
    @staticmethod
    def mock_azure_auth_success() -> Dict[str, Any]:
        """Create a mock successful Azure authentication response."""
        return {
            "access_token": AuthTestHelper.create_mock_token(),
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "test-refresh-token",
            "scope": "User.Read Mail.Read Mail.ReadWrite",
            "id_token": "test-id-token"
        }


class DatabaseTestHelper:
    """Helper for database-related testing."""
    
    @staticmethod
    async def cleanup_database(session: AsyncSession) -> None:
        """Clean up all data from test database."""
        from sqlalchemy import text
        
        # Get all table names
        result = await session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ))
        tables = [row[0] for row in result.fetchall()]
        
        # Delete from all tables
        for table in tables:
            await session.execute(text(f"DELETE FROM {table}"))
        
        await session.commit()
    
    @staticmethod
    async def count_records(session: AsyncSession, model_class) -> int:
        """Count records in a table."""
        from sqlalchemy import select, func
        
        result = await session.execute(select(func.count()).select_from(model_class))
        return result.scalar()
    
    @staticmethod
    async def get_records(session: AsyncSession, model_class, **filters) -> List:
        """Get records from database with filters."""
        from sqlalchemy import select
        
        query = select(model_class)
        for key, value in filters.items():
            query = query.where(getattr(model_class, key) == value)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    @staticmethod
    def create_test_database_url() -> str:
        """Create a unique test database URL."""
        import uuid
        return f"sqlite+aiosqlite:///:memory:?cache=shared&uri=true&test_id={uuid.uuid4().hex[:8]}"


class FileTestHelper:
    """Helper for file-related testing operations."""
    
    @staticmethod
    def create_temp_audio_file(
        filename: str = "test_audio.wav",
        size_bytes: int = 1024,
        content: Optional[bytes] = None
    ) -> str:
        """Create a temporary audio file for testing."""
        if content is None:
            # Create minimal WAV header + dummy data
            wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00D\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\x00\x08\x00\x00'
            content = wav_header + b'\x00' * max(0, size_bytes - len(wav_header))
        
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return file_path
    
    @staticmethod
    def create_temp_json_file(data: Dict[str, Any], filename: str = "test_data.json") -> str:
        """Create a temporary JSON file for testing."""
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return file_path
    
    @staticmethod
    def cleanup_temp_file(file_path: str) -> None:
        """Clean up a temporary file and its directory."""
        try:
            os.remove(file_path)
            os.rmdir(os.path.dirname(file_path))
        except OSError:
            pass  # File or directory may not exist


class AsyncTestHelper:
    """Helper for async testing operations."""
    
    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run an async coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            pytest.fail(f"Operation timed out after {timeout} seconds")
    
    @staticmethod
    def create_async_mock(return_value: Any = None) -> AsyncMock:
        """Create an AsyncMock with optional return value."""
        mock = AsyncMock()
        if return_value is not None:
            mock.return_value = return_value
        return mock
    
    @staticmethod
    async def collect_async_generator(async_gen: AsyncGenerator) -> List[Any]:
        """Collect all items from an async generator."""
        items = []
        async for item in async_gen:
            items.append(item)
        return items


class MockingHelper:
    """Helper for creating and managing mocks."""
    
    @staticmethod
    def mock_httpx_response(
        status_code: int = 200,
        json_data: Optional[Dict] = None,
        text: Optional[str] = None,
        headers: Optional[Dict] = None
    ) -> Mock:
        """Create a mock httpx Response object."""
        response = Mock()
        response.status_code = status_code
        response.headers = headers or {}
        
        if json_data:
            response.json.return_value = json_data
            response.text = json.dumps(json_data)
        elif text:
            response.text = text
            response.json.side_effect = json.JSONDecodeError("No JSON", "", 0)
        else:
            response.text = ""
            response.json.return_value = {}
        
        return response
    
    @staticmethod
    def patch_settings(**overrides) -> patch:
        """Create a context manager to patch settings."""
        return patch.object(settings, **overrides)
    
    @staticmethod
    @contextmanager
    def mock_datetime_now(fixed_datetime: datetime):
        """Mock datetime.utcnow() to return a fixed datetime."""
        from unittest.mock import patch
        
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = fixed_datetime
            mock_datetime.now.return_value = fixed_datetime
            yield mock_datetime


class DataValidationHelper:
    """Helper for validating test data and responses."""
    
    @staticmethod
    def validate_api_response_structure(
        response: Dict[str, Any],
        required_fields: List[str],
        optional_fields: List[str] = None
    ) -> bool:
        """Validate that an API response has the required structure."""
        optional_fields = optional_fields or []
        
        # Check required fields
        for field in required_fields:
            assert field in response, f"Missing required field: {field}"
        
        # Check that there are no unexpected fields
        all_allowed_fields = set(required_fields + optional_fields)
        response_fields = set(response.keys())
        unexpected_fields = response_fields - all_allowed_fields
        
        assert not unexpected_fields, f"Unexpected fields in response: {unexpected_fields}"
        
        return True
    
    @staticmethod
    def validate_email_format(email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_uuid_format(uuid_string: str) -> bool:
        """Validate UUID format."""
        import uuid
        try:
            uuid.UUID(uuid_string)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_datetime_iso_format(datetime_string: str) -> bool:
        """Validate ISO datetime format."""
        try:
            datetime.fromisoformat(datetime_string.replace('Z', '+00:00'))
            return True
        except ValueError:
            return False


class PerformanceTestHelper:
    """Helper for performance testing."""
    
    @staticmethod
    def measure_execution_time(func, *args, **kwargs) -> tuple:
        """Measure function execution time."""
        import time
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        return result, execution_time
    
    @staticmethod
    async def measure_async_execution_time(coro) -> tuple:
        """Measure async function execution time."""
        import time
        start_time = time.time()
        result = await coro
        execution_time = time.time() - start_time
        return result, execution_time
    
    @staticmethod
    def assert_execution_time_under(max_time: float):
        """Decorator to assert that function executes under max_time seconds."""
        def decorator(func):
            if asyncio.iscoroutinefunction(func):
                async def async_wrapper(*args, **kwargs):
                    result, execution_time = await PerformanceTestHelper.measure_async_execution_time(
                        func(*args, **kwargs)
                    )
                    assert execution_time < max_time, (
                        f"Function {func.__name__} took {execution_time:.3f}s, "
                        f"expected under {max_time}s"
                    )
                    return result
                return async_wrapper
            else:
                def sync_wrapper(*args, **kwargs):
                    result, execution_time = PerformanceTestHelper.measure_execution_time(
                        func, *args, **kwargs
                    )
                    assert execution_time < max_time, (
                        f"Function {func.__name__} took {execution_time:.3f}s, "
                        f"expected under {max_time}s"
                    )
                    return result
                return sync_wrapper
        return decorator


class ConfigTestHelper:
    """Helper for configuration testing."""
    
    @staticmethod
    def create_test_settings(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create test settings with optional overrides."""
        default_settings = {
            "app_name": "Scribe API Test",
            "debug": True,
            "api_v1_prefix": "/api/v1",
            "database_url": "sqlite+aiosqlite:///:memory:",
            "secret_key": "test-secret-key-32-chars-long!!",
            "jwt_secret": "test-jwt-secret-key-32-chars!",
            "azure_tenant_id": "test-tenant-id",
            "azure_client_id": "test-client-id",
            "azure_client_secret": "test-client-secret",
            "cache_default_ttl": 60,
            "cache_max_size": 100
        }
        
        if overrides:
            default_settings.update(overrides)
        
        return default_settings
    
    @staticmethod
    def patch_test_settings(overrides: Dict[str, Any] = None):
        """Context manager to patch settings for testing."""
        test_settings = ConfigTestHelper.create_test_settings(overrides)
        
        patches = []
        for key, value in test_settings.items():
            patches.append(patch.object(settings, key, value))
        
        return patches


# Convenience functions for common test scenarios
def create_test_user_data(email: str = "test@example.com") -> Dict[str, Any]:
    """Create test user data dictionary."""
    return {
        "azure_user_id": "12345678-1234-1234-1234-123456789012",
        "email": email,
        "display_name": "Test User",
        "given_name": "Test",
        "surname": "User",
        "job_title": "Software Engineer",
        "is_active": True
    }


def create_test_mail_data(sender_email: str = "sender@example.com") -> Dict[str, Any]:
    """Create test mail data dictionary."""
    return {
        "message_id": "test-message-id-123",
        "subject": "Test Email Subject",
        "sender_email": sender_email,
        "sender_name": "Test Sender",
        "received_datetime": datetime.utcnow().isoformat(),
        "has_attachments": True,
        "is_read": False,
        "folder_name": "Inbox"
    }


def create_test_voice_attachment_data() -> Dict[str, Any]:
    """Create test voice attachment data dictionary."""
    return {
        "attachment_id": "test-attachment-id-123",
        "filename": "voice_recording.wav",
        "content_type": "audio/wav",
        "size_bytes": 1048576,
        "duration_seconds": 45.5,
        "is_stored": True
    }