"""
Production Structured Logger for Scribe Voice Email Processor
Provides structured logging for Application Insights integration
Follows Azure Functions best practices for observability
"""

import logging
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from .configuration_manager import ScribeConfiguration


@dataclass
class LogEvent:
    """Structured log event data"""
    timestamp: str
    level: str
    event_type: str
    message: str
    workflow_id: Optional[str] = None
    component: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, float]] = None


class ScribeLogger:
    """
    Production-ready structured logger for comprehensive observability
    Integrates with Azure Application Insights for monitoring and alerting
    """
    
    def __init__(self, config: Optional[ScribeConfiguration] = None):
        """
        Initialize structured logger
        
        Args:
            config: Optional Scribe configuration for logging settings
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Set up structured logging format
        self._setup_structured_logging()
        
        # Performance tracking
        self._performance_metrics: Dict[str, list] = {}
        self._workflow_timers: Dict[str, float] = {}
    
    def _setup_structured_logging(self) -> None:
        """Configure structured logging format for Application Insights"""
        # Create custom formatter for structured logs
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                # Convert log record to structured format
                log_data = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                
                # Add custom properties if present
                if hasattr(record, 'properties'):
                    log_data['properties'] = record.properties
                
                if hasattr(record, 'metrics'):
                    log_data['metrics'] = record.metrics
                
                return json.dumps(log_data)
        
        # Apply formatter to root logger if in production
        if self.config and self.config.azure_functions_environment == 'Production':
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                handler.setFormatter(StructuredFormatter())
    
    def log_workflow_start(self, 
                          workflow_id: str, 
                          trigger_type: str, 
                          properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Log workflow start event
        
        Args:
            workflow_id: Unique workflow identifier
            trigger_type: Type of trigger (timer, http)
            properties: Additional workflow properties
        """
        self._workflow_timers[workflow_id] = time.time()
        
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level='INFO',
            event_type='workflow_start',
            message=f'Workflow {workflow_id} started via {trigger_type}',
            workflow_id=workflow_id,
            component='workflow_orchestrator',
            properties={
                'trigger_type': trigger_type,
                **(properties or {})
            }
        )
        
        self._log_structured_event(event)
    
    def log_workflow_completion(self, 
                               workflow_id: str, 
                               trigger_type: str, 
                               result: Dict[str, Any], 
                               processing_time: float) -> None:
        """
        Log workflow completion event
        
        Args:
            workflow_id: Unique workflow identifier
            trigger_type: Type of trigger
            result: Workflow execution results
            processing_time: Total processing time in seconds
        """
        # Track performance metrics
        self._track_performance_metric('workflow_processing_time', processing_time)
        
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level='INFO',
            event_type='workflow_completion',
            message=f'Workflow {workflow_id} completed successfully',
            workflow_id=workflow_id,
            component='workflow_orchestrator',
            properties={
                'trigger_type': trigger_type,
                'success': result.get('success', False),
                'steps_completed': result.get('steps_completed', []),
                'emails_processed': result.get('emails_processed', 0),
                'warnings_count': len(result.get('warnings', [])),
                'errors_count': len(result.get('errors', []))
            },
            metrics={
                'processing_time_seconds': processing_time,
                'emails_processed': result.get('emails_processed', 0)
            }
        )
        
        self._log_structured_event(event)
        
        # Clean up timer
        if workflow_id in self._workflow_timers:
            del self._workflow_timers[workflow_id]
    
    def log_workflow_error(self, 
                          workflow_id: str, 
                          trigger_type: str, 
                          error_message: str, 
                          processing_time: float) -> None:
        """
        Log workflow error event
        
        Args:
            workflow_id: Unique workflow identifier
            trigger_type: Type of trigger
            error_message: Error message
            processing_time: Processing time before error
        """
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level='ERROR',
            event_type='workflow_error',
            message=f'Workflow {workflow_id} failed: {error_message}',
            workflow_id=workflow_id,
            component='workflow_orchestrator',
            properties={
                'trigger_type': trigger_type,
                'error_message': error_message
            },
            metrics={
                'processing_time_seconds': processing_time
            }
        )
        
        self._log_structured_event(event)
        
        # Clean up timer
        if workflow_id in self._workflow_timers:
            del self._workflow_timers[workflow_id]
    
    def log_service_initialization(self, 
                                  service_name: str, 
                                  success: bool, 
                                  initialization_time: float,
                                  error_message: Optional[str] = None) -> None:
        """
        Log service initialization event
        
        Args:
            service_name: Name of the service being initialized
            success: Whether initialization succeeded
            initialization_time: Time taken for initialization
            error_message: Error message if initialization failed
        """
        level = 'INFO' if success else 'ERROR'
        message = f'Service {service_name} initialization {"succeeded" if success else "failed"}'
        
        if error_message:
            message += f': {error_message}'
        
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level=level,
            event_type='service_initialization',
            message=message,
            component='service_initializer',
            properties={
                'service_name': service_name,
                'success': success,
                'error_message': error_message
            },
            metrics={
                'initialization_time_seconds': initialization_time
            }
        )
        
        self._log_structured_event(event)
    
    def log_api_call(self, 
                    api_name: str, 
                    operation: str, 
                    success: bool, 
                    response_time: float,
                    status_code: Optional[int] = None,
                    error_message: Optional[str] = None) -> None:
        """
        Log API call event
        
        Args:
            api_name: Name of the API (e.g., 'Microsoft Graph', 'Azure AI Foundry')
            operation: Operation performed
            success: Whether the call succeeded
            response_time: API response time in seconds
            status_code: HTTP status code if applicable
            error_message: Error message if call failed
        """
        level = 'INFO' if success else 'WARNING'
        message = f'{api_name} {operation} {"succeeded" if success else "failed"}'
        
        if error_message:
            message += f': {error_message}'
        
        # Track API performance
        self._track_performance_metric(f'{api_name}_response_time', response_time)
        
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level=level,
            event_type='api_call',
            message=message,
            component='api_client',
            properties={
                'api_name': api_name,
                'operation': operation,
                'success': success,
                'status_code': status_code,
                'error_message': error_message
            },
            metrics={
                'response_time_seconds': response_time
            }
        )
        
        self._log_structured_event(event)
    
    def log_processing_step(self, 
                           step_name: str, 
                           workflow_id: str, 
                           success: bool, 
                           processing_time: float,
                           items_processed: int = 0,
                           details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log processing step event
        
        Args:
            step_name: Name of the processing step
            workflow_id: Associated workflow ID
            success: Whether the step succeeded
            processing_time: Time taken for the step
            items_processed: Number of items processed
            details: Additional step details
        """
        level = 'INFO' if success else 'WARNING'
        message = f'Processing step {step_name} {"completed" if success else "failed"}'
        
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level=level,
            event_type='processing_step',
            message=message,
            workflow_id=workflow_id,
            component='processor',
            properties={
                'step_name': step_name,
                'success': success,
                'items_processed': items_processed,
                **(details or {})
            },
            metrics={
                'processing_time_seconds': processing_time,
                'items_processed': items_processed
            }
        )
        
        self._log_structured_event(event)
    
    def log_performance_summary(self, workflow_id: str) -> None:
        """
        Log performance summary for a workflow
        
        Args:
            workflow_id: Workflow ID to log performance for
        """
        if not self._performance_metrics:
            return
        
        summary = {}
        for metric_name, values in self._performance_metrics.items():
            if values:
                summary[f'{metric_name}_avg'] = sum(values) / len(values)
                summary[f'{metric_name}_max'] = max(values)
                summary[f'{metric_name}_min'] = min(values)
                summary[f'{metric_name}_count'] = len(values)
        
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level='INFO',
            event_type='performance_summary',
            message=f'Performance summary for workflow {workflow_id}',
            workflow_id=workflow_id,
            component='performance_monitor',
            metrics=summary
        )
        
        self._log_structured_event(event)
    
    def log_warning(self, message_or_event_type: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Log warning message - supports both simple message and event-based logging
        
        Args:
            message_or_event_type: Warning message or event type
            properties: Additional properties (if None, treats first arg as simple message)
        """
        if properties is None:
            # Simple message mode: log_warning("Something went wrong")
            event = LogEvent(
                timestamp=self._get_timestamp(),
                level='WARNING',
                event_type='warning',
                message=message_or_event_type,
                component='general',
                properties={}
            )
        else:
            # Event-based mode: log_warning("api_timeout", {"endpoint": "/api/data"})
            event = LogEvent(
                timestamp=self._get_timestamp(),
                level='WARNING',
                event_type=message_or_event_type,
                message=properties.get('message', f'Warning: {message_or_event_type}'),
                workflow_id=properties.get('workflow_id'),
                component=properties.get('component', 'system'),
                properties=properties
            )
        
        self._log_structured_event(event)
    
    def _log_structured_event(self, event: LogEvent) -> None:
        """
        Log structured event to logger with appropriate level
        
        Args:
            event: Log event to write
        """
        # Convert event to extra properties for logger
        extra = {
            'properties': asdict(event),
            'metrics': event.metrics or {}
        }
        
        # Log at appropriate level
        level_map = {
            'DEBUG': self.logger.debug,
            'INFO': self.logger.info,
            'WARNING': self.logger.warning,
            'ERROR': self.logger.error,
            'CRITICAL': self.logger.critical
        }
        
        log_func = level_map.get(event.level, self.logger.info)
        log_func(event.message, extra=extra)
    
    def log_info(self, message: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Log general info message
        
        Args:
            message: Info message
            properties: Additional properties
        """
        event = LogEvent(
            timestamp=self._get_timestamp(),
            level='INFO',
            event_type='info',
            message=message,
            component='general',
            properties=properties or {}
        )
        
        self._log_structured_event(event)

    def _track_performance_metric(self, metric_name: str, value: float) -> None:
        """Track performance metric for aggregation"""
        if metric_name not in self._performance_metrics:
            self._performance_metrics[metric_name] = []
        
        self._performance_metrics[metric_name].append(value)
        
        # Keep only recent metrics (last 100 values)
        if len(self._performance_metrics[metric_name]) > 100:
            self._performance_metrics[metric_name] = self._performance_metrics[metric_name][-100:]
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.now(timezone.utc).isoformat()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics summary
        
        Returns:
            Dict[str, Any]: Performance metrics summary
        """
        summary = {}
        for metric_name, values in self._performance_metrics.items():
            if values:
                summary[metric_name] = {
                    'count': len(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'recent': values[-10:] if len(values) >= 10 else values
                }
        
        return summary
    
    def clear_performance_metrics(self) -> None:
        """Clear accumulated performance metrics"""
        self._performance_metrics.clear()
        self.logger.info("🔄 Performance metrics cleared")
