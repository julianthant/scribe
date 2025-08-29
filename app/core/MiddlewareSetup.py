"""
MiddlewareSetup.py - Centralized Middleware Configuration

This module handles all middleware setup for the FastAPI application including:
- CORS middleware configuration
- Authentication middleware setup
- Request logging middleware
- Startup timing and logging for each middleware component

Extracted from main.py to improve code organization and maintainability.
"""

import time
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.Logging import log_startup_component, log_api_request
from app.middleware.AuthMiddleware import AuthenticationMiddleware
from app.middleware.RateLimitMiddleware import RateLimitMiddleware

if TYPE_CHECKING:
    from fastapi.responses import Response


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    _setup_cors_middleware(app)
    _setup_rate_limiting_middleware(app)
    _setup_authentication_middleware(app)
    _setup_request_logging_middleware(app)


def _setup_cors_middleware(app: FastAPI) -> None:
    """Configure CORS middleware with settings from configuration."""
    cors_start_time = time.time()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    log_startup_component(
        "CORS Middleware",
        cors_start_time,
        success=True,
        details={
            "Allowed Origins": len(settings.backend_cors_origins),
            "Allow Credentials": True
        }
    )


def _setup_rate_limiting_middleware(app: FastAPI) -> None:
    """Configure rate limiting middleware for API protection."""
    rate_limit_start_time = time.time()
    
    app.add_middleware(RateLimitMiddleware)
    
    log_startup_component(
        "Rate Limiting Middleware",
        rate_limit_start_time,
        success=True,
        details={
            "IP Limit": "60 req/min",
            "User Limit": "120 req/min",
            "Endpoint Limits": "Configured"
        }
    )


def _setup_authentication_middleware(app: FastAPI) -> None:
    """Configure authentication middleware for token and session handling."""
    auth_middleware_start_time = time.time()
    
    app.add_middleware(AuthenticationMiddleware)
    
    log_startup_component(
        "Authentication Middleware",
        auth_middleware_start_time,
        success=True,
        details={
            "Auto Header Injection": True,
            "Cookie Support": True
        }
    )


def _setup_request_logging_middleware(app: FastAPI) -> None:
    """Configure request logging middleware for API request tracking."""
    middleware_start_time = time.time()

    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> "Response":
        """Log all HTTP requests with timing and response information."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log the request
        log_api_request(
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            response_time=process_time,
            client_ip=request.client.host if request.client else "unknown"
        )
        
        return response

    log_startup_component(
        "Request Logging Middleware",
        middleware_start_time,
        success=True
    )