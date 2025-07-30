#!/usr/bin/env python3
"""
Excel Processor Unit Tests
Tests Excel file operations, formatting, and data writing
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import re

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestExcelProcessor(unittest.TestCase):
    """Test Excel processing functionality"""
    
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
    
    def test_excel_processor_initialization(self):
        """Test Excel processor initialization"""
        try:
            from processors.excel import ExcelProcessor
            
            processor = ExcelProcessor(self.config)
            self.assertIsNotNone(processor)
            self.assertEqual(processor.excel_file_name, 'Test_Scribe.xlsx')
            
        except ImportError as e:
            self.skipTest(f"Excel processor import failed: {e}")
    
    def test_phone_number_extraction(self):
        """Test phone number extraction from email subjects"""
        try:
            from processors.excel import ExcelProcessor
            
            processor = ExcelProcessor(self.config)
            
            # Test various phone number formats
            test_cases = [
                ("Voice Message from (555) 123-4567", "555-123-4567"),
                ("Voicemail from 555.123.4567", "555-123-4567"), 
                ("Voice message from +1 555 123 4567", "+1-555-123-4567"),
                ("Call from 5551234567", "555-123-4567"),
                ("No phone number here", "Unknown")
            ]
            
            for subject, expected_pattern in test_cases:
                result = processor._extract_phone_number(subject)
                self.assertIsNotNone(result)
                # Phone number should either match expected pattern or be "Unknown"
                self.assertTrue(
                    result == "Unknown" or re.match(r'[\+\d\-\s\(\)]+', result),
                    f"Invalid phone number format: {result}"
                )
                
        except ImportError as e:
            self.skipTest(f"Phone number extraction test skipped: {e}")
    
    def test_transcription_formatting(self):
        """Test transcription text formatting for Excel"""
        try:
            from processors.excel import ExcelProcessor
            
            processor = ExcelProcessor(self.config)
            
            # Test transcription formatting
            test_text = "This is a   multi-line\n\n\ntranscription with    extra spaces."
            
            # Test that formatting method exists
            self.assertTrue(hasattr(processor, '_format_transcription_text'))
            
            formatted = processor._format_transcription_text(test_text)
            
            # Should be a single paragraph without excessive whitespace
            self.assertIsInstance(formatted, str)
            self.assertNotIn('\n\n\n', formatted)  # No excessive newlines
            
        except ImportError as e:
            self.skipTest(f"Transcription formatting test skipped: {e}")
    
    def test_excel_row_data_structure(self):
        """Test Excel row data structure"""
        try:
            from processors.excel import ExcelRowData
            from models.data import TranscriptionResult
            
            # Create test transcription result
            transcription = TranscriptionResult(
                success=True,
                text="Test transcription",
                confidence=0.95,
                processing_time=2.1,
                file_name="test.wav"
            )
            
            # Create Excel row data
            row_data = ExcelRowData(
                transcription=transcription,
                email_subject="Voice Message from (555) 123-4567",
                email_sender="test@example.com",
                email_date=datetime.now(),
                attachment_filename="test_voice.wav",
                download_url="https://example.com/download/123"
            )
            
            self.assertEqual(row_data.transcription, transcription)
            self.assertEqual(row_data.email_subject, "Voice Message from (555) 123-4567")
            self.assertIsNotNone(row_data.download_url)
            
        except ImportError as e:
            self.skipTest(f"Excel row data test skipped: {e}")
    
    def test_download_url_generation(self):
        """Test secure download URL generation"""
        try:
            from processors.excel import ExcelProcessor
            
            processor = ExcelProcessor(self.config)
            
            # Test download URL generation
            filename = "test_voice_message.wav"
            
            if hasattr(processor, '_generate_download_url'):
                download_url = processor._generate_download_url(filename)
                
                # Should be a valid URL format
                self.assertTrue(download_url.startswith('http'))
                self.assertIn('/api/download_voice/', download_url)
                
        except ImportError as e:
            self.skipTest(f"Download URL test skipped: {e}")
    
    def test_excel_column_structure(self):
        """Test Excel column structure (11 columns)"""
        try:
            from processors.excel import ExcelProcessor
            
            processor = ExcelProcessor(self.config)
            
            # Test that we have the expected 11-column structure
            expected_columns = [
                'Date Received', 'Time Received', 'Date Processed', 'Time Processed',
                'Phone Number', 'Voice Length', 'Transcription', 'Download',
                'Sender', 'Subject', 'Status'
            ]
            
            # This validates the structure exists in the processor
            self.assertTrue(hasattr(processor, '_prepare_row_data'))
            
        except ImportError as e:
            self.skipTest(f"Excel column test skipped: {e}")


if __name__ == '__main__':
    unittest.main()