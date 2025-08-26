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

from app.azure.AzureAuthService import azure_auth_service
from app.core.Exceptions import AuthenticationError, ValidationError
from app.models.AuthModel import TokenResponse, UserInfo
from app.repositories.UserRepository import UserRepository
from app.db.models.User import UserRole

logger = logging.getLogger(__name__)


class OAuthService:
    """Service for handling OAuth authentication operations."""

    def __init__(self, user_repository: Optional[UserRepository] = None):
        """Initialize OAuth service.
        
        Args:
            user_repository: Optional UserRepository for database operations
        """
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        self.user_repository = user_repository

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
            auth_data = azure_auth_service.get_authorization_url(state=state)
            
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
        state: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> TokenResponse:
        """Handle OAuth callback and exchange code for tokens.

        Args:
            callback_url: Full callback URL from Azure AD
            state: State parameter for CSRF validation
            ip_address: Optional client IP address
            user_agent: Optional client user agent

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
            token_data = azure_auth_service.acquire_token_by_auth_code(callback_url)
            
            # Get user profile
            access_token = token_data["access_token"]
            user_profile = await azure_auth_service.get_user_profile(access_token)
            
            # Create initial user info (role will be updated after database persistence)
            user_info = UserInfo(
                id=user_profile["id"],
                display_name=user_profile.get("displayName", ""),
                email=user_profile.get("mail") or user_profile.get("userPrincipalName", ""),
                given_name=user_profile.get("givenName", ""),
                surname=user_profile.get("surname", "")
            )
            
            # Persist user data to database if repository is available
            session_id = None
            if self.user_repository:
                try:
                    # Get or create user
                    user = await self.user_repository.get_or_create_by_azure_id(
                        azure_id=user_profile["id"],
                        email=user_info.email
                    )
                    
                    # Check if user role needs to be updated (in case configuration changed)
                    role_updated = await self.user_repository.update_user_role_if_changed(user)
                    if role_updated:
                        logger.info(f"User role updated during login: {user.email}")
                    
                    # Update or create user profile
                    profile_data = {
                        "first_name": user_profile.get("givenName"),
                        "last_name": user_profile.get("surname"),
                        "display_name": user_profile.get("displayName")
                    }
                    await self.user_repository.update_or_create_profile(user, profile_data)
                    
                    # Create session record
                    expires_in = token_data.get("expires_in", 3600)
                    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                    
                    session = await self.user_repository.create_session(
                        user=user,
                        access_token=access_token,
                        refresh_token=token_data.get("refresh_token"),
                        expires_at=expires_at,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    session_id = session.id
                    
                    # Update user_info with role information from database
                    user_info.role = user.role
                    user_info.is_superuser = (user.role == UserRole.SUPERUSER)
                    
                    logger.info(f"User login persisted to database: {user_info.email}, Role: {user.role.value}")
                    
                except Exception as db_error:
                    # Log database error but don't fail the authentication
                    logger.error(f"Failed to persist login data: {str(db_error)}", exc_info=True)
            
            # Create token response
            token_response = TokenResponse(
                access_token=access_token,
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                scope=" ".join(token_data.get("scope", [])),
                user_info=user_info
            )
            
            # Store session ID in token response for future reference
            if session_id:
                # Add session_id as a custom field (we'll need to extend TokenResponse model)
                token_response.session_id = session_id
            
            # Clean up OAuth state session
            if state and state in self._active_sessions:
                del self._active_sessions[state]
            
            logger.info(f"Successfully authenticated user: {user_info.email}")
            return token_response

        except (ValidationError, AuthenticationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error handling callback: {str(e)}")
            raise AuthenticationError("Failed to process authentication callback")

    async def refresh_user_token(
        self, 
        refresh_token: str,
        session_id: Optional[str] = None
    ) -> TokenResponse:
        """Refresh an expired access token.

        Args:
            refresh_token: The refresh token
            session_id: Optional session ID to update in database

        Returns:
            New TokenResponse with refreshed tokens

        Raises:
            AuthenticationError: If token refresh fails
        """
        try:
            # Refresh the token
            token_data = azure_auth_service.refresh_token(refresh_token)
            
            # Get updated user profile
            access_token = token_data["access_token"]
            user_profile = await azure_auth_service.get_user_profile(access_token)
            
            # Create user info with role information
            user_info = UserInfo(
                id=user_profile["id"],
                display_name=user_profile.get("displayName", ""),
                email=user_profile.get("mail") or user_profile.get("userPrincipalName", ""),
                given_name=user_profile.get("givenName", ""),
                surname=user_profile.get("surname", "")
            )
            
            # Get role information from database if repository is available
            if self.user_repository:
                try:
                    user = await self.user_repository.get_by_azure_id(user_profile["id"])
                    if user:
                        user_info.role = user.role
                        user_info.is_superuser = (user.role == UserRole.SUPERUSER)
                except Exception as db_error:
                    logger.error(f"Failed to get user role during token refresh: {str(db_error)}")
                    # Continue with default role if there's an error
            
            # Update session in database if available
            if self.user_repository and session_id:
                try:
                    expires_in = token_data.get("expires_in", 3600)
                    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                    
                    await self.user_repository.update_session(
                        session_id=session_id,
                        access_token=access_token,
                        refresh_token=token_data.get("refresh_token", refresh_token),
                        expires_at=expires_at
                    )
                    logger.debug(f"Updated session {session_id} with new tokens")
                    
                except Exception as db_error:
                    # Log database error but don't fail the token refresh
                    logger.error(f"Failed to update session in database: {str(db_error)}", exc_info=True)
            
            # Create token response
            token_response = TokenResponse(
                access_token=access_token,
                refresh_token=token_data.get("refresh_token", refresh_token),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in", 3600),
                scope=" ".join(token_data.get("scope", [])),
                user_info=user_info
            )
            
            # Preserve session ID in response
            if session_id:
                token_response.session_id = session_id
            
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
            user_profile = await azure_auth_service.get_user_profile(access_token)
            
            # Create user info with role information
            user_info = UserInfo(
                id=user_profile["id"],
                display_name=user_profile.get("displayName", ""),
                email=user_profile.get("mail") or user_profile.get("userPrincipalName", ""),
                given_name=user_profile.get("givenName", ""),
                surname=user_profile.get("surname", "")
            )
            
            # Get role information from database if repository is available
            if self.user_repository:
                try:
                    user = await self.user_repository.get_by_azure_id(user_profile["id"])
                    if user:
                        user_info.role = user.role
                        user_info.is_superuser = (user.role == UserRole.SUPERUSER)
                except Exception as db_error:
                    logger.error(f"Failed to get user role: {str(db_error)}")
                    # Continue with default role if there's an error
            
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
            return azure_auth_service.validate_token(access_token)
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return False

    async def logout(self, session_id: Optional[str] = None) -> bool:
        """Logout user and clean up session.

        Args:
            session_id: Optional session ID to revoke

        Returns:
            True if logout successful
        """
        try:
            success = True
            
            # Revoke session in database if available
            if self.user_repository and session_id:
                try:
                    revoked = await self.user_repository.revoke_session(session_id)
                    if revoked:
                        logger.info(f"Revoked database session: {session_id}")
                    else:
                        logger.warning(f"Session not found in database: {session_id}")
                        
                except Exception as db_error:
                    logger.error(f"Failed to revoke session in database: {str(db_error)}", exc_info=True)
                    success = False
            
            # Clean up OAuth state session (legacy)
            if session_id and session_id in self._active_sessions:
                del self._active_sessions[session_id]
            
            if success:
                logger.info("User logged out successfully")
            
            return success

        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return False

    async def cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions in both memory and database."""
        try:
            # Clean up OAuth state sessions (in-memory)
            current_time = datetime.utcnow()
            expired_sessions = [
                state for state, session in self._active_sessions.items()
                if current_time - session["created_at"] > timedelta(minutes=10)
            ]
            
            for state in expired_sessions:
                del self._active_sessions[state]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired OAuth state sessions")
            
            # Clean up database sessions if repository is available
            if self.user_repository:
                try:
                    cleaned_count = await self.user_repository.cleanup_expired_sessions()
                    if cleaned_count > 0:
                        logger.info(f"Cleaned up {cleaned_count} expired database sessions")
                        
                except Exception as db_error:
                    logger.error(f"Failed to cleanup database sessions: {str(db_error)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error cleaning up sessions: {str(e)}")


# Global service instance
oauth_service = OAuthService()