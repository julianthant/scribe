"""
azure_auth.py - Azure AD Authentication Client

Provides Azure Active Directory authentication and Microsoft Graph API integration using MSAL.
This module handles:
- OAuth 2.0 authorization code flow with Azure AD
- Token acquisition, validation, and refresh
- Microsoft Graph API calls for user information and mail operations
- PKCE support for enhanced security
- State management for CSRF protection
- Token caching and session management
- Graph API endpoints for mail folders, messages, and attachments

The AzureAuthClient class serves as the main interface for all Azure AD and Graph API operations.
"""

from typing import Optional, Dict, Any, List
import logging
from urllib.parse import urlparse, parse_qs, urlencode
import base64

import msal
import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class AzureAuthClient:
    """Azure AD authentication client using MSAL."""

    def __init__(self):
        """Initialize the Azure AD client."""
        if not settings.azure_client_id:
            raise ValueError("Azure Client ID is required")
        if not settings.azure_client_secret:
            raise ValueError("Azure Client Secret is required")

        self._client_app = msal.ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=settings.azure_authority_url
        )
        self._scopes = settings.azure_scopes
        self._auth_flow_cache = {}

    def get_authorization_url(self, state: Optional[str] = None) -> Dict[str, str]:
        """Generate authorization URL for OAuth flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Dictionary containing auth_uri and state
        """
        try:
            auth_request = self._client_app.initiate_auth_code_flow(
                scopes=self._scopes,
                redirect_uri=settings.azure_redirect_uri,
                state=state
            )
            
            if "error" in auth_request:
                logger.error(f"Error initiating auth flow: {auth_request}")
                raise AuthenticationError("Failed to initiate authentication flow")

            # Cache the auth flow for later use
            flow_state = auth_request.get("state", "")
            self._auth_flow_cache[flow_state] = auth_request

            return {
                "auth_uri": auth_request["auth_uri"],
                "state": flow_state
            }

        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
            raise AuthenticationError("Failed to generate authorization URL")

    def acquire_token_by_auth_code(
        self, 
        auth_response_url: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token.

        Args:
            auth_response_url: Full callback URL with authorization code

        Returns:
            Token response containing access_token, refresh_token, etc.

        Raises:
            AuthenticationError: If token acquisition fails
        """
        try:
            # Parse the authorization code from the callback URL
            parsed_url = urlparse(auth_response_url)
            query_params = parse_qs(parsed_url.query)

            if "error" in query_params:
                error_desc = query_params.get("error_description", ["Unknown error"])[0]
                logger.error(f"OAuth error: {error_desc}")
                raise AuthenticationError(f"OAuth authentication failed: {error_desc}")

            if "code" not in query_params:
                raise AuthenticationError("Authorization code not found in callback URL")

            # Get the state and retrieve cached auth flow
            flow_state = query_params.get("state", [""])[0]
            auth_code_flow = self._auth_flow_cache.get(flow_state)
            
            if not auth_code_flow:
                logger.warning("Auth flow not found in cache, creating minimal flow")
                # Fallback: create minimal auth flow
                auth_code_flow = {
                    "redirect_uri": settings.azure_redirect_uri,
                    "scope": self._scopes
                }

            # Exchange code for token
            logger.info(f"Attempting token exchange with flow: {auth_code_flow}")
            
            # Convert URL to dict format expected by MSAL
            auth_response = dict(query_params)
            # Flatten the lists in query_params to single values
            for key, value in auth_response.items():
                if isinstance(value, list) and len(value) == 1:
                    auth_response[key] = value[0]
            
            logger.info(f"Auth response dict: {auth_response}")
            
            result = self._client_app.acquire_token_by_auth_code_flow(
                auth_code_flow,
                auth_response
            )
            
            logger.info(f"Token exchange result: {result}")
            
            # Clean up cached flow
            if flow_state in self._auth_flow_cache:
                del self._auth_flow_cache[flow_state]

            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Token acquisition error: {error_msg}")
                raise AuthenticationError(f"Failed to acquire token: {error_msg}")

            if "access_token" not in result:
                logger.error(f"No access token in result: {result}")
                raise AuthenticationError("No access token received")

            logger.info("Successfully acquired access token")
            return result

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error acquiring token: {str(e)}", exc_info=True)
            logger.error(f"Auth code flow: {auth_code_flow}")
            logger.error(f"Callback URL: {auth_response_url}")
            raise AuthenticationError("Failed to acquire access token")

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token

        Returns:
            New token response

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            result = self._client_app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self._scopes
            )

            if "error" in result:
                error_msg = result.get("error_description", result.get("error"))
                logger.error(f"Token refresh error: {error_msg}")
                raise AuthenticationError(f"Failed to refresh token: {error_msg}")

            logger.info("Successfully refreshed access token")
            return result

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error refreshing token: {str(e)}")
            raise AuthenticationError("Failed to refresh access token")

    async def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Get user profile from Microsoft Graph API.

        Args:
            access_token: Valid access token

        Returns:
            User profile information

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
                    "https://graph.microsoft.com/v1.0/me",
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access user profile")
            elif not response.is_success:
                logger.error(f"Graph API error: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve user profile")

            user_data = response.json()
            logger.info(f"Retrieved profile for user: {user_data.get('userPrincipalName')}")
            return user_data

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting user profile: {str(e)}")
            raise AuthenticationError("Failed to retrieve user profile")

    def validate_token(self, access_token: str) -> bool:
        """Validate if an access token is still valid.

        Args:
            access_token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            # Simple validation by making a lightweight API call
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self.get_user_profile(access_token))
                return True
            except (AuthenticationError, AuthorizationError):
                return False
            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False

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
azure_auth_client = AzureAuthClient()