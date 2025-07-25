"""
Test suite for Excel Processor component
Tests Excel file operations, OneDrive integration, and data formatting
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.excel_processor_class import ExcelProcessor


class TestExcelProcessor(unittest.TestCase):
    """Test cases for ExcelProcessor component"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.excel_processor = ExcelProcessor("test_access_token", "Voice_Emails.xlsx")
        
        # Sample test data
        self.sample_structured_data = {
            'processed_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'received_date': '2024-01-15 10:30:00',
            'sender': 'test@example.com',
            'contact': '555-123-4567',
            'transcript': 'This is a test transcript from a voice message.',
            'ai_summary': 'Test caller requesting information about project status.',
            'confidence_score': '95.5%',
            'status': 'Processed',
            'attachment_name': 'voice_message.wav',
            'blob_url': 'https://test.blob.core.windows.net/voice-files/test.wav'
        }
        self.sample_voice_url = "https://test.blob.core.windows.net/voice-files/test.wav"
    
    def test_excel_processor_initialization(self):
        """Test Excel processor initialization"""
        self.assertIsNotNone(self.excel_processor)
        self.assertEqual(self.excel_processor.access_token, "test_access_token")
        self.assertEqual(self.excel_processor.excel_file_name, "Voice_Emails.xlsx")
    
    @patch('src.excel_processor_functions.update_excel_file_impl')
    def test_update_excel_file(self, mock_update_impl):
        """Test Excel file update with voicemail data"""
        # Mock the implementation
        mock_update_impl.return_value = True
        
        # Test the method
        result = self.excel_processor.update_excel_file(self.sample_structured_data, self.sample_voice_url)
        
        # Verify results
        self.assertTrue(result)
        mock_update_impl.assert_called_once_with(
            self.excel_processor, 
            self.sample_structured_data, 
            self.sample_voice_url
        )
    
    @patch('src.excel_processor_functions.find_excel_file_impl')
    def test_find_excel_file(self, mock_find_impl):
        """Test finding Excel file in OneDrive"""
        # Mock the implementation
        mock_find_impl.return_value = "test_file_id_12345"
        
        # Test the method
        file_id = self.excel_processor._find_excel_file()
        
        # Verify results
        self.assertEqual(file_id, "test_file_id_12345")
        mock_find_impl.assert_called_once_with(self.excel_processor)
    
    @patch('src.excel_processor_functions.setup_excel_worksheet_impl')
    def test_setup_excel_worksheet(self, mock_setup_impl):
        """Test Excel worksheet setup"""
        # Mock the implementation
        mock_setup_impl.return_value = None
        
        # Test the method
        workbook_url = "https://test.microsoft.com/workbook"
        headers = {"Authorization": "Bearer test_token"}
        
        self.excel_processor._setup_excel_worksheet(workbook_url, headers)
        
        # Verify setup was called
        mock_setup_impl.assert_called_once_with(self.excel_processor, workbook_url, headers)
    
    @patch('src.excel_processor_functions.find_next_column_impl')
    def test_find_next_column(self, mock_find_impl):
        """Test finding next available column"""
        # Mock the implementation
        mock_find_impl.return_value = 'C'
        
        # Test the method
        workbook_url = "https://test.microsoft.com/workbook"
        headers = {"Authorization": "Bearer test_token"}
        
        column = self.excel_processor._find_next_column(workbook_url, headers)
        
        # Verify results
        self.assertEqual(column, 'C')
        mock_find_impl.assert_called_once_with(self.excel_processor, workbook_url, headers)
    
    @patch('src.excel_processor_functions.shift_columns_right_impl')
    def test_shift_columns_right(self, mock_shift_impl):
        """Test shifting columns to make room for new data"""
        # Mock the implementation
        mock_shift_impl.return_value = None
        
        # Test the method
        workbook_url = "https://test.microsoft.com/workbook"
        headers = {"Authorization": "Bearer test_token"}
        rightmost_column = 'D'
        
        self.excel_processor._shift_columns_right(workbook_url, headers, rightmost_column)
        
        # Verify shift was called
        mock_shift_impl.assert_called_once_with(
            self.excel_processor, 
            workbook_url, 
            headers, 
            rightmost_column
        )
    
    @patch('src.excel_processor_functions.format_excel_column_impl')
    def test_format_excel_column(self, mock_format_impl):
        """Test Excel column formatting"""
        # Mock the implementation
        mock_format_impl.return_value = None
        
        # Test the method
        workbook_url = "https://test.microsoft.com/workbook"
        headers = {"Authorization": "Bearer test_token"}
        column_letter = 'B'
        
        self.excel_processor._format_excel_column(workbook_url, headers, column_letter, self.sample_voice_url)
        
        # Verify formatting was called
        mock_format_impl.assert_called_once_with(
            self.excel_processor, 
            workbook_url, 
            headers, 
            column_letter, 
            self.sample_voice_url
        )
    
    @patch('src.excel_processor_functions.create_enhanced_hyperlink_impl')
    def test_create_enhanced_hyperlink(self, mock_hyperlink_impl):
        """Test creating hyperlinks for audio files"""
        # Mock the implementation
        mock_hyperlink_impl.return_value = None
        
        # Test the method
        workbook_url = "https://test.microsoft.com/workbook"
        headers = {"Authorization": "Bearer test_token"}
        column_letter = 'B'
        
        self.excel_processor._create_enhanced_hyperlink(workbook_url, headers, column_letter, self.sample_voice_url)
        
        # Verify hyperlink creation was called
        mock_hyperlink_impl.assert_called_once_with(
            self.excel_processor, 
            workbook_url, 
            headers, 
            column_letter, 
            self.sample_voice_url
        )
    
    def test_method_delegation(self):
        """Test that all methods are properly delegated to implementation functions"""
        # Check that methods exist and are callable
        self.assertTrue(hasattr(self.excel_processor, 'update_excel_file'))
        self.assertTrue(callable(self.excel_processor.update_excel_file))
        
        self.assertTrue(hasattr(self.excel_processor, '_find_excel_file'))
        self.assertTrue(callable(self.excel_processor._find_excel_file))
        
        self.assertTrue(hasattr(self.excel_processor, '_setup_excel_worksheet'))
        self.assertTrue(callable(self.excel_processor._setup_excel_worksheet))
        
        self.assertTrue(hasattr(self.excel_processor, '_format_excel_column'))
        self.assertTrue(callable(self.excel_processor._format_excel_column))


class TestExcelProcessorErrorHandling(unittest.TestCase):
    """Test error handling in Excel Processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.excel_processor = ExcelProcessor("test_token", "test_file.xlsx")
    
    def test_invalid_access_token_handling(self):
        """Test handling of invalid access token"""
        with patch('src.excel_processor_functions.update_excel_file_impl') as mock_impl:
            mock_impl.return_value = False
            
            result = self.excel_processor.update_excel_file({}, "")
            self.assertFalse(result)
    
    def test_missing_excel_file_handling(self):
        """Test handling when Excel file is not found"""
        with patch('src.excel_processor_functions.find_excel_file_impl') as mock_impl:
            mock_impl.return_value = None
            
            file_id = self.excel_processor._find_excel_file()
            self.assertIsNone(file_id)
    
    def test_invalid_structured_data_handling(self):
        """Test handling of invalid structured data"""
        with patch('src.excel_processor_functions.update_excel_file_impl') as mock_impl:
            mock_impl.return_value = False
            
            # Test with empty data
            result = self.excel_processor.update_excel_file({}, "test_url")
            self.assertFalse(result)


class TestExcelProcessorIntegration(unittest.TestCase):
    """Integration tests for Excel Processor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.excel_processor = ExcelProcessor("test_token", "Voice_Emails.xlsx")
        self.complete_data = {
            'processed_date': '2024-01-15 14:30:00',
            'received_date': '2024-01-15 10:30:00',
            'sender': 'john.doe@example.com',
            'contact': '555-987-6543',
            'transcript': 'Hello, this is John calling about the quarterly report. I need to schedule a meeting to discuss the new projections. Please call me back at your earliest convenience.',
            'ai_summary': 'John Doe called requesting a meeting to discuss quarterly report and new projections. Requires callback to schedule.',
            'confidence_score': '92.3%',
            'status': 'Processed',
            'attachment_name': 'quarterly_report_call.wav'
        }
    
    @patch('src.excel_processor_functions.update_excel_file_impl')
    @patch('src.excel_processor_functions.find_excel_file_impl')
    @patch('src.excel_processor_functions.setup_excel_worksheet_impl')
    def test_complete_excel_workflow(self, mock_setup, mock_find, mock_update):
        """Test the complete Excel processing workflow"""
        # Mock successful operations
        mock_find.return_value = "file_id_12345"
        mock_setup.return_value = None
        mock_update.return_value = True
        
        # Test the complete workflow
        voice_url = "https://test.blob.core.windows.net/voice-files/quarterly_report_call.wav"
        result = self.excel_processor.update_excel_file(self.complete_data, voice_url)
        
        # Verify the result
        self.assertTrue(result)
        mock_update.assert_called_once()


if __name__ == '__main__':
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestExcelProcessor))
    test_suite.addTest(unittest.makeSuite(TestExcelProcessorErrorHandling))
    test_suite.addTest(unittest.makeSuite(TestExcelProcessorIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Excel Processor Tests Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
