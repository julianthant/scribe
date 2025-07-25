"""
Data Models for Scribe Voice Email Processor
Simple dataclasses for clean data handling
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any

@dataclass
class VoiceAttachment:
    """Voice attachment from email"""
    filename: str
    content: bytes
    size: int
    content_type: str
    
    @property
    def is_voice_file(self) -> bool:
        """Check if this is a voice file"""
        voice_extensions = ['.wav', '.mp3', '.m4a', '.mp4', '.ogg']
        return any(self.filename.lower().endswith(ext) for ext in voice_extensions)

@dataclass
class VoiceEmail:
    """Email containing voice attachments"""
    message_id: str
    subject: str
    sender: str
    received_date: datetime
    voice_attachments: List[VoiceAttachment]
    
    @property
    def has_voice_attachments(self) -> bool:
        """Check if email has voice attachments"""
        return len(self.voice_attachments) > 0

@dataclass
class TranscriptionResult:
    """Result of audio transcription"""
    success: bool
    text: str = ""
    confidence: float = 0.0
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    error_message: str = ""
    
    @property
    def word_count(self) -> int:
        """Get word count of transcription"""
        return len(self.text.split()) if self.text else 0

@dataclass
class ExcelWriteResult:
    """Result of Excel file write operation"""
    success: bool
    row_number: int = 0
    error_message: str = ""
    processing_time_seconds: float = 0.0

@dataclass
class WorkflowResult:
    """Complete workflow execution result"""
    success: bool
    emails_processed: int = 0
    transcriptions_completed: int = 0
    excel_rows_added: int = 0
    errors: List[str] = None
    processing_time_seconds: float = 0.0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.emails_processed == 0:
            return 0.0
        return (self.transcriptions_completed / self.emails_processed) * 100