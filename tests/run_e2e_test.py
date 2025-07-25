#!/usr/bin/env python3
"""
End-to-End Test Script for Voice Email Processing
Tests the complete workflow using your real inbox with longer connection timeouts
"""

import os
import sys
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables if not already set
def setup_environment():
    """Setup environment variables with longer timeouts"""
    env_vars = {
        'AZURE_STORAGE_CONNECTION_STRING': 'your_storage_connection_string',
        'SPEECH_SERVICE_KEY': os.environ.get('AZURE_SPEECH_KEY', 'your-speech-key-here'),
        'SPEECH_SERVICE_REGION': 'eastus', 
        'AZURE_FOUNDRY_ENDPOINT': 'https://ai-julianthant562797747914.cognitiveservices.azure.com',
        'TENANT_ID': 'your_tenant_id',
        'CLIENT_ID': 'your_client_id', 
        'CLIENT_SECRET': 'your_client_secret',
        'TARGET_USER_EMAIL': 'your_email@domain.com',
        'EXCEL_FILE_NAME': 'Scribe.xlsx'
    }
    
    print("🔧 Setting up environment variables...")
    missing_vars = []
    
    for key, default_value in env_vars.items():
        if not os.environ.get(key):
            if default_value.startswith('your_'):
                missing_vars.append(key)
            else:
                os.environ[key] = default_value
                print(f"✅ Set {key}")
        else:
            print(f"✅ Found {key}")
    
    if missing_vars:
        print(f"\n❌ Please set these environment variables:")
        for var in missing_vars:
            print(f"   export {var}='your_value_here'")
        return False
    
    return True


def run_end_to_end_test():
    """Run the complete end-to-end test"""
    print("🎯 Voice Email Processing - End-to-End Test")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Setup logging with more detail
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'test_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    
    try:
        # Import test class
        from tests.test_real_workflow import RealWorldWorkflowTest
        
        # Create and run test
        print("🚀 Initializing test...")
        test = RealWorldWorkflowTest()
        
        print("📧 Running complete workflow test...")
        test.test_real_workflow()
        
        print("\n✅ End-to-end test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logging.error(f"Test failed: {e}", exc_info=True)
        return False
    
    return True


def check_configuration():
    """Check that all required services are configured"""
    print("\n🔍 Configuration Check:")
    print("-" * 30)
    
    # Check Azure Storage
    storage_conn = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    if storage_conn and 'DefaultEndpointsProtocol' in storage_conn:
        print("✅ Azure Storage: Configured")
    else:
        print("❌ Azure Storage: Not configured")
    
    # Check Speech Service
    speech_key = os.environ.get('SPEECH_SERVICE_KEY')
    speech_region = os.environ.get('SPEECH_SERVICE_REGION')
    if speech_key and speech_region:
        print("✅ Azure Speech Service: Configured")
    else:
        print("❌ Azure Speech Service: Not configured")
    
    # Check Azure Foundry
    foundry_endpoint = os.environ.get('AZURE_FOUNDRY_ENDPOINT')
    if foundry_endpoint and 'cognitiveservices.azure.com' in foundry_endpoint:
        print("✅ Azure Foundry: Configured")
    else:
        print("❌ Azure Foundry: Not configured")
    
    # Check Microsoft Graph
    tenant_id = os.environ.get('TENANT_ID')
    client_id = os.environ.get('CLIENT_ID')
    client_secret = os.environ.get('CLIENT_SECRET')
    if tenant_id and client_id and client_secret:
        print("✅ Microsoft Graph: Configured")
    else:
        print("❌ Microsoft Graph: Not configured")
    
    print()


if __name__ == "__main__":
    print("🎤 Voice Email Processing - End-to-End Test Runner")
    print()
    
    # Setup environment
    if not setup_environment():
        print("❌ Environment setup failed. Please configure missing variables.")
        sys.exit(1)
    
    # Check configuration
    check_configuration()
    
    # Ask for confirmation
    print("⚠️  This test will:")
    print("   • Connect to your real email inbox")
    print("   • Process actual voice messages")
    print("   • Update your Excel file")
    print("   • Move emails to processed folder")
    print()
    
    response = input("Continue with end-to-end test? (y/N): ").strip().lower()
    if response != 'y':
        print("Test cancelled.")
        sys.exit(0)
    
    # Run the test
    success = run_end_to_end_test()
    sys.exit(0 if success else 1)
