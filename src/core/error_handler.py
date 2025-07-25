"""
Production Error Handler for Scribe Voice Email Processor
Centralized error handling with retry logic and graceful degradation
Follows Azure Functions best practices for error management
"""

import logging
import time
import traceback
from typing import Dict, Any, Optional, Callable, Type, Union
from functools import wraps
from dataclasses import dataclass

from .configuration_manager import ScribeConfiguration


@dataclass
class RetryPolicy:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ScribeErrorHandler:
    """
    Production-ready error handler with comprehensive error management
    Provides retry logic, error categorization, and graceful degradation
    """
    
    def __init__(self, config: ScribeConfiguration):
        """
        Initialize error handler with configuration
        
        Args:
            config: Scribe configuration for error handling settings
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Error tracking
        self._error_counts: Dict[str, int] = {}
        self._last_errors: Dict[str, float] = {}
        
        # Retry policies for different operation types
        self.retry_policies = {
            'azure_api': RetryPolicy(max_attempts=3, base_delay=2.0, max_delay=30.0),
            'network': RetryPolicy(max_attempts=5, base_delay=1.0, max_delay=60.0),
            'authentication': RetryPolicy(max_attempts=2, base_delay=5.0, max_delay=30.0),
            'storage': RetryPolicy(max_attempts=3, base_delay=1.5, max_delay=45.0),
            'processing': RetryPolicy(max_attempts=2, base_delay=3.0, max_delay=60.0)
        }
    
    def handle_error(self, 
                    error: Exception, 
                    context: Union[str, Dict[str, Any]], 
                    error_category: str = 'general') -> None:
        """
        Handle errors with comprehensive logging and categorization
        
        Args:
            error: Exception that occurred
            context: Error context (string message or dict with details)
            error_category: Category of error (workflow, api, storage, etc.)
        """
        # Normalize context to dictionary format
        if isinstance(context, str):
            error_context = {
                'error_message': context,
                'category': error_category
            }
        else:
            error_context = {
                'category': error_category,
                **context
            }
        
        error_id = f"{error_category}_{int(time.time())}"
        error_type = type(error).__name__
        
        # Log detailed error information
        error_details = {
            'error_id': error_id,
            'error_type': error_type,
            'error_message': str(error),
            'context': error_context,
            'traceback': traceback.format_exc()
        }
        
        self.logger.error(f"💥 {error_category.title()} Error [{error_id}]: {error_type} - {str(error)}")
        self.logger.debug(f"Error details: {error_details}")
        
        # Track error frequency
        self._track_error(error_type)
        
        # Determine if this is a critical error that should stop processing
        is_critical = self._is_critical_error(error, error_context)
        
        if is_critical:
            self.logger.critical(f"🚨 Critical error detected: {error_type}")
            # In production, this might trigger alerts
        else:
            self.logger.warning(f"⚠️ Non-critical error, processing may continue: {error_type}")
    
    # DEPRECATED: Remove this method, replaced by consolidated handle_error
    def handle_workflow_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """DEPRECATED: Use handle_error(error, context, 'workflow') instead"""
        self.handle_error(error, context, 'workflow')
    
    def retry_with_backoff(self, 
                          operation: Callable,
                          operation_type: str = 'default',
                          context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute operation with exponential backoff retry logic
        
        Args:
            operation: Function to execute with retry
            operation_type: Type of operation for retry policy selection
            context: Optional context for error handling
            
        Returns:
            Any: Result of successful operation execution
            
        Raises:
            Exception: Last exception if all retries failed
        """
        policy = self.retry_policies.get(operation_type, RetryPolicy())
        context = context or {}
        
        last_exception = None
        
        for attempt in range(policy.max_attempts):
            try:
                self.logger.debug(f"🔄 Executing {operation.__name__} (attempt {attempt + 1}/{policy.max_attempts})")
                result = operation()
                
                if attempt > 0:
                    self.logger.info(f"✅ {operation.__name__} succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if attempt < policy.max_attempts - 1:  # Not the last attempt
                    delay = self._calculate_delay(attempt, policy)
                    
                    self.logger.warning(
                        f"⚠️ {operation.__name__} failed (attempt {attempt + 1}/{policy.max_attempts}): "
                        f"{type(e).__name__} - {str(e)}. Retrying in {delay:.1f}s..."
                    )
                    
                    time.sleep(delay)
                else:
                    self.logger.error(
                        f"❌ {operation.__name__} failed after {policy.max_attempts} attempts: "
                        f"{type(e).__name__} - {str(e)}"
                    )
        
        # All retries failed
        if last_exception:
            self._track_error(f"{operation.__name__}_retry_exhausted")
            raise last_exception
    
    def with_error_handling(self, 
                           operation_type: str = 'default',
                           suppress_errors: bool = False,
                           default_return: Any = None):
        """
        Decorator for automatic error handling and retry logic
        
        Args:
            operation_type: Type of operation for retry policy
            suppress_errors: Whether to suppress errors and return default
            default_return: Default value to return if error is suppressed
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return self.retry_with_backoff(
                        lambda: func(*args, **kwargs),
                        operation_type=operation_type,
                        context={'function': func.__name__, 'args': args, 'kwargs': kwargs}
                    )
                except Exception as e:
                    if suppress_errors:
                        self.logger.warning(
                            f"🔇 Suppressing error in {func.__name__}: {type(e).__name__} - {str(e)}"
                        )
                        return default_return
                    else:
                        raise
            return wrapper
        return decorator
    
    def _calculate_delay(self, attempt: int, policy: RetryPolicy) -> float:
        """Calculate delay for exponential backoff with jitter"""
        delay = min(
            policy.base_delay * (policy.exponential_base ** attempt),
            policy.max_delay
        )
        
        if policy.jitter:
            import random
            # Add up to 25% jitter to prevent thundering herd
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def _is_critical_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """
        Determine if an error is critical and should stop all processing
        
        Args:
            error: Exception to evaluate
            context: Error context
            
        Returns:
            bool: True if error is critical
        """
        critical_error_types = [
            'AuthenticationError',
            'PermissionError',
            'ConfigurationError',
            'SystemExit',
            'MemoryError'
        ]
        
        error_type = type(error).__name__
        
        # Check if this is a known critical error type
        if error_type in critical_error_types:
            return True
        
        # Check if this error type has occurred too frequently
        if self._error_counts.get(error_type, 0) > 5:
            self.logger.warning(f"🚨 Error type {error_type} has occurred {self._error_counts[error_type]} times")
            return True
        
        # Check error message for critical indicators
        error_message = str(error).lower()
        critical_keywords = [
            'authentication failed',
            'access denied',
            'permission denied',
            'configuration error',
            'quota exceeded',
            'service unavailable'
        ]
        
        if any(keyword in error_message for keyword in critical_keywords):
            return True
        
        return False
    
    def _track_error(self, error_type: str) -> None:
        """Track error frequency for pattern analysis"""
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        self._last_errors[error_type] = time.time()
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for monitoring and debugging
        
        Returns:
            Dict[str, Any]: Error statistics
        """
        return {
            'error_counts': self._error_counts.copy(),
            'last_errors': self._last_errors.copy(),
            'total_errors': sum(self._error_counts.values()),
            'unique_error_types': len(self._error_counts)
        }
    
    def reset_error_tracking(self) -> None:
        """Reset error tracking counters"""
        self._error_counts.clear()
        self._last_errors.clear()
        self.logger.info("🔄 Error tracking statistics reset")
    
    def should_circuit_break(self, operation_type: str, threshold: int = 10) -> bool:
        """
        Determine if circuit breaker should activate for an operation type
        
        Args:
            operation_type: Type of operation to check
            threshold: Error count threshold for circuit breaking
            
        Returns:
            bool: True if circuit breaker should activate
        """
        error_count = self._error_counts.get(operation_type, 0)
        
        if error_count >= threshold:
            last_error_time = self._last_errors.get(operation_type, 0)
            time_since_last_error = time.time() - last_error_time
            
            # Circuit break for 5 minutes after threshold reached
            if time_since_last_error < 300:  # 5 minutes
                self.logger.warning(
                    f"🔴 Circuit breaker activated for {operation_type}: "
                    f"{error_count} errors in recent period"
                )
                return True
        
        return False
