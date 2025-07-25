"""
Secure Credential Manager for Scribe Voice Email Processor
Handles secure storage and retrieval of sensitive credentials using Azure Key Vault
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, ClientSecretCredential
from azure.core.exceptions import ResourceNotFoundError, ClientAuthenticationError

logger = logging.getLogger(__name__)


class SecureCredentialManager:
    """Secure credential management using Azure Key Vault"""
    
    def __init__(self):
        self.key_vault_url = os.getenv('AZURE_KEY_VAULT_URL', '').rstrip('/')
        self.secret_client = None
        self.fallback_to_file = os.getenv('FALLBACK_TO_FILE_STORAGE', 'false').lower() == 'true'
        self.token_file = '.oauth_tokens.json'  # Fallback file for development
        
        if self.key_vault_url:
            self._initialize_key_vault_client()
        else:
            logger.warning("⚠️ No Azure Key Vault URL configured, falling back to file storage")
            self.fallback_to_file = True
    
    def _initialize_key_vault_client(self) -> None:
        """Initialize Azure Key Vault client with proper authentication"""
        try:
            # Try different authentication methods in order of preference
            credential = None
            
            # 1. Try Managed Identity (production)
            try:
                credential = ManagedIdentityCredential()
                # Test the credential
                test_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
                # This will raise an exception if auth fails
                list(test_client.list_properties_of_secrets(max_results=1))
                logger.info("✅ Using Managed Identity for Key Vault authentication")
                
            except Exception:
                # 2. Try Service Principal (if configured)
                client_id = os.getenv('AZURE_CLIENT_ID')
                client_secret = os.getenv('AZURE_CLIENT_SECRET') 
                tenant_id = os.getenv('AZURE_TENANT_ID')
                
                if client_id and client_secret and tenant_id:
                    try:
                        credential = ClientSecretCredential(
                            tenant_id=tenant_id,
                            client_id=client_id,
                            client_secret=client_secret
                        )
                        test_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
                        list(test_client.list_properties_of_secrets(max_results=1))
                        logger.info("✅ Using Service Principal for Key Vault authentication")
                        
                    except Exception:
                        credential = None
                
                # 3. Try Default Azure Credential (development)
                if not credential:
                    try:
                        credential = DefaultAzureCredential()
                        test_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
                        list(test_client.list_properties_of_secrets(max_results=1))
                        logger.info("✅ Using Default Azure Credential for Key Vault authentication")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to authenticate with Azure Key Vault: {e}")
                        logger.warning("⚠️ Falling back to file storage")
                        self.fallback_to_file = True
                        return
            
            if credential:
                self.secret_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
                logger.info(f"✅ Azure Key Vault client initialized: {self.key_vault_url}")
            else:
                logger.error("❌ No valid Azure credentials found")
                self.fallback_to_file = True
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize Key Vault client: {e}")
            self.fallback_to_file = True
    
    def store_oauth_token(self, token_data: Dict[str, Any]) -> bool:
        """Store OAuth token data securely"""
        try:
            if not self.fallback_to_file and self.secret_client:
                return self._store_token_in_key_vault(token_data)
            else:
                logger.warning("⚠️ Using fallback file storage for OAuth token")
                return self._store_token_in_file(token_data)
                
        except Exception as e:
            logger.error(f"❌ Failed to store OAuth token: {e}")
            return False
    
    def retrieve_oauth_token(self) -> Optional[Dict[str, Any]]:
        """Retrieve OAuth token data securely"""
        try:
            if not self.fallback_to_file and self.secret_client:
                return self._retrieve_token_from_key_vault()
            else:
                logger.warning("⚠️ Using fallback file storage for OAuth token retrieval")
                return self._retrieve_token_from_file()
                
        except Exception as e:
            logger.error(f"❌ Failed to retrieve OAuth token: {e}")
            return None
    
    def _store_token_in_key_vault(self, token_data: Dict[str, Any]) -> bool:
        """Store token data in Azure Key Vault"""
        try:
            # Sanitize token data for Key Vault storage
            sanitized_data = {
                'timestamp': token_data.get('timestamp'),
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token'),
                'expires_in': token_data.get('expires_in'),
                'expiry_time': token_data.get('expiry_time'),
                'token_type': token_data.get('token_type', 'Bearer'),
                'scope': token_data.get('scope', ''),
                'client_id': token_data.get('client_id'),
                'user_email': token_data.get('user_email')
            }
            
            # Store as JSON string in Key Vault
            secret_name = "scribe-oauth-token"
            secret_value = json.dumps(sanitized_data)
            
            self.secret_client.set_secret(secret_name, secret_value)
            logger.info("✅ OAuth token stored securely in Azure Key Vault")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store token in Key Vault: {e}")
            return False
    
    def _retrieve_token_from_key_vault(self) -> Optional[Dict[str, Any]]:
        """Retrieve token data from Azure Key Vault"""
        try:
            secret_name = "scribe-oauth-token"
            secret = self.secret_client.get_secret(secret_name)
            
            if secret and secret.value:
                token_data = json.loads(secret.value)
                logger.info("✅ OAuth token retrieved securely from Azure Key Vault")
                return token_data
            else:
                logger.warning("⚠️ No OAuth token found in Azure Key Vault")
                return None
                
        except ResourceNotFoundError:
            logger.warning("⚠️ OAuth token not found in Azure Key Vault")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to retrieve token from Key Vault: {e}")
            return None
    
    def _store_token_in_file(self, token_data: Dict[str, Any]) -> bool:
        """Fallback: Store token in file (with warning)"""
        try:
            logger.warning("🚨 SECURITY WARNING: Storing OAuth token in plain text file")
            logger.warning("🚨 This is not secure for production use!")
            
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            logger.warning(f"⚠️ Token stored in file: {self.token_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to store token in file: {e}")
            return False
    
    def _retrieve_token_from_file(self) -> Optional[Dict[str, Any]]:
        """Fallback: Retrieve token from file (with warning)"""
        try:
            if not os.path.exists(self.token_file):
                logger.warning(f"⚠️ Token file not found: {self.token_file}")
                return None
            
            logger.warning("🚨 SECURITY WARNING: Reading OAuth token from plain text file")
            logger.warning("🚨 This is not secure for production use!")
            
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            logger.warning(f"⚠️ Token retrieved from file: {self.token_file}")
            return token_data
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve token from file: {e}")
            return None
    
    def delete_oauth_token(self) -> bool:
        """Delete OAuth token from secure storage"""
        try:
            if not self.fallback_to_file and self.secret_client:
                return self._delete_token_from_key_vault()
            else:
                return self._delete_token_file()
                
        except Exception as e:
            logger.error(f"❌ Failed to delete OAuth token: {e}")
            return False
    
    def _delete_token_from_key_vault(self) -> bool:
        """Delete token from Azure Key Vault"""
        try:
            secret_name = "scribe-oauth-token"
            self.secret_client.begin_delete_secret(secret_name)
            logger.info("✅ OAuth token deleted from Azure Key Vault")
            return True
            
        except ResourceNotFoundError:
            logger.info("ℹ️ OAuth token was not found in Key Vault (already deleted)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete token from Key Vault: {e}")
            return False
    
    def _delete_token_file(self) -> bool:
        """Delete token file"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"✅ Token file deleted: {self.token_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete token file: {e}")
            return False
    
    def test_key_vault_connection(self) -> bool:
        """Test connection to Azure Key Vault"""
        try:
            if self.fallback_to_file:
                logger.warning("⚠️ Key Vault not configured, using file storage")
                return False
            
            if not self.secret_client:
                logger.error("❌ Key Vault client not initialized")
                return False
            
            # Try to list secrets (this tests authentication and connectivity)
            list(self.secret_client.list_properties_of_secrets(max_results=1))
            logger.info("✅ Azure Key Vault connection test passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Key Vault connection test failed: {e}")
            return False


# Global instance
secure_credential_manager = SecureCredentialManager()