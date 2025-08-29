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

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings, validate_required_settings
from app.core.Logging import (
    setup_logging, 
    log_startup_component,
    log_service_startup,
    get_logger
)
from app.models.BaseModel import WelcomeResponse, HealthResponse
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

# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan event handler."""
    startup_logger = get_logger("app.startup")
    
    # Startup
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
    
    # Start authentication state cleanup task
    from app.core.AuthState import cleanup_expired_tokens_periodically
    import asyncio
    cleanup_task = asyncio.create_task(cleanup_expired_tokens_periodically())
    startup_logger.info("[SERVICE] Started authentication state cleanup task")
    
    # Calculate total startup time
    total_startup_time = (time.time() - app_start_time) * 1000
    startup_logger.info("\n" + "="*80)
    startup_logger.info(f"[READY] SCRIBE API READY - Total startup time: {total_startup_time:.2f}ms")
    startup_logger.info(f"[URL] Server available at: http://localhost:8000")
    startup_logger.info(f"[URL] API Documentation: http://localhost:8000/docs")
    startup_logger.info(f"[URL] Health Check: http://localhost:8000/health")
    startup_logger.info("="*80 + "\n")
    
    yield
    
    # Shutdown cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    startup_logger.info("[CLEANUP] Authentication cleanup task stopped")
    
    # Shutdown
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


# Initialize FastAPI application
fastapi_start_time = time.time()
app = FastAPI(
    title=settings.app_name,
    description="A FastAPI application with strict coding standards",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan
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

# Setup all middleware
from app.core.MiddlewareSetup import setup_middleware
setup_middleware(app)

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

# Setup exception handlers
from app.core.ExceptionHandlers import setup_exception_handlers
setup_exception_handlers(app)

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