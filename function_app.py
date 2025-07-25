"""
Production Azure Function App for Scribe Voice Email Processor
Clean, modern implementation using the new src structure
"""

import azure.functions as func
import logging
import json
import os
import sys
import traceback
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import validation after path setup
from core.input_validation import input_validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Azure Function App
app = func.FunctionApp()

def _check_manual_trigger_auth(req: func.HttpRequest) -> dict:
    """Check authentication for manual trigger requests"""
    try:
        # Extract and validate Authorization header
        auth_header = _extract_auth_header(req)
        if not auth_header['valid']:
            return auth_header
        
        # Extract and validate Bearer token
        token = _extract_bearer_token(auth_header['header'])
        if not token['valid']:
            return token
        
        # Validate token with Microsoft Graph
        validation_result = _validate_token_with_graph(token['token'])
        
        if validation_result['valid']:
            logger.info(f"✓ Manual trigger authenticated for user: {validation_result.get('user', 'Unknown')}")
        
        return validation_result
            
    except Exception as e:
        logger.error(f"❌ Authentication check failed: {e}")
        return {'valid': False, 'error': f'Authentication error: {str(e)}'}

def _extract_auth_header(req: func.HttpRequest) -> dict:
    """Extract and validate Authorization header"""
    auth_header = req.headers.get('Authorization', '')
    if not auth_header:
        return {'valid': False, 'error': 'No Authorization header provided'}
    
    return {'valid': True, 'header': auth_header}

def _extract_bearer_token(auth_header: str) -> dict:
    """Extract Bearer token from Authorization header"""
    if not auth_header.startswith('Bearer '):
        return {'valid': False, 'error': 'Invalid Authorization header format'}
    
    token = auth_header[7:].strip()  # Remove 'Bearer ' prefix
    if not token:
        return {'valid': False, 'error': 'No token provided'}
    
    return {'valid': True, 'token': token}

def _validate_token_with_graph(token: str) -> dict:
    """Validate token by testing with Microsoft Graph"""
    try:
        from helpers.oauth import OAuthManager
        temp_oauth = OAuthManager()
        temp_oauth._cached_token = token
        
        # Test the token
        test_result = temp_oauth.test_token()
        if test_result.get('valid', False):
            return {
                'valid': True, 
                'user': test_result.get('user_email', 'Unknown')
            }
        else:
            return {'valid': False, 'error': 'Invalid or expired token'}
            
    except Exception as e:
        logger.error(f"❌ Token validation failed: {e}")
        return {'valid': False, 'error': f'Token validation error: {str(e)}'}

# Global components (initialized on first use)
_config = None
_workflow_orchestrator = None

def get_config():
    """Get or create configuration"""
    global _config
    if _config is None:
        try:
            from core.config import ScribeConfig
            _config = ScribeConfig.from_environment()
            if not _config.validate():
                logger.error("❌ Configuration validation failed")
                return None
            logger.info("✅ Configuration loaded and validated")
        except Exception as e:
            logger.error(f"❌ Failed to load configuration: {e}")
            return None
    return _config

def get_workflow_orchestrator():
    """Get or create workflow orchestrator"""
    global _workflow_orchestrator
    if _workflow_orchestrator is None:
        try:
            config = get_config()
            if not config:
                return None
            
            from core.workflow import WorkflowOrchestrator
            _workflow_orchestrator = WorkflowOrchestrator(config)
            logger.info("✅ Workflow orchestrator initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize workflow orchestrator: {e}")
            return None
    return _workflow_orchestrator

