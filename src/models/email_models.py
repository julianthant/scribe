"""
Email data models for structured email processing
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EmailStatus(Enum):
    """Email processing status"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VoiceAttachment:
    """Voice attachment information"""
    filename: str
    content_type: str
    size_bytes: int
    blob_url: Optional[str] = None
    local_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    def is_voice_file(self) -> bool:
        """Check if attachment is a supported voice file"""
        voice_extensions = ['.mp3', '.wav', '.m4a', '.mp4', '.ogg', '.flac']
        return any(self.filename.lower().endswith(ext) for ext in voice_extensions)


@dataclass
class EmailMessage:
    """Email message structure"""
    message_id: str
    subject: str
    sender: str
    received_datetime: datetime
    body_preview: str
    attachments: List[VoiceAttachment]
    status: EmailStatus = EmailStatus.PENDING
    processing_start_time: Optional[datetime] = None
    processing_end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    
    @property
    def has_voice_attachments(self) -> bool:
        """Check if email has voice attachments"""
        return any(att.is_voice_file() for att in self.attachments)
    
    @property
    def voice_attachments(self) -> List[VoiceAttachment]:
        """Get only voice attachments"""
        return [att for att in self.attachments if att.is_voice_file()]
    
    @property
    def processing_duration(self) -> Optional[float]:
        """Get processing duration in seconds"""
        if self.processing_start_time and self.processing_end_time:
            return (self.processing_end_time - self.processing_start_time).total_seconds()
        return None


@dataclass
class ProcessingResult:
    """Result of email processing operation"""
    email_id: str
    success: bool
    transcription_results: List[Dict[str, Any]]
    excel_updated: bool = False
    email_moved: bool = False
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    warnings: Optional[List[str]] = None
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message"""
        if self.warnings is None:
            self.warnings = []
        self.warnings.append(warning)
