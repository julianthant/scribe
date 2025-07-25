"""
Workflow and state management models for orchestrating the email processing pipeline
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from enum import Enum
import uuid

from .email_models import EmailMessage, ProcessingResult
from .transcription_models import TranscriptionResult


class WorkflowStage(Enum):
    """Workflow processing stages"""
    INITIALIZATION = "initialization"
    EMAIL_RETRIEVAL = "email_retrieval"
    EMAIL_FILTERING = "email_filtering"
    ATTACHMENT_PROCESSING = "attachment_processing"
    TRANSCRIPTION = "transcription"
    DATA_VALIDATION = "data_validation"
    EXCEL_UPDATE = "excel_update"
    EMAIL_CLEANUP = "email_cleanup"
    COMPLETION = "completion"
    ERROR_HANDLING = "error_handling"


class WorkflowStatus(Enum):
    """Overall workflow status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY_PENDING = "retry_pending"


@dataclass
class StageResult:
    """Result of a single workflow stage"""
    stage: WorkflowStage
    status: WorkflowStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    items_processed: int = 0
    items_total: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get stage duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def progress_percentage(self) -> float:
        """Get stage progress percentage"""
        if self.items_total == 0:
            return 100.0 if self.success else 0.0
        return (self.items_processed / self.items_total) * 100


@dataclass
class WorkflowRun:
    """Complete workflow execution instance"""
    run_id: str
    start_time: datetime
    status: WorkflowStatus
    current_stage: WorkflowStage
    stage_results: List[StageResult] = field(default_factory=list)
    emails_processed: List[EmailMessage] = field(default_factory=list)
    processing_results: List[ProcessingResult] = field(default_factory=list)
    transcription_results: List[TranscriptionResult] = field(default_factory=list)
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize run_id if not provided"""
        if not self.run_id:
            self.run_id = str(uuid.uuid4())
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get total workflow duration"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def can_retry(self) -> bool:
        """Check if workflow can be retried"""
        return self.retry_count < self.max_retries and self.status == WorkflowStatus.FAILED
    
    @property
    def total_emails_found(self) -> int:
        """Get total number of emails found"""
        return len(self.emails_processed)
    
    @property
    def emails_with_voice(self) -> int:
        """Get number of emails with voice attachments"""
        return len([email for email in self.emails_processed if email.has_voice_attachments])
    
    @property
    def successful_transcriptions(self) -> int:
        """Get number of successful transcriptions"""
        return len([result for result in self.processing_results if result.success])
    
    def add_stage_result(self, stage_result: StageResult) -> None:
        """Add a stage result to the workflow"""
        self.stage_results.append(stage_result)
        self.current_stage = stage_result.stage
        
        if not stage_result.success and stage_result.stage != WorkflowStage.ERROR_HANDLING:
            self.status = WorkflowStatus.FAILED
            self.error_message = stage_result.error_message
    
    def get_stage_result(self, stage: WorkflowStage) -> Optional[StageResult]:
        """Get result for a specific stage"""
        for result in self.stage_results:
            if result.stage == stage:
                return result
        return None
    
    def mark_completed(self) -> None:
        """Mark workflow as completed"""
        self.status = WorkflowStatus.COMPLETED
        self.end_time = datetime.now(timezone.utc)
    
    def mark_failed(self, error_message: str) -> None:
        """Mark workflow as failed"""
        self.status = WorkflowStatus.FAILED
        self.error_message = error_message
        self.end_time = datetime.now(timezone.utc)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Get workflow summary for logging"""
        return {
            'run_id': self.run_id,
            'status': self.status.value,
            'current_stage': self.current_stage.value,
            'duration_seconds': self.duration_seconds,
            'total_emails': self.total_emails_found,
            'emails_with_voice': self.emails_with_voice,
            'successful_transcriptions': self.successful_transcriptions,
            'retry_count': self.retry_count,
            'error_message': self.error_message,
            'stages_completed': len(self.stage_results)
        }


@dataclass
class WorkflowConfiguration:
    """Configuration for workflow execution"""
    max_emails_per_run: int = 50
    max_attachment_size_mb: int = 100
    supported_audio_formats: Set[str] = field(default_factory=lambda: {'.mp3', '.wav', '.m4a', '.mp4'})
    retry_failed_emails: bool = True
    move_processed_emails: bool = True
    excel_backup_enabled: bool = True
    transcription_timeout_seconds: int = 300
    parallel_transcription_limit: int = 3
    
    def is_supported_format(self, filename: str) -> bool:
        """Check if file format is supported"""
        return any(filename.lower().endswith(fmt) for fmt in self.supported_audio_formats)
