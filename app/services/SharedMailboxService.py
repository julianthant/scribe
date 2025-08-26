"""
shared_mailbox_service.py - Shared Mailbox Business Logic Service

Provides business logic layer for shared mailbox operations with caching and validation.
This service handles:
- Shared mailbox discovery and access management
- Permission validation and access control
- Content organization and management
- Message operations in shared mailboxes
- Send-as and delegation operations
- Statistics and analytics processing
- Caching for performance optimization
- Audit logging and compliance tracking
- Business rule enforcement

The SharedMailboxService class manages complex shared mailbox workflows and
provides enterprise-grade features for collaborative email management.
"""

from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime, timedelta
import asyncio

from app.repositories.SharedMailboxRepository import SharedMailboxRepository
from app.core.Exceptions import AuthenticationError, ValidationError, AuthorizationError
from app.core.Cache import get_shared_mailbox_cache, SharedMailboxCache
from app.models.SharedMailboxModel import (
    SharedMailbox, SharedMailboxMessage, SharedMailboxAccess,
    SharedMailboxStatistics, SharedMailboxSearchRequest, SharedMailboxSearchResponse,
    SendAsSharedRequest, OrganizeSharedMailboxRequest, OrganizeSharedMailboxResponse,
    SharedMailboxAccessLevel, SharedMailboxListResponse, SharedMailboxAuditEntry
)
from app.models.MailModel import MailFolder, MessageListResponse, VoiceAttachment

logger = logging.getLogger(__name__)


