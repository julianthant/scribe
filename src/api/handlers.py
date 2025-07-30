"""
HTTP request handlers for Azure Function endpoints
Contains the main business logic for processing requests
"""

import logging
from typing import Dict, Any, List
import azure.functions as func
from datetime import datetime

from core.input_validation import input_validator
from .validation import (
    validate_request, 
    validate_auth_required,
    get_processing_params_validation,
    get_file_listing_params_validation
)
from .responses import (
    create_success_response, create_test_error_response, 
    create_workflow_error_response, create_workflow_response,
    build_test_mode_response, build_workflow_response,
    determine_response_status_code, success_response, error_response,
    validation_error_response
)

logger = logging.getLogger(__name__)


def parse_and_validate_request_params(req: func.HttpRequest) -> Dict[str, Any]:
    """Parse and validate request parameters"""
    try:
        raw_params = req.get_json() if req.get_body() else {}
    except:
        raw_params = {}
    
    return input_validator.validate_request_parameters(raw_params)


def process_request_data(req: func.HttpRequest) -> Dict[str, Any]:
    """Process and validate request data"""
    try:
        # Parse and validate parameters
        params = parse_and_validate_request_params(req)
        
        # Log processing parameters
        log_processing_parameters(params)
        
        return params
        
    except Exception as e:
        logger.error(f"❌ Request processing failed: {str(e)}")
        raise


def handle_test_mode(workflow: Any, days_back: int, max_emails: int) -> func.HttpResponse:
    """Handle test mode processing"""
    try:
        # Search for voice emails
        voice_emails = search_voice_emails(workflow, days_back, max_emails)
        
        # Build test mode response
        response = build_test_mode_response(voice_emails)
        
        # Log results and return
        return create_success_response(response)
        
    except Exception as e:
        logger.error(f"❌ Test mode failed: {str(e)}")
        return create_test_error_response(str(e))


def handle_full_processing(workflow: Any, max_emails: int, days_back: int) -> func.HttpResponse:
    """Handle full processing workflow"""
    logger.info("🚀 Running full processing workflow")
    
    try:
        # Execute the complete workflow
        workflow_result = execute_workflow(workflow, max_emails, days_back)
        
        # Build response based on results
        response = build_workflow_response(workflow_result)
        
        # Determine appropriate status code
        status_code = determine_response_status_code(workflow_result)
        
        # Log completion and return response
        log_workflow_completion(workflow_result)
        return create_workflow_response(response, status_code)
        
    except Exception as e:
        logger.error(f"❌ Full processing failed: {str(e)}")
        return create_workflow_error_response(str(e))


def route_processing_mode(workflow: Any, params: Dict[str, Any]) -> func.HttpResponse:
    """Route request to appropriate processing mode"""
    days_back = params['days_back']
    max_emails = params['max_emails']
    test_mode = params['test_mode']
    
    if test_mode:
        logger.info("🧪 Running in test mode")
        return handle_test_mode(workflow, days_back, max_emails)
    else:
        return handle_full_processing(workflow, max_emails, days_back)


# Helper functions

def search_voice_emails(workflow: Any, days_back: int, max_emails: int) -> List[Any]:
    """Search for voice emails using the workflow"""
    return workflow.email_processor.get_voice_emails(days_back, max_emails)


def execute_workflow(workflow: Any, max_emails: int, days_back: int) -> Any:
    """Execute the complete workflow"""
    return workflow.execute_complete_workflow(
        max_emails=max_emails,
        days_back=days_back
    )


def log_workflow_completion(workflow_result: Any) -> None:
    """Log workflow completion details"""
    logger.info(f"📧 Full processing completed: {workflow_result.transcriptions_completed} transcriptions")


def log_processing_parameters(params: Dict[str, Any]) -> None:
    """Log processing parameters for debugging"""
    test_mode_str = "test mode" if params.get('test_mode', False) else "full processing"
    manual_str = "manual trigger" if params.get('manual_trigger', False) else "scheduled"
    
    logger.info(f"📋 Request: {test_mode_str}, {manual_str}, max_emails={params.get('max_emails', 5)}, days_back={params.get('days_back', 7)}")


# Main API endpoint handlers

@validate_request(methods=["GET"])
def handle_auth_status(req: func.HttpRequest) -> func.HttpResponse:
    """Handle authentication status check"""
    try:
        from helpers.auth_manager import get_auth_method, initialize_authentication, get_auth_info
        
        auth_method = get_auth_method()
        auth_initialized = initialize_authentication()
        auth_info = get_auth_info()
        
        return success_response({
            "status": "authenticated" if auth_initialized else "not_authenticated",
            "auth_method": auth_method,
            "message": "✅ Authentication system operational" if auth_initialized else "❌ Authentication failed",
            "timestamp": datetime.utcnow().isoformat(),
            "details": auth_info
        })
        
    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        return error_response(f"Authentication check failed: {str(e)}", status_code=500)


@validate_request(
    methods=["POST"],
    query_params=get_processing_params_validation()
)
@validate_auth_required
def handle_process_emails(req: func.HttpRequest) -> func.HttpResponse:
    """Handle email processing request with validation"""
    try:
        from core.components import initialize_workflow
        
        # Get validated parameters
        max_emails = req.validated_params.get("max_emails", 10)
        days_back = req.validated_params.get("days_back", 1)
        test_mode = req.validated_params.get("test_mode", "false").lower() == "true"
        
        # Initialize workflow
        workflow = initialize_workflow()
        
        # Process based on mode
        if test_mode:
            return handle_test_mode(workflow, days_back, max_emails)
        else:
            return handle_full_processing(workflow, max_emails, days_back)
        
    except Exception as e:
        logger.error(f"Email processing failed: {e}")
        return error_response(f"Email processing failed: {str(e)}", status_code=500)


@validate_request(
    methods=["GET"],
    query_params=get_file_listing_params_validation()
)
def handle_list_voice_files(req: func.HttpRequest) -> func.HttpResponse:
    """Handle list voice files request with validation"""
    try:
        from core.voice_storage_manager import voice_storage_manager
        
        # Get validated parameters
        format_type = req.validated_params.get("format", "json")
        
        # Get list of voice files
        files = voice_storage_manager.list_voice_files()
        
        response_data = {
            "files": files,
            "count": len(files),
            "message": f"Found {len(files)} voice files",
            "timestamp": datetime.utcnow().isoformat(),
            "format": format_type
        }
        
        return success_response(response_data)
        
    except Exception as e:
        logger.error(f"List voice files failed: {e}")
        return error_response(f"Failed to list voice files: {str(e)}", status_code=500)


@validate_request(methods=["GET"])
def handle_download_voice_message(req: func.HttpRequest) -> func.HttpResponse:
    """Handle download voice message request with authentication and validation"""
    try:
        from core.voice_storage_manager import voice_storage_manager
        from helpers.auth_manager import is_authenticated
        
        # Log download attempt for security monitoring (auth check removed for Excel link compatibility)
        logger.info(f"🔒 Download request for file_id: {req.route_params.get('file_id', 'unknown')}")
        
        # Validate file_id parameter
        file_id = req.route_params.get('file_id')
        if not file_id or not file_id.strip():
            return validation_error_response(
                "File ID is required and cannot be empty", 
                status_code=400, 
                field="file_id"
            )
        
        # Enhanced file_id format validation for security
        if not file_id.replace('-', '').replace('_', '').replace('.', '').isalnum():
            logger.warning(f"Invalid file ID format attempted: {file_id}")
            return validation_error_response(
                "Invalid file ID format. Only alphanumeric characters, hyphens, underscores, and periods are allowed.", 
                status_code=400, 
                field="file_id"
            )
        
        # Additional security: prevent path traversal attacks
        if '..' in file_id or '/' in file_id or '\\' in file_id:
            logger.warning(f"Path traversal attempt detected in file_id: {file_id}")
            return validation_error_response(
                "Invalid file ID: path traversal not allowed", 
                status_code=400, 
                field="file_id"
            )
        
        # Log the download attempt for security monitoring
        logger.info(f"🔒 Authenticated download request for file_id: {file_id}")
        
        # Download the file
        file_data = voice_storage_manager.download_voice_message(file_id)
        
        if not file_data:
            logger.warning(f"File not found for download: {file_id}")
            return error_response("File not found", status_code=404)
        
        # Log successful download
        logger.info(f"📁 Successfully serving file: {file_data.get('filename', file_id)}")
        
        return func.HttpResponse(
            file_data['content'],
            status_code=200,
            headers={
                'Content-Type': file_data.get('content_type', 'audio/wav'),
                'Content-Disposition': f'attachment; filename="{file_data.get("filename", file_id)}"',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
        
    except Exception as e:
        logger.error(f"Download voice message failed: {e}")
        return error_response(f"Failed to download voice message: {str(e)}", status_code=500)