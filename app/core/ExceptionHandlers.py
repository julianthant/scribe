"""
ExceptionHandlers.py - Centralized Exception Handler Configuration

This module handles all global exception handlers for the FastAPI application including:
- ValidationError - 400 responses for validation failures
- NotFoundError - 404 responses for missing resources  
- AuthenticationError - 401 responses for authentication failures
- AuthorizationError - 403 responses for authorization failures
- DatabaseError - 500 responses for database errors
- RateLimitError - 429 responses for rate limit exceeded
- ScribeBaseException - 500 responses for general application errors

Extracted from main.py to improve code organization and maintainability.
"""

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.Exceptions import (
    ScribeBaseException,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    RateLimitError
)
from app.models.BaseModel import ErrorResponse

if TYPE_CHECKING:
    pass


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Configure all exception handlers for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(NotFoundError, not_found_exception_handler)
    app.add_exception_handler(AuthenticationError, authentication_exception_handler)
    app.add_exception_handler(AuthorizationError, authorization_exception_handler)
    app.add_exception_handler(DatabaseError, database_exception_handler)
    app.add_exception_handler(RateLimitError, rate_limit_exception_handler)
    app.add_exception_handler(ScribeBaseException, scribe_exception_handler)


async def validation_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle validation errors with 400 status code."""
    validation_exc = exc  # Type: ValidationError at runtime
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Validation Error",
            message=getattr(validation_exc, 'message', str(validation_exc)),
            error_code=getattr(validation_exc, 'error_code', None),
            details=getattr(validation_exc, 'details', None)
        ).model_dump(mode='json')
    )


async def not_found_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle not found errors with 404 status code."""
    not_found_exc = exc  # Type: NotFoundError at runtime
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="Not Found",
            message=getattr(not_found_exc, 'message', str(not_found_exc)),
            error_code=getattr(not_found_exc, 'error_code', None),
            details=getattr(not_found_exc, 'details', None)
        ).model_dump(mode='json')
    )


async def authentication_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle authentication errors with 401 status code."""
    auth_exc = exc  # Type: AuthenticationError at runtime
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(
            error="Authentication Error",
            message=getattr(auth_exc, 'message', str(auth_exc)),
            error_code=getattr(auth_exc, 'error_code', None),
            details=getattr(auth_exc, 'details', None)
        ).model_dump(mode='json')
    )


async def authorization_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle authorization errors with 403 status code."""
    authz_exc = exc  # Type: AuthorizationError at runtime
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(
            error="Authorization Error",
            message=getattr(authz_exc, 'message', str(authz_exc)),
            error_code=getattr(authz_exc, 'error_code', None),
            details=getattr(authz_exc, 'details', None)
        ).model_dump(mode='json')
    )


async def database_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle database errors with 500 status code."""
    db_exc = exc  # Type: DatabaseError at runtime
    details = getattr(db_exc, 'details', None)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Database Error",
            message="An internal database error occurred",
            error_code=getattr(db_exc, 'error_code', None),
            details={"operation": details.get("operation")} if details else None
        ).model_dump(mode='json')
    )


async def rate_limit_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle rate limit exceeded errors with 429 status code."""
    rate_limit_exc = exc  # Type: RateLimitError at runtime
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error="Rate Limit Exceeded",
            message=getattr(rate_limit_exc, 'message', str(rate_limit_exc)),
            error_code=getattr(rate_limit_exc, 'error_code', None),
            details=getattr(rate_limit_exc, 'details', None)
        ).model_dump(mode='json')
    )


async def scribe_exception_handler(
    request: Request, 
    exc: Exception
) -> JSONResponse:
    """Handle general application errors with 500 status code."""
    scribe_exc = exc  # Type: ScribeBaseException at runtime
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Error",
            message=getattr(scribe_exc, 'message', str(scribe_exc)),
            error_code=getattr(scribe_exc, 'error_code', None),
            details=getattr(scribe_exc, 'details', None)
        ).model_dump(mode='json')
    )