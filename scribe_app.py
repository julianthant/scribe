"""
Scribe Application Entry Point
Provides clean imports without sys.path manipulation
Production-ready module for Azure Functions
"""

import os
import sys
from pathlib import Path

# Add src directory to path for clean imports
current_dir = Path(__file__).parent
src_dir = current_dir / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Now we can import everything cleanly
from helpers.auth_manager import (
    initialize_authentication,
    get_access_token,
    make_graph_request,
    test_authentication,
    is_authenticated,
    get_auth_info,
    get_auth_health_status
)

from core.components import (
    initialize_workflow,
    get_config,
    get_workflow_orchestrator,
    reset_components,
    get_component_status
)

from api.handlers import (
    handle_auth_status,
    handle_process_emails,
    handle_list_voice_files,
    handle_download_voice_message
)

from api.responses import (
    success_response,
    error_response,
    validation_error_response
)

# Export all the functions that function_app.py needs
__all__ = [
    # Authentication
    'initialize_authentication',
    'get_access_token', 
    'make_graph_request',
    'test_authentication',
    'is_authenticated',
    'get_auth_info',
    'get_auth_health_status',
    'store_oauth_tokens',
    
    # Core components
    'initialize_workflow',
    'get_config',
    'get_workflow_orchestrator', 
    'reset_components',
    'get_component_status',
    
    # API handlers
    'handle_auth_status',
    'handle_process_emails',
    'handle_list_voice_files', 
    'handle_download_voice_message',
    
    # API responses
    'success_response',
    'error_response',
    'validation_error_response'
]

def store_oauth_tokens(access_token: str, refresh_token: str) -> bool:
    """Store OAuth tokens in Key Vault"""
    try:
        from helpers.auth_providers import KeyVaultTokenStorage
        
        # Initialize Key Vault storage
        keyvault_storage = KeyVaultTokenStorage()
        
        # Store the refresh token (access tokens are short-lived)
        if refresh_token:
            result = keyvault_storage.store_refresh_token(refresh_token)
            if result:
                return True
        
        return False
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Failed to store OAuth tokens: {e}")
        return False

def get_application_info():
    """Get application information for health checks"""
    return {
        'name': 'Scribe Voice Email Processor',
        'version': '2.0.0',
        'description': 'Production-ready Azure Functions app for voice email processing',
        'auth_status': get_auth_health_status(),
        'component_status': get_component_status()
    }