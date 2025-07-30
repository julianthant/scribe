"""
Authentication providers for Microsoft Graph API access
Implements Strategy pattern for different authentication methods
Production-ready implementation with proper error handling and security
"""

import os
import json
import logging
import time
import requests
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from msal import ConfidentialClientApplication, PublicClientApplication

logger = logging.getLogger(__name__)


class AuthProvider(ABC):
    """Abstract base class for authentication providers"""
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the authentication provider"""
        pass
    
    @abstractmethod
    def get_access_token(self) -> Optional[str]:
        """Get a valid access token"""
        pass
    
    @abstractmethod
    def make_graph_request(self, url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
        """Make Microsoft Graph API request"""
        pass
    
    @abstractmethod
    def test_authentication(self) -> Dict[str, Any]:
        """Test authentication and return status"""
        pass
    
    @abstractmethod
    def get_auth_info(self) -> Dict[str, Any]:
        """Get authentication provider information"""
        pass


class CertificateAuthProvider(AuthProvider):
    """Certificate-based authentication for production environments"""
    
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.tenant_id = os.getenv('TENANT_ID')
        self.thumbprint = os.getenv('CERTIFICATE_THUMBPRINT')
        self.private_key_path = os.getenv('CERTIFICATE_PRIVATE_KEY_PATH')
        self._msal_app = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize certificate authentication using MSAL"""
        if self._initialized:
            return True
            
        try:
            # Validate configuration
            missing_config = []
            if not self.tenant_id: missing_config.append('TENANT_ID')
            if not self.client_id: missing_config.append('CLIENT_ID')
            if not self.thumbprint: missing_config.append('CERTIFICATE_THUMBPRINT')
            if not self.private_key_path: missing_config.append('CERTIFICATE_PRIVATE_KEY_PATH')
            
            if missing_config:
                logger.error(f"❌ Missing certificate configuration: {', '.join(missing_config)}")
                return False
            
            # Check if certificate file exists
            if not os.path.exists(self.private_key_path):
                logger.error(f"❌ Certificate file not found: {self.private_key_path}")
                return False
            
            # Read certificate
            with open(self.private_key_path, 'r') as cert_file:
                private_key = cert_file.read()
            
            # Initialize MSAL app with certificate
            self._msal_app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential={
                    "thumbprint": self.thumbprint,
                    "private_key": private_key
                },
                authority=f"https://login.microsoftonline.com/{self.tenant_id}"
            )
            
            self._initialized = True
            logger.info("✅ Certificate authentication initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Certificate authentication initialization failed: {e}")
            return False
    
    def get_access_token(self) -> Optional[str]:
        """Get access token using certificate authentication"""
        if not self._initialized and not self.initialize():
            return None
        
        try:
            # Get token for Microsoft Graph
            result = self._msal_app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            
            if "access_token" in result:
                return result["access_token"]
            else:
                logger.error(f"❌ Failed to acquire token: {result.get('error_description', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Token acquisition failed: {e}")
            return None
    
    def make_graph_request(self, url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
        """Make Microsoft Graph API request using certificate authentication"""
        access_token = self.get_access_token()
        if not access_token:
            logger.error("❌ No access token available for Graph request")
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            timeout = 10
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=timeout)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=data, timeout=timeout)
            else:
                logger.error(f"❌ Unsupported HTTP method: {method}")
                return None
                
            return response
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ Graph API request timed out: {url}")
            return None
        except Exception as e:
            logger.error(f"❌ Graph API request failed: {e}")
            return None
    
    def test_authentication(self) -> Dict[str, Any]:
        """Test certificate authentication by calling Microsoft Graph"""
        try:
            if not self.initialize():
                return {'valid': False, 'error': 'Certificate authentication initialization failed'}

            # Test with a simple Graph API call
            response = self.make_graph_request("https://graph.microsoft.com/v1.0/organization")
            
            if response and response.status_code == 200:
                org_data = response.json()
                org_name = org_data.get('value', [{}])[0].get('displayName', 'Unknown')
                
                return {
                    'valid': True,
                    'organization': org_name,
                    'auth_method': 'certificate',
                    'tenant_id': self.tenant_id
                }
            else:
                status_code = response.status_code if response else 'No response'
                return {'valid': False, 'error': f'Graph API call failed with status: {status_code}'}

        except Exception as e:
            logger.error(f"❌ Authentication test failed: {e}")
            return {'valid': False, 'error': str(e)}
    
    def get_auth_info(self) -> Dict[str, Any]:
        """Get certificate authentication information"""
        return {
            'provider': 'certificate',
            'client_id': self.client_id,
            'tenant_id': self.tenant_id,
            'certificate_configured': bool(self.thumbprint and self.private_key_path),
            'certificate_file_exists': os.path.exists(self.private_key_path) if self.private_key_path else False,
            'initialized': self._initialized
        }


