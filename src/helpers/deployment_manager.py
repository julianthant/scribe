"""
Production Deployment Manager
Handles Azure Function deployment, configuration, and monitoring
"""

import subprocess
import json
import logging
import os
import time
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DeploymentConfig:
    """Configuration for deployment"""
    function_name: str = os.getenv('AZURE_FUNCTION_NAME', 'your-function-app')
    resource_group: str = os.getenv('AZURE_RESOURCE_GROUP', 'your-resource-group') 
    key_vault_url: str = os.getenv('KEY_VAULT_URL', 'https://your-keyvault.vault.azure.net/')
    subscription_id: str = os.getenv('AZURE_SUBSCRIPTION_ID', 'your-subscription-id')

@dataclass
class DeploymentResult:
    """Result of deployment operation"""
    success: bool
    message: str
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}

class DeploymentManager:
    """Manages Azure Function deployment and configuration"""
    
    def __init__(self, config: DeploymentConfig = None):
        self.config = config or DeploymentConfig()
        
    def run_az_command(self, command: str, timeout: int = 60) -> Tuple[bool, str]:
        """Run Azure CLI command safely"""
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                logger.error(f"Command failed: {command}")
                logger.error(f"Error: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Command exception: {e}")
            return False, str(e)
    
    def update_function_app_settings(self, settings: Dict[str, str]) -> DeploymentResult:
        """Update Azure Function App environment variables"""
        logger.info("🔧 Updating Azure Function App Settings")
        
        failed_settings = []
        
        for key, value in settings.items():
            command = f"az functionapp config appsettings set --name {self.config.function_name} --resource-group {self.config.resource_group} --settings {key}={value}"
            
            success, output = self.run_az_command(command)
            if success:
                logger.info(f"✅ {key} updated")
            else:
                logger.error(f"❌ Failed to update {key}: {output}")
                failed_settings.append(key)
        
        if failed_settings:
            return DeploymentResult(
                success=False,
                message=f"Failed to update settings: {failed_settings}",
                details={"failed_settings": failed_settings}
            )
        
        return DeploymentResult(
            success=True,
            message="All settings updated successfully"
        )
    
    def deploy_function_code(self) -> DeploymentResult:
        """Deploy function code to Azure"""
        logger.info("📦 Deploying Function Code")
        
        # Try Azure Functions Core Tools first
        command = f"func azure functionapp publish {self.config.function_name}"
        success, output = self.run_az_command(command, timeout=300)
        
        if success:
            return DeploymentResult(
                success=True,
                message="Code deployment successful",
                details={"method": "func_tools", "output": output}
            )
        
        # Fallback: try az CLI deployment
        logger.info("🔄 Trying alternative deployment method...")
        command = f"az functionapp deployment source config-zip --name {self.config.function_name} --resource-group {self.config.resource_group} --src function.zip"
        success, output = self.run_az_command(command, timeout=300)
        
        if success:
            return DeploymentResult(
                success=True,
                message="Alternative deployment successful",
                details={"method": "az_cli", "output": output}
            )
        
        return DeploymentResult(
            success=False,
            message="Both deployment methods failed",
            details={"error": output}
        )
    
    def verify_deployment(self, base_url: str) -> DeploymentResult:
        """Verify deployment is working"""
        logger.info("🧪 Verifying Deployment")
        
        # Wait for deployment to propagate
        time.sleep(30)
        
        # Test health endpoint
        try:
            response = requests.get(f"{base_url}/api/health", timeout=30)
            if response.status_code == 200:
                health_data = response.json()
                logger.info("✅ Health endpoint working")
            else:
                return DeploymentResult(
                    success=False,
                    message=f"Health endpoint failed: {response.status_code}"
                )
        except Exception as e:
            return DeploymentResult(
                success=False,
                message=f"Health endpoint test failed: {e}"
            )
        
        # Test auth endpoint
        try:
            response = requests.get(f"{base_url}/api/auth", timeout=30)
            if response.status_code == 200:
                auth_data = response.json()
                auth_method = auth_data.get('auth_method', 'unknown')
                
                if auth_method == 'keyvault_oauth':
                    logger.info("✅ Key Vault OAuth is working")
                    return DeploymentResult(
                        success=True,
                        message="Deployment verification successful",
                        details={
                            "auth_method": auth_method,
                            "health_status": health_data.get('status', 'unknown')
                        }
                    )
                else:
                    return DeploymentResult(
                        success=False,
                        message=f"Unexpected auth method: {auth_method}"
                    )
            else:
                return DeploymentResult(
                    success=False,
                    message=f"Auth endpoint failed: {response.status_code}"
                )
        except Exception as e:
            return DeploymentResult(
                success=False,
                message=f"Auth endpoint test failed: {e}"
            )
    
    def get_function_status(self) -> Dict:
        """Get current function status"""
        command = f"az functionapp show --name {self.config.function_name} --resource-group {self.config.resource_group} --query {{state:state,hostNames:defaultHostName,kind:kind}}"
        
        success, output = self.run_az_command(command)
        if success:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return {"error": "Failed to parse function status"}
        
        return {"error": f"Failed to get function status: {output}"}
    
    def setup_production_oauth_deployment(self) -> DeploymentResult:
        """Complete OAuth deployment setup"""
        logger.info("🚀 Setting up Production OAuth Deployment")
        
        # Step 1: Update environment variables
        oauth_settings = {
            "KEY_VAULT_URL": self.config.key_vault_url,
            "AUTH_METHOD": "personal_oauth",
            "TARGET_USER_EMAIL": "me",
            "OUTLOOK_USERNAME": os.getenv('OUTLOOK_USERNAME', 'user@example.com'),
            "SPEECH_ENDPOINT": "https://westus.api.cognitive.microsoft.com"
        }
        
        settings_result = self.update_function_app_settings(oauth_settings)
        if not settings_result.success:
            return settings_result
        
        # Step 2: Remove sensitive environment variables
        logger.info("🔐 Removing OAUTH_REFRESH_TOKEN from environment")
        command = f"az functionapp config appsettings delete --name {self.config.function_name} --resource-group {self.config.resource_group} --setting-names OAUTH_REFRESH_TOKEN"
        success, output = self.run_az_command(command)
        
        if success:
            logger.info("✅ OAUTH_REFRESH_TOKEN removed (now in Key Vault)")
        else:
            logger.warning(f"⚠️ Could not remove OAUTH_REFRESH_TOKEN: {output}")
        
        # Step 3: Deploy code
        deployment_result = self.deploy_function_code()
        if not deployment_result.success:
            return deployment_result
        
        # Step 4: Verify deployment
        base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
        verification_result = self.verify_deployment(base_url)
        
        return verification_result