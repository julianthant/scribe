"""
Azure AI Foundry Speech Services Audio Processor Class
Fast transcription using Azure AI Foundry Fast Transcription API with API key authentication
"""

import logging
import os


class AzureFoundryAudioProcessor:
    """Azure AI Foundry-based audio processor with Fast Transcription API"""
    
    def __init__(self, speech_key, speech_region, blob_client=None, foundry_endpoint=None):
        """Initialize the Azure Foundry Audio Processor with Fast Transcription"""
        self.speech_key = speech_key
        self.speech_region = speech_region  
        self.blob_client = blob_client
        
        # Azure AI Foundry Fast Transcription endpoint
        if foundry_endpoint:
            self.foundry_endpoint = foundry_endpoint
        else:
            self.foundry_endpoint = f"https://{speech_region}.stt.speech.microsoft.com"
        
        # Fast Transcription API endpoint for API key authentication  
        if foundry_endpoint and 'cognitiveservices.azure.com' in foundry_endpoint:
            # Use custom subdomain endpoint
            base_domain = foundry_endpoint.replace('https://', '').replace('http://', '')
            self.fast_transcription_endpoint = f"https://{base_domain}/speechtotext/transcriptions:transcribe?api-version=2024-11-15"
        else:
            # Default endpoint for API key authentication  
            self.fast_transcription_endpoint = f"https://{speech_region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2024-11-15"
        
        logging.info(f"Initialized Azure Foundry Audio Processor with Fast Transcription")
        logging.info(f"Authentication: API Key")
        logging.info(f"Endpoint: {self.foundry_endpoint}")
        logging.info(f"Fast Transcription API: {self.fast_transcription_endpoint}")
    
    def transcribe_local_audio(self, local_file_path):
        """Transcribe audio from a local file path"""
        from .azure_foundry_processor_functions import transcribe_local_audio_impl
        return transcribe_local_audio_impl(self, local_file_path)
    
    def transcribe_audio(self, blob_url_or_path):
        """Transcribe audio from blob URL or local path"""
        from .azure_foundry_processor_functions import transcribe_audio_impl
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
