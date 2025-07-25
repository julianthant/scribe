"""
Key Vault Manager for securely accessing secrets from Azure Key Vault
Uses Managed Identity for authentication in Azure Functions
"""

from azure.keyvault.secrets import SecretClient
from azure.identity import ManagedIdentityCredential
import os
import logging


class KeyVaultManager:
    """Manages secure access to Azure Key Vault secrets using Managed Identity"""
    
    def __init__(self):
        """Initialize Key Vault client with Managed Identity authentication"""
        try:
            # Use ManagedIdentityCredential directly for better Azure Functions compatibility
            credential = ManagedIdentityCredential()
            vault_url = os.environ.get("KEY_VAULT_URL")
            
            if not vault_url:
                raise ValueError("KEY_VAULT_URL environment variable not set")
            
            self.client = SecretClient(vault_url=vault_url, credential=credential)
            self._cache = {}  # In-memory cache for secrets during function execution
            
            logging.info(f"✅ Key Vault Manager initialized with vault: {vault_url}")
            logging.info(f"🔐 Authentication: Managed Identity (Function App Principal)")
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize Key Vault Manager: {str(e)}")
            raise

from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import os
import logging


class KeyVaultManager:
    """Manages secure access to Azure Key Vault secrets using Managed Identity"""
    
    def __init__(self):
        """Initialize Key Vault client with Managed Identity authentication"""
        try:
            vault_url = os.environ.get("KEY_VAULT_URL")
            
            if not vault_url:
                raise ValueError("KEY_VAULT_URL environment variable not set")
            
            # Try ManagedIdentityCredential first for Azure Functions
            try:
                credential = ManagedIdentityCredential()
                self.client = SecretClient(vault_url=vault_url, credential=credential)
                logging.info("✅ Using ManagedIdentityCredential for Key Vault access")
            except Exception as e:
                logging.warning(f"⚠️ ManagedIdentityCredential failed: {str(e)}")
                # Fallback to DefaultAzureCredential
                credential = DefaultAzureCredential()
                self.client = SecretClient(vault_url=vault_url, credential=credential)
                logging.info("✅ Using DefaultAzureCredential for Key Vault access")
            
            self._cache = {}  # In-memory cache for secrets during function execution
            
            logging.info(f"✅ Key Vault Manager initialized with vault: {vault_url}")
            
        except Exception as e:
            logging.error(f"❌ Failed to initialize Key Vault Manager: {str(e)}")
            raise
    
    def get_secret(self, secret_name: str) -> str:
        """
        Retrieve a secret from Key Vault with caching
        
        Args:
            secret_name (str): Name of the secret to retrieve
            
        Returns:
            str: Secret value
            
        Raises:
            Exception: If secret cannot be retrieved
        """
        try:
            # Check cache first
            if secret_name not in self._cache:
                logging.info(f"🔐 Retrieving secret '{secret_name}' from Key Vault...")
                secret = self.client.get_secret(secret_name)
                self._cache[secret_name] = secret.value
                logging.info(f"✅ Secret '{secret_name}' retrieved and cached")
            else:
                logging.info(f"📋 Using cached secret '{secret_name}'")
                
            return self._cache[secret_name]
            
        except Exception as e:
            logging.error(f"❌ Failed to retrieve secret '{secret_name}': {str(e)}")
            raise
    
    def refresh_secret(self, secret_name: str) -> str:
        """
        Force refresh a secret from Key Vault (bypass cache)
        
        Args:
            secret_name (str): Name of the secret to refresh
            
        Returns:
            str: Updated secret value
        """
        try:
            logging.info(f"🔄 Force refreshing secret '{secret_name}' from Key Vault...")
            
            # Remove from cache and fetch fresh
            if secret_name in self._cache:
                del self._cache[secret_name]
                
            secret = self.client.get_secret(secret_name)
            self._cache[secret_name] = secret.value
            
            logging.info(f"✅ Secret '{secret_name}' refreshed successfully")
            return self._cache[secret_name]
            
        except Exception as e:
            logging.error(f"❌ Failed to refresh secret '{secret_name}': {str(e)}")
            raise
    
    def clear_cache(self):
        """Clear all cached secrets"""
        self._cache.clear()
        logging.info("🗑️ Key Vault cache cleared")
