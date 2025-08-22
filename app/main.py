"""
main.py - FastAPI Application Entry Point

This is the main application file that configures and initializes the Scribe FastAPI application.
It sets up:
- FastAPI application with title, description, and version
- CORS middleware for cross-origin requests
- Request logging middleware to track API usage
- Global exception handlers for standardized error responses
- Static file serving
- API v1 router integration
- Root endpoints for welcome and health checks

The application provides a REST API for email operations with Azure AD authentication.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logging import setup_logging, log_api_request
from app.core.exceptions import (
    ScribeBaseException,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    RateLimitError
)
from app.models.default import ErrorResponse, WelcomeResponse, HealthResponse
from app.api.v1.router import router as v1_router
import time

# Setup logging
setup_logging()

app = FastAPI(
    title=settings.app_name,
    description="A FastAPI application with strict coding standards",
    version=settings.app_version,
    debug=settings.debug
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(v1_router, prefix=settings.api_v1_prefix)

# Exception handlers
@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, 
    exc: ValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Validation Error",
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        ).model_dump()
    )

@app.exception_handler(NotFoundError)
async def not_found_exception_handler(
    request: Request, 
    exc: NotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="Not Found",
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        ).model_dump()
    )

@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(
    request: Request, 
    exc: AuthenticationError
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=ErrorResponse(
            error="Authentication Error",
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        ).model_dump()
    )

@app.exception_handler(AuthorizationError)
async def authorization_exception_handler(
    request: Request, 
    exc: AuthorizationError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=ErrorResponse(
            error="Authorization Error",
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        ).model_dump()
    )

@app.exception_handler(DatabaseError)
async def database_exception_handler(
    request: Request, 
    exc: DatabaseError
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Database Error",
            message="An internal database error occurred",
            error_code=exc.error_code,
            details={"operation": exc.details.get("operation")} if exc.details else None
        ).model_dump()
    )

@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(
    request: Request, 
    exc: RateLimitError
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error="Rate Limit Exceeded",
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        ).model_dump()
    )

@app.exception_handler(ScribeBaseException)
async def scribe_exception_handler(
    request: Request, 
    exc: ScribeBaseException
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Error",
            message=exc.message,
            error_code=exc.error_code,
            details=exc.details
        ).model_dump()
    )

# Root endpoints
@app.get("/", response_model=WelcomeResponse)
async def root() -> WelcomeResponse:
    """Welcome endpoint."""
    return WelcomeResponse(
        message="Welcome to Scribe API",
        version=settings.app_version,
        docs_url="/docs"
    )

@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version
    )