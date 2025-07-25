"""
Authentication helper functions for token management with persistent storage
Provides centralized authentication with automatic token refresh and caching
"""

import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import jwt
from azure.identity import ManagedIdentityCredential


class PersistentAuthManager:
    """
    Centralized authentication manager with persistent token storage
    Handles automatic refresh and caching to minimize re-authentication
    """
    
    def __init__(self, 
                 client_id: Optional[str] = None,
                 cache_file: Optional[str] = None):
        """
        Initialize persistent authentication manager
        
        Args:
            client_id: Optional client ID for user-assigned managed identity
            cache_file: Optional path to token cache file
        """
        self.client_id = client_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Token cache file location
        self.cache_file = Path(cache_file or "./.auth_cache.json")
        
        # In-memory token cache
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        
        # Load cached tokens on initialization
        self._load_token_cache()
    
    def _load_token_cache(self) -> None:
        """Load cached tokens from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self._token_cache = json.load(f)
                self.logger.info(f"✅ Loaded {len(self._token_cache)} cached tokens")
            else:
                self._token_cache = {}
                self.logger.info("🔄 No token cache found, starting fresh")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to load token cache: {e}")
            self._token_cache = {}
    
    def _save_token_cache(self) -> None:
        """Save token cache to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._token_cache, f, indent=2)
            self.logger.debug("💾 Token cache saved to disk")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to save token cache: {e}")
    
    def _is_token_valid(self, token_data: Dict[str, Any], buffer_minutes: int = 5) -> bool:
        """
        Check if cached token is still valid
        
        Args:
            token_data: Cached token data with 'token' and 'expires_at'
            buffer_minutes: Minutes before expiry to consider token expired
            
        Returns:
            bool: True if token is valid and not expiring soon
        """
        if not token_data or 'token' not in token_data or 'expires_at' not in token_data:
            return False
        
        try:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            buffer_time = datetime.now(timezone.utc) + timedelta(minutes=buffer_minutes)
            return expires_at > buffer_time
        except Exception:
            return False
    
    def _get_fresh_token(self, scope: str) -> Optional[Dict[str, Any]]:
        """
        Get fresh token from Azure identity
        
        Args:
            scope: Token scope (e.g., 'https://graph.microsoft.com/.default')
            
        Returns:
            Optional[Dict]: Token data with token and expiry, or None if failed
        """
        try:
            credential = ManagedIdentityCredential(client_id=self.client_id)
            token_result = credential.get_token(scope)
            
            if token_result and token_result.token:
                # Calculate expiry time
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_result.expires_on - time.time())
                
                token_data = {
                    'token': token_result.token,
                    'expires_at': expires_at.isoformat(),
                    'scope': scope,
                    'obtained_at': datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info(f"✅ Fresh token obtained for scope: {scope}")
                return token_data
            else:
                self.logger.error(f"❌ Failed to obtain token for scope: {scope}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error obtaining token for {scope}: {e}")
            return None
    
    def get_token(self, scope: str, force_refresh: bool = False) -> Optional[str]:
        """
        Get access token with automatic caching and refresh
        
        Args:
            scope: Token scope
            force_refresh: Force refresh even if cached token is valid
            
        Returns:
            Optional[str]: Access token or None if failed
        """
        cache_key = f"{scope}_{self.client_id or 'default'}"
        
        # Check cached token first (unless force refresh)
        if not force_refresh and cache_key in self._token_cache:
            cached_token = self._token_cache[cache_key]
            if self._is_token_valid(cached_token):
                self.logger.debug(f"🔄 Using cached token for {scope}")
                return cached_token['token']
            else:
                self.logger.debug(f"⏰ Cached token expired for {scope}")
        
        # Get fresh token
        token_data = self._get_fresh_token(scope)
        if token_data:
            # Cache the new token
            self._token_cache[cache_key] = token_data
            self._save_token_cache()
            return token_data['token']
        
        return None
    
    def get_graph_token(self, force_refresh: bool = False) -> Optional[str]:
        """Get Microsoft Graph API token"""
        return self.get_token("https://graph.microsoft.com/.default", force_refresh)
    
    def get_ai_foundry_token(self, force_refresh: bool = False) -> Optional[str]:
        """Get Azure AI Foundry token"""
        return self.get_token("https://ml.azure.com/.default", force_refresh)
    
    def get_storage_token(self, force_refresh: bool = False) -> Optional[str]:
        """Get Azure Storage token"""
        return self.get_token("https://storage.azure.com/.default", force_refresh)
    
    def get_auth_headers(self, token_type: str = 'graph', force_refresh: bool = False) -> Dict[str, str]:
        """
        Get authentication headers for API requests
        
        Args:
            token_type: Type of token ('graph', 'ai_foundry', 'storage')
            force_refresh: Force token refresh
            
        Returns:
            Dict[str, str]: Headers with authorization
        """
        token_methods = {
            'graph': self.get_graph_token,
            'ai_foundry': self.get_ai_foundry_token,
            'storage': self.get_storage_token
        }
        
        token_method = token_methods.get(token_type)
        if not token_method:
            self.logger.error(f"❌ Unknown token type: {token_type}")
            return {}
        
        token = token_method(force_refresh)
        if not token:
            self.logger.error(f"❌ Failed to get {token_type} token")
            return {}
        
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def clear_cache(self) -> None:
        """Clear all cached tokens"""
        self._token_cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()
        self.logger.info("🗑️ Token cache cleared")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get current cache status
        
        Returns:
            Dict with cache information
        """
        status = {
            'cached_tokens': len(self._token_cache),
            'cache_file': str(self.cache_file),
            'tokens': {}
        }
        
        for key, token_data in self._token_cache.items():
            status['tokens'][key] = {
                'valid': self._is_token_valid(token_data),
                'expires_at': token_data.get('expires_at'),
                'scope': token_data.get('scope')
            }
        
        return status


# Global authentication manager instance
_auth_manager: Optional[PersistentAuthManager] = None


def get_auth_manager(client_id: Optional[str] = None, 
                    cache_file: Optional[str] = None) -> PersistentAuthManager:
    """
    Get or create global persistent authentication manager
    
    Args:
        client_id: Optional client ID for user-assigned managed identity
        cache_file: Optional path to token cache file
        
    Returns:
        PersistentAuthManager: Global authentication manager
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = PersistentAuthManager(client_id, cache_file)
    return _auth_manager


def validate_token_expiry(token: str, buffer_minutes: int = 5) -> bool:
    """
    Check if a JWT token is valid and not expiring soon
    
    Args:
        token: JWT token to validate
        buffer_minutes: Minutes before expiry to consider token as expired
        
    Returns:
        bool: True if token is valid and not expiring soon
    """
    try:
        # Decode without verification to check expiry
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        if 'exp' not in decoded:
            return False
        
        # Check if token expires within buffer period
        exp_timestamp = decoded['exp']
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        buffer_time = datetime.now() + timedelta(minutes=buffer_minutes)
        
        return exp_datetime > buffer_time
        
    except Exception as e:
        logging.getLogger(__name__).warning(f"Token validation failed: {str(e)}")
        return False


def refresh_token_if_needed(current_token: Optional[str], 
                           token_refresh_func: callable,
                           buffer_minutes: int = 5) -> Optional[str]:
    """
    Refresh token if it's expired or expiring soon
    
    Args:
        current_token: Current access token
        token_refresh_func: Function to call for token refresh
        buffer_minutes: Minutes before expiry to refresh token
        
    Returns:
        Optional[str]: New token if refreshed, current token if still valid, None if refresh failed
    """
    logger = logging.getLogger(__name__)
    
    if not current_token:
        logger.info("🔑 No current token, attempting refresh...")
        try:
            return token_refresh_func()
        except Exception as e:
            logger.error(f"❌ Token refresh failed: {str(e)}")
            return None
    
    if validate_token_expiry(current_token, buffer_minutes):
        logger.debug("🔑 Current token is still valid")
        return current_token
    
    logger.info("🔄 Token is expired or expiring soon, refreshing...")
    try:
        new_token = token_refresh_func()
        if new_token:
            logger.info("✅ Token refreshed successfully")
            return new_token
        else:
            logger.warning("⚠️ Token refresh returned empty token")
            return current_token
    except Exception as e:
        logger.error(f"❌ Token refresh failed: {str(e)}")
        return current_token


def get_managed_identity_token(resource: str, credential: Optional[ManagedIdentityCredential] = None) -> Optional[str]:
    """
    Get access token using Managed Identity
    
    Args:
        resource: Azure resource to get token for
        credential: Optional pre-initialized credential
        
    Returns:
        Optional[str]: Access token if successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        if not credential:
            credential = ManagedIdentityCredential()
        
        logger.debug(f"🔑 Getting managed identity token for resource: {resource}")
        token = credential.get_token(resource)
        
        if token and token.token:
            logger.info("✅ Managed identity token obtained successfully")
            return token.token
        else:
            logger.error("❌ Managed identity token request returned empty token")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get managed identity token: {str(e)}")
        return None