@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Comprehensive health check endpoint"""
    try:
        logger.info("🏥 Health check initiated")
        
        # Get workflow orchestrator
        workflow = get_workflow_orchestrator()
        if not workflow:
            return func.HttpResponse(
                json.dumps({
                    "status": "unhealthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": "Failed to initialize workflow orchestrator"
                }, indent=2),
                status_code=500,
                headers={"Content-Type": "application/json"}
            )
        
        # Get comprehensive health status
        health_status = workflow.get_health_status()
        
        # Determine HTTP status code
        if health_status.get('ready_for_processing', False):
            status_code = 200
            status_message = "healthy"
            message = "✅ Scribe Voice Email Processor is fully operational"
        else:
            status_code = 503
            status_message = "degraded"
            message = "⚠️ Some components are not fully operational"
        
        response_data = {
            "status": status_message,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "4.0.0",
            "function_app": "scribe-voice-processor-production",
            "message": message,
            "health_details": health_status
        }
        
        logger.info(f"✅ Health check completed: {status_message}")
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }, indent=2),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@app.route(route="oauth_test", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def test_oauth(req: func.HttpRequest) -> func.HttpResponse:
    """Test OAuth token validity"""
    try:
        logger.info("🔐 OAuth test initiated")
        
        from helpers.oauth import test_oauth_configuration
        oauth_status = test_oauth_configuration()
        
        response = {
            "timestamp": datetime.utcnow().isoformat(),
            "oauth_status": oauth_status
        }
        
        if oauth_status.get('valid', False):
            response["status"] = "token_valid"
            response["message"] = "✅ OAuth token is valid and Microsoft Graph is accessible"
            status_code = 200
        else:
            response["status"] = "token_invalid" 
            response["message"] = "❌ OAuth token is invalid or Microsoft Graph is not accessible"
            status_code = 401
        
        logger.info(f"🔐 OAuth test completed: {response['status']}")
        return func.HttpResponse(
            json.dumps(response, indent=2),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"❌ OAuth test failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }, indent=2),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

def _parse_and_validate_request_params(req: func.HttpRequest) -> dict:
    """Parse and validate request parameters"""
    try:
        raw_params = req.get_json() if req.get_body() else {}
    except:
        raw_params = {}
    
    return input_validator.validate_request_parameters(raw_params)

def _handle_test_mode(workflow, days_back: int, max_emails: int) -> func.HttpResponse:
    """Handle test mode processing"""
    logger.info("🧪 Running in test mode - searching for voice emails")
    
    try:
        # Search for voice emails
        voice_emails = _search_voice_emails(workflow, days_back, max_emails)
        
        # Build test mode response
        response = _build_test_mode_response(voice_emails)
        
        # Log results and return
        logger.info(f"📧 Test mode completed: {len(voice_emails)} voice emails found")
        return _create_success_response(response)
        
    except Exception as e:
        logger.error(f"❌ Test mode failed: {str(e)}")
        return _create_test_error_response(str(e))

def _search_voice_emails(workflow, days_back: int, max_emails: int):
    """Search for voice emails using the workflow"""
    return workflow.email_processor.get_voice_emails(days_back, max_emails)

def _build_test_mode_response(voice_emails) -> dict:
    """Build the test mode response data"""
    return {
        "status": "test_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "message": f"✅ Found {len(voice_emails)} voice emails (test mode)",
        "test_mode": True,
        "emails_found": len(voice_emails),
        "voice_emails": _format_email_summaries(voice_emails)
    }

def _format_email_summaries(voice_emails) -> list:
    """Format email data for response (limit to first 5)"""
    return [
        {
            "subject": _truncate_subject(email.subject),
            "sender": email.sender,
            "received_date": email.received_date.isoformat(),
            "voice_attachments_count": len(email.voice_attachments)
        }
        for email in voice_emails[:5]  # Limit to first 5 for response size
    ]

def _truncate_subject(subject: str) -> str:
    """Truncate email subject if too long"""
    return subject[:50] + "..." if len(subject) > 50 else subject

def _create_success_response(response_data: dict) -> func.HttpResponse:
    """Create a successful HTTP response"""
    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

def _create_test_error_response(error_message: str) -> func.HttpResponse:
    """Create an error response for test mode"""
    return func.HttpResponse(
        json.dumps({
            "status": "test_error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_message
        }, indent=2),
        status_code=500,
        headers={"Content-Type": "application/json"}
    )

def _handle_full_processing(workflow, max_emails: int, days_back: int) -> func.HttpResponse:
    """Handle full processing workflow"""
    logger.info("🚀 Running full processing workflow")
    
    try:
        # Execute the complete workflow
        workflow_result = _execute_workflow(workflow, max_emails, days_back)
        
        # Build response based on results
        response = _build_workflow_response(workflow_result)
        
        # Determine appropriate status code
        status_code = _determine_response_status_code(workflow_result)
        
        # Log completion and return response
        _log_workflow_completion(workflow_result)
        return _create_workflow_response(response, status_code)
        
    except Exception as e:
        logger.error(f"❌ Full processing failed: {str(e)}")
        return _create_workflow_error_response(str(e))

def _execute_workflow(workflow, max_emails: int, days_back: int):
    """Execute the complete workflow"""
    return workflow.execute_complete_workflow(
        max_emails=max_emails,
        days_back=days_back
    )

def _build_workflow_response(workflow_result) -> dict:
    """Build the workflow response data"""
    return {
        "status": "completed" if workflow_result.success else "partially_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "message": _get_workflow_message(workflow_result),
        "test_mode": False,
        "workflow_result": _extract_workflow_details(workflow_result)
    }

def _get_workflow_message(workflow_result) -> str:
    """Get appropriate message based on workflow result"""
    return "✅ Workflow completed" if workflow_result.success else "⚠️ Workflow completed with issues"

def _extract_workflow_details(workflow_result) -> dict:
    """Extract workflow result details for response"""
    return {
        "success": workflow_result.success,
        "emails_processed": workflow_result.emails_processed,
        "transcriptions_completed": workflow_result.transcriptions_completed,
        "excel_rows_added": workflow_result.excel_rows_added,
        "success_rate": workflow_result.success_rate,
        "processing_time_seconds": workflow_result.processing_time_seconds,
        "errors": workflow_result.errors
    }

def _determine_response_status_code(workflow_result) -> int:
    """Determine appropriate HTTP status code"""
    return 200 if workflow_result.success else 207  # 207 = Multi-Status

def _log_workflow_completion(workflow_result) -> None:
    """Log workflow completion details"""
    logger.info(f"📧 Full processing completed: {workflow_result.transcriptions_completed} transcriptions")

def _create_workflow_response(response_data: dict, status_code: int) -> func.HttpResponse:
    """Create workflow HTTP response"""
    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )

def _create_workflow_error_response(error_message: str) -> func.HttpResponse:
    """Create an error response for workflow failures"""
    return func.HttpResponse(
        json.dumps({
            "status": "workflow_error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_message
        }, indent=2),
        status_code=500,
        headers={"Content-Type": "application/json"}
    )

def _create_error_response(error_message: str, status_code: int = 500) -> func.HttpResponse:
    """Create standardized error response"""
    return func.HttpResponse(
        json.dumps({
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_message
        }, indent=2),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )

@app.route(route="process_emails", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def process_voice_emails(req: func.HttpRequest) -> func.HttpResponse:
    """Process voice emails using the complete workflow"""
    try:
        logger.info("📧 Voice email processing initiated")
        
        # Parse and validate request
        request_data = _process_request_data(req)
        if not request_data['valid']:
            return request_data['response']
        
        params = request_data['params']
        
        # Log processing parameters
        _log_processing_parameters(params)
        
        # Initialize workflow
        workflow = _initialize_workflow()
        if not workflow:
            return _create_error_response("Failed to initialize workflow orchestrator")
        
        # Route to appropriate processing mode
        return _route_processing_mode(workflow, params)
        
    except Exception as e:
        logger.error(f"❌ Voice email processing failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return _create_error_response(str(e))

def _process_request_data(req: func.HttpRequest) -> dict:
    """Process and validate all request data"""
    try:
        # Parse parameters
        params = _parse_and_validate_request_params(req)
        
        # Handle authentication if needed
        auth_result = _handle_authentication_if_required(req, params)
        if not auth_result['valid']:
            return {'valid': False, 'response': auth_result['response']}
        
        return {'valid': True, 'params': params}
        
    except Exception as e:
        logger.error(f"❌ Error processing request data: {e}")
        return {'valid': False, 'response': _create_error_response(str(e))}

def _handle_authentication_if_required(req: func.HttpRequest, params: dict) -> dict:
    """Handle authentication for manual triggers"""
    manual_trigger = params.get('manual_trigger', False)
    
    if not manual_trigger:
        return {'valid': True}
    
    auth_result = _check_manual_trigger_auth(req)
    if not auth_result['valid']:
        logger.warning(f"🚫 Manual trigger authentication failed: {auth_result['error']}")
        return {
            'valid': False,
            'response': _create_authentication_error_response(auth_result['error'])
        }
    
    return {'valid': True}

def _create_authentication_error_response(error_details: str) -> func.HttpResponse:
    """Create authentication error response"""
    return func.HttpResponse(
        json.dumps({
            "status": "authentication_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Authentication required for manual triggers",
            "details": error_details
        }, indent=2),
        status_code=401,
        headers={"Content-Type": "application/json"}
    )

def _log_processing_parameters(params: dict) -> None:
    """Log the processing parameters"""
    manual_trigger = params.get('manual_trigger', False)
    max_emails = params.get('max_emails', 5)
    days_back = params.get('days_back', 7)
    test_mode = params.get('test_mode', False)
    
    auth_info = " (authenticated)" if manual_trigger else " (scheduled)"
    logger.info(f"📋 Processing parameters: manual={manual_trigger}{auth_info}, max={max_emails}, days={days_back}, test={test_mode}")

def _initialize_workflow():
    """Initialize the workflow orchestrator"""
    return get_workflow_orchestrator()

def _route_processing_mode(workflow, params: dict) -> func.HttpResponse:
    """Route to the appropriate processing mode"""
    test_mode = params.get('test_mode', False)
    max_emails = params.get('max_emails', 5)
    days_back = params.get('days_back', 7)
    
    if test_mode:
        return _handle_test_mode(workflow, days_back, max_emails)
    else:
        return _handle_full_processing(workflow, max_emails, days_back)

@app.timer_trigger(schedule="0 */30 * * * *", arg_name="timer", run_on_startup=False)
def scheduled_processing(timer: func.TimerRequest) -> None:
    """Scheduled voice email processing every 30 minutes"""
    try:
        logger.info("⏰ Scheduled processing triggered")
        
        if timer.past_due:
            logger.warning("⚠️ Timer is past due!")
        
        # Get workflow orchestrator
        workflow = get_workflow_orchestrator()
        if not workflow:
            logger.error("❌ Failed to initialize workflow for scheduled processing")
            return
        
        # Process voice emails automatically
        max_emails = int(os.getenv('SCHEDULED_MAX_EMAILS', '3'))
        days_back = int(os.getenv('SCHEDULED_DAYS_BACK', '1'))  # Only process last day
        
        logger.info(f"📋 Scheduled processing: max={max_emails}, days={days_back}")
        
        # Execute workflow
        workflow_result = workflow.execute_complete_workflow(
            max_emails=max_emails,
            days_back=days_back
        )
        
        if workflow_result.success:
            logger.info(f"⏰ Scheduled processing completed successfully:")
            logger.info(f"   📧 Emails processed: {workflow_result.emails_processed}")
            logger.info(f"   🎤 Transcriptions: {workflow_result.transcriptions_completed}")
            logger.info(f"   📊 Excel rows: {workflow_result.excel_rows_added}")
            logger.info(f"   📈 Success rate: {workflow_result.success_rate:.1f}%")
        else:
            logger.warning(f"⚠️ Scheduled processing completed with issues:")
            logger.warning(f"   📧 Emails processed: {workflow_result.emails_processed}")
            logger.warning(f"   🎤 Transcriptions: {workflow_result.transcriptions_completed}")
            for error in workflow_result.errors:
                logger.warning(f"   Error: {error}")
        
    except Exception as e:
        logger.error(f"❌ Scheduled processing failed: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")

@app.route(route="warmup", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def warmup(req: func.HttpRequest) -> func.HttpResponse:
    """Warmup endpoint to keep function hot and initialize components"""
    try:
        logger.info("🔥 Warmup initiated")
        
        # Try to initialize components
        config = get_config()
        workflow = get_workflow_orchestrator()
        
        if config and workflow:
            response = {
                "status": "warm",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "🔥 Function is warmed up and components are ready",
                "components_ready": True,
                "config_valid": config.validate()
            }
            status_code = 200
        else:
            response = {
                "status": "warming",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "🔄 Function is warming up but components need initialization",
                "components_ready": False
            }
            status_code = 202  # Accepted, but not ready
        
        logger.info(f"🔥 Warmup completed: {response['status']}")
        return func.HttpResponse(
            json.dumps(response, indent=2),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"❌ Warmup failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "cold",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }, indent=2),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )

@app.route(route="component_test", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def test_components(req: func.HttpRequest) -> func.HttpResponse:
    """Test all individual components"""
    try:
        logger.info("🧪 Component testing initiated")
        
        workflow = get_workflow_orchestrator()
        if not workflow:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": "Failed to initialize workflow orchestrator"
                }, indent=2),
                status_code=500,
                headers={"Content-Type": "application/json"}
            )
        
        # Run component tests
        test_results = workflow.test_all_components()
        
        response = {
            "status": "tests_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"✅ Component tests completed" if test_results['overall_success'] else "⚠️ Some component tests failed",
            "test_results": test_results
        }
        
        status_code = 200 if test_results['overall_success'] else 207
        
        logger.info(f"🧪 Component testing completed: {test_results['success_rate']:.1f}% success rate")
        return func.HttpResponse(
            json.dumps(response, indent=2, default=str),
            status_code=status_code,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logger.error(f"❌ Component testing failed: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }, indent=2),
            status_code=500,
            headers={"Content-Type": "application/json"}
        )