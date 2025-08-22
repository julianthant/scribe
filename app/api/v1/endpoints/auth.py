"""
auth.py - Authentication API Endpoints

Provides REST API endpoints for Azure AD OAuth authentication flow.
This module handles:
- GET /auth/login: Initiates OAuth login and returns authorization URL
- GET /auth/callback: Handles OAuth callback and exchanges code for tokens
- POST /auth/refresh: Refreshes access tokens using refresh tokens
- GET /auth/status: Returns current authentication status
- POST /auth/logout: Logs out the current user
- GET /auth/user: Returns current user information

All endpoints integrate with the OAuth service and provide standardized responses
for authentication workflows in the frontend application.
"""

from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import RedirectResponse

from app.services.oauth_service import oauth_service
from app.dependencies.auth import get_current_user, get_current_user_optional
from app.models.auth import (
    LoginResponse,
    TokenResponse,
    LogoutResponse,
    RefreshTokenRequest,
    AuthStatus,
    UserInfo
)
from app.core.exceptions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/login", response_model=LoginResponse)
async def initiate_login():
    """Initiate OAuth login flow with Azure AD.
    
    Returns:
        LoginResponse: Contains authorization URL and state parameter
        
    Raises:
        HTTPException: If login initiation fails
    """
    try:
        auth_data = oauth_service.initiate_login()
        return LoginResponse(
            auth_url=auth_data["auth_uri"],
            state=auth_data["state"]
        )
    except AuthenticationError as e:
        logger.error(f"Login initiation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during login initiation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initiate login")


@router.get("/callback", response_model=TokenResponse)
async def handle_oauth_callback(
    request: Request,
    code: Optional[str] = Query(None, description="Authorization code from Azure AD"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    error_description: Optional[str] = Query(None, description="Error description")
):
    """Handle OAuth callback from Azure AD.
    
    Args:
        request: FastAPI request object
        code: Authorization code from Azure AD
        state: State parameter for CSRF validation
        error: Error code if authentication failed
        error_description: Detailed error description
        
    Returns:
        TokenResponse: Contains access token and user information
        
    Raises:
        HTTPException: If callback handling fails
    """
    try:
        # Check for OAuth errors
        if error:
            logger.error(f"OAuth error: {error} - {error_description}")
            raise HTTPException(
                status_code=400,
                detail=f"Authentication failed: {error_description or error}"
            )

        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        # Get full callback URL
        callback_url = str(request.url)
        
        # Handle the callback
        token_response = await oauth_service.handle_callback(callback_url, state)
        
        logger.info(f"User successfully authenticated: {token_response.user_info.email}")
        return token_response
        
    except ValidationError as e:
        logger.error(f"Callback validation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Callback authentication failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process authentication callback")


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(refresh_request: RefreshTokenRequest):
    """Refresh an expired access token.
    
    Args:
        refresh_request: Contains the refresh token
        
    Returns:
        TokenResponse: New access token and user information
        
    Raises:
        HTTPException: If token refresh fails
    """
    try:
        token_response = await oauth_service.refresh_user_token(
            refresh_request.refresh_token
        )
        
        logger.info(f"Token refreshed for user: {token_response.user_info.email}")
        return token_response
        
    except AuthenticationError as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")


@router.post("/logout", response_model=LogoutResponse)
async def logout(session_id: Optional[str] = None):
    """Logout user and clean up session.
    
    Args:
        session_id: Optional session identifier
        
    Returns:
        LogoutResponse: Logout status and message
    """
    try:
        success = oauth_service.logout(session_id)
        
        if success:
            logger.info("User logged out successfully")
            return LogoutResponse(success=True, message="Successfully logged out")
        else:
            logger.warning("Logout failed")
            return LogoutResponse(success=False, message="Logout failed")
            
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        return LogoutResponse(success=False, message="Error during logout")


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: UserInfo = Depends(get_current_user)
):
    """Get current authenticated user information.
    
    Returns:
        UserInfo: Current user details
        
    Raises:
        HTTPException: If user is not authenticated
    """
    return current_user


@router.get("/status", response_model=AuthStatus)
async def get_auth_status(
    current_user: Optional[UserInfo] = Depends(get_current_user_optional)
):
    """Get current authentication status.
    
    Returns:
        AuthStatus: Authentication status and user info if authenticated
    """
    if current_user:
        return AuthStatus(
            is_authenticated=True,
            user_info=current_user,
            expires_at=None  # Could be enhanced to include token expiration
        )
    else:
        return AuthStatus(
            is_authenticated=False,
            user_info=None,
            expires_at=None
        )