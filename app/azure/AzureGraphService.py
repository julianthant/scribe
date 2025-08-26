"""
AzureGraphService.py - Microsoft Graph API Base Service

Provides base Microsoft Graph API operations for mail and folders.
This service handles:
- Mail folder operations (get, create)
- Message operations (get, move, update)
- Message attachment operations (get, download)
- Base Graph API utility methods

The AzureGraphService class serves as the base interface for Graph API operations.
"""

from typing import Optional, Dict, Any
import logging
import base64

import httpx

from app.core.Exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class AzureGraphService:
    """Microsoft Graph API service for mail operations."""

    async def get_mail_folders(self, access_token: str) -> Dict[str, Any]:
        """Get all mail folders from Microsoft Graph API.

        Args:
            access_token: Valid access token

        Returns:
            Mail folders data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/mailFolders",
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access mail folders")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve mail folders")

            folders_data = response.json()
            logger.info(f"Retrieved {len(folders_data.get('value', []))} mail folders")
            return folders_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting mail folders: {str(e)}")
            raise AuthenticationError("Failed to retrieve mail folders")

    async def create_mail_folder(
        self, 
        access_token: str, 
        folder_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new mail folder.

        Args:
            access_token: Valid access token
            folder_data: Folder creation data

        Returns:
            Created folder data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Determine parent endpoint
            parent_id = folder_data.get("parentFolderId")
            if parent_id:
                url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{parent_id}/childFolders"
            else:
                url = "https://graph.microsoft.com/v1.0/me/mailFolders"

            request_body = {
                "displayName": folder_data["displayName"]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to create mail folder")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to create mail folder")

            folder_data = response.json()
            logger.info(f"Created mail folder: {folder_data.get('displayName')}")
            return folder_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating mail folder: {str(e)}")
            raise AuthenticationError("Failed to create mail folder")

    async def get_messages(
        self, 
        access_token: str,
        folder_id: Optional[str] = None,
        filter_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get messages from a mail folder or mailbox.

        Args:
            access_token: Valid access token
            folder_id: Optional folder ID (defaults to all messages)
            filter_params: Optional query parameters for filtering

        Returns:
            Messages data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Build URL
            if folder_id:
                url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/messages"
            else:
                url = "https://graph.microsoft.com/v1.0/me/messages"

            # Build query parameters
            params = {}
            if filter_params:
                if "top" in filter_params:
                    params["$top"] = filter_params["top"]
                if "skip" in filter_params:
                    params["$skip"] = filter_params["skip"]
                if "orderby" in filter_params:
                    params["$orderby"] = filter_params["orderby"]
                if "select" in filter_params:
                    params["$select"] = ",".join(filter_params["select"])
                if "filter" in filter_params:
                    params["$filter"] = filter_params["filter"]
                if "expand" in filter_params:
                    params["$expand"] = filter_params["expand"]

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access messages")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve messages")

            messages_data = response.json()
            logger.info(f"Retrieved {len(messages_data.get('value', []))} messages")
            return messages_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting messages: {str(e)}")
            raise AuthenticationError("Failed to retrieve messages")

    async def get_message_attachments(
        self, 
        access_token: str, 
        message_id: str
    ) -> Dict[str, Any]:
        """Get attachments for a specific message.

        Args:
            access_token: Valid access token
            message_id: Message ID

        Returns:
            Attachments data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access attachments")
            elif response.status_code == 404:
                raise AuthenticationError("Message not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve attachments")

            attachments_data = response.json()
            logger.info(f"Retrieved {len(attachments_data.get('value', []))} attachments for message {message_id}")
            return attachments_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting attachments: {str(e)}")
            raise AuthenticationError("Failed to retrieve attachments")

    async def download_attachment(
        self, 
        access_token: str, 
        message_id: str, 
        attachment_id: str
    ) -> bytes:
        """Download attachment content.

        Args:
            access_token: Valid access token
            message_id: Message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # First get attachment metadata
            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_id}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access attachment")
            elif response.status_code == 404:
                raise AuthenticationError("Attachment not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve attachment")

            attachment_data = response.json()
            
            # For file attachments, content is in contentBytes (base64 encoded)
            if attachment_data.get("@odata.type") == "#microsoft.graph.fileAttachment":
                content_bytes = attachment_data.get("contentBytes")
                if content_bytes:
                    logger.info(f"Downloaded attachment {attachment_id} from message {message_id}")
                    return base64.b64decode(content_bytes)
                else:
                    raise AuthenticationError("No content available for attachment")
            else:
                # For other attachment types, might need to use /$value endpoint
                value_url = f"{url}/$value"
                async with httpx.AsyncClient() as client:
                    value_response = await client.get(
                        value_url,
                        headers=headers,
                        timeout=30.0
                    )
                
                if value_response.is_success:
                    logger.info(f"Downloaded attachment {attachment_id} from message {message_id}")
                    return value_response.content
                else:
                    raise AuthenticationError("Failed to download attachment content")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error downloading attachment: {str(e)}")
            raise AuthenticationError("Failed to download attachment")

    async def move_message(
        self, 
        access_token: str, 
        message_id: str, 
        destination_folder_id: str
    ) -> Dict[str, Any]:
        """Move a message to a different folder.

        Args:
            access_token: Valid access token
            message_id: Message ID
            destination_folder_id: Destination folder ID

        Returns:
            Updated message data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/move"

            request_body = {
                "destinationId": destination_folder_id
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to move message")
            elif response.status_code == 404:
                raise AuthenticationError("Message or folder not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to move message")

            message_data = response.json()
            logger.info(f"Moved message {message_id} to folder {destination_folder_id}")
            return message_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error moving message: {str(e)}")
            raise AuthenticationError("Failed to move message")

    async def update_message(
        self, 
        access_token: str, 
        message_id: str, 
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update message properties.

        Args:
            access_token: Valid access token
            message_id: Message ID
            updates: Dictionary of properties to update

        Returns:
            Updated message data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url,
                    headers=headers,
                    json=updates,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to update message")
            elif response.status_code == 404:
                raise AuthenticationError("Message not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to update message")

            message_data = response.json()
            logger.info(f"Updated message {message_id}")
            return message_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating message: {str(e)}")
            raise AuthenticationError("Failed to update message")


# Global instance
azure_graph_service = AzureGraphService()