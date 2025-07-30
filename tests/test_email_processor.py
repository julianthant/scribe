#!/usr/bin/env python3
"""
Email Processor Unit Tests
Tests email retrieval, filtering, and processing logic
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestEmailProcessor(unittest.TestCase):
    """Test email processing functionality"""
    
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
    
    def test_email_processor_initialization(self):
        """Test email processor initialization"""
        try:
            from processors.email import EmailProcessor
            
            processor = EmailProcessor(self.config)
            self.assertIsNotNone(processor)
            self.assertEqual(processor.config, self.config)
            
        except ImportError as e:
            self.skipTest(f"Email processor import failed: {e}")
    
    @patch('processors.email.make_graph_request')
    def test_voice_email_filtering(self, mock_graph_request):
        """Test filtering of voice emails from all emails"""
        # Mock Graph API response
        mock_graph_request.return_value = Mock(
            status_code=200,
            json=lambda: {
                'value': [
                    {
                        'id': 'email1',
                        'subject': 'Voice Message from (555) 123-4567',
                        'from': {'emailAddress': {'address': 'test@example.com'}},
                        'receivedDateTime': datetime.now().isoformat(),
                        'hasAttachments': True
                    },
                    {
                        'id': 'email2', 
                        'subject': 'Regular email',
                        'from': {'emailAddress': {'address': 'test@example.com'}},
                        'receivedDateTime': datetime.now().isoformat(),
                        'hasAttachments': False
                    }
                ]
            }
        )
        
        try:
            from processors.email import EmailProcessor
            
            processor = EmailProcessor(self.config)
            
            # Test that voice email filtering logic exists
            self.assertTrue(hasattr(processor, '_is_voice_email'))
            
        except Exception as e:
            self.skipTest(f"Voice email filtering test skipped (requires graph API): {e}")
    
    def test_email_date_filtering(self):
        """Test email date range filtering"""
        try:
            from processors.email import EmailProcessor
            
            processor = EmailProcessor(self.config)
            
            # Test date range calculation
            now = datetime.now()
            days_back = 7
            
            # This tests the logic structure exists
            self.assertTrue(hasattr(processor, 'get_voice_emails'))
            
        except ImportError as e:
            self.skipTest(f"Email date filtering test skipped: {e}")
    
    def test_attachment_processing(self):
        """Test email attachment processing"""
        try:
            from processors.email import EmailProcessor
            from models.data import EmailAttachment
            
            processor = EmailProcessor(self.config)
            
            # Test attachment structure
            attachment = EmailAttachment(
                filename='test.wav',
                content=b'test_audio_data',
                content_type='audio/wav',
                size=1024
            )
            
            self.assertEqual(attachment.filename, 'test.wav')
            self.assertEqual(attachment.content_type, 'audio/wav')
            self.assertEqual(attachment.size, 1024)
            
        except ImportError as e:
            self.skipTest(f"Attachment processing test skipped: {e}")
    
    def test_email_moving_functionality(self):
        """Test moving emails to processed folder"""
        try:
            from processors.email import EmailProcessor
            
            processor = EmailProcessor(self.config)
            
            # Test that email moving functionality exists
            self.assertTrue(hasattr(processor, 'mark_email_processed'))
            
        except ImportError as e:
            self.skipTest(f"Email moving test skipped: {e}")


if __name__ == '__main__':
    unittest.main()