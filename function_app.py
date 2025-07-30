"""
Azure Function App for Scribe Voice Email Processor
Production-ready function app with OAuth authentication and timer-based processing
"""

import logging
import azure.functions as func
from datetime import datetime

# Import all needed functions from centralized module
from scribe_app import (
    initialize_authentication,
    initialize_workflow,
    success_response,
    error_response,
    handle_auth_status,
    handle_process_emails,
    handle_list_voice_files,
    handle_download_voice_message,
    get_application_info
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the function app
app = func.FunctionApp()


def handle_function_error(operation: str, error: Exception) -> func.HttpResponse:
    """Centralized error handling for all functions"""
    error_msg = f"{operation} failed: {str(error)}"
    logger.error(f"❌ {error_msg}")
    return error_response(error_msg, 500)

@app.timer_trigger(schedule="0 * * * * *", arg_name="timer", run_on_startup=True)
def scheduled_processing(timer: func.TimerRequest) -> None:
    """Scheduled processing function (every minute) - Uses OAuth authentication!"""
    try:
        current_time = datetime.utcnow().isoformat()
        logger.info(f"⏰ TIMER TRIGGERED: Scheduled processing at {current_time}")
        logger.info(f"⏰ Timer past_due status: {timer.past_due}")
        
        # Check environment variables first
        import os
        required_vars = ['CLIENT_ID', 'KEYVAULT_NAME', 'AZURE_CLIENT_ID', 'AUTH_METHOD']
        env_status = {}
        for var in required_vars:
            value = os.getenv(var)
            env_status[var] = "✅ SET" if value else "❌ MISSING"
            if value:
                logger.info(f"   {var}: {value[:10]}..." if len(str(value)) > 10 else f"   {var}: {value}")
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"❌ Missing environment variables: {missing_vars}")
            return
        
        logger.info("🔐 AUTHENTICATION CHECK: Starting authentication initialization...")
        
        # Initialize authentication with detailed logging
        auth_success = initialize_authentication()
        if auth_success:
            logger.info("✅ AUTHENTICATION SUCCESS: Authentication initialized successfully")
            
            # Test the authentication
            from scribe_app import test_authentication
            auth_test = test_authentication()
            if auth_test.get('valid'):
                logger.info(f"✅ AUTHENTICATION VERIFIED: User={auth_test.get('user', 'Unknown')}")
                logger.info(f"   Method: {auth_test.get('method', 'Unknown')}")
                logger.info(f"   Provider: {auth_test.get('provider', 'Unknown')}")
                
                # Only proceed with workflow if authentication is working
                logger.info("🚀 WORKFLOW START: Executing complete workflow...")
                workflow = initialize_workflow()
                result = workflow.execute_complete_workflow(max_emails=5, days_back=1)
                
                if result and result.success:
                    logger.info(f"✅ WORKFLOW SUCCESS: {result.emails_processed} emails processed, {result.transcriptions_completed} transcriptions")
                else:
                    logger.warning(f"⚠️ WORKFLOW ISSUES: {result.errors if result else 'No result'}")
            else:
                error_msg = auth_test.get('error', 'Unknown error')
                logger.error(f"❌ AUTHENTICATION TEST FAILED: {error_msg}")
                
                # Send smart notification if token-related issue
                if 'token' in error_msg.lower() or 'refresh' in error_msg.lower() or 'expired' in error_msg.lower():
                    try:
                        workflow = initialize_workflow()
                        workflow._send_token_expiry_notification()
                    except Exception as e:
                        logger.error(f"❌ Failed to send token expiry notification: {e}")
        else:
            logger.error("❌ AUTHENTICATION FAILED: Could not initialize authentication")
            
    except Exception as e:
        logger.error(f"❌ SCHEDULED PROCESSING EXCEPTION: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint with comprehensive system status"""
    try:
        app_info = get_application_info()
        health_data = {
            "status": "healthy",
            "message": "✅ Scribe Voice Email Processor is healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "application": app_info
        }
        return success_response(health_data)
    except Exception as e:
        return handle_function_error("Health check", e)

@app.route(route="auth", methods=["GET"])
def authenticate(req: func.HttpRequest) -> func.HttpResponse:
    """Authentication status endpoint"""
    try:
        return handle_auth_status(req)
    except Exception as e:
        return handle_function_error("Authentication check", e)

@app.route(route="process_emails", methods=["POST"])
def process_voice_emails(req: func.HttpRequest) -> func.HttpResponse:
    """Process voice emails endpoint"""
    try:
        logger.info("📧 Manual email processing endpoint triggered")
        
        # Check environment variables first
        import os
        required_vars = ['CLIENT_ID', 'KEYVAULT_NAME', 'AZURE_CLIENT_ID']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            logger.error(f"❌ Missing environment variables: {missing_vars}")
            return error_response(f"Missing environment variables: {missing_vars}", 500)
        
        logger.info("🔐 Environment variables present, processing request...")
        return handle_process_emails(req)
    except Exception as e:
        logger.error(f"❌ Email processing exception: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return handle_function_error("Email processing", e)


@app.route(route="voice_files", methods=["GET"])
def list_voice_files(req: func.HttpRequest) -> func.HttpResponse:
    """List stored voice files endpoint"""
    try:
        return handle_list_voice_files(req)
    except Exception as e:
        return handle_function_error("List voice files", e)


@app.route(route="download_voice/{file_id}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def download_voice_message(req: func.HttpRequest) -> func.HttpResponse:
    """Download voice message endpoint"""
    try:
        return handle_download_voice_message(req)
    except Exception as e:
        return handle_function_error("Download voice message", e)

@app.route(route="signin", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_signin(req: func.HttpRequest) -> func.HttpResponse:
    """OAuth sign-in endpoint - redirects to Microsoft authorization"""
    try:
        logger.info("🔐 OAuth sign-in endpoint triggered")
        
        import os
        import urllib.parse
        import secrets
        
        # Get configuration
        client_id = os.getenv('CLIENT_ID')
        function_base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
        
        if not client_id:
            return error_response("CLIENT_ID not configured", 400)
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in temporary storage (you might want to use Redis or similar in production)
        # For now, we'll include it in the redirect and validate it in callback
        
        # Microsoft Graph scopes
        scopes = [
            "https://graph.microsoft.com/User.Read",
            "https://graph.microsoft.com/Mail.ReadWrite", 
            "https://graph.microsoft.com/Files.ReadWrite.All",
            "offline_access"  # For refresh tokens
        ]
        
        # Build authorization URL
        auth_params = {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': f"{function_base_url}/api/oauth_callback",
            'response_mode': 'query',
            'scope': ' '.join(scopes),
            'state': state
        }
        
        auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urllib.parse.urlencode(auth_params)
        
        logger.info(f"🔐 Generated authorization URL, redirecting user")
        
        # Return HTML with redirect
        html_response = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Scribe Voice Processor - Sign In</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 50px; }}
                .container {{ max-width: 600px; margin: 0 auto; text-align: center; }}
                .btn {{ background: #0078d4; color: white; padding: 15px 30px; 
                        text-decoration: none; border-radius: 5px; display: inline-block; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎤 Scribe Voice Email Processor</h1>
                <p>Click the button below to sign in with your Microsoft account:</p>
                <a href="{auth_url}" class="btn">Sign In with Microsoft</a>
                <p><small>You will be redirected to Microsoft's secure sign-in page.</small></p>
            </div>
            <script>
                // Auto-redirect after 3 seconds
                setTimeout(function() {{
                    window.location.href = "{auth_url}";
                }}, 3000);
            </script>
        </body>
        </html>
        """
        
        return func.HttpResponse(html_response, status_code=200, mimetype="text/html")
        
    except Exception as e:
        logger.error(f"❌ OAuth sign-in failed: {e}")
        return handle_function_error("OAuth sign-in", e)

@app.route(route="oauth_callback", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def oauth_callback(req: func.HttpRequest) -> func.HttpResponse:
    """OAuth callback endpoint - handles authorization code exchange"""
    try:
        logger.info("🔐 OAuth callback endpoint triggered")
        
        # Get parameters from callback
        code = req.params.get('code')
        state = req.params.get('state')
        error = req.params.get('error')
        error_description = req.params.get('error_description')
        
        if error:
            logger.error(f"❌ OAuth error: {error} - {error_description}")
            return error_response(f"Authentication failed: {error_description}", 400)
        
        if not code:
            logger.error("❌ No authorization code received")
            return error_response("No authorization code received", 400)
        
        logger.info("✅ Authorization code received, exchanging for tokens...")
        
        # Exchange code for tokens
        import os
        import requests
        
        client_id = os.getenv('CLIENT_ID')
        function_base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
        
        token_data = {
            'client_id': client_id,
            'code': code,
            'redirect_uri': f"{function_base_url}/api/oauth_callback",
            'grant_type': 'authorization_code',
            'scope': 'https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Files.ReadWrite.All offline_access'
        }
        
        token_response = requests.post(
            'https://login.microsoftonline.com/common/oauth2/v2.0/token',
            data=token_data,
            timeout=30
        )
        
        if token_response.status_code == 200:
            tokens = token_response.json()
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            
            logger.info("✅ Tokens received successfully")
            
            # Store refresh token in Key Vault
            from scribe_app import store_oauth_tokens
            if store_oauth_tokens(access_token, refresh_token):
                logger.info("✅ Tokens stored in Key Vault successfully")
                
                # Test the authentication immediately
                from scribe_app import initialize_authentication, test_authentication
                if initialize_authentication():
                    auth_test = test_authentication()
                    if auth_test.get('valid'):
                        logger.info(f"✅ Authentication test successful: {auth_test.get('user')}")
                        
                        html_response = """
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <title>Scribe Voice Processor - Success</title>
                            <style>
                                body { font-family: Arial, sans-serif; margin: 50px; }
                                .container { max-width: 600px; margin: 0 auto; text-align: center; }
                                .success { color: #107c10; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <h1 class="success">✅ Authentication Successful!</h1>
                                <p>Your Microsoft account has been linked successfully.</p>
                                <p>The Scribe Voice Email Processor will now automatically process your voice emails every minute.</p>
                                <p><strong>User:</strong> """ + str(auth_test.get('user', 'Unknown')) + """</p>
                                <p><small>You can close this window.</small></p>
                            </div>
                        </body>
                        </html>
                        """
                        return func.HttpResponse(html_response, status_code=200, mimetype="text/html")
                    else:
                        logger.error(f"❌ Authentication test failed: {auth_test.get('error')}")
                else:
                    logger.error("❌ Failed to initialize authentication after token storage")
            else:
                logger.error("❌ Failed to store tokens in Key Vault")
        else:
            logger.error(f"❌ Token exchange failed: {token_response.status_code} - {token_response.text}")
            return error_response(f"Token exchange failed: {token_response.text}", 400)
            
        return error_response("Authentication setup failed", 500)
        
    except Exception as e:
        logger.error(f"❌ OAuth callback failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return handle_function_error("OAuth callback", e)

@app.route(route="warmup", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS)
def warmup(req: func.HttpRequest) -> func.HttpResponse:
    """Warmup endpoint for cold start optimization"""
    return func.HttpResponse("Function app warmed up", status_code=200)