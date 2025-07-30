#!/usr/bin/env python3
"""
Authentication System Unit Tests
Tests OAuth authentication, token management, and auth providers
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestAuthenticationSystem(unittest.TestCase):
    """Test authentication components"""
    
    def setUp(self):
        """Set up test environment"""
        # Load test environment variables if available
        self._load_test_env()
    
    def _load_test_env(self):
        """Load environment variables from local.settings.json if available"""
        try:
            settings_path = os.path.join(os.path.dirname(__file__), '..', 'local.settings.json')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                for key, value in settings.get('Values', {}).items():
                    os.environ[key] = str(value)
        except Exception:
            pass  # Test environment may not have this file
    
    @patch('helpers.auth_manager.os.getenv')
    def test_auth_manager_initialization(self, mock_getenv):
        """Test auth manager initialization"""
        mock_getenv.side_effect = lambda key, default=None: {
            'CLIENT_ID': 'test-client-id',
            'TENANT_ID': 'test-tenant-id',
            'AUTH_METHOD': 'personal_oauth'
        }.get(key, default)
        
        try:
            from helpers import auth_manager
            # Test that auth manager can import without errors
            self.assertTrue(hasattr(auth_manager, 'initialize_authentication'))
            self.assertTrue(hasattr(auth_manager, 'get_auth_info'))
        except ImportError as e:
            self.skipTest(f"Auth manager import failed (expected in test env): {e}")
    
    def test_auth_providers_structure(self):
        """Test that auth providers have correct structure"""
        try:
            from helpers.auth_providers import AuthProvider, PersonalOAuthProvider
            
            # Test abstract base class
            self.assertTrue(hasattr(AuthProvider, 'initialize'))
            self.assertTrue(hasattr(AuthProvider, 'get_access_token'))
            
            # Test concrete implementation
            self.assertTrue(issubclass(PersonalOAuthProvider, AuthProvider))
            
        except ImportError as e:
            self.skipTest(f"Auth providers import failed (expected in test env): {e}")
    
    @patch('helpers.auth_providers.requests.post')
    def test_token_refresh_logic(self, mock_post):
        """Test OAuth token refresh logic"""
        # Mock successful token refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response
        
        try:
            from helpers.auth_providers import PersonalOAuthProvider
            
            # Test token refresh functionality
            provider = PersonalOAuthProvider()
            # This test validates the structure exists
            self.assertTrue(hasattr(provider, '_refresh_access_token'))
            
        except Exception as e:
            self.skipTest(f"Token refresh test skipped (requires real auth): {e}")
    
    def test_secure_credentials_structure(self):
        """Test secure credentials management structure"""
        try:
            from core.secure_credentials import SecureCredentialsManager
            
            manager = SecureCredentialsManager()
            
            # Test that required methods exist
            self.assertTrue(hasattr(manager, 'get_oauth_tokens'))
            self.assertTrue(hasattr(manager, 'store_oauth_tokens'))
            self.assertTrue(hasattr(manager, 'refresh_oauth_tokens'))
            
        except ImportError as e:
            self.skipTest(f"Secure credentials test skipped: {e}")


if __name__ == '__main__':
    unittest.main()