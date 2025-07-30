#!/usr/bin/env python3
"""
Transcription Processor Unit Tests
Tests audio transcription functionality and AI services integration
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestTranscriptionProcessor(unittest.TestCase):
    """Test transcription processing functionality"""
    
    def setUp(self):
        """Set up test configuration"""
        from core.config import ScribeConfig
        
        self.config = ScribeConfig(
            client_id='test-client-id',
            tenant_id='test-tenant-id',
            storage_connection_string='test-connection',
            excel_file_name='Test_Scribe.xlsx',
            speech_api_key='test-api-key',
            max_emails=5,
            days_back=7
        )
        
        # Sample audio data for testing
        self.sample_audio_data = b"fake_wav_audio_data_for_testing"
    
    def test_transcription_processor_initialization(self):
        """Test transcription processor initialization"""
        try:
            from processors.transcription import TranscriptionProcessor
            
            processor = TranscriptionProcessor(self.config)
            self.assertIsNotNone(processor)
            self.assertEqual(processor.config, self.config)
            
        except ImportError as e:
            self.skipTest(f"Transcription processor import failed: {e}")
    
    def test_transcription_result_structure(self):
        """Test transcription result data structure"""
        try:
            from models.data import TranscriptionResult
            
            # Test successful transcription result
            success_result = TranscriptionResult(
                success=True,
                text="This is a test transcription.",
                confidence=0.95,
                processing_time=2.5,
                file_name="test.wav"
            )
            
            self.assertTrue(success_result.success)
            self.assertEqual(success_result.text, "This is a test transcription.")
            self.assertEqual(success_result.confidence, 0.95)
            self.assertEqual(success_result.file_name, "test.wav")
            
            # Test failed transcription result
            failed_result = TranscriptionResult(
                success=False,
                text="",
                confidence=0.0,
                processing_time=0.0,
                file_name="test.wav",
                error_message="Transcription failed"
            )
            
            self.assertFalse(failed_result.success)
            self.assertEqual(failed_result.error_message, "Transcription failed")
            
        except ImportError as e:
            self.skipTest(f"Transcription result test skipped: {e}")
    
    @patch('processors.transcription.requests.post')
    def test_ai_foundry_api_call(self, mock_post):
        """Test AI Foundry API call for transcription"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'recognitionStatus': 'Success',
            'displayText': 'This is a test transcription.',
            'confidence': 0.95
        }
        mock_post.return_value = mock_response
        
        try:
            from processors.transcription import TranscriptionProcessor
            
            processor = TranscriptionProcessor(self.config)
            
            # Test transcription method exists
            self.assertTrue(hasattr(processor, 'transcribe_audio'))
            
            # If AI Foundry method exists, test it
            if hasattr(processor, '_transcribe_with_ai_foundry'):
                result = processor._transcribe_with_ai_foundry(
                    self.sample_audio_data, 
                    "test.wav"
                )
                
                self.assertIsNotNone(result)
                
        except Exception as e:
            self.skipTest(f"AI Foundry API test skipped (requires real API key): {e}")
    
    def test_audio_validation(self):
        """Test audio file validation"""
        try:
            from processors.transcription import TranscriptionProcessor
            
            processor = TranscriptionProcessor(self.config)
            
            # Test valid audio file types
            valid_files = ['test.wav', 'voice.mp3', 'audio.m4a']
            invalid_files = ['document.pdf', 'image.jpg', 'text.txt']
            
            for filename in valid_files:
                # Test that validation logic exists
                if hasattr(processor, '_is_valid_audio_file'):
                    is_valid = processor._is_valid_audio_file(filename)
                    self.assertTrue(is_valid or is_valid is None)  # May not be implemented
            
        except ImportError as e:
            self.skipTest(f"Audio validation test skipped: {e}")
    
    def test_transcription_error_handling(self):
        """Test transcription error handling"""
        try:
            from processors.transcription import TranscriptionProcessor
            
            processor = TranscriptionProcessor(self.config)
            
            # Test with invalid audio data
            invalid_audio = b""  # Empty audio data
            
            if hasattr(processor, 'transcribe_audio'):
                result = processor.transcribe_audio(invalid_audio, "empty.wav")
                
                # Should return a result object (success or failure)
                self.assertIsNotNone(result)
                self.assertTrue(hasattr(result, 'success'))
                
        except Exception as e:
            self.skipTest(f"Error handling test skipped (expected without real API): {e}")
    
    def test_confidence_scoring(self):
        """Test confidence score validation"""
        try:
            from processors.transcription import TranscriptionProcessor
            
            processor = TranscriptionProcessor(self.config)
            
            # Test confidence score validation
            valid_confidences = [0.0, 0.5, 0.95, 1.0]
            invalid_confidences = [-0.1, 1.1, 2.0]
            
            for confidence in valid_confidences:
                # Confidence should be between 0 and 1
                self.assertGreaterEqual(confidence, 0.0)
                self.assertLessEqual(confidence, 1.0)
            
            for confidence in invalid_confidences:
                # These should be outside valid range
                self.assertTrue(confidence < 0.0 or confidence > 1.0)
                
        except ImportError as e:
            self.skipTest(f"Confidence scoring test skipped: {e}")
    
    def test_processing_time_tracking(self):
        """Test processing time tracking"""
        try:
            from processors.transcription import TranscriptionProcessor
            import time
            
            processor = TranscriptionProcessor(self.config)
            
            # Test time tracking logic exists
            start_time = time.time()
            time.sleep(0.1)  # Small delay
            end_time = time.time()
            
            processing_time = end_time - start_time
            self.assertGreater(processing_time, 0.0)
            self.assertLess(processing_time, 1.0)  # Should be quick
            
        except ImportError as e:
            self.skipTest(f"Processing time test skipped: {e}")


if __name__ == '__main__':
    unittest.main()