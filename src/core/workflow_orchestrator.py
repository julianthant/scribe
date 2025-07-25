"""
Production Workflow Orchestrator for Scribe Voice Email Processor
Coordinates the entire email processing workflow with comprehensive error handling
Follows Azure Functions best practices for workflow management
"""

import logging
import time
import json
from typing import Dict, Any, Optional
import azure.functions as func

from .configuration_manager import ScribeConfigurationManager, ScribeConfiguration
from .service_initializer import ScribeServiceInitializer
from .error_handler import ScribeErrorHandler
from .logger import ScribeLogger


class ScribeWorkflowOrchestrator:
    """
    Production-ready workflow orchestrator for Scribe email processing
    Manages the complete lifecycle of voice email processing
    """
    
    def __init__(self, config_manager: ScribeConfigurationManager, logger: ScribeLogger):
        """
        Initialize workflow orchestrator
        
        Args:
            config_manager: Configuration manager instance
            logger: Structured logger instance
        """
        self.config_manager = config_manager
        self.structured_logger = logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize core components
        self.config = self.config_manager.get_configuration()
        self.error_handler = ScribeErrorHandler(self.config)
        self.service_initializer = ScribeServiceInitializer(self.config)
        
        # Workflow state
        self._services_initialized = False
        self._last_initialization_time: Optional[float] = None
    
    def execute_scheduled_workflow(self, timer_request: func.TimerRequest) -> None:
        """
        Execute the scheduled email processing workflow (timer trigger)
        
        Args:
            timer_request: Azure Functions timer request object
        """
        workflow_id = f"timer_{int(time.time())}"
        start_time = time.time()
        
        try:
            self.structured_logger.log_workflow_start(workflow_id, 'timer_trigger', {
                'past_due': timer_request.past_due,
                'schedule_status': timer_request.schedule_status
            })
            
            if timer_request.past_due:
                self.logger.warning('⏰ Timer trigger is past due!')
                self.structured_logger.log_warning('timer_past_due', {
                    'workflow_id': workflow_id,
                    'schedule_status': timer_request.schedule_status
                })
            
            # Execute main workflow
            result = self._execute_main_workflow(workflow_id)
            
            processing_time = time.time() - start_time
            self.structured_logger.log_workflow_completion(
                workflow_id, 'timer_trigger', result, processing_time
            )
            
            self.logger.info(f"✅ Timer workflow completed in {processing_time:.2f}s")
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_context = {
                'workflow_id': workflow_id,
                'trigger_type': 'timer_trigger',
                'processing_time': processing_time,
                'past_due': timer_request.past_due
            }
            
            self.error_handler.handle_workflow_error(e, error_context)
            self.structured_logger.log_workflow_error(workflow_id, 'timer_trigger', str(e), processing_time)
            
            # Re-raise for Azure Functions runtime
            raise
    
    def execute_manual_workflow(self, http_request: func.HttpRequest) -> func.HttpResponse:
        """
        Execute manual email processing workflow (HTTP trigger)
        
        Args:
            http_request: Azure Functions HTTP request object
            
        Returns:
            func.HttpResponse: HTTP response with workflow results
        """
        workflow_id = f"http_{int(time.time())}"
        start_time = time.time()
        
        try:
            # Parse request parameters
            request_params = self._parse_http_request(http_request)
            
            self.structured_logger.log_workflow_start(workflow_id, 'http_trigger', request_params)
            self.logger.info(f"🎯 Manual workflow started via HTTP trigger: {workflow_id}")
            
            # Execute main workflow
            result = self._execute_main_workflow(workflow_id, request_params)
            
            processing_time = time.time() - start_time
            self.structured_logger.log_workflow_completion(
                workflow_id, 'http_trigger', result, processing_time
            )
            
            # Return success response
            response_data = {
                'success': True,
                'workflow_id': workflow_id,
                'processing_time': processing_time,
                'result': result
            }
            
            return func.HttpResponse(
                json.dumps(response_data, indent=2),
                status_code=200,
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_context = {
                'workflow_id': workflow_id,
                'trigger_type': 'http_trigger',
                'processing_time': processing_time,
                'request_params': request_params if 'request_params' in locals() else None
            }
            
            self.error_handler.handle_workflow_error(e, error_context)
            self.structured_logger.log_workflow_error(workflow_id, 'http_trigger', str(e), processing_time)
            
            # Return error response
            error_response = {
                'success': False,
                'workflow_id': workflow_id,
                'error': str(e),
                'processing_time': processing_time
            }
            
            return func.HttpResponse(
                json.dumps(error_response, indent=2),
                status_code=500,
                headers={'Content-Type': 'application/json'}
            )
    
    def execute_health_check(self, http_request: func.HttpRequest) -> func.HttpResponse:
        """
        Execute health check endpoint
        
        Args:
            http_request: Azure Functions HTTP request object
            
        Returns:
            func.HttpResponse: Health check response
        """
        try:
            self.logger.info("🏥 Executing health check...")
            
            # Check configuration
            config_validation = self.config_manager.validate_runtime_environment()
            
            # Check service health (if initialized)
            service_health = None
            if self._services_initialized:
                service_health = self.service_initializer.get_service_health()
            
            # Overall health determination
            overall_health = 'healthy'
            if not config_validation['valid']:
                overall_health = 'unhealthy'
            elif config_validation['warnings'] or (service_health and service_health['overall_health'] != 'healthy'):
                overall_health = 'degraded'
            
            health_data = {
                'status': overall_health,
                'timestamp': time.time(),
                'configuration': config_validation,
                'services': service_health,
                'environment': self.config.azure_functions_environment,
                'version': '1.0.0'
            }
            
            status_code = 200 if overall_health == 'healthy' else 503
            
            return func.HttpResponse(
                json.dumps(health_data, indent=2),
                status_code=status_code,
                headers={'Content-Type': 'application/json'}
            )
            
        except Exception as e:
            self.logger.error(f"❌ Health check failed: {str(e)}")
            
            error_response = {
                'status': 'error',
                'timestamp': time.time(),
                'error': str(e)
            }
            
            return func.HttpResponse(
                json.dumps(error_response, indent=2),
                status_code=500,
                headers={'Content-Type': 'application/json'}
            )
    
    def _execute_main_workflow(self, workflow_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the main email processing workflow
        
        Args:
            workflow_id: Unique workflow identifier
            params: Optional workflow parameters
            
        Returns:
            Dict[str, Any]: Workflow execution results
        """
        workflow_start = time.time()
        result = {
            'workflow_id': workflow_id,
            'success': True,
            'steps_completed': [],
            'emails_processed': 0,
            'warnings': [],
            'errors': []
        }
        
        try:
            # Step 1: Initialize services if needed
            if not self._services_initialized:
                self.logger.info("🔧 Initializing services...")
                init_success, init_results = self._initialize_services()
                
                if not init_success:
                    result['success'] = False
                    result['errors'].append(f"Service initialization failed: {init_results}")
                    return result
                
                result['steps_completed'].append('service_initialization')
            
            # Step 2: Refresh access token if needed
            self.logger.info("🔑 Checking access token...")
            if self._should_refresh_token():
                token_refreshed = self.service_initializer.refresh_access_token()
                if token_refreshed:
                    result['steps_completed'].append('token_refresh')
                else:
                    result['warnings'].append('Token refresh attempted but no new token available')
            
            # Step 3: Process emails
            self.logger.info("📧 Processing voice emails...")
            email_result = self._process_emails(workflow_id)
            
            result['emails_processed'] = email_result.get('emails_processed', 0)
            result['steps_completed'].append('email_processing')
            
            if email_result.get('warnings'):
                result['warnings'].extend(email_result['warnings'])
            
            if email_result.get('errors'):
                result['errors'].extend(email_result['errors'])
                if email_result.get('critical_errors'):
                    result['success'] = False
            
            workflow_time = time.time() - workflow_start
            result['processing_time'] = workflow_time
            
            self.logger.info(f"🎉 Workflow {workflow_id} completed in {workflow_time:.2f}s")
            
            return result
            
        except Exception as e:
            workflow_time = time.time() - workflow_start
            result['success'] = False
            result['processing_time'] = workflow_time
            result['errors'].append(f"Workflow execution failed: {str(e)}")
            
            self.logger.error(f"💥 Workflow {workflow_id} failed after {workflow_time:.2f}s: {str(e)}")
            raise
    
    def _initialize_services(self) -> tuple[bool, Dict[str, Any]]:
        """Initialize all required services"""
        try:
            # Initialize core services
            core_success, core_results = self.service_initializer.initialize_core_services()
            if not core_success:
                return False, core_results
            
            # Initialize processing services
            proc_success, proc_results = self.service_initializer.initialize_processing_services()
            if not proc_success:
                return False, proc_results
            
            self._services_initialized = True
            self._last_initialization_time = time.time()
            
            return True, {**core_results, **proc_results}
            
        except Exception as e:
            self.logger.error(f"Service initialization failed: {str(e)}")
            return False, {'error': str(e)}
    
    def _should_refresh_token(self) -> bool:
        """Determine if access token should be refreshed"""
        # For now, always attempt refresh for each workflow
        # In production, implement token expiry checking
        return True
    
    def _process_emails(self, workflow_id: str) -> Dict[str, Any]:
        """Process voice emails"""
        try:
            email_processor = self.service_initializer.email_processor
            if not email_processor:
                return {
                    'emails_processed': 0,
                    'errors': ['Email processor not initialized'],
                    'critical_errors': True
                }
            
            # Execute email processing
            email_processor.process_emails()
            
            return {
                'emails_processed': 1,  # Placeholder - actual count would come from processor
                'warnings': [],
                'errors': []
            }
            
        except Exception as e:
            self.logger.error(f"Email processing failed: {str(e)}")
            return {
                'emails_processed': 0,
                'errors': [f'Email processing failed: {str(e)}'],
                'critical_errors': True
            }
    
    def _parse_http_request(self, http_request: func.HttpRequest) -> Dict[str, Any]:
        """Parse HTTP request parameters"""
        params = {}
        
        # Parse query parameters
        for key in http_request.params:
            params[key] = http_request.params[key]
        
        # Parse JSON body if present
        try:
            if http_request.get_body():
                body_data = http_request.get_json()
                if body_data:
                    params.update(body_data)
        except (ValueError, TypeError):
            # Invalid JSON in body - ignore
            pass
        
        return params
