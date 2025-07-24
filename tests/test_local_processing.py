#!/usr/bin/env python3
"""
Local Test Script for Voice Email Processing
This script manually runs the email processing logic for testing
"""
import os
import json
import logging
import sys

# Set up the same environment as the function
def setup_environment():
    """Setup environment variables from local.settings.json"""
    with open('local.settings.json', 'r') as f:
        settings = json.load(f)
        config = settings.get('Values', {})
    
    # Set environment variables
    for key, value in config.items():
        os.environ[key] = value
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("✅ Environment configured from local.settings.json")

def test_email_processing():
    """Test the email processing functionality"""
    print("🧪 Starting local voice email processing test...")
    print("=" * 60)
    
    # Import the processor class after setting environment
    sys.path.append('.')
    from function_app import EmailVoiceProcessorWithKeyVault
    
    try:
        # Initialize the processor
        print("🔧 Initializing EmailVoiceProcessorWithKeyVault...")
        processor = EmailVoiceProcessorWithKeyVault()
        print("✅ Processor initialized successfully")
        
        # Process emails (this will look for emails with voice attachments)
        print("\n📧 Processing emails with voice attachments...")
        processor.process_emails()
        print("✅ Email processing completed")
        
        print("\n🎉 Local test completed successfully!")
        print("Check your OneDrive Scribe.xlsx file for new entries.")
        
    except Exception as e:
        print(f"❌ Error during processing: {e}")
        logging.exception("Full error details:")
        return False
    
    return True

def check_prerequisites():
    """Check if everything is ready for local testing"""
    print("🔍 Checking prerequisites for local testing...")
    
    required_files = ['function_app.py', 'local.settings.json', '.oauth_tokens.json']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    
    print("✅ All required files present")
    
    # Check if we can load oauth tokens
    try:
        with open('.oauth_tokens.json', 'r') as f:
            tokens = json.load(f)
            if not tokens.get('access_token'):
                print("❌ No access token in OAuth tokens file")
                return False
        print("✅ OAuth tokens available")
    except Exception as e:
        print(f"❌ Error loading OAuth tokens: {e}")
        return False
    
    return True

def main():
    print("🧪 Voice Email Processor - Local Test")
    print("=" * 40)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n💥 Prerequisites not met. Please fix the issues above.")
        return
    
    # Setup environment
    setup_environment()
    
    # Ask for confirmation
    print(f"\nThis will:")
    print(f"1. Connect to your email account ({os.environ.get('TARGET_USER_EMAIL', 'Unknown')})")
    print(f"2. Look for emails with voice attachments")
    print(f"3. Download and transcribe any voice files found")
    print(f"4. Update the Excel file in OneDrive")
    print(f"5. Store voice files in Azure Storage")
    
    confirm = input(f"\nProceed with local testing? (y/N): ")
    if confirm.lower() != 'y':
        print("Test cancelled")
        return
    
    # Run the test
    success = test_email_processing()
    
    if success:
        print("\n🌟 Local test completed successfully!")
        print("\n📋 Next steps:")
        print("1. Check your OneDrive Scribe.xlsx file for new entries")
        print("2. Check Azure Storage voice-files container for uploaded files")
        print("3. Deploy to Azure when ready")
    else:
        print("\n💥 Local test failed. Check the error messages above.")

if __name__ == "__main__":
    main()
