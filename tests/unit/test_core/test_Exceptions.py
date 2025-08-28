"""
Unit tests for app.core.Exceptions module.

Tests cover:
- ScribeBaseException and all derived exception classes
- Exception initialization with messages, error codes, and details
- Timestamp functionality
- Mail-specific exception classes
- Exception inheritance hierarchy
"""

import pytest
from datetime import datetime
from unittest.mock import patch

from app.core.Exceptions import (
    ScribeBaseException,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    DuplicateError,
    DatabaseError,
    ExternalServiceError,
    RateLimitError,
    MailNotFoundException,
    MailSendException,
    AttachmentException,
    MailQuotaException
)


class TestScribeBaseException:
    """Test ScribeBaseException base class functionality."""

    def test_basic_initialization(self):
        """Test basic exception initialization with message only."""
        exception = ScribeBaseException("Test error message")
        
        assert str(exception) == "Test error message"
        assert exception.message == "Test error message"
        assert exception.error_code is None
        assert exception.details == {}
        assert isinstance(exception.timestamp, datetime)

    def test_initialization_with_error_code(self):
        """Test exception initialization with error code."""
        exception = ScribeBaseException(
            "Test error message",
            error_code="TEST_ERROR"
        )
        
        assert exception.message == "Test error message"
        assert exception.error_code == "TEST_ERROR"
        assert exception.details == {}

    def test_initialization_with_details(self):
        """Test exception initialization with details dictionary."""
        details = {"field": "email", "value": "invalid@"}
        exception = ScribeBaseException(
            "Test error message",
            error_code="TEST_ERROR",
            details=details
        )
        
        assert exception.message == "Test error message"
        assert exception.error_code == "TEST_ERROR"
        assert exception.details == details

    def test_initialization_with_none_details(self):
        """Test exception initialization with None details."""
        exception = ScribeBaseException(
            "Test error message",
            details=None
        )
        
        assert exception.details == {}

    def test_timestamp_creation(self):
        """Test that timestamp is automatically created."""
        with patch('app.core.Exceptions.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 12, 0, 0)
            
            exception = ScribeBaseException("Test message")
            
            assert exception.timestamp == datetime(2023, 1, 1, 12, 0, 0)
            mock_datetime.utcnow.assert_called_once()

    def test_inheritance_from_exception(self):
        """Test that ScribeBaseException inherits from Exception."""
        exception = ScribeBaseException("Test message")
        
        assert isinstance(exception, Exception)
        assert issubclass(ScribeBaseException, Exception)


class TestValidationError:
    """Test ValidationError class functionality."""

    def test_basic_initialization(self):
        """Test basic ValidationError initialization."""
        error = ValidationError()
        
        assert error.message == "Validation failed"
        assert error.error_code == "VALIDATION_ERROR"
        assert isinstance(error.details, dict)

    def test_initialization_with_custom_message(self):
        """Test ValidationError with custom message."""
        error = ValidationError("Custom validation message")
        
        assert error.message == "Custom validation message"
        assert error.error_code == "VALIDATION_ERROR"

    def test_initialization_with_field(self):
        """Test ValidationError with field parameter."""
        error = ValidationError("Invalid email format", field="email")
        
        assert error.message == "Invalid email format"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.details["field"] == "email"

    def test_initialization_with_field_and_details(self):
        """Test ValidationError with both field and additional details."""
        additional_details = {"pattern": "^[^@]+@[^@]+$"}
        error = ValidationError(
            "Invalid email format",
            field="email",
            details=additional_details
        )
        
        assert error.details["field"] == "email"
        assert error.details["pattern"] == "^[^@]+@[^@]+$"

    def test_inheritance_from_base_exception(self):
        """Test that ValidationError inherits from ScribeBaseException."""
        error = ValidationError()
        
        assert isinstance(error, ScribeBaseException)
        assert isinstance(error, Exception)


class TestNotFoundError:
    """Test NotFoundError class functionality."""

    def test_initialization_with_resource_only(self):
        """Test NotFoundError with resource parameter only."""
        error = NotFoundError("User")
        
        assert error.message == "User not found"
        assert error.error_code == "NOT_FOUND"
        assert error.details["resource"] == "User"
        assert error.details["identifier"] is None

    def test_initialization_with_resource_and_identifier(self):
        """Test NotFoundError with both resource and identifier."""
        error = NotFoundError("User", identifier="user123")
        
        assert error.message == "User not found with identifier: user123"
        assert error.error_code == "NOT_FOUND"
        assert error.details["resource"] == "User"
        assert error.details["identifier"] == "user123"

    def test_initialization_with_additional_details(self):
        """Test NotFoundError with additional details."""
        additional_details = {"table": "users", "query": "SELECT * FROM users"}
        error = NotFoundError(
            "User",
            identifier="user123",
            details=additional_details
        )
        
        assert error.details["resource"] == "User"
        assert error.details["identifier"] == "user123"
        assert error.details["table"] == "users"
        assert error.details["query"] == "SELECT * FROM users"


class TestAuthenticationError:
    """Test AuthenticationError class functionality."""

    def test_default_initialization(self):
        """Test AuthenticationError with default message."""
        error = AuthenticationError()
        
        assert error.message == "Authentication failed"
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_initialization_with_custom_message(self):
        """Test AuthenticationError with custom message."""
        error = AuthenticationError("Invalid credentials")
        
        assert error.message == "Invalid credentials"
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_initialization_with_details(self):
        """Test AuthenticationError with additional details."""
        details = {"user": "john@example.com", "reason": "password_expired"}
        error = AuthenticationError("Authentication failed", details=details)
        
        assert error.details == details


class TestAuthorizationError:
    """Test AuthorizationError class functionality."""

    def test_default_initialization(self):
        """Test AuthorizationError with default message."""
        error = AuthorizationError()
        
        assert error.message == "Access denied"
        assert error.error_code == "AUTHORIZATION_ERROR"

    def test_initialization_with_action(self):
        """Test AuthorizationError with action parameter."""
        error = AuthorizationError("Access denied", action="delete")
        
        assert error.message == "Access denied"
        assert error.details["action"] == "delete"
        assert "resource" not in error.details

    def test_initialization_with_resource(self):
        """Test AuthorizationError with resource parameter."""
        error = AuthorizationError("Access denied", resource="User")
        
        assert error.message == "Access denied"
        assert error.details["resource"] == "User"
        assert "action" not in error.details

    def test_initialization_with_action_and_resource(self):
        """Test AuthorizationError with both action and resource."""
        error = AuthorizationError(
            "Access denied",
            action="delete",
            resource="User"
        )
        
        assert error.details["action"] == "delete"
        assert error.details["resource"] == "User"


class TestDuplicateError:
    """Test DuplicateError class functionality."""

    def test_initialization_with_resource_only(self):
        """Test DuplicateError with resource parameter only."""
        error = DuplicateError("User")
        
        assert error.message == "User already exists"
        assert error.error_code == "DUPLICATE_ERROR"
        assert error.details["resource"] == "User"
        assert error.details["field"] is None
        assert error.details["value"] is None

    def test_initialization_with_field_and_value(self):
        """Test DuplicateError with field and value parameters."""
        error = DuplicateError("User", field="email", value="john@example.com")
        
        assert error.message == "User already exists with email: john@example.com"
        assert error.details["resource"] == "User"
        assert error.details["field"] == "email"
        assert error.details["value"] == "john@example.com"

    def test_initialization_with_additional_details(self):
        """Test DuplicateError with additional details."""
        additional_details = {"table": "users", "constraint": "unique_email"}
        error = DuplicateError(
            "User",
            field="email",
            value="john@example.com",
            details=additional_details
        )
        
        assert error.details["resource"] == "User"
        assert error.details["field"] == "email"
        assert error.details["value"] == "john@example.com"
        assert error.details["table"] == "users"
        assert error.details["constraint"] == "unique_email"


class TestDatabaseError:
    """Test DatabaseError class functionality."""

    def test_default_initialization(self):
        """Test DatabaseError with default message."""
        error = DatabaseError()
        
        assert error.message == "Database operation failed"
        assert error.error_code == "DATABASE_ERROR"

    def test_initialization_with_custom_message(self):
        """Test DatabaseError with custom message."""
        error = DatabaseError("Connection timeout")
        
        assert error.message == "Connection timeout"
        assert error.error_code == "DATABASE_ERROR"

    def test_initialization_with_operation(self):
        """Test DatabaseError with operation parameter."""
        error = DatabaseError("Query failed", operation="SELECT")
        
        assert error.message == "Query failed"
        assert error.details["operation"] == "SELECT"

    def test_initialization_with_operation_and_details(self):
        """Test DatabaseError with operation and additional details."""
        additional_details = {"table": "users", "query": "SELECT * FROM users"}
        error = DatabaseError(
            "Query failed",
            operation="SELECT",
            details=additional_details
        )
        
        assert error.details["operation"] == "SELECT"
        assert error.details["table"] == "users"
        assert error.details["query"] == "SELECT * FROM users"


class TestExternalServiceError:
    """Test ExternalServiceError class functionality."""

    def test_initialization_with_service_only(self):
        """Test ExternalServiceError with service parameter only."""
        error = ExternalServiceError("Azure AD")
        
        assert error.message == "External service error"
        assert error.error_code == "EXTERNAL_SERVICE_ERROR"
        assert error.details["service"] == "Azure AD"
        assert error.details["status_code"] is None

    def test_initialization_with_custom_message(self):
        """Test ExternalServiceError with custom message."""
        error = ExternalServiceError("Azure AD", "Authentication service unavailable")
        
        assert error.message == "Authentication service unavailable"
        assert error.details["service"] == "Azure AD"

    def test_initialization_with_status_code(self):
        """Test ExternalServiceError with status code."""
        error = ExternalServiceError(
            "Azure AD",
            "Service unavailable",
            status_code=503
        )
        
        assert error.message == "Service unavailable"
        assert error.details["service"] == "Azure AD"
        assert error.details["status_code"] == 503

    def test_initialization_with_additional_details(self):
        """Test ExternalServiceError with additional details."""
        additional_details = {"endpoint": "/oauth/token", "retry_after": 300}
        error = ExternalServiceError(
            "Azure AD",
            "Rate limited",
            status_code=429,
            details=additional_details
        )
        
        assert error.details["service"] == "Azure AD"
        assert error.details["status_code"] == 429
        assert error.details["endpoint"] == "/oauth/token"
        assert error.details["retry_after"] == 300


class TestRateLimitError:
    """Test RateLimitError class functionality."""

    def test_default_initialization(self):
        """Test RateLimitError with default message."""
        error = RateLimitError()
        
        assert error.message == "Rate limit exceeded"
        assert error.error_code == "RATE_LIMIT_ERROR"
        assert error.details["limit"] is None
        assert error.details["window"] is None

    def test_initialization_with_limit_and_window(self):
        """Test RateLimitError with limit and window parameters."""
        error = RateLimitError(
            "API rate limit exceeded",
            limit=100,
            window=3600
        )
        
        assert error.message == "API rate limit exceeded"
        assert error.details["limit"] == 100
        assert error.details["window"] == 3600

    def test_initialization_with_additional_details(self):
        """Test RateLimitError with additional details."""
        additional_details = {"endpoint": "/api/users", "retry_after": 600}
        error = RateLimitError(
            "Rate limit exceeded",
            limit=100,
            window=3600,
            details=additional_details
        )
        
        assert error.details["limit"] == 100
        assert error.details["window"] == 3600
        assert error.details["endpoint"] == "/api/users"
        assert error.details["retry_after"] == 600


class TestMailNotFoundException:
    """Test MailNotFoundException class functionality."""

    def test_initialization_with_resource_type_only(self):
        """Test MailNotFoundException with resource_type only."""
        error = MailNotFoundException("Message")
        
        assert error.message == "Message not found"
        assert error.error_code == "MAIL_NOT_FOUND"
        assert error.details["resource_type"] == "Message"
        assert error.details["resource_id"] is None

    def test_initialization_with_custom_message(self):
        """Test MailNotFoundException with custom message."""
        error = MailNotFoundException("Folder", "Custom folder not found")
        
        assert error.message == "Custom folder not found"
        assert error.details["resource_type"] == "Folder"

    def test_initialization_with_resource_id(self):
        """Test MailNotFoundException with resource_id."""
        error = MailNotFoundException("Message", resource_id="msg123")
        
        assert error.message == "Message with ID msg123 not found"
        assert error.details["resource_type"] == "Message"
        assert error.details["resource_id"] == "msg123"

    def test_initialization_without_resource_id(self):
        """Test MailNotFoundException message formatting without resource_id."""
        error = MailNotFoundException("Folder")
        
        assert error.message == "Folder not found"
        assert error.details["resource_type"] == "Folder"
        assert error.details["resource_id"] is None


class TestMailSendException:
    """Test MailSendException class functionality."""

    def test_default_initialization(self):
        """Test MailSendException with default message."""
        error = MailSendException()
        
        assert error.message == "Failed to send mail"
        assert error.error_code == "MAIL_SEND_ERROR"

    def test_initialization_with_recipient(self):
        """Test MailSendException with recipient parameter."""
        error = MailSendException("Send failed", recipient="john@example.com")
        
        assert error.message == "Send failed"
        assert error.details["recipient"] == "john@example.com"
        assert "subject" not in error.details

    def test_initialization_with_subject(self):
        """Test MailSendException with subject parameter."""
        error = MailSendException("Send failed", subject="Important Message")
        
        assert error.message == "Send failed"
        assert error.details["subject"] == "Important Message"
        assert "recipient" not in error.details

    def test_initialization_with_recipient_and_subject(self):
        """Test MailSendException with both recipient and subject."""
        error = MailSendException(
            "Send failed",
            recipient="john@example.com",
            subject="Important Message"
        )
        
        assert error.details["recipient"] == "john@example.com"
        assert error.details["subject"] == "Important Message"

    def test_initialization_with_additional_details(self):
        """Test MailSendException with additional details."""
        additional_details = {"smtp_error": "550 Mailbox unavailable"}
        error = MailSendException(
            "SMTP error",
            recipient="john@example.com",
            details=additional_details
        )
        
        assert error.details["recipient"] == "john@example.com"
        assert error.details["smtp_error"] == "550 Mailbox unavailable"


class TestAttachmentException:
    """Test AttachmentException class functionality."""

    def test_default_initialization(self):
        """Test AttachmentException with default message."""
        error = AttachmentException()
        
        assert error.message == "Attachment operation failed"
        assert error.error_code == "ATTACHMENT_ERROR"

    def test_initialization_with_attachment_id(self):
        """Test AttachmentException with attachment_id parameter."""
        error = AttachmentException(
            "Download failed",
            attachment_id="att123"
        )
        
        assert error.message == "Download failed"
        assert error.details["attachment_id"] == "att123"
        assert "operation" not in error.details

    def test_initialization_with_operation(self):
        """Test AttachmentException with operation parameter."""
        error = AttachmentException(
            "Operation failed",
            operation="download"
        )
        
        assert error.message == "Operation failed"
        assert error.details["operation"] == "download"
        assert "attachment_id" not in error.details

    def test_initialization_with_attachment_id_and_operation(self):
        """Test AttachmentException with both attachment_id and operation."""
        error = AttachmentException(
            "Upload failed",
            attachment_id="att123",
            operation="upload"
        )
        
        assert error.details["attachment_id"] == "att123"
        assert error.details["operation"] == "upload"

    def test_initialization_with_additional_details(self):
        """Test AttachmentException with additional details."""
        additional_details = {"file_size": 1024000, "max_size": 512000}
        error = AttachmentException(
            "File too large",
            attachment_id="att123",
            operation="upload",
            details=additional_details
        )
        
        assert error.details["attachment_id"] == "att123"
        assert error.details["operation"] == "upload"
        assert error.details["file_size"] == 1024000
        assert error.details["max_size"] == 512000


class TestMailQuotaException:
    """Test MailQuotaException class functionality."""

    def test_default_initialization(self):
        """Test MailQuotaException with default message."""
        error = MailQuotaException()
        
        assert error.message == "Mail quota exceeded"
        assert error.error_code == "MAIL_QUOTA_ERROR"
        assert error.details["quota_type"] is None
        assert error.details["current_usage"] is None
        assert error.details["limit"] is None

    def test_initialization_with_quota_parameters(self):
        """Test MailQuotaException with quota-related parameters."""
        error = MailQuotaException(
            "Storage quota exceeded",
            quota_type="storage",
            current_usage=1024000,
            limit=1000000
        )
        
        assert error.message == "Storage quota exceeded"
        assert error.details["quota_type"] == "storage"
        assert error.details["current_usage"] == 1024000
        assert error.details["limit"] == 1000000

    def test_initialization_with_additional_details(self):
        """Test MailQuotaException with additional details."""
        additional_details = {"mailbox": "john@example.com", "unit": "bytes"}
        error = MailQuotaException(
            "Storage quota exceeded",
            quota_type="storage",
            current_usage=1024000,
            limit=1000000,
            details=additional_details
        )
        
        assert error.details["quota_type"] == "storage"
        assert error.details["current_usage"] == 1024000
        assert error.details["limit"] == 1000000
        assert error.details["mailbox"] == "john@example.com"
        assert error.details["unit"] == "bytes"


class TestExceptionInheritance:
    """Test exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from ScribeBaseException."""
        exception_classes = [
            ValidationError,
            NotFoundError,
            AuthenticationError,
            AuthorizationError,
            DuplicateError,
            DatabaseError,
            ExternalServiceError,
            RateLimitError,
            MailNotFoundException,
            MailSendException,
            AttachmentException,
            MailQuotaException
        ]
        
        for exception_class in exception_classes:
            assert issubclass(exception_class, ScribeBaseException)
            assert issubclass(exception_class, Exception)

    def test_exception_instances_have_common_interface(self):
        """Test that all exception instances have common interface."""
        exceptions = [
            ValidationError("test"),
            NotFoundError("Resource"),
            AuthenticationError("test"),
            AuthorizationError("test"),
            DuplicateError("Resource"),
            DatabaseError("test"),
            ExternalServiceError("Service"),
            RateLimitError("test"),
            MailNotFoundException("Message"),
            MailSendException("test"),
            AttachmentException("test"),
            MailQuotaException("test")
        ]
        
        for exception in exceptions:
            assert hasattr(exception, 'message')
            assert hasattr(exception, 'error_code')
            assert hasattr(exception, 'details')
            assert hasattr(exception, 'timestamp')
            assert isinstance(exception.details, dict)
            assert isinstance(exception.timestamp, datetime)

    def test_exception_error_codes_are_unique(self):
        """Test that different exception types have unique error codes."""
        exceptions = [
            ValidationError("test"),
            NotFoundError("Resource"),
            AuthenticationError("test"),
            AuthorizationError("test"),
            DuplicateError("Resource"),
            DatabaseError("test"),
            ExternalServiceError("Service"),
            RateLimitError("test"),
            MailNotFoundException("Message"),
            MailSendException("test"),
            AttachmentException("test"),
            MailQuotaException("test")
        ]
        
        error_codes = [exc.error_code for exc in exceptions if exc.error_code is not None]
        
        # All error codes should be unique
        assert len(error_codes) == len(set(error_codes))

    def test_exception_string_representation(self):
        """Test that exceptions have proper string representation."""
        exception = ValidationError("Invalid email format")
        
        # Should use the message as string representation
        assert str(exception) == "Invalid email format"

    def test_exception_can_be_raised_and_caught(self):
        """Test that exceptions can be properly raised and caught."""
        # Test raising and catching specific exception
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Test validation error")
        
        assert str(exc_info.value) == "Test validation error"
        
        # Test catching as base exception
        with pytest.raises(ScribeBaseException):
            raise ValidationError("Test validation error")
        
        # Test catching as generic Exception
        with pytest.raises(Exception):
            raise ValidationError("Test validation error")