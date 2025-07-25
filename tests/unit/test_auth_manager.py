"""
Unit tests for PersistentAuthManager
Tests token caching, refresh, and multi-service authentication
"""

import pytest
import tempfile
import json
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.helpers.auth_helpers import PersistentAuthManager, get_auth_manager


class TestPersistentAuthManager:
    """Test suite for PersistentAuthManager"""
    
    def setup_method(self):
        """Setup test environment with temporary cache file"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, "test_tokens.json")
        self.client_id = "test-client-id"
        
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_auth_manager_initialization(self):
        """Test auth manager initializes correctly"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Test initialization
        assert auth_manager.client_id == self.client_id
        assert str(auth_manager.cache_file) == self.cache_file
        assert auth_manager._token_cache == {}
    
    def test_token_cache_save_and_load(self):
        """Test token cache persistence"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Create test token data with correct cache key format
        cache_key = f"graph_{self.client_id}"
        test_token_data = {
            cache_key: {
                "token": "test-token-123",
                "expires_at": "2025-07-24T16:00:00Z",
                "scope": "graph"
            }
        }
        
        # Save token cache
        auth_manager._token_cache = test_token_data
        auth_manager._save_token_cache()
        
        # Verify file exists and contains correct data
        assert os.path.exists(self.cache_file)
        
        with open(self.cache_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data == test_token_data
        
        # Test loading
        # Test loading - should contain the saved data
        new_auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        assert new_auth_manager._token_cache == test_token_data
    
    @patch('src.helpers.auth_helpers.ManagedIdentityCredential')
    def test_get_token_new_token(self, mock_credential):
        """Test getting new token when none exists"""
        # Mock credential and token
        mock_token = Mock()
        mock_token.token = "new-test-token"
        mock_token.expires_on = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        
        mock_credential_instance = Mock()
        mock_credential_instance.get_token.return_value = mock_token
        mock_credential.return_value = mock_credential_instance
        
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Get token for graph service
        token = auth_manager.get_token('graph')
        
        assert token == "new-test-token"
        # Cache key format is: scope_client_id  
        cache_key = f"graph_{self.client_id}"
        assert cache_key in auth_manager._token_cache
        assert auth_manager._token_cache[cache_key]['token'] == "new-test-token"
    
    def test_get_token_cached_valid(self):
        """Test getting cached token that's still valid"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Set up valid cached token
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        cache_key = f"graph_{self.client_id}"
        auth_manager._token_cache = {
            cache_key: {
                "token": "cached-token",
                "expires_at": future_time.isoformat(),
                "scope": "graph"
            }
        }
        
        token = auth_manager.get_token('graph')
        assert token == "cached-token"
    
    def test_get_auth_headers(self):
        """Test getting authentication headers"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Mock get_token method
        with patch.object(auth_manager, 'get_token', return_value="test-auth-token"):
            headers = auth_manager.get_auth_headers('graph')
        
        expected_headers = {
            'Authorization': 'Bearer test-auth-token',
            'Content-Type': 'application/json'
        }
        
        assert headers == expected_headers
    
    def test_is_token_valid_expired(self):
        """Test token validation for expired token"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Create expired token
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        token_data = {
            "token": "expired-token",
            "expires_at": past_time.isoformat(),
            "scope": "test-scope"
        }
        
        assert not auth_manager._is_token_valid(token_data)
    
    def test_is_token_valid_valid(self):
        """Test token validation for valid token"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Create valid token
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        token_data = {
            "token": "valid-token",
            "expires_at": future_time.isoformat(),
            "scope": "test-scope"
        }
        
        assert auth_manager._is_token_valid(token_data)
    
    def test_get_auth_manager_singleton(self):
        """Test that get_auth_manager returns singleton instance"""
        with patch.dict(os.environ, {'AZURE_CLIENT_ID': 'test-client'}):
            manager1 = get_auth_manager()
            manager2 = get_auth_manager()
            
            assert manager1 is manager2
    
    def test_clear_cache(self):
        """Test cache clearing functionality"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Add some data
        auth_manager._token_cache = {"test": "data"}
        auth_manager._save_token_cache()
        
        # Clear cache
        auth_manager.clear_cache()
        
        assert auth_manager._token_cache == {}
        assert not os.path.exists(self.cache_file)
    
    def test_get_cache_status(self):
        """Test auth status reporting"""
        auth_manager = PersistentAuthManager(self.client_id, self.cache_file)
        
        # Mock some cached tokens with correct cache key format
        graph_key = f"graph_{self.client_id}"
        custom_key = f"custom_{self.client_id}"
        test_token_data = {
            graph_key: {
                "token": "test-graph-token",
                "expires_at": "2025-07-24T16:00:00Z",
                "scope": "graph"
            },
            custom_key: {
                "token": "test-custom-token", 
                "expires_at": "2025-07-24T16:00:00Z",
                "scope": "custom"
            }
        }
        
        auth_manager._token_cache = test_token_data
        
        status = auth_manager.get_cache_status()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
