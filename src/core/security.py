"""
Security utilities and validation for Scribe Voice Email Processor
Production-ready security controls and validation
"""

import re
import logging
import hashlib
import secrets
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of security validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __post_init__(self):
        if not hasattr(self, 'errors'):
            self.errors = []
        if not hasattr(self, 'warnings'):
            self.warnings = []

class SecurityValidator:
    """Production security validation and sanitization"""
    
    # Email validation regex (RFC 5322 compliant)
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )
    
    # Safe filename regex
    SAFE_FILENAME_REGEX = re.compile(r'^[a-zA-Z0-9._-]+$')
    
    # Content type whitelist
    ALLOWED_AUDIO_TYPES = {
        'audio/wav', 'audio/mpeg', 'audio/mp4', 'audio/ogg', 
        'audio/webm', 'audio/flac', 'audio/aac'
    }
    
    # Maximum file sizes (in bytes)
    MAX_AUDIO_SIZE = 300 * 1024 * 1024  # 300MB
    MAX_FILENAME_LENGTH = 255
    
    @staticmethod
    def validate_email_address(email: str) -> ValidationResult:
        """Validate email address format and security"""
        errors = []
        warnings = []
        
        if not email:
            errors.append("Email address is required")
            return ValidationResult(False, errors, warnings)
        
        # Length check
        if len(email) > 254:  # RFC 5321 limit
            errors.append("Email address too long")
        
        # Format validation
        if not SecurityValidator.EMAIL_REGEX.match(email):
            errors.append("Invalid email address format")
        
        # Domain validation
        if '@' in email:
            local, domain = email.rsplit('@', 1)
            
            # Local part checks
            if len(local) > 64:  # RFC 5321 limit
                errors.append("Email local part too long")
            
            # Domain checks
            if len(domain) > 253:
                errors.append("Email domain too long")
            
            # Check for suspicious patterns
            if '..' in email:
                warnings.append("Email contains consecutive dots")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def validate_filename(filename: str) -> ValidationResult:
        """Validate filename for security"""
        errors = []
        warnings = []
        
        if not filename:
            errors.append("Filename is required")
            return ValidationResult(False, errors, warnings)
        
        # Length check
        if len(filename) > SecurityValidator.MAX_FILENAME_LENGTH:
            errors.append(f"Filename too long (max {SecurityValidator.MAX_FILENAME_LENGTH} chars)")
        
        # Path traversal check
        if '..' in filename or '/' in filename or '\\' in filename:
            errors.append("Filename contains path traversal characters")
        
        # Null byte check
        if '\x00' in filename:
            errors.append("Filename contains null bytes")
        
        # Character validation
        if not SecurityValidator.SAFE_FILENAME_REGEX.match(filename):
            warnings.append("Filename contains potentially unsafe characters")
        
        # Extension check
        if not any(filename.lower().endswith(ext) for ext in ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.aac']):
            warnings.append("File extension not in common audio formats")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def validate_audio_content(content: bytes, content_type: str) -> ValidationResult:
        """Validate audio content for security"""
        errors = []
        warnings = []
        
        if not content:
            errors.append("Audio content is empty")
            return ValidationResult(False, errors, warnings)
        
        # Size validation
        if len(content) > SecurityValidator.MAX_AUDIO_SIZE:
            errors.append(f"Audio file too large (max {SecurityValidator.MAX_AUDIO_SIZE / (1024*1024):.0f}MB)")
        
        if len(content) < 100:  # Suspiciously small
            warnings.append("Audio file is very small")
        
        # Content type validation
        if content_type not in SecurityValidator.ALLOWED_AUDIO_TYPES:
            warnings.append(f"Content type '{content_type}' not in whitelist")
        
        # Basic header validation for common formats
        if content_type == 'audio/wav' and not content.startswith(b'RIFF'):
            warnings.append("WAV file doesn't start with RIFF header")
        elif content_type == 'audio/mpeg' and not (content.startswith(b'ID3') or content[0:2] == b'\xff\xfb'):
            warnings.append("MP3 file doesn't have expected header")
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    @staticmethod
    def sanitize_text_content(text: str, max_length: int = 10000) -> str:
        """Sanitize text content for safe storage"""
        if not text:
            return ""
        
        # Remove null bytes and control characters (except newlines and tabs)
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length] + "..."
            logger.warning(f"Text content truncated to {max_length} characters")
        
        return sanitized.strip()
    
    @staticmethod
    def generate_secure_filename(original_filename: str) -> str:
        """Generate a secure filename based on original"""
        # Extract extension
        if '.' in original_filename:
            name, ext = original_filename.rsplit('.', 1)
            ext = '.' + ext.lower()
        else:
            name = original_filename
            ext = ''
        
        # Generate secure name
        timestamp = int(time.time())
        random_suffix = secrets.token_hex(8)
        
        # Sanitize original name (take first 20 safe chars)
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:20]
        
        return f"{timestamp}_{safe_name}_{random_suffix}{ext}"
    
    @staticmethod
    def validate_configuration(config: Dict[str, Any]) -> ValidationResult:
        """Validate system configuration for security"""
        errors = []
        warnings = []
        
        # Check for sensitive data in config
        sensitive_keys = ['password', 'secret', 'key', 'token']
        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str) and len(value) > 10:
                    warnings.append(f"Potentially sensitive data in config key: {key}")
        
        # Validate URLs
        url_keys = ['endpoint', 'url', 'uri']
        for key, value in config.items():
            if any(url_key in key.lower() for url_key in url_keys):
                if isinstance(value, str) and value:
                    if not value.startswith(('https://', 'http://localhost')):
                        warnings.append(f"Non-HTTPS URL in config: {key}")
        
        return ValidationResult(len(errors) == 0, errors, warnings)

# Global security validator instance
security_validator = SecurityValidator()

def validate_and_sanitize_input(**kwargs) -> Dict[str, Any]:
    """Decorator function to validate and sanitize inputs"""
    def decorator(func):
        def wrapper(*args, **kwargs_inner):
            # Validate inputs based on function signature
            # This would need to be customized per function
            return func(*args, **kwargs_inner)
        return wrapper
    return decorator