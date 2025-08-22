"""
mail_service.py - Mail Business Logic Service

Provides business logic layer for mail operations with validation and processing.
This service handles:
- Mail folder listing, creation, and management
- Message retrieval, search, and filtering
- Voice attachment detection and organization
- Message operations (move, update, delete)
- Attachment processing and download
- Folder statistics and analytics
- Business rule validation and enforcement
- Error handling and logging

The MailService class orchestrates mail repository operations and implements
business logic while maintaining separation of concerns from the API layer.
"""

from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime

from app.repositories.mail_repository import MailRepository
from app.core.exceptions import AuthenticationError, ValidationError
from app.models.mail import (
    MailFolder, Message, MessageListResponse, Attachment,
    FileAttachment, VoiceAttachment, FolderStatistics,
    CreateFolderRequest, MoveMessageRequest, UpdateMessageRequest,
    AttachmentFilter, SearchMessagesRequest, OrganizeVoiceResponse
)

logger = logging.getLogger(__name__)


class MailService:
    """Service for mail operations and business logic."""

    # Audio content types for voice attachment detection
    AUDIO_CONTENT_TYPES = {
        'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg',
        'audio/m4a', 'audio/aac', 'audio/webm', 'audio/amr',
        'audio/3gpp', 'audio/x-m4a', 'audio/x-wav', 'audio/flac',
        'audio/aiff', 'audio/au', 'audio/basic', 'audio/midi',
        'audio/x-aiff', 'audio/x-au', 'audio/x-midi'
    }

    def __init__(self, mail_repository: MailRepository):
        """Initialize mail service with repository."""
        self.mail_repository = mail_repository

    async def list_mail_folders(self) -> List[MailFolder]:
        """Get all mail folders with hierarchy.

        Returns:
            List of mail folders

        Raises:
            AuthenticationError: If retrieval fails
        """
        try:
            folders = await self.mail_repository.get_folders()
            logger.info(f"Retrieved {len(folders)} mail folders")
            return folders

        except Exception as e:
            logger.error(f"Failed to list mail folders: {str(e)}")
            raise

    async def create_mail_folder(
        self, 
        request: CreateFolderRequest
    ) -> MailFolder:
        """Create a new mail folder.

        Args:
            request: Folder creation request

        Returns:
            Created mail folder

        Raises:
            ValidationError: If request is invalid
            AuthenticationError: If creation fails
        """
        try:
            if not request.displayName.strip():
                raise ValidationError("Folder name cannot be empty")

            folder = await self.mail_repository.create_folder(
                request.displayName.strip(),
                request.parentFolderId
            )
            
            logger.info(f"Created mail folder: {folder.displayName}")
            return folder

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create folder '{request.displayName}': {str(e)}")
            raise AuthenticationError(f"Failed to create folder: {str(e)}")

    async def get_or_create_folder(self, name: str) -> MailFolder:
        """Get existing folder by name or create if it doesn't exist.

        Args:
            name: Folder name

        Returns:
            Mail folder (existing or newly created)

        Raises:
            AuthenticationError: If operation fails
        """
        try:
            # Get all folders and look for existing one
            folders = await self.list_mail_folders()
            
            for folder in folders:
                if folder.displayName.lower() == name.lower():
                    logger.info(f"Found existing folder: {folder.displayName}")
                    return folder

            # Create new folder if not found
            request = CreateFolderRequest(displayName=name)
            folder = await self.create_mail_folder(request)
            logger.info(f"Created new folder: {folder.displayName}")
            return folder

        except Exception as e:
            logger.error(f"Failed to get or create folder '{name}': {str(e)}")
            raise

    async def get_inbox_messages(
        self, 
        top: int = 25, 
        skip: int = 0
    ) -> MessageListResponse:
        """Get messages from inbox.

        Args:
            top: Number of messages to return
            skip: Number of messages to skip

        Returns:
            Message list response

        Raises:
            AuthenticationError: If retrieval fails
        """
        try:
            # Get inbox folder first
            folders = await self.list_mail_folders()
            inbox_folder = None
            
            for folder in folders:
                if folder.displayName.lower() == "inbox":
                    inbox_folder = folder
                    break
            
            if not inbox_folder:
                raise AuthenticationError("Inbox folder not found")

            messages = await self.mail_repository.get_messages(
                folder_id=inbox_folder.id,
                top=top,
                skip=skip
            )
            
            logger.info(f"Retrieved {len(messages.value)} inbox messages")
            return messages

        except Exception as e:
            logger.error(f"Failed to get inbox messages: {str(e)}")
            raise

    async def get_messages_with_attachments(
        self, 
        folder_id: Optional[str] = None,
        top: int = 25,
        skip: int = 0
    ) -> MessageListResponse:
        """Get messages that have attachments.

        Args:
            folder_id: Optional folder ID to search in
            top: Number of messages to return
            skip: Number of messages to skip

        Returns:
            Message list response with messages containing attachments

        Raises:
            AuthenticationError: If retrieval fails
        """
        try:
            messages = await self.mail_repository.get_messages(
                folder_id=folder_id,
                has_attachments=True,
                top=top,
                skip=skip
            )
            
            logger.info(f"Retrieved {len(messages.value)} messages with attachments")
            return messages

        except Exception as e:
            logger.error(f"Failed to get messages with attachments: {str(e)}")
            raise

    async def get_messages_with_voice_attachments(
        self, 
        folder_id: Optional[str] = None,
        top: int = 100,
        skip: int = 0
    ) -> Tuple[MessageListResponse, List[VoiceAttachment]]:
        """Get messages that have voice/audio attachments.

        Args:
            folder_id: Optional folder ID to search in
            top: Number of messages to return
            skip: Number of messages to skip

        Returns:
            Tuple of (message list response, list of voice attachments)

        Raises:
            AuthenticationError: If retrieval fails
        """
        try:
            # First get messages with attachments
            messages = await self.mail_repository.get_messages(
                folder_id=folder_id,
                has_attachments=True,
                top=top,
                skip=skip
            )

            voice_messages = []
            voice_attachments = []

            # Check each message for voice attachments
            for message in messages.value:
                if message.hasAttachments:
                    try:
                        attachments = await self.mail_repository.get_attachments(message.id)
                        message_voice_attachments = []
                        
                        for attachment in attachments:
                            if self._is_voice_attachment(attachment):
                                voice_attachment = VoiceAttachment(
                                    messageId=message.id,
                                    attachmentId=attachment.id,
                                    name=attachment.name,
                                    contentType=attachment.contentType or "",
                                    size=attachment.size
                                )
                                message_voice_attachments.append(voice_attachment)
                                voice_attachments.append(voice_attachment)
                        
                        if message_voice_attachments:
                            # Add attachments to message
                            message.attachments = attachments
                            voice_messages.append(message)
                    
                    except Exception as e:
                        logger.warning(f"Failed to process attachments for message {message.id}: {str(e)}")
                        # Continue with next message
                        continue

            # Create response with only voice messages
            voice_message_response = MessageListResponse(
                value=voice_messages,
                odata_nextLink=messages.odata_nextLink,
                odata_count=len(voice_messages)
            )

            logger.info(f"Found {len(voice_messages)} messages with {len(voice_attachments)} voice attachments")
            return voice_message_response, voice_attachments

        except Exception as e:
            logger.error(f"Failed to get messages with voice attachments: {str(e)}")
            raise

    async def extract_voice_attachments(self, message_id: str) -> List[VoiceAttachment]:
        """Extract all voice/audio attachments from a message.

        Args:
            message_id: Message ID

        Returns:
            List of voice attachments

        Raises:
            AuthenticationError: If extraction fails
        """
        try:
            attachments = await self.mail_repository.get_attachments(message_id)
            voice_attachments = []

            for attachment in attachments:
                if self._is_voice_attachment(attachment):
                    voice_attachment = VoiceAttachment(
                        messageId=message_id,
                        attachmentId=attachment.id,
                        name=attachment.name,
                        contentType=attachment.contentType or "",
                        size=attachment.size
                    )
                    voice_attachments.append(voice_attachment)

            logger.info(f"Extracted {len(voice_attachments)} voice attachments from message {message_id}")
            return voice_attachments

        except Exception as e:
            logger.error(f"Failed to extract voice attachments from message {message_id}: {str(e)}")
            raise

    async def download_voice_attachment(
        self, 
        message_id: str, 
        attachment_id: str
    ) -> bytes:
        """Download voice attachment content.

        Args:
            message_id: Message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes

        Raises:
            ValidationError: If attachment is not a voice attachment
            AuthenticationError: If download fails
        """
        try:
            # First verify it's a voice attachment
            attachments = await self.mail_repository.get_attachments(message_id)
            target_attachment = None
            
            for attachment in attachments:
                if attachment.id == attachment_id:
                    target_attachment = attachment
                    break
            
            if not target_attachment:
                raise ValidationError("Attachment not found")
            
            if not self._is_voice_attachment(target_attachment):
                raise ValidationError("Attachment is not a voice/audio file")

            content = await self.mail_repository.download_attachment(message_id, attachment_id)
            logger.info(f"Downloaded voice attachment {attachment_id} ({len(content)} bytes)")
            return content

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to download voice attachment {attachment_id}: {str(e)}")
            raise AuthenticationError(f"Failed to download voice attachment: {str(e)}")

    async def organize_voice_messages(
        self, 
        target_folder_name: str = "Voice Messages"
    ) -> OrganizeVoiceResponse:
        """Auto-organize messages with voice attachments into a folder.

        Args:
            target_folder_name: Name of target folder for voice messages

        Returns:
            Organization response with statistics

        Raises:
            AuthenticationError: If organization fails
        """
        try:
            errors = []
            messages_processed = 0
            messages_moved = 0
            voice_attachments_found = 0
            folder_created = False

            # Get or create target folder
            try:
                target_folder = await self.get_or_create_folder(target_folder_name)
                if not any(folder.displayName == target_folder_name 
                          for folder in await self.list_mail_folders()):
                    folder_created = True
            except Exception as e:
                error_msg = f"Failed to create target folder: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                raise AuthenticationError(error_msg)

            # Get all messages with attachments (larger batch for processing)
            try:
                messages_response, voice_attachments = await self.get_messages_with_voice_attachments(
                    top=200  # Process more messages at once
                )
                voice_attachments_found = len(voice_attachments)
                
                # Move each message with voice attachments
                for message in messages_response.value:
                    messages_processed += 1
                    
                    try:
                        # Check if message is already in target folder
                        if message.parentFolderId == target_folder.id:
                            continue
                        
                        await self.mail_repository.move_message(message.id, target_folder.id)
                        messages_moved += 1
                        logger.info(f"Moved message '{message.subject}' to {target_folder_name}")
                        
                    except Exception as e:
                        error_msg = f"Failed to move message {message.id}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        
            except Exception as e:
                error_msg = f"Failed to process voice messages: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

            response = OrganizeVoiceResponse(
                messagesProcessed=messages_processed,
                messagesMoved=messages_moved,
                voiceAttachmentsFound=voice_attachments_found,
                folderCreated=folder_created,
                targetFolderId=target_folder.id,
                errors=errors
            )

            logger.info(f"Voice message organization completed: {messages_moved}/{messages_processed} messages moved")
            return response

        except Exception as e:
            logger.error(f"Failed to organize voice messages: {str(e)}")
            raise

    async def move_message_to_folder(
        self, 
        message_id: str, 
        folder_name: str
    ) -> bool:
        """Move message to a named folder.

        Args:
            message_id: Message ID
            folder_name: Target folder name

        Returns:
            True if successful

        Raises:
            ValidationError: If folder not found
            AuthenticationError: If move fails
        """
        try:
            # Find folder by name
            folders = await self.list_mail_folders()
            target_folder = None
            
            for folder in folders:
                if folder.displayName.lower() == folder_name.lower():
                    target_folder = folder
                    break
            
            if not target_folder:
                raise ValidationError(f"Folder '{folder_name}' not found")

            success = await self.mail_repository.move_message(message_id, target_folder.id)
            
            if success:
                logger.info(f"Moved message {message_id} to folder '{folder_name}'")
            
            return success

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to move message to folder '{folder_name}': {str(e)}")
            raise AuthenticationError(f"Failed to move message: {str(e)}")

    async def search_messages(
        self, 
        request: SearchMessagesRequest
    ) -> MessageListResponse:
        """Search messages with various filters.

        Args:
            request: Search request with query and filters

        Returns:
            Message list response with search results

        Raises:
            ValidationError: If request is invalid
            AuthenticationError: If search fails
        """
        try:
            if not request.query.strip():
                raise ValidationError("Search query cannot be empty")

            messages = await self.mail_repository.search_messages(
                query=request.query.strip(),
                folder_id=request.folderId,
                has_attachments=request.hasAttachments,
                top=request.top,
                skip=request.skip
            )

            # If filtering by voice attachments, check each message
            if request.hasVoiceAttachments:
                filtered_messages = []
                for message in messages.value:
                    if message.hasAttachments:
                        attachments = await self.mail_repository.get_attachments(message.id)
                        has_voice = any(self._is_voice_attachment(att) for att in attachments)
                        if has_voice:
                            message.attachments = attachments
                            filtered_messages.append(message)
                
                messages.value = filtered_messages
                messages.odata_count = len(filtered_messages)

            logger.info(f"Search for '{request.query}' returned {len(messages.value)} results")
            return messages

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to search messages: {str(e)}")
            raise AuthenticationError(f"Search failed: {str(e)}")

    async def mark_message_as_read(
        self, 
        message_id: str, 
        is_read: bool = True
    ) -> bool:
        """Mark message as read or unread.

        Args:
            message_id: Message ID
            is_read: Whether to mark as read (True) or unread (False)

        Returns:
            True if successful

        Raises:
            AuthenticationError: If update fails
        """
        try:
            success = await self.mail_repository.mark_as_read(message_id, is_read)
            
            if success:
                status = "read" if is_read else "unread"
                logger.info(f"Marked message {message_id} as {status}")
            
            return success

        except Exception as e:
            logger.error(f"Failed to mark message as read: {str(e)}")
            raise AuthenticationError(f"Failed to update message: {str(e)}")

    async def get_folder_statistics(self, folder_id: Optional[str] = None) -> FolderStatistics:
        """Get statistics for a folder or entire mailbox.

        Args:
            folder_id: Optional folder ID (if None, gets stats for entire mailbox)

        Returns:
            Folder statistics

        Raises:
            AuthenticationError: If retrieval fails
        """
        try:
            # Get all messages in folder
            messages = await self.mail_repository.get_messages(
                folder_id=folder_id,
                top=1000  # Get a large batch for statistics
            )

            folder_name = "Entire Mailbox"
            if folder_id:
                folders = await self.list_mail_folders()
                folder = next((f for f in folders if f.id == folder_id), None)
                if folder:
                    folder_name = folder.displayName

            total_messages = len(messages.value)
            unread_messages = sum(1 for msg in messages.value if not msg.isRead)
            messages_with_attachments = sum(1 for msg in messages.value if msg.hasAttachments)
            
            # Count voice messages by checking attachments
            voice_messages = 0
            total_attachment_size = 0
            
            for message in messages.value:
                if message.hasAttachments:
                    try:
                        attachments = await self.mail_repository.get_attachments(message.id)
                        has_voice = any(self._is_voice_attachment(att) for att in attachments)
                        if has_voice:
                            voice_messages += 1
                        total_attachment_size += sum(att.size for att in attachments)
                    except Exception:
                        # Skip messages where we can't get attachments
                        continue

            stats = FolderStatistics(
                folderId=folder_id or "mailbox",
                folderName=folder_name,
                totalMessages=total_messages,
                unreadMessages=unread_messages,
                messagesWithAttachments=messages_with_attachments,
                voiceMessages=voice_messages,
                totalAttachmentSize=total_attachment_size
            )

            logger.info(f"Generated statistics for {folder_name}: {total_messages} messages, {voice_messages} voice messages")
            return stats

        except Exception as e:
            logger.error(f"Failed to get folder statistics: {str(e)}")
            raise AuthenticationError(f"Failed to get statistics: {str(e)}")

    def _is_voice_attachment(self, attachment: Attachment) -> bool:
        """Check if an attachment is a voice/audio file.

        Args:
            attachment: Attachment to check

        Returns:
            True if it's a voice attachment
        """
        if not attachment.contentType:
            return False
        
        # Check if content type is in our audio types set
        content_type = attachment.contentType.lower()
        
        # Direct match
        if content_type in self.AUDIO_CONTENT_TYPES:
            return True
        
        # Check if it starts with 'audio/'
        if content_type.startswith('audio/'):
            return True
        
        # Check common audio file extensions in the name
        if attachment.name:
            name_lower = attachment.name.lower()
            audio_extensions = {
                '.mp3', '.wav', '.ogg', '.m4a', '.aac', '.webm', 
                '.amr', '.3gp', '.flac', '.aiff', '.au', '.mid'
            }
            if any(name_lower.endswith(ext) for ext in audio_extensions):
                return True
        
        return False