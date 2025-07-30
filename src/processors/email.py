"""
Email Processor for Scribe Voice Email Processor
Handles email retrieval and voice attachment detection using Microsoft Graph API
"""

import logging
import base64
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from core.config import ScribeConfig
from core.input_validation import input_validator
from helpers.auth_manager import make_graph_request
from models.data import VoiceEmail, VoiceAttachment

logger = logging.getLogger(__name__)

class EmailProcessor:
    """Process emails and extract voice attachments"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        logger.info(f"📧 Email processor initialized for {config.target_user_email}")
    
    def get_voice_emails(self, days_back: int = None, max_emails: int = None) -> List[VoiceEmail]:
        """Get emails with voice attachments from the last N days"""
        try:
            days_back = days_back or self.config.days_back
            max_emails = max_emails or self.config.max_emails
            
            logger.info(f"🔍 Searching for voice emails: {days_back} days back, max {max_emails} emails")
            
            # Fetch emails with attachments
            messages = self._fetch_emails_with_attachments(max_emails)
            if not messages:
                return []
            
            # Filter messages by date
            filtered_messages = self._filter_messages_by_date(messages, days_back, max_emails)
            logger.info(f"📅 After date filtering: {len(filtered_messages)} emails from last {days_back} days")
            
            # Process messages to find voice emails
            voice_emails = self._process_messages_for_voice_attachments(filtered_messages)
            
            logger.info(f"✅ Found {len(voice_emails)} emails with voice attachments")
            return voice_emails
            
        except Exception as e:
            logger.error(f"❌ Error getting voice emails: {e}")
            return []
    
    def _fetch_emails_with_attachments(self, max_emails: int) -> List[dict]:
        """Fetch emails with attachments from inbox folder only"""
        try:
            # Search for emails with attachments in inbox folder only
            url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter=hasAttachments eq true&$top={max_emails * 3}"
            
            response = make_graph_request(url)
            if not response or response.status_code != 200:
                logger.error(f"❌ Failed to fetch inbox emails: {response.status_code if response else 'No response'}")
                return []
            
            messages = response.json().get('value', [])
            logger.info(f"📧 Found {len(messages)} emails with attachments in inbox")
            
            # Log summary only
            if messages:
                recent_subjects = [msg.get('subject', 'No Subject')[:50] for msg in messages[:3]]
                logger.info(f"📧 Recent emails: {', '.join(recent_subjects)}")
            else:
                logger.warning("⚠️ No emails with attachments found in inbox")
            
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error fetching inbox emails: {e}")
            return []
    
    def _filter_messages_by_date(self, messages: List[dict], days_back: int, max_emails: int) -> List[dict]:
        """Filter messages by date and limit count"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            filtered_messages = []
            
            for message in messages:
                if len(filtered_messages) >= max_emails:
                    break
                    
                parsed_date = self._parse_message_date(message)
                if parsed_date and parsed_date >= cutoff_date:
                    filtered_messages.append(message)
            
            return filtered_messages
            
        except Exception as e:
            logger.error(f"❌ Error filtering messages by date: {e}")
            return []
    
    def _parse_message_date(self, message: dict) -> Optional[datetime]:
        """Parse message received date, returns None if invalid"""
        received_str = message.get('receivedDateTime', '')
        if not received_str:
            return None
            
        try:
            return datetime.fromisoformat(received_str.replace('Z', '+00:00'))
        except Exception:
            return None
    
    def _process_messages_for_voice_attachments(self, messages: List[dict]) -> List[VoiceEmail]:
        """Process messages to extract voice emails with WAV attachments"""
        voice_emails = []
        
        for message in messages:
            try:
                voice_attachments = self._get_voice_attachments(message['id'])
                
                if voice_attachments:
                    voice_email = self._create_voice_email_from_message(message, voice_attachments)
                    if voice_email:
                        voice_emails.append(voice_email)
                        logger.info(f"📎 Voice email found: {voice_email.subject[:50]} ({len(voice_attachments)} attachments)")
            
            except Exception as e:
                logger.warning(f"⚠️ Error processing message {message.get('id', 'unknown')}: {e}")
                continue
        
        return voice_emails
    
    def _create_voice_email_from_message(self, message: dict, voice_attachments: List[VoiceAttachment]) -> Optional[VoiceEmail]:
        """Create VoiceEmail object from message data"""
        try:
            # Parse and validate sender
            sender_info = message.get('sender', {}).get('emailAddress', {})
            raw_sender = sender_info.get('address', 'Unknown')
            sender = input_validator.validate_email_address(raw_sender) or 'Unknown'
            
            # Parse received date
            received_str = message.get('receivedDateTime', '')
            received_date = datetime.fromisoformat(received_str.replace('Z', '+00:00')) if received_str else datetime.now(timezone.utc)
            
            # Validate subject
            raw_subject = message.get('subject', 'No Subject')
            validated_subject = input_validator.validate_email_subject(raw_subject) or 'No Subject'
            
            return VoiceEmail(
                message_id=message['id'],
                subject=validated_subject,
                sender=sender,
                received_date=received_date,
                voice_attachments=voice_attachments
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating voice email from message: {e}")
            return None
    
    def _get_voice_attachments(self, message_id: str) -> List[VoiceAttachment]:
        """Get voice attachments from a specific email message"""
        try:
            attachments_data = self._fetch_message_attachments(message_id)
            if not attachments_data:
                logger.info(f"🔍 No attachments found for message {message_id}")
                return []
            
            logger.info(f"🔍 Found {len(attachments_data)} attachments for message {message_id}")
            for i, att in enumerate(attachments_data):
                filename = att.get('name', 'Unknown')
                content_type = att.get('contentType', 'Unknown')
                size = att.get('size', 0)
                logger.info(f"   {i+1}. {filename} ({content_type}, {size} bytes)")
            
            voice_attachments = []
            for attachment in attachments_data:
                voice_attachment = self._process_single_attachment(message_id, attachment)
                if voice_attachment:
                    voice_attachments.append(voice_attachment)
            
            return voice_attachments
            
        except Exception as e:
            logger.error(f"❌ Error getting voice attachments: {e}")
            return []
    
    def _fetch_message_attachments(self, message_id: str) -> List[dict]:
        """Fetch attachment metadata from a message"""
        try:
            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"
            response = make_graph_request(url)
            
            if not response or response.status_code != 200:
                logger.warning(f"⚠️ Failed to get attachments for message {message_id}")
                return []
            
            return response.json().get('value', [])
            
        except Exception as e:
            logger.error(f"❌ Error fetching attachments metadata: {e}")
            return []
    
    def _process_single_attachment(self, message_id: str, attachment: dict) -> Optional[VoiceAttachment]:
        """Process a single attachment and return VoiceAttachment if valid"""
        try:
            # Extract and validate attachment metadata
            attachment_info = self._extract_attachment_info(attachment)
            if not attachment_info:
                return None
            
            filename, content_type, size = attachment_info
            
            # Check if attachment meets our criteria
            if not self._is_valid_wav_attachment(filename, size):
                return None
            
            # Download and validate content
            content_bytes = self._download_and_validate_content(message_id, attachment['id'], filename)
            if not content_bytes:
                return None
            
            # Create VoiceAttachment object
            voice_attachment = VoiceAttachment(
                filename=filename,
                content=content_bytes,
                size=size,
                content_type=content_type
            )
            
            logger.info(f"      📎 Voice attachment: {filename} ({size} bytes)")
            return voice_attachment
            
        except Exception as e:
            logger.warning(f"⚠️ Error processing attachment: {e}")
            return None
    
    def _extract_attachment_info(self, attachment: dict) -> Optional[tuple]:
        """Extract and validate attachment information"""
        try:
            raw_filename = attachment.get('name', '')
            content_type = attachment.get('contentType', '')
            size = attachment.get('size', 0)
            
            # Validate filename
            filename = input_validator.validate_audio_filename(raw_filename)
            if not filename:
                logger.warning(f"⚠️ Invalid audio filename: {raw_filename}")
                return None
            
            return filename, content_type, size
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting attachment info: {e}")
            return None
    
    def _is_valid_wav_attachment(self, filename: str, size: int) -> bool:
        """Check if attachment is a valid audio file within size limits"""
        try:
            # Check if this is an audio file (expanded to support common voice message formats)
            audio_extensions = ['.wav', '.m4a', '.mp3', '.amr', '.mp4', '.3gp', '.aac', '.ogg']
            file_ext = filename.lower()[-4:] if len(filename) >= 4 else ''
            
            is_audio = any(file_ext.endswith(ext) for ext in audio_extensions)
            if not is_audio:
                logger.info(f"🔍 Skipping non-audio file: {filename}")
                return False
            
            # Check if file has content
            if size <= 0:
                logger.warning(f"⚠️ Empty attachment: {filename}")
                return False
            
            # Check file size limit
            max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
            if size > max_size_bytes:
                logger.warning(f"⚠️ Voice file too large: {filename} ({size} bytes)")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Error validating WAV attachment: {e}")
            return False
    
    def _download_and_validate_content(self, message_id: str, attachment_id: str, filename: str) -> Optional[bytes]:
        """Download attachment content and validate it"""
        try:
            # Download content
            content_bytes = self._download_attachment_content(message_id, attachment_id)
            if not content_bytes:
                return None
            
            # Validate audio data
            if not input_validator.validate_audio_data(content_bytes, filename):
                logger.warning(f"⚠️ Audio data validation failed: {filename}")
                return None
            
            return content_bytes
            
        except Exception as e:
            logger.warning(f"⚠️ Error downloading and validating content: {e}")
            return None
    
    def _download_attachment_content(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """Download attachment content as bytes"""
        try:
            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_id}/$value"
            response = make_graph_request(url)
            
            if response and response.status_code == 200:
                return response.content
            else:
                logger.warning(f"⚠️ Failed to download attachment content: {response.status_code if response else 'No response'}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error downloading attachment: {e}")
            return None
    
    def mark_email_processed(self, message_id: str) -> bool:
        """Mark email as read and move to Voice Messages Processed folder"""
        try:
            # Step 1: Mark as read
            read_success = self._mark_email_as_read(message_id)
            
            # Step 2: Move to processed folder
            move_success = self._move_email_to_processed_folder(message_id)
            
            if read_success and move_success:
                logger.info(f"✅ Email marked as read and moved to processed folder: {message_id}")
                return True
            else:
                logger.warning(f"⚠️ Partial success - read: {read_success}, moved: {move_success}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error processing email: {e}")
            return False
    
    def _mark_email_as_read(self, message_id: str) -> bool:
        """Mark email as read"""
        try:
            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"
            data = {
                "isRead": True
            }
            
            response = make_graph_request(url, method='PATCH', data=data)
            
            if response and response.status_code == 200:
                logger.info(f"📖 Email marked as read: {message_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to mark email as read: {response.status_code if response else 'No response'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error marking email as read: {e}")
            return False
    
    def _move_email_to_processed_folder(self, message_id: str) -> bool:
        """Move email to Voice Messages Processed folder"""
        try:
            # First, ensure the processed folder exists
            processed_folder_id = self._get_or_create_processed_folder()
            if not processed_folder_id:
                logger.error("❌ Could not get or create processed folder")
                return False
            
            # Move the message
            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/move"
            data = {
                "destinationId": processed_folder_id
            }
            
            response = make_graph_request(url, method='POST', data=data)
            
            if response and response.status_code == 201:  # Created (message moved)
                logger.info(f"📁 Email moved to processed folder: {message_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to move email: {response.status_code if response else 'No response'}")
                if response:
                    logger.warning(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error moving email to processed folder: {e}")
            return False
    
    def _get_or_create_processed_folder(self) -> Optional[str]:
        """Get or create the Voice Messages Processed folder"""
        try:
            folder_name = "Voice Messages Processed"
            
            # First, try to find existing folder
            folder_id = self._find_folder_by_name(folder_name)
            if folder_id:
                logger.info(f"📁 Found existing processed folder: {folder_id}")
                return folder_id
            
            # If not found, create it
            folder_id = self._create_folder(folder_name)
            if folder_id:
                logger.info(f"📁 Created new processed folder: {folder_id}")
                return folder_id
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting or creating processed folder: {e}")
            return None
    
    def _find_folder_by_name(self, folder_name: str) -> Optional[str]:
        """Find a mail folder by name"""
        try:
            url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            response = make_graph_request(url)
            
            if not response or response.status_code != 200:
                logger.warning(f"⚠️ Failed to get mail folders: {response.status_code if response else 'No response'}")
                return None
            
            folders = response.json().get('value', [])
            for folder in folders:
                if folder.get('displayName') == folder_name:
                    return folder.get('id')
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding folder by name: {e}")
            return None
    
    def _create_folder(self, folder_name: str) -> Optional[str]:
        """Create a new mail folder"""
        try:
            url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            data = {
                "displayName": folder_name
            }
            
            response = make_graph_request(url, method='POST', data=data)
            
            if response and response.status_code == 201:  # Created
                folder_data = response.json()
                folder_id = folder_data.get('id')
                logger.info(f"📁 Created folder '{folder_name}' with ID: {folder_id}")
                return folder_id
            else:
                logger.error(f"❌ Failed to create folder: {response.status_code if response else 'No response'}")
                if response:
                    logger.error(f"   Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating folder: {e}")
            return None