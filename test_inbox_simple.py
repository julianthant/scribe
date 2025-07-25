"""
Simple test to check inbox folder access and email processing
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_inbox_access():
    """Test basic inbox access and voice email detection"""
    try:
        logger.info("🧪 Testing inbox access for voice emails...")
        
        # Import OAuth helper
        from helpers.oauth import test_oauth_configuration, make_graph_request
        
        # Test OAuth
        logger.info("🔐 Testing OAuth...")
        oauth_status = test_oauth_configuration()
        
        if not oauth_status.get('valid', False):
            logger.error(f"❌ OAuth failed: {oauth_status}")
            return False
        
        logger.info(f"✅ OAuth successful: {oauth_status.get('user_email', 'Unknown')}")
        
        # Check inbox emails with attachments
        logger.info("📧 Checking inbox for emails with attachments...")
        response = make_graph_request("https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter=hasAttachments eq true&$top=5")
        
        if not response or response.status_code != 200:
            logger.error(f"❌ Failed to fetch inbox emails: {response.status_code if response else 'No response'}")
            return False
        
        messages = response.json().get('value', [])
        logger.info(f"📧 Found {len(messages)} emails with attachments in inbox")
        
        if not messages:
            logger.info("ℹ️ No emails with attachments found in inbox")
            return True
        
        # Check each email for WAV attachments
        wav_emails = []
        for i, message in enumerate(messages[:3], 1):
            subject = message.get('subject', 'No Subject')[:50]
            message_id = message.get('id')
            logger.info(f"   {i}. {subject}...")
            
            # Get attachments
            attach_url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"
            attach_response = make_graph_request(attach_url)
            
            if attach_response and attach_response.status_code == 200:
                attachments = attach_response.json().get('value', [])
                wav_attachments = [a for a in attachments if a.get('name', '').lower().endswith('.wav')]
                
                if wav_attachments:
                    wav_emails.append(message)
                    logger.info(f"      🎤 Found {len(wav_attachments)} WAV attachment(s)")
                    for wav in wav_attachments:
                        logger.info(f"         📎 {wav.get('name')} ({wav.get('size', 0)} bytes)")
                else:
                    logger.info(f"      📎 {len(attachments)} attachment(s), but no WAV files")
            else:
                logger.warning(f"      ⚠️ Could not get attachments")
        
        logger.info(f"🎤 Found {len(wav_emails)} emails with WAV attachments")
        
        # Test folder creation/finding
        if wav_emails:
            logger.info("📁 Testing processed folder management...")
            
            # Check if processed folder exists
            folders_response = make_graph_request("https://graph.microsoft.com/v1.0/me/mailFolders")
            if folders_response and folders_response.status_code == 200:
                folders = folders_response.json().get('value', [])
                processed_folder = None
                
                for folder in folders:
                    if folder.get('displayName') == 'Voice Messages Processed':
                        processed_folder = folder
                        break
                
                if processed_folder:
                    logger.info(f"✅ Found existing 'Voice Messages Processed' folder: {processed_folder.get('id')}")
                else:
                    logger.info("📁 'Voice Messages Processed' folder not found, would create it during processing")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Inbox Access for Voice Emails")
    print("=" * 50)
    
    success = test_inbox_access()
    
    print("=" * 50)
    if success:
        print("✅ Inbox access test completed!")
    else:
        print("❌ Inbox access test failed!")