class TokenStorageStrategy(ABC):
    """Abstract base class for token storage strategies"""
    
    @abstractmethod
    def get_refresh_token(self) -> Optional[str]:
        """Get stored refresh token"""
        pass
    
    @abstractmethod
    def store_refresh_token(self, token: str) -> bool:
        """Store refresh token"""
        pass
    
    @abstractmethod
    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage strategy information"""
        pass


class KeyVaultTokenStorage(TokenStorageStrategy):
    """Azure Key Vault token storage"""
    
    def __init__(self):
        self.key_vault_url = os.getenv('KEY_VAULT_URL', 'https://your-keyvault.vault.azure.net/')
        self.key_vault_client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Azure Key Vault client"""
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            
            credential = DefaultAzureCredential()
            self.key_vault_client = SecretClient(
                vault_url=self.key_vault_url,
                credential=credential
            )
            logger.info("✅ Key Vault client initialized")
            
        except ImportError:
            logger.error("❌ Azure Key Vault libraries not installed. Run: pip install azure-keyvault-secrets azure-identity")
        except Exception as e:
            logger.error(f"❌ Key Vault client initialization failed: {e}")
    
    def get_refresh_token(self) -> Optional[str]:
        """Get refresh token from Key Vault"""
        if not self.key_vault_client:
            return None
            
        try:
            secret = self.key_vault_client.get_secret('oauth-refresh-token')
            logger.info("✅ Retrieved refresh token from Key Vault")
            return secret.value
        except Exception as e:
            logger.warning(f"⚠️ Key Vault access failed: {e}")
            return None
    
    def store_refresh_token(self, token: str) -> bool:
        """Store refresh token in Key Vault"""
        if not self.key_vault_client:
            logger.warning("⚠️ Key Vault client not available")
            return False
            
        try:
            self.key_vault_client.set_secret('oauth-refresh-token', token)
            logger.info("✅ Refresh token updated in Key Vault")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store refresh token in Key Vault: {e}")
            return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get Key Vault storage information"""
        return {
            'type': 'keyvault',
            'vault_url': self.key_vault_url,
            'client_available': self.key_vault_client is not None
        }


class EnvironmentTokenStorage(TokenStorageStrategy):
    """Environment variable token storage"""
    
    def get_refresh_token(self) -> Optional[str]:
        """Get refresh token from environment variable"""
        token = os.getenv('OAUTH_REFRESH_TOKEN')
        if token:
            logger.info("✅ Retrieved refresh token from environment")
        return token
    
    def store_refresh_token(self, token: str) -> bool:
        """Cannot store token in environment variables at runtime"""
        logger.warning("⚠️ Cannot update environment variable at runtime")
        logger.info("💡 Consider updating OAUTH_REFRESH_TOKEN environment variable")
        return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get environment storage information"""
        return {
            'type': 'environment',
            'has_token': bool(os.getenv('OAUTH_REFRESH_TOKEN'))
        }


class FileTokenStorage(TokenStorageStrategy):
    """File-based token storage for development"""
    
    def __init__(self):
        self.token_file = 'personal_oauth_tokens.json'
    
    def get_refresh_token(self) -> Optional[str]:
        """Get refresh token from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                    token = token_data.get('refresh_token')
                    if token:
                        logger.info("✅ Retrieved refresh token from file")
                        return token
        except Exception as e:
            logger.error(f"❌ Failed to read token file: {e}")
        return None
    
    def store_refresh_token(self, token: str) -> bool:
        """Store refresh token in file"""
        try:
            token_data = {'refresh_token': token, 'updated': time.time()}
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            logger.info("✅ Refresh token stored in file")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to store token in file: {e}")
            return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get file storage information"""
        return {
            'type': 'file',
            'file_path': self.token_file,
            'file_exists': os.path.exists(self.token_file)
        }


class OAuthProvider(AuthProvider):
    """OAuth provider with configurable token storage"""
    
    SCOPES = [
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Files.ReadWrite.All"
    ]
    
    def __init__(self, storage_strategy: TokenStorageStrategy):
        self.client_id = os.getenv('CLIENT_ID')
        self.storage_strategy = storage_strategy
        self._msal_app = None
        self.current_token = None
        self.token_expiry = 0
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize OAuth authentication"""
        if self._initialized:
            return True
            
        if not self.client_id:
            logger.error("❌ CLIENT_ID not found in environment")
            return False
        
        try:
            self._msal_app = PublicClientApplication(
                client_id=self.client_id,
                authority="https://login.microsoftonline.com/common"
            )
            
            self._initialized = True
            logger.info("✅ OAuth provider initialized")
            return True
        except Exception as e:
            logger.error(f"❌ OAuth provider initialization failed: {e}")
            return False
    
    def get_access_token(self) -> Optional[str]:
        """Get valid access token with automatic refresh"""
        if not self._initialized and not self.initialize():
            return None
        
        try:
            # Check if current token is still valid
            current_time = time.time()
            if self.current_token and current_time < self.token_expiry - 300:  # 5 min buffer
                return self.current_token
            
            # Need to refresh token
            logger.info("🔄 Access token expired, refreshing...")
            refresh_token = self.storage_strategy.get_refresh_token()
            if not refresh_token:
                logger.error("❌ No refresh token available")
                return None
            
            return self._refresh_access_token(refresh_token)
                
        except Exception as e:
            logger.error(f"❌ Token acquisition failed: {e}")
            return None
    
    def _refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token with improved error handling"""
        try:
            logger.info("🔄 Refreshing access token...")
            token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            
            data = {
                'client_id': self.client_id,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
                'scope': ' '.join(self.SCOPES)
            }
            
            response = requests.post(token_url, data=data, timeout=30)  # Increased timeout
            
            if response.status_code == 200:
                token_data = response.json()
                self.current_token = token_data.get('access_token')
                self.token_expiry = time.time() + token_data.get('expires_in', 3600)
                
                # Store new refresh token if provided
                new_refresh_token = token_data.get('refresh_token')
                if new_refresh_token and new_refresh_token != refresh_token:
                    logger.info("🔄 New refresh token received, updating storage...")
                    self.storage_strategy.store_refresh_token(new_refresh_token)
                
                logger.info("✅ Token refresh successful")
                return self.current_token
            else:
                logger.error(f"❌ Token refresh failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                
                # Check for specific error types
                try:
                    error_data = response.json()
                    error_code = error_data.get('error')
                    error_desc = error_data.get('error_description')
                    
                    if error_code == 'invalid_grant':
                        logger.error("❌ Refresh token is invalid or expired - user needs to re-authenticate")
                    elif error_code == 'unauthorized_client':
                        logger.error("❌ Client not authorized for refresh token flow")
                    else:
                        logger.error(f"❌ Token refresh error: {error_code} - {error_desc}")
                except:
                    pass
                    
                return None
                
        except requests.exceptions.Timeout:
            logger.error("❌ Token refresh request timed out")
            return None
        except Exception as e:
            logger.error(f"❌ Token refresh exception: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def make_graph_request(self, url: str, method: str = 'GET', data: Dict = None) -> Optional[requests.Response]:
        """Make Microsoft Graph API request with automatic token refresh and retry"""
        max_retries = 2
        
        for attempt in range(max_retries):
            token = self.get_access_token()
            if not token:
                logger.error("❌ No access token available for Graph request")
                return None
            
            try:
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
                
                timeout = 30  # Increased timeout for Excel operations
                
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=headers, json=data, timeout=timeout)
                elif method.upper() == 'PATCH':
                    response = requests.patch(url, headers=headers, json=data, timeout=timeout)
                else:
                    logger.error(f"❌ Unsupported HTTP method: {method}")
                    return None
                
                # Handle token expiry with retry
                if response.status_code == 401:
                    logger.warning(f"⚠️ 401 response on attempt {attempt + 1} - forcing token refresh")
                    self.current_token = None
                    self.token_expiry = 0
                    
                    # If this was the last attempt, return the response
                    if attempt == max_retries - 1:
                        return response
                    
                    # Otherwise, continue to retry with fresh token
                    continue
                
                # Success or non-auth error - return response
                return response
                
            except requests.exceptions.Timeout:
                logger.error(f"❌ Graph API request timed out on attempt {attempt + 1}: {url}")
                if attempt == max_retries - 1:
                    return None
                continue
            except requests.exceptions.ConnectionError as e:
                logger.error(f"❌ Connection error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return None
                continue
            except Exception as e:
                logger.error(f"❌ Graph API request failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return None
                continue
        
        return None
    
    def test_authentication(self) -> Dict[str, Any]:
        """Test OAuth authentication"""
        try:
            # Test inbox access
            response = self.make_graph_request("https://graph.microsoft.com/v1.0/me/mailFolders/inbox")
            
            if response and response.status_code == 200:
                inbox_data = response.json()
                
                return {
                    'valid': True,
                    'user': 'Personal Account User',
                    'auth_method': 'oauth',
                    'inbox_items': inbox_data.get('totalItemCount', 0),
                    'storage_strategy': self.storage_strategy.__class__.__name__
                }
            else:
                status_code = response.status_code if response else 'No response'
                return {'valid': False, 'error': f'Inbox access failed with status: {status_code}'}

        except Exception as e:
            logger.error(f"❌ Authentication test failed: {e}")
            return {'valid': False, 'error': str(e)}
    
    def get_auth_info(self) -> Dict[str, Any]:
        """Get OAuth provider information"""
        return {
            'provider': 'oauth',
            'client_id': self.client_id,
            'has_access_token': bool(self.current_token),
            'token_expires_in': max(0, self.token_expiry - time.time()) if self.token_expiry else 0,
            'storage_strategy': self.storage_strategy.get_storage_info(),
            'initialized': self._initialized
        }