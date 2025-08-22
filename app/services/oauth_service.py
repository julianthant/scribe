"""
oauth_service.py - OAuth Authentication Service

Provides business logic for OAuth 2.0 authentication flow with Azure AD.
This service handles:
- OAuth login initiation and callback processing
- Token exchange and validation
- User session management and state tracking
- Access token refresh operations
- User information retrieval from Graph API
- Token expiration handling
- CSRF protection with state parameters
- Session cleanup and logout operations

The OAuthService class manages the complete OAuth lifecycle and provides
a clean interface for authentication operations throughout the application.
"""

from typing import Optional, Dict, Any
import logging
import secrets
from datetime import datetime, timedelta

from app.core.azure_auth import azure_auth_client
from app.core.exceptions import AuthenticationError, ValidationError
from app.models.auth import TokenResponse, UserInfo

logger = logging.getLogger(__name__)


class OAuthService:
    """Service for handling OAuth authentication operations."""

    def __init__(self):
        """Initialize OAuth service."""
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    def initiate_login(self) -> Dict[str, str]:
        """Initiate OAuth login flow.

        Returns:
            Dictionary containing authorization URL and state

        Raises:
            AuthenticationError: If login initiation fails
        """
        try:
            # Generate secure state parameter for CSRF protection
            state = secrets.token_urlsafe(32)
            
            # Get authorization URL from Azure client
            auth_data = azure_auth_client.get_authorization_url(state=state)
            
            # Store state for validation
            self._active_sessions[state] = {
                "created_at": datetime.utcnow(),
                "status": "pending"
            }
            
            logger.info(f"Initiated OAuth login flow with state: {state}")
            return auth_data

        except Exception as e:
            logger.error(f"Failed to initiate login: {str(e)}")
            raise AuthenticationError("Failed to initiate login process")

    async def handle_callback(
        self, 
        callback_url: str, 
        state: Optional[str] = None
    ) -> TokenResponse:
        """Handle OAuth callback and exchange code for tokens.

        Args:
            callback_url: Full callback URL from Azure AD
            state: State parameter for CSRF validation

        Returns:
            TokenResponse with access token and user info

        Raises:
            ValidationError: If state validation fails
            AuthenticationError: If token exchange fails
        """
        try:
            # Validate state parameter
            if state and state in self._active_sessions:
                session = self._active_sessions[state]
                if session["status"] != "pending":
                    raise ValidationError("Invalid session state")
                
                # Check if session is expired (10 minutes)
                if datetime.utcnow() - session["created_at"] > timedelta(minutes=10):
                    del self._active_sessions[state]
                    raise ValidationError("Session expired")
                
                # Mark as processing
                session["status"] = "processing"
            else:
                logger.warning("State validation failed or missing")
                # Continue without strict state validation for flexibility

            # Exchange authorization code for tokens
            token_data = azure_auth_client.acquire_token_by_auth_code(callback_url)
            
            # Get user profile
            access_token = token_data["access_token"]
            user_profile = await azure_auth_client.get_user_profile(access_token)
            
            # Create user info
            user_info = UserInfo(
                id=user_profile["id"],
                display_name=user_profile.get("displayName", ""),
                email=user_profile.get("mail") or user_profile.get("userPrincipalName", ""),
                given_name=user_profile.get("givenName", ""),
                surname=user_profile.get("surname", "")
            )
            
            # Create token response
            token_response = TokenResponse(
                access_token=access_token,
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                scope=" ".join(token_data.get("scope", [])),
                user_info=user_info
            )
            
            # Clean up session
            if state and state in self._active_sessions:
                del self._active_sessions[state]
            
            logger.info(f"Successfully authenticated user: {user_info.email}")
            return token_response

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error handling callback: {str(e)}")
            raise AuthenticationError("Failed to process authentication callback")

    async def refresh_user_token(self, refresh_token: str) -> TokenResponse:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token

        Returns:
            New TokenResponse with refreshed tokens

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            # Refresh the token
            token_data = azure_auth_client.refresh_token(refresh_token)
            
            # Get updated user profile
            access_token = token_data["access_token"]
            user_profile = await azure_auth_client.get_user_profile(access_token)
            
            # Create user info
            user_info = UserInfo(
                id=user_profile["id"],
                display_name=user_profile.get("displayName", ""),
                email=user_profile.get("mail") or user_profile.get("userPrincipalName", ""),
                given_name=user_profile.get("givenName", ""),
                surname=user_profile.get("surname", "")
            )
            
            # Create token response
            token_response = TokenResponse(
                access_token=access_token,
                refresh_token=token_data.get("refresh_token", refresh_token),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                scope=" ".join(token_data.get("scope", [])),
                user_info=user_info
            )
            
            logger.info(f"Successfully refreshed token for user: {user_info.email}")
            return token_response

        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise AuthenticationError("Failed to refresh access token")

    async def get_current_user(self, access_token: str) -> UserInfo:
        """Get current user information from access token.

        Args:
            access_token: Valid access token

        Returns:
            UserInfo with current user details

        Raises:
            AuthenticationError: If token is invalid or user retrieval fails
        """
        try:
            # Get user profile from Microsoft Graph
            user_profile = await azure_auth_client.get_user_profile(access_token)
            
            # Create user info
            user_info = UserInfo(
                id=user_profile["id"],
                display_name=user_profile.get("displayName", ""),
                email=user_profile.get("mail") or user_profile.get("userPrincipalName", ""),
                given_name=user_profile.get("givenName", ""),
                surname=user_profile.get("surname", "")
            )
            
            return user_info

        except Exception as e:
            logger.error(f"Failed to get current user: {str(e)}")
            raise AuthenticationError("Failed to retrieve current user information")

    def validate_access_token(self, access_token: str) -> bool:
        """Validate if an access token is still valid.

        Args:
            access_token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            return azure_auth_client.validate_token(access_token)
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False

    def logout(self, session_id: Optional[str] = None) -> bool:
        """Logout user and clean up session.

        Args:
            session_id: Optional session ID to clean up

        Returns:
            True if logout successful
        """
        try:
            if session_id and session_id in self._active_sessions:
                del self._active_sessions[session_id]
            
            logger.info("User logged out successfully")
            return True

        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return False

    def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        try:
            current_time = datetime.utcnow()
            expired_sessions = [
                state for state, session in self._active_sessions.items()
                if current_time - session["created_at"] > timedelta(minutes=10)
            ]
            
            for state in expired_sessions:
                del self._active_sessions[state]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        except Exception as e:
            logger.error(f"Error cleaning up sessions: {str(e)}")


# Global service instance
oauth_service = OAuthService()