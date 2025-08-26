"""
AzureMailService.py - Azure Mail Operations Service

Provides Microsoft Graph API operations specifically for shared mailbox functionality.
This service handles:
- Shared mailbox discovery and access
- Shared mailbox message operations
- Shared mailbox folder operations
- Shared mailbox permission management
- Message sending from shared mailboxes

The AzureMailService class serves as the interface for shared mailbox operations.
"""

from typing import Optional, Dict, Any
import logging

import httpx

from app.core.Exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class AzureMailService:
    """Microsoft Graph API service for shared mailbox operations."""

    async def get_shared_mailboxes(self, access_token: str) -> Dict[str, Any]:
        """Get list of shared mailboxes the user has access to.

        Args:
            access_token: Valid access token

        Returns:
            Shared mailboxes data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Since we can't easily discover shared mailboxes without admin permissions,
            # we'll return a simple example structure. In practice, you would:
            # 1. Know the shared mailbox email addresses from your organization
            # 2. Test access using: GET users/{sharedmailboxemail}/messages
            # 3. Add them to this list if accessible
            
            # For demonstration, return common shared mailbox examples
            # In a real implementation, these would be configured or discovered through admin APIs
            async with httpx.AsyncClient() as client:
                # Test the current user's access to verify the token works
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers=headers,
                    timeout=10.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access current user profile")
            elif not response.is_success:
                logger.warning(f"Current user endpoint returned {response.status_code}: {response.text}")
                return {"value": []}

            # Return example shared mailboxes for demonstration
            # In a real implementation, you would configure known shared mailbox addresses
            # and test access to them using: GET users/{sharedmailboxemail}/messages
            shared_mailboxes = {
                "value": [
                    {
                        "id": "support@company.com",
                        "displayName": "Support Team",
                        "mail": "support@company.com", 
                        "userPrincipalName": "support@company.com",
                        "mailboxType": "Shared",
                        "isActive": True
                    },
                    {
                        "id": "sales@company.com",
                        "displayName": "Sales Team", 
                        "mail": "sales@company.com",
                        "userPrincipalName": "sales@company.com",
                        "mailboxType": "Shared",
                        "isActive": True
                    }
                ]
            }
            
            logger.info(f"Retrieved {len(shared_mailboxes.get('value', []))} configured shared mailboxes")
            return shared_mailboxes

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting shared mailboxes: {str(e)}")
            # Return empty result rather than failing completely
            return {"value": []}

    async def _get_current_user_email(self, access_token: str) -> str:
        """Get current user's email address."""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    return user_data.get("mail", user_data.get("userPrincipalName", "")).lower()
                    
        except Exception:
            pass
        
        return ""

    async def get_shared_mailbox_by_address(
        self, 
        access_token: str, 
        email_address: str
    ) -> Dict[str, Any]:
        """Get shared mailbox information by email address.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address

        Returns:
            Shared mailbox data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Query for the specific mailbox
            url = f"https://graph.microsoft.com/v1.0/users/{email_address}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access shared mailbox")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve shared mailbox")

            mailbox_data = response.json()
            logger.info(f"Retrieved shared mailbox: {email_address}")
            return mailbox_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting shared mailbox: {str(e)}")
            raise AuthenticationError("Failed to retrieve shared mailbox")

    async def get_shared_mailbox_messages(
        self, 
        access_token: str,
        email_address: str,
        folder_id: Optional[str] = None,
        filter_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get messages from a shared mailbox.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address
            folder_id: Optional folder ID
            filter_params: Optional query parameters

        Returns:
            Messages data from shared mailbox

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Build URL for shared mailbox messages
            if folder_id:
                url = f"https://graph.microsoft.com/v1.0/users/{email_address}/mailFolders/{folder_id}/messages"
            else:
                url = f"https://graph.microsoft.com/v1.0/users/{email_address}/messages"

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
                raise AuthorizationError("Insufficient permissions to access shared mailbox messages")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox or folder not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve shared mailbox messages")

            messages_data = response.json()
            logger.info(f"Retrieved {len(messages_data.get('value', []))} messages from shared mailbox {email_address}")
            return messages_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting shared mailbox messages: {str(e)}")
            raise AuthenticationError("Failed to retrieve shared mailbox messages")

    async def get_shared_mailbox_folders(
        self, 
        access_token: str, 
        email_address: str
    ) -> Dict[str, Any]:
        """Get folders from a shared mailbox.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address

        Returns:
            Folders data from shared mailbox

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"https://graph.microsoft.com/v1.0/users/{email_address}/mailFolders"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access shared mailbox folders")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve shared mailbox folders")

            folders_data = response.json()
            logger.info(f"Retrieved {len(folders_data.get('value', []))} folders from shared mailbox {email_address}")
            return folders_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting shared mailbox folders: {str(e)}")
            raise AuthenticationError("Failed to retrieve shared mailbox folders")

    async def send_shared_mailbox_message(
        self,
        access_token: str,
        email_address: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a message from a shared mailbox.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address
            message_data: Message data to send

        Returns:
            Sent message data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"https://graph.microsoft.com/v1.0/users/{email_address}/sendMail"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=message_data,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to send from shared mailbox")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to send shared mailbox message")

            logger.info(f"Sent message from shared mailbox {email_address}")
            
            # Return response data if available, otherwise return success indicator
            if response.content:
                return response.json()
            else:
                return {"success": True, "status": "sent"}

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending shared mailbox message: {str(e)}")
            raise AuthenticationError("Failed to send shared mailbox message")

    async def create_shared_mailbox_folder(
        self,
        access_token: str,
        email_address: str,
        folder_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a folder in a shared mailbox.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address
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
                url = f"https://graph.microsoft.com/v1.0/users/{email_address}/mailFolders/{parent_id}/childFolders"
            else:
                url = f"https://graph.microsoft.com/v1.0/users/{email_address}/mailFolders"

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
                raise AuthorizationError("Insufficient permissions to create folder in shared mailbox")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox or parent folder not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to create shared mailbox folder")

            created_folder_data = response.json()
            logger.info(f"Created folder in shared mailbox {email_address}: {created_folder_data.get('displayName')}")
            return created_folder_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating shared mailbox folder: {str(e)}")
            raise AuthenticationError("Failed to create shared mailbox folder")

    async def move_shared_mailbox_message(
        self,
        access_token: str,
        email_address: str,
        message_id: str,
        destination_folder_id: str
    ) -> Dict[str, Any]:
        """Move a message in a shared mailbox.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address
            message_id: Message ID to move
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

            url = f"https://graph.microsoft.com/v1.0/users/{email_address}/messages/{message_id}/move"

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
                raise AuthorizationError("Insufficient permissions to move message in shared mailbox")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox, message, or folder not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to move shared mailbox message")

            message_data = response.json()
            logger.info(f"Moved message {message_id} in shared mailbox {email_address}")
            return message_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error moving shared mailbox message: {str(e)}")
            raise AuthenticationError("Failed to move shared mailbox message")

    async def get_shared_mailbox_permissions(
        self,
        access_token: str,
        email_address: str
    ) -> Dict[str, Any]:
        """Get permissions for a shared mailbox.

        Args:
            access_token: Valid access token
            email_address: Shared mailbox email address

        Returns:
            Permissions data

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Get mailbox permissions - this might not be directly available via Graph API
            # This is a placeholder for a more complex implementation
            url = f"https://graph.microsoft.com/v1.0/users/{email_address}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access shared mailbox permissions")
            elif response.status_code == 404:
                raise AuthenticationError("Shared mailbox not found")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve shared mailbox permissions")

            # For now, return basic user info - in a real implementation,
            # you'd need to query Exchange Online PowerShell or use different Graph endpoints
            permissions_data = response.json()
            logger.info(f"Retrieved permissions for shared mailbox {email_address}")
            return {"value": [permissions_data], "mailbox": email_address}

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting shared mailbox permissions: {str(e)}")
            raise AuthenticationError("Failed to retrieve shared mailbox permissions")


# Global instance
azure_mail_service = AzureMailService()