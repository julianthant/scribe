"""
auth.py - Authentication API Endpoints

Provides REST API endpoints for Azure AD OAuth authentication flow.
This module handles:
- GET /auth/login: Redirects directly to Azure AD OAuth authorization URL
- GET /auth/callback: Handles OAuth callback and exchanges code for tokens
- POST /auth/refresh: Refreshes access tokens using refresh tokens
- GET /auth/status: Returns current authentication status
- POST /auth/logout: Logs out the current user
- GET /auth/user: Returns current user information

All endpoints integrate with the OAuth service and provide standardized responses
for authentication workflows.
"""

from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import RedirectResponse

from app.services.OAuthService import OAuthService
from app.dependencies.Auth import get_current_user, get_current_user_optional, get_user_repository
from app.repositories.UserRepository import UserRepository
from app.models.AuthModel import (
    LoginResponse,
    TokenResponse,
    LogoutResponse,
    RefreshTokenRequest,
    AuthStatus,
    UserInfo
)
from app.core.Exceptions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_oauth_service(
    user_repository: UserRepository = Depends(get_user_repository)
) -> OAuthService:
    """Get OAuthService instance with UserRepository injected."""
    return OAuthService(user_repository=user_repository)


@router.get("/login")
async def initiate_login(
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """Initiate OAuth login flow with Azure AD by redirecting to auth URL.
    
    Returns:
        RedirectResponse: Direct redirect to Azure AD authorization URL
        
    Raises:
        HTTPException: If login initiation fails
    """
    try:
        auth_data = oauth_service.initiate_login()
        return RedirectResponse(url=auth_data["auth_uri"])
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
    error_description: Optional[str] = Query(None, description="Error description"),
    oauth_service: OAuthService = Depends(get_oauth_service)
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
        
        # Extract client information for audit trail
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Handle the callback
        token_response = await oauth_service.handle_callback(
            callback_url=callback_url,
            state=state,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
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
async def refresh_access_token(
    refresh_request: RefreshTokenRequest,
    oauth_service: OAuthService = Depends(get_oauth_service)
):
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
            refresh_token=refresh_request.refresh_token,
            session_id=refresh_request.session_id
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
async def logout(
    session_id: Optional[str] = None,
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """Logout user and clean up session.
    
    Args:
        session_id: Optional session identifier
        
    Returns:
        LogoutResponse: Logout status and message
    """
    try:
        success = await oauth_service.logout(session_id)
        
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
    current_user: UserInfo = Depends(get_current_user),
    oauth_service: OAuthService = Depends(get_oauth_service)
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
    current_user: Optional[UserInfo] = Depends(get_current_user_optional),
    oauth_service: OAuthService = Depends(get_oauth_service)
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