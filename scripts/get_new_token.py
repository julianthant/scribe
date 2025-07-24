#!/usr/bin/env python3
"""
Get new OAuth token with Mail.ReadWrite permission
"""

import webbrowser
import urllib.parse
import json
import os
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/oauth/callback'):
            # Parse the authorization code from the callback URL
            query_string = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query_string)
            
            if 'code' in params:
                self.server.auth_code = params['code'][0]
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                html_response = '''
                <html>
                <body>
                <h2>Authorization Successful!</h2>
                <p>You can close this window and return to the terminal.</p>
                <script>setTimeout(function(){ window.close(); }, 3000);</script>
                </body>
                </html>
                '''
                self.wfile.write(html_response.encode('utf-8'))
            else:
                # Handle error
                error = params.get('error', ['Unknown error'])[0]
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                error_html = f'''
                <html>
                <body>
                <h2>Authorization Failed</h2>
                <p>Error: {error}</p>
                </body>
                </html>
                '''
                self.wfile.write(error_html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress server logs

def get_new_oauth_token():
    """Get new OAuth token with Mail.ReadWrite permission"""
    print("🔐 Getting New OAuth Token with Mail.ReadWrite Permission")
    print("=" * 60)
    
    try:
        # Load existing client credentials if available
        oauth_file = '.oauth_tokens.json'
        client_id = None
        client_secret = None
        
        if os.path.exists(oauth_file):
            with open(oauth_file, 'r') as f:
                existing_data = json.load(f)
                client_id = existing_data.get('client_id')
                client_secret = existing_data.get('client_secret')
        
        if not client_id or not client_secret:
            print("❌ No existing client credentials found")
            print("💡 Make sure you have previously set up OAuth tokens")
            return False
        
        print(f"✅ Using existing client ID: {client_id[:8]}...")
        
        # OAuth configuration with NEW SCOPE including Mail.ReadWrite
        redirect_uri = "http://localhost:8080/oauth/callback"
        scope = "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Files.ReadWrite.All https://graph.microsoft.com/User.Read offline_access"
        
        # Start local server for callback
        print("🌐 Starting local callback server...")
        server = HTTPServer(('localhost', 8080), OAuthCallbackHandler)
        server.auth_code = None
        
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Build authorization URL
        auth_url = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
            f"&scope={urllib.parse.quote(scope)}"
            "&response_mode=query"
            "&prompt=consent"  # Force consent to show new permissions
        )
        
        print("\n🚀 Opening browser for authorization...")
        print("📋 New permissions being requested:")
        print("   • Mail.ReadWrite (NEW!) - Create/move emails and folders")
        print("   • Files.ReadWrite.All - Access OneDrive Excel file")
        print("   • User.Read - Basic profile info")
        print("   • offline_access - Refresh tokens")
        
        print(f"\n🔗 If browser doesn't open, visit this URL:")
        print(f"   {auth_url}")
        
        webbrowser.open(auth_url)
        
        # Wait for authorization code
        print("\n⏳ Waiting for authorization (complete the process in your browser)...")
        
        timeout = 120  # 2 minutes timeout
        start_time = time.time()
        
        while server.auth_code is None and (time.time() - start_time) < timeout:
            time.sleep(1)
        
        server.shutdown()
        
        if server.auth_code is None:
            print("❌ Authorization timed out or failed")
            return False
        
        print("✅ Authorization code received!")
        
        # Exchange authorization code for tokens
        print("🔄 Exchanging authorization code for access tokens...")
        
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        token_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': server.auth_code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
            'scope': scope
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code == 200:
            token_response = response.json()
            
            # Add client credentials to token data
            token_response['client_id'] = client_id
            token_response['client_secret'] = client_secret
            
            # Save new tokens
            with open(oauth_file, 'w') as f:
                json.dump(token_response, f, indent=2)
            
            print("✅ Successfully obtained new tokens!")
            print(f"   Scope: {token_response.get('scope', 'Not provided')}")
            
            # Test Mail.ReadWrite permission
            print("\n🧪 Testing Mail.ReadWrite permission...")
            access_token = token_response.get('access_token')
            
            headers = {'Authorization': f'Bearer {access_token}'}
            folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            
            test_response = requests.get(folders_url, headers=headers)
            
            if test_response.status_code == 200:
                folders = test_response.json().get('value', [])
                print(f"✅ Mail folders access confirmed! Found {len(folders)} folders")
                
                # Check if we can create folders (Mail.ReadWrite test)
                folder_names = [f['displayName'] for f in folders]
                if 'Voice Messages Processed' in folder_names:
                    print("✅ Processed folder already exists")
                else:
                    print("📁 Ready to create 'Voice Messages Processed' folder")
                
                return True
            else:
                print(f"❌ Mail folders test failed: {test_response.status_code}")
                print(f"   Response: {test_response.text}")
                return False
                
        else:
            print(f"❌ Token exchange failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error getting new token: {e}")
        return False

def main():
    print("🎯 OAuth Token Setup with Mail.ReadWrite Permission")
    print("This will get a new token with mailbox write permissions for folder organization.\n")
    
    success = get_new_oauth_token()
    
    if success:
        print("\n🌟 New OAuth token setup completed successfully!")
        print("\n📋 What you can now do:")
        print("  ✅ Create email folders")
        print("  ✅ Move processed emails to organized folders")
        print("  ✅ Keep inbox clean with automatic organization")
        print("  ✅ Run folder-based duplicate prevention")
        print("\n🚀 Ready to test folder organization!")
        print("   Run: python test_folder_organization.py")
    else:
        print("\n❌ OAuth token setup failed")
        print("\n💡 Troubleshooting:")
        print("  1. Make sure you granted Mail.ReadWrite permission")
        print("  2. Complete the authorization in the browser")
        print("  3. Check your Azure app registration permissions")

if __name__ == "__main__":
    main()
