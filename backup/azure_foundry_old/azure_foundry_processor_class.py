"""
Azure AI Foundry Audio Processor Class
Transcription using Azure AI Foundry with Managed Identity authentication
"""

import logging
import os
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential


class AzureFoundryAudioProcessor:
    """Azure AI Foundry-based audio processor with Managed Identity authentication"""
    
    def __init__(self, foundry_endpoint=None, blob_client=None):
        """Initialize the Azure AI Foundry Audio Processor"""
        self.blob_client = blob_client
        
        # Use AI Foundry project endpoint from environment
        self.foundry_endpoint = foundry_endpoint or os.environ.get('AI_FOUNDRY_PROJECT_URL')
        
        if not self.foundry_endpoint:
            raise ValueError("AI_FOUNDRY_PROJECT_URL environment variable or foundry_endpoint parameter required")
        
        # Try ManagedIdentityCredential first for Azure Functions
        try:
            self.credential = ManagedIdentityCredential()
            logging.info("✅ Using ManagedIdentityCredential for Azure AI Foundry access")
        except Exception as e:
            logging.warning(f"⚠️ ManagedIdentityCredential failed: {str(e)}")
            # Fallback to DefaultAzureCredential
            self.credential = DefaultAzureCredential()
            logging.info("✅ Using DefaultAzureCredential for Azure AI Foundry access")
        
        # Build the AI Foundry transcription endpoint
        # Format: https://<project-name>.<region>.inference.ml.azure.com/v1/audio/transcriptions
        if '/inference.ml.azure.com' in self.foundry_endpoint:
            self.transcription_endpoint = f"{self.foundry_endpoint.rstrip('/')}/v1/audio/transcriptions"
        else:
            # Handle legacy format or custom endpoints
            self.transcription_endpoint = f"{self.foundry_endpoint.rstrip('/')}/v1/audio/transcriptions"
        
        logging.info(f"✅ Initialized Azure AI Foundry Audio Processor")
        logging.info(f"🔗 Project Endpoint: {self.foundry_endpoint}")
        logging.info(f"🎤 Transcription API: {self.transcription_endpoint}")
        logging.info(f"🔐 Authentication: Managed Identity")

import logging
import os
from azure.identity import DefaultAzureCredential


class AzureFoundryAudioProcessor:
    """Azure AI Foundry-based audio processor with Managed Identity authentication"""
    
    def __init__(self, foundry_endpoint=None, blob_client=None):
        """Initialize the Azure AI Foundry Audio Processor"""
        self.blob_client = blob_client
        
        # Use AI Foundry project endpoint from environment
        self.foundry_endpoint = foundry_endpoint or os.environ.get('AI_FOUNDRY_PROJECT_URL')
        
        if not self.foundry_endpoint:
            raise ValueError("AI_FOUNDRY_PROJECT_URL environment variable or foundry_endpoint parameter required")
        
        # Initialize credential for Managed Identity
        self.credential = DefaultAzureCredential()
        
        # For Azure AI Foundry, we'll convert the ML endpoint to the Speech API endpoint in the functions
        # The actual Fast Transcription API endpoint will be built dynamically
        
        logging.info(f"✅ Initialized Azure AI Foundry Audio Processor")
        logging.info(f"🔗 AI Foundry Project: {self.foundry_endpoint}")
        logging.info(f"🎤 Will use Azure AI Foundry Fast Transcription API")
        logging.info(f"🔐 Authentication: Managed Identity")
    
    def transcribe_local_audio(self, local_file_path):
        """Transcribe audio from a local file path"""
        from .azure_foundry_processor_functions_new import transcribe_local_audio_impl
        return transcribe_local_audio_impl(self, local_file_path)
    
    def transcribe_audio(self, blob_url_or_path):
        """Transcribe audio from blob URL or local path"""
        from .azure_foundry_processor_functions_new import transcribe_audio_impl
        return transcribe_audio_impl(self, blob_url_or_path)
    
    def _get_audio_duration(self, file_path):
        """Get audio file duration in seconds"""
        from .azure_foundry_processor_functions import get_audio_duration_impl
        return get_audio_duration_impl(self, file_path)
    
    def _perform_fast_transcription(self, audio_file_path, audio_duration):
        """Perform Fast Transcription using Azure AI Foundry Fast Transcription API"""
        from .azure_foundry_processor_functions import perform_fast_transcription_impl
        return perform_fast_transcription_impl(self, audio_file_path, audio_duration)
    
    def _process_fast_transcription_result(self, result, processing_time, audio_duration):
        """Process Fast Transcription API response"""
        from .azure_foundry_processor_functions import process_fast_transcription_result_impl
        return process_fast_transcription_result_impl(self, result, processing_time, audio_duration)
    
    def _fallback_to_speech_sdk(self, audio_file_path, audio_duration):
        """Fallback to regular Speech SDK if Fast Transcription fails"""
        from .azure_foundry_processor_functions import fallback_to_speech_sdk_impl
        return fallback_to_speech_sdk_impl(self, audio_file_path, audio_duration)
    
    def _perform_continuous_fallback(self, speech_recognizer, audio_duration):
        """Continuous recognition fallback for longer audio"""
        from .azure_foundry_processor_functions import perform_continuous_fallback_impl
        return perform_continuous_fallback_impl(self, speech_recognizer, audio_duration)
    
    def _extract_confidence(self, result):
        """Extract confidence score from recognition result"""
        from .azure_foundry_processor_functions import extract_confidence_impl
        return extract_confidence_impl(self, result)
