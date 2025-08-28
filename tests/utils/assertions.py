"""Custom assertions for testing.

This module provides specialized assertion functions for:
- API response validation
- Database state verification
- Authentication assertions
- Mail and voice attachment assertions
- Azure service response validation
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class APIAssertions:
    """Assertions for API responses and HTTP interactions."""
    
    @staticmethod
    def assert_successful_response(response, expected_status: int = 200) -> None:
        """Assert that the response indicates success."""
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. "
            f"Response: {response.text if hasattr(response, 'text') else response}"
        )
    
    @staticmethod
    def assert_error_response(
        response,
        expected_status: int,
        expected_error_code: Optional[str] = None
    ) -> None:
        """Assert that the response indicates an error with expected details."""
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}"
        )
        
        if expected_error_code and hasattr(response, 'json'):
            try:
                error_data = response.json()
                if 'error' in error_data:
                    assert error_data['error']['code'] == expected_error_code, (
                        f"Expected error code {expected_error_code}, "
                        f"got {error_data['error'].get('code')}"
                    )
            except Exception:
                pytest.fail("Response does not contain expected error structure")
    
    @staticmethod
    def assert_json_response(response) -> Dict[str, Any]:
        """Assert response is valid JSON and return parsed data."""
        try:
            return response.json()
        except Exception as e:
            pytest.fail(f"Response is not valid JSON: {e}. Response text: {response.text}")
    
    @staticmethod
    def assert_response_has_fields(response_data: Dict[str, Any], required_fields: List[str]) -> None:
        """Assert that response data contains all required fields."""
        missing_fields = []
        for field in required_fields:
            if '.' in field:  # Nested field like 'user.email'
                parts = field.split('.')
                current = response_data
                for part in parts:
                    if not isinstance(current, dict) or part not in current:
                        missing_fields.append(field)
                        break
                    current = current[part]
            else:
                if field not in response_data:
                    missing_fields.append(field)
        
        assert not missing_fields, f"Missing required fields: {missing_fields}"
    
    @staticmethod
    def assert_pagination_response(
        response_data: Dict[str, Any],
        has_next_page: bool = False
    ) -> None:
        """Assert response follows pagination structure."""
        assert 'value' in response_data, "Pagination response must have 'value' field"
        assert isinstance(response_data['value'], list), "'value' must be a list"
        
        if has_next_page:
            assert '@odata.nextLink' in response_data, "Expected next page link"
        else:
            assert '@odata.nextLink' not in response_data, "Unexpected next page link"


class AuthAssertions:
    """Assertions for authentication and authorization."""
    
    @staticmethod
    def assert_valid_token_response(token_data: Dict[str, Any]) -> None:
        """Assert token response has valid structure."""
        required_fields = ['access_token', 'token_type', 'expires_in']
        for field in required_fields:
            assert field in token_data, f"Token response missing '{field}'"
        
        assert token_data['token_type'].lower() == 'bearer', (
            f"Expected Bearer token, got {token_data['token_type']}"
        )
        assert isinstance(token_data['expires_in'], int), "expires_in must be integer"
        assert token_data['expires_in'] > 0, "expires_in must be positive"
    
    @staticmethod
    def assert_valid_jwt_token(token: str) -> Dict[str, Any]:
        """Assert token is a valid JWT and return decoded claims."""
        import jwt
        try:
            # For testing, we skip signature verification
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Check for required claims
            required_claims = ['sub', 'exp', 'iat']
            for claim in required_claims:
                assert claim in decoded, f"JWT missing required claim '{claim}'"
            
            # Check expiration is in future
            exp_time = datetime.fromtimestamp(decoded['exp'])
            assert exp_time > datetime.utcnow(), "JWT token is expired"
            
            return decoded
        except jwt.InvalidTokenError as e:
            pytest.fail(f"Invalid JWT token: {e}")
    
    @staticmethod
    def assert_oauth_flow_state(flow_data: Dict[str, Any]) -> None:
        """Assert OAuth flow data has required fields."""
        required_fields = ['auth_uri', 'flow']
        for field in required_fields:
            assert field in flow_data, f"OAuth flow missing '{field}'"
        
        assert 'state' in flow_data['flow'], "OAuth flow missing state"
        assert flow_data['auth_uri'].startswith('https://'), "Auth URI must be HTTPS"
    
    @staticmethod
    def assert_user_profile(profile: Dict[str, Any]) -> None:
        """Assert user profile has required fields."""
        required_fields = ['id', 'email', 'displayName']
        for field in required_fields:
            assert field in profile, f"User profile missing '{field}'"
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        assert re.match(email_pattern, profile['email']), f"Invalid email format: {profile['email']}"


class DatabaseAssertions:
    """Assertions for database state and operations."""
    
    @staticmethod
    async def assert_record_exists(
        session: AsyncSession,
        model_class,
        **filters
    ) -> Any:
        """Assert that a record exists in database."""
        from sqlalchemy import select
        
        query = select(model_class)
        for key, value in filters.items():
            query = query.where(getattr(model_class, key) == value)
        
        result = await session.execute(query)
        record = result.scalar_one_or_none()
        
        assert record is not None, (
            f"No {model_class.__name__} found with filters: {filters}"
        )
        
        return record
    
    @staticmethod
    async def assert_record_does_not_exist(
        session: AsyncSession,
        model_class,
        **filters
    ) -> None:
        """Assert that a record does not exist in database."""
        from sqlalchemy import select
        
        query = select(model_class)
        for key, value in filters.items():
            query = query.where(getattr(model_class, key) == value)
        
        result = await session.execute(query)
        record = result.scalar_one_or_none()
        
        assert record is None, (
            f"Unexpected {model_class.__name__} found with filters: {filters}"
        )
    
    @staticmethod
    async def assert_record_count(
        session: AsyncSession,
        model_class,
        expected_count: int,
        **filters
    ) -> None:
        """Assert the count of records matching filters."""
        from sqlalchemy import select, func
        
        query = select(func.count()).select_from(model_class)
        for key, value in filters.items():
            query = query.where(getattr(model_class, key) == value)
        
        result = await session.execute(query)
        actual_count = result.scalar()
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} {model_class.__name__} records, "
            f"found {actual_count} with filters: {filters}"
        )
    
    @staticmethod
    def assert_model_fields(model_instance: Any, expected_values: Dict[str, Any]) -> None:
        """Assert that model instance has expected field values."""
        for field, expected_value in expected_values.items():
            actual_value = getattr(model_instance, field, None)
            assert actual_value == expected_value, (
                f"Expected {field}={expected_value}, got {actual_value}"
            )


class MailAssertions:
    """Assertions for mail and messaging functionality."""
    
    @staticmethod
    def assert_valid_mail_folder(folder_data: Dict[str, Any]) -> None:
        """Assert mail folder data has valid structure."""
        required_fields = ['id', 'displayName', 'totalItemCount', 'unreadItemCount']
        for field in required_fields:
            assert field in folder_data, f"Mail folder missing '{field}'"
        
        assert isinstance(folder_data['totalItemCount'], int), "totalItemCount must be integer"
        assert isinstance(folder_data['unreadItemCount'], int), "unreadItemCount must be integer"
        assert folder_data['unreadItemCount'] <= folder_data['totalItemCount'], (
            "Unread count cannot exceed total count"
        )
    
    @staticmethod
    def assert_valid_mail_message(message_data: Dict[str, Any]) -> None:
        """Assert mail message data has valid structure."""
        required_fields = [
            'id', 'subject', 'sender', 'receivedDateTime', 
            'hasAttachments', 'isRead'
        ]
        for field in required_fields:
            assert field in message_data, f"Mail message missing '{field}'"
        
        # Validate sender structure
        assert 'emailAddress' in message_data['sender'], "Sender missing emailAddress"
        assert 'address' in message_data['sender']['emailAddress'], "Sender missing email address"
        
        # Validate datetime format
        datetime_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z?$'
        assert re.match(datetime_pattern, message_data['receivedDateTime']), (
            f"Invalid receivedDateTime format: {message_data['receivedDateTime']}"
        )
    
    @staticmethod
    def assert_valid_attachment(attachment_data: Dict[str, Any]) -> None:
        """Assert attachment data has valid structure."""
        required_fields = ['id', 'name', 'contentType', 'size']
        for field in required_fields:
            assert field in attachment_data, f"Attachment missing '{field}'"
        
        assert isinstance(attachment_data['size'], int), "Size must be integer"
        assert attachment_data['size'] > 0, "Size must be positive"
    
    @staticmethod
    def assert_voice_message_properties(message_data: Dict[str, Any]) -> None:
        """Assert message has voice message characteristics."""
        MailAssertions.assert_valid_mail_message(message_data)
        
        assert message_data['hasAttachments'] is True, "Voice message must have attachments"
        
        # Check if subject indicates voice message
        voice_indicators = ['voice message', 'voice mail', 'voicemail']
        subject_lower = message_data['subject'].lower()
        has_voice_indicator = any(indicator in subject_lower for indicator in voice_indicators)
        
        assert has_voice_indicator, f"Subject doesn't indicate voice message: {message_data['subject']}"
    
    @staticmethod
    def assert_shared_mailbox_access(mailbox_data: Dict[str, Any]) -> None:
        """Assert shared mailbox data structure."""
        required_fields = ['id', 'displayName', 'mail']
        for field in required_fields:
            assert field in mailbox_data, f"Shared mailbox missing '{field}'"
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        assert re.match(email_pattern, mailbox_data['mail']), (
            f"Invalid mailbox email format: {mailbox_data['mail']}"
        )


class VoiceAttachmentAssertions:
    """Assertions for voice attachment functionality."""
    
    @staticmethod
    def assert_audio_content_type(content_type: str) -> None:
        """Assert content type is valid audio format."""
        valid_audio_types = [
            'audio/wav', 'audio/wave', 'audio/x-wav',
            'audio/mp3', 'audio/mpeg', 'audio/m4a', 
            'audio/aac', 'audio/ogg'
        ]
        
        assert content_type.lower() in valid_audio_types, (
            f"Invalid audio content type: {content_type}"
        )
    
    @staticmethod
    def assert_voice_attachment_metadata(metadata: Dict[str, Any]) -> None:
        """Assert voice attachment metadata structure."""
        required_fields = [
            'attachment_id', 'filename', 'content_type', 
            'size_bytes', 'duration_seconds'
        ]
        for field in required_fields:
            assert field in metadata, f"Voice metadata missing '{field}'"
        
        VoiceAttachmentAssertions.assert_audio_content_type(metadata['content_type'])
        
        assert isinstance(metadata['size_bytes'], int), "size_bytes must be integer"
        assert metadata['size_bytes'] > 0, "size_bytes must be positive"
        
        assert isinstance(metadata['duration_seconds'], (int, float)), "duration_seconds must be number"
        assert metadata['duration_seconds'] > 0, "duration_seconds must be positive"
    
    @staticmethod
    def assert_blob_storage_url(url: str) -> None:
        """Assert URL is valid Azure Blob Storage URL."""
        blob_patterns = [
            r'https://[\w\-]+\.blob\.core\.windows\.net/',
            r'https://[\w\-]+\.blob\.core\.usgovcloudapi\.net/',
            r'https://[\w\-]+\.blob\.core\.chinacloudapi\.cn/'
        ]
        
        is_valid = any(re.match(pattern, url) for pattern in blob_patterns)
        assert is_valid, f"Invalid Azure Blob Storage URL: {url}"
    
    @staticmethod
    def assert_audio_file_content(content: bytes, min_size: int = 44) -> None:
        """Assert content appears to be valid audio file."""
        assert len(content) >= min_size, f"Audio content too small: {len(content)} bytes"
        
        # Check for common audio file signatures
        audio_signatures = [
            b'RIFF',  # WAV
            b'ID3',   # MP3
            b'\xff\xfb',  # MP3
            b'\xff\xf3',  # MP3
            b'\xff\xf2',  # MP3
            b'OggS',  # OGG
            b'ftyp'   # M4A (occurs at byte 4)
        ]
        
        has_audio_signature = any(
            content.startswith(sig) or (sig == b'ftyp' and content[4:8] == sig)
            for sig in audio_signatures
        )
        
        assert has_audio_signature, "Content does not appear to be valid audio file"


class AzureAssertions:
    """Assertions for Azure service interactions."""
    
    @staticmethod
    def assert_graph_api_response(response_data: Dict[str, Any]) -> None:
        """Assert response follows Microsoft Graph API structure."""
        # Graph API responses typically have @odata.context
        if 'value' in response_data:  # Collection response
            assert '@odata.context' in response_data, "Graph collection response missing @odata.context"
            assert isinstance(response_data['value'], list), "Graph 'value' must be list"
        else:  # Single entity response
            # Single entities may or may not have @odata.context depending on endpoint
            pass
    
    @staticmethod
    def assert_graph_error_response(error_data: Dict[str, Any]) -> None:
        """Assert error response follows Graph API structure."""
        assert 'error' in error_data, "Graph error response missing 'error'"
        
        error = error_data['error']
        required_error_fields = ['code', 'message']
        for field in required_error_fields:
            assert field in error, f"Graph error missing '{field}'"
    
    @staticmethod
    def assert_blob_operation_success(operation_result: Any) -> None:
        """Assert blob operation completed successfully."""
        # For upload operations, result may be None (success)
        # For download operations, result should have content
        if operation_result is not None:
            # If it's a download result, check it has readable content
            if hasattr(operation_result, 'readall'):
                content = operation_result.readall()
                assert len(content) > 0, "Downloaded blob content is empty"


class PerformanceAssertions:
    """Assertions for performance requirements."""
    
    @staticmethod
    def assert_execution_time_under(max_seconds: float):
        """Decorator to assert function execution time."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import time
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                assert execution_time < max_seconds, (
                    f"Function {func.__name__} took {execution_time:.3f}s, "
                    f"expected under {max_seconds}s"
                )
                return result
            return wrapper
        return decorator
    
    @staticmethod
    def assert_memory_usage_under(max_mb: int):
        """Assert memory usage stays under limit during function execution."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                import tracemalloc
                tracemalloc.start()
                
                try:
                    result = func(*args, **kwargs)
                    current, peak = tracemalloc.get_traced_memory()
                    peak_mb = peak / (1024 * 1024)
                    
                    assert peak_mb < max_mb, (
                        f"Function {func.__name__} used {peak_mb:.1f}MB, "
                        f"expected under {max_mb}MB"
                    )
                    
                    return result
                finally:
                    tracemalloc.stop()
            return wrapper
        return decorator


# Convenience assertion functions
def assert_valid_uuid(uuid_string: str) -> None:
    """Assert string is valid UUID format."""
    import uuid
    try:
        uuid.UUID(uuid_string)
    except ValueError:
        pytest.fail(f"Invalid UUID format: {uuid_string}")


def assert_datetime_recent(dt: datetime, max_age_seconds: int = 60) -> None:
    """Assert datetime is recent (within max_age_seconds of now)."""
    time_diff = abs((datetime.utcnow() - dt).total_seconds())
    assert time_diff <= max_age_seconds, (
        f"Datetime {dt} is {time_diff:.1f}s old, expected within {max_age_seconds}s"
    )


def assert_list_contains_items(items: List[Any], expected_count: Optional[int] = None) -> None:
    """Assert list contains items and optionally check count."""
    assert isinstance(items, list), f"Expected list, got {type(items)}"
    assert len(items) > 0, "List is empty"
    
    if expected_count is not None:
        assert len(items) == expected_count, (
            f"Expected {expected_count} items, got {len(items)}"
        )