"""
Custom exceptions for Scribe Voice Email Processor
Production-ready exception hierarchy with proper error handling
"""

import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ScribeBaseException(Exception):
    """Base exception for all Scribe-related errors"""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.timestamp = time.time()
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp
        }
    
    def log_error(self, logger_instance: logging.Logger = None):
        """Log the exception with appropriate level"""
        log = logger_instance or logger
        log.error(f"{self.error_code}: {self.message}", extra={'details': self.details})

class AuthenticationError(ScribeBaseException):
    """Authentication-related errors"""
    pass

class OAuthTokenError(AuthenticationError):
    """OAuth token acquisition or refresh errors"""
    pass

class KeyVaultError(AuthenticationError):
    """Key Vault access errors"""
    pass

class ConfigurationError(ScribeBaseException):
    """Configuration-related errors"""
    pass

# Processing exceptions
class EmailProcessingError(ScribeBaseException):
    """Email processing errors"""
    pass

class EmailNotFoundError(EmailProcessingError):
    """Email not found or inaccessible"""
    pass

class AttachmentError(EmailProcessingError):
    """Email attachment processing errors"""
    pass

# Transcription exceptions
class TranscriptionError(ScribeBaseException):
    """Transcription service errors"""
    pass

class AudioFormatError(TranscriptionError):
    """Unsupported or invalid audio format"""
    pass

class TranscriptionServiceError(TranscriptionError):
    """Azure AI Speech service errors"""
    pass

# Excel/OneDrive exceptions
class ExcelProcessingError(ScribeBaseException):
    """Excel processing errors"""
    pass

class OneDriveError(ExcelProcessingError):
    """OneDrive access errors"""
    pass

class ExcelFileError(ExcelProcessingError):
    """Excel file operation errors"""
    pass

# Storage exceptions
class StorageError(ScribeBaseException):
    """Storage operation errors"""
    pass

class BlobStorageError(StorageError):
    """Azure Blob Storage errors"""
    pass

# Validation exceptions
class ValidationError(ScribeBaseException):
    """Data validation errors"""
    pass

class SecurityValidationError(ValidationError):
    """Security validation failures"""
    pass

# Workflow exceptions
class WorkflowError(ScribeBaseException):
    """Workflow execution errors"""
    pass

class WorkflowTimeoutError(WorkflowError):
    """Workflow execution timeout"""
    pass

class PartialWorkflowError(WorkflowError):
    """Workflow completed with some failures"""
    pass

# Network exceptions
class NetworkError(ScribeBaseException):
    """Network-related errors"""
    pass

class APITimeoutError(NetworkError):
    """API request timeout"""
    pass

class APIRateLimitError(NetworkError):
    """API rate limit exceeded"""
    pass

# Legacy compatibility - keep old names
ScribeException = ScribeBaseException  # For backward compatibility