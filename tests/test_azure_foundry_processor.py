"""
Test Azure Foundry Audio Processor
"""

import unittest
import logging
import os
import sys

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from azure_foundry_processor_functions import (
    create_foundry_audio_processor,
    test_foundry_transcription,
    validate_audio_file,
    get_audio_file_info,
    format_transcription_result
)


class TestAzureFoundryProcessor(unittest.TestCase):
    """Test cases for Azure Foundry Audio Processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.speech_key = "7e4c2a0696114bf0939646fc49e46094"
        self.speech_region = "eastus"
        self.foundry_endpoint = "https://ai-julianthant562797747914.cognitiveservices.azure.com"
        self.test_audio_file = "/Users/julianhein/Work/Personal-Projects/scribe/VoiceMessage (4).wav"
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
    
    def test_create_processor(self):
        """Test creating Azure Foundry processor"""
        processor = create_foundry_audio_processor(
            speech_key=self.speech_key,
            speech_region=self.speech_region,
            foundry_endpoint=self.foundry_endpoint
        )
        
        self.assertIsNotNone(processor)
        self.assertEqual(processor.speech_key, self.speech_key)
        self.assertEqual(processor.speech_region, self.speech_region)
    
    def test_validate_audio_file(self):
        """Test audio file validation"""
        # Test existing file
        if os.path.exists(self.test_audio_file):
            is_valid, message = validate_audio_file(self.test_audio_file)
            self.assertTrue(is_valid, f"Audio file should be valid: {message}")
        
        # Test non-existent file
        is_valid, message = validate_audio_file("/nonexistent/file.wav")
        self.assertFalse(is_valid)
        self.assertIn("does not exist", message)
    
    def test_get_audio_file_info(self):
        """Test getting audio file information"""
        if os.path.exists(self.test_audio_file):
            info = get_audio_file_info(self.test_audio_file)
            
            self.assertIn('path', info)
            self.assertIn('size_bytes', info)
            self.assertIn('duration_seconds', info)
            self.assertIn('format', info)
            
            self.assertEqual(info['path'], self.test_audio_file)
            self.assertGreater(info['size_bytes'], 0)
    
    def test_format_transcription_result(self):
        """Test transcription result formatting"""
        # Test with metadata
        transcription_with_metadata = "Hello world [Azure Fast Transcription: 5.5x speed, 61.3s]"
        formatted = format_transcription_result(transcription_with_metadata, include_metadata=True)
        self.assertIn("Text: Hello world", formatted)
        self.assertIn("Metadata:", formatted)
        
        # Test without metadata
        formatted_no_meta = format_transcription_result(transcription_with_metadata, include_metadata=False)
        self.assertEqual(formatted_no_meta, "Hello world")
        
        # Test simple text
        simple_text = "Hello world"
        formatted_simple = format_transcription_result(simple_text)
        self.assertEqual(formatted_simple, "Hello world")
    
    def test_transcription_integration(self):
        """Integration test for transcription (requires valid audio file)"""
        if os.path.exists(self.test_audio_file):
            try:
                result = test_foundry_transcription(
                    self.test_audio_file,
                    self.speech_key,
                    self.speech_region,
                    self.foundry_endpoint
                )
                
                self.assertIsNotNone(result)
                self.assertNotEqual(result, "")
                self.assertNotIn("failed", result.lower())
                
                print(f"\nTranscription result: {result}")
                
            except Exception as e:
                self.fail(f"Transcription test failed: {e}")
        else:
            self.skipTest(f"Test audio file not found: {self.test_audio_file}")


if __name__ == '__main__':
    unittest.main()
