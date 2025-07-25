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
from helpers.oauth import make_graph_request
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
        """Fetch emails with attachments from Microsoft Graph"""
        try:
            # Search for emails with attachments (cast wider net)
            url = f"https://graph.microsoft.com/v1.0/me/messages?$filter=hasAttachments eq true&$top={max_emails * 3}"
            
            response = make_graph_request(url)
            if not response or response.status_code != 200:
                logger.error(f"❌ Failed to fetch emails: {response.status_code if response else 'No response'}")
                return []
            
            messages = response.json().get('value', [])
            logger.info(f"📧 Found {len(messages)} emails with attachments")
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error fetching emails: {e}")
            return []
    
    def _filter_messages_by_date(self, messages: List[dict], days_back: int, max_emails: int) -> List[dict]:
        """Filter messages by date and limit count"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            filtered_messages = []
            
            for message in messages:
                received_str = message.get('receivedDateTime', '')
                if received_str:
                    try:
                        received_date = datetime.fromisoformat(received_str.replace('Z', '+00:00'))
                        if received_date >= cutoff_date:
                            filtered_messages.append(message)
                            if len(filtered_messages) >= max_emails:
                                break
                    except:
                        continue
            
            return filtered_messages
            
        except Exception as e:
            logger.error(f"❌ Error filtering messages by date: {e}")
            return []
    
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
                        logger.info(f"   📎 Voice email found: {voice_email.subject[:50]}... ({len(voice_attachments)} attachments)")
            
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
                return []
            
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
        """Check if attachment is a valid WAV file within size limits"""
        try:
            # Check if this is a .wav file (only format we process)
            if not filename.lower().endswith('.wav'):
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
        """Mark email as processed by moving to a folder or adding a flag"""
        try:
            # Option 1: Add a category
            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"
            data = {
                "categories": ["Scribe Processed"]
            }
            
            response = make_graph_request(url, method='PATCH', data=data)
            
            if response and response.status_code == 200:
                logger.info(f"✅ Email marked as processed: {message_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to mark email as processed: {response.status_code if response else 'No response'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error marking email as processed: {e}")
            return False