"""
mail_repository.py - Mail Data Access Repository

Provides data access layer for mail operations using Microsoft Graph API.
This repository handles:
- Direct Graph API integration for mail folder operations
- Message retrieval, creation, updating, and deletion
- Attachment handling and download operations
- Folder management and hierarchy operations
- Message search and filtering
- Raw API response to model conversion
- Error handling and authentication management

The MailRepository class abstracts Graph API calls and provides a clean interface
for the mail service layer to perform email operations.
"""

from typing import List, Optional, Dict, Any
import logging

from app.azure.AzureGraphService import azure_graph_service
from app.core.Exceptions import AuthenticationError, AuthorizationError
from app.models.MailModel import (
    MailFolder, Message, MessageListResponse, Attachment,
    FileAttachment, ItemAttachment, ReferenceAttachment
)

logger = logging.getLogger(__name__)


class MailRepository:
    """Repository for mail operations using Microsoft Graph API."""

    def __init__(self, access_token: str):
        """Initialize mail repository with access token."""
        self.access_token = access_token

    async def get_folders(self) -> List[MailFolder]:
        """Get all mail folders.

        Returns:
            List of mail folders

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            folders_data = await azure_graph_service.get_mail_folders(self.access_token)
            
            folders = []
            for folder_data in folders_data.get("value", []):
                folder = MailFolder(
                    id=folder_data["id"],
                    displayName=folder_data["displayName"],
                    parentFolderId=folder_data.get("parentFolderId"),
                    childFolderCount=folder_data.get("childFolderCount", 0),
                    unreadItemCount=folder_data.get("unreadItemCount", 0),
                    totalItemCount=folder_data.get("totalItemCount", 0),
                    isHidden=folder_data.get("isHidden", False)
                )
                folders.append(folder)
            
            return folders

        except Exception as e:
            logger.error(f"Error retrieving mail folders: {str(e)}")
            raise

    async def create_folder(
        self, 
        name: str, 
        parent_id: Optional[str] = None
    ) -> MailFolder:
        """Create a new mail folder.

        Args:
            name: Folder name
            parent_id: Optional parent folder ID

        Returns:
            Created mail folder

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            folder_data = {
                "displayName": name
            }
            if parent_id:
                folder_data["parentFolderId"] = parent_id

            created_folder_data = await azure_graph_service.create_mail_folder(
                self.access_token, folder_data
            )
            
            return MailFolder(
                id=created_folder_data["id"],
                displayName=created_folder_data["displayName"],
                parentFolderId=created_folder_data.get("parentFolderId"),
                childFolderCount=created_folder_data.get("childFolderCount", 0),
                unreadItemCount=created_folder_data.get("unreadItemCount", 0),
                totalItemCount=created_folder_data.get("totalItemCount", 0),
                isHidden=created_folder_data.get("isHidden", False)
            )

        except Exception as e:
            logger.error(f"Error creating mail folder '{name}': {str(e)}")
            raise

    async def get_messages(
        self,
        folder_id: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        top: int = 25,
        skip: int = 0,
        orderby: str = "receivedDateTime DESC",
        select: Optional[List[str]] = None
    ) -> MessageListResponse:
        """Get messages from a folder or mailbox.

        Args:
            folder_id: Optional folder ID
            has_attachments: Optional filter for messages with attachments
            top: Number of messages to return
            skip: Number of messages to skip
            orderby: Sort order
            select: List of properties to select

        Returns:
            Message list response with pagination

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            filter_params: dict[str, int | str] = {
                "top": top,
                "skip": skip
            }

            if select:
                filter_params["select"] = ",".join(select)

            # Build OData filter
            filters = []
            if has_attachments is not None:
                filters.append(f"hasAttachments eq {str(has_attachments).lower()}")

            if filters:
                filter_params["filter"] = " and ".join(filters)
                # Remove orderby when filtering by attachments to avoid InefficientFilter error
            else:
                filter_params["orderby"] = orderby

            messages_data = await azure_graph_service.get_messages(
                self.access_token, folder_id, filter_params
            )

            messages = []
            for message_data in messages_data.get("value", []):
                message = self._parse_message_data(message_data)
                messages.append(message)

            return MessageListResponse(
                value=messages,
                **{"@odata.nextLink": messages_data.get("@odata.nextLink")},
                **{"@odata.count": messages_data.get("@odata.count")}
            )

        except Exception as e:
            logger.error(f"Error retrieving messages: {str(e)}")
            raise

    async def get_message_by_id(self, message_id: str) -> Message:
        """Get a specific message by ID.

        Args:
            message_id: Message ID

        Returns:
            Message object

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            # Get single message by using filter with top=1
            filter_params: dict[str, int | str] = {
                "top": 1,
                "filter": f"id eq '{message_id}'"
            }

            messages_data = await azure_graph_service.get_messages(
                self.access_token, None, filter_params
            )

            message_list = messages_data.get("value", [])
            if not message_list:
                raise AuthenticationError("Message not found")

            return self._parse_message_data(message_list[0])

        except Exception as e:
            logger.error(f"Error retrieving message {message_id}: {str(e)}")
            raise

    async def get_attachments(self, message_id: str) -> List[Attachment]:
        """Get all attachments for a message.

        Args:
            message_id: Message ID

        Returns:
            List of attachments

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            attachments_data = await azure_graph_service.get_message_attachments(
                self.access_token, message_id
            )

            attachments = []
            for attachment_data in attachments_data.get("value", []):
                try:
                    attachment = self._parse_attachment_data(attachment_data)
                    attachments.append(attachment)
                except Exception as e:
                    logger.warning(f"Failed to parse attachment data: {str(e)}, skipping attachment")
                    # Skip this attachment and continue with the rest
                    continue

            return attachments

        except Exception as e:
            logger.error(f"Error retrieving attachments for message {message_id}: {str(e)}")
            raise

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment content.

        Args:
            message_id: Message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            return await azure_graph_service.download_attachment(
                self.access_token, message_id, attachment_id
            )

        except Exception as e:
            logger.error(f"Error downloading attachment {attachment_id}: {str(e)}")
            raise

    async def move_message(self, message_id: str, destination_folder_id: str) -> bool:
        """Move a message to a different folder.

        Args:
            message_id: Message ID
            destination_folder_id: Destination folder ID

        Returns:
            True if successful

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            await azure_graph_service.move_message(
                self.access_token, message_id, destination_folder_id
            )
            return True

        except Exception as e:
            logger.error(f"Error moving message {message_id}: {str(e)}")
            raise

    async def mark_as_read(self, message_id: str, is_read: bool = True) -> bool:
        """Mark a message as read or unread.

        Args:
            message_id: Message ID
            is_read: Whether to mark as read (True) or unread (False)

        Returns:
            True if successful

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            updates = {"isRead": is_read}
            await azure_graph_service.update_message(
                self.access_token, message_id, updates
            )
            return True

        except Exception as e:
            logger.error(f"Error updating read status for message {message_id}: {str(e)}")
            raise

    async def search_messages(
        self,
        query: str,
        folder_id: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        top: int = 25,
        skip: int = 0
    ) -> MessageListResponse:
        """Search messages with a query.

        Args:
            query: Search query
            folder_id: Optional folder to search in
            has_attachments: Optional filter for messages with attachments
            top: Number of messages to return
            skip: Number of messages to skip

        Returns:
            Message list response with search results

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            filter_params: dict[str, int | str] = {
                "top": top,
                "skip": skip
            }

            # Build OData filter with search query
            filters = [f"contains(subject,'{query}') or contains(bodyPreview,'{query}')"]
            
            if has_attachments is not None:
                filters.append(f"hasAttachments eq {str(has_attachments).lower()}")

            filter_params["filter"] = " and ".join(filters)
            
            # Only add orderby if not filtering by attachments to avoid InefficientFilter error
            if has_attachments is None:
                filter_params["orderby"] = "receivedDateTime DESC"

            messages_data = await azure_graph_service.get_messages(
                self.access_token, folder_id, filter_params
            )

            messages = []
            for message_data in messages_data.get("value", []):
                message = self._parse_message_data(message_data)
                messages.append(message)

            return MessageListResponse(
                value=messages,
                **{"@odata.nextLink": messages_data.get("@odata.nextLink")},
                **{"@odata.count": messages_data.get("@odata.count")}
            )

        except Exception as e:
            logger.error(f"Error searching messages with query '{query}': {str(e)}")
            raise

    def _parse_message_data(self, message_data: Dict[str, Any]) -> Message:
        """Parse message data from Graph API response.

        Args:
            message_data: Raw message data from API

        Returns:
            Message object
        """
        from datetime import datetime

        # Parse recipients
        def parse_recipients(recipients_data):
            recipients = []
            for recipient_data in recipients_data or []:
                from app.models.MailModel import Recipient, EmailAddress
                recipient = Recipient(
                    emailAddress=EmailAddress(
                        name=recipient_data["emailAddress"].get("name", ""),
                        address=recipient_data["emailAddress"]["address"]
                    )
                )
                recipients.append(recipient)
            return recipients

        # Parse datetime strings
        def parse_datetime(dt_str):
            if dt_str:
                try:
                    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except:
                    return None
            return None

        # Parse body
        body = None
        if message_data.get("body"):
            from app.models.MailModel import ItemBody, BodyType
            body = ItemBody(
                contentType=BodyType(message_data["body"]["contentType"]),
                content=message_data["body"]["content"]
            )

        # Parse sender
        sender = None
        if message_data.get("sender"):
            from app.models.MailModel import Recipient, EmailAddress
            sender = Recipient(
                emailAddress=EmailAddress(
                    name=message_data["sender"]["emailAddress"].get("name", ""),
                    address=message_data["sender"]["emailAddress"]["address"]
                )
            )

        # Parse from
        from_ = None
        if message_data.get("from"):
            from app.models.MailModel import Recipient, EmailAddress
            from_ = Recipient(
                emailAddress=EmailAddress(
                    name=message_data["from"]["emailAddress"].get("name", ""),
                    address=message_data["from"]["emailAddress"]["address"]
                )
            )

        from app.models.MailModel import Importance
        importance = Importance.NORMAL
        if message_data.get("importance"):
            try:
                importance = Importance(message_data["importance"])
            except ValueError:
                importance = Importance.NORMAL

        # Create message data dict with proper field names
        message_dict = {
            "id": message_data["id"],
            "subject": message_data.get("subject", ""),
            "body": body,
            "bodyPreview": message_data.get("bodyPreview", ""),
            "sender": sender,
            "from": from_,  # Use the alias name directly
            "toRecipients": parse_recipients(message_data.get("toRecipients")),
            "ccRecipients": parse_recipients(message_data.get("ccRecipients")),
            "bccRecipients": parse_recipients(message_data.get("bccRecipients")),
            "receivedDateTime": parse_datetime(message_data.get("receivedDateTime")),
            "sentDateTime": parse_datetime(message_data.get("sentDateTime")),
            "createdDateTime": parse_datetime(message_data.get("createdDateTime")),
            "lastModifiedDateTime": parse_datetime(message_data.get("lastModifiedDateTime")),
            "hasAttachments": message_data.get("hasAttachments", False),
            "importance": importance,
            "isRead": message_data.get("isRead", False),
            "isDraft": message_data.get("isDraft", False),
            "parentFolderId": message_data.get("parentFolderId"),
            "conversationId": message_data.get("conversationId"),
            "internetMessageId": message_data.get("internetMessageId"),
            "webLink": message_data.get("webLink")
        }
        
        return Message.model_validate(message_dict)

    def _parse_attachment_data(self, attachment_data: Dict[str, Any]) -> Attachment:
        """Parse attachment data from Graph API response.

        Args:
            attachment_data: Raw attachment data from API

        Returns:
            Attachment object
        """
        from datetime import datetime

        def parse_datetime(dt_str):
            if dt_str:
                try:
                    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except:
                    return None
            return None

        odata_type = attachment_data.get("@odata.type", "#microsoft.graph.fileAttachment")
        
        common_props = {
            "id": attachment_data["id"],
            "name": attachment_data.get("name", ""),
            "contentType": attachment_data.get("contentType"),
            "size": attachment_data.get("size", 0),
            "isInline": attachment_data.get("isInline", False),
            "lastModifiedDateTime": parse_datetime(attachment_data.get("lastModifiedDateTime")),
            "@odata.type": odata_type
        }

        if odata_type == "#microsoft.graph.fileAttachment":
            return FileAttachment(
                **common_props,
                contentBytes=attachment_data.get("contentBytes"),
                contentId=attachment_data.get("contentId"),
                contentLocation=attachment_data.get("contentLocation")
            )
        elif odata_type == "#microsoft.graph.itemAttachment":
            return ItemAttachment(
                **common_props,
                item=attachment_data.get("item")
            )
        elif odata_type == "#microsoft.graph.referenceAttachment":
            return ReferenceAttachment(
                **common_props,
                sourceUrl=attachment_data.get("sourceUrl"),
                providerType=attachment_data.get("providerType"),
                permission=attachment_data.get("permission")
            )
        else:
            # Default to FileAttachment if type is unknown
            return FileAttachment(
                **common_props,
                contentBytes=attachment_data.get("contentBytes"),
                contentId=attachment_data.get("contentId"),
                contentLocation=attachment_data.get("contentLocation")
            )