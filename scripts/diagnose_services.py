#!/usr/bin/env python3
"""
Service Diagnostic Tool
Diagnoses and fixes service connection issues
"""
import json
import requests
import time
import os
from azure.storage.blob import BlobServiceClient
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

class ServiceDiagnostic:
    def __init__(self):
        self.load_config()
        self.load_oauth_tokens()
    
    def load_config(self):
        """Load configuration"""
        with open('local.settings.json', 'r') as f:
            settings = json.load(f)
            self.config = settings.get('Values', {})
        print("✅ Configuration loaded")
    
    def load_oauth_tokens(self):
        """Load OAuth tokens"""
        try:
            with open('.oauth_tokens.json', 'r') as f:
                self.oauth_tokens = json.load(f)
            print("✅ OAuth tokens loaded")
        except FileNotFoundError:
            self.oauth_tokens = None
            print("❌ No OAuth tokens found")
    
    def check_token_expiry(self):
        """Check if tokens are expired"""
        if not self.oauth_tokens:
            return False
        
        # Simple check - try to use the token
        headers = {'Authorization': f'Bearer {self.oauth_tokens["access_token"]}'}
        response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ OAuth tokens valid for: {user_info.get('userPrincipalName', 'Unknown')}")
            return True
        elif response.status_code == 401:
            print("❌ OAuth tokens expired")
            return False
        else:
            print(f"⚠️ OAuth token check returned: {response.status_code}")
            return False
    
    def refresh_oauth_tokens(self):
        """Refresh expired OAuth tokens"""
        if not self.oauth_tokens or 'refresh_token' not in self.oauth_tokens:
            print("❌ No refresh token available")
            return False
        
        print("🔄 Refreshing OAuth tokens...")
        
        token_data = {
            'grant_type': 'refresh_token',
            'client_id': self.oauth_tokens['client_id'],
            'client_secret': self.oauth_tokens['client_secret'],
            'refresh_token': self.oauth_tokens['refresh_token']
        }
        
        response = requests.post(
            f'https://login.microsoftonline.com/{self.config.get("TENANT_ID", "common")}/oauth2/v2.0/token',
            data=token_data
        )
        
        if response.status_code == 200:
            new_tokens = response.json()
            
            # Update tokens
            self.oauth_tokens.update({
                'access_token': new_tokens['access_token'],
                'expires_in': new_tokens.get('expires_in', 3600),
                'scope': new_tokens.get('scope', self.oauth_tokens.get('scope', ''))
            })
            
            if 'refresh_token' in new_tokens:
                self.oauth_tokens['refresh_token'] = new_tokens['refresh_token']
            
            # Save updated tokens
            with open('.oauth_tokens.json', 'w') as f:
                json.dump(self.oauth_tokens, f, indent=2)
            
            print("✅ OAuth tokens refreshed successfully")
            return True
        else:
            print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
            return False
    
    def test_microsoft_graph_detailed(self):
        """Detailed Microsoft Graph API test"""
        print("\n🔍 Testing Microsoft Graph API...")
        
        if not self.oauth_tokens:
            print("❌ No OAuth tokens available")
            return False
        
        headers = {'Authorization': f'Bearer {self.oauth_tokens["access_token"]}'}
        
        # Test 1: User profile
        print("  Testing user profile access...")
        response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        if response.status_code == 200:
            user = response.json()
            print(f"  ✅ User: {user.get('displayName')} ({user.get('userPrincipalName')})")
        else:
            print(f"  ❌ User profile failed: {response.status_code}")
            if response.status_code == 401:
                print("    Token may be expired - attempting refresh...")
                if self.refresh_oauth_tokens():
                    headers = {'Authorization': f'Bearer {self.oauth_tokens["access_token"]}'}
                    return self.test_microsoft_graph_detailed()  # Retry
            return False
        
        # Test 2: Email access
        print("  Testing email access...")
        email_response = requests.get(
            'https://graph.microsoft.com/v1.0/me/messages?$top=1',
            headers=headers
        )
        if email_response.status_code == 200:
            emails = email_response.json().get('value', [])
            print(f"  ✅ Email access working ({len(emails)} messages found)")
        else:
            print(f"  ❌ Email access failed: {email_response.status_code}")
            print(f"    Response: {email_response.text[:200]}...")
        
        # Test 3: OneDrive access
        print("  Testing OneDrive access...")
        drive_response = requests.get(
            'https://graph.microsoft.com/v1.0/me/drive',
            headers=headers
        )
        if drive_response.status_code == 200:
            drive = drive_response.json()
            print(f"  ✅ OneDrive access working ({drive.get('driveType', 'unknown')} drive)")
        else:
            print(f"  ❌ OneDrive access failed: {drive_response.status_code}")
            print(f"    Response: {drive_response.text[:200]}...")
        
        return True
    
    def test_azure_storage_detailed(self):
        """Detailed Azure Storage test"""
        print("\n🔍 Testing Azure Storage...")
        
        connection_string = self.config.get('AZURE_STORAGE_CONNECTION_STRING')
        if not connection_string:
            print("❌ No storage connection string configured")
            return False
        
        print(f"  Connection string: {connection_string[:50]}...")
        
        try:
            # Test connection
            blob_service = BlobServiceClient.from_connection_string(connection_string)
            
            # Test account info
            print("  Testing account info...")
            account_info = blob_service.get_account_information()
            print(f"  ✅ Account type: {account_info.get('account_kind', 'Unknown')}")
            
            # Test container listing
            print("  Testing container access...")
            containers = list(blob_service.list_containers())
            print(f"  ✅ Found {len(containers)} containers")
            
            for container in containers:
                print(f"    - {container.name}")
            
            # Test creating/accessing voice-files container
            print("  Testing voice-files container...")
            container_client = blob_service.get_container_client("voice-files")
            try:
                container_client.get_container_properties()
                print("  ✅ voice-files container exists")
            except Exception as e:
                if "ContainerNotFound" in str(e):
                    print("  ℹ️ voice-files container not found, creating...")
                    try:
                        container_client.create_container()
                        print("  ✅ voice-files container created")
                    except Exception as create_error:
                        print(f"  ❌ Failed to create container: {create_error}")
                else:
                    print(f"  ❌ Container access error: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ Storage test failed: {e}")
            
            # Check if it's an authentication error
            if "AuthenticationFailed" in str(e):
                print("  This appears to be an authentication issue.")
                print("  Checking Key Vault for correct storage key...")
                return self.check_storage_key_in_keyvault()
            
            return False
    
    def check_storage_key_in_keyvault(self):
        """Check if storage key in Key Vault matches connection string"""
        print("  Checking Key Vault for storage credentials...")
        
        key_vault_url = self.config.get('KEY_VAULT_URL')
        if not key_vault_url:
            print("  ❌ No Key Vault URL configured")
            return False
        
        try:
            credential = DefaultAzureCredential()
            secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
            
            # Get storage account key from Key Vault
            storage_key_secret = secret_client.get_secret("storage-account-key")
            kv_storage_key = storage_key_secret.value
            
            # Extract key from connection string
            conn_string = self.config.get('AZURE_STORAGE_CONNECTION_STRING', '')
            if 'AccountKey=' in conn_string:
                cs_storage_key = conn_string.split('AccountKey=')[1].split(';')[0]
                
                if kv_storage_key == cs_storage_key:
                    print("  ✅ Storage keys match between Key Vault and connection string")
                else:
                    print("  ❌ Storage key mismatch!")
                    print(f"    Key Vault key: {kv_storage_key[:20]}...")
                    print(f"    Connection string key: {cs_storage_key[:20]}...")
                    print("  💡 You may need to update local.settings.json with the correct key")
            else:
                print("  ⚠️ Cannot extract key from connection string")
            
        except Exception as e:
            print(f"  ❌ Key Vault check failed: {e}")
        
        return False
    
    def run_full_diagnosis(self):
        """Run complete service diagnosis"""
        print("🔍 Service Diagnostic Tool")
        print("=" * 40)
        
        # Check OAuth tokens
        if self.oauth_tokens:
            if not self.check_token_expiry():
                self.refresh_oauth_tokens()
        
        # Test Microsoft Graph
        self.test_microsoft_graph_detailed()
        
        # Test Azure Storage
        self.test_azure_storage_detailed()
        
        print("\n📋 Diagnosis complete!")
        print("Run the comprehensive test again to see improvements.")

def main():
    diagnostic = ServiceDiagnostic()
    diagnostic.run_full_diagnosis()

if __name__ == "__main__":
    main()
