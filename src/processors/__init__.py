"""
Production processors using the new core architecture
"""

from .email_processor import ScribeEmailProcessor
from .excel_processor import ScribeExcelProcessor  
from .transcription_processor import ScribeTranscriptionProcessor
from .workflow_processor import ScribeWorkflowProcessor

__all__ = [
    'ScribeEmailProcessor',
    'ScribeExcelProcessor', 
    'ScribeTranscriptionProcessor',
    'ScribeWorkflowProcessor'
]
