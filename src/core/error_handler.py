"""
Centralized error handling utilities for Scribe Voice Email Processor
Provides consistent error logging, formatting, and response creation
"""

import logging
from typing import Dict, Any, Optional
from .exceptions import ScribeException

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def log_error(error: Exception, context: str = "", extra_details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Log error with consistent format and return error info
        
        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            extra_details: Additional details to include in the error info
            
        Returns:
            Dict containing formatted error information
        """
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'timestamp': None  # Will be added by logging framework
        }
        
        # Add extra details
        if extra_details:
            error_info.update(extra_details)
        
        # Handle custom ScribeException with structured data
        if isinstance(error, ScribeException):
            error_info.update({
                'error_code': error.error_code,
                'details': error.details
            })
            
            # Log with appropriate level based on error type
            if error.error_code.startswith('AUTH'):
                logger.warning(f"🔐 Authentication Error in {context}: {error.message}", extra=error_info)
            elif error.error_code.startswith('CONFIG'):
                logger.error(f"⚙️ Configuration Error in {context}: {error.message}", extra=error_info)
            else:
                logger.error(f"❌ {error.error_code} in {context}: {error.message}", extra=error_info)
        else:
            # Standard exception logging
            logger.error(f"❌ {type(error).__name__} in {context}: {str(error)}", extra=error_info, exc_info=True)
        
        return error_info
    
    @staticmethod
    def create_error_response(error: Exception, context: str = "", status_code: int = 500) -> Dict[str, Any]:
        """
        Create standardized error response for API endpoints
        
        Args:
            error: The exception that occurred
            context: Additional context
            status_code: HTTP status code
            
        Returns:
            Dict containing error response data
        """
        error_info = ErrorHandler.log_error(error, context)
        
        # Create user-friendly response (don't expose internal details)
        response = {
            'status': 'error',
            'error_code': getattr(error, 'error_code', 'INTERNAL_ERROR'),
            'message': str(error),
            'timestamp': error_info.get('timestamp'),
            'status_code': status_code
        }
        
        # Add context if provided
        if context:
            response['context'] = context
            
        return response
    
    @staticmethod
    def handle_workflow_error(error: Exception, operation: str, email_subject: str = None) -> Dict[str, Any]:
        """
        Handle workflow-specific errors with additional context
        
        Args:
            error: The exception that occurred
            operation: The workflow operation that failed
            email_subject: Subject of email being processed (if applicable)
            
        Returns:
            Dict containing error information
        """
        extra_details = {
            'operation': operation,
            'workflow_step': True
        }
        
        if email_subject:
            extra_details['email_subject'] = email_subject[:100]  # Truncate for logging
            
        return ErrorHandler.log_error(error, f"Workflow/{operation}", extra_details)

# Convenience functions for common error scenarios
def handle_auth_error(error: Exception, context: str = "authentication") -> Dict[str, Any]:
    """Handle authentication errors"""
    return ErrorHandler.log_error(error, context)

def handle_config_error(error: Exception, missing_config: list = None) -> Dict[str, Any]:
    """Handle configuration errors"""
    extra_details = {'missing_config': missing_config} if missing_config else None
    return ErrorHandler.log_error(error, "configuration", extra_details)

def handle_api_error(error: Exception, endpoint: str, method: str = "GET") -> Dict[str, Any]:
    """Handle API-related errors"""
    extra_details = {'endpoint': endpoint, 'method': method}
    return ErrorHandler.log_error(error, f"API/{endpoint}", extra_details)