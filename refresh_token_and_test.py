"""
Refresh OAuth token and test the system
"""

import sys
import os
import json
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def refresh_and_test():
    """Refresh OAuth token and test system"""
    try:
        logger.info("🔄 Attempting to refresh OAuth token...")
        
        # Import OAuth manager
        from helpers.oauth import OAuthManager
        
        oauth_manager = OAuthManager()
        
        # Try to get a fresh token (this will auto-refresh if needed)
        access_token = oauth_manager.get_access_token()
        
        if not access_token:
            logger.error("❌ Failed to get access token")
            return False
        
        logger.info("✅ Access token obtained")
        
        # Test the token
        oauth_status = oauth_manager.test_token()
        
        if oauth_status.get('valid', False):
            logger.info(f"✅ Token is valid for user: {oauth_status.get('user_email', 'Unknown')}")
            
            # Now test inbox access
            from helpers.oauth import make_graph_request
            
            logger.info("📧 Testing inbox access...")
            response = make_graph_request("https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top=3")
            
            if response and response.status_code == 200:
                messages = response.json().get('value', [])
                logger.info(f"✅ Successfully accessed inbox: {len(messages)} messages found")
                
                # Check for emails with attachments
                attach_response = make_graph_request("https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter=hasAttachments eq true&$top=3")
                if attach_response and attach_response.status_code == 200:
                    attach_messages = attach_response.json().get('value', [])
                    logger.info(f"📎 Found {len(attach_messages)} emails with attachments in inbox")
                    return True
                else:
                    logger.warning("⚠️ Could not check for attachments")
                    return True
            else:
                logger.error(f"❌ Failed to access inbox: {response.status_code if response else 'No response'}")
                return False
        else:
            logger.error(f"❌ Token is invalid: {oauth_status}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Refresh and test failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🔄 Refreshing OAuth Token and Testing System")
    print("=" * 50)
    
    success = refresh_and_test()
    
    print("=" * 50)
    if success:
        print("✅ Token refresh and test successful!")
    else:
        print("❌ Token refresh and test failed!")
        print("💡 You may need to re-authenticate your OAuth token")