"""
OAuth Token Generator for Microsoft Graph API
Generates fresh OAuth tokens for the Scribe application and stores them in Azure Key Vault
"""

import os
import requests
import logging
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Configuration
AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID') 
KEY_VAULT_URL = os.environ.get('KEY_VAULT_URL')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')  # Temporary for initial setup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_oauth_tokens():
    """
    Generate fresh OAuth tokens using client credentials flow
    This is for service-to-service authentication (no user interaction required)
    """
    try:
        logger.info("🔐 Generating fresh OAuth tokens...")
        
        if not all([AZURE_CLIENT_ID, AZURE_TENANT_ID, CLIENT_SECRET]):
            raise ValueError("Missing required environment variables: AZURE_CLIENT_ID, AZURE_TENANT_ID, CLIENT_SECRET")
        
        # Microsoft Graph token endpoint
        url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
        
        # Request payload for client credentials flow
        data = {
            'grant_type': 'client_credentials',
            'client_id': AZURE_CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'scope': 'https://graph.microsoft.com/.default'
        }
        
        logger.info(f"🌐 Requesting tokens from: {url}")
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            
            access_token = token_data['access_token']
            token_type = token_data.get('token_type', 'Bearer')
            expires_in = token_data.get('expires_in', 3600)
            
            logger.info(f"✅ OAuth tokens generated successfully")
            logger.info(f"📝 Token Type: {token_type}")
            logger.info(f"⏰ Expires In: {expires_in} seconds")
            
            return {
                'access_token': access_token,
                'token_type': token_type,
                'expires_in': expires_in
            }
        else:
            logger.error(f"❌ Failed to generate OAuth tokens: {response.status_code}")
            logger.error(f"❌ Response: {response.text}")
            raise Exception(f"Token generation failed: {response.text}")
            
    except Exception as e:
        logger.error(f"❌ Error generating OAuth tokens: {str(e)}")
        raise


def store_tokens_in_keyvault(tokens):
    """Store OAuth tokens in Azure Key Vault"""
    try:
        logger.info("🔐 Storing tokens in Azure Key Vault...")
        
        if not KEY_VAULT_URL:
            raise ValueError("KEY_VAULT_URL environment variable not set")
        
        # Initialize Key Vault client with Managed Identity
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
        
        # Store access token
        client.set_secret('access-token', tokens['access_token'])
        logger.info("✅ Access token stored in Key Vault")
        
        # Note: Client credentials flow doesn't provide refresh tokens
        # For service-to-service auth, we'll regenerate tokens as needed
        logger.info("ℹ️ Client credentials flow - no refresh token needed")
        
        logger.info("✅ All tokens stored successfully in Key Vault")
        
    except Exception as e:
        logger.error(f"❌ Error storing tokens in Key Vault: {str(e)}")
        raise


def store_client_secret_in_keyvault():
    """Store the client secret in Key Vault for future token refreshes"""
    try:
        if not all([KEY_VAULT_URL, CLIENT_SECRET]):
            raise ValueError("KEY_VAULT_URL and CLIENT_SECRET environment variables required")
        
        logger.info("🔐 Storing client secret in Azure Key Vault...")
        
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
        
        # Store client secret
        client.set_secret('client-secret', CLIENT_SECRET)
        logger.info("✅ Client secret stored in Key Vault")
        
    except Exception as e:
        logger.error(f"❌ Error storing client secret in Key Vault: {str(e)}")
        raise


def main():
    """Main function to generate and store OAuth tokens"""
    try:
        logger.info("🚀 Starting OAuth token generation and storage...")
        
        # Generate fresh tokens
        tokens = generate_oauth_tokens()
        
        # Store tokens in Key Vault
        store_tokens_in_keyvault(tokens)
        
        # Store client secret for future use
        store_client_secret_in_keyvault()
        
        logger.info("🎉 OAuth token setup completed successfully!")
        logger.info("ℹ️ Tokens are now securely stored in Azure Key Vault")
        logger.info("ℹ️ The Function App can now authenticate with Microsoft Graph")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ OAuth token setup failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
