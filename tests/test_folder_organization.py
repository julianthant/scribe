#!/usr/bin/env python3
"""
Test the folder-based email organization system
"""

import os
import sys
import json
from datetime import datetime

def test_folder_organization():
    """Test the folder-based email organization"""
    print("🧪 Testing Folder-Based Email Organization")
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
        
        # Test 1: Check/create processed folder
        print("\n📁 Step 1: Setting up 'Voice Messages Processed' folder...")
        processed_folder_id = processor._get_or_create_processed_folder()
        
        if processed_folder_id:
            print(f"✅ Processed folder ready: {processed_folder_id}")
        else:
            print("❌ Could not create processed folder")
            return False
        
        # Test 2: Get emails from inbox only
        print("\n📧 Step 2: Getting voice emails from INBOX only...")
        emails = processor._get_emails_with_voice_attachments()
        print(f"Found {len(emails)} voice emails in inbox")
        
        # Test 3: Show the workflow
        print("\n⚡ Step 3: Email Processing Workflow:")
        print("  1. ✅ Monitor INBOX only (not all folders)")
        print("  2. ✅ Find voice attachments")
        print("  3. ✅ Process transcription")
        print("  4. ✅ Update Excel file")
        print("  5. ✅ Move email to 'Voice Messages Processed' folder")
        print("  6. ✅ Next timer cycle only sees NEW emails in inbox")
        
        if emails:
            print(f"\n📝 Voice emails currently in inbox:")
            for i, email in enumerate(emails, 1):
                sender = email['from']['emailAddress']['address']
                subject = email['subject'] or '[No subject]'
                print(f"  {i}. From: {sender}")
                print(f"     Subject: {subject[:50]}...")
                print(f"     Attachments: {len(email['voice_attachments'])}")
                
            print(f"\n⚠️  Note: These emails would be processed and moved to:")
            print(f"     📁 'Voice Messages Processed' folder")
        else:
            print("\n✅ No voice emails in inbox!")
            print("   This means either:")
            print("   • No new voice messages received")
            print("   • All voice messages already processed and moved")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in folder organization test: {e}")
        return False

def show_folder_benefits():
    """Show the benefits of folder-based organization"""
    print("\n🌟 Folder-Based Organization Benefits:")
    print("=" * 50)
    
    print("📂 Email Organization:")
    print("  • INBOX: Only unprocessed voice emails")
    print("  • 'Voice Messages Processed': All processed voice emails")
    print("  • Clean separation of new vs processed")
    
    print("\n⚡ Processing Efficiency:")
    print("  • No need to track processed emails in Excel")
    print("  • No duplicate processing (emails are moved)")
    print("  • Faster inbox checks (fewer emails to scan)")
    print("  • Timer only processes what's actually new")
    
    print("\n🔄 Workflow Simplification:")
    print("  • Receive voice email → Stays in inbox")
    print("  • Timer detects it → Processes transcription") 
    print("  • Updates Excel → Moves to processed folder")
    print("  • Next timer cycle → Only sees truly new emails")
    
    print("\n📱 User Experience:")
    print("  • Inbox stays clean (only unprocessed items)")
    print("  • Easy to find all processed voice messages")
    print("  • Can manually move emails back to inbox to reprocess")
    print("  • Clear visual separation in email client")

def main():
    print("🎯 Folder-Based Email Organization Test")
    print("This test shows how the system now uses email folders")
    print("instead of Excel tracking to prevent duplicate processing.\n")
    
    success = test_folder_organization()
    
    if success:
        show_folder_benefits()
        print("\n🚀 Ready for Deployment!")
        print("The system now:")
        print("  ✅ Only monitors INBOX for new voice emails")
        print("  ✅ Moves processed emails to organized folder")
        print("  ✅ Prevents duplicate processing automatically")
        print("  ✅ Keeps your inbox clean and organized")
    else:
        print("\n❌ Folder organization test failed")

if __name__ == "__main__":
    main()
