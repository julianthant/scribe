#!/usr/bin/env python3
"""
Production Deployment Script
Deploy Key Vault OAuth integration to production using deployment manager
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from helpers.deployment_manager import DeploymentManager, DeploymentConfig

def main():
    """Main deployment function"""
    print("🚀 Production Deployment - Key Vault OAuth")
    print("=" * 50)
    
    # Initialize deployment manager
    config = DeploymentConfig()
    manager = DeploymentManager(config)
    
    print(f"Function: {config.function_name}")
    print(f"Resource Group: {config.resource_group}")
    print(f"Key Vault: {config.key_vault_url}")
    
    # Execute complete OAuth deployment
    result = manager.setup_production_oauth_deployment()
    
    if result.success:
        print(f"\n🎉 DEPLOYMENT SUCCESSFUL!")
        print("=" * 30)
        print("✅ Environment variables updated")
        print("✅ Code deployed")
        print("✅ Key Vault OAuth activated")
        print("✅ Production verification passed")
        print(f"\nMessage: {result.message}")
        
        if result.details:
            print(f"Auth Method: {result.details.get('auth_method', 'Unknown')}")
            print(f"Health Status: {result.details.get('health_status', 'Unknown')}")
    else:
        print(f"\n❌ DEPLOYMENT FAILED!")
        print("=" * 25)
        print(f"Error: {result.message}")
        
        if result.details:
            print("Details:")
            for key, value in result.details.items():
                print(f"  {key}: {value}")
    
    return 0 if result.success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)