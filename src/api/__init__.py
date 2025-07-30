"""
API module for Azure Function HTTP endpoints
Provides request handling, response building, and validation utilities
"""

# Export main functions for easier imports
from .handlers import (
    handle_auth_status,
    handle_process_emails,
    handle_list_voice_files,
    handle_download_voice_message
)
from .responses import (
    success_response,
    error_response,
    validation_error_response,
    create_success_response,
    create_error_response,
    create_simple_response,
    create_json_response
)

__all__ = [
    # Handlers
    'handle_auth_status',
    'handle_process_emails',
    'handle_list_voice_files',
    'handle_download_voice_message',
    # Responses
    'success_response',
    'error_response',
    'validation_error_response',
    'create_success_response',
    'create_error_response',
    'create_simple_response',
    'create_json_response'
]