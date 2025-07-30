"""
HTTP response builders for Azure Function endpoints
Standardizes response formats and error handling
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import azure.functions as func

logger = logging.getLogger(__name__)


def create_success_response(response_data: Dict[str, Any]) -> func.HttpResponse:
    """Create a successful HTTP response"""
    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )


def create_error_response(error_message: str, status_code: int = 500) -> func.HttpResponse:
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


def create_authentication_error_response(error_details: str) -> func.HttpResponse:
    """Create authentication error response"""
    return func.HttpResponse(
        json.dumps({
            "status": "authentication_required",
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_details,
            "signin_url": "/.auth/login/aad"
        }, indent=2),
        status_code=401,
        headers={"Content-Type": "application/json"}
    )


def create_test_error_response(error_message: str) -> func.HttpResponse:
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


def create_workflow_response(response_data: Dict[str, Any], status_code: int) -> func.HttpResponse:
    """Create workflow HTTP response"""
    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )


def create_workflow_error_response(error_message: str) -> func.HttpResponse:
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


def build_test_mode_response(voice_emails: List[Any]) -> Dict[str, Any]:
    """Build the test mode response data"""
    return {
        "status": "test_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "message": f"✅ Found {len(voice_emails)} voice emails (test mode)",
        "test_mode": True,
        "emails_found": len(voice_emails),
        "voice_emails": format_email_summaries(voice_emails)
    }


def build_workflow_response(workflow_result: Any) -> Dict[str, Any]:
    """Build the workflow response data"""
    return {
        "status": "completed" if workflow_result.success else "partially_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "message": get_workflow_message(workflow_result),
        "test_mode": False,
        "workflow_result": extract_workflow_details(workflow_result)
    }


def format_email_summaries(voice_emails: List[Any]) -> List[Dict[str, Any]]:
    """Format email data for response (limit to first 5)"""
    return [
        {
            "subject": truncate_subject(email.subject),
            "sender": email.sender,
            "received_date": email.received_date.isoformat(),
            "voice_attachments_count": len(email.voice_attachments)
        }
        for email in voice_emails[:5]  # Limit to first 5 for response size
    ]


def truncate_subject(subject: str) -> str:
    """Truncate email subject if too long"""
    return subject[:50] + "..." if len(subject) > 50 else subject


def get_workflow_message(workflow_result: Any) -> str:
    """Get appropriate message based on workflow result"""
    return "✅ Workflow completed" if workflow_result.success else "⚠️ Workflow completed with issues"


def extract_workflow_details(workflow_result: Any) -> Dict[str, Any]:
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


def determine_response_status_code(workflow_result: Any) -> int:
    """Determine appropriate HTTP status code"""
    return 200 if workflow_result.success else 207  # 207 = Multi-Status


def create_simple_response(status: str, message: str, **kwargs) -> Dict[str, Any]:
    """Create a simple response dictionary"""
    response = {
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    response.update(kwargs)
    return response


def create_json_response(data: Dict[str, Any], status_code: int = 200) -> func.HttpResponse:
    """Create JSON HTTP response"""
    return func.HttpResponse(
        json.dumps(data, indent=2),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )


# Alias functions for backward compatibility
def success_response(data: Dict[str, Any]) -> func.HttpResponse:
    """Create a successful HTTP response (alias for create_success_response)"""
    return create_success_response(data)


def error_response(error_message: str, status_code: int = 500) -> func.HttpResponse:
    """Create an error HTTP response (alias for create_error_response)"""
    return create_error_response(error_message, status_code)


def validation_error_response(error_message: str, status_code: int = 400, field: str = None, details: Dict = None) -> func.HttpResponse:
    """Create standardized validation error response"""
    response_data = {
        "status": "validation_error",
        "timestamp": datetime.utcnow().isoformat(),
        "message": error_message
    }
    
    if field:
        response_data["field"] = field
    if details:
        response_data["details"] = details
    
    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )