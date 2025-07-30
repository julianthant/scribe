"""
Models module for Scribe Voice Email Processor
Contains data models and structures
"""

# Export main classes for easier imports
from .data import VoiceEmail, VoiceAttachment, TranscriptionResult, WorkflowResult

__all__ = [
    'VoiceEmail',
    'VoiceAttachment', 
    'TranscriptionResult',
    'WorkflowResult'
]