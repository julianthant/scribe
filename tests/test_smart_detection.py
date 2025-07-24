#!/usr/bin/env python3
"""
Test the smart email detection system
"""

import os
import sys
import json
from datetime import datetime

def test_smart_email_detection():
    """Test the smart email filtering"""
    print("🧪 Testing Smart Email Detection System")
    print("=" * 50)
    
    try:
        # Load environment
        if os.path.exists('local.settings.json'):
            with open('local.settings.json', 'r') as f:
                settings = json.load(f)
                for key, value in settings.get('Values', {}).items():
                    os.environ[key] = value
        
        # Import and initialize processor
        from function_app import EmailVoiceProcessorWithKeyVault
        
        print("🔧 Initializing processor...")
        processor = EmailVoiceProcessorWithKeyVault()
        
        if not processor.access_token:
            print("❌ No access token available")
            return False
        
        print("✅ Processor initialized")
        
        # Test 1: Get all emails with voice attachments
        print("\n📧 Step 1: Getting emails with voice attachments...")
        emails = processor._get_emails_with_voice_attachments()
        print(f"Found {len(emails)} emails with voice attachments")
        
        if not emails:
            print("ℹ️  No voice emails found - system would skip processing")
            return True
        
        # Test 2: Check which are already processed
        print("\n🔍 Step 2: Checking for already processed emails...")
        processed_signatures = processor._get_processed_email_signatures()
        print(f"Found {len(processed_signatures)} previously processed email signatures")
        
        # Test 3: Filter unprocessed emails
        print("\n⚡ Step 3: Filtering for new emails only...")
        new_emails = processor._filter_unprocessed_emails(emails)
        print(f"Found {len(new_emails)} new emails to process")
        
        # Show results
        print("\n📊 Smart Detection Results:")
        print(f"  • Total voice emails found: {len(emails)}")
        print(f"  • Previously processed: {len(emails) - len(new_emails)}")
        print(f"  • New emails to process: {len(new_emails)}")
        
        if new_emails:
            print(f"\n📝 New emails would be processed:")
            for i, email in enumerate(new_emails, 1):
                sender = email['from']['emailAddress']['address']
                subject = email['subject'] or '[No subject]'
                print(f"  {i}. From: {sender}")
                print(f"     Subject: {subject[:50]}...")
                print(f"     Attachments: {len(email['voice_attachments'])}")
        else:
            print("\n✅ No new voice emails - processing would be skipped!")
            print("   This saves resources and prevents duplicate processing.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in smart detection test: {e}")
        return False

def main():
    print("🎯 Smart Email Detection Test")
    print("This test shows how the timer trigger now intelligently")
    print("detects only NEW voice emails instead of reprocessing everything.\n")
    
    success = test_smart_email_detection()
    
    if success:
        print("\n🌟 Smart detection test completed!")
        print("\n📋 How the Timer System Now Works:")
        print("  1. Timer runs every 5 minutes (instead of 15)")
        print("  2. Checks only last 2 hours for emails (not 24)")
        print("  3. Compares against Excel to find NEW emails only")
        print("  4. Skips processing if no new voice emails found")
        print("  5. Only processes truly new voice messages")
        print("\n💡 Benefits:")
        print("  • No duplicate processing")
        print("  • Faster execution when no new emails")
        print("  • More responsive (5 min vs 15 min)")
        print("  • Reduces Azure resource usage")
    else:
        print("\n❌ Smart detection test failed")

if __name__ == "__main__":
    main()
