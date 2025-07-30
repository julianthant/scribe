"""
Transcription Processor for Scribe Voice Email Processor
Handles audio transcription using Azure Foundry AI fast transcription
"""

import logging
import requests
import tempfile
import os
import time
import json
from typing import Optional

from core.config import ScribeConfig
from core.input_validation import input_validator
from models.data import TranscriptionResult

logger = logging.getLogger(__name__)

class TranscriptionProcessor:
    """Process audio transcription using Azure Foundry AI fast transcription"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        self.speech_endpoint = config.speech_endpoint.rstrip('/')
        self.api_key = config.speech_api_key
        logger.info(f"🎤 Transcription processor initialized: {self.speech_endpoint}")
    
    def transcribe_audio(self, audio_data: bytes, filename: str = "audio.wav") -> TranscriptionResult:
        """Transcribe audio data using Azure Foundry AI fast transcription"""
        start_time = time.time()
        
        try:
            logger.info(f"🎤 Starting transcription: {filename} ({len(audio_data)} bytes)")
            
            # Validate audio data
            if not audio_data or len(audio_data) == 0:
                return TranscriptionResult(
                    success=False,
                    error_message="No audio data provided"
                )
            
            # Check file size (Azure AI Speech Fast Transcription has limits)
            max_size = 300 * 1024 * 1024  # 300MB limit for Fast Transcription API
            if len(audio_data) > max_size:
                return TranscriptionResult(
                    success=False,
                    error_message=f"Audio file too large: {len(audio_data)} bytes (max: {max_size})"
                )
            
            # Azure AI Speech Fast Transcription API
            transcription_url = f"{self.speech_endpoint}/speechtotext/transcriptions:transcribe?api-version=2024-11-15"
            
            # Prepare multipart/form-data for Fast Transcription API
            files = {
                'audio': (filename, audio_data, self._get_content_type(filename))
            }
            
            # Form definition with locale specification
            form_definition = {
                "locales": ["en-US"]
            }
            
            data = {
                'definition': json.dumps(form_definition)
            }
            
            headers = {
                'Ocp-Apim-Subscription-Key': self.api_key
                # Content-Type will be set automatically for multipart/form-data
            }
            
            # Make transcription request
            logger.info("📡 Sending transcription request")
            response = requests.post(
                transcription_url,
                files=files,
                data=data,
                headers=headers,
                timeout=120  # 120 second timeout for larger files
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                result_data = response.json()
                return self._parse_transcription_response(result_data, processing_time)
            else:
                error_msg = f"Azure AI Foundry fast transcription error: {response.status_code} - {response.text}"
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
        """Parse Azure AI Speech Fast Transcription response"""
        try:
            # Azure AI Speech Fast Transcription response format
            duration_ms = response_data.get('durationMilliseconds', 0)
            duration_seconds = duration_ms / 1000.0
            
            # Get the combined transcription text
            combined_phrases = response_data.get('combinedPhrases', [])
            if combined_phrases:
                text = combined_phrases[0].get('text', '')
            else:
                text = ''
            
            # Calculate average confidence from phrases
            phrases = response_data.get('phrases', [])
            avg_confidence = 0.0
            
            if phrases:
                confidences = [phrase.get('confidence', 0.0) for phrase in phrases if phrase.get('confidence')]
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)
                else:
                    avg_confidence = 0.9  # Default confidence for Fast Transcription
            else:
                avg_confidence = 0.9  # Default confidence when phrases not available
            
            logger.info(f"✅ Transcription successful: {len(text)} characters, {avg_confidence:.2f} confidence, {duration_seconds:.1f}s duration")
            
            # Validate and sanitize transcription text
            validated_text = input_validator.validate_transcription_text(text) or ""
            
            return TranscriptionResult(
                success=True,
                text=validated_text,
                confidence=avg_confidence,
                duration_seconds=duration_seconds,
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
            logger.info("🧪 Testing Azure Speech Services connection")
            
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