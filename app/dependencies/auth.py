"""
auth.py - Authentication Dependencies

Provides FastAPI dependency injection functions for user authentication and authorization.
This module handles:
- get_current_user(): Validates Bearer tokens and returns authenticated user info
- get_current_user_optional(): Optional authentication for public endpoints
- Token validation and user information extraction
- HTTP Bearer token scheme configuration
- Authentication error handling and standardized responses

These dependencies are used throughout the API endpoints to ensure proper authentication
and provide consistent access to current user information.
"""

from typing import Optional
import logging

from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.OAuthService import oauth_service
from app.models.AuthModel import UserInfo
from app.core.Exceptions import AuthenticationError
from app.db.Database import get_async_db
from app.repositories.UserRepository import UserRepository

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserInfo:
    """Get current authenticated user from Bearer token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        UserInfo: Current authenticated user information
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        # Extract token from credentials
        access_token = credentials.credentials
        
        # Get user info from token
        user_info = await oauth_service.get_current_user(access_token)
        return user_info
        
    except AuthenticationError as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Unexpected authentication error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Authentication service error"
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserInfo]:
    """Get current authenticated user if present, otherwise return None.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        UserInfo or None: Current authenticated user or None if not authenticated
    """
    if not credentials:
        return None

    try:
        access_token = credentials.credentials
        user_info = await oauth_service.get_current_user(access_token)
        return user_info
    except Exception as e:
        logger.warning(f"Optional authentication failed: {str(e)}")
        return None


def validate_token(access_token: str) -> bool:
    """Validate an access token.
    
    Args:
        access_token: Token to validate
        
    Returns:
        bool: True if token is valid, False otherwise
    """
    try:
        return oauth_service.validate_access_token(access_token)
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return False


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


