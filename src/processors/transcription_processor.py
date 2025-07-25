"""
Production Transcription Processor using new core architecture
Handles audio transcription with Azure AI Foundry and error handling
"""

import logging
import os
import json
from typing import Optional, Dict, Any
import requests
from datetime import datetime, timezone

from ..core import ScribeLogger, ScribeErrorHandler, ScribeConfigurationManager
from ..helpers.retry_helpers import RetryConfig, retry_with_exponential_backoff
from ..helpers.performance_helpers import PerformanceTimer
from ..helpers.validation_helpers import validate_url
from ..helpers.auth_helpers import get_managed_identity_token
from ..models import (
    TranscriptionResult, TranscriptionStatus, TranscriptionProvider,
    AudioMetadata, TranscriptionSegment
)


class ScribeTranscriptionProcessor:
    """Production transcription processor using Azure AI Foundry"""
    
    def __init__(self, configuration_manager: ScribeConfigurationManager,
                 error_handler: ScribeErrorHandler, logger: ScribeLogger):
        """Initialize transcription processor with injected dependencies"""
        self.config = configuration_manager
        self.error_handler = error_handler
        self.logger = logger
        
        # Azure AI Foundry configuration
        self.foundry_endpoint = None
        self.speech_endpoint = None
        self.access_token = None
        
        # Request timeout configuration
        self.request_timeout = 300  # 5 minutes for transcription
        
        # Retry configuration for transcription operations
        self.retry_config = RetryConfig(
            max_attempts=3,
            base_delay=5.0,
            max_delay=120.0,
            exponential_base=2.0
        )
    
    def initialize(self) -> bool:
        """Initialize processor with Azure AI Foundry configuration"""
        try:
            # Get AI Foundry endpoint from configuration
            self.foundry_endpoint = self.config.get_setting('AI_FOUNDRY_PROJECT_URL')
            if not self.foundry_endpoint:
                raise ValueError("AI_FOUNDRY_PROJECT_URL not configured")
            
            # Configure speech endpoint
            self._configure_speech_endpoint()
            
            # Get managed identity token
            self.access_token = get_managed_identity_token(
                scope="https://cognitiveservices.azure.com/.default"
            )
            
            if not self.access_token:
                raise ValueError("Failed to obtain managed identity token")
            
            self.logger.log_info("Transcription processor initialized successfully", {
                'foundry_endpoint': self.foundry_endpoint,
                'speech_endpoint': self.speech_endpoint,
                'has_token': bool(self.access_token)
            })
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize transcription processor")
            return False
    
    def transcribe_audio_file(self, audio_url: str, filename: str) -> Optional[TranscriptionResult]:
        """Transcribe audio file from URL"""
        with PerformanceTimer("process_transcription") as timer:
            try:
                if not validate_url(audio_url):
                    raise ValueError(f"Invalid audio URL: {audio_url}")
                
                # Start transcription
                transcription_data = self._transcribe_audio_url(audio_url)
                if not transcription_data:
                    return None
                
                # Convert to TranscriptionResult model
                result = self._convert_to_transcription_result(
                    transcription_data, filename, timer.elapsed_seconds
                )
                
                if result:
                    self.logger.log_info("Audio transcription completed successfully", {
                        'filename': filename,
                        'audio_url': audio_url,
                        'word_count': result.word_count,
                        'confidence': result.confidence_score,
                        'processing_time_seconds': timer.elapsed_seconds
                    })
                
                return result
                
            except Exception as e:
                self.error_handler.handle_error(e, f"Failed to transcribe audio file {filename}")
                return self._create_failed_result(filename, str(e), timer.elapsed_seconds)
    
    def get_supported_formats(self) -> list:
        """Get list of supported audio formats"""
        return ['.mp3', '.wav', '.m4a', '.mp4', '.ogg', '.flac']
    
    def validate_audio_file(self, filename: str, file_size_bytes: int) -> bool:
        """Validate audio file format and size"""
        try:
            # Check format
            supported_formats = self.get_supported_formats()
            if not any(filename.lower().endswith(fmt) for fmt in supported_formats):
                return False
            
            # Check size (max 100MB for example)
            max_size_mb = self.config.get_setting('MAX_AUDIO_FILE_SIZE_MB', 100)
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if file_size_bytes > max_size_bytes:
                return False
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to validate audio file {filename}")
            return False
    
    def _configure_speech_endpoint(self):
        """Configure Azure Speech API endpoint from AI Foundry endpoint"""
        try:
            if 'api.azureml.ms' in self.foundry_endpoint:
                # Extract region from AI Foundry endpoint
                region = self.foundry_endpoint.split('.')[0].split('://')[-1]
                self.speech_endpoint = f"https://{region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2024-05-15-preview"
            else:
                raise ValueError("Unsupported AI Foundry endpoint format")
            
            self.logger.log_info(f"Speech endpoint configured: {self.speech_endpoint}")
            
        except Exception as e:
            raise ValueError(f"Failed to configure speech endpoint: {str(e)}")
    
    def _transcribe_audio_url(self, audio_url: str) -> Optional[Dict]:
        """Transcribe audio from URL using Azure Speech API"""
        
        def _transcribe_operation():
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare transcription request
            transcription_data = {
                "contentUrls": [audio_url],
                "properties": {
                    "diarizationEnabled": False,
                    "wordLevelTimestampsEnabled": True,
                    "punctuationMode": "DictatedAndAutomatic",
                    "profanityFilterMode": "Masked"
                },
                "locale": "en-US",
                "displayName": f"Scribe transcription {datetime.now().isoformat()}"
            }
            
            # Submit transcription request
            response = requests.post(
                self.speech_endpoint,
                headers=headers,
                json=transcription_data,
                timeout=self.request_timeout
            )
            
            if response.status_code not in [200, 201]:
                raise Exception(f"Transcription failed: {response.status_code} - {response.text}")
            
            return response.json()
        
        try:
            return retry_with_exponential_backoff(_transcribe_operation, self.retry_config)
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to transcribe audio URL {audio_url}")
            return None
    
    def _convert_to_transcription_result(self, transcription_data: Dict, 
                                       filename: str, processing_duration: float) -> Optional[TranscriptionResult]:
        """Convert API response to TranscriptionResult model"""
        try:
            # Extract transcription text
            full_text = ""
            segments = []
            confidence_scores = []
            
            # Parse transcription results
            if 'combinedRecognizedPhrases' in transcription_data:
                for phrase in transcription_data['combinedRecognizedPhrases']:
                    if phrase.get('display'):
                        full_text += phrase['display'] + " "
                        
                        # Extract confidence if available
                        if 'confidence' in phrase:
                            confidence_scores.append(phrase['confidence'])
            
            # Parse detailed segments if available
            if 'recognizedPhrases' in transcription_data:
                for phrase in transcription_data['recognizedPhrases']:
                    if phrase.get('nBest') and len(phrase['nBest']) > 0:
                        best = phrase['nBest'][0]
                        
                        segment = TranscriptionSegment(
                            text=best.get('display', ''),
                            start_time=phrase.get('offsetInTicks', 0) / 10000000,  # Convert ticks to seconds
                            end_time=(phrase.get('offsetInTicks', 0) + phrase.get('durationInTicks', 0)) / 10000000,
                            confidence=best.get('confidence', 0.0)
                        )
                        segments.append(segment)
            
            # Calculate average confidence
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else None
            
            # Create audio metadata (placeholder - would extract from actual file)
            audio_metadata = AudioMetadata(
                duration_seconds=sum(seg.duration for seg in segments) if segments else 0.0
            )
            
            # Create transcription result
            result = TranscriptionResult(
                audio_filename=filename,
                provider=TranscriptionProvider.AZURE_SPEECH,
                status=TranscriptionStatus.COMPLETED,
                full_text=full_text.strip(),
                segments=segments,
                audio_metadata=audio_metadata,
                transcription_time=datetime.now(timezone.utc),
                processing_duration_seconds=processing_duration,
                confidence_score=avg_confidence,
                language_detected="en-US"
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to convert transcription result for {filename}")
            return None
    
    def _create_failed_result(self, filename: str, error_message: str, 
                            processing_duration: float) -> TranscriptionResult:
        """Create a failed transcription result"""
        return TranscriptionResult(
            audio_filename=filename,
            provider=TranscriptionProvider.AZURE_SPEECH,
            status=TranscriptionStatus.FAILED,
            full_text="",
            segments=[],
            audio_metadata=AudioMetadata(duration_seconds=0.0),
            transcription_time=datetime.now(timezone.utc),
            processing_duration_seconds=processing_duration,
            error_message=error_message
        )
    
    def _refresh_access_token(self) -> bool:
        """Refresh the managed identity access token"""
        try:
            new_token = get_managed_identity_token(
                scope="https://cognitiveservices.azure.com/.default"
            )
            
            if new_token:
                self.access_token = new_token
                self.logger.log_info("Access token refreshed successfully")
                return True
            
            return False
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to refresh access token")
            return False
