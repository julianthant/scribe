"""
Transcription data models for audio processing results
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json


class TranscriptionProvider(Enum):
    """Transcription service provider"""
    AZURE_SPEECH = "azure_speech"
    WHISPER = "whisper"
    CUSTOM = "custom"


class TranscriptionStatus(Enum):
    """Transcription processing status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class AudioMetadata:
    """Audio file metadata"""
    duration_seconds: float
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_rate: Optional[int] = None
    format: Optional[str] = None
    file_size_bytes: Optional[int] = None


@dataclass
class TranscriptionSegment:
    """Individual transcription segment with timing"""
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    speaker_id: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """Get segment duration in seconds"""
        return self.end_time - self.start_time


@dataclass
class TranscriptionResult:
    """Complete transcription result"""
    audio_filename: str
    provider: TranscriptionProvider
    status: TranscriptionStatus
    full_text: str
    segments: List[TranscriptionSegment]
    audio_metadata: AudioMetadata
    transcription_time: datetime
    processing_duration_seconds: float
    confidence_score: Optional[float] = None
    language_detected: Optional[str] = None
    error_message: Optional[str] = None
    
    @property
    def word_count(self) -> int:
        """Get word count of transcription"""
        return len(self.full_text.split()) if self.full_text else 0
    
    @property
    def has_segments(self) -> bool:
        """Check if result has detailed segments"""
        return len(self.segments) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'audio_filename': self.audio_filename,
            'provider': self.provider.value,
            'status': self.status.value,
            'full_text': self.full_text,
            'segments': [
                {
                    'text': seg.text,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time,
                    'confidence': seg.confidence,
                    'speaker_id': seg.speaker_id
                }
                for seg in self.segments
            ],
            'audio_metadata': {
                'duration_seconds': self.audio_metadata.duration_seconds,
                'sample_rate': self.audio_metadata.sample_rate,
                'channels': self.audio_metadata.channels,
                'bit_rate': self.audio_metadata.bit_rate,
                'format': self.audio_metadata.format,
                'file_size_bytes': self.audio_metadata.file_size_bytes
            },
            'transcription_time': self.transcription_time.isoformat(),
            'processing_duration_seconds': self.processing_duration_seconds,
            'confidence_score': self.confidence_score,
            'language_detected': self.language_detected,
            'error_message': self.error_message,
            'word_count': self.word_count
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class BatchTranscriptionJob:
    """Batch transcription job for multiple files"""
    job_id: str
    files: List[str]
    status: TranscriptionStatus
    created_time: datetime
    results: List[TranscriptionResult]
    total_files: int
    completed_files: int = 0
    failed_files: int = 0
    
    @property
    def progress_percentage(self) -> float:
        """Get completion percentage"""
        if self.total_files == 0:
            return 0.0
        return (self.completed_files / self.total_files) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if all files are processed"""
        return (self.completed_files + self.failed_files) >= self.total_files
