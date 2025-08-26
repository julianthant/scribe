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
import time
from functools import wraps
from typing import Callable, Any
from datetime import datetime

from app.core.config import settings


def setup_logging() -> None:
    """Configure application logging."""
    startup_logger = logging.getLogger("app.startup")
    startup_time = time.time()
    
    startup_logger.info("[STARTUP] Initializing Scribe application logging...")
    
    # Determine log format
    if settings.log_format == "json":
        # Use a simple format for JSON-style logging
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    elif settings.log_format == "standard":
        # Standard format
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    else:
        # Use the format as-is if it's already a valid format string
        format_string = settings.log_format
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
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
    
    # Suppress SQLAlchemy SQL query logging
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    # Suppress verbose Azure credential logging
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    logging.getLogger("azure.core").setLevel(logging.WARNING)
    logging.getLogger("azure.identity._credentials").setLevel(logging.WARNING)
    logging.getLogger("azure.identity._internal").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    
    # Keep application loggers at appropriate levels
    logging.getLogger("app.startup").setLevel(logging.INFO)
    logging.getLogger("app.database").setLevel(logging.INFO)
    logging.getLogger("app.services").setLevel(logging.INFO)
    logging.getLogger("app.azure").setLevel(logging.INFO)
    
    setup_time = (time.time() - startup_time) * 1000
    startup_logger.info(f"[OK] Logging configuration completed in {setup_time:.2f}ms")
    startup_logger.info(f"[CONFIG] Log level: {settings.log_level}")
    startup_logger.info(f"[CONFIG] Log format: {settings.log_format}")
    startup_logger.info(f"[CONFIG] Environment: {settings.current_env}")


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
    context: str | None = None,
    extra_data: dict | None = None
) -> None:
    """Log error with context."""
    logger = get_logger("app.errors")
    
    message = f"Error in {context}: {str(error)}" if context else str(error)
    
    if extra_data:
        message += f" | Extra data: {extra_data}"
    
    logger.error(message, exc_info=True)


def log_startup_component(
    component_name: str,
    start_time: float,
    success: bool = True,
    error: Exception = None,
    details: dict = None
) -> None:
    """Log startup component initialization."""
    logger = get_logger("app.startup")
    duration = (time.time() - start_time) * 1000
    
    if success:
        logger.info(f"[OK] {component_name} initialized successfully in {duration:.2f}ms")
        if details:
            for key, value in details.items():
                logger.info(f"  -> {key}: {value}")
    else:
        logger.error(f"[ERROR] {component_name} initialization failed after {duration:.2f}ms")
        if error:
            logger.error(f"  -> Error: {str(error)}")


def log_service_startup(
    service_name: str,
    version: str = None,
    config_details: dict = None
) -> None:
    """Log service startup information."""
    logger = get_logger("app.services")
    
    logger.info(f"[SERVICE] Starting {service_name}...")
    if version:
        logger.info(f"  -> Version: {version}")
    
    if config_details:
        for key, value in config_details.items():
            # Don't log sensitive information
            if any(sensitive in key.lower() for sensitive in ['secret', 'password', 'key', 'token']):
                logger.info(f"  -> {key}: [REDACTED]")
            else:
                logger.info(f"  -> {key}: {value}")