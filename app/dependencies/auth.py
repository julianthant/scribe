"""
auth.py - Authentication Dependencies

Provides FastAPI dependency injection functions for user authentication and authorization.
This module handles:
- get_current_user(): Validates Bearer tokens OR session IDs and returns authenticated user info
- get_current_user_optional(): Optional authentication for public endpoints (supports both methods)
- Session validation from database for session-based authentication
- Token validation and user information extraction
- HTTP Bearer token scheme configuration
- Authentication error handling and standardized responses

Authentication Methods Supported:
1. Bearer Token: Authorization header with Azure AD access token
2. Session ID: X-Session-Id header with database session identifier

These dependencies are used throughout the API endpoints to ensure proper authentication
and provide consistent access to current user information.
"""

from typing import Optional
import logging
from datetime import datetime

from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.OAuthService import oauth_service
from app.models.AuthModel import UserInfo
from app.core.Exceptions import AuthenticationError
from app.db.Database import get_async_db
from app.repositories.UserRepository import UserRepository
from app.db.models.User import UserRole

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_user_repository(
    db_session: AsyncSession = Depends(get_async_db)
) -> UserRepository:
    """Get UserRepository instance with database session.
    
    Args:
        db_session: Async database session
        
    Returns:
        UserRepository: Repository instance for user operations
    """
    return UserRepository(db_session)


async def _validate_session(session_id: str, user_repository: UserRepository) -> Optional[UserInfo]:
    """Validate a session ID and return user info if valid.
    
    Args:
        session_id: Session ID to validate
        user_repository: UserRepository for database operations
        
    Returns:
        UserInfo if session is valid, None otherwise
    """
    try:
        logger.debug(f"Validating session: {session_id[:8]}...")
        
        # Get session from database with timeout
        import asyncio
        session = await asyncio.wait_for(
            user_repository.get_session_by_id(session_id),
            timeout=5.0  # 5 second timeout for database query
        )
        
        if not session:
            logger.debug(f"Session not found in database: {session_id[:8]}...")
            return None
            
        # Check if session is revoked
        if session.is_revoked:
            logger.debug(f"Session is revoked: {session_id[:8]}...")
            return None
            
        # Check if session is expired
        if session.expires_at and session.expires_at <= datetime.utcnow():
            logger.debug(f"Session is expired: {session_id[:8]}..., expired at: {session.expires_at}")
            return None
        
        # Get user info from the session's user
        if not session.user:
            logger.error(f"Session has no associated user: {session_id[:8]}...")
            return None
            
        user = session.user
        logger.debug(f"Session validation successful for user: {user.email}")
        
        user_info = UserInfo(
            id=user.azure_id,
            display_name=user.profile.display_name if user.profile and user.profile.display_name else "",
            email=user.email,
            given_name=user.profile.first_name if user.profile and user.profile.first_name else "",
            surname=user.profile.last_name if user.profile and user.profile.last_name else "",
            role=user.role,
            is_superuser=(user.role == UserRole.SUPERUSER)
        )
        
        return user_info
        
    except asyncio.TimeoutError:
        logger.error(f"Session validation timeout for session: {session_id[:8]}...")
        return None
    except Exception as e:
        logger.error(f"Error validating session {session_id[:8]}...: {str(e)}")
        return None




async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    user_repository: UserRepository = Depends(get_user_repository)
) -> tuple[UserInfo, str]:
    """Get current authenticated user and access token from Bearer token or session ID.
    
    Args:
        credentials: HTTP Bearer token credentials
        x_session_id: Optional session ID from X-Session-Id header
        user_repository: UserRepository for session validation
        
    Returns:
        tuple[UserInfo, str]: User info and access token for Graph API
        
    Raises:
        HTTPException: If authentication fails
    """
    # Try Bearer token authentication first
    if credentials:
        try:
            # Extract token from credentials
            access_token = credentials.credentials
            
            # Get user info from token
            user_info = await oauth_service.get_current_user(access_token)
            logger.debug(f"Bearer token authentication successful for user: {user_info.email}")
            return user_info, access_token
            
        except AuthenticationError as e:
            logger.error(f"Bearer token authentication failed: {str(e)}")
            # Don't immediately fail, try session authentication
        except Exception as e:
            logger.error(f"Unexpected Bearer token authentication error: {str(e)}")
            # Don't immediately fail, try session authentication
    
    # Try session ID authentication if Bearer token failed or not provided
    if x_session_id:
        try:
            logger.debug(f"Attempting session authentication: {x_session_id[:8]}...")
            
            # Use the validated session helper with timeout
            import asyncio
            session_user_info: Optional[UserInfo] = await asyncio.wait_for(
                _validate_session(x_session_id, user_repository),
                timeout=10.0  # 10 second timeout for complete validation
            )
            
            if not session_user_info:
                logger.error(f"Session validation failed: {x_session_id[:8]}...")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired session",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Get the session to extract the access token
            session = await asyncio.wait_for(
                user_repository.get_session_by_id(x_session_id),
                timeout=5.0
            )
            
            if not session:
                logger.error(f"Session not found during token retrieval: {x_session_id[:8]}...")
                raise HTTPException(
                    status_code=401,
                    detail="Session not found",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Return user info AND the stored access token
            access_token = session.access_token
            logger.debug(f"Session authentication successful for user: {session_user_info.email}")
            return session_user_info, access_token
                
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except asyncio.TimeoutError:
            logger.error(f"Session authentication timeout: {x_session_id[:8]}...")
            raise HTTPException(
                status_code=401,
                detail="Authentication timeout - please try again",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            logger.error(f"Unexpected session authentication error: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Authentication service error",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    # Both authentication methods failed or not provided
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide either Bearer token or X-Session-Id header",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_current_user_info_only(
    auth_data: tuple[UserInfo, str] = Depends(get_current_user)
) -> UserInfo:
    """Get only the UserInfo from the current authenticated user (for endpoints that don't need the token).
    
    Args:
        auth_data: Tuple of (UserInfo, access_token) from get_current_user
        
    Returns:
        UserInfo: Current authenticated user information only
    """
    user_info, _ = auth_data
    return user_info


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    user_repository: UserRepository = Depends(get_user_repository)
) -> Optional[UserInfo]:
    """Get current authenticated user if present, otherwise return None.
    
    Args:
        credentials: HTTP Bearer token credentials
        x_session_id: Optional session ID from X-Session-Id header
        user_repository: UserRepository for session validation
        
    Returns:
        UserInfo or None: Current authenticated user or None if not authenticated
    """
    # Try Bearer token authentication first
    if credentials:
        try:
            access_token = credentials.credentials
            user_info = await oauth_service.get_current_user(access_token)
            logger.debug(f"Optional Bearer token authentication successful for user: {user_info.email}")
            return user_info
        except Exception as e:
            logger.debug(f"Optional Bearer token authentication failed: {str(e)}")
            # Continue to try session authentication
    
    # Try session ID authentication
    if x_session_id:
        try:
            session_auth_user_info: Optional[UserInfo] = await _validate_session(x_session_id, user_repository)
            if session_auth_user_info:
                logger.debug(f"Optional session authentication successful for user: {session_auth_user_info.email}")
                return session_auth_user_info
        except Exception as e:
            logger.debug(f"Optional session authentication failed: {str(e)}")
    
    # No valid authentication found
    return None


async def validate_token(access_token: str) -> bool:
    """Validate an access token.
    
    Args:
        access_token: Token to validate
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    try:
        return await oauth_service.validate_access_token(access_token)
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return False


