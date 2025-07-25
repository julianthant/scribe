"""
Helper functions module for Scribe voice email processor
Contains reusable utility functions for retry logic, validation, performance monitoring, and authentication
"""

from .retry_helpers import (
    retry_with_exponential_backoff,
    create_retry_decorator,
    RetryConfig
)

from .validation_helpers import (
    validate_email_address,
    validate_url,
    validate_file_extension,
    validate_environment_variable,
    ValidationResult
)

from .performance_helpers import (
    time_operation,
    PerformanceTimer,
    track_memory_usage,
    log_performance_metrics
)

from .auth_helpers import (
    refresh_token_if_needed,
    validate_token_expiry,
    get_managed_identity_token
)

__all__ = [
    # Retry helpers
    'retry_with_exponential_backoff',
    'create_retry_decorator', 
    'RetryConfig',
    
    # Validation helpers
    'validate_email_address',
    'validate_url',
    'validate_file_extension',
    'validate_environment_variable',
    'ValidationResult',
    
    # Performance helpers
    'time_operation',
    'PerformanceTimer',
    'track_memory_usage',
    'log_performance_metrics',
    
    # Auth helpers
    'refresh_token_if_needed',
    'validate_token_expiry',
    'get_managed_identity_token'
]
