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
    ):
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
    ):
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
    ):
        super().__init__(message, error_code="AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(ScribeBaseException):
    """Raised when user is not authorized for action."""
    
    def __init__(
        self, 
        message: str = "Access denied",
        action: Optional[str] = None,
        resource: Optional[str] = None,
        **kwargs
    ):
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
    ):
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
    ):
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
    ):
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
    ):
        details = kwargs.get("details", {})
        details.update({"limit": limit, "window": window})
        
        super().__init__(message, error_code="RATE_LIMIT_ERROR", details=details)