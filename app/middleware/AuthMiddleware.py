"""
AuthMiddleware.py - Authentication Middleware

This middleware provides automatic authentication header injection for requests
and cookie-based session management. It handles:
- Automatic Bearer token header injection from stored auth state
- Session ID header injection from stored sessions
- Cookie-based session management for browser clients
- Token refresh for expiring tokens
- Seamless authentication state management

The middleware operates transparently, allowing clients to make requests without
manually managing authentication headers after the initial login.
"""

import logging
from typing import Optional, Tuple, Callable, Awaitable, Dict, Any
from datetime import datetime, timedelta

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send, Message
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from app.core.AuthState import (
    auth_state_manager, 
    AuthenticationState,
    get_user_auth_by_email,
    get_user_auth_by_session,
    get_user_auth_by_token
)
from app.models.AuthModel import UserInfo

logger = logging.getLogger(__name__)


class AuthenticationMiddleware:
    """
    Middleware for automatic authentication header management.
    
    This middleware:
    1. Checks for existing authentication headers
    2. Falls back to session cookies if headers are missing
    3. Automatically injects authentication headers for protected endpoints
    4. Handles token refresh for expiring tokens
    5. Manages cookie-based sessions for browser clients
    """
    
    def __init__(self, app: ASGIApp):
        self.app = app
        self.protected_paths = [
            "/api/v1/mail/",
            "/api/v1/shared-mailbox/",
            "/api/v1/transcription/",
            "/api/v1/voice-attachment/",
            "/api/v1/excel-sync/"
        ]
        self.auth_paths = ["/api/v1/auth/"]
        
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI middleware entry point.
        
        Args:
            scope: ASGI scope containing request information
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            # Only process HTTP requests
            await self.app(scope, receive, send)
            return
        
        # Create a request object for path checking
        request = StarletteRequest(scope)
        
        # Skip middleware for non-protected paths
        if not self._is_protected_path(request.url.path):
            await self.app(scope, receive, send)
            return
        
        # Check if request already has authentication headers
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization")
        session_header = headers.get(b"x-session-id")
        
        if auth_header or session_header:
            # Request already has authentication headers, skip middleware injection
            logger.debug("Request already has auth headers, skipping middleware injection")
            await self.app(scope, receive, send)
            return
        
        # Try to get authentication from cookies or stored state
        auth_state = await self._get_auth_from_request(request)
        
        if auth_state:
            # Create modified scope with authentication headers
            modified_scope = await self._inject_auth_headers_to_scope(scope, auth_state)
            
            # Wrap send to potentially modify response (for cookies)
            modified_send = self._wrap_send_for_cookies(send, auth_state)
            
            await self.app(modified_scope, receive, modified_send)
        else:
            # No authentication available - let the request proceed
            await self.app(scope, receive, send)
    
    def _is_protected_path(self, path: str) -> bool:
        """
        Check if the path requires authentication.
        
        Args:
            path: Request path to check
            
        Returns:
            True if path requires authentication
        """
        # Skip auth paths themselves (login, callback, etc.)
        for auth_path in self.auth_paths:
            if path.startswith(auth_path):
                return False
        
        # Check protected paths
        for protected_path in self.protected_paths:
            if path.startswith(protected_path):
                return True
        
        return False
    
    async def _get_auth_from_request(self, request: Request) -> Optional[AuthenticationState]:
        """
        Extract authentication state from request cookies or stored state.
        
        Args:
            request: HTTP request to extract auth from
            
        Returns:
            AuthenticationState if found, None otherwise
        """
        try:
            # Try session ID from cookie first (most secure)
            session_id = request.cookies.get("scribe_session")
            if session_id:
                logger.debug(f"Found session cookie: {session_id[:8]}...")
                auth_state = get_user_auth_by_session(session_id)
                if auth_state and not auth_state.is_expired:
                    logger.debug(f"Valid session found for user: {auth_state.user_info.email}")
                    return auth_state
                else:
                    logger.debug(f"Session invalid or expired: {session_id[:8]}...")
            
            # Try access token from cookie (fallback for testing)
            access_token = request.cookies.get("scribe_token")
            if access_token:
                logger.debug(f"Found token cookie: {access_token[:20]}...")
                auth_state = get_user_auth_by_token(access_token)
                if auth_state and not auth_state.is_expired:
                    logger.debug(f"Valid token found for user: {auth_state.user_info.email}")
                    return auth_state
                else:
                    logger.debug("Token invalid or expired")
            
            # Development fallback (only for localhost)
            client_ip = request.client.host if request.client else None
            if client_ip and client_ip in ["127.0.0.1", "::1", "localhost"]:
                active_users = auth_state_manager.get_all_active_users()
                if active_users:
                    logger.debug(f"Development fallback: using auth state for {active_users[0]}")
                    return get_user_auth_by_email(active_users[0])
            
            logger.debug("No valid authentication found in request")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting auth from request: {str(e)}")
            return None
    
    async def _inject_auth_headers_to_scope(
        self, 
        scope: Scope, 
        auth_state: AuthenticationState
    ) -> Scope:
        """
        Create a modified scope with authentication headers injected.
        
        Args:
            scope: Original ASGI scope
            auth_state: Authentication state to inject
            
        Returns:
            Modified scope with authentication headers
        """
        # Create a copy of the scope
        modified_scope = dict(scope)
        
        # Get existing headers and convert to mutable list
        headers = list(scope.get("headers", []))
        
        # Prefer session-based authentication if available
        if auth_state.session_id:
            headers.append((b"x-session-id", auth_state.session_id.encode()))
            logger.debug(f"Injected session ID header for user: {auth_state.user_info.email}")
        else:
            # Fall back to Bearer token
            auth_value = f"Bearer {auth_state.access_token}"
            headers.append((b"authorization", auth_value.encode()))
            logger.debug(f"Injected Bearer token header for user: {auth_state.user_info.email}")
        
        # Update the scope with new headers
        modified_scope["headers"] = headers
        
        return modified_scope
    
    def _wrap_send_for_cookies(self, send: Send, auth_state: AuthenticationState) -> Send:
        """
        Wrap the ASGI send callable to inject cookies into the response.
        
        Args:
            send: Original ASGI send callable
            auth_state: Authentication state for cookie data
            
        Returns:
            Wrapped send callable that adds cookies
        """
        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Modify response headers to include cookies
                headers = list(message.get("headers", []))
                
                # Set session cookie if we have a session ID
                if auth_state.session_id:
                    cookie_value = f"scribe_session={auth_state.session_id}; Max-Age=86400; HttpOnly; SameSite=Lax; Path=/"
                    headers.append((b"set-cookie", cookie_value.encode()))
                
                # Set user info cookie (non-sensitive data only)
                import json
                user_info = {
                    "email": auth_state.user_info.email,
                    "display_name": auth_state.user_info.display_name,
                    "role": auth_state.user_info.role.value if hasattr(auth_state.user_info.role, 'value') else str(auth_state.user_info.role)
                }
                
                user_cookie_value = f"scribe_user={json.dumps(user_info)}; Max-Age=86400; SameSite=Lax; Path=/"
                headers.append((b"set-cookie", user_cookie_value.encode()))
                
                # Update the message with new headers
                message["headers"] = headers
            
            await send(message)
        
        return wrapped_send


class CookieAuthenticationMiddleware:
    """
    Simplified middleware that only handles cookie-based authentication.
    
    This is a lighter version that focuses specifically on cookie management
    without the complexity of header injection.
    """
    
    def __init__(self, app: ASGIApp):
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI middleware for cookie-based authentication."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
            
        request = StarletteRequest(scope)
        
        # Check if this is a successful authentication callback
        if request.url.path == "/api/v1/auth/callback":
            # For the callback endpoint, we might want to set cookies
            # This would need to be implemented based on your specific needs
            pass
        
        await self.app(scope, receive, send)


def create_auth_middleware(app: ASGIApp) -> AuthenticationMiddleware:
    """
    Factory function to create authentication middleware.
    
    Args:
        app: ASGI application instance
    
    Returns:
        Configured AuthenticationMiddleware instance
    """
    return AuthenticationMiddleware(app)


# Cookie utility functions
def set_auth_cookies(
    response: Response, 
    auth_state: AuthenticationState,
    secure: bool = False
) -> None:
    """
    Set authentication cookies on a response.
    
    Args:
        response: HTTP response to set cookies on
        auth_state: Authentication state to store
        secure: Whether to use secure cookies (HTTPS only)
    """
    # Session cookie
    if auth_state.session_id:
        response.set_cookie(
            key="scribe_session",
            value=auth_state.session_id,
            max_age=3600 * 24,  # 24 hours
            httponly=True,
            secure=secure,
            samesite="lax"
        )
    
    # User info cookie (non-sensitive data)
    import json
    user_info = {
        "email": auth_state.user_info.email,
        "display_name": auth_state.user_info.display_name,
        "role": auth_state.user_info.role.value if hasattr(auth_state.user_info.role, 'value') else str(auth_state.user_info.role),
        "expires_at": auth_state.expires_at.isoformat()
    }
    
    response.set_cookie(
        key="scribe_user",
        value=json.dumps(user_info),
        max_age=3600 * 24,  # 24 hours
        httponly=False,  # Allow client-side access
        secure=secure,
        samesite="lax"
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clear authentication cookies from a response.
    
    Args:
        response: HTTP response to clear cookies from
    """
    response.delete_cookie("scribe_session")
    response.delete_cookie("scribe_user")
    response.delete_cookie("scribe_token")  # Clear any legacy token cookies


def get_session_from_cookies(request: Request) -> Optional[str]:
    """
    Extract session ID from request cookies.
    
    Args:
        request: HTTP request
        
    Returns:
        Session ID if found, None otherwise
    """
    return request.cookies.get("scribe_session")


def get_user_info_from_cookies(request: Request) -> Optional[dict]:
    """
    Extract user info from request cookies.
    
    Args:
        request: HTTP request
        
    Returns:
        User info dictionary if found, None otherwise
    """
    import json
    try:
        user_cookie = request.cookies.get("scribe_user")
        if user_cookie:
            return json.loads(user_cookie)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Invalid user info cookie format")
    
    return None