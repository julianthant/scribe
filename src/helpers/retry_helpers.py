"""
Retry helper functions for robust Azure API interactions
Provides exponential backoff and configurable retry policies
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps
from dataclasses import dataclass


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Optional[List[Type[Exception]]] = None


def retry_with_exponential_backoff(
    operation: Callable,
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None
) -> Any:
    """
    Execute operation with exponential backoff retry logic
    
    Args:
        operation: Function to execute with retry
        config: Retry configuration
        operation_name: Name for logging purposes
        
    Returns:
        Any: Result of successful operation execution
        
    Raises:
        Exception: Last exception if all retries failed
    """
    config = config or RetryConfig()
    operation_name = operation_name or operation.__name__
    logger = logging.getLogger(__name__)
    
    last_exception = None
    
    for attempt in range(config.max_attempts):
        try:
            logger.debug(f"🔄 Executing {operation_name} (attempt {attempt + 1}/{config.max_attempts})")
            result = operation()
            
            if attempt > 0:
                logger.info(f"✅ {operation_name} succeeded on attempt {attempt + 1}")
            
            return result
            
        except Exception as e:
            last_exception = e
            
            # Check if this exception type should be retried
            if config.retryable_exceptions and type(e) not in config.retryable_exceptions:
                logger.error(f"❌ {operation_name} failed with non-retryable exception: {type(e).__name__}")
                raise
            
            if attempt < config.max_attempts - 1:  # Not the last attempt
                delay = _calculate_delay(attempt, config)
                
                logger.warning(
                    f"⚠️ {operation_name} failed (attempt {attempt + 1}/{config.max_attempts}): "
                    f"{type(e).__name__} - {str(e)}. Retrying in {delay:.1f}s..."
                )
                
                time.sleep(delay)
            else:
                logger.error(
                    f"❌ {operation_name} failed after {config.max_attempts} attempts: "
                    f"{type(e).__name__} - {str(e)}"
                )
    
    # All retries failed
    if last_exception:
        raise last_exception


def create_retry_decorator(config: Optional[RetryConfig] = None):
    """
    Create a retry decorator with specified configuration
    
    Args:
        config: Retry configuration
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return retry_with_exponential_backoff(
                lambda: func(*args, **kwargs),
                config=config,
                operation_name=func.__name__
            )
        return wrapper
    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for exponential backoff with jitter"""
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        # Add up to 25% jitter to prevent thundering herd
        jitter_amount = delay * 0.25
        delay += random.uniform(-jitter_amount, jitter_amount)
    
    return max(0, delay)


# Pre-configured retry decorators for common scenarios
azure_api_retry = create_retry_decorator(RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0
))

network_retry = create_retry_decorator(RetryConfig(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0
))

auth_retry = create_retry_decorator(RetryConfig(
    max_attempts=2,
    base_delay=5.0,
    max_delay=30.0
))
