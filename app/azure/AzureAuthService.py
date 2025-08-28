"""
AzureAuthService.py - Azure AD Authentication Service

Provides Azure Active Directory authentication using MSAL.
This service handles:
- OAuth 2.0 authorization code flow with Azure AD
- Token acquisition, validation, and refresh
- User profile retrieval from Microsoft Graph API
- PKCE support for enhanced security
- State management for CSRF protection
- Token caching and session management

The AzureAuthService class serves as the authentication interface for Azure AD operations.
"""

from typing import Optional, Dict, Any
import logging
from urllib.parse import urlparse, parse_qs

import msal  # type: ignore[import-untyped]
import httpx

from app.core.config import settings
from app.core.Exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)


class AzureAuthService:
    """Azure AD authentication service using MSAL."""

    def __init__(self):
        """Initialize the Azure AD client."""
        logger.info("[SERVICE] Azure Auth Service initializing...")
        
        if not settings.get("azure_client_id"):
            logger.error("[ERROR] Azure Client ID is required but not configured")
            raise ValueError("Azure Client ID is required")
        if not settings.get("azure_client_secret"):
            logger.error("[ERROR] Azure Client Secret is required but not configured")
            raise ValueError("Azure Client Secret is required")

        try:
            self._client_app = msal.ConfidentialClientApplication(
                client_id=settings.azure_client_id,
                client_credential=settings.azure_client_secret,
                authority=settings.azure_authority
            )
            self._scopes = settings.azure_scopes
            self._auth_flow_cache = {}
            
            logger.info(f"[CONFIG] Azure authority: {settings.azure_authority}")
            logger.info(f"[CONFIG] Azure scopes: {settings.azure_scopes}")
            logger.info(f"[CONFIG] Azure client ID: {settings.azure_client_id[:8]}...")
            logger.info("[OK] Azure Auth Service initialized successfully")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize Azure Auth Service: {str(e)}")
            raise

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
            auth_response: dict[str, str] = {}
            # Flatten the lists in query_params to single values
            for key, value in query_params.items():
                if isinstance(value, list) and len(value) == 1:
                    auth_response[key] = value[0]
                elif isinstance(value, list) and len(value) > 1:
                    auth_response[key] = value[0]  # Take first value
                else:
                    auth_response[key] = str(value)
            
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


# Global instance
azure_auth_service = AzureAuthService()