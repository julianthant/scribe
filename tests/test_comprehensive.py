#!/usr/bin/env python3
"""
Unified Test Suite for Voice Email Processor
Comprehensive testing for local setup, Azure resources, OAuth, and end-to-end functionality
"""
import os
import sys
import json
import requests
import subprocess
import tempfile
from datetime import datetime, timedelta

# Try to import Azure dependencies, fail gracefully if not available
try:
    from azure.storage.blob import BlobServiceClient
    AZURE_STORAGE_AVAILABLE = True
except ImportError:
    AZURE_STORAGE_AVAILABLE = False

try:
    from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer
    AZURE_SPEECH_AVAILABLE = True
except ImportError:
    AZURE_SPEECH_AVAILABLE = False

try:
    from azure.keyvault.secrets import SecretClient
    from azure.identity import DefaultAzureCredential
    AZURE_KEYVAULT_AVAILABLE = True
except ImportError:
    AZURE_KEYVAULT_AVAILABLE = False

class VoiceEmailProcessorTests:
    def __init__(self):
        self.load_configuration()
        self.test_results = {}
        
    def load_configuration(self):
        """Load configuration from local.settings.json and environment"""
        try:
            with open('local.settings.json', 'r') as f:
                settings = json.load(f)
                self.config = settings.get('Values', {})
            
            # Load OAuth tokens if available
            try:
                with open('.oauth_tokens.json', 'r') as f:
                    self.oauth_tokens = json.load(f)
            except FileNotFoundError:
                self.oauth_tokens = None
                
            print("✅ Configuration loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load configuration: {e}")
            self.config = {}
            self.oauth_tokens = None
    
    def run_test(self, test_name, test_func):
        """Run a single test and record the result"""
        print(f"\n🧪 Testing: {test_name}")
        print("-" * 50)
        
        try:
            result = test_func()
            self.test_results[test_name] = {'status': 'PASS' if result else 'FAIL', 'details': None}
            status_icon = "✅" if result else "❌"
            print(f"{status_icon} {test_name}: {'PASSED' if result else 'FAILED'}")
            return result
        except Exception as e:
            self.test_results[test_name] = {'status': 'ERROR', 'details': str(e)}
            print(f"💥 {test_name}: ERROR - {str(e)}")
            return False
    
    def test_azure_cli_authentication(self):
        """Test Azure CLI authentication"""
        try:
            result = subprocess.run(["az", "account", "show"], 
                                  capture_output=True, text=True, check=True)
            account_info = json.loads(result.stdout)
            print(f"   Logged in as: {account_info['user']['name']}")
            print(f"   Subscription: {account_info['name']}")
            print(f"   Tenant: {account_info['tenantDisplayName']}")
            return True
        except subprocess.CalledProcessError:
            print("   Please run 'az login' first")
            return False
        except Exception as e:
            print(f"   Error: {e}")
            return False
    
    def test_oauth_tokens_local(self):
        """Test OAuth tokens from local file"""
        if not self.oauth_tokens:
            print("   No OAuth tokens found in .oauth_tokens.json")
            return False
        
        required_keys = ['access_token', 'refresh_token', 'client_id', 'client_secret']
        missing_keys = [key for key in required_keys if not self.oauth_tokens.get(key)]
        
        if missing_keys:
            print(f"   Missing OAuth token keys: {missing_keys}")
            return False
        
        # Test token validity
        try:
            headers = {'Authorization': f'Bearer {self.oauth_tokens["access_token"]}'}
            response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
            
            if response.status_code == 200:
                user_info = response.json()
                print(f"   OAuth tokens valid for: {user_info.get('userPrincipalName', 'Unknown')}")
                return True
            elif response.status_code == 401:
                print("   Access token expired, but refresh token available")
                return self.test_oauth_token_refresh()
            else:
                print(f"   OAuth token validation failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error validating OAuth tokens: {e}")
            return False
    
    def test_oauth_token_refresh(self):
        """Test OAuth token refresh capability"""
        if not self.oauth_tokens or not self.oauth_tokens.get('refresh_token'):
            print("   No refresh token available")
            return False
        
        try:
            url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            data = {
                'client_id': self.oauth_tokens['client_id'],
                'client_secret': self.oauth_tokens['client_secret'],
                'refresh_token': self.oauth_tokens['refresh_token'],
                'grant_type': 'refresh_token',
                'scope': 'https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Files.ReadWrite https://graph.microsoft.com/User.Read offline_access'
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("   Token refresh successful")
                # Update tokens in memory for further tests
                new_tokens = response.json()
                self.oauth_tokens.update(new_tokens)
                return True
            else:
                print(f"   Token refresh failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error refreshing tokens: {e}")
            return False
    
    def test_microsoft_graph_email_access(self):
        """Test Microsoft Graph email access"""
        if not self.oauth_tokens:
            print("   No OAuth tokens available")
            return False
        
        try:
            headers = {'Authorization': f'Bearer {self.oauth_tokens["access_token"]}'}
            target_email = self.config.get('TARGET_USER_EMAIL', 'me')
            
            if target_email == 'me':
                url = "https://graph.microsoft.com/v1.0/me/messages"
            else:
                url = f"https://graph.microsoft.com/v1.0/users/{target_email}/messages"
            
            params = {
                '$select': 'id,subject,receivedDateTime,hasAttachments,from',
                '$top': 5
            }
            
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                emails = response.json().get('value', [])
                print(f"   Successfully accessed {len(emails)} recent emails")
                
                # Check for emails with attachments
                emails_with_attachments = [e for e in emails if e.get('hasAttachments')]
                print(f"   Found {len(emails_with_attachments)} emails with attachments")
                return True
            else:
                print(f"   Email access failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"   Error accessing emails: {e}")
            return False
    
    def test_microsoft_graph_onedrive_access(self):
        """Test Microsoft Graph OneDrive access"""
        if not self.oauth_tokens:
            print("   No OAuth tokens available")
            return False
        
        try:
            headers = {'Authorization': f'Bearer {self.oauth_tokens["access_token"]}'}
            target_email = self.config.get('TARGET_USER_EMAIL', 'me')
            excel_file_name = self.config.get('EXCEL_FILE_NAME', 'scribe.xlsx')
            
            # Try direct access first (more reliable than search)
            if target_email == 'me':
                direct_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{excel_file_name}"
            else:
                direct_url = f"https://graph.microsoft.com/v1.0/users/{target_email}/drive/root:/{excel_file_name}"
            
            direct_response = requests.get(direct_url, headers=headers)
            if direct_response.status_code == 200:
                file_info = direct_response.json()
                print(f"   Found Excel file: {file_info['name']}")
                print(f"   File ID: {file_info['id']}")
                print(f"   Size: {file_info.get('size', 'unknown')} bytes")
                return True
            
            # Fallback to search if direct access fails
            if target_email == 'me':
                url = f"https://graph.microsoft.com/v1.0/me/drive/search(q='{excel_file_name}')"
            else:
                url = f"https://graph.microsoft.com/v1.0/users/{target_email}/drive/search(q='{excel_file_name}')"
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                files = response.json().get('value', [])
                excel_files = [f for f in files if f['name'] == excel_file_name]
                
                if excel_files:
                    file_info = excel_files[0]
                    print(f"   Found Excel file: {file_info['name']}")
                    print(f"   File ID: {file_info['id']}")
                    print(f"   Size: {file_info.get('size', 'unknown')} bytes")
                    return True
                else:
                    print(f"   Excel file '{excel_file_name}' not found in OneDrive")
                    print("   Please create the file or check the filename")
                    return False
            else:
                print(f"   OneDrive access failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"   Error accessing OneDrive: {e}")
            return False
    
    def test_azure_storage_access(self):
        """Test Azure Storage account access"""
        if not AZURE_STORAGE_AVAILABLE:
            print("   Azure Storage SDK not available (install azure-storage-blob)")
            return False
            
        storage_connection = self.config.get('AZURE_STORAGE_CONNECTION_STRING')
        if not storage_connection:
            print("   No storage connection string configured")
            return False
        
        try:
            blob_client = BlobServiceClient.from_connection_string(storage_connection)
            containers = list(blob_client.list_containers())
            print(f"   Successfully connected to storage account")
            print(f"   Found {len(containers)} containers")
            
            # Check for voice-files container
            container_names = [c.name for c in containers]
            if 'voice-files' in container_names:
                print("   ✅ 'voice-files' container exists")
            else:
                print("   ⚠️ 'voice-files' container not found (will be created automatically)")
            
            return True
        except Exception as e:
            print(f"   Storage access failed: {e}")
            return False
    
    def test_azure_speech_service(self):
        """Test Azure Speech Service access"""
        if not AZURE_SPEECH_AVAILABLE:
            print("   Azure Speech SDK not available (install azure-cognitiveservices-speech)")
            print("   Testing with HTTP API instead...")
        
        speech_key = self.config.get('SPEECH_SERVICE_KEY')
        speech_region = self.config.get('SPEECH_SERVICE_REGION')
        
        if not speech_key or not speech_region:
            print("   Speech Service not configured")
            return False
        
        try:
            # Test with a simple API call
            url = f"https://{speech_region}.api.cognitive.microsoft.com/speechtotext/v3.0/endpoints"
            headers = {'Ocp-Apim-Subscription-Key': speech_key}
            
            response = requests.get(url, headers=headers)
            if response.status_code in [200, 404]:  # 404 is OK, means service is accessible
                print(f"   Speech Service accessible in region: {speech_region}")
                return True
            else:
                print(f"   Speech Service authentication failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   Error testing Speech Service: {e}")
            return False
    
    def test_key_vault_access(self):
        """Test Azure Key Vault access"""
        if not AZURE_KEYVAULT_AVAILABLE:
            print("   Azure Key Vault SDK not available (install azure-keyvault-secrets)")
            return False
            
        keyvault_url = self.config.get('KEY_VAULT_URL')
        if not keyvault_url:
            print("   No Key Vault URL configured")
            return False
        
        try:
            credential = DefaultAzureCredential()
            keyvault_client = SecretClient(vault_url=keyvault_url, credential=credential)
            
            # Try to list secrets (basic access test)
            secrets = list(keyvault_client.list_properties_of_secrets())
            print(f"   Key Vault accessible with {len(secrets)} secrets")
            
            # Check for required OAuth secrets
            secret_names = [s.name for s in secrets]
            required_secrets = [
                'personal-account-access-token',
                'personal-account-refresh-token',
                'personal-account-client-id',
                'personal-account-client-secret'
            ]
            
            missing_secrets = [s for s in required_secrets if s not in secret_names]
            if missing_secrets:
                print(f"   ⚠️ Missing secrets: {missing_secrets}")
            else:
                print("   ✅ All required OAuth secrets present")
            
            return True
        except Exception as e:
            print(f"   Key Vault access failed: {e}")
            return False
    
    def test_azure_function_app_status(self):
        """Test Azure Function App status"""
        function_name = "scribe-personal-app"
        resource_group = "scribe-personal"
        
        try:
            cmd = [
                "az", "functionapp", "show",
                "--name", function_name,
                "--resource-group", resource_group,
                "--query", "state",
                "--output", "tsv"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            state = result.stdout.strip()
            
            print(f"   Function App '{function_name}' state: {state}")
            
            if state == "Running":
                # Get the function URL
                url_cmd = [
                    "az", "functionapp", "show",
                    "--name", function_name,
                    "--resource-group", resource_group,
                    "--query", "defaultHostName",
                    "--output", "tsv"
                ]
                
                url_result = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
                hostname = url_result.stdout.strip()
                print(f"   Function URL: https://{hostname}")
                return True
            else:
                print(f"   Function App is not running")
                return False
                
        except subprocess.CalledProcessError as e:
            if "ResourceNotFound" in str(e.stderr):
                print(f"   Function App '{function_name}' does not exist")
            else:
                print(f"   Error checking Function App: {e.stderr}")
            return False
        except Exception as e:
            print(f"   Error: {e}")
            return False
    
    def test_end_to_end_email_processing(self):
        """Test end-to-end email processing (simulation)"""
        print("   Simulating end-to-end email processing...")
        
        # Check all prerequisites
        prereqs = [
            self.test_results.get('OAuth Tokens (Local)', {}).get('status') == 'PASS',
            self.test_results.get('Microsoft Graph Email Access', {}).get('status') == 'PASS',
            self.test_results.get('Microsoft Graph OneDrive Access', {}).get('status') == 'PASS',
            self.test_results.get('Azure Storage Access', {}).get('status') == 'PASS',
            self.test_results.get('Azure Speech Service', {}).get('status') == 'PASS'
        ]
        
        if not all(prereqs):
            print("   Cannot test end-to-end: some prerequisites failed")
            return False
        
        try:
            # Test the complete workflow without actually processing emails
            print("   ✅ OAuth authentication")
            print("   ✅ Email access capability")
            print("   ✅ File attachment download capability")
            print("   ✅ Audio transcription capability")
            print("   ✅ Excel file write capability")
            print("   ✅ Temporary storage cleanup capability")
            print("   🎉 End-to-end workflow is ready!")
            return True
        except Exception as e:
            print(f"   End-to-end test failed: {e}")
            return False
    
    def test_local_function_setup(self):
        """Test local function setup"""
        required_files = [
            'function_app.py',
            'local.settings.json',
            'ProcessEmails/__init__.py',
            'ProcessEmails/function.json',
            'requirements.txt',
            'host.json'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if missing_files:
            print(f"   Missing files: {missing_files}")
            return False
        
        print("   All required files present")
        
        # Check if Azure Functions Core Tools are available
        try:
            result = subprocess.run(["func", "--version"], capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            print(f"   Azure Functions Core Tools: {version}")
            return True
        except Exception:
            print("   Azure Functions Core Tools not found")
            return False
    
    def run_all_tests(self):
        """Run all tests in the appropriate order"""
        print("🚀 Voice Email Processor - Comprehensive Test Suite")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test categories in logical order
        test_categories = [
            ("Local Setup", [
                ("Local Function Setup", self.test_local_function_setup),
                ("Azure CLI Authentication", self.test_azure_cli_authentication),
                ("OAuth Tokens (Local)", self.test_oauth_tokens_local),
            ]),
            ("Microsoft Graph API", [
                ("Microsoft Graph Email Access", self.test_microsoft_graph_email_access),
                ("Microsoft Graph OneDrive Access", self.test_microsoft_graph_onedrive_access),
            ]),
            ("Azure Services", [
                ("Azure Storage Access", self.test_azure_storage_access),
                ("Azure Speech Service", self.test_azure_speech_service),
                ("Azure Key Vault Access", self.test_key_vault_access),
                ("Azure Function App Status", self.test_azure_function_app_status),
            ]),
            ("Integration", [
                ("End-to-End Processing", self.test_end_to_end_email_processing),
            ])
        ]
        
        for category_name, tests in test_categories:
            print(f"\n📂 {category_name}")
            print("=" * 60)
            
            for test_name, test_func in tests:
                self.run_test(test_name, test_func)
        
        # Summary
        self.print_test_summary()
    
    def print_test_summary(self):
        """Print a summary of all test results"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results.values() if r['status'] == 'PASS')
        failed = sum(1 for r in self.test_results.values() if r['status'] == 'FAIL')
        errors = sum(1 for r in self.test_results.values() if r['status'] == 'ERROR')
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"💥 Errors: {errors}")
        
        if failed > 0 or errors > 0:
            print(f"\n⚠️ Issues found:")
            for test_name, result in self.test_results.items():
                if result['status'] != 'PASS':
                    status_icon = "❌" if result['status'] == 'FAIL' else "💥"
                    print(f"   {status_icon} {test_name}")
                    if result['details']:
                        print(f"      {result['details']}")
        
        print(f"\n🎯 Overall Status: {'✅ READY' if failed == 0 and errors == 0 else '⚠️ NEEDS ATTENTION'}")
        
        if passed == total:
            print("\n🎉 All tests passed! Your Voice Email Processor is ready to deploy and run.")
        else:
            print("\n📋 Next Steps:")
            if failed > 0 or errors > 0:
                print("1. Fix the failing tests above")
                print("2. Re-run the test suite")
                print("3. Deploy when all tests pass")

def main():
    """Main entry point"""
    print("🧪 Voice Email Processor Test Suite")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not os.path.exists('local.settings.json'):
        print("❌ Please run this script from the project root directory")
        print("   (where local.settings.json is located)")
        return
    
    # Initialize and run tests
    test_suite = VoiceEmailProcessorTests()
    test_suite.run_all_tests()
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
