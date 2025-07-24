#!/usr/bin/env python3
"""
Deployment script for the Voice Email Processor with dual-account architecture
This script deploys the Azure Function and sets up Key Vault for token management
"""
import subprocess
import json
import requests
import os
from datetime import datetime

class VoiceEmailDeployer:
    def __init__(self):
        self.resource_group = "scribe-personal"
        self.location = "eastus"
        self.function_app_name = "scribe-personal-app"
        self.keyvault_name = "scribe-personal-vault"
        
        # Generate unique storage account name with timestamp
        import time
        timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
        self.storage_account = f"scribepersonal{timestamp}"  # Must be globally unique
        self.speech_service_name = "scribe-personal-speech"
        
        # Load current OAuth tokens
        self.load_oauth_tokens()
        
    def load_oauth_tokens(self):
        """Load existing OAuth tokens from file"""
        try:
            with open('.oauth_tokens.json', 'r') as f:
                self.oauth_tokens = json.load(f)
            print("✅ Loaded existing OAuth tokens")
        except FileNotFoundError:
            print("❌ No OAuth tokens found. Please run OAuth setup first.")
            self.oauth_tokens = None
    
    def create_resource_group(self):
        """Create resource group"""
        print(f"📦 Creating resource group: {self.resource_group}")
        
        create_cmd = [
            "az", "group", "create",
            "--name", self.resource_group,
            "--location", self.location
        ]
        
        try:
            subprocess.run(create_cmd, capture_output=True, text=True, check=True)
            print("✅ Resource group created successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create resource group: {e.stderr}")
            return False

    def create_storage_account(self):
        """Create storage account or use existing one"""
        print(f"💾 Setting up storage account: {self.storage_account}")
        
        # For personal accounts, we might hit subscription limits
        # Let's try to create, but fall back to using existing organizational storage
        create_cmd = [
            "az", "storage", "account", "create",
            "--name", self.storage_account,
            "--resource-group", self.resource_group,
            "--location", self.location,
            "--sku", "Standard_LRS",
            "--kind", "StorageV2"
        ]
        
        try:
            result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
            print("✅ Storage account created successfully")
            
            # Get storage connection string
            conn_cmd = [
                "az", "storage", "account", "show-connection-string",
                "--name", self.storage_account,
                "--resource-group", self.resource_group,
                "--query", "connectionString",
                "--output", "tsv"
            ]
            
            conn_result = subprocess.run(conn_cmd, capture_output=True, text=True, check=True)
            self.storage_connection_string = conn_result.stdout.strip()
            print("✅ Storage connection string retrieved")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Failed to create new storage account: {e.stderr}")
            print("📝 Using existing storage account from configuration...")
            
            # Fall back to existing storage account from local.settings.json
            try:
                with open('local.settings.json', 'r') as f:
                    settings = json.load(f)
                    existing_connection = settings['Values'].get('AZURE_STORAGE_CONNECTION_STRING')
                    
                if existing_connection and 'scribevmblob' in existing_connection:
                    self.storage_connection_string = existing_connection
                    self.storage_account = "scribevmblob"  # Use existing account
                    print("✅ Using existing organizational storage account")
                    return True
                else:
                    print("❌ No valid existing storage account found")
                    return False
            except Exception as fallback_error:
                print(f"❌ Failed to use existing storage account: {fallback_error}")
                return False

    def create_speech_service(self):
        """Create Azure Speech Service"""
        print(f"🗣️ Creating Speech Service: {self.speech_service_name}")
        
        create_cmd = [
            "az", "cognitiveservices", "account", "create",
            "--name", self.speech_service_name,
            "--resource-group", self.resource_group,
            "--location", self.location,
            "--kind", "SpeechServices",
            "--sku", "F0",  # Free tier
            "--yes"
        ]
        
        try:
            subprocess.run(create_cmd, capture_output=True, text=True, check=True)
            print("✅ Speech Service created successfully")
            
            # Get speech service key
            key_cmd = [
                "az", "cognitiveservices", "account", "keys", "list",
                "--name", self.speech_service_name,
                "--resource-group", self.resource_group,
                "--query", "key1",
                "--output", "tsv"
            ]
            
            key_result = subprocess.run(key_cmd, capture_output=True, text=True, check=True)
            self.speech_service_key = key_result.stdout.strip()
            print("✅ Speech Service key retrieved")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create Speech Service: {e.stderr}")
            return False



    def deploy_function_app(self):
        """Deploy the Azure Function App"""
        print(f"🚀 Deploying Azure Function App: {self.function_app_name}")
        
        # Create Function App
        create_cmd = [
            "az", "functionapp", "create",
            "--resource-group", self.resource_group,
            "--consumption-plan-location", self.location,
            "--runtime", "python",
            "--runtime-version", "3.12",
            "--functions-version", "4",
            "--name", self.function_app_name,
            "--storage-account", self.storage_account,
            "--os-type", "Linux",  # Python requires Linux
            "--assign-identity"  # Enable system-assigned managed identity
        ]
        
        try:
            result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
            print("✅ Function App created successfully")
            
            # Get the managed identity principal ID
            identity_cmd = [
                "az", "functionapp", "identity", "show",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group,
                "--query", "principalId",
                "--output", "tsv"
            ]
            
            identity_result = subprocess.run(identity_cmd, capture_output=True, text=True, check=True)
            self.managed_identity_id = identity_result.stdout.strip()
            print(f"✅ Managed Identity ID: {self.managed_identity_id}")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create Function App: {e.stderr}")
            return False
    
    def create_key_vault(self):
        """Create Azure Key Vault and configure access"""
        print(f"🔐 Creating Key Vault: {self.keyvault_name}")
        
        # Create Key Vault with RBAC authorization
        create_cmd = [
            "az", "keyvault", "create",
            "--name", self.keyvault_name,
            "--resource-group", self.resource_group,
            "--location", self.location,
            "--enable-rbac-authorization", "true"
        ]
        
        try:
            subprocess.run(create_cmd, capture_output=True, text=True, check=True)
            print("✅ Key Vault created successfully")
            
            # Get current user's object ID
            user_cmd = [
                "az", "ad", "signed-in-user", "show",
                "--query", "id",
                "--output", "tsv"
            ]
            
            user_result = subprocess.run(user_cmd, capture_output=True, text=True, check=True)
            user_object_id = user_result.stdout.strip()
            
            # Assign Key Vault Secrets Officer role to current user
            role_cmd = [
                "az", "role", "assignment", "create",
                "--role", "Key Vault Secrets Officer",
                "--assignee", user_object_id,
                "--scope", f"/subscriptions/{self.get_subscription_id()}/resourceGroups/{self.resource_group}/providers/Microsoft.KeyVault/vaults/{self.keyvault_name}"
            ]
            
            subprocess.run(role_cmd, capture_output=True, text=True, check=True)
            print("✅ RBAC permissions set for current user")
            
            # Assign Key Vault Secrets User role to Function App managed identity
            if hasattr(self, 'managed_identity_id'):
                role_cmd2 = [
                    "az", "role", "assignment", "create",
                    "--role", "Key Vault Secrets User",
                    "--assignee", self.managed_identity_id,
                    "--scope", f"/subscriptions/{self.get_subscription_id()}/resourceGroups/{self.resource_group}/providers/Microsoft.KeyVault/vaults/{self.keyvault_name}"
                ]
                
                subprocess.run(role_cmd2, capture_output=True, text=True, check=True)
                print("✅ RBAC permissions set for Function App managed identity")
            
            # Get Key Vault URL
            url_cmd = [
                "az", "keyvault", "show",
                "--name", self.keyvault_name,
                "--resource-group", self.resource_group,
                "--query", "properties.vaultUri",
                "--output", "tsv"
            ]
            
            url_result = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
            self.keyvault_url = url_result.stdout.strip()
            print(f"✅ Key Vault URL: {self.keyvault_url}")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create Key Vault: {e.stderr}")
            return False

    def get_subscription_id(self):
        """Get current subscription ID"""
        cmd = [
            "az", "account", "show",
            "--query", "id",
            "--output", "tsv"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    
    def store_oauth_tokens_in_keyvault(self):
        """Store OAuth tokens in Key Vault"""
        if not self.oauth_tokens:
            print("❌ No OAuth tokens to store")
            return False
        
        print("🔒 Storing OAuth tokens in Key Vault")
        
        secrets = {
            "personal-account-access-token": self.oauth_tokens.get('access_token'),
            "personal-account-refresh-token": self.oauth_tokens.get('refresh_token'),
            "personal-account-client-id": self.oauth_tokens.get('client_id'),
            "personal-account-client-secret": self.oauth_tokens.get('client_secret')
        }
        
        for secret_name, secret_value in secrets.items():
            if secret_value:
                cmd = [
                    "az", "keyvault", "secret", "set",
                    "--vault-name", self.keyvault_name,
                    "--name", secret_name,
                    "--value", secret_value
                ]
                
                try:
                    subprocess.run(cmd, capture_output=True, text=True, check=True)
                    print(f"✅ Stored secret: {secret_name}")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to store {secret_name}: {e.stderr}")
                    return False
        
        print("✅ All OAuth tokens stored in Key Vault")
        return True
    
    def configure_function_app_settings(self):
        """Configure Function App application settings"""
        print("⚙️ Configuring Function App settings")
        
        # Prepare settings for Azure with personal account values
        settings = [
            f"CLIENT_ID={self.oauth_tokens.get('client_id')}",
            f"CLIENT_SECRET={self.oauth_tokens.get('client_secret')}",
            f"TENANT_ID=4d65b975-8618-4496-aabd-2a1d1876c28d",
            f"AZURE_STORAGE_CONNECTION_STRING={self.storage_connection_string}",
            f"SPEECH_SERVICE_KEY={self.speech_service_key}",
            f"SPEECH_SERVICE_REGION={self.location}",
            f"EXCEL_FILE_NAME=scribe.xlsx",
            f"TARGET_USER_EMAIL=julianthant@gmail.com",
            f"KEY_VAULT_URL={self.keyvault_url}"
        ]
        
        # Set application settings
        cmd = [
            "az", "functionapp", "config", "appsettings", "set",
            "--name", self.function_app_name,
            "--resource-group", self.resource_group,
            "--settings"
        ] + settings
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Function App settings configured")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to configure settings: {e.stderr}")
            return False
    
    def update_local_settings(self):
        """Update local.settings.json with new personal account resources"""
        print("📝 Updating local.settings.json with personal account resources")
        
        try:
            with open('local.settings.json', 'r') as f:
                settings = json.load(f)
            
            # Update with new resource configurations
            settings['Values']['AZURE_STORAGE_CONNECTION_STRING'] = self.storage_connection_string
            settings['Values']['SPEECH_SERVICE_KEY'] = self.speech_service_key
            settings['Values']['SPEECH_SERVICE_REGION'] = self.location
            settings['Values']['KEY_VAULT_URL'] = self.keyvault_url
            
            with open('local.settings.json', 'w') as f:
                json.dump(settings, f, indent=2)
            
            print("✅ Local settings updated with personal account resources")
            return True
        except Exception as e:
            print(f"❌ Failed to update local settings: {e}")
            return False
    
    def deploy_function_code(self):
        """Deploy the function code to Azure"""
        print("📦 Deploying function code")
        
        try:
            # Deploy using func tools
            cmd = ["func", "azure", "functionapp", "publish", self.function_app_name]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Function code deployed successfully")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to deploy function code: {e.stderr}")
            return False
    
    def test_deployment(self):
        """Test the deployed function"""
        print("🧪 Testing deployed function")
        
        # Get function URL
        url_cmd = [
            "az", "functionapp", "show",
            "--name", self.function_app_name,
            "--resource-group", self.resource_group,
            "--query", "defaultHostName",
            "--output", "tsv"
        ]
        
        try:
            result = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
            function_url = f"https://{result.stdout.strip()}"
            print(f"✅ Function App URL: {function_url}")
            
            # Check function logs
            logs_cmd = [
                "az", "functionapp", "log", "tail",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group
            ]
            
            print("📝 To monitor function logs, run:")
            print(f"az functionapp log tail --name {self.function_app_name} --resource-group {self.resource_group}")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to get function URL: {e.stderr}")
            return False
    
    def cleanup_on_failure(self):
        """Clean up resources if deployment fails"""
        print("🧹 Cleaning up failed deployment")
        
        # Delete entire resource group (this will delete all resources)
        try:
            cmd = [
                "az", "group", "delete",
                "--name", self.resource_group,
                "--yes", "--no-wait"
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Cleaned up resource group and all resources")
        except:
            print("⚠️ Could not clean up resource group")
    
    def run_deployment(self):
        """Run the complete deployment process"""
        print("🚀 Starting Voice Email Processor Deployment")
        print("=" * 50)
        
        if not self.oauth_tokens:
            print("❌ Cannot deploy without OAuth tokens. Please run OAuth setup first.")
            return False
        
        try:
            # Step 1: Create resource group
            if not self.create_resource_group():
                return False
            
            # Step 2: Create storage account
            if not self.create_storage_account():
                self.cleanup_on_failure()
                return False
            
            # Step 3: Create Speech Service
            if not self.create_speech_service():
                self.cleanup_on_failure()
                return False
            
            # Step 4: Deploy Function App
            if not self.deploy_function_app():
                self.cleanup_on_failure()
                return False
            
            # Step 5: Create Key Vault
            if not self.create_key_vault():
                self.cleanup_on_failure()
                return False
            
            # Step 6: Store OAuth tokens
            if not self.store_oauth_tokens_in_keyvault():
                self.cleanup_on_failure()
                return False
            
            # Step 7: Configure Function App
            if not self.configure_function_app_settings():
                self.cleanup_on_failure()
                return False
            
            # Step 8: Update local settings
            if not self.update_local_settings():
                self.cleanup_on_failure()
                return False
            
            # Step 9: Deploy code
            if not self.deploy_function_code():
                self.cleanup_on_failure()
                return False
            
            # Step 10: Test deployment
            self.test_deployment()
            
            print("\n🎉 Deployment completed successfully!")
            print("=" * 50)
            print(f"Resource Group: {self.resource_group}")
            print(f"Function App: {self.function_app_name}")
            print(f"Storage Account: {self.storage_account}")
            print(f"Speech Service: {self.speech_service_name}")
            print(f"Key Vault: {self.keyvault_name}")
            print("\n📋 Next Steps:")
            print("1. Monitor function logs for any issues")
            print("2. Send a test email with voice attachment")
            print("3. Check your Excel file for results")
            print("4. Run: python3 test_comprehensive.py")
            
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {str(e)}")
            self.cleanup_on_failure()
            return False

def main():
    print("🔧 Voice Email Processor Deployment Tool")
    print("=" * 40)
    
    # Check prerequisites
    print("📋 Checking prerequisites...")
    
    # Check if logged in to Azure
    try:
        result = subprocess.run(["az", "account", "show"], capture_output=True, text=True, check=True)
        account_info = json.loads(result.stdout)
        print(f"✅ Logged in as: {account_info['user']['name']}")
    except:
        print("❌ Not logged in to Azure. Please run 'az login' first.")
        return
    
    # Check if Function Core Tools are available
    try:
        subprocess.run(["func", "--version"], capture_output=True, text=True, check=True)
        print("✅ Azure Functions Core Tools available")
    except:
        print("❌ Azure Functions Core Tools not found. Please install them first.")
        return
    
    # Check if OAuth tokens exist
    if not os.path.exists('.oauth_tokens.json'):
        print("❌ OAuth tokens not found. Please run OAuth setup first.")
        return
    
    print("✅ All prerequisites met")
    
    # Confirm deployment
    print(f"\n⚠️ This will create new Azure resources in your personal account:")
    print("- Resource Group: scribe-personal")
    print("- Storage Account: scribepersonalstorage")
    print("- Speech Service: scribe-personal-speech (Free tier)")
    print("- Azure Function App: scribe-personal-app")
    print("- Azure Key Vault: scribe-personal-vault")
    print("- Configure managed identity and RBAC permissions")
    
    confirm = input("\nProceed with deployment? (y/N): ")
    if confirm.lower() != 'y':
        print("Deployment cancelled")
        return
    
    # Run deployment
    deployer = VoiceEmailDeployer()
    success = deployer.run_deployment()
    
    if success:
        print("\n🌟 Deployment completed successfully!")
    else:
        print("\n💥 Deployment failed. Check the error messages above.")

if __name__ == "__main__":
    main()
