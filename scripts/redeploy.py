#!/usr/bin/env python3
"""
Clean Redeployment Script for Voice Email Processor
This script removes the existing function and deploys fresh
"""
import subprocess
import json
import os
from datetime import datetime

class CleanRedeployer:
    def __init__(self):
        self.function_app_name = "scribe-personal-app"
        self.resource_group = "scribe-personal"
        
    def check_prerequisites(self):
        """Check if all prerequisites are met"""
        print("🔍 Checking prerequisites...")
        
        # Check Azure CLI login
        try:
            result = subprocess.run(["az", "account", "show"], capture_output=True, text=True, check=True)
            account_info = json.loads(result.stdout)
            print(f"✅ Azure CLI logged in as: {account_info['user']['name']}")
        except:
            print("❌ Not logged in to Azure. Please run 'az login' first.")
            return False
        
        # Check Function Core Tools
        try:
            subprocess.run(["func", "--version"], capture_output=True, text=True, check=True)
            print("✅ Azure Functions Core Tools available")
        except:
            print("❌ Azure Functions Core Tools not found. Please install them first.")
            return False
        
        # Check required files
        required_files = ['function_app.py', 'local.settings.json', 'requirements.txt', 'host.json']
        missing_files = [f for f in required_files if not os.path.exists(f)]
        
        if missing_files:
            print(f"❌ Missing required files: {missing_files}")
            return False
        
        print("✅ All required files present")
        return True
    
    def check_function_exists(self):
        """Check if the function app exists"""
        print(f"🔍 Checking if Function App '{self.function_app_name}' exists...")
        
        try:
            cmd = [
                "az", "functionapp", "show",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group,
                "--query", "state",
                "--output", "tsv"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            state = result.stdout.strip()
            print(f"✅ Function App exists and is: {state}")
            return True
            
        except subprocess.CalledProcessError:
            print(f"ℹ️ Function App '{self.function_app_name}' does not exist")
            return False
    
    def stop_function_app(self):
        """Stop the function app before cleanup"""
        print(f"⏹️ Stopping Function App '{self.function_app_name}'...")
        
        try:
            cmd = [
                "az", "functionapp", "stop",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Function App stopped successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Failed to stop Function App: {e.stderr}")
            return False
    
    def clear_function_content(self):
        """Clear all function content from the app"""
        print(f"🧹 Clearing existing function content...")
        
        try:
            # Get the list of functions
            list_cmd = [
                "az", "functionapp", "function", "list",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group,
                "--query", "[].name",
                "--output", "tsv"
            ]
            
            result = subprocess.run(list_cmd, capture_output=True, text=True, check=True)
            functions = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            if functions and functions[0]:  # Check if there are actual functions
                print(f"📝 Found {len(functions)} existing functions: {functions}")
                
                # Delete each function
                for func_name in functions:
                    if func_name.strip():  # Skip empty names
                        delete_cmd = [
                            "az", "functionapp", "function", "delete",
                            "--name", self.function_app_name,
                            "--resource-group", self.resource_group,
                            "--function-name", func_name.strip(),
                            "--yes"
                        ]
                        
                        try:
                            subprocess.run(delete_cmd, capture_output=True, text=True, check=True)
                            print(f"✅ Deleted function: {func_name}")
                        except subprocess.CalledProcessError as e:
                            print(f"⚠️ Failed to delete function {func_name}: {e.stderr}")
            else:
                print("ℹ️ No existing functions found to delete")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Failed to list/delete functions: {e.stderr}")
            # Continue anyway - might be empty
            return True
    
    def restart_function_app(self):
        """Restart the function app"""
        print(f"🔄 Starting Function App '{self.function_app_name}'...")
        
        try:
            cmd = [
                "az", "functionapp", "start",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("✅ Function App started successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Failed to start Function App: {e.stderr}")
            return False
    
    def deploy_fresh_code(self):
        """Deploy the fresh function code"""
        print(f"🚀 Deploying fresh function code to '{self.function_app_name}'...")
        
        try:
            # Deploy using func tools
            cmd = ["func", "azure", "functionapp", "publish", self.function_app_name, "--build", "remote"]
            
            print("📦 Publishing function (this may take a few minutes)...")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            print("✅ Function code deployed successfully!")
            
            # Show deployment info
            if "https://" in result.stdout:
                import re
                urls = re.findall(r'https://[^\s]+', result.stdout)
                if urls:
                    print(f"🌐 Function URL: {urls[0]}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to deploy function code: {e.stderr}")
            print(f"❌ stdout: {e.stdout}")
            return False
    
    def verify_deployment(self):
        """Verify the deployment was successful"""
        print("🔍 Verifying deployment...")
        
        try:
            # Check function status
            cmd = [
                "az", "functionapp", "function", "list",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group,
                "--query", "[].{Name:name, Status:config.disabled}",
                "--output", "table"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("📋 Deployed functions:")
            print(result.stdout)
            
            # Get function app URL
            url_cmd = [
                "az", "functionapp", "show",
                "--name", self.function_app_name,
                "--resource-group", self.resource_group,
                "--query", "defaultHostName",
                "--output", "tsv"
            ]
            
            url_result = subprocess.run(url_cmd, capture_output=True, text=True, check=True)
            function_url = f"https://{url_result.stdout.strip()}"
            print(f"🌐 Function App URL: {function_url}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Verification failed: {e.stderr}")
            return False
    
    def run_clean_redeployment(self):
        """Run the complete clean redeployment process"""
        print("🔄 Voice Email Processor - Clean Redeployment")
        print("=" * 50)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Check prerequisites
        if not self.check_prerequisites():
            print("❌ Prerequisites not met. Exiting.")
            return False
        
        # Step 2: Check if function exists
        function_exists = self.check_function_exists()
        
        if function_exists:
            print(f"\n🧹 Cleaning existing deployment...")
            
            # Step 3: Stop function app
            if not self.stop_function_app():
                print("⚠️ Could not stop function app, continuing anyway...")
            
            # Step 4: Clear function content
            if not self.clear_function_content():
                print("⚠️ Could not clear all function content, continuing anyway...")
            
            # Step 5: Restart function app
            if not self.restart_function_app():
                print("⚠️ Could not restart function app, continuing anyway...")
        
        print(f"\n🚀 Deploying fresh code...")
        
        # Step 6: Deploy fresh code
        if not self.deploy_fresh_code():
            print("❌ Deployment failed!")
            return False
        
        # Step 7: Verify deployment
        if not self.verify_deployment():
            print("⚠️ Verification had issues, but deployment may still be successful")
        
        print(f"\n🎉 Clean redeployment completed!")
        print("=" * 50)
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n📋 Next steps:")
        print(f"1. Monitor function logs: az functionapp log tail --name {self.function_app_name} --resource-group {self.resource_group}")
        print(f"2. Test the function: python3 test_comprehensive.py")
        print(f"3. Send a test email with voice attachment")
        
        return True

def main():
    print("🔄 Clean Redeployment Tool")
    print("=" * 30)
    
    print("This will:")
    print("1. Stop the existing function app")
    print("2. Clear all existing function content")
    print("3. Deploy fresh function code")
    print("4. Verify the deployment")
    
    confirm = input(f"\nProceed with clean redeployment? (y/N): ")
    if confirm.lower() != 'y':
        print("Redeployment cancelled")
        return
    
    redeployer = CleanRedeployer()
    success = redeployer.run_clean_redeployment()
    
    if success:
        print("\n🌟 Clean redeployment completed successfully!")
    else:
        print("\n💥 Clean redeployment failed. Check the error messages above.")

if __name__ == "__main__":
    main()
