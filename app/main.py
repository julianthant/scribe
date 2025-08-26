"""
main.py - FastAPI Application Entry Point

This is the main application file that configures and initializes the Scribe FastAPI application.
It sets up:
- FastAPI application with title, description, and version
- CORS middleware for cross-origin requests
- Request logging middleware to track API usage
- Global exception handlers for standardized error responses
- API v1 router integration
- Root endpoints for welcome and health checks

The application provides a REST API for email operations with Azure AD authentication.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings, validate_required_settings
from app.core.Logging import (
    setup_logging, 
    log_api_request, 
    log_startup_component,
    log_service_startup,
    get_logger
)
from app.core.Exceptions import (
    ScribeBaseException,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    DatabaseError,
    RateLimitError
)
from app.models.BaseModel import ErrorResponse, WelcomeResponse, HealthResponse
from app.api.v1.router import router as v1_router
from app.core.Exceptions import DatabaseError
import time
import logging

# Application startup timing
app_start_time = time.time()

# Setup logging first
setup_logging()
startup_logger = get_logger("app.startup")

startup_logger.info("\n" + "="*80)
startup_logger.info("[STARTUP] SCRIBE API STARTUP SEQUENCE")
startup_logger.info("="*80)

# Validate configuration
config_start_time = time.time()
try:
    validate_required_settings()
    log_startup_component(
        "Configuration Validation",
        config_start_time,
        success=True,
        details={
            "Environment": settings.current_env,
            "Debug Mode": settings.debug,
            "API Version": settings.app_version
        }
    )
except Exception as e:
    log_startup_component(
        "Configuration Validation",
        config_start_time,
        success=False,
        error=e
    )
    raise

# Initialize FastAPI application
fastapi_start_time = time.time()
app = FastAPI(
    title=settings.app_name,
    description="A FastAPI application with strict coding standards",
    version=settings.app_version,
    debug=settings.debug
)
log_startup_component(
    "FastAPI Application",
    fastapi_start_time,
    success=True,
    details={
        "Title": settings.app_name,
        "Version": settings.app_version,
        "Debug": settings.debug
    }
)

# CORS Middleware
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

# Request logging middleware
middleware_start_time = time.time()

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

log_startup_component(
    "Request Logging Middleware",
    middleware_start_time,
    success=True
)

# Include routers
router_start_time = time.time()
app.include_router(v1_router, prefix=settings.api_v1_prefix)
log_startup_component(
    "API Routes",
    router_start_time,
    success=True,
    details={
        "API Prefix": settings.api_v1_prefix,
        "Router": "v1_router"
    }
)

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


# Startup event handler
@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    startup_logger = get_logger("app.startup")
    
    # Initialize and test database connection
    await initialize_database()
    
    # Log service configurations
    log_service_startup(
        "Cache Service",
        config_details={
            "Default TTL": f"{settings.cache_default_ttl}s",
            "Max Size": settings.cache_max_size,
            "Cleanup Interval": f"{settings.cache_cleanup_interval}s"
        }
    )
    
    log_service_startup(
        "Rate Limiting",
        config_details={
            "Requests per Window": settings.rate_limit_requests,
            "Window Duration": f"{settings.rate_limit_window}s"
        }
    )
    
    log_service_startup(
        "Azure AD OAuth",
        config_details={
            "Redirect URI": settings.azure_redirect_uri,
            "Scopes": len(settings.azure_scopes)
        }
    )
    
    # Calculate total startup time
    total_startup_time = (time.time() - app_start_time) * 1000
    startup_logger.info("\n" + "="*80)
    startup_logger.info(f"[READY] SCRIBE API READY - Total startup time: {total_startup_time:.2f}ms")
    startup_logger.info(f"[URL] Server available at: http://localhost:8000")
    startup_logger.info(f"[URL] API Documentation: http://localhost:8000/docs")
    startup_logger.info(f"[URL] Health Check: http://localhost:8000/health")
    startup_logger.info("="*80 + "\n")


async def initialize_database() -> None:
    """Initialize database connection and perform health checks."""
    from app.db.Database import db_manager
    
    db_start_time = time.time()
    db_logger = get_logger("app.database")
    
    try:
        db_logger.info("[DATABASE] Initializing database connection...")
        
        # Test database connection
        connection_test_start = time.time()
        is_healthy = await db_manager.health_check()
        connection_test_time = (time.time() - connection_test_start) * 1000
        
        if is_healthy:
            db_logger.info(f"[OK] Database connection established in {connection_test_time:.2f}ms")
            
            # Get database information
            db_info = await db_manager.get_database_info()
            
            if db_info.get("connection_successful"):
                db_logger.info(f"[DB-INFO] Database: {db_info.get('database_name')}")
                db_logger.info(f"[DB-INFO] Authentication: {'Azure AD Token' if db_info.get('azure_authentication') else 'SQL Credentials'}")
                db_logger.info(f"[DB-INFO] Row-Level Security: {'Enabled' if db_info.get('rls_enabled') else 'Disabled'}")
                db_logger.info(f"[DB-INFO] Database User: {db_info.get('current_user')}")
                
                # Log SQL Server version (first line only for brevity)
                version = db_info.get('version', '')
                if version:
                    version_line = version.split('\n')[0].strip()
                    db_logger.info(f"[DB-INFO] Server: {version_line}")
            
            log_startup_component(
                "Database Connection",
                db_start_time,
                success=True,
                details={
                    "Health Check Time": f"{connection_test_time:.2f}ms",
                    "Database Name": db_info.get('database_name', 'Unknown'),
                    "Authentication Type": 'Azure AD' if db_info.get('azure_authentication') else 'SQL',
                    "RLS Enabled": db_info.get('rls_enabled', False)
                }
            )
        else:
            raise DatabaseError(
                "Database health check failed",
                error_code="DB_HEALTH_CHECK_FAILED",
                details={"connection_test_time_ms": connection_test_time}
            )
            
    except Exception as e:
        db_logger.error(f"[ERROR] Database initialization failed: {str(e)}")
        log_startup_component(
            "Database Connection",
            db_start_time,
            success=False,
            error=e
        )
        raise


# Shutdown event handler
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    from app.db.Database import db_manager
    
    shutdown_logger = get_logger("app.shutdown")
    shutdown_logger.info("[SHUTDOWN] Scribe API shutting down...")
    
    # Cleanup database connections
    try:
        await db_manager.close()
        shutdown_logger.info("[CLEANUP] Database connections closed")
    except Exception as e:
        shutdown_logger.error(f"[ERROR] Error closing database connections: {e}")
    
    shutdown_logger.info("[SHUTDOWN] Goodbye!")