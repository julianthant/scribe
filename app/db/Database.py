"""
Database.py - Core Database Configuration

Provides database connectivity and session management for the Scribe application using SQLAlchemy 2.0.
This module handles:
- Async database engine configuration for Azure SQL Server
- Connection pooling with Azure-optimized settings
- Session factories with proper transaction management
- Row-Level Security (RLS) session context support
- Connection lifecycle management

The database configuration supports async operations for Azure SQL Server 
with proper connection string formatting and error handling.
"""

import logging
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from sqlalchemy import NullPool, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from app.core.config import settings
from app.core.Exceptions import DatabaseError
from app.models.DatabaseModel import Base
from app.azure.AzureDatabaseService import azure_database_service

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self) -> None:
        self._async_engine: Optional[AsyncEngine] = None
        self._async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    
    def _build_sql_credentials_connection_string(self, async_mode: bool = True) -> str:
        """Build connection string using SQL Server credentials for migrations."""
        database_server = getattr(settings, 'database_server', '')
        database_name = getattr(settings, 'database_name', '')
        username = getattr(settings, 'database_username', '')
        password = getattr(settings, 'database_password', '')
        
        if not all([database_server, database_name, username, password]):
            raise DatabaseError(
                "SQL credentials not configured. Please set database_username and database_password in .secrets.toml",
                error_code="SQL_CREDENTIALS_MISSING",
                details={
                    "database_server": bool(database_server),
                    "database_name": bool(database_name),
                    "database_username": bool(username),
                    "database_password": bool(password)
                }
            )
        
        # Connection string with SQL Server authentication
        driver_name = '{ODBC Driver 18 for SQL Server}'
        
        # Use configurable timeouts for Azure SQL Database
        connection_timeout = getattr(settings, 'database_connection_timeout', 30)
        command_timeout = getattr(settings, 'database_command_timeout', 60)
        login_timeout = getattr(settings, 'database_login_timeout', 30)
        
        base_connection_string = (
            f'Driver={driver_name};'
            f'Server=tcp:{database_server},1433;'
            f'Database={database_name};'
            f'Uid={username};'
            f'Pwd={password};'
            f'Encrypt=yes;'
            f'TrustServerCertificate=no;'
            f'Connection Timeout={connection_timeout};'
            f'Command Timeout={command_timeout};'
            f'LoginTimeout={login_timeout}'
        )
        
        # URL encode the connection string
        params = urllib.parse.quote(base_connection_string)
        
        # Use appropriate dialect for async/sync
        dialect = "mssql+aioodbc" if async_mode else "mssql+pyodbc"
        
        return f"{dialect}:///?odbc_connect={params}"

    def _build_connection_string(self, async_mode: bool = True, use_sql_auth: bool = False) -> str:
        """Build Azure SQL connection string with specified authentication method."""
        if use_sql_auth:
            return self._build_sql_credentials_connection_string(async_mode)
            
        # Existing Azure AD authentication logic
        database_url = getattr(settings, 'database_url', None)
        
        if database_url:
            # Use provided database URL
            if async_mode and not database_url.startswith("mssql+aioodbc://"):
                # Convert sync URL to async if needed
                return database_url.replace("mssql+pyodbc://", "mssql+aioodbc://", 1)
            elif not async_mode and not database_url.startswith("mssql+pyodbc://"):
                # Convert async URL to sync if needed  
                return database_url.replace("mssql+aioodbc://", "mssql+pyodbc://", 1)
            return database_url
        
        # Build connection string from individual settings for Azure AD authentication
        database_server = getattr(settings, 'database_server', '')
        database_name = getattr(settings, 'database_name', '')
        
        if not database_server or not database_name:
            raise DatabaseError(
                "Database connection not configured. Please set database_server and database_name in settings.toml or provide database_url",
                error_code="DATABASE_CONFIG_MISSING",
                details={"database_server": database_server, "database_name": database_name}
            )
        
        # Simple connection string format for Azure AD authentication (no username/password)
        driver_name = '{ODBC Driver 18 for SQL Server}'
        
        # Build base connection string without username/password for Azure AD
        # Use configurable timeouts for Azure SQL Database
        connection_timeout = getattr(settings, 'database_connection_timeout', 30)
        command_timeout = getattr(settings, 'database_command_timeout', 60)
        login_timeout = getattr(settings, 'database_login_timeout', 30)
        
        base_connection_string = (
            f'Driver={driver_name};'
            f'Server=tcp:{database_server},1433;'
            f'Database={database_name};'
            f'Encrypt=yes;'
            f'TrustServerCertificate=no;'
            f'Connection Timeout={connection_timeout};'
            f'Command Timeout={command_timeout};'
            f'LoginTimeout={login_timeout}'
        )
        
        # URL encode the connection string
        params = urllib.parse.quote(base_connection_string)
        
        # Use appropriate dialect for async/sync
        dialect = "mssql+aioodbc" if async_mode else "mssql+pyodbc"
        
        return f"{dialect}:///?odbc_connect={params}"
    
    def _configure_azure_access_token(self, engine: AsyncEngine) -> None:
        """Configure Azure AD access token authentication if enabled."""
        if not azure_database_service.is_token_authentication_enabled():
            return
        
        try:
            @event.listens_for(engine.sync_engine, "do_connect")
            def provide_token(dialect, conn_rec, cargs, cparams):
                """Inject Azure AD token into connection parameters."""
                logger.debug("Injecting Azure AD token for database connection")
                
                # Get connection attributes from Azure service
                attrs = azure_database_service.get_connection_attrs()
                if attrs:
                    cparams["attrs_before"] = attrs
                    logger.debug("Azure AD token applied to connection")
            
            logger.info("Azure AD access token authentication configured")
        
        except Exception as e:
            logger.error(f"Failed to configure Azure AD access token: {e}")
            # Don't raise exception - allow connection without token
    
    @property
    def async_engine(self) -> AsyncEngine:
        """Get or create async database engine."""
        if self._async_engine is None:
            connection_string = self._build_connection_string(async_mode=True)
            
            # SQL echoing disabled to keep startup output clean
            enable_echo = False
            
            self._async_engine = create_async_engine(
                connection_string,
                echo=enable_echo,
                poolclass=NullPool,  # Azure SQL works better with NullPool
                # Azure SQL specific settings
                execution_options={
                    "isolation_level": "READ_COMMITTED"
                }
            )
            
            # Configure Azure AD token authentication
            self._configure_azure_access_token(self._async_engine)
            
            logger.info("Async database engine configured for Azure SQL")
        
        return self._async_engine
    
    @property
    def async_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create async session factory."""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
        
        return self._async_session_factory
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session with proper cleanup."""
        session = self.async_session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise DatabaseError(
                "Database operation failed",
                error_code="DB_SESSION_ERROR",
                details={"error": str(e)}
            )
        finally:
            await session.close()
    
    async def set_rls_context(self, session: AsyncSession, context: Dict[str, Any]) -> None:
        """Set Row-Level Security context for the session."""
        if not getattr(settings, 'enable_rls', False):
            return
        
        try:
            # Set organization ID for tenant isolation
            if "organization_id" in context:
                await session.execute(
                    text("EXEC sp_set_session_context @key=N'OrganizationId', @value=:org_id"),
                    {"org_id": context["organization_id"]}
                )
            
            # Set user ID for user-based RLS
            if "user_id" in context:
                await session.execute(
                    text("EXEC sp_set_session_context @key=N'UserId', @value=:user_id"),
                    {"user_id": context["user_id"]}
                )
            
            # Set superuser flag for RLS bypass
            if "is_superuser" in context:
                await session.execute(
                    text("EXEC sp_set_session_context @key=N'IsSuperUser', @value=:is_super"),
                    {"is_super": 1 if context["is_superuser"] else 0}
                )
            
            logger.debug(f"RLS context set: {context}")
        
        except Exception as e:
            logger.error(f"Failed to set RLS context: {e}")
            raise DatabaseError(
                "Failed to set security context",
                error_code="DB_RLS_ERROR",
                details={"context": context, "error": str(e)}
            )
    
    async def clear_rls_context(self, session: AsyncSession) -> None:
        """Clear Row-Level Security context for a database session."""
        if not getattr(settings, 'enable_rls', False):
            return
        
        try:
            await session.execute(text("EXEC sp_set_session_context @key=N'OrganizationId', @value=NULL"))
            await session.execute(text("EXEC sp_set_session_context @key=N'UserId', @value=NULL"))
            await session.execute(text("EXEC sp_set_session_context @key=N'IsSuperUser', @value=0"))
            logger.debug("RLS context cleared")
        except Exception as e:
            logger.error(f"Failed to clear RLS context: {e}")
    
    async def health_check(self, max_retries: int = 2) -> bool:
        """Check database connectivity with retry mechanism."""
        import asyncio
        
        for attempt in range(max_retries + 1):
            try:
                async with self.get_async_session() as session:
                    result = await session.execute(text("SELECT 1"))
                    is_healthy = result.scalar() == 1
                    if is_healthy and attempt > 0:
                        logger.info(f"Database connection successful on attempt {attempt + 1}")
                    return is_healthy
            except Exception as e:
                if attempt < max_retries:
                    wait_time = (attempt + 1) * 2  # Exponential backoff: 2, 4 seconds
                    logger.warning(f"Database health check failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    logger.info(f"Retrying database connection in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Database health check failed after {max_retries + 1} attempts: {e}")
                    return False
        return False
    
    async def get_database_info(self) -> Dict[str, Any]:
        """Get information about the database."""
        try:
            async with self.get_async_session() as session:
                # Get SQL Server version info
                version_result = await session.execute(text("SELECT @@VERSION"))
                version = version_result.scalar()
                
                # Get database name
                db_name_result = await session.execute(text("SELECT DB_NAME()"))
                db_name = db_name_result.scalar()
                
                # Get current user
                user_result = await session.execute(text("SELECT SYSTEM_USER"))
                user = user_result.scalar()
                
                return {
                    "version": version,
                    "database_name": db_name,
                    "current_user": user,
                    "azure_authentication": azure_database_service.is_token_authentication_enabled(),
                    "rls_enabled": getattr(settings, 'enable_rls', False),
                    "connection_successful": True
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "connection_successful": False,
                "error": str(e)
            }
    
    async def close(self) -> None:
        """Close all database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_factory = None
            logger.info("Database engine disposed")


# Global database manager instance
db_manager = DatabaseManager()


# Dependency injection functions
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with db_manager.get_async_session() as session:
        yield session


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency injection.
    
    This is the correct way to provide database sessions to FastAPI endpoints.
    The @asynccontextmanager decorator is not used here to ensure proper
    dependency injection behavior.
    """
    async with db_manager.get_async_session() as session:
        yield session


async def validate_database_connection() -> bool:
    """Validate database connectivity."""
    return await db_manager.health_check()


async def set_rls_context(
    session: AsyncSession, 
    organization_id: Optional[str] = None, 
    user_id: Optional[str] = None, 
    is_superuser: bool = False
) -> None:
    """Set Row-Level Security context for a database session."""
    context: dict[str, str | bool] = {}
    if organization_id is not None:
        context["organization_id"] = organization_id
    if user_id is not None:
        context["user_id"] = user_id
    if is_superuser:
        context["is_superuser"] = is_superuser
    
    if context:
        await db_manager.set_rls_context(session, context)


async def clear_rls_context(session: AsyncSession) -> None:
    """Clear Row-Level Security context for a database session."""
    await db_manager.clear_rls_context(session)
