"""
Processors module for Scribe Voice Email Processor
Contains email, transcription, and Excel processing components
"""

# Export main classes for easier imports
from .email import EmailProcessor
from .transcription import TranscriptionProcessor
from .excel import ExcelProcessor

__all__ = [
    'EmailProcessor',
    'TranscriptionProcessor',
    'ExcelProcessor'
]