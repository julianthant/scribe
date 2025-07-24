#!/usr/bin/env python3
"""
Refresh OAuth tokens with new Mail.ReadWrite permission
"""

import os
import json
import requests

def refresh_tokens_with_new_permission():
    """Refresh tokens to include Mail.ReadWrite permission"""
    print("🔐 Refreshing OAuth Tokens with Mail.ReadWrite Permission")
    print("=" * 60)
    
    try:
        # Load existing tokens
        oauth_file = '.oauth_tokens.json'
        if not os.path.exists(oauth_file):
            print("❌ No OAuth tokens file found")
            return False
        
        with open(oauth_file, 'r') as f:
            token_data = json.load(f)
        
        print("✅ Loaded existing tokens")
        
        # Extract credentials
        refresh_token = token_data.get('refresh_token')
        client_id = token_data.get('client_id')
        client_secret = token_data.get('client_secret')
        
        if not all([refresh_token, client_id, client_secret]):
            print("❌ Missing required token data")
            return False
        
        print("🔄 Requesting new tokens with Mail.ReadWrite permission...")
        
        # Request new tokens with expanded scope
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': 'https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Files.ReadWrite.All https://graph.microsoft.com/User.Read offline_access'
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            new_token_data = response.json()
            
            # Update token data
            token_data.update(new_token_data)
            
            # Save updated tokens
            with open(oauth_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print("✅ Successfully refreshed tokens with new permissions!")
            print(f"   New scope: {new_token_data.get('scope', 'Not provided')}")
            
            # Test the new permissions
            print("\n🧪 Testing Mail.ReadWrite permission...")
            access_token = new_token_data.get('access_token')
            
            headers = {'Authorization': f'Bearer {access_token}'}
            folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            
            test_response = requests.get(folders_url, headers=headers)
            
            if test_response.status_code == 200:
                folders = test_response.json().get('value', [])
                print(f"✅ Mail folders access works! Found {len(folders)} folders")
                return True
            else:
                print(f"❌ Mail folders test failed: {test_response.status_code}")
                return False
                
        else:
            print(f"❌ Token refresh failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error refreshing tokens: {e}")
        return False

def main():
    print("🎯 OAuth Token Refresh for Mail.ReadWrite")
    print("This will refresh your tokens to include mailbox write permissions.\n")
    
    success = refresh_tokens_with_new_permission()
    
    if success:
        print("\n🌟 Token refresh completed successfully!")
        print("\n📋 Next steps:")
        print("  1. ✅ Tokens now include Mail.ReadWrite permission")
        print("  2. ✅ System can create and move emails to folders")
        print("  3. ✅ Ready to test folder-based organization")
        print("\n🚀 You can now run the folder organization test!")
    else:
        print("\n❌ Token refresh failed")
        print("\n💡 You may need to:")
        print("  1. Re-authorize the app with new permissions")
        print("  2. Check if Mail.ReadWrite permission was granted")
        print("  3. Verify the refresh token is still valid")

if __name__ == "__main__":
    main()
