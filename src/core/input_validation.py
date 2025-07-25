"""
Input Validation and Sanitization for Scribe Voice Email Processor
Protects against injection attacks and ensures data integrity
"""

import re
import html
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    # Security patterns
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',                # JavaScript URLs
        r'data:.*base64',             # Base64 data URLs
        r'vbscript:',                 # VBScript
        r'onload\s*=',                # Event handlers
        r'onerror\s*=',
        r'onclick\s*=',
        r'\.\./',                     # Path traversal
        r'\\\.\\\.\\',               # Windows path traversal
        r'%2e%2e%2f',                # URL encoded path traversal
        r'%252e%252e%252f',          # Double URL encoded path traversal
    ]
    
    # File extension validation (only .wav files as per user requirement)
    ALLOWED_AUDIO_EXTENSIONS = {'.wav'}
    ALLOWED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
    
    # Size limits
    MAX_TEXT_LENGTH = 50000          # 50KB of text
    MAX_FILENAME_LENGTH = 255        # Standard filesystem limit
    MAX_EMAIL_LENGTH = 320           # RFC standard
    MAX_SUBJECT_LENGTH = 998         # RFC standard
    MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB
    
    def __init__(self):
        # Compile regex patterns for performance
        self.dangerous_pattern = re.compile('|'.join(self.DANGEROUS_PATTERNS), re.IGNORECASE)
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        self.safe_filename_pattern = re.compile(r'^[a-zA-Z0-9._-]+$')
        
        logger.info("🛡️ Input validator initialized")
    
    def validate_email_address(self, email: str) -> Optional[str]:
        """Validate and sanitize email address"""
        try:
            if not email or not isinstance(email, str):
                logger.warning("⚠️ Invalid email: empty or non-string")
                return None
            
            # Length check
            if len(email) > self.MAX_EMAIL_LENGTH:
                logger.warning(f"⚠️ Email too long: {len(email)} chars (max: {self.MAX_EMAIL_LENGTH})")
                return None
            
            # Basic sanitization
            email = email.strip().lower()
            
            # Pattern validation
            if not self.email_pattern.match(email):
                logger.warning(f"⚠️ Invalid email format: {email}")
                return None
            
            # Security check
            if self.dangerous_pattern.search(email):
                logger.warning(f"🚨 Dangerous pattern detected in email: {email}")
                return None
            
            return email
            
        except Exception as e:
            logger.error(f"❌ Email validation error: {e}")
            return None
    
    def validate_email_subject(self, subject: str) -> Optional[str]:
        """Validate and sanitize email subject"""
        try:
            if not isinstance(subject, str):
                logger.warning("⚠️ Invalid subject: not a string")
                return ""
            
            # Length check
            if len(subject) > self.MAX_SUBJECT_LENGTH:
                logger.warning(f"⚠️ Subject too long: {len(subject)} chars (max: {self.MAX_SUBJECT_LENGTH})")
                subject = subject[:self.MAX_SUBJECT_LENGTH]
            
            # HTML escape and strip dangerous content
            subject = html.escape(subject.strip())
            
            # Remove dangerous patterns
            subject = self.dangerous_pattern.sub('', subject)
            
            # Remove control characters
            subject = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', subject)
            
            return subject
            
        except Exception as e:
            logger.error(f"❌ Subject validation error: {e}")
            return ""
    
    def validate_filename(self, filename: str) -> Optional[str]:
        """Validate and sanitize filename"""
        try:
            if not filename or not isinstance(filename, str):
                logger.warning("⚠️ Invalid filename: empty or non-string")
                return None
            
            # Length check
            if len(filename) > self.MAX_FILENAME_LENGTH:
                logger.warning(f"⚠️ Filename too long: {len(filename)} chars (max: {self.MAX_FILENAME_LENGTH})")
                return None
            
            # Basic sanitization
            filename = filename.strip()
            
            # Security check - prevent path traversal
            if '..' in filename or '/' in filename or '\\' in filename:
                logger.warning(f"🚨 Path traversal attempt in filename: {filename}")
                return None
            
            # Check for dangerous patterns
            if self.dangerous_pattern.search(filename):
                logger.warning(f"🚨 Dangerous pattern detected in filename: {filename}")
                return None
            
            # Remove control characters
            filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
            
            # Ensure safe characters only
            if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
                # Sanitize by keeping only safe characters
                filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
                logger.info(f"📋 Filename sanitized: {filename}")
            
            return filename
            
        except Exception as e:
            logger.error(f"❌ Filename validation error: {e}")
            return None
    
    def validate_audio_filename(self, filename: str) -> Optional[str]:
        """Validate audio filename with extension check"""
        try:
            validated_filename = self.validate_filename(filename)
            if not validated_filename:
                return None
            
            # Check extension
            file_path = Path(validated_filename)
            extension = file_path.suffix.lower()
            
            if extension not in self.ALLOWED_AUDIO_EXTENSIONS:
                logger.info(f"ℹ️ Skipping non-WAV audio file: {extension}. Only .wav files are processed.")
                return None
            
            return validated_filename
            
        except Exception as e:
            logger.error(f"❌ Audio filename validation error: {e}")
            return None
    
    def validate_transcription_text(self, text: str) -> Optional[str]:
        """Validate and sanitize transcription text"""
        try:
            if not isinstance(text, str):
                logger.warning("⚠️ Invalid transcription: not a string")
                return ""
            
            # Length check
            if len(text) > self.MAX_TEXT_LENGTH:
                logger.warning(f"⚠️ Transcription too long: {len(text)} chars (max: {self.MAX_TEXT_LENGTH})")
                text = text[:self.MAX_TEXT_LENGTH]
            
            # Basic sanitization
            text = text.strip()
            
            # HTML escape
            text = html.escape(text)
            
            # Remove dangerous patterns
            text = self.dangerous_pattern.sub('', text)
            
            # Normalize line endings
            text = re.sub(r'\r\n|\r|\n', ' ', text)
            
            # Remove excessive whitespace
            text = re.sub(r'\s+', ' ', text)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Transcription validation error: {e}")
            return ""
    
    def validate_audio_data(self, audio_data: bytes, filename: str = "") -> bool:
        """Validate audio data"""
        try:
            if not audio_data or not isinstance(audio_data, bytes):
                logger.warning("⚠️ Invalid audio data: empty or not bytes")
                return False
            
            # Size check
            if len(audio_data) > self.MAX_AUDIO_SIZE:
                logger.warning(f"⚠️ Audio file too large: {len(audio_data)} bytes (max: {self.MAX_AUDIO_SIZE})")
                return False
            
            # Basic magic number check for common audio formats
            if self._validate_audio_format(audio_data, filename):
                return True
            
            logger.warning(f"⚠️ Audio format validation failed for: {filename}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Audio data validation error: {e}")
            return False
    
    def _validate_audio_format(self, audio_data: bytes, filename: str) -> bool:
        """Validate audio format by magic numbers"""
        try:
            if len(audio_data) < 12:
                return False
            
            # Check magic numbers for common formats
            if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
                return True  # WAV
            elif audio_data.startswith(b'ID3') or audio_data.startswith(b'\xff\xfb'):
                return True  # MP3
            elif audio_data.startswith(b'\x00\x00\x00\x20ftypM4A'):
                return True  # M4A
            elif audio_data.startswith(b'OggS'):
                return True  # OGG
            elif audio_data.startswith(b'fLaC'):
                return True  # FLAC
            
            # If we can't validate by magic number, allow it but log warning
            logger.warning(f"⚠️ Could not validate audio format for: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Audio format validation error: {e}")
            return False
    
    def validate_excel_filename(self, filename: str) -> Optional[str]:
        """Validate Excel filename"""
        try:
            validated_filename = self.validate_filename(filename)
            if not validated_filename:
                return None
            
            # Check extension
            file_path = Path(validated_filename)
            extension = file_path.suffix.lower()
            
            if extension not in self.ALLOWED_EXCEL_EXTENSIONS:
                logger.warning(f"⚠️ Invalid Excel file extension: {extension}. Allowed: {self.ALLOWED_EXCEL_EXTENSIONS}")
                return None
            
            return validated_filename
            
        except Exception as e:
            logger.error(f"❌ Excel filename validation error: {e}")
            return None
    
    def validate_request_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize request parameters"""
        try:
            sanitized_params = {}
            
            # Validate max_emails
            max_emails = params.get('max_emails', 5)
            if isinstance(max_emails, (int, str)):
                try:
                    max_emails = int(max_emails)
                    if 1 <= max_emails <= 100:  # Reasonable limits
                        sanitized_params['max_emails'] = max_emails
                    else:
                        logger.warning(f"⚠️ max_emails out of range: {max_emails}, using default: 5")
                        sanitized_params['max_emails'] = 5
                except ValueError:
                    sanitized_params['max_emails'] = 5
            else:
                sanitized_params['max_emails'] = 5
            
            # Validate days_back
            days_back = params.get('days_back', 7)
            if isinstance(days_back, (int, str)):
                try:
                    days_back = int(days_back)
                    if 1 <= days_back <= 90:  # Reasonable limits
                        sanitized_params['days_back'] = days_back
                    else:
                        logger.warning(f"⚠️ days_back out of range: {days_back}, using default: 7")
                        sanitized_params['days_back'] = 7
                except ValueError:
                    sanitized_params['days_back'] = 7
            else:
                sanitized_params['days_back'] = 7
            
            # Validate boolean parameters
            sanitized_params['manual_trigger'] = bool(params.get('manual_trigger', False))
            sanitized_params['test_mode'] = bool(params.get('test_mode', False))
            
            return sanitized_params
            
        except Exception as e:
            logger.error(f"❌ Parameter validation error: {e}")
            return {'max_emails': 5, 'days_back': 7, 'manual_trigger': False, 'test_mode': False}
    
    def validate_url(self, url: str) -> bool:
        """Validate URL for Graph API requests"""
        try:
            if not url or not isinstance(url, str):
                return False
            
            parsed = urlparse(url)
            
            # Must be HTTPS
            if parsed.scheme != 'https':
                logger.warning(f"🚨 Non-HTTPS URL rejected: {url}")
                return False
            
            # Must be Microsoft Graph domain
            allowed_hosts = ['graph.microsoft.com', 'graph.microsoft.us', 'microsoftgraph.chinacloudapi.cn']
            if parsed.hostname not in allowed_hosts:
                logger.warning(f"🚨 Invalid host for Graph API: {parsed.hostname}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ URL validation error: {e}")
            return False


# Global validator instance
input_validator = InputValidator()