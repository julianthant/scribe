"""
Voice Email Processing Components Package
Contains all the modular components for voice email processing
"""

from .azure_foundry_processor_class import AzureFoundryAudioProcessor
from .azure_foundry_processor_functions import (
    create_foundry_audio_processor,
    test_foundry_transcription,
    process_audio_file,
    batch_process_audio_files
)
from .excel_processor_class import ExcelProcessor
from .email_processor_class import EmailProcessor

__all__ = [
    'AzureFoundryAudioProcessor',
    'create_foundry_audio_processor',
    'test_foundry_transcription',
    'process_audio_file',
    'batch_process_audio_files',
    'ExcelProcessor',
    'EmailProcessor'
]