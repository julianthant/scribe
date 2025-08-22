"""
voice_attachment_service.py - Voice Attachment Processing Service

Provides specialized business logic for voice attachment detection, processing, and organization.
This service handles:
- Voice attachment detection across multiple audio formats
- Automatic voice attachment organization and categorization
- Cross-mailbox voice attachment analysis
- Voice attachment statistics and reporting
- Audio file metadata extraction and validation
- Duplicate detection and consolidation
- Voice attachment workflow automation
- Performance optimization for large attachment sets

The VoiceAttachmentService class provides advanced voice mail management
capabilities for both personal and shared mailboxes.
"""

from typing import List, Optional, Dict, Any, Set, Tuple
import logging
import os
import io
from pathlib import Path
from datetime import datetime

from app.services.mail_service import MailService
from app.repositories.mail_repository import MailRepository
from app.repositories.shared_mailbox_repository import SharedMailboxRepository
from app.core.exceptions import ValidationError, AuthenticationError
from app.models.mail import (
    VoiceAttachment, Message, Attachment, FileAttachment,
    OrganizeVoiceResponse, FolderStatistics
)
from app.models.shared_mailbox import (
    SharedMailboxMessage, OrganizeSharedMailboxResponse
)

logger = logging.getLogger(__name__)


class VoiceAttachmentService:
    """Specialized service for voice attachment operations."""

    # Comprehensive list of audio content types
    AUDIO_CONTENT_TYPES = {
        # Standard audio MIME types
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave',
        'audio/ogg', 'audio/vorbis', 'audio/opus',
        'audio/m4a', 'audio/aac', 'audio/mp4',
        'audio/webm', 'audio/webm;codecs=opus',
        'audio/amr', 'audio/amr-nb', 'audio/amr-wb',
        'audio/3gpp', 'audio/3gpp2',
        'audio/flac', 'audio/x-flac',
        'audio/aiff', 'audio/x-aiff',
        'audio/au', 'audio/basic', 'audio/x-au',
        'audio/midi', 'audio/mid', 'audio/x-midi',
        'audio/x-m4a', 'audio/x-wav', 'audio/x-wave',
        'audio/x-ms-wma', 'audio/wma',
        'audio/x-realaudio', 'audio/vnd.rn-realaudio',
        'audio/ac3', 'audio/eac3',
        'audio/dts', 'audio/x-dts',
        'audio/speex', 'audio/x-speex',
        # Voice message specific types
        'audio/voice', 'audio/voicemail',
        'audio/x-voice', 'audio/x-voicemail'
    }

    # Audio file extensions
    AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.wave', '.ogg', '.oga',
        '.m4a', '.aac', '.mp4a', '.webm',
        '.amr', '.3gp', '.3gpp', '.3g2',
        '.flac', '.fla', '.aiff', '.aif', '.aifc',
        '.au', '.snd', '.mid', '.midi', '.rmi',
        '.wma', '.asf', '.ra', '.ram',
        '.ac3', '.eac3', '.dts', '.spx',
        '.mka', '.mpc', '.ape', '.wv'
    }

    def __init__(
        self, 
        mail_service: MailService, 
        mail_repository: MailRepository,
        shared_mailbox_repository: Optional[SharedMailboxRepository] = None
    ):
        """Initialize voice attachment service.
        
        Args:
            mail_service: Mail service instance
            mail_repository: Mail repository instance
            shared_mailbox_repository: Optional shared mailbox repository instance
        """
        self.mail_service = mail_service
        self.mail_repository = mail_repository
        self.shared_mailbox_repository = shared_mailbox_repository

    async def find_all_voice_messages(
        self, 
        folder_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Message]:
        """Find all messages containing voice attachments.

        Args:
            folder_id: Optional folder ID to search within
            limit: Maximum number of messages to check

        Returns:
            List of messages containing voice attachments

        Raises:
            AuthenticationError: If search fails
        """
        try:
            messages_response, _ = await self.mail_service.get_messages_with_voice_attachments(
                folder_id=folder_id,
                top=limit
            )
            
            logger.info(f"Found {len(messages_response.value)} voice messages")
            return messages_response.value

        except Exception as e:
            logger.error(f"Failed to find voice messages: {str(e)}")
            raise AuthenticationError(f"Failed to find voice messages: {str(e)}")

    async def extract_voice_attachments_from_message(
        self, 
        message_id: str
    ) -> List[VoiceAttachment]:
        """Extract all voice attachments from a specific message.

        Args:
            message_id: Message ID to extract from

        Returns:
            List of voice attachments found

        Raises:
            AuthenticationError: If extraction fails
        """
        try:
            attachments = await self.mail_repository.get_attachments(message_id)
            voice_attachments = []

            for attachment in attachments:
                if self.is_voice_attachment(attachment):
                    voice_attachment = VoiceAttachment(
                        messageId=message_id,
                        attachmentId=attachment.id,
                        name=attachment.name,
                        contentType=attachment.contentType or "unknown",
                        size=attachment.size
                    )
                    
                    # Try to extract additional metadata
                    metadata = await self._extract_audio_metadata(attachment)
                    voice_attachment.duration = metadata.get("duration")
                    voice_attachment.sampleRate = metadata.get("sampleRate")
                    voice_attachment.bitRate = metadata.get("bitRate")
                    
                    voice_attachments.append(voice_attachment)

            logger.info(f"Extracted {len(voice_attachments)} voice attachments from message {message_id}")
            return voice_attachments

        except Exception as e:
            logger.error(f"Failed to extract voice attachments from {message_id}: {str(e)}")
            raise AuthenticationError(f"Failed to extract voice attachments: {str(e)}")

    async def save_voice_attachment(
        self, 
        message_id: str, 
        attachment_id: str, 
        save_path: str
    ) -> str:
        """Download and save a voice attachment to local storage.

        Args:
            message_id: Message ID
            attachment_id: Attachment ID
            save_path: Path to save the file

        Returns:
            Full path where file was saved

        Raises:
            ValidationError: If attachment is not voice or path is invalid
            AuthenticationError: If download fails
        """
        try:
            # Validate that it's a voice attachment
            attachments = await self.mail_repository.get_attachments(message_id)
            target_attachment = None
            
            for attachment in attachments:
                if attachment.id == attachment_id:
                    target_attachment = attachment
                    break
            
            if not target_attachment:
                raise ValidationError("Attachment not found")
            
            if not self.is_voice_attachment(target_attachment):
                raise ValidationError("Attachment is not a voice/audio file")

            # Create directory if it doesn't exist
            save_dir = Path(save_path).parent
            save_dir.mkdir(parents=True, exist_ok=True)

            # Download attachment content
            content = await self.mail_repository.download_attachment(message_id, attachment_id)
            
            # Generate filename if save_path is a directory
            if Path(save_path).is_dir():
                filename = target_attachment.name or f"voice_{attachment_id}"
                # Ensure proper extension
                if not any(filename.lower().endswith(ext) for ext in self.AUDIO_EXTENSIONS):
                    ext = self._get_extension_from_content_type(target_attachment.contentType)
                    filename += ext
                save_path = str(Path(save_path) / filename)

            # Write content to file
            with open(save_path, 'wb') as f:
                f.write(content)

            logger.info(f"Saved voice attachment to: {save_path} ({len(content)} bytes)")
            return save_path

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to save voice attachment: {str(e)}")
            raise AuthenticationError(f"Failed to save voice attachment: {str(e)}")

    async def organize_voice_messages(
        self, 
        target_folder_name: str = "Voice Messages",
        source_folder_id: Optional[str] = None
    ) -> OrganizeVoiceResponse:
        """Organize all voice messages into a dedicated folder.

        Args:
            target_folder_name: Name of folder to organize voice messages into
            source_folder_id: Optional source folder (if None, searches entire mailbox)

        Returns:
            Organization response with detailed statistics

        Raises:
            AuthenticationError: If organization fails
        """
        try:
            logger.info(f"Starting voice message organization to folder: {target_folder_name}")
            
            # Use the mail service organize functionality
            response = await self.mail_service.organize_voice_messages(target_folder_name)
            
            logger.info(f"Voice message organization completed: {response.messagesMoved} messages moved")
            return response

        except Exception as e:
            logger.error(f"Failed to organize voice messages: {str(e)}")
            raise AuthenticationError(f"Failed to organize voice messages: {str(e)}")

    async def get_voice_attachment_metadata(
        self, 
        message_id: str, 
        attachment_id: str
    ) -> Dict[str, Any]:
        """Get detailed metadata for a voice attachment.

        Args:
            message_id: Message ID
            attachment_id: Attachment ID

        Returns:
            Dictionary containing attachment metadata

        Raises:
            ValidationError: If attachment is not found or not a voice file
            AuthenticationError: If retrieval fails
        """
        try:
            attachments = await self.mail_repository.get_attachments(message_id)
            target_attachment = None
            
            for attachment in attachments:
                if attachment.id == attachment_id:
                    target_attachment = attachment
                    break
            
            if not target_attachment:
                raise ValidationError("Attachment not found")
            
            if not self.is_voice_attachment(target_attachment):
                raise ValidationError("Attachment is not a voice/audio file")

            # Build metadata dictionary
            metadata = {
                "messageId": message_id,
                "attachmentId": attachment_id,
                "name": target_attachment.name,
                "contentType": target_attachment.contentType,
                "size": target_attachment.size,
                "isInline": target_attachment.isInline,
                "lastModifiedDateTime": target_attachment.lastModifiedDateTime.isoformat() if target_attachment.lastModifiedDateTime else None,
                "isVoiceAttachment": True
            }

            # Try to extract audio-specific metadata
            audio_metadata = await self._extract_audio_metadata(target_attachment)
            metadata.update(audio_metadata)

            # Add file extension info
            if target_attachment.name:
                ext = Path(target_attachment.name).suffix.lower()
                metadata["fileExtension"] = ext
                metadata["detectedAudioFormat"] = self._get_audio_format_from_extension(ext)

            logger.info(f"Retrieved metadata for voice attachment {attachment_id}")
            return metadata

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to get voice attachment metadata: {str(e)}")
            raise AuthenticationError(f"Failed to get metadata: {str(e)}")

    async def get_voice_statistics(self, folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive statistics about voice messages and attachments.

        Args:
            folder_id: Optional folder ID (if None, analyzes entire mailbox)

        Returns:
            Dictionary with voice attachment statistics

        Raises:
            AuthenticationError: If analysis fails
        """
        try:
            logger.info("Generating voice attachment statistics...")
            
            # Get basic folder statistics
            folder_stats = await self.mail_service.get_folder_statistics(folder_id)
            
            # Get detailed voice message data
            voice_messages = await self.find_all_voice_messages(folder_id, limit=500)
            
            # Analyze voice attachments
            total_voice_attachments = 0
            content_type_counts = {}
            extension_counts = {}
            total_voice_size = 0
            duration_total = 0.0
            duration_count = 0

            for message in voice_messages:
                voice_attachments = await self.extract_voice_attachments_from_message(message.id)
                total_voice_attachments += len(voice_attachments)
                
                for voice_att in voice_attachments:
                    # Count content types
                    content_type = voice_att.contentType
                    content_type_counts[content_type] = content_type_counts.get(content_type, 0) + 1
                    
                    # Count extensions
                    if voice_att.name:
                        ext = Path(voice_att.name).suffix.lower()
                        if ext:
                            extension_counts[ext] = extension_counts.get(ext, 0) + 1
                    
                    # Sum sizes
                    total_voice_size += voice_att.size
                    
                    # Sum durations if available
                    if voice_att.duration:
                        duration_total += voice_att.duration
                        duration_count += 1

            # Calculate averages
            avg_voice_size = total_voice_size / total_voice_attachments if total_voice_attachments > 0 else 0
            avg_duration = duration_total / duration_count if duration_count > 0 else 0

            statistics = {
                "folderInfo": {
                    "folderId": folder_stats.folderId,
                    "folderName": folder_stats.folderName,
                    "totalMessages": folder_stats.totalMessages,
                    "messagesWithAttachments": folder_stats.messagesWithAttachments
                },
                "voiceMessages": {
                    "totalVoiceMessages": len(voice_messages),
                    "voiceMessagePercentage": (len(voice_messages) / folder_stats.totalMessages * 100) if folder_stats.totalMessages > 0 else 0
                },
                "voiceAttachments": {
                    "totalVoiceAttachments": total_voice_attachments,
                    "totalVoiceSize": total_voice_size,
                    "totalVoiceSizeMB": round(total_voice_size / (1024 * 1024), 2),
                    "averageVoiceSize": round(avg_voice_size),
                    "averageVoiceSizeMB": round(avg_voice_size / (1024 * 1024), 2),
                    "averageDurationSeconds": round(avg_duration, 1),
                    "averageDurationMinutes": round(avg_duration / 60, 1)
                },
                "contentTypes": dict(sorted(content_type_counts.items(), key=lambda x: x[1], reverse=True)),
                "fileExtensions": dict(sorted(extension_counts.items(), key=lambda x: x[1], reverse=True)),
                "analysis": {
                    "mostCommonContentType": max(content_type_counts.items(), key=lambda x: x[1])[0] if content_type_counts else "None",
                    "mostCommonExtension": max(extension_counts.items(), key=lambda x: x[1])[0] if extension_counts else "None",
                    "hasMetadata": duration_count > 0
                }
            }

            logger.info(f"Generated voice statistics: {total_voice_attachments} attachments in {len(voice_messages)} messages")
            return statistics

        except Exception as e:
            logger.error(f"Failed to generate voice statistics: {str(e)}")
            raise AuthenticationError(f"Failed to generate statistics: {str(e)}")

    def is_voice_attachment(self, attachment: Attachment) -> bool:
        """Check if an attachment is a voice/audio file.

        Args:
            attachment: Attachment to check

        Returns:
            True if it's a voice attachment, False otherwise
        """
        # Check content type
        if attachment.contentType:
            content_type = attachment.contentType.lower().strip()
            
            # Direct match in our audio types
            if content_type in self.AUDIO_CONTENT_TYPES:
                return True
            
            # Check if it starts with 'audio/'
            if content_type.startswith('audio/'):
                return True
            
            # Handle content types with parameters (e.g., "audio/mpeg; codecs=mp3")
            base_type = content_type.split(';')[0].strip()
            if base_type in self.AUDIO_CONTENT_TYPES or base_type.startswith('audio/'):
                return True

        # Check file extension if content type is not definitive
        if attachment.name:
            name_lower = attachment.name.lower()
            if any(name_lower.endswith(ext) for ext in self.AUDIO_EXTENSIONS):
                return True

        return False

    async def _extract_audio_metadata(self, attachment: Attachment) -> Dict[str, Any]:
        """Extract audio metadata from attachment (placeholder for future enhancement).

        Args:
            attachment: Audio attachment

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}
        
        # Basic content type analysis
        if attachment.contentType:
            content_type = attachment.contentType.lower()
            
            # Estimate quality based on content type
            if 'flac' in content_type or 'wav' in content_type:
                metadata["estimatedQuality"] = "lossless"
            elif 'mp3' in content_type or 'aac' in content_type:
                metadata["estimatedQuality"] = "compressed"
            elif 'amr' in content_type or '3gpp' in content_type:
                metadata["estimatedQuality"] = "voice_optimized"
        
        # Size-based duration estimation (very rough)
        if attachment.size:
            # Rough estimation: assume 128 kbps average bitrate
            estimated_duration = attachment.size * 8 / (128 * 1000)  # seconds
            if estimated_duration > 0 and estimated_duration < 7200:  # Less than 2 hours seems reasonable
                metadata["estimatedDuration"] = round(estimated_duration, 1)
        
        return metadata

    def _get_extension_from_content_type(self, content_type: Optional[str]) -> str:
        """Get appropriate file extension from content type.

        Args:
            content_type: MIME content type

        Returns:
            File extension with dot prefix
        """
        if not content_type:
            return ".bin"
        
        content_type = content_type.lower()
        
        extension_map = {
            'audio/mpeg': '.mp3',
            'audio/mp3': '.mp3',
            'audio/wav': '.wav',
            'audio/wave': '.wav',
            'audio/ogg': '.ogg',
            'audio/m4a': '.m4a',
            'audio/aac': '.aac',
            'audio/webm': '.webm',
            'audio/amr': '.amr',
            'audio/3gpp': '.3gp',
            'audio/flac': '.flac',
            'audio/aiff': '.aiff'
        }
        
        return extension_map.get(content_type, '.audio')

    def _get_audio_format_from_extension(self, extension: str) -> str:
        """Get audio format name from file extension.

        Args:
            extension: File extension (with or without dot)

        Returns:
            Human-readable format name
        """
        ext = extension.lower().lstrip('.')
        
        format_map = {
            'mp3': 'MP3 (MPEG Audio)',
            'wav': 'WAV (Waveform Audio)',
            'ogg': 'OGG Vorbis',
            'm4a': 'M4A (MPEG-4 Audio)',
            'aac': 'AAC (Advanced Audio Coding)',
            'webm': 'WebM Audio',
            'amr': 'AMR (Adaptive Multi-Rate)',
            '3gp': '3GPP Audio',
            'flac': 'FLAC (Free Lossless Audio)',
            'aiff': 'AIFF (Audio Interchange File)',
            'wma': 'WMA (Windows Media Audio)',
            'au': 'AU (Audio File Format)'
        }
        
        return format_map.get(ext, f'{ext.upper()} Audio')

    # Shared Mailbox Voice Attachment Methods

    async def find_voice_messages_in_shared_mailbox(
        self,
        email_address: str,
        folder_id: Optional[str] = None,
        limit: int = 100
    ) -> List[SharedMailboxMessage]:
        """Find all voice messages in a shared mailbox.

        Args:
            email_address: Shared mailbox email address
            folder_id: Optional folder ID to search within
            limit: Maximum number of messages to check

        Returns:
            List of shared mailbox messages containing voice attachments

        Raises:
            AuthenticationError: If search fails
            ValidationError: If shared mailbox repository not configured
        """
        if not self.shared_mailbox_repository:
            raise ValidationError("Shared mailbox repository not configured")

        try:
            # Get messages with attachments from shared mailbox
            messages_response = await self.shared_mailbox_repository.get_shared_mailbox_messages(
                email_address=email_address,
                folder_id=folder_id,
                has_attachments=True,
                top=limit
            )

            voice_messages = []
            
            # Check each message for voice attachments
            for message in messages_response.value:
                if message.hasAttachments:
                    try:
                        attachments = await self.shared_mailbox_repository.get_shared_mailbox_attachments(
                            email_address, message.id
                        )
                        
                        # Check if any attachment is a voice file
                        has_voice = any(self.is_voice_attachment(att) for att in attachments)
                        if has_voice:
                            # Ensure message is a SharedMailboxMessage instance
                            if isinstance(message, SharedMailboxMessage):
                                voice_messages.append(message)
                            else:
                                # Convert to SharedMailboxMessage if needed
                                voice_message = SharedMailboxMessage(
                                    **message.dict(),
                                    sharedMailboxId=email_address,
                                    sharedMailboxName=email_address.split('@')[0],
                                    sharedMailboxEmail=email_address
                                )
                                voice_messages.append(voice_message)
                    except Exception as e:
                        logger.warning(f"Failed to check attachments for message {message.id}: {str(e)}")
                        continue

            logger.info(f"Found {len(voice_messages)} voice messages in shared mailbox {email_address}")
            return voice_messages

        except Exception as e:
            logger.error(f"Failed to find voice messages in shared mailbox {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to find voice messages: {str(e)}")

    async def extract_voice_attachments_from_shared_mailbox_message(
        self,
        email_address: str,
        message_id: str
    ) -> List[VoiceAttachment]:
        """Extract voice attachments from a shared mailbox message.

        Args:
            email_address: Shared mailbox email address
            message_id: Message ID

        Returns:
            List of voice attachments found

        Raises:
            AuthenticationError: If extraction fails
            ValidationError: If shared mailbox repository not configured
        """
        if not self.shared_mailbox_repository:
            raise ValidationError("Shared mailbox repository not configured")

        try:
            attachments = await self.shared_mailbox_repository.get_shared_mailbox_attachments(
                email_address, message_id
            )
            voice_attachments = []

            for attachment in attachments:
                if self.is_voice_attachment(attachment):
                    voice_attachment = VoiceAttachment(
                        messageId=message_id,
                        attachmentId=attachment.id,
                        name=attachment.name,
                        contentType=attachment.contentType or "unknown",
                        size=attachment.size
                    )
                    
                    # Try to extract additional metadata
                    metadata = await self._extract_audio_metadata(attachment)
                    voice_attachment.duration = metadata.get("duration")
                    voice_attachment.sampleRate = metadata.get("sampleRate")
                    voice_attachment.bitRate = metadata.get("bitRate")
                    
                    voice_attachments.append(voice_attachment)

            logger.info(f"Extracted {len(voice_attachments)} voice attachments from shared mailbox message {message_id}")
            return voice_attachments

        except Exception as e:
            logger.error(f"Failed to extract voice attachments from shared mailbox message {message_id}: {str(e)}")
            raise AuthenticationError(f"Failed to extract voice attachments: {str(e)}")

    async def organize_voice_messages_in_shared_mailbox(
        self,
        email_address: str,
        target_folder_name: str = "Voice Messages",
        source_folder_id: Optional[str] = None
    ) -> OrganizeSharedMailboxResponse:
        """Organize voice messages in a shared mailbox into a dedicated folder.

        Args:
            email_address: Shared mailbox email address
            target_folder_name: Name of folder to organize voice messages into
            source_folder_id: Optional source folder to search in

        Returns:
            Organization response with detailed statistics

        Raises:
            AuthenticationError: If organization fails
            ValidationError: If shared mailbox repository not configured
        """
        if not self.shared_mailbox_repository:
            raise ValidationError("Shared mailbox repository not configured")

        try:
            logger.info(f"Starting voice message organization in shared mailbox {email_address}")
            
            start_time = datetime.utcnow()
            errors = []
            messages_processed = 0
            messages_moved = 0
            folders_created = 0
            
            # Get or create target folder
            folders = await self.shared_mailbox_repository.get_shared_mailbox_folders(email_address)
            target_folder = None
            
            for folder in folders:
                if folder.displayName.lower() == target_folder_name.lower():
                    target_folder = folder
                    break
            
            if not target_folder:
                target_folder = await self.shared_mailbox_repository.create_shared_mailbox_folder(
                    email_address, target_folder_name
                )
                folders_created = 1
            
            # Find voice messages
            voice_messages = await self.find_voice_messages_in_shared_mailbox(
                email_address, source_folder_id, limit=200
            )
            
            # Move each voice message to target folder
            for message in voice_messages:
                messages_processed += 1
                try:
                    # Check if message is already in target folder
                    if message.parentFolderId == target_folder.id:
                        continue
                    
                    await self.shared_mailbox_repository.move_shared_mailbox_message(
                        email_address, message.id, target_folder.id
                    )
                    messages_moved += 1
                    logger.info(f"Moved voice message '{message.subject}' to {target_folder_name}")
                    
                except Exception as e:
                    error_msg = f"Failed to move message {message.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            response = OrganizeSharedMailboxResponse(
                mailboxId=email_address,
                mailboxName=email_address.split('@')[0],
                messagesProcessed=messages_processed,
                messagesMoved=messages_moved,
                foldersCreated=folders_created,
                targetFolderId=target_folder.id,
                processingTimeMs=processing_time,
                errors=errors
            )
            
            logger.info(f"Voice message organization completed in shared mailbox {email_address}: {messages_moved}/{messages_processed} messages moved")
            return response

        except Exception as e:
            logger.error(f"Failed to organize voice messages in shared mailbox {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to organize voice messages: {str(e)}")

    async def get_voice_statistics_for_shared_mailbox(
        self, 
        email_address: str,
        folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get voice attachment statistics for a shared mailbox.

        Args:
            email_address: Shared mailbox email address
            folder_id: Optional folder ID to analyze

        Returns:
            Dictionary with voice attachment statistics

        Raises:
            AuthenticationError: If analysis fails
            ValidationError: If shared mailbox repository not configured
        """
        if not self.shared_mailbox_repository:
            raise ValidationError("Shared mailbox repository not configured")

        try:
            logger.info(f"Generating voice statistics for shared mailbox {email_address}")
            
            # Get voice messages
            voice_messages = await self.find_voice_messages_in_shared_mailbox(
                email_address, folder_id, limit=500
            )
            
            # Get all messages for comparison
            all_messages_response = await self.shared_mailbox_repository.get_shared_mailbox_messages(
                email_address=email_address,
                folder_id=folder_id,
                top=1000
            )
            
            # Analyze voice attachments
            total_voice_attachments = 0
            content_type_counts = {}
            extension_counts = {}
            total_voice_size = 0
            duration_total = 0.0
            duration_count = 0

            for message in voice_messages:
                voice_attachments = await self.extract_voice_attachments_from_shared_mailbox_message(
                    email_address, message.id
                )
                total_voice_attachments += len(voice_attachments)
                
                for voice_att in voice_attachments:
                    # Count content types
                    content_type = voice_att.contentType
                    content_type_counts[content_type] = content_type_counts.get(content_type, 0) + 1
                    
                    # Count extensions
                    if voice_att.name:
                        ext = Path(voice_att.name).suffix.lower()
                        if ext:
                            extension_counts[ext] = extension_counts.get(ext, 0) + 1
                    
                    # Sum sizes
                    total_voice_size += voice_att.size
                    
                    # Sum durations if available
                    if voice_att.duration:
                        duration_total += voice_att.duration
                        duration_count += 1

            # Calculate averages
            avg_voice_size = total_voice_size / total_voice_attachments if total_voice_attachments > 0 else 0
            avg_duration = duration_total / duration_count if duration_count > 0 else 0
            total_messages = len(all_messages_response.value)

            statistics = {
                "sharedMailbox": {
                    "emailAddress": email_address,
                    "displayName": email_address.split('@')[0],
                    "folderId": folder_id,
                    "totalMessages": total_messages
                },
                "voiceMessages": {
                    "totalVoiceMessages": len(voice_messages),
                    "voiceMessagePercentage": (len(voice_messages) / total_messages * 100) if total_messages > 0 else 0
                },
                "voiceAttachments": {
                    "totalVoiceAttachments": total_voice_attachments,
                    "totalVoiceSize": total_voice_size,
                    "totalVoiceSizeMB": round(total_voice_size / (1024 * 1024), 2),
                    "averageVoiceSize": round(avg_voice_size),
                    "averageVoiceSizeMB": round(avg_voice_size / (1024 * 1024), 2),
                    "averageDurationSeconds": round(avg_duration, 1),
                    "averageDurationMinutes": round(avg_duration / 60, 1)
                },
                "contentTypes": dict(sorted(content_type_counts.items(), key=lambda x: x[1], reverse=True)),
                "fileExtensions": dict(sorted(extension_counts.items(), key=lambda x: x[1], reverse=True)),
                "analysis": {
                    "mostCommonContentType": max(content_type_counts.items(), key=lambda x: x[1])[0] if content_type_counts else "None",
                    "mostCommonExtension": max(extension_counts.items(), key=lambda x: x[1])[0] if extension_counts else "None",
                    "hasMetadata": duration_count > 0
                }
            }

            logger.info(f"Generated voice statistics for shared mailbox {email_address}: {total_voice_attachments} attachments in {len(voice_messages)} messages")
            return statistics

        except Exception as e:
            logger.error(f"Failed to generate voice statistics for shared mailbox {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to generate statistics: {str(e)}")

    async def find_voice_messages_across_shared_mailboxes(
        self,
        mailbox_addresses: List[str],
        limit_per_mailbox: int = 50
    ) -> Dict[str, List[SharedMailboxMessage]]:
        """Find voice messages across multiple shared mailboxes.

        Args:
            mailbox_addresses: List of shared mailbox email addresses
            limit_per_mailbox: Maximum messages to check per mailbox

        Returns:
            Dictionary mapping mailbox addresses to their voice messages

        Raises:
            ValidationError: If shared mailbox repository not configured
        """
        if not self.shared_mailbox_repository:
            raise ValidationError("Shared mailbox repository not configured")

        try:
            results = {}
            
            # Process each mailbox concurrently
            import asyncio
            
            async def process_mailbox(email_address: str) -> Tuple[str, List[SharedMailboxMessage]]:
                try:
                    voice_messages = await self.find_voice_messages_in_shared_mailbox(
                        email_address, limit=limit_per_mailbox
                    )
                    return email_address, voice_messages
                except Exception as e:
                    logger.warning(f"Failed to process mailbox {email_address}: {str(e)}")
                    return email_address, []
            
            # Execute all mailbox searches concurrently
            tasks = [process_mailbox(addr) for addr in mailbox_addresses]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results_list:
                if isinstance(result, tuple):
                    email_address, voice_messages = result
                    results[email_address] = voice_messages
                else:
                    logger.error(f"Error processing mailbox: {str(result)}")
            
            total_voice_messages = sum(len(messages) for messages in results.values())
            logger.info(f"Found {total_voice_messages} voice messages across {len(mailbox_addresses)} shared mailboxes")
            
            return results

        except Exception as e:
            logger.error(f"Failed to find voice messages across shared mailboxes: {str(e)}")
            raise AuthenticationError(f"Failed to search shared mailboxes: {str(e)}")