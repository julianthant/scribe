"""
Helpers module for Scribe Voice Email Processor
Contains consolidated authentication system and utility functions
"""

# Export main functions from new auth manager
from .auth_manager import (
    initialize_authentication,
    get_access_token,
    make_graph_request,
    test_authentication,
    is_authenticated,
    get_auth_info,
    get_auth_health_status,
    get_auth_method
)

__all__ = [
    'initialize_authentication',
    'get_access_token',
    'make_graph_request', 
    'test_authentication',
    'is_authenticated',
    'get_auth_info',
    'get_auth_health_status',
    'get_auth_method'
]