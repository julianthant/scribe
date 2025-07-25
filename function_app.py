"""
Production-ready Azure Function app for voice email processing
Uses new production architecture with comprehensive error handling and monitoring
"""

import azure.functions as func
import logging
import os
import json
from datetime import datetime, timezone

app = func.FunctionApp()

# Global variables for production components
logger = None
config_manager = None
error_handler = None
_workflow_processor = None

def _ensure_components_initialized():
    """Lazy initialization of production components with error handling"""
    global logger, config_manager, error_handler, _workflow_processor
    
    if logger is None:
        try:
            # Import production architecture components
            from src.core import (
                ScribeConfigurationManager,
                ScribeServiceInitializer, 
                ScribeErrorHandler,
                ScribeLogger
            )
            from src.processors import ScribeWorkflowProcessor
            
            # Initialize production components
            logger = ScribeLogger()
            config_manager = ScribeConfigurationManager()
            error_handler = ScribeErrorHandler(logger)
            
            logging.info("Production components initialized successfully")
            
        except Exception as e:
            # Fallback to basic logging if production components fail
            logging.error(f"Failed to initialize production components: {str(e)}")
            logger = logging
            return False
    
    return True


def get_workflow_processor():
    """Get or create the global workflow processor instance"""
    global _workflow_processor
    
    if not _ensure_components_initialized():
        logging.error("Cannot initialize workflow processor: components failed to initialize")
        return None
        
    if _workflow_processor is None:
        try:
            # Import components locally to avoid import errors at module level
            from src.core import ScribeServiceInitializer, ScribeWorkflowOrchestrator
            from src.processors import ScribeWorkflowProcessor
            
            # Initialize service initializer
            service_initializer = ScribeServiceInitializer(config_manager, error_handler, logger)
            
            # Create workflow processor with all dependencies
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
            
            if hasattr(logger, 'log_info'):
                logger.log_info("Workflow processor initialized successfully")
            else:
                logging.info("Workflow processor initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize workflow processor: {str(e)}"
            if hasattr(error_handler, 'handle_error'):
                error_handler.handle_error(e, error_msg)
            else:
                logging.error(error_msg)
            return None
    
    return _workflow_processor


@app.timer_trigger(schedule="0 */30 * * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False) 
def process_voice_emails_timer(myTimer: func.TimerRequest) -> None:
    """Timer-triggered email processing every 30 minutes"""
    
    try:
        # Initialize components first
        if not _ensure_components_initialized():
            logging.error("Cannot process emails: failed to initialize components")
            return
            
        if myTimer.past_due:
            if hasattr(logger, 'log_warning'):
                logger.log_warning("Timer trigger is past due")
            else:
                logging.warning("Timer trigger is past due")

        log_data = {
            'trigger_type': 'timer',
            'schedule': '30_minutes',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if hasattr(logger, 'log_info'):
            logger.log_info("Voice email processing started via timer trigger", log_data)
        else:
            logging.info(f"Voice email processing started via timer trigger: {log_data}")
        
        # Get workflow processor and execute
        processor = get_workflow_processor()
        if processor is None:
            logging.error("Cannot process emails: workflow processor initialization failed")
            return
            
        workflow_run = processor.process_voice_emails()
        
        # Log workflow results
        if hasattr(logger, 'log_info'):
            logger.log_info("Voice email processing completed", {
                'workflow_summary': workflow_run.to_summary_dict(),
                'trigger_type': 'timer'
            })
        else:
            logging.info(f"Voice email processing completed: {workflow_run.to_summary_dict()}")

    except Exception as e:
        error_msg = f"Error in timer trigger: {str(e)}"
        if hasattr(error_handler, 'handle_error'):
            error_handler.handle_error(e, "Timer trigger execution failed")
        else:
            logging.error(error_msg)
        raise
@app.function_name(name="ProcessEmailsHTTP")
@app.route(route="process", auth_level=func.AuthLevel.FUNCTION) 
def process_voice_emails_http(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered manual email processing"""
    
    try:
        # Initialize components first
        if not _ensure_components_initialized():
            error_response = {
                'status': 'error',
                'message': 'Failed to initialize components',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            return func.HttpResponse(
                json.dumps(error_response, indent=2),
                status_code=500,
                mimetype="application/json"
            )
        
        log_data = {
            'trigger_type': 'http',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if hasattr(logger, 'log_info'):
            logger.log_info("Manual voice email processing triggered via HTTP", log_data)
        else:
            logging.info(f"Manual voice email processing triggered via HTTP: {log_data}")
        
        # Parse request parameters
        request_params = {}
        try:
            if req.get_body():
                request_params = req.get_json() or {}
        except ValueError:
            pass
        
        # Get workflow processor and execute
        processor = get_workflow_processor()
        if processor is None:
            error_response = {
                'status': 'error',
                'message': 'Failed to initialize workflow processor',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            return func.HttpResponse(
                json.dumps(error_response, indent=2),
                status_code=500,
                mimetype="application/json"
            )
            
        workflow_run = processor.process_voice_emails()
        
        # Prepare response
        response_data = {
            'status': 'success',
            'message': 'Voice email processing completed successfully',
            'workflow_summary': workflow_run.to_summary_dict(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if hasattr(logger, 'log_info'):
            logger.log_info("Manual voice email processing completed", {
                'workflow_summary': workflow_run.to_summary_dict(),
                'trigger_type': 'http'
            })
        else:
            logging.info(f"Manual voice email processing completed: {workflow_run.to_summary_dict()}")
        
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        error_msg = f"HTTP-triggered email processing failed: {str(e)}"
        if hasattr(error_handler, 'handle_error'):
            error_handler.handle_error(e, "HTTP-triggered email processing failed")
        else:
            logging.error(error_msg)
        
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
        
        # Check configuration only if components are available
        config_check = True
        try:
            if config_manager is not None and hasattr(config_manager, 'validate_configuration'):
                config_check = config_manager.validate_configuration()
            else:
                # Try to initialize just for config check
                _ensure_components_initialized()
                if config_manager is not None:
                    config_check = config_manager.validate_configuration()
                    
        except Exception as e:
            logging.warning(f"Configuration check failed: {str(e)}")
            config_check = False
            
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
