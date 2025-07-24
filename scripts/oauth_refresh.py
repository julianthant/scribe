#!/usr/bin/env python3
"""
OAuth Token Refresh Utility
Refreshes expired OAuth tokens for Microsoft Graph access
"""
import json
import requests
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

class OAuthRefresh:
    def __init__(self):
        self.load_config()
        self.auth_code = None
        
    def load_config(self):
        """Load configuration from local.settings.json"""
        with open('local.settings.json', 'r') as f:
            settings = json.load(f)
            self.config = settings.get('Values', {})
        
        self.client_id = self.config.get('CLIENT_ID')
        self.client_secret = self.config.get('CLIENT_SECRET')
        self.tenant_id = self.config.get('TENANT_ID', 'common')
        
        if not self.client_id or not self.client_secret:
            raise ValueError("CLIENT_ID and CLIENT_SECRET must be configured in local.settings.json")
    
    def get_fresh_tokens(self):
        """Get fresh OAuth tokens through browser authentication"""
        print("🔐 Getting fresh OAuth tokens...")
        
        # OAuth parameters
        redirect_uri = "http://localhost:8080/oauth/callback"  # Standard redirect URI
        scope = "https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/Files.ReadWrite.All offline_access"
        
        # Start local server to receive callback
        server = self.start_callback_server()
        
        # Build authorization URL
        auth_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize?"
            f"client_id={self.client_id}&"
            f"response_type=code&"
            f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
            f"response_mode=query&"
            f"scope={urllib.parse.quote(scope)}&"
            f"state=12345"
        )
        
        print("🌐 Opening browser for authentication...")
        print(f"If browser doesn't open, visit: {auth_url}")
        webbrowser.open(auth_url)
        
        # Wait for callback
        print("⏳ Waiting for authorization callback...")
        start_time = time.time()
        while self.auth_code is None and time.time() - start_time < 300:  # 5 minute timeout
            time.sleep(1)
        
        server.shutdown()
        
        if self.auth_code is None:
            print("❌ Authentication timed out")
            return False
        
        # Exchange code for tokens
        print("🔄 Exchanging authorization code for tokens...")
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': self.auth_code,
            'redirect_uri': redirect_uri,
            'scope': scope
        }
        
        token_response = requests.post(
            f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token',
            data=token_data
        )
        
        if token_response.status_code == 200:
            tokens = token_response.json()
            
            # Save tokens
            token_data = {
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'expires_in': tokens.get('expires_in', 3600),
                'scope': tokens.get('scope', scope)
            }
            
            with open('.oauth_tokens.json', 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print("✅ OAuth tokens saved successfully!")
            
            # Test the tokens
            self.test_tokens(tokens['access_token'])
            return True
        else:
            print(f"❌ Failed to get tokens: {token_response.text}")
            return False
    
    def test_tokens(self, access_token):
        """Test the OAuth tokens"""
        print("🧪 Testing OAuth tokens...")
        
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
        
        if response.status_code == 200:
            user = response.json()
            print(f"✅ Successfully authenticated as: {user.get('userPrincipalName')}")
            print(f"   Display name: {user.get('displayName')}")
        else:
            print(f"❌ Token test failed: {response.status_code}")
    
    def start_callback_server(self):
        """Start local server to receive OAuth callback"""
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/oauth/callback'):  # Match the registered path
                    # Parse query parameters
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(self.path)
                    params = parse_qs(parsed.query)
                    
                    if 'code' in params:
                        oauth_refresh.auth_code = params['code'][0]
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <body>
                        <h1>Authorization Successful!</h1>
                        <p>You can close this browser window.</p>
                        <script>window.close();</script>
                        </body>
                        </html>
                        """)
                    else:
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b"<h1>Authorization Failed</h1>")
                
                def log_message(self, format, *args):
                    pass  # Suppress server logs
        
        oauth_refresh = self
        server = HTTPServer(('localhost', 8080), CallbackHandler)  # Match the redirect URI port
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        return server

def main():
    print("🔐 OAuth Token Refresh Utility")
    print("=" * 40)
    
    try:
        oauth = OAuthRefresh()
        success = oauth.get_fresh_tokens()
        
        if success:
            print("\n🎉 OAuth refresh completed successfully!")
            print("You can now run tests or deploy the function.")
        else:
            print("\n💥 OAuth refresh failed.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()
