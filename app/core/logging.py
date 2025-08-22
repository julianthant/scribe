"""
logging.py - Application Logging Configuration

Configures structured logging for the Scribe application with multiple handlers and formatters.
This module provides:
- Centralized logging setup with console and file handlers
- Configurable log levels and formats
- API request logging middleware integration
- Function execution time tracking decorators
- Logger factory functions
- Request/response logging with performance metrics

Logs are written to both console (for development) and app.log file (for persistence).
The logging configuration respects the LOG_LEVEL setting from the application config.
"""

import logging
import sys
from functools import wraps
from typing import Callable, Any
from datetime import datetime

from app.core.config import settings


def setup_logging() -> None:
    """Configure application logging."""
    
    # Create formatter
    formatter = logging.Formatter(settings.log_format)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    console_handler.setFormatter(formatter)
    
    # Create file handler
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


def log_execution_time(func: Callable) -> Callable:
    """Decorator to log function execution time."""
    
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        import time
        start_time = time.time()
        logger = get_logger(func.__module__)
        
        try:
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"{func.__name__} executed successfully in {execution_time:.3f}s"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{func.__name__} failed after {execution_time:.3f}s: {str(e)}"
            )
            raise
    
    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        import time
        start_time = time.time()
        logger = get_logger(func.__module__)
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(
                f"{func.__name__} executed successfully in {execution_time:.3f}s"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{func.__name__} failed after {execution_time:.3f}s: {str(e)}"
            )
            raise
    
    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    response_time: float,
    client_ip: str
) -> None:
    """Log API request details."""
    logger = get_logger("api.requests")
    logger.info(
        f"{method} {path} - {status_code} - {response_time:.3f}s - {client_ip}"
    )


def log_error(
    error: Exception,
    context: str = None,
    extra_data: dict = None
) -> None:
    """Log error with context."""
    logger = get_logger("app.errors")
    
    message = f"Error in {context}: {str(error)}" if context else str(error)
    
    if extra_data:
        message += f" | Extra data: {extra_data}"
    
    logger.error(message, exc_info=True)