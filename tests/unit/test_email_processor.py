"""
Unit tests for Email Processor
Tests email fetching, attachment processing, and centralized services integration
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from src.processors.email_processor import ScribeEmailProcessor
from src.models.email_models import EmailMessage, VoiceAttachment


class TestScribeEmailProcessor:
    """Test suite for ScribeEmailProcessor"""
    
    def setup_method(self):
        """Setup test environment"""
        # Mock dependencies
        self.mock_config = Mock()
        self.mock_error_handler = Mock()
        self.mock_logger = Mock()
        
        # Create processor instance
        self.processor = ScribeEmailProcessor(
            self.mock_config,
            self.mock_error_handler,
            self.mock_logger
        )
    
    def test_processor_initialization(self):
        """Test processor initializes correctly"""
        assert self.processor.config == self.mock_config
        assert self.processor.error_handler == self.mock_error_handler
        assert self.processor.logger == self.mock_logger
        assert self.processor.auth_manager is None
        assert self.processor.target_user_email is None
    
    @patch('src.processors.email_processor.get_auth_manager')
    @patch('src.processors.email_processor.validate_email_address')
    def test_initialize_success(self, mock_validate_email, mock_get_auth_manager):
        """Test successful processor initialization"""
        # Mock dependencies
        mock_validate_email.return_value = True
        mock_auth_manager = Mock()
        mock_get_auth_manager.return_value = mock_auth_manager
        
        # Initialize processor
        result = self.processor.initialize("test@example.com")
        
        # Verify initialization
        assert result is True
        assert self.processor.target_user_email == "test@example.com"
        assert self.processor.auth_manager == mock_auth_manager
        
        # Verify logger was called
        self.mock_logger.log_info.assert_called_once()
    
    @patch('src.processors.email_processor.get_auth_manager')
    @patch('src.processors.email_processor.validate_email_address')
    def test_initialize_invalid_email(self, mock_validate_email, mock_get_auth_manager):
        """Test initialization with invalid email"""
        # Mock invalid email
        mock_validate_email.return_value = False
        
        # Initialize processor
        result = self.processor.initialize("invalid-email")
        
        # Verify initialization failed
        assert result is False
        self.mock_error_handler.handle_error.assert_called_once()
    
    @patch('src.processors.email_processor.get_auth_manager')
    @patch('src.processors.email_processor.validate_email_address')
    def test_initialize_auth_manager_error(self, mock_validate_email, mock_get_auth_manager):
        """Test initialization when auth manager fails"""
        # Mock email validation success but auth manager failure
        mock_validate_email.return_value = True
        mock_get_auth_manager.side_effect = Exception("Auth error")
        
        # Initialize processor
        result = self.processor.initialize("test@example.com")
        
        # Verify initialization failed
        assert result is False
        self.mock_error_handler.handle_error.assert_called_once()
    
    def test_get_request_headers(self):
        """Test request headers generation"""
        # Mock auth manager
        mock_auth_manager = Mock()
        mock_auth_manager.get_auth_headers.return_value = {
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json'
        }
        self.processor.auth_manager = mock_auth_manager
        
        # Get headers
        headers = self.processor._get_request_headers()
        
        # Verify headers
        mock_auth_manager.get_auth_headers.assert_called_once_with('graph')
        assert headers['Authorization'] == 'Bearer test-token'
        assert headers['Content-Type'] == 'application/json'
    
    @patch('src.processors.email_processor.make_authenticated_request')
    @patch('src.processors.email_processor.retry_with_exponential_backoff')
    def test_fetch_inbox_emails_with_attachments(self, mock_retry, mock_request):
        """Test fetching emails with attachments"""
        # Mock response data
        mock_response = Mock()
        mock_response.json.return_value = {
            'value': [
                {
                    'id': 'email1',
                    'subject': 'Voice Message',
                    'receivedDateTime': '2025-07-24T10:00:00Z',
                    'from': {'emailAddress': {'address': 'sender@example.com'}},
                    'attachments': [
                        {'name': 'voice.mp3', 'contentType': 'audio/mpeg'}
                    ]
                }
            ]
        }
        mock_request.return_value = mock_response
        mock_retry.return_value = [
            {
                'id': 'email1',
                'subject': 'Voice Message',
                'receivedDateTime': '2025-07-24T10:00:00Z',
                'from': {'emailAddress': {'address': 'sender@example.com'}},
                'attachments': [
                    {'name': 'voice.mp3', 'contentType': 'audio/mpeg'}
                ]
            }
        ]
        
        # Initialize processor
        self.processor.auth_manager = Mock()
        
        # Fetch emails
        result = self.processor._fetch_inbox_emails_with_attachments(7, 50)
        
        # Verify result
        assert len(result) == 1
        assert result[0]['id'] == 'email1'
        assert result[0]['subject'] == 'Voice Message'
        
        # Verify retry was called
        mock_retry.assert_called_once()
    
    @patch('src.processors.email_processor.make_authenticated_request')
    @patch('src.processors.email_processor.retry_with_exponential_backoff')
    def test_download_attachment_content(self, mock_retry, mock_request):
        """Test downloading attachment content"""
        # Mock attachment list response
        attachments_response = Mock()
        attachments_response.json.return_value = {
            'value': [
                {
                    'id': 'attachment1',
                    'name': 'voice.mp3',
                    'contentType': 'audio/mpeg'
                }
            ]
        }
        
        # Mock content response
        content_response = Mock()
        content_response.content = b'audio content data'
        
        # Configure make_authenticated_request to return different responses
        mock_request.side_effect = [attachments_response, content_response]
        
        # Mock retry to return the content
        mock_retry.return_value = b'audio content data'
        
        # Initialize processor
        self.processor.auth_manager = Mock()
        
        # Download attachment
        result = self.processor._download_attachment_content('email1', 'voice.mp3')
        
        # Verify result
        assert result == b'audio content data'
        
        # Verify retry was called
        mock_retry.assert_called_once()
    
    def test_download_attachment_content_not_found(self):
        """Test downloading non-existent attachment"""
        # Mock retry to raise exception
        with patch('src.processors.email_processor.retry_with_exponential_backoff') as mock_retry:
            mock_retry.side_effect = Exception("Attachment not found")
            
            # Initialize processor
            self.processor.auth_manager = Mock()
            
            # Download attachment
            result = self.processor._download_attachment_content('email1', 'nonexistent.mp3')
            
            # Verify result is None and error was handled
            assert result is None
            self.mock_error_handler.handle_error.assert_called_once()
    
    def test_convert_to_email_message(self):
        """Test converting Graph API data to EmailMessage"""
        # Mock email data
        email_data = {
            'id': 'email1',
            'subject': 'Voice Message',
            'receivedDateTime': '2025-07-24T10:00:00Z',
            'from': {
                'emailAddress': {'address': 'sender@example.com', 'name': 'John Doe'}
            },
            'bodyPreview': 'Voice message attached',
            'attachments': [
                {
                    'id': 'attachment1',
                    'name': 'voice.mp3',
                    'contentType': 'audio/mpeg',
                    'size': 1024
                }
            ]
        }
        
        # Convert to EmailMessage
        email_message = self.processor._convert_to_email_message(email_data)
        
        # Verify conversion
        assert email_message is not None
        assert isinstance(email_message, EmailMessage)
        assert email_message.email_id == 'email1'
        assert email_message.subject == 'Voice Message'
        assert email_message.sender_email == 'sender@example.com'
        assert email_message.sender_name == 'John Doe'
        assert len(email_message.voice_attachments) == 1
        
        # Verify voice attachment
        attachment = email_message.voice_attachments[0]
        assert isinstance(attachment, VoiceAttachment)
        assert attachment.attachment_id == 'attachment1'
        assert attachment.filename == 'voice.mp3'
        assert attachment.content_type == 'audio/mpeg'
        assert attachment.size_bytes == 1024
    
    def test_convert_to_email_message_no_attachments(self):
        """Test converting email data with no voice attachments"""
        # Mock email data without voice attachments
        email_data = {
            'id': 'email1',
            'subject': 'Text Email',
            'receivedDateTime': '2025-07-24T10:00:00Z',
            'from': {
                'emailAddress': {'address': 'sender@example.com', 'name': 'John Doe'}
            },
            'bodyPreview': 'Text message',
            'attachments': [
                {
                    'id': 'attachment1',
                    'name': 'document.pdf',
                    'contentType': 'application/pdf',
                    'size': 2048
                }
            ]
        }
        
        # Convert to EmailMessage
        email_message = self.processor._convert_to_email_message(email_data)
        
        # Should return None since no voice attachments
        assert email_message is None
    
    def test_is_voice_attachment(self):
        """Test voice attachment detection"""
        # Test various attachment types
        voice_attachments = [
            {'name': 'voice.mp3', 'contentType': 'audio/mpeg'},
            {'name': 'message.wav', 'contentType': 'audio/wav'},
            {'name': 'recording.m4a', 'contentType': 'audio/mp4'},
            {'name': 'audio.ogg', 'contentType': 'audio/ogg'},
        ]
        
        non_voice_attachments = [
            {'name': 'document.pdf', 'contentType': 'application/pdf'},
            {'name': 'image.jpg', 'contentType': 'image/jpeg'},
            {'name': 'video.mp4', 'contentType': 'video/mp4'},
            {'name': 'text.txt', 'contentType': 'text/plain'},
        ]
        
        # Test voice attachments
        for attachment in voice_attachments:
            assert self.processor._is_voice_attachment(attachment) == True
        
        # Test non-voice attachments
        for attachment in non_voice_attachments:
            assert self.processor._is_voice_attachment(attachment) == False
    
    def test_get_time_filter(self):
        """Test time filter generation"""
        # Test time filter for 7 days back
        time_filter = self.processor._get_time_filter(7)
        
        # Verify format
        assert isinstance(time_filter, str)
        assert time_filter.endswith('Z')
        assert len(time_filter) == 20  # ISO format length
        
        # Verify it's a valid datetime string
        parsed_time = datetime.fromisoformat(time_filter.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        time_diff = now - parsed_time
        
        # Should be approximately 7 days (allow some variance for test execution time)
        assert 6.9 <= time_diff.days <= 7.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
