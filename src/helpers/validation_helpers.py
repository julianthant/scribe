"""
Validation helper functions for input validation and data integrity
"""

import re
import os
from typing import Union, Optional, List
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass 
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None


def validate_email_address(email: str) -> ValidationResult:
    """
    Validate email address format
    
    Args:
        email: Email address to validate
        
    Returns:
        ValidationResult: Validation result
    """
    if not email:
        return ValidationResult(False, "Email address is required")
    
    # Basic email pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email):
        return ValidationResult(True)
    else:
        return ValidationResult(False, f"Invalid email format: {email}")


def validate_url(url: str, require_https: bool = True) -> ValidationResult:
    """
    Validate URL format and scheme
    
    Args:
        url: URL to validate
        require_https: Whether to require HTTPS scheme
        
    Returns:
        ValidationResult: Validation result
    """
    if not url:
        return ValidationResult(False, "URL is required")
    
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            return ValidationResult(False, "URL must include scheme (https://)")
        
        if require_https and parsed.scheme != 'https':
            return ValidationResult(False, f"URL must use HTTPS: {url}")
        
        if not parsed.netloc:
            return ValidationResult(False, f"URL must include domain: {url}")
        
        return ValidationResult(True)
        
    except Exception as e:
        return ValidationResult(False, f"Invalid URL format: {str(e)}")


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> ValidationResult:
    """
    Validate file extension
    
    Args:
        filename: Name of file to validate
        allowed_extensions: List of allowed extensions (with dots)
        
    Returns:
        ValidationResult: Validation result
    """
    if not filename:
        return ValidationResult(False, "Filename is required")
    
    if not allowed_extensions:
        return ValidationResult(True)  # No restrictions
    
    # Get file extension
    _, ext = os.path.splitext(filename.lower())
    
    if ext in [e.lower() for e in allowed_extensions]:
        return ValidationResult(True)
    else:
        return ValidationResult(
            False, 
            f"File extension '{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"
        )


def validate_environment_variable(var_name: str, required: bool = True) -> ValidationResult:
    """
    Validate environment variable presence and value
    
    Args:
        var_name: Environment variable name
        required: Whether the variable is required
        
    Returns:
        ValidationResult: Validation result
    """
    value = os.environ.get(var_name)
    
    if not value:
        if required:
            return ValidationResult(False, f"Required environment variable '{var_name}' is missing")
        else:
            return ValidationResult(True, None, [f"Optional environment variable '{var_name}' is not set"])
    
    if not value.strip():
        return ValidationResult(False, f"Environment variable '{var_name}' is empty")
    
    return ValidationResult(True)
