"""
Production Email Processor using centralized architecture
Handles email retrieval, filtering, and processing coordination
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from ..core import ScribeLogger, ScribeErrorHandler, ScribeConfigurationManager
from ..helpers.validation_helpers import validate_email_address
from ..helpers.retry_helpers import RetryConfig, retry_with_exponential_backoff
from ..helpers.performance_helpers import PerformanceTimer
from ..helpers.http_helpers import make_authenticated_request
from ..helpers.auth_helpers import get_auth_manager
from ..helpers.request_config import RequestConfig
from ..models import EmailMessage, VoiceAttachment, EmailStatus, ProcessingResult


class ScribeEmailProcessor:
    """Production email processor with centralized authentication and HTTP handling"""
    
    def __init__(self, configuration_manager: ScribeConfigurationManager, 
                 error_handler: ScribeErrorHandler, logger: ScribeLogger):
        """Initialize email processor with injected dependencies"""
        self.config = configuration_manager
        self.error_handler = error_handler
        self.logger = logger
        self.target_user_email = None
        
        # Get centralized services
        self.auth_manager = get_auth_manager(self.config.client_id)
        
        # Email processing settings
        self.voice_extensions = {'.wav', '.mp3', '.m4a', '.amr', '.3gp', '.flac', '.ogg'}
        
        try:
            self.logger.log_info("Email processor initialized successfully", {
                'voice_extensions_count': len(self.voice_extensions),
                'has_auth_manager': bool(self.auth_manager)
            })
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize email processor")
    
    def initialize(self, target_user_email: str) -> bool:
        """
        Initialize email processor with target user email
        
        Args:
            target_user_email: Target email address for processing
            
        Returns:
            bool: True if initialization successful
        """
        try:
            # Validate email
            if not validate_email_address(target_user_email):
                raise ValueError(f"Invalid target email address: {target_user_email}")
            
            self.target_user_email = target_user_email
            
            # Test authentication
            auth_headers = self.auth_manager.get_auth_headers('graph')
            if not auth_headers:
                raise Exception("Failed to obtain authentication headers")
            
            self.logger.log_info("Email processor initialized", {
                'target_email': target_user_email,
                'has_auth': bool(auth_headers)
            })
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize email processor")
            return False

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import requests

from ..core import ScribeLogger, ScribeErrorHandler, ScribeConfigurationManager
from ..helpers.validation_helpers import validate_email_address
from ..helpers.retry_helpers import RetryConfig, retry_with_exponential_backoff
from ..helpers.performance_helpers import PerformanceTimer
from ..models import EmailMessage, VoiceAttachment, EmailStatus, ProcessingResult


class ScribeEmailProcessor:
    """Production email processor with error handling and monitoring"""
    
    def __init__(self, configuration_manager: ScribeConfigurationManager, 
                 error_handler: ScribeErrorHandler, logger: ScribeLogger):
        """Initialize email processor with injected dependencies"""
        self.config = configuration_manager
        self.error_handler = error_handler
        self.logger = logger
        self.auth_manager = None
        self.target_user_email = None
    
    def initialize(self, target_user_email: str) -> bool:
        """Initialize processor with target email configuration"""
        try:
            # Get centralized auth manager
            from ..helpers.auth_helpers import get_auth_manager
            self.auth_manager = get_auth_manager()
            
            if not validate_email_address(target_user_email):
                raise ValueError(f"Invalid target email address: {target_user_email}")
            
            self.target_user_email = target_user_email
            
            self.logger.log_info("Email processor initialized successfully", {
                'target_email': target_user_email,
                'has_auth_manager': bool(self.auth_manager)
            })
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize email processor")
            return False
    
    def get_voice_emails(self, days_back: int = 7, max_emails: int = 50) -> List[EmailMessage]:
        """Get emails with voice attachments from inbox"""
        with PerformanceTimer("get_voice_emails") as timer:
            try:
                emails_data = self._fetch_inbox_emails_with_attachments(days_back, max_emails)
                voice_emails = []
                
                for email_data in emails_data:
                    email_message = self._convert_to_email_message(email_data)
                    if email_message and email_message.has_voice_attachments:
                        voice_emails.append(email_message)
                
                self.logger.log_info(f"Retrieved {len(voice_emails)} voice emails", {
                    'total_emails_checked': len(emails_data),
                    'voice_emails_found': len(voice_emails),
                    'processing_time_ms': timer.elapsed_ms
                })
                
                return voice_emails
                
            except Exception as e:
                self.error_handler.handle_error(e, "Failed to retrieve voice emails")
                return []
    
    def download_voice_attachment(self, email_id: str, attachment: VoiceAttachment, 
                                blob_client) -> Optional[str]:
        """Download voice attachment to blob storage"""
        try:
            # Download attachment content
            attachment_data = self._download_attachment_content(email_id, attachment.filename)
            if not attachment_data:
                return None
            
            # Upload to blob storage with public access
            blob_name = f"voice-messages/{email_id}/{attachment.filename}"
            blob_url = self._upload_to_blob_storage(blob_client, blob_name, attachment_data)
            
            self.logger.log_info("Voice attachment downloaded successfully", {
                'email_id': email_id,
                'attachment_name': attachment.filename,
                'blob_url': blob_url,
                'size_bytes': len(attachment_data)
            })
            
            return blob_url
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to download attachment {attachment.filename}")
            return None
    
    def move_email_to_processed(self, email_id: str) -> bool:
        """Move email to processed folder"""
        try:
            processed_folder_id = self._ensure_processed_folder_exists()
            if not processed_folder_id:
                return False
            
            success = self._move_email_to_folder(email_id, processed_folder_id)
            
            if success:
                self.logger.log_info("Email moved to processed folder", {
                    'email_id': email_id,
                    'folder_id': processed_folder_id
                })
            
            return success
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to move email {email_id}")
            return False
    
    def _fetch_inbox_emails_with_attachments(self, days_back: int, max_emails: int) -> List[Dict]:
        """Fetch emails from inbox with attachments using retry logic"""
        
        def _fetch_operation():
            time_filter = self._get_time_filter(days_back)
            
            url = f"{RequestConfig.ENDPOINTS['graph_messages']}/inbox/messages"
            params = {
                '$filter': f"receivedDateTime ge {time_filter} and hasAttachments eq true",
                '$expand': 'attachments',
                '$select': 'id,subject,receivedDateTime,from,bodyPreview,attachments',
                '$orderby': 'receivedDateTime desc',
                '$top': max_emails
            }
            
            response = make_authenticated_request(
                'GET', url,
                token_type='graph',
                operation_type='api',
                params=params
            )
            
            return response.json().get('value', [])
        
        return retry_with_exponential_backoff(
            _fetch_operation, 
            RequestConfig.get_retry_for_operation('network'),
            "fetch_inbox_emails"
        )
    
    def _convert_to_email_message(self, email_data: Dict) -> Optional[EmailMessage]:
        """Convert Graph API email data to EmailMessage model"""
        try:
            attachments = []
            for att_data in email_data.get('attachments', []):
                if self._is_voice_attachment(att_data):
                    attachment = VoiceAttachment(
                        filename=att_data.get('name', ''),
                        content_type=att_data.get('contentType', ''),
                        size_bytes=att_data.get('size', 0)
                    )
                    attachments.append(attachment)
            
            email_message = EmailMessage(
                message_id=email_data['id'],
                subject=email_data.get('subject', ''),
                sender=email_data.get('from', {}).get('emailAddress', {}).get('address', ''),
                received_datetime=datetime.fromisoformat(
                    email_data['receivedDateTime'].replace('Z', '+00:00')
                ),
                body_preview=email_data.get('bodyPreview', ''),
                attachments=attachments
            )
            
            return email_message
            
        except Exception as e:
            self.logger.log_warning(f"Failed to convert email data: {str(e)}", {
                'email_id': email_data.get('id', 'unknown')
            })
            return None
    
    def _is_voice_attachment(self, attachment_data: Dict) -> bool:
        """Check if attachment is a supported voice file"""
        filename = attachment_data.get('name', '').lower()
        voice_extensions = ['.mp3', '.wav', '.m4a', '.mp4', '.ogg', '.flac']
        return any(filename.endswith(ext) for ext in voice_extensions)
    
    def _download_attachment_content(self, email_id: str, attachment_name: str) -> Optional[bytes]:
        """Download attachment content from email"""
        
        def _download_operation():
            url = f"{RequestConfig.ENDPOINTS['graph_messages']}/{email_id}/attachments"
            
            response = make_authenticated_request(
                'GET', url,
                token_type='graph',
                operation_type='api'
            )
            
            attachments = response.json().get('value', [])
            target_attachment = None
            
            for att in attachments:
                if att.get('name') == attachment_name:
                    target_attachment = att
                    break
            
            if not target_attachment:
                raise Exception(f"Attachment {attachment_name} not found")
            
            # Get attachment content
            attachment_id = target_attachment['id']
            content_url = f"{RequestConfig.ENDPOINTS['graph_messages']}/{email_id}/attachments/{attachment_id}/$value"
            
            content_response = make_authenticated_request(
                'GET', content_url,
                token_type='graph',
                operation_type='file_transfer'
            )
            
            return content_response.content
        
        try:
            return retry_with_exponential_backoff(
                _download_operation, 
                RequestConfig.get_retry_for_operation('network'),
                "download_attachment"
            )
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to download attachment {attachment_name}")
            return None
    
    def _upload_to_blob_storage(self, blob_client, blob_name: str, data: bytes) -> str:
        """Upload data to blob storage with public access"""
        try:
            # Upload blob with public access
            blob_client.upload_blob(
                name=blob_name,
                data=data,
                overwrite=True,
                blob_type="BlockBlob"
            )
            
            # Return public URL
            blob_url = f"{blob_client.url}/{blob_name}"
            return blob_url
            
        except Exception as e:
            raise Exception(f"Failed to upload to blob storage: {str(e)}")
    
    def _ensure_processed_folder_exists(self) -> Optional[str]:
        """Ensure processed folder exists and return its ID"""
        folder_name = "Voice Messages Processed"
        
        def _get_or_create_folder():
            headers = self._get_request_headers()
            
            # First, try to find existing folder
            search_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            params = {'$filter': f"displayName eq '{folder_name}'"}
            
            response = requests.get(search_url, headers=headers, params=params,
                                  timeout=self.request_timeout)
            
            if response.status_code == 200:
                folders = response.json().get('value', [])
                if folders:
                    return folders[0]['id']
            
            # Create folder if it doesn't exist
            create_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            create_data = {'displayName': folder_name}
            
            create_response = requests.post(create_url, headers=headers,
                                          json=create_data, timeout=self.request_timeout)
            
            if create_response.status_code == 201:
                return create_response.json()['id']
            
            raise Exception(f"Failed to create folder: {create_response.text}")
        
        try:
            return retry_with_exponential_backoff(_get_or_create_folder, self.retry_config)
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to ensure folder {folder_name} exists")
            return None
    
    def _move_email_to_folder(self, email_id: str, folder_id: str) -> bool:
        """Move email to specified folder"""
        
        def _move_operation():
            headers = self._get_request_headers()
            url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/move"
            data = {'destinationId': folder_id}
            
            response = requests.post(url, headers=headers, json=data,
                                   timeout=self.request_timeout)
            
            if response.status_code != 201:
                raise Exception(f"Failed to move email: {response.text}")
            
            return True
        
        try:
            return retry_with_exponential_backoff(_move_operation, self.retry_config)
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to move email {email_id}")
            return False
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get headers for Graph API requests"""
        return self.auth_manager.get_auth_headers('graph')
    
    def _get_time_filter(self, days_back: int) -> str:
        """Get time filter for email queries"""
        time_filter = datetime.now(timezone.utc) - timedelta(days=days_back)
        return time_filter.strftime('%Y-%m-%dT%H:%M:%SZ')
