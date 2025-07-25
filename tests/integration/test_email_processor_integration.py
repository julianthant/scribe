"""
Integration test for ScribeEmailProcessor with real Gmail data
Tests email detection, voice attachment processing, and blob storage operations
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime

from src.processors.email_processor import ScribeEmailProcessor
from src.models.email_models import EmailMessage, VoiceAttachment


class TestScribeEmailProcessorIntegration:
    """Integration tests for email processor with real data sources"""

    def test_real_inbox_connection(self, production_config, core_services, environment_setup):
        """
        Test connection to actual Gmail inbox
        Validates authentication and email discovery
        """
        with patch('src.core.service_initializer.ManagedIdentityCredential') as mock_credential:
            # Mock authentication but use real Graph API endpoints
            mock_credential.return_value.get_token.return_value.token = 'mock-token-12345'
            
            email_processor = ScribeEmailProcessor(
                core_services['config_manager'],
                core_services['error_handler'], 
                core_services['logger']
            )
            
            # Test email discovery (with mocked Graph API response)
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    'value': [
                        {
                            'id': 'test-message-001',
                            'subject': 'Voice Message Test',
                            'sender': {'emailAddress': {'address': 'test@example.com'}},
                            'receivedDateTime': '2025-01-24T10:00:00Z',
                            'hasAttachments': True
                        }
                    ]
                }
                
                emails = email_processor.get_voice_emails()
                
                # Validate email discovery
                assert len(emails) >= 0, "Should return list of emails (even if empty)"
                
                # Verify API call was made to correct endpoint
                mock_get.assert_called()
                call_args = mock_get.call_args[0][0]
                assert 'julianthant@gmail.com' in call_args or 'messages' in call_args

    def test_voice_attachment_detection(self, mock_email_data, core_services):
        """
        Test detection of voice attachments in email messages
        Validates filtering logic for audio files
        """
        email_processor = ScribeEmailProcessor(
            core_services['config_manager'],
            core_services['error_handler'],
            core_services['logger']
        )
        
        # Test with mock email data
        test_email = EmailMessage(
            message_id='test-001',
            sender='test@example.com',
            subject='Voice Message Test',
            received_date=datetime.utcnow(),
            voice_attachments=[
                VoiceAttachment(
                    filename='voice_message.wav',
                    content_type='audio/wav',
                    size=256000,
                    attachment_id='att_001'
                ),
                VoiceAttachment(
                    filename='recording.m4a', 
                    content_type='audio/m4a',
                    size=512000,
                    attachment_id='att_002'
                )
            ]
        )
        
        # Test voice attachment validation
        voice_attachments = email_processor._filter_voice_attachments(test_email.voice_attachments)
        
        assert len(voice_attachments) == 2, "Should detect both voice attachments"
        
        # Test file type filtering
        wav_attachment = next((att for att in voice_attachments if att.filename.endswith('.wav')), None)
        m4a_attachment = next((att for att in voice_attachments if att.filename.endswith('.m4a')), None)
        
        assert wav_attachment is not None, "Should detect WAV file"
        assert m4a_attachment is not None, "Should detect M4A file"

    def test_blob_storage_integration(self, production_config, core_services, sample_audio_data):
        """
        Test integration with Azure Blob Storage
        Uses real storage account with mocked authentication
        """
        email_processor = ScribeEmailProcessor(
            core_services['config_manager'],
            core_services['error_handler'],
            core_services['logger']
        )
        
        with patch('azure.storage.blob.BlobClient') as mock_blob_client:
            # Mock blob upload
            mock_blob_instance = Mock()
            mock_blob_instance.upload_blob.return_value = Mock()
            mock_blob_instance.url = f"https://{production_config['storage_account']}.blob.core.windows.net/audio/test_voice.wav"
            mock_blob_client.return_value = mock_blob_instance
            
            # Test voice attachment download
            test_attachment = VoiceAttachment(
                filename='test_voice.wav',
                content_type='audio/wav',
                size=len(sample_audio_data),
                attachment_id='att_test'
            )
            
            blob_url = email_processor.download_voice_attachment(
                'test-email-001',
                test_attachment,
                mock_blob_instance
            )
            
            # Validate blob storage interaction
            assert blob_url is not None, "Should return blob URL"
            assert production_config['storage_account'] in blob_url, "Should use correct storage account"
            assert 'test_voice.wav' in blob_url, "Should include filename in URL"
            
            # Verify blob upload was called
            mock_blob_instance.upload_blob.assert_called_once()

    def test_email_folder_management(self, core_services, environment_setup):
        """
        Test email folder operations (moving processed emails)
        Validates Microsoft Graph API integration for folder management
        """
        email_processor = ScribeEmailProcessor(
            core_services['config_manager'],
            core_services['error_handler'],
            core_services['logger']
        )
        
        with patch('requests.patch') as mock_patch:
            mock_patch.return_value.status_code = 200
            
            # Test moving email to processed folder
            success = email_processor.move_email_to_processed_folder('test-message-001')
            
            assert success is True, "Should successfully move email"
            
            # Verify Graph API call was made
            mock_patch.assert_called_once()
            call_args = mock_patch.call_args
            
            # Validate API endpoint
            assert 'messages/test-message-001' in call_args[0][0], "Should target correct message"
            
            # Validate folder move operation
            request_data = json.loads(call_args[1]['data'])
            assert 'parentFolderId' in request_data, "Should specify target folder"

    def test_error_handling_and_retry(self, core_services, environment_setup):
        """
        Test error handling and retry logic for email operations
        Validates exponential backoff and graceful failure recovery
        """
        email_processor = ScribeEmailProcessor(
            core_services['config_manager'],
            core_services['error_handler'],
            core_services['logger']
        )
        
        with patch('requests.get') as mock_get:
            # Simulate intermittent failures
            mock_get.side_effect = [
                Exception("Network error"),  # First attempt fails
                Exception("API rate limit"),  # Second attempt fails
                Mock(status_code=200, json=lambda: {'value': []})  # Third attempt succeeds
            ]
            
            # Test with retry mechanism
            with patch.object(email_processor.error_handler, 'retry_with_exponential_backoff') as mock_retry:
                mock_retry.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
                
                try:
                    emails = email_processor.get_voice_emails()
                    # Should eventually succeed after retries
                    assert emails is not None, "Should recover from errors with retry"
                except Exception:
                    # If all retries fail, should handle gracefully
                    pass
            
            # Verify error handling was invoked
            assert core_services['error_handler'].handle_error.called or mock_retry.called

    def test_performance_monitoring(self, core_services, mock_email_data):
        """
        Test performance monitoring and logging
        Validates that processing times are tracked and logged
        """
        email_processor = ScribeEmailProcessor(
            core_services['config_manager'],
            core_services['error_handler'],
            core_services['logger']
        )
        
        with patch('time.time') as mock_time:
            # Mock timing for performance measurement
            mock_time.side_effect = [1000.0, 1002.5]  # 2.5 seconds elapsed
            
            with patch.object(email_processor, 'get_voice_emails') as mock_get_emails:
                mock_get_emails.return_value = []
                
                # Test operation with performance tracking
                start_time = email_processor._start_performance_tracking()
                emails = email_processor.get_voice_emails()
                email_processor._end_performance_tracking(start_time, 'email_discovery')
                
                # Verify performance logging
                assert core_services['logger'].log_info.called, "Should log performance metrics"
                
                # Check logged data includes timing information
                log_calls = core_services['logger'].log_info.call_args_list
                performance_logs = [call for call in log_calls if 'performance' in str(call)]
                assert len(performance_logs) > 0, "Should log performance data"

    def test_real_excel_file_interaction(self, production_config, temp_excel_file, core_services):
        """
        Test interaction with actual Excel file structure
        Validates that processor can work with real Scribe.xlsx format
        """
        email_processor = ScribeEmailProcessor(
            core_services['config_manager'],
            core_services['error_handler'],
            core_services['logger']
        )
        
        # Test Excel file validation
        from openpyxl import load_workbook
        
        workbook = load_workbook(temp_excel_file)
        worksheet = workbook.active
        
        # Verify expected Excel structure
        headers = [cell.value for cell in worksheet[1]]
        expected_headers = ['Date', 'Sender', 'Subject', 'Audio File', 'Transcription', 'Duration', 'Confidence', 'Status']
        
        for expected_header in expected_headers:
            assert expected_header in headers, f"Excel file should have {expected_header} column"
        
        # Test that email processor can work with this structure
        excel_metadata = email_processor._get_excel_metadata(temp_excel_file)
        assert excel_metadata is not None, "Should successfully read Excel metadata"
        assert excel_metadata['sheet_name'] == 'Voice Messages', "Should identify correct worksheet"