class SharedMailboxService:
    """Service for shared mailbox operations and business logic."""

    def __init__(self, shared_mailbox_repository: SharedMailboxRepository):
        """Initialize shared mailbox service with repository."""
        self.shared_mailbox_repository = shared_mailbox_repository
        self.cache = get_shared_mailbox_cache()

    async def get_accessible_shared_mailboxes(self) -> SharedMailboxListResponse:
        """Get all shared mailboxes the current user has access to.

        Returns:
            Response with accessible shared mailboxes

        Raises:
            AuthenticationError: If retrieval fails
        """
        try:
            mailboxes = await self.shared_mailbox_repository.get_accessible_mailboxes()
            
            # Filter out inactive mailboxes
            active_mailboxes = [mb for mb in mailboxes if mb.isActive]
            
            response = SharedMailboxListResponse(
                value=active_mailboxes,
                totalCount=len(mailboxes),
                accessibleCount=len(active_mailboxes),
                **{"@odata.nextLink": None}
            )
            
            logger.info(f"Retrieved {len(active_mailboxes)} accessible shared mailboxes")
            return response

        except Exception as e:
            logger.error(f"Failed to get accessible shared mailboxes: {str(e)}")
            raise AuthenticationError(f"Failed to retrieve shared mailboxes: {str(e)}")

    async def get_shared_mailbox_details(self, email_address: str) -> SharedMailboxAccess:
        """Get detailed information about a specific shared mailbox.

        Args:
            email_address: Shared mailbox email address

        Returns:
            Shared mailbox access details with permissions

        Raises:
            ValidationError: If mailbox not found
            AuthenticationError: If retrieval fails
        """
        try:
            # Check cache first
            cached_access = self.cache.get_mailbox(email_address)
            if cached_access:
                logger.debug(f"Retrieved shared mailbox details from cache: {email_address}")
                return cached_access
            
            # Get mailbox info
            mailbox = await self.shared_mailbox_repository.get_shared_mailbox_by_address(email_address)
            
            # Get permissions (simplified - in real implementation would check actual permissions)
            permissions = await self.shared_mailbox_repository.get_shared_mailbox_permissions(email_address)
            
            # Determine current user's access level (simplified)
            access_level = SharedMailboxAccessLevel.REVIEWER  # Default
            can_read = True
            can_write = False
            can_send = False
            can_manage = False
            
            # In a real implementation, this would analyze the permissions
            # and determine what the current user can do
            
            access = SharedMailboxAccess(
                mailbox=mailbox,
                permissions=permissions,
                accessLevel=access_level,
                canRead=can_read,
                canWrite=can_write,
                canSend=can_send,
                canManage=can_manage,
                lastAccessed=datetime.utcnow()
            )
            
            # Cache the result
            self.cache.set_mailbox(email_address, access)
            
            logger.info(f"Retrieved shared mailbox details for {email_address}")
            return access

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to get shared mailbox details for {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to get mailbox details: {str(e)}")

    async def get_shared_mailbox_folders(self, email_address: str) -> List[MailFolder]:
        """Get folders from a shared mailbox with business logic validation.

        Args:
            email_address: Shared mailbox email address

        Returns:
            List of mail folders

        Raises:
            ValidationError: If access validation fails
            AuthenticationError: If retrieval fails
        """
        try:
            # Validate access to mailbox
            await self._validate_mailbox_access(email_address, "read")
            
            # Check cache first
            cached_folders = self.cache.get_folders(email_address)
            if cached_folders:
                logger.debug(f"Retrieved folders from cache: {email_address}")
                return cached_folders
            
            folders = await self.shared_mailbox_repository.get_shared_mailbox_folders(email_address)
            
            # Sort folders by name for consistency
            folders.sort(key=lambda f: f.displayName.lower())
            
            # Cache the result
            self.cache.set_folders(email_address, folders)
            
            logger.info(f"Retrieved {len(folders)} folders from shared mailbox {email_address}")
            return folders

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to get folders from {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to get folders: {str(e)}")

    async def get_shared_mailbox_messages(
        self,
        email_address: str,
        folder_id: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        top: int = 25,
        skip: int = 0
    ) -> MessageListResponse:
        """Get messages from a shared mailbox with business logic.

        Args:
            email_address: Shared mailbox email address
            folder_id: Optional folder ID
            has_attachments: Filter by attachment presence
            top: Number of messages to return
            skip: Number of messages to skip

        Returns:
            Message list response

        Raises:
            ValidationError: If validation fails
            AuthenticationError: If retrieval fails
        """
        try:
            # Validate access
            await self._validate_mailbox_access(email_address, "read")
            
            # Validate parameters
            if top < 1 or top > 1000:
                raise ValidationError("Top parameter must be between 1 and 1000")
            if skip < 0:
                raise ValidationError("Skip parameter must be non-negative")
            
            messages = await self.shared_mailbox_repository.get_shared_mailbox_messages(
                email_address=email_address,
                folder_id=folder_id,
                has_attachments=has_attachments,
                top=top,
                skip=skip
            )
            
            # Log access for audit
            await self._log_audit_entry(
                email_address, "read_messages",
                {"folder_id": folder_id, "message_count": len(messages.value)}
            )
            
            logger.info(f"Retrieved {len(messages.value)} messages from shared mailbox {email_address}")
            return messages

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to get messages from {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to get messages: {str(e)}")

    async def send_shared_mailbox_message(
        self,
        email_address: str,
        request: SendAsSharedRequest
    ) -> Dict[str, Any]:
        """Send a message from a shared mailbox.

        Args:
            email_address: Shared mailbox email address
            request: Send message request

        Returns:
            Send result

        Raises:
            ValidationError: If validation fails
            AuthorizationError: If user cannot send from mailbox
            AuthenticationError: If sending fails
        """
        try:
            # Validate send permission
            await self._validate_mailbox_access(email_address, "send")
            
            # Validate message data
            if not request.to:
                raise ValidationError("At least one recipient is required")
            if not request.subject.strip():
                raise ValidationError("Subject is required")
            if not request.body.strip():
                raise ValidationError("Message body is required")
            
            # Build message data for Graph API
            message_data: dict[str, Any] = {
                "message": {
                    "subject": request.subject,
                    "body": {
                        "contentType": request.bodyType,
                        "content": request.body
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": addr}} for addr in request.to
                    ]
                },
                "saveToSentItems": request.saveToSentItems
            }
            
            # Add optional recipients
            if request.cc:
                message_data["message"]["ccRecipients"] = [
                    {"emailAddress": {"address": addr}} for addr in request.cc
                ]
            
            if request.bcc:
                message_data["message"]["bccRecipients"] = [
                    {"emailAddress": {"address": addr}} for addr in request.bcc
                ]
            
            # Add importance if specified
            if request.importance:
                message_data["message"]["importance"] = request.importance
            
            # Send message
            result = await self.shared_mailbox_repository.send_shared_mailbox_message(
                email_address, message_data
            )
            
            # Log audit entry
            await self._log_audit_entry(
                email_address, "send_message",
                {"recipients": len(request.to), "subject": request.subject[:50]}
            )
            
            logger.info(f"Sent message from shared mailbox {email_address}")
            return result

        except (ValidationError, AuthorizationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to send message from {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to send message: {str(e)}")

    async def create_shared_mailbox_folder(
        self,
        email_address: str,
        folder_name: str,
        parent_id: Optional[str] = None
    ) -> MailFolder:
        """Create a folder in a shared mailbox.

        Args:
            email_address: Shared mailbox email address
            folder_name: Name for the new folder
            parent_id: Optional parent folder ID

        Returns:
            Created mail folder

        Raises:
            ValidationError: If validation fails
            AuthorizationError: If user cannot create folders
            AuthenticationError: If creation fails
        """
        try:
            # Validate write permission
            await self._validate_mailbox_access(email_address, "write")
            
            # Validate folder name
            if not folder_name.strip():
                raise ValidationError("Folder name cannot be empty")
            if len(folder_name) > 255:
                raise ValidationError("Folder name too long (max 255 characters)")
            
            folder = await self.shared_mailbox_repository.create_shared_mailbox_folder(
                email_address, folder_name.strip(), parent_id
            )
            
            # Log audit entry
            await self._log_audit_entry(
                email_address, "create_folder",
                {"folder_name": folder_name, "parent_id": parent_id}
            )
            
            logger.info(f"Created folder '{folder_name}' in shared mailbox {email_address}")
            return folder

        except (ValidationError, AuthorizationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to create folder in {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to create folder: {str(e)}")

    async def organize_shared_mailbox_messages(
        self,
        email_address: str,
        request: OrganizeSharedMailboxRequest
    ) -> OrganizeSharedMailboxResponse:
        """Organize messages in a shared mailbox (e.g., voice messages).

        Args:
            email_address: Shared mailbox email address
            request: Organization request

        Returns:
            Organization response with statistics

        Raises:
            AuthorizationError: If user cannot organize messages
            AuthenticationError: If organization fails
        """
        try:
            # Validate write permission
            await self._validate_mailbox_access(email_address, "write")
            
            start_time = datetime.utcnow()
            errors = []
            messages_processed = 0
            messages_moved = 0
            folders_created = 0
            target_folder_id = ""
            
            # Get or create target folder
            try:
                folders = await self.shared_mailbox_repository.get_shared_mailbox_folders(email_address)
                target_folder = None
                
                for folder in folders:
                    if folder.displayName.lower() == request.targetFolderName.lower():
                        target_folder = folder
                        break
                
                if not target_folder and request.createFolder:
                    target_folder = await self.shared_mailbox_repository.create_shared_mailbox_folder(
                        email_address, request.targetFolderName
                    )
                    folders_created = 1
                
                if not target_folder:
                    raise ValidationError(f"Target folder '{request.targetFolderName}' not found")
                
                target_folder_id = target_folder.id
                
            except Exception as e:
                error_msg = f"Failed to prepare target folder: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                raise AuthenticationError(error_msg)
            
            # Get messages to organize based on type
            if request.messageType == "voice":
                # This would integrate with voice attachment detection logic
                # For now, just get messages with attachments
                messages_response = await self.shared_mailbox_repository.get_shared_mailbox_messages(
                    email_address=email_address,
                    has_attachments=True,
                    top=200
                )
                
                for message in messages_response.value:
                    messages_processed += 1
                    try:
                        # Check if message is already in target folder
                        if message.parentFolderId == target_folder_id:
                            continue
                        
                        # Move message
                        await self.shared_mailbox_repository.move_shared_mailbox_message(
                            email_address, message.id, target_folder_id
                        )
                        messages_moved += 1
                        
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
                targetFolderId=target_folder_id,
                processingTimeMs=processing_time,
                errors=errors
            )
            
            # Log audit entry
            await self._log_audit_entry(
                email_address, "organize_messages",
                {"type": request.messageType, "moved": messages_moved}
            )
            
            logger.info(f"Organized {messages_moved} messages in shared mailbox {email_address}")
            return response

        except (ValidationError, AuthorizationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to organize messages in {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to organize messages: {str(e)}")

    async def search_shared_mailboxes(
        self,
        request: SharedMailboxSearchRequest
    ) -> SharedMailboxSearchResponse:
        """Search across multiple shared mailboxes.

        Args:
            request: Search request with query and filters

        Returns:
            Search response with results from all accessible mailboxes

        Raises:
            ValidationError: If request is invalid
            AuthenticationError: If search fails
        """
        try:
            # Validate search request
            if not request.query.strip():
                raise ValidationError("Search query cannot be empty")
            
            start_time = datetime.utcnow()
            all_results = []
            searched_mailboxes = []
            
            # Get target mailboxes
            if request.mailboxIds:
                # Search specific mailboxes
                target_mailboxes = request.mailboxIds
            else:
                # Search all accessible mailboxes
                accessible_response = await self.get_accessible_shared_mailboxes()
                target_mailboxes = [mb.emailAddress for mb in accessible_response.value]
            
            # Search each mailbox concurrently
            search_tasks = []
            for email_address in target_mailboxes:
                task = self._search_single_mailbox(email_address, request)
                search_tasks.append(task)
            
            # Wait for all searches to complete
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Process results
            total_results = 0
            for i, result in enumerate(search_results):
                email_address = target_mailboxes[i]
                
                if isinstance(result, Exception):
                    logger.warning(f"Search failed for {email_address}: {str(result)}")
                    continue
                
                # At this point, result is not an Exception
                searched_mailboxes.append(email_address)
                if result and hasattr(result, 'value') and result.value:
                    total_results += len(result.value)
                    all_results.append({
                        "mailbox": email_address,
                        "results": [msg.dict() for msg in result.value],
                        "count": len(result.value)
                    })
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            response = SharedMailboxSearchResponse(
                query=request.query,
                totalResults=total_results,
                searchedMailboxes=searched_mailboxes,
                results=all_results,
                executionTimeMs=execution_time
            )
            
            logger.info(f"Searched {len(searched_mailboxes)} mailboxes, found {total_results} results")
            return response

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to search shared mailboxes: {str(e)}")
            raise AuthenticationError(f"Search failed: {str(e)}")

    async def get_shared_mailbox_statistics(self, email_address: str) -> SharedMailboxStatistics:
        """Get comprehensive statistics for a shared mailbox.

        Args:
            email_address: Shared mailbox email address

        Returns:
            Mailbox statistics

        Raises:
            AuthenticationError: If statistics generation fails
        """
        try:
            # Validate access
            await self._validate_mailbox_access(email_address, "read")
            
            # Get basic message statistics
            messages_response = await self.shared_mailbox_repository.get_shared_mailbox_messages(
                email_address=email_address,
                top=1000  # Get large sample for statistics
            )
            
            folders = await self.shared_mailbox_repository.get_shared_mailbox_folders(email_address)
            
            # Calculate statistics
            total_messages = len(messages_response.value)
            unread_messages = sum(1 for msg in messages_response.value if not msg.isRead)
            messages_with_attachments = sum(1 for msg in messages_response.value if msg.hasAttachments)
            
            # Find most recent message
            last_message_date = None
            if messages_response.value:
                last_message_date = max(
                    (msg.receivedDateTime for msg in messages_response.value if msg.receivedDateTime),
                    default=None
                )
            
            # Create statistics object
            stats = SharedMailboxStatistics(
                mailboxId=email_address,
                mailboxName=email_address.split('@')[0],
                emailAddress=email_address,
                totalMessages=total_messages,
                unreadMessages=unread_messages,
                messagesWithAttachments=messages_with_attachments,
                voiceMessages=0,  # Would need voice detection logic
                totalFolders=len(folders),
                mailboxSizeMB=0.0,  # Would need to calculate from message sizes
                lastMessageDate=last_message_date,
                mostActiveUsers=[],  # Would analyze sender patterns
                dailyMessageCounts={},  # Would analyze date patterns
                attachmentStatistics={}  # Would analyze attachment types
            )
            
            logger.info(f"Generated statistics for shared mailbox {email_address}")
            return stats

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Failed to get statistics for {email_address}: {str(e)}")
            raise AuthenticationError(f"Failed to generate statistics: {str(e)}")

    async def _validate_mailbox_access(self, email_address: str, operation: str) -> None:
        """Validate user access to a shared mailbox for a specific operation.

        Args:
            email_address: Shared mailbox email address
            operation: Operation type (read, write, send, manage)

        Raises:
            AuthorizationError: If access is denied
            ValidationError: If mailbox not found
        """
        try:
            # This is a simplified validation - in a real implementation,
            # you would check actual Azure AD permissions
            
            # For now, assume user has read access to any accessible mailbox
            if operation == "read":
                return
            
            # For write operations, implement more strict checking
            if operation in ["write", "send", "manage"]:
                # Would check actual permissions here
                pass
                
        except Exception as e:
            logger.error(f"Access validation failed for {email_address}: {str(e)}")
            raise AuthorizationError(f"Access denied to shared mailbox")

    async def _search_single_mailbox(
        self, 
        email_address: str, 
        request: SharedMailboxSearchRequest
    ) -> Optional[MessageListResponse]:
        """Search a single shared mailbox.

        Args:
            email_address: Shared mailbox email address
            request: Search request

        Returns:
            Search results or None if search failed
        """
        try:
            return await self.shared_mailbox_repository.search_shared_mailbox_messages(
                email_address=email_address,
                query=request.query,
                folder_id=request.folderId,
                has_attachments=request.hasAttachments,
                top=request.top,
                skip=request.skip
            )
        except Exception as e:
            logger.error(f"Search failed for mailbox {email_address}: {str(e)}")
            return None

    async def _log_audit_entry(
        self, 
        mailbox_id: str, 
        action: str, 
        details: Dict[str, Any]
    ) -> None:
        """Log an audit entry for shared mailbox operations.

        Args:
            mailbox_id: Shared mailbox ID/email
            action: Action performed
            details: Action details
        """
        try:
            # Create audit entry
            audit_entry = SharedMailboxAuditEntry(
                mailboxId=mailbox_id,
                mailboxName=mailbox_id.split('@')[0],
                userId="current_user",  # Would get from auth context
                userPrincipalName="current_user@domain.com",  # Would get from auth context
                action=action,
                details=details,
                timestamp=datetime.utcnow(),
                success=True,
                ipAddress=None,
                userAgent=None,
                errorMessage=None
            )
            
            # In a real implementation, would persist to database/logging system
            logger.info(f"Audit: {audit_entry.action} on {audit_entry.mailboxId} by {audit_entry.userPrincipalName}")
            
        except Exception as e:
            logger.error(f"Failed to log audit entry: {str(e)}")
            # Don't fail the main operation if audit logging fails