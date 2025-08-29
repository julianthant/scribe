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
from datetime import datetime, timedelta

from app.services.MailService import MailService
from app.repositories.MailRepository import MailRepository
from app.repositories.SharedMailboxRepository import SharedMailboxRepository
from app.repositories.VoiceAttachmentRepository import VoiceAttachmentRepository
from app.azure.AzureBlobService import AzureBlobService
from app.core.Exceptions import ValidationError, AuthenticationError
from app.core.config import settings
from app.models.MailModel import (
    VoiceAttachment, Message, Attachment, FileAttachment,
    OrganizeVoiceResponse, FolderStatistics
)
from app.models.SharedMailboxModel import (
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
        voice_attachment_repository: VoiceAttachmentRepository,
        blob_service: AzureBlobService,
        shared_mailbox_repository: Optional[SharedMailboxRepository] = None
    ):
        """Initialize voice attachment service.
        
        Args:
            mail_service: Mail service instance
            mail_repository: Mail repository instance
            voice_attachment_repository: Voice attachment repository instance
            blob_service: Azure blob storage service instance
            shared_mailbox_repository: Optional shared mailbox repository instance
        """
        self.mail_service = mail_service
        self.mail_repository = mail_repository
        self.voice_attachment_repository = voice_attachment_repository
        self.blob_service = blob_service
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
                        size=attachment.size,
                        duration=None,
                        sampleRate=None,
                        bitRate=None
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
            content_type_counts: dict[str, int] = {}
            extension_counts: dict[str, int] = {}
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
        metadata: dict[str, str | float | int] = {}
        
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

    # Blob Storage Methods

    async def store_voice_attachment_in_blob(
        self,
        message_id: str,
        attachment_id: str,
        user_id: str,
        sender_name: Optional[str] = None,
        subject: Optional[str] = None,
        received_at: Optional[datetime] = None
    ) -> str:
        """Download voice attachment from Graph API and store in blob storage.
        
        Args:
            message_id: Graph API message ID
            attachment_id: Graph API attachment ID
            user_id: User storing the attachment
            sender_name: Optional sender name
            subject: Optional email subject
            received_at: Optional received timestamp
            
        Returns:
            Blob name of stored attachment
            
        Raises:
            ValidationError: If attachment validation fails
            AuthenticationError: If storage fails
        """
        try:
            # Check if already stored
            existing = await self.voice_attachment_repository.get_by_graph_api_ids(
                user_id, message_id, attachment_id
            )
            if existing and existing.storage_status == "stored":
                logger.info(f"Voice attachment already stored: {existing.blob_name}")
                return existing.blob_name
            
            # Get attachment metadata
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
            
            # Download attachment content from Graph API
            content = await self.mail_repository.download_attachment(message_id, attachment_id)
            
            # Generate blob name
            blob_name = self.blob_service.generate_blob_name(
                message_id=message_id,
                attachment_id=attachment_id,
                original_filename=target_attachment.name,
                user_id=user_id
            )
            
            # Get container name from settings
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            
            # Prepare metadata
            metadata = {
                "user_id": user_id,
                "message_id": message_id,
                "attachment_id": attachment_id,
                "original_filename": target_attachment.name or "",
                "sender_name": sender_name or "",
                "subject": subject or ""
            }
            
            # Upload to blob storage
            blob_url = await self.blob_service.upload_voice_attachment(
                content=content,
                blob_name=blob_name,
                content_type=target_attachment.contentType or "audio/mpeg",
                metadata=metadata
            )
            
            # Get additional metadata for database
            message = await self.mail_repository.get_message_by_id(message_id)
            
            # Store metadata in database
            voice_attachment = await self.voice_attachment_repository.create_voice_attachment(
                user_id=user_id,
                azure_message_id=message_id,
                azure_attachment_id=attachment_id,
                blob_name=blob_name,
                blob_container=container_name,
                original_filename=target_attachment.name or f"attachment_{attachment_id}",
                content_type=target_attachment.contentType or "audio/mpeg",
                size_bytes=target_attachment.size,
                sender_email=message.from_.emailAddress.address if message.from_ else "",
                subject=message.subject if message else subject or "Unknown",
                received_at=message.receivedDateTime if message and message.receivedDateTime else received_at or datetime.utcnow(),
                blob_url=blob_url,
                sender_name=sender_name or (message.from_.emailAddress.name if message and message.from_ else ""),
            )
            
            logger.info(f"Stored voice attachment in blob: {blob_name} ({len(content)} bytes)")
            return blob_name
            
        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to store voice attachment in blob: {str(e)}")
            raise AuthenticationError(f"Failed to store voice attachment: {str(e)}")
    
    async def download_voice_attachment_from_blob(
        self,
        blob_name: str,
        user_id: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Download voice attachment from blob storage.
        
        Args:
            blob_name: Blob storage name
            user_id: User requesting download
            client_ip: Optional client IP for tracking
            user_agent: Optional user agent for tracking
            
        Returns:
            Tuple of (content bytes, metadata dict)
            
        Raises:
            ValidationError: If blob not found
            AuthenticationError: If download fails
        """
        try:
            start_time = datetime.utcnow()
            
            # Get voice attachment metadata from database
            voice_attachment = await self.voice_attachment_repository.get_by_blob_name(
                blob_name, user_id
            )
            if not voice_attachment:
                raise ValidationError(
                    f"Voice attachment {blob_name} not found or not accessible",
                    error_code="VOICE_ATTACHMENT_NOT_FOUND"
                )
            
            # Check if user has access (must be the owner)
            if voice_attachment.user_id != user_id:
                raise ValidationError(
                    "Access denied: You can only download your own voice attachments",
                    error_code="ACCESS_DENIED"
                )
            
            # Download from blob storage
            content = await self.blob_service.download_voice_attachment(blob_name)
            
            # Calculate download duration
            download_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Record download in database
            await self.voice_attachment_repository.record_download(
                attachment_id=voice_attachment.id,
                user_id=user_id,
                download_method="blob_stream",
                download_size_bytes=len(content),
                client_ip=client_ip,
                user_agent=user_agent,
                download_duration_ms=int(download_duration),
                success=True
            )
            
            # Prepare metadata for response
            metadata = {
                "filename": voice_attachment.original_filename,
                "content_type": voice_attachment.content_type,
                "size": len(content),
                "received_at": voice_attachment.received_at.isoformat(),
                "sender_email": voice_attachment.sender_email,
                "sender_name": voice_attachment.sender_name,
                "subject": voice_attachment.subject,
                "download_count": voice_attachment.download_count + 1  # Updated count
            }
            
            return content, metadata
            
        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to download voice attachment from blob: {str(e)}")
            raise AuthenticationError(f"Failed to download voice attachment: {str(e)}")
    
    async def list_stored_voice_attachments(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        content_type_filter: Optional[str] = None,
        order_by: str = "received_at"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List stored voice attachments for a user.
        
        Args:
            user_id: User ID
            limit: Maximum results to return
            offset: Number of results to skip
            content_type_filter: Optional content type filter
            order_by: Field to order by
            
        Returns:
            Tuple of (attachment list, total count)
        """
        try:
            attachments, total_count = await self.voice_attachment_repository.list_user_attachments(
                user_id=user_id,
                limit=limit,
                offset=offset,
                status_filter="stored",
                content_type_filter=content_type_filter,
                order_by=order_by,
                order_direction="desc"
            )
            
            # Convert to response format
            attachment_list = []
            for attachment in attachments:
                attachment_dict = {
                    "id": attachment.id,
                    "blob_name": attachment.blob_name,
                    "original_filename": attachment.original_filename,
                    "content_type": attachment.content_type,
                    "size_bytes": attachment.size_bytes,
                    "size_mb": round(attachment.size_bytes / (1024 * 1024), 2),
                    "duration_seconds": attachment.duration_seconds,
                    "sender_email": attachment.sender_email,
                    "sender_name": attachment.sender_name,
                    "subject": attachment.subject,
                    "received_at": attachment.received_at.isoformat(),
                    "stored_at": attachment.created_at.isoformat(),
                    "download_count": attachment.download_count,
                    "last_downloaded_at": attachment.last_downloaded_at.isoformat() if attachment.last_downloaded_at else None,
                    "expires_at": attachment.expires_at.isoformat() if attachment.expires_at else None
                }
                attachment_list.append(attachment_dict)
            
            logger.info(f"Listed {len(attachment_list)} stored voice attachments for user {user_id}")
            return attachment_list, total_count
            
        except Exception as e:
            logger.error(f"Failed to list stored voice attachments: {str(e)}")
            raise AuthenticationError(f"Failed to list stored voice attachments: {str(e)}")
    
    async def delete_stored_voice_attachment(
        self,
        blob_name: str,
        user_id: str
    ) -> bool:
        """Delete stored voice attachment from blob storage and database.
        
        Args:
            blob_name: Blob storage name
            user_id: User requesting deletion
            
        Returns:
            True if successful
            
        Raises:
            ValidationError: If attachment not found
            AuthenticationError: If deletion fails
        """
        try:
            # Get voice attachment metadata from database
            voice_attachment = await self.voice_attachment_repository.get_by_blob_name(
                blob_name, user_id
            )
            if not voice_attachment:
                raise ValidationError(
                    f"Voice attachment {blob_name} not found or not accessible",
                    error_code="VOICE_ATTACHMENT_NOT_FOUND"
                )
            
            # Check if user has access (must be the owner)
            if voice_attachment.user_id != user_id:
                raise ValidationError(
                    "Access denied: You can only delete your own voice attachments",
                    error_code="ACCESS_DENIED"
                )
            
            # Delete from blob storage
            await self.blob_service.delete_voice_attachment(blob_name)
            
            # Mark as deleted in database
            await self.voice_attachment_repository.mark_as_deleted(voice_attachment.id)
            
            logger.info(f"Deleted stored voice attachment: {blob_name}")
            return True
            
        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to delete stored voice attachment: {str(e)}")
            raise AuthenticationError(f"Failed to delete stored voice attachment: {str(e)}")
    
    async def get_voice_attachment_storage_statistics(
        self,
        user_id: Optional[str] = None,
        days_ago: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get voice attachment storage statistics.
        
        Args:
            user_id: Optional user filter
            days_ago: Optional filter for recent data
            
        Returns:
            Storage statistics dictionary
        """
        try:
            statistics = await self.voice_attachment_repository.get_statistics(
                user_id=user_id,
                days_ago=days_ago
            )
            
            # Add additional computed statistics
            if statistics["total_attachments"] > 0:
                statistics["average_downloads_per_attachment"] = round(
                    statistics["total_downloads"] / statistics["total_attachments"], 1
                )
            else:
                statistics["average_downloads_per_attachment"] = 0
            
            # Storage efficiency metrics
            storage_efficiency = {
                "stored_percentage": round(
                    (statistics["stored_attachments"] / statistics["total_attachments"] * 100) 
                    if statistics["total_attachments"] > 0 else 0, 1
                ),
                "deleted_percentage": round(
                    (statistics["deleted_attachments"] / statistics["total_attachments"] * 100) 
                    if statistics["total_attachments"] > 0 else 0, 1
                )
            }
            statistics["storage_efficiency"] = storage_efficiency
            
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get storage statistics: {str(e)}")
            raise AuthenticationError(f"Failed to get storage statistics: {str(e)}")
    
    async def cleanup_expired_voice_attachments(
        self,
        max_age_days: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Clean up expired voice attachments from both blob storage and database.
        
        Args:
            max_age_days: Maximum age in days (default from settings)
            dry_run: If True, only return count without deleting
            
        Returns:
            Dictionary with cleanup statistics
            
        Raises:
            AuthenticationError: If cleanup fails
        """
        try:
            logger.info(f"Starting voice attachment cleanup (dry_run={dry_run})")
            
            # Get expired attachments from database
            cutoff_date = None
            if max_age_days is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            expired_attachments = await self.voice_attachment_repository.get_expired_attachments(
                cutoff_date=cutoff_date,
                limit=1000
            )
            
            blob_deletion_count = 0
            db_update_count = 0
            errors = []
            
            if not dry_run:
                for attachment in expired_attachments:
                    try:
                        # Delete from blob storage
                        await self.blob_service.delete_voice_attachment(attachment.blob_name)
                        blob_deletion_count += 1
                        
                        # Mark as deleted in database
                        await self.voice_attachment_repository.mark_as_deleted(attachment.id)
                        db_update_count += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to cleanup attachment {attachment.blob_name}: {str(e)}"
                        errors.append(error_msg)
                        logger.warning(error_msg)
            
            cleanup_stats = {
                "expired_found": len(expired_attachments),
                "blobs_deleted": blob_deletion_count,
                "database_updated": db_update_count,
                "errors": len(errors),
                "error_details": errors,
                "dry_run": dry_run
            }
            
            logger.info(f"Voice attachment cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired voice attachments: {str(e)}")
            raise AuthenticationError(f"Failed to cleanup expired voice attachments: {str(e)}")

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
                        size=attachment.size,
                        duration=None,
                        sampleRate=None,
                        bitRate=None
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
            content_type_counts: dict[str, int] = {}
            extension_counts: dict[str, int] = {}
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