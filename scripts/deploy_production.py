#!/usr/bin/env python3
"""
🚀 Production Deployment Script for Scribe Voice Email Processor

This script handles the complete deployment of the Scribe voice email processing system to Azure.
Designed for production use with comprehensive error handling and validation.

Features:
- Pre-deployment validation
- Azure resource verification
- Function app deployment
- Environment configuration
- OAuth token upload to Key Vault
- Post-deployment verification
- Deployment summary and monitoring info

Usage:
    python scripts/deploy_production.py
    
Prerequisites:
    - Azure CLI installed and logged in
    - Azure resources created (Function App, Key Vault, Storage, Speech Service)
    - OAuth tokens generated (scripts/get_new_token.py)
    - Environment variables configured
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

class ProductionDeployer:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.deployment_config = self.load_deployment_config()
        
    def load_deployment_config(self):
        """Load deployment configuration"""
        config_file = self.project_root / ".deployment_info.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        return {}
        
    def log(self, message, level="INFO"):
        """Enhanced logging with timestamps and levels"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        emoji_map = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌", 
            "WARNING": "⚠️",
            "STEP": "🔄",
            "DEPLOY": "🚀",
            "VERIFY": "🔍"
        }
        print(f"[{timestamp}] {emoji_map.get(level, 'ℹ️')} {message}")
        
    def check_prerequisites(self):
        """Comprehensive prerequisite checks"""
        self.log("Checking deployment prerequisites", "STEP")
        
        checks = [
            ("Azure CLI", self.check_azure_cli),
            ("Azure Login", self.check_azure_login),
            ("OAuth Tokens", self.check_oauth_tokens),
            ("Local Settings", self.check_local_settings),
            ("Project Structure", self.check_project_structure)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            if not check_func():
                self.log(f"❌ {check_name} check failed", "ERROR")
                all_passed = False
            else:
                self.log(f"✅ {check_name} check passed", "SUCCESS")
                
        return all_passed
        
    def check_azure_cli(self):
        """Check Azure CLI installation"""
        try:
            result = subprocess.run(['az', '--version'], 
                                  capture_output=True, text=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log("Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli", "ERROR")
            return False
            
    def check_azure_login(self):
        """Verify Azure CLI login status"""
        try:
            result = subprocess.run(['az', 'account', 'show'], 
                                  capture_output=True, text=True, check=True)
            account_info = json.loads(result.stdout)
            self.log(f"Logged in as: {account_info['user']['name']} ({account_info['name']})")
            return True
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            self.log("Not logged into Azure CLI. Please run: az login", "ERROR")
            return False
            
    def check_oauth_tokens(self):
        """Check OAuth tokens exist and are valid"""
        tokens_file = self.project_root / ".oauth_tokens.json"
        if not tokens_file.exists():
            self.log("OAuth tokens not found. Run: python scripts/get_new_token.py", "ERROR")
            return False
            
        try:
            with open(tokens_file, 'r') as f:
                tokens = json.load(f)
            required_keys = ['access_token', 'refresh_token']
            if all(key in tokens for key in required_keys):
                return True
            else:
                self.log("Invalid token format. Re-run OAuth setup.", "ERROR")
                return False
        except json.JSONDecodeError:
            self.log("Corrupted token file. Re-run OAuth setup.", "ERROR")
            return False
            
    def check_local_settings(self):
        """Verify local.settings.json configuration"""
        settings_file = self.project_root / "local.settings.json"
        if not settings_file.exists():
            self.log("local.settings.json not found", "ERROR")
            return False
            
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                
            required_settings = [
                'SPEECH_SERVICE_KEY',
                'SPEECH_SERVICE_REGION', 
                'EXCEL_FILE_NAME',
                'TARGET_USER_EMAIL',
                'KEY_VAULT_URL'
            ]
            
            values = settings.get('Values', {})
            missing = [key for key in required_settings if not values.get(key)]
            
            if missing:
                self.log(f"Missing required settings: {', '.join(missing)}", "ERROR")
                return False
                
            return True
        except json.JSONDecodeError:
            self.log("Invalid local.settings.json format", "ERROR")
            return False
            
    def check_project_structure(self):
        """Verify project structure is complete"""
        required_files = [
            'function_app.py',
            'host.json',
            'requirements.txt',
            'ProcessEmails/function.json',
            'ProcessEmails/__init__.py'
        ]
        
        missing_files = []
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                missing_files.append(file_path)
                
        if missing_files:
            self.log(f"Missing project files: {', '.join(missing_files)}", "ERROR")
            return False
            
        return True
        
    def get_deployment_info(self):
        """Get deployment information from user or config"""
        config = self.deployment_config
        
        # Get or prompt for required information
        function_app = config.get('function_app_name') or input("🔸 Function App name: ")
        resource_group = config.get('resource_group') or input("🔸 Resource Group name: ")
        keyvault_name = config.get('keyvault_name') or input("🔸 Key Vault name: ")
        
        # Save for future use
        updated_config = {
            'function_app_name': function_app,
            'resource_group': resource_group,
            'keyvault_name': keyvault_name,
            'last_deployment': datetime.now().isoformat()
        }
        
        with open(self.project_root / ".deployment_info.json", 'w') as f:
            json.dump(updated_config, f, indent=2)
            
        return function_app, resource_group, keyvault_name
        
    def deploy_function_app(self, function_app_name):
        """Deploy the Function App using Azure Functions Core Tools"""
        self.log(f"Deploying Function App: {function_app_name}", "DEPLOY")
        
        try:
            # Change to project directory
            original_dir = os.getcwd()
            os.chdir(self.project_root)
            
            # Deploy using func command
            cmd = ['func', 'azure', 'functionapp', 'publish', function_app_name, '--python']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.log("Function App deployed successfully", "SUCCESS")
            self.log("Deploy output (last 5 lines):")
            for line in result.stdout.strip().split('\n')[-5:]:
                print(f"    {line}")
                
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Deployment failed: {e.stderr}", "ERROR")
            return False
        except FileNotFoundError:
            self.log("Azure Functions Core Tools not found. Install: https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local", "ERROR")
            return False
        finally:
            os.chdir(original_dir)
            
    def configure_app_settings(self, function_app_name, resource_group):
        """Configure Function App application settings"""
        self.log("Configuring application settings", "STEP")
        
        # Load local settings
        with open(self.project_root / "local.settings.json", 'r') as f:
            local_settings = json.load(f)
            
        settings = local_settings.get('Values', {})
        
        # Filter out Azure WebJobs settings (handled automatically)
        app_settings = {k: v for k, v in settings.items() 
                       if not k.startswith('AzureWebJobs') and k != 'FUNCTIONS_WORKER_RUNTIME'}
        
        try:
            settings_args = []
            for key, value in app_settings.items():
                settings_args.extend(['--settings', f'{key}={value}'])
                
            cmd = [
                'az', 'functionapp', 'config', 'appsettings', 'set',
                '--name', function_app_name,
                '--resource-group', resource_group
            ] + settings_args
            
            subprocess.run(cmd, check=True, capture_output=True)
            self.log(f"Configured {len(app_settings)} application settings", "SUCCESS")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to configure app settings: {e.stderr}", "ERROR")
            return False
            
    def upload_oauth_tokens(self, keyvault_name):
        """Upload OAuth tokens to Azure Key Vault"""
        self.log("Uploading OAuth tokens to Key Vault", "STEP")
        
        try:
            with open(self.project_root / ".oauth_tokens.json", 'r') as f:
                tokens = json.load(f)
                
            # Upload access token
            cmd = [
                'az', 'keyvault', 'secret', 'set',
                '--vault-name', keyvault_name,
                '--name', 'personal-account-access-token',
                '--value', tokens['access_token']
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Upload refresh token
            cmd = [
                'az', 'keyvault', 'secret', 'set',
                '--vault-name', keyvault_name,
                '--name', 'personal-account-refresh-token', 
                '--value', tokens['refresh_token']
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            self.log("OAuth tokens uploaded successfully", "SUCCESS")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to upload tokens: {e.stderr}", "ERROR")
            return False
            
    def verify_deployment(self, function_app_name, resource_group):
        """Verify deployment is successful"""
        self.log("Verifying deployment", "VERIFY")
        
        checks = [
            ("Function App Status", self.verify_function_app_status),
            ("Function Exists", self.verify_function_exists),
            ("App Settings", self.verify_app_settings),
            ("Timer Trigger", self.verify_timer_configuration)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            if not check_func(function_app_name, resource_group):
                self.log(f"❌ {check_name} verification failed", "WARNING")
                all_passed = False
            else:
                self.log(f"✅ {check_name} verified", "SUCCESS")
                
        return all_passed
        
    def verify_function_app_status(self, function_app_name, resource_group):
        """Check if Function App is running"""
        try:
            cmd = [
                'az', 'functionapp', 'show',
                '--name', function_app_name,
                '--resource-group', resource_group,
                '--query', 'state',
                '--output', 'tsv'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip() == 'Running'
        except subprocess.CalledProcessError:
            return False
            
    def verify_function_exists(self, function_app_name, resource_group):
        """Check if ProcessEmails function exists"""
        try:
            cmd = [
                'az', 'functionapp', 'function', 'show',
                '--name', function_app_name,
                '--resource-group', resource_group,
                '--function-name', 'ProcessEmails'
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
            
    def verify_app_settings(self, function_app_name, resource_group):
        """Verify critical app settings are configured"""
        try:
            cmd = [
                'az', 'functionapp', 'config', 'appsettings', 'list',
                '--name', function_app_name,
                '--resource-group', resource_group
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            settings = json.loads(result.stdout)
            
            required_keys = ['SPEECH_SERVICE_KEY', 'KEY_VAULT_URL', 'TARGET_USER_EMAIL']
            setting_names = [s['name'] for s in settings]
            
            return all(key in setting_names for key in required_keys)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return False
            
    def verify_timer_configuration(self, function_app_name, resource_group):
        """Verify timer trigger is configured correctly"""
        function_json_path = self.project_root / "ProcessEmails" / "function.json"
        try:
            with open(function_json_path, 'r') as f:
                function_config = json.load(f)
                
            # Check for timer trigger
            bindings = function_config.get('bindings', [])
            timer_binding = next((b for b in bindings if b['type'] == 'timerTrigger'), None)
            
            if timer_binding and timer_binding.get('schedule') == '0 */1 * * * *':
                return True
            return False
        except (FileNotFoundError, json.JSONDecodeError):
            return False
            
    def show_deployment_summary(self, function_app_name, resource_group):
        """Display comprehensive deployment summary"""
        print("\n" + "="*80)
        print("🎉 SCRIBE DEPLOYMENT COMPLETED SUCCESSFULLY!")
        print("="*80)
        print(f"📱 Function App: {function_app_name}")
        print(f"📁 Resource Group: {resource_group}")
        print(f"⏱️  Schedule: Every minute (1-minute response time)")
        print(f"🔄 Process: Voice Emails → Speech Recognition → Excel Logging")
        print(f"📊 Features: Folder organization, duplicate prevention, continuous recognition")
        
        print(f"\n🔍 MONITORING & MANAGEMENT")
        print(f"Azure Portal: https://portal.azure.com")
        print(f"Function Logs: az functionapp logs tail --name {function_app_name} --resource-group {resource_group}")
        print(f"Function URL: https://{function_app_name}.azurewebsites.net")
        
        print(f"\n✅ TESTING CHECKLIST")
        print(f"1. Send voice email to {self.get_target_email()}")
        print(f"2. Wait 1-2 minutes for processing")
        print(f"3. Check Azure Function logs for execution")
        print(f"4. Verify Excel file updated on OneDrive")
        print(f"5. Confirm email moved to 'Voice Messages Processed' folder")
        
        print(f"\n📚 DOCUMENTATION")
        print(f"Deployment Guide: docs/DEPLOYMENT.md")
        print(f"Configuration: docs/CONFIGURATION.md")
        print(f"API Reference: docs/API_REFERENCE.md")
        print(f"Project Structure: docs/PROJECT_STRUCTURE.md")
        
        print(f"\n💡 PERFORMANCE EXPECTATIONS")
        print(f"Response Time: ~1 minute from email arrival")
        print(f"Audio Length: Supports 60+ second voice messages")
        print(f"Daily Executions: ~1440 (every minute)")
        print(f"Cost: Minimal (consumption plan + speech service usage)")
        print("="*80)
        
    def get_target_email(self):
        """Get target email from settings"""
        try:
            with open(self.project_root / "local.settings.json", 'r') as f:
                settings = json.load(f)
            return settings.get('Values', {}).get('TARGET_USER_EMAIL', 'your-email@outlook.com')
        except:
            return 'your-email@outlook.com'
            
    def run_production_deployment(self):
        """Execute the complete production deployment process"""
        self.log("🚀 Starting Scribe Production Deployment", "DEPLOY")
        
        # Phase 1: Prerequisites
        if not self.check_prerequisites():
            self.log("Prerequisites not met. Please fix issues and try again.", "ERROR")
            return False
            
        # Phase 2: Get deployment configuration
        function_app_name, resource_group, keyvault_name = self.get_deployment_info()
        
        # Phase 3: Deployment steps
        deployment_steps = [
            ("Deploy Function App", lambda: self.deploy_function_app(function_app_name)),
            ("Configure App Settings", lambda: self.configure_app_settings(function_app_name, resource_group)),
            ("Upload OAuth Tokens", lambda: self.upload_oauth_tokens(keyvault_name)),
            ("Verify Deployment", lambda: self.verify_deployment(function_app_name, resource_group))
        ]
        
        for step_name, step_func in deployment_steps:
            self.log(f"Executing: {step_name}", "STEP")
            if not step_func():
                self.log(f"❌ Deployment failed at: {step_name}", "ERROR")
                self.log("Check logs above for details. Fix issues and re-run deployment.", "ERROR")
                return False
                
        # Phase 4: Success summary
        self.show_deployment_summary(function_app_name, resource_group)
        return True

def main():
    """Main deployment entry point"""
    deployer = ProductionDeployer()
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        print(__doc__)
        return
        
    try:
        success = deployer.run_production_deployment()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
