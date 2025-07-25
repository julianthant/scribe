"""
Transcription Processor for Scribe Voice Email Processor
Handles audio transcription using Azure Speech Services
"""

import logging
import requests
import tempfile
import os
import time
from typing import Optional

from core.config import ScribeConfig
from core.input_validation import input_validator
from models.data import TranscriptionResult

logger = logging.getLogger(__name__)

class TranscriptionProcessor:
    """Process audio transcription using Azure Speech Services"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        self.speech_endpoint = config.speech_endpoint.rstrip('/')
        self.api_key = config.speech_api_key
        logger.info(f"🎤 Transcription processor initialized: {self.speech_endpoint}")
    
    def transcribe_audio(self, audio_data: bytes, filename: str = "audio.wav") -> TranscriptionResult:
        """Transcribe audio data using Azure Speech Services"""
        start_time = time.time()
        
        try:
            logger.info(f"🎤 Starting transcription: {filename} ({len(audio_data)} bytes)")
            
            # Validate audio data
            if not audio_data or len(audio_data) == 0:
                return TranscriptionResult(
                    success=False,
                    error_message="No audio data provided"
                )
            
            # Check file size (Azure Speech Services has limits)
            max_size = 50 * 1024 * 1024  # 50MB limit
            if len(audio_data) > max_size:
                return TranscriptionResult(
                    success=False,
                    error_message=f"Audio file too large: {len(audio_data)} bytes (max: {max_size})"
                )
            
            # Prepare Azure Speech Services request
            transcription_url = f"{self.speech_endpoint}/speech/recognition/conversation/cognitiveservices/v1"
            
            params = {
                'language': 'en-US',
                'format': 'detailed'
            }
            
            headers = {
                'Ocp-Apim-Subscription-Key': self.api_key,
                'Content-Type': self._get_content_type(filename),
                'Accept': 'application/json'
            }
            
            # Make transcription request
            logger.info(f"📡 Sending transcription request to Azure Speech Services...")
            response = requests.post(
                transcription_url,
                params=params,
                headers=headers,
                data=audio_data,
                timeout=60  # 60 second timeout
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                result_data = response.json()
                return self._parse_transcription_response(result_data, processing_time)
            else:
                error_msg = f"Azure Speech Services error: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                return TranscriptionResult(
                    success=False,
                    error_message=error_msg,
                    processing_time_seconds=processing_time
                )
                
        except requests.exceptions.Timeout:
            processing_time = time.time() - start_time
            error_msg = "Transcription request timed out"
            logger.error(f"❌ {error_msg}")
            return TranscriptionResult(
                success=False,
                error_message=error_msg,
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return TranscriptionResult(
                success=False,
                error_message=error_msg,
                processing_time_seconds=processing_time
            )
    
    def _get_content_type(self, filename: str) -> str:
        """Get appropriate content type based on file extension"""
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.wav'):
            return 'audio/wav'
        elif filename_lower.endswith('.mp3'):
            return 'audio/mpeg'
        elif filename_lower.endswith('.m4a'):
            return 'audio/mp4'
        elif filename_lower.endswith('.ogg'):
            return 'audio/ogg'
        else:
            # Default to WAV
            return 'audio/wav'
    
    def _parse_transcription_response(self, response_data: dict, processing_time: float) -> TranscriptionResult:
        """Parse Azure Speech Services response"""
        try:
            # Azure Speech Services response format
            recognition_status = response_data.get('RecognitionStatus', '')
            
            if recognition_status == 'Success':
                display_text = response_data.get('DisplayText', '')
                confidence = response_data.get('Confidence', 0.0)
                duration = response_data.get('Duration', 0) / 10_000_000  # Convert from 100ns units to seconds
                
                logger.info(f"✅ Transcription successful: {len(display_text)} characters, {confidence:.2f} confidence")
                
                # Validate and sanitize transcription text
                validated_text = input_validator.validate_transcription_text(display_text) or ""
                
                return TranscriptionResult(
                    success=True,
                    text=validated_text,
                    confidence=confidence,
                    duration_seconds=duration,
                    processing_time_seconds=processing_time
                )
            
            elif recognition_status == 'NoMatch':
                logger.warning("⚠️ No speech detected in audio")
                return TranscriptionResult(
                    success=False,
                    error_message="No speech detected in audio file",
                    processing_time_seconds=processing_time
                )
            
            else:
                error_msg = f"Recognition failed: {recognition_status}"
                logger.error(f"❌ {error_msg}")
                return TranscriptionResult(
                    success=False,
                    error_message=error_msg,
                    processing_time_seconds=processing_time
                )
                
        except Exception as e:
            error_msg = f"Failed to parse transcription response: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return TranscriptionResult(
                success=False,
                error_message=error_msg,
                processing_time_seconds=processing_time
            )
    
    def test_connection(self) -> bool:
        """Test connection to Azure Speech Services"""
        try:
            logger.info("🧪 Testing Azure Speech Services connection...")
            
            # Create a simple test audio (silence)
            test_audio = b'\x00' * 1024  # Simple silence
            
            # Test with minimal audio data
            result = self.transcribe_audio(test_audio, "test.wav")
            
            # Even if transcription fails due to no speech, connection is working if we get a proper response
            if result.success or "No speech detected" in result.error_message:
                logger.info("✅ Azure Speech Services connection test passed")
                return True
            else:
                logger.error(f"❌ Azure Speech Services connection test failed: {result.error_message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Azure Speech Services connection test error: {e}")
            return False