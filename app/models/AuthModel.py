"""
auth.py - Authentication Data Models

Defines Pydantic models for authentication-related data structures and API responses.
This module provides:
- UserInfo: Azure AD user information (ID, name, email)
- TokenResponse: OAuth token response with user info
- AuthStatus: Current authentication status with expiration
- LoginResponse: Login initiation response with auth URL
- LogoutResponse: Logout confirmation response
- RefreshTokenRequest: Token refresh request structure

All models include validation, serialization, and documentation for the authentication
API endpoints and OAuth flow integration.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

from app.db.models.User import UserRole


class UserInfo(BaseModel):
    """User information from Azure AD."""
    id: str = Field(..., description="Azure AD user ID")
    display_name: str = Field("", description="User's display name")
    email: EmailStr = Field(..., description="User's email address")
    given_name: str = Field("", description="User's first name")
    surname: str = Field("", description="User's last name")
    role: UserRole = Field(UserRole.USER, description="User's role in the system")
    is_superuser: bool = Field(False, description="Whether user has superuser privileges")


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str = Field(..., description="Access token for API calls")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    scope: str = Field("", description="Token scope")
    user_info: UserInfo = Field(..., description="Authenticated user information")
    session_id: Optional[str] = Field(None, description="Database session ID")


class AuthStatus(BaseModel):
    """Authentication status response."""
    is_authenticated: bool = Field(..., description="Whether user is authenticated")
    user_info: Optional[UserInfo] = Field(None, description="User info if authenticated")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")


class LoginResponse(BaseModel):
    """Login initiation response."""
    auth_url: str = Field(..., description="URL to redirect user for authentication")
    state: str = Field(..., description="State parameter for CSRF protection")


class LogoutResponse(BaseModel):
    """Logout response."""
    success: bool = Field(..., description="Whether logout was successful")
    message: str = Field("Successfully logged out", description="Logout message")


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str = Field(..., description="Valid refresh token")
    session_id: Optional[str] = Field(None, description="Database session ID")