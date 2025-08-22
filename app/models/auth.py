from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class UserInfo(BaseModel):
    """User information from Azure AD."""
    id: str = Field(..., description="Azure AD user ID")
    display_name: str = Field("", description="User's display name")
    email: EmailStr = Field(..., description="User's email address")
    given_name: str = Field("", description="User's first name")
    surname: str = Field("", description="User's last name")


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str = Field(..., description="Access token for API calls")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: str = Field("Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    scope: str = Field("", description="Token scope")
    user_info: UserInfo = Field(..., description="Authenticated user information")


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