"""
Production Scribe Voice Email Processor
"""

# Export production processors
from .processors import (
    ScribeEmailProcessor,
    ScribeExcelProcessor, 
    ScribeTranscriptionProcessor,
    ScribeWorkflowProcessor
)

# Export core architecture
from .core import (
    ScribeConfigurationManager,
    ScribeServiceInitializer,
    ScribeWorkflowOrchestrator,
    ScribeErrorHandler,
    ScribeLogger
)

# Export models
from .models import (
    EmailMessage,
    VoiceAttachment,
    TranscriptionResult,
    WorkflowRun
)

__all__ = [
    # Processors
    'ScribeEmailProcessor',
    'ScribeExcelProcessor', 
    'ScribeTranscriptionProcessor',
    'ScribeWorkflowProcessor',
    
    # Core
    'ScribeConfigurationManager',
    'ScribeServiceInitializer',
    'ScribeWorkflowOrchestrator', 
    'ScribeErrorHandler',
    'ScribeLogger',
    
    # Models
    'EmailMessage',
    'VoiceAttachment',
    'TranscriptionResult',
    'WorkflowRun'
]