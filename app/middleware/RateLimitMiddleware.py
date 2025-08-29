"""
RateLimitMiddleware.py - Rate Limiting Middleware

This middleware provides rate limiting functionality to prevent abuse and protect API endpoints.
It uses an in-memory sliding window approach that integrates with the existing cache system.

Features:
- Per-IP address rate limiting
- Per-endpoint rate limiting
- Per-user rate limiting (for authenticated requests)
- Configurable limits and time windows
- Graceful degradation (logs warnings but doesn't fail)
"""

import time
import logging
from collections import defaultdict, deque
from typing import Dict, Deque, Tuple, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.Exceptions import RateLimitError

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    In-memory sliding window rate limiter.
    
    Uses deques to efficiently track request timestamps within time windows.
    """
    
    def __init__(self):
        # Key format: "type:identifier" -> deque of timestamps
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
    
    def is_allowed(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int
    ) -> Tuple[bool, int, int]:
        """
        Check if a request should be allowed based on rate limits.
        
        Args:
            key: Unique identifier for the rate limit (IP, user, endpoint, etc.)
            limit: Maximum requests allowed in the time window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, current_count, remaining_count)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Get request timestamps for this key
        timestamps = self._windows[key]
        
        # Remove old timestamps outside the current window
        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()
        
        current_count = len(timestamps)
        
        # Check if request is allowed
        if current_count >= limit:
            return False, current_count, 0
        
        # Add current request timestamp
        timestamps.append(now)
        
        # Periodic cleanup of old keys
        self._cleanup_if_needed(now)
        
        remaining = limit - current_count - 1
        return True, current_count + 1, remaining
    
    def _cleanup_if_needed(self, now: float) -> None:
        """Clean up old empty windows to prevent memory leaks."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
            
        # Remove empty deques
        empty_keys = [
            key for key, timestamps in self._windows.items()
            if not timestamps
        ]
        
        for key in empty_keys:
            del self._windows[key]
        
        self._last_cleanup = now
        
        if empty_keys:
            logger.debug(f"Cleaned up {len(empty_keys)} empty rate limit windows")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting HTTP requests.
    
    Applies different rate limits based on:
    - IP address (global limit)
    - Endpoint (per-endpoint limits)
    - User (per-authenticated-user limits)
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter()
        
        # Default rate limits (per minute unless specified)
        self.default_limits = {
            "ip": (60, 60),          # 60 requests per minute per IP
            "user": (120, 60),       # 120 requests per minute per user
            "endpoint": (100, 60),   # 100 requests per minute per endpoint
        }
        
        # Special endpoint limits
        self.endpoint_limits = {
            "/auth/login": (5, 60),           # 5 login attempts per minute
            "/auth/callback": (10, 60),       # 10 callback requests per minute
            "/auth/refresh": (20, 60),        # 20 token refreshes per minute
            "/mail/search": (30, 60),         # 30 search requests per minute
            "/voice-attachments/": (50, 60),  # 50 voice operations per minute
        }
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with rate limiting."""
        try:
            # Extract client information
            client_ip = self._get_client_ip(request)
            endpoint = request.url.path
            user_id = self._get_user_id(request)
            
            # Check rate limits in order of importance
            rate_limit_checks = []
            
            # 1. IP-based rate limiting (most important)
            ip_limit, ip_window = self.default_limits["ip"]
            rate_limit_checks.append(("ip", f"ip:{client_ip}", ip_limit, ip_window))
            
            # 2. Endpoint-specific rate limiting
            if endpoint in self.endpoint_limits:
                endpoint_limit, endpoint_window = self.endpoint_limits[endpoint]
                rate_limit_checks.append(
                    ("endpoint", f"endpoint:{endpoint}:{client_ip}", endpoint_limit, endpoint_window)
                )
            
            # 3. User-based rate limiting (for authenticated requests)
            if user_id:
                user_limit, user_window = self.default_limits["user"]
                rate_limit_checks.append(("user", f"user:{user_id}", user_limit, user_window))
            
            # Apply rate limit checks
            for limit_type, key, limit, window in rate_limit_checks:
                allowed, current, remaining = self.limiter.is_allowed(key, limit, window)
                
                if not allowed:
                    logger.warning(
                        f"Rate limit exceeded for {limit_type}: {key} "
                        f"({current}/{limit} requests in {window}s)"
                    )
                    
                    # Return rate limit error
                    raise RateLimitError(
                        f"Rate limit exceeded for {limit_type}",
                        error_code="RATE_LIMIT_EXCEEDED",
                        details={
                            "limit_type": limit_type,
                            "limit": limit,
                            "window_seconds": window,
                            "current_requests": current,
                            "retry_after": window
                        }
                    )
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limiting headers to response
            self._add_rate_limit_headers(response, rate_limit_checks[-1] if rate_limit_checks else None)
            
            return response
            
        except RateLimitError:
            # Re-raise rate limit errors
            raise
        except Exception as e:
            # Log unexpected errors but don't fail the request
            logger.error(f"Rate limiting middleware error: {str(e)}")
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request headers."""
        # Check forwarded headers first (for load balancers/proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, get the first one
            return forwarded_for.split(",")[0].strip()
        
        # Check direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """
        Extract user ID from request if authenticated.
        
        This checks for authentication headers/cookies without fully
        authenticating the user to avoid performance overhead.
        """
        try:
            # Check for session cookie
            session_cookie = request.cookies.get("scribe_session")
            if session_cookie:
                return f"session:{session_cookie[:8]}"  # Use first 8 chars as identifier
            
            # Check for authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]
                return f"token:{token[:8]}"  # Use first 8 chars as identifier
            
            return None
            
        except Exception:
            # If we can't extract user info, just return None
            return None
    
    def _add_rate_limit_headers(
        self, 
        response: Response, 
        last_check: Optional[Tuple[str, str, int, int]]
    ) -> None:
        """Add rate limiting information to response headers."""
        if not last_check:
            return
            
        limit_type, key, limit, window = last_check
        
        try:
            # Get current count for the key
            allowed, current, remaining = self.limiter.is_allowed(key, limit + 1, window)  # +1 to not trigger limit
            
            # Add standard rate limiting headers
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)
            response.headers["X-RateLimit-Window"] = str(window)
            
        except Exception as e:
            logger.debug(f"Failed to add rate limit headers: {str(e)}")
            # Don't fail if we can't add headers