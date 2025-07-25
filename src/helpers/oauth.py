"""
OAuth Helper for Microsoft Graph API
Secure OAuth token management with Azure Key Vault integration
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from core.secure_credentials import secure_credential_manager

logger = logging.getLogger(__name__)

class OAuthManager:
    """Secure OAuth token management for Microsoft Graph with Azure Key Vault"""
    
    def __init__(self):
        self.credential_manager = secure_credential_manager
        self._cached_token = None
        logger.info("🔐 OAuth Manager initialized with secure credential storage")
    
    def get_access_token(self) -> Optional[str]:
        """Get valid access token from secure storage or refresh if needed"""
        try:
            # Load token from secure storage
            token_data = self.credential_manager.retrieve_oauth_token()
            if not token_data:
                logger.error("❌ OAuth token not found in secure storage")
                return None
            
            access_token = token_data.get('access_token')
            if not access_token:
                logger.error("❌ No access token found in token file")
                return None
            
            # Check if token is still valid
            expiry_str = token_data.get('expiry_time')
            if expiry_str:
                try:
                    expiry_time = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                    current_time = datetime.now(timezone.utc)
                    
                    # Check if token expires within next 5 minutes (early refresh)
                    expires_soon = expiry_time - current_time < timedelta(minutes=5)
                    
                    if current_time >= expiry_time:
                        logger.warning("⚠️ OAuth token has expired")
                        # Try to refresh token if we have refresh_token
                        refresh_token = token_data.get('refresh_token')
                        if refresh_token:
                            logger.info("🔄 Attempting to refresh expired token...")
                            new_token = self._refresh_access_token(refresh_token)
                            if new_token:
                                return new_token
                        return None
                    elif expires_soon:
                        logger.info("🔄 Token expires soon, attempting early refresh...")
                        refresh_token = token_data.get('refresh_token')
                        if refresh_token:
                            new_token = self._refresh_access_token(refresh_token)
                            if new_token:
                                return new_token
                        # Fall back to current token if refresh fails
                        logger.warning("⚠️ Early refresh failed, using current token")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse token expiry: {e}")
            
            logger.info("✅ OAuth token loaded and valid")
            return access_token
            
        except Exception as e:
            logger.error(f"❌ Failed to load OAuth token: {e}")
            return None
    
    def _refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            logger.info("🔄 Refreshing OAuth access token...")
            
            # Get configuration
            client_id = os.getenv('CLIENT_ID', os.getenv('MICROSOFT_GRAPH_CLIENT_ID', ''))
            tenant_id = os.getenv('TENANT_ID', os.getenv('MICROSOFT_GRAPH_TENANT_ID', 'common'))
            
            if not client_id:
                logger.error("❌ No client ID available for token refresh")
                return None
            
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            
            data = {
                'grant_type': 'refresh_token',
                'client_id': client_id,
                'refresh_token': refresh_token,
                'scope': 'https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Files.ReadWrite.All https://graph.microsoft.com/User.Read'
            }
            
            response = requests.post(token_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Calculate expiry time
                expires_in = token_data.get('expires_in', 3600)
                expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                # Update token file
                updated_token_data = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'access_token': token_data['access_token'],
                    'refresh_token': token_data.get('refresh_token', refresh_token),  # Keep old if new not provided
                    'expires_in': expires_in,
                    'expiry_time': expiry_time.isoformat(),
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'scope': token_data.get('scope', ''),
                    'client_id': client_id,
                    'user_email': os.getenv('TARGET_USER_EMAIL', 'Unknown')
                }
                
                # Save updated token to secure storage
                if not self.credential_manager.store_oauth_token(updated_token_data):
                    logger.error("❌ Failed to store refreshed token securely")
                    return None
                
                logger.info(f"✅ Token refreshed successfully! Expires: {expiry_time}")
                return token_data['access_token']
            
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                logger.error(f"❌ Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error refreshing token: {e}")
            return None
    
    def test_token(self) -> Dict[str, Any]:
        """Test OAuth token by calling Microsoft Graph API"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'valid': False, 'error': 'No access token available'}
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    'valid': True,
                    'user_name': user_data.get('displayName', 'Unknown'),
                    'user_email': user_data.get('mail', user_data.get('userPrincipalName', 'Unknown')),
                    'user_id': user_data.get('id', 'Unknown')
                }
            else:
                logger.error(f"❌ OAuth token test failed: {response.status_code}")
                return {
                    'valid': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            logger.error(f"❌ OAuth token test error: {e}")
            return {'valid': False, 'error': str(e)}
    
    def make_graph_request(self, url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
        """Make authenticated request to Microsoft Graph API"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                logger.error("❌ No access token available for Graph request")
                return None
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=data)
            else:
                logger.error(f"❌ Unsupported HTTP method: {method}")
                return None
            
            # Log errors but still return the response for debugging
            if response.status_code >= 400:
                logger.warning(f"⚠️ Graph API returned {response.status_code}: {response.text}")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Graph API request failed: {e}")
            return None

# Global instance for easy access
oauth_manager = OAuthManager()

def get_access_token() -> Optional[str]:
    """Get access token - simple function interface"""
    return oauth_manager.get_access_token()

def store_oauth_token(token_data: Dict[str, Any]) -> bool:
    """Store OAuth token securely - simple function interface"""
    return secure_credential_manager.store_oauth_token(token_data)

def delete_oauth_token() -> bool:
    """Delete OAuth token from secure storage - simple function interface"""
    return secure_credential_manager.delete_oauth_token()

def test_key_vault_connection() -> bool:
    """Test Azure Key Vault connection - simple function interface"""
    return secure_credential_manager.test_key_vault_connection()

def test_oauth_configuration() -> Dict[str, Any]:
    """Test OAuth configuration - simple function interface"""
    return oauth_manager.test_token()

def make_graph_request(url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
    """Make Graph API request - simple function interface"""
    return oauth_manager.make_graph_request(url, method, data)