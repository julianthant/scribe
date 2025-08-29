"""
exceptions.py - Custom Exception Classes

Defines custom exception classes for the Scribe application with consistent error handling.
This module provides:
- ScribeBaseException: Base exception class with error codes and details
- ValidationError: For input validation failures
- NotFoundError: For missing resources
- AuthenticationError: For authentication failures
- AuthorizationError: For permission/access issues
- DatabaseError: For database operation failures
- RateLimitError: For rate limiting violations
- ExternalServiceError: For third-party service issues

All exceptions include timestamps, error codes, and optional detail dictionaries
for structured error responses and debugging.
"""

from datetime import datetime
from typing import Optional, Dict, Any


class ScribeBaseException(Exception):
    """Base exception for Scribe application."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        super().__init__(message)


class ValidationError(ScribeBaseException):
    """Raised when input validation fails."""
    
    def __init__(
        self, 
        message: str = "Validation failed",
        field: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        if field:
            details["field"] = field
        super().__init__(message, error_code="VALIDATION_ERROR", details=details)


class NotFoundError(ScribeBaseException):
    """Raised when requested resource is not found."""
    
    def __init__(
        self, 
        resource: str,
        identifier: Optional[str] = None,
        **kwargs
    ) -> None:
        message = f"{resource} not found"
        if identifier:
            message += f" with identifier: {identifier}"
        
        details = kwargs.get("details", {})
        details.update({"resource": resource, "identifier": identifier})
        
        super().__init__(message, error_code="NOT_FOUND", details=details)


class AuthenticationError(ScribeBaseException):
    """Raised when authentication fails."""
    
    def __init__(
        self, 
        message: str = "Authentication failed",
        **kwargs
    ) -> None:
        super().__init__(message, error_code="AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(ScribeBaseException):
    """Raised when user is not authorized for action."""
    
    def __init__(
        self, 
        message: str = "Access denied",
        action: Optional[str] = None,
        resource: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        if action:
            details["action"] = action
        if resource:
            details["resource"] = resource
            
        super().__init__(message, error_code="AUTHORIZATION_ERROR", details=details)


class DuplicateError(ScribeBaseException):
    """Raised when attempting to create duplicate resource."""
    
    def __init__(
        self, 
        resource: str,
        field: Optional[str] = None,
        value: Optional[str] = None,
        **kwargs
    ) -> None:
        message = f"{resource} already exists"
        if field and value:
            message += f" with {field}: {value}"
            
        details = kwargs.get("details", {})
        details.update({"resource": resource, "field": field, "value": value})
        
        super().__init__(message, error_code="DUPLICATE_ERROR", details=details)


class DatabaseError(ScribeBaseException):
    """Raised when database operation fails."""
    
    def __init__(
        self, 
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        if operation:
            details["operation"] = operation
            
        super().__init__(message, error_code="DATABASE_ERROR", details=details)


class ExternalServiceError(ScribeBaseException):
    """Raised when external service operation fails."""
    
    def __init__(
        self, 
        service: str,
        message: str = "External service error",
        status_code: Optional[int] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        details.update({"service": service, "status_code": status_code})
        
        super().__init__(message, error_code="EXTERNAL_SERVICE_ERROR", details=details)


class RateLimitError(ScribeBaseException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[int] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        details.update({"limit": limit, "window": window})
        
        super().__init__(message, error_code="RATE_LIMIT_ERROR", details=details)


# Mail-specific exceptions

class MailNotFoundException(ScribeBaseException):
    """Raised when mail message or folder is not found."""
    
    def __init__(
        self, 
        resource_type: str,
        message: str = "Mail resource not found",
        resource_id: Optional[str] = None,
        **kwargs
    ) -> None:
        if resource_id:
            message = f"{resource_type} with ID {resource_id} not found"
        else:
            message = f"{resource_type} not found"
            
        details = kwargs.get("details", {})
        details.update({"resource_type": resource_type, "resource_id": resource_id})
        
        super().__init__(message, error_code="MAIL_NOT_FOUND", details=details)


class MailSendException(ScribeBaseException):
    """Raised when mail sending fails."""
    
    def __init__(
        self, 
        message: str = "Failed to send mail",
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        if recipient:
            details["recipient"] = recipient
        if subject:
            details["subject"] = subject
            
        super().__init__(message, error_code="MAIL_SEND_ERROR", details=details)


class AttachmentException(ScribeBaseException):
    """Raised when attachment operations fail."""
    
    def __init__(
        self, 
        message: str = "Attachment operation failed",
        attachment_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        if attachment_id:
            details["attachment_id"] = attachment_id
        if operation:
            details["operation"] = operation
            
        super().__init__(message, error_code="ATTACHMENT_ERROR", details=details)


class MailQuotaException(ScribeBaseException):
    """Raised when mail quota or limits are exceeded."""
    
    def __init__(
        self, 
        message: str = "Mail quota exceeded",
        quota_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs
    ) -> None:
        details = kwargs.get("details", {})
        details.update({
            "quota_type": quota_type,
            "current_usage": current_usage,
            "limit": limit
        })
        
        super().__init__(message, error_code="MAIL_QUOTA_ERROR", details=details)