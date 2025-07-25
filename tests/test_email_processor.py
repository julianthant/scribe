"""
Test suite for Email Processor component
Tests email management, attachment processing, and folder operations
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.email_processor_class import EmailProcessor


class TestEmailProcessor(unittest.TestCase):
    """Test cases for EmailProcessor component"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_blob_client = Mock()
        self.email_processor = EmailProcessor("test_access_token", self.mock_blob_client, "test@example.com")
        
        # Sample test data
        self.sample_email = {
            'id': 'email_123',
            'subject': 'Voice message from John - 555-123-4567',
            'receivedDateTime': '2024-01-15T10:30:00Z',
            'from': {
                'emailAddress': {
                    'address': 'john.doe@example.com'
                }
            },
            'voice_attachments': [{
                'id': 'attachment_456',
                'name': 'voice_message.wav',
                'size': 1024000
            }]
        }
        
        self.sample_attachment = {
            'id': 'attachment_456',
            'name': 'voice_message.wav',
            'size': 1024000
        }
    
    def test_email_processor_initialization(self):
        """Test email processor initialization"""
        self.assertIsNotNone(self.email_processor)
        self.assertEqual(self.email_processor.access_token, "test_access_token")
        self.assertEqual(self.email_processor.blob_client, self.mock_blob_client)
        self.assertEqual(self.email_processor.target_user_email, "test@example.com")
    
    @patch('src.email_processor_functions.process_emails_impl')
    def test_process_emails(self, mock_process_impl):
        """Test main email processing function"""
        # Mock the implementation
        mock_process_impl.return_value = None
        
        # Test the method
        self.email_processor.process_emails()
        
        # Verify process was called
        mock_process_impl.assert_called_once_with(self.email_processor)
    
    @patch('src.email_processor_functions.get_emails_with_voice_attachments_impl')
    def test_get_emails_with_voice_attachments(self, mock_get_impl):
        """Test getting emails with voice attachments"""
        # Mock the implementation
        mock_get_impl.return_value = [self.sample_email]
        
        # Test the method
        emails = self.email_processor._get_emails_with_voice_attachments()
        
        # Verify results
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]['id'], 'email_123')
        mock_get_impl.assert_called_once_with(self.email_processor)
    
    @patch('src.email_processor_functions.is_voice_attachment_impl')
    def test_is_voice_attachment(self, mock_is_voice_impl):
        """Test voice attachment detection"""
        # Mock the implementation
        mock_is_voice_impl.return_value = True
        
        # Test the method
        is_voice = self.email_processor._is_voice_attachment(self.sample_attachment)
        
        # Verify results
        self.assertTrue(is_voice)
        mock_is_voice_impl.assert_called_once_with(self.email_processor, self.sample_attachment)
    
    @patch('src.email_processor_functions.process_single_email_impl')
    def test_process_single_email(self, mock_process_impl):
        """Test processing a single email"""
        # Mock the implementation
        mock_process_impl.return_value = True
        
        # Test the method
        result = self.email_processor._process_single_email(self.sample_email)
        
        # Verify results
        self.assertTrue(result)
        mock_process_impl.assert_called_once_with(self.email_processor, self.sample_email)
    
    @patch('src.email_processor_functions.download_attachment_to_blob_impl')
    def test_download_attachment_to_blob(self, mock_download_impl):
        """Test downloading attachment to blob storage"""
        # Mock the implementation
        expected_blob_url = "https://test.blob.core.windows.net/voice-files/email_123_attachment_456_voice_message.wav"
        mock_download_impl.return_value = expected_blob_url
        
        # Test the method
        blob_url = self.email_processor._download_attachment_to_blob('email_123', self.sample_attachment)
        
        # Verify results
        self.assertEqual(blob_url, expected_blob_url)
        mock_download_impl.assert_called_once_with(self.email_processor, 'email_123', self.sample_attachment)
    
    @patch('src.email_processor_functions.extract_structured_data_impl')
    def test_extract_structured_data(self, mock_extract_impl):
        """Test extracting structured data from email and transcript"""
        # Mock the implementation
        expected_data = {
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'received_date': '2024-01-15 10:30:00',
            'sender': 'john.doe@example.com',
            'subject': 'Voice message from John - 555-123-4567',
            'transcript': 'This is a test transcript',
            'ai_summary': 'John called requesting information',
            'contact': '555-123-4567',
            'confidence_score': '95.0%',
            'status': 'Processed'
        }
        mock_extract_impl.return_value = expected_data
        
        # Test the method
        transcript = "This is a test transcript"
        blob_url = "https://test.blob.core.windows.net/test.wav"
        
        structured_data = self.email_processor._extract_structured_data(
            transcript, self.sample_email, self.sample_attachment, blob_url
        )
        
        # Verify results
        self.assertIsInstance(structured_data, dict)
        self.assertEqual(structured_data['sender'], 'john.doe@example.com')
        self.assertEqual(structured_data['transcript'], 'This is a test transcript')
        mock_extract_impl.assert_called_once()
    
    @patch('src.email_processor_functions.move_email_to_processed_folder_impl')
    def test_move_email_to_processed_folder(self, mock_move_impl):
        """Test moving email to processed folder"""
        # Mock the implementation
        mock_move_impl.return_value = True
        
        # Test the method
        result = self.email_processor._move_email_to_processed_folder('email_123')
        
        # Verify results
        self.assertTrue(result)
        mock_move_impl.assert_called_once_with(self.email_processor, 'email_123')
    
    @patch('src.email_processor_functions.get_or_create_processed_folder_impl')
    def test_get_or_create_processed_folder(self, mock_folder_impl):
        """Test getting or creating processed folder"""
        # Mock the implementation
        mock_folder_impl.return_value = "folder_id_789"
        
        # Test the method
        folder_id = self.email_processor._get_or_create_processed_folder()
        
        # Verify results
        self.assertEqual(folder_id, "folder_id_789")
        mock_folder_impl.assert_called_once_with(self.email_processor)
    
    @patch('src.email_processor_functions.cleanup_blob_impl')
    def test_cleanup_blob(self, mock_cleanup_impl):
        """Test blob cleanup"""
        # Mock the implementation
        mock_cleanup_impl.return_value = None
        
        # Test the method
        blob_url = "https://test.blob.core.windows.net/voice-files/test.wav"
        self.email_processor._cleanup_blob(blob_url)
        
        # Verify cleanup was called
        mock_cleanup_impl.assert_called_once_with(self.email_processor, blob_url)
    
    def test_method_delegation(self):
        """Test that all methods are properly delegated to implementation functions"""
        # Check that methods exist and are callable
        self.assertTrue(hasattr(self.email_processor, 'process_emails'))
        self.assertTrue(callable(self.email_processor.process_emails))
        
        self.assertTrue(hasattr(self.email_processor, '_get_emails_with_voice_attachments'))
        self.assertTrue(callable(self.email_processor._get_emails_with_voice_attachments))
        
        self.assertTrue(hasattr(self.email_processor, '_process_single_email'))
        self.assertTrue(callable(self.email_processor._process_single_email))
        
        self.assertTrue(hasattr(self.email_processor, '_download_attachment_to_blob'))
        self.assertTrue(callable(self.email_processor._download_attachment_to_blob))


class TestEmailProcessorErrorHandling(unittest.TestCase):
    """Test error handling in Email Processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_blob_client = Mock()
        self.email_processor = EmailProcessor("test_token", self.mock_blob_client, "test@example.com")
    
    def test_invalid_access_token_handling(self):
        """Test handling of invalid access token"""
        with patch('src.email_processor_functions.get_emails_with_voice_attachments_impl') as mock_impl:
            mock_impl.return_value = []
            
            emails = self.email_processor._get_emails_with_voice_attachments()
            self.assertEqual(len(emails), 0)
    
    def test_no_voice_attachments_handling(self):
        """Test handling when no voice attachments are found"""
        with patch('src.email_processor_functions.is_voice_attachment_impl') as mock_impl:
            mock_impl.return_value = False
            
            attachment = {'name': 'document.pdf'}
            is_voice = self.email_processor._is_voice_attachment(attachment)
            self.assertFalse(is_voice)
    
    def test_blob_download_failure_handling(self):
        """Test handling of blob download failures"""
        with patch('src.email_processor_functions.download_attachment_to_blob_impl') as mock_impl:
            mock_impl.return_value = None
            
            blob_url = self.email_processor._download_attachment_to_blob('email_123', {'id': 'att_456'})
            self.assertIsNone(blob_url)
    
    def test_folder_creation_failure_handling(self):
        """Test handling when folder creation fails"""
        with patch('src.email_processor_functions.get_or_create_processed_folder_impl') as mock_impl:
            mock_impl.return_value = None
            
            folder_id = self.email_processor._get_or_create_processed_folder()
            self.assertIsNone(folder_id)


class TestEmailProcessorIntegration(unittest.TestCase):
    """Integration tests for Email Processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_blob_client = Mock()
        self.email_processor = EmailProcessor("test_token", self.mock_blob_client, "test@example.com")
    
    @patch('src.email_processor_functions.process_emails_impl')
    @patch('src.email_processor_functions.get_emails_with_voice_attachments_impl')
    @patch('src.email_processor_functions.process_single_email_impl')
    def test_complete_email_processing_workflow(self, mock_single, mock_get, mock_process):
        """Test the complete email processing workflow"""
        # Mock successful operations
        sample_emails = [
            {
                'id': 'email_123',
                'subject': 'Voice message from client',
                'voice_attachments': [{'name': 'message.wav'}]
            }
        ]
        
        mock_get.return_value = sample_emails
        mock_single.return_value = True
        mock_process.return_value = None
        
        # Test the complete workflow
        self.email_processor.process_emails()
        
        # Verify the workflow was executed
        mock_process.assert_called_once()


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestEmailProcessor))
    test_suite.addTest(unittest.makeSuite(TestEmailProcessorErrorHandling))
    test_suite.addTest(unittest.makeSuite(TestEmailProcessorIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Email Processor Tests Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
