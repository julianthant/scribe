"""
Data models for the Scribe application
"""

# Email models
from .email_models import (
    EmailStatus,
    VoiceAttachment,
    EmailMessage,
    ProcessingResult
)

# Transcription models
from .transcription_models import (
    TranscriptionProvider,
    TranscriptionStatus,
    AudioMetadata,
    TranscriptionSegment,
    TranscriptionResult,
    BatchTranscriptionJob
)

# Workflow models
from .workflow_models import (
    WorkflowStage,
    WorkflowStatus,
    StageResult,
    WorkflowRun,
    WorkflowConfiguration
)

__all__ = [
    # Email models
    'EmailStatus',
    'VoiceAttachment', 
    'EmailMessage',
    'ProcessingResult',
    
    # Transcription models
    'TranscriptionProvider',
    'TranscriptionStatus',
    'AudioMetadata',
    'TranscriptionSegment',
    'TranscriptionResult',
    'BatchTranscriptionJob',
    
    # Workflow models
    'WorkflowStage',
    'WorkflowStatus',
    'StageResult',
    'WorkflowRun',
    'WorkflowConfiguration'
]

from .email_models import EmailMessage, VoiceAttachment, ProcessingResult
from .transcription_models import TranscriptionResult, AudioMetadata, TranscriptionStatus
from .workflow_models import WorkflowStage, WorkflowStatus, WorkflowRun, WorkflowConfiguration, StageResult

__all__ = [
    # Email models
    'EmailMessage',
    'VoiceAttachment', 
    'ProcessingResult',
    
    # Transcription models
    'TranscriptionResult',
    'AudioMetadata',
    'TranscriptionStatus',
    
    # Workflow models
    'WorkflowStage',
    'WorkflowStatus', 
    'WorkflowRun',
    'WorkflowConfiguration',
    'StageResult'
]
