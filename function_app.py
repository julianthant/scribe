"""
Production-ready Azure Function app for voice email processing
Uses new production architecture with comprehensive error handling and monitoring
"""

import azure.functions as func
import logging
import os
import json
from datetime import datetime, timezone

# Import production architecture components
from src.core import (
    ScribeConfigurationManager,
    ScribeServiceInitializer, 
    ScribeErrorHandler,
    ScribeLogger
)
from src.processors import ScribeWorkflowProcessor

app = func.FunctionApp()

# Initialize production components
logger = ScribeLogger()
config_manager = ScribeConfigurationManager()
error_handler = ScribeErrorHandler(logger)

# Global workflow processor instance
_workflow_processor = None


def get_workflow_processor() -> ScribeWorkflowProcessor:
    """Get or create the global workflow processor instance"""
    global _workflow_processor
    if _workflow_processor is None:
        try:
            # Initialize service initializer
            service_initializer = ScribeServiceInitializer(config_manager, error_handler, logger)
            
            # Create workflow processor with all dependencies
            from src.core import ScribeWorkflowOrchestrator
            orchestrator = ScribeWorkflowOrchestrator(config_manager, error_handler, logger)
            
            _workflow_processor = ScribeWorkflowProcessor({
                'config_manager': config_manager,
                'service_initializer': service_initializer,
                'workflow_orchestrator': orchestrator,
                'error_handler': error_handler,
                'logger': logger
            })
            
            # Initialize Azure services
            if not _workflow_processor.initialize_services():
                raise Exception("Failed to initialize Azure services")
            
            logger.log_info("Workflow processor initialized successfully")
            
        except Exception as e:
            error_handler.handle_error(e, "Failed to initialize workflow processor")
            raise
    
    return _workflow_processor


@app.timer_trigger(schedule="0 */30 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False) 
def process_voice_emails_timer(myTimer: func.TimerRequest) -> None:
    """Timer-triggered email processing every 30 minutes"""
    
    try:
        if myTimer.past_due:
            logger.log_warning("Timer trigger is past due")

        logger.log_info("Voice email processing started via timer trigger", {
            'trigger_type': 'timer',
            'schedule': '30_minutes',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Get workflow processor and execute
        processor = get_workflow_processor()
        workflow_run = processor.process_voice_emails()
        
        # Log workflow results
        logger.log_info("Voice email processing completed", {
            'workflow_summary': workflow_run.to_summary_dict(),
            'trigger_type': 'timer'
        })
        
    except Exception as e:
        error_handler.handle_error(e, "Timer-triggered email processing failed")
        # Re-raise to ensure Function App logs the error
        raise


@app.function_name(name="ProcessEmailsHTTP")
@app.route(route="process", auth_level=func.AuthLevel.FUNCTION) 
def process_voice_emails_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered manual email processing"""
    
    try:
        logger.log_info("Manual voice email processing triggered via HTTP", {
            'trigger_type': 'http',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Parse request parameters
        request_params = {}
        try:
            if req.get_body():
                request_params = req.get_json() or {}
        except ValueError:
            pass
        
        # Get workflow processor and execute
        processor = get_workflow_processor()
        workflow_run = processor.process_voice_emails()
        
        # Prepare response
        response_data = {
            'status': 'success',
            'message': 'Voice email processing completed successfully',
            'workflow_summary': workflow_run.to_summary_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.log_info("Manual voice email processing completed", {
            'workflow_summary': workflow_run.to_summary_dict(),
            'trigger_type': 'http'
        })
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_handler.handle_error(e, "HTTP-triggered email processing failed")
        
        error_response = {
            'status': 'error',
            'message': f'Processing failed: {str(e)}',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="HealthCheck")
@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint for monitoring"""
    
    try:
        # Basic health check
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment': os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT', 'unknown'),
            'version': '2.0-production'
        }
        
        # Try to get processor status (without full initialization)
        try:
            if _workflow_processor is not None:
                health_status['processor_initialized'] = True
            else:
                health_status['processor_initialized'] = False
        except Exception:
            health_status['processor_initialized'] = False
        
        # Check configuration
        config_check = config_manager.validate_configuration()
        health_status['configuration_valid'] = config_check
        
        status_code = 200 if config_check else 503
        
        return func.HttpResponse(
            json.dumps(health_status, indent=2),
            status_code=status_code,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_response = {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return func.HttpResponse(
            json.dumps(error_response, indent=2),
            status_code=503,
            mimetype="application/json"
        )
