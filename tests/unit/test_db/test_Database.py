"""
Unit tests for app.db.Database module.

Tests cover:
- DatabaseManager class functionality
- Connection string building (SQL auth and Azure AD auth)
- Async engine and session factory creation
- Session context management and cleanup
- Row-Level Security (RLS) context handling
- Health checks and database info
- Error handling and exceptions
"""

import pytest
import urllib.parse
from unittest.mock import patch, MagicMock, AsyncMock, call
from contextlib import asynccontextmanager
from typing import Dict, Any

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker
from sqlalchemy import text

from app.db.Database import DatabaseManager
from app.core.Exceptions import DatabaseError


class TestDatabaseManagerInitialization:
    """Test DatabaseManager initialization."""

    def test_database_manager_initialization(self):
        """Test DatabaseManager initializes with None values."""
        db_manager = DatabaseManager()
        
        assert db_manager._async_engine is None
        assert db_manager._async_session_factory is None

    def test_database_manager_singleton_behavior(self):
        """Test that DatabaseManager instances are independent."""
        db_manager1 = DatabaseManager()
        db_manager2 = DatabaseManager()
        
        # Should be different instances
        assert db_manager1 is not db_manager2
        assert db_manager1._async_engine is db_manager2._async_engine is None


class TestConnectionStringBuilding:
    """Test connection string building methods."""

    @patch('app.db.Database.settings')
    def test_build_sql_credentials_connection_string_success(self, mock_settings):
        """Test building SQL credentials connection string successfully."""
        mock_settings.database_server = "test-server.database.windows.net"
        mock_settings.database_name = "test-database"
        mock_settings.database_username = "test-user"
        mock_settings.database_password = "test-password"
        
        db_manager = DatabaseManager()
        connection_string = db_manager._build_sql_credentials_connection_string(async_mode=True)
        
        # Should contain AIOODBC dialect for async
        assert connection_string.startswith("mssql+aioodbc:///?odbc_connect=")
        
        # Decode the connection parameters
        encoded_params = connection_string.split("=", 1)[1]
        decoded_params = urllib.parse.unquote(encoded_params)
        
        assert "test-server.database.windows.net" in decoded_params
        assert "test-database" in decoded_params
        assert "test-user" in decoded_params
        assert "test-password" in decoded_params

    @patch('app.db.Database.settings')
    def test_build_sql_credentials_connection_string_sync_mode(self, mock_settings):
        """Test building SQL credentials connection string for sync mode."""
        mock_settings.database_server = "test-server.database.windows.net"
        mock_settings.database_name = "test-database"
        mock_settings.database_username = "test-user"
        mock_settings.database_password = "test-password"
        
        db_manager = DatabaseManager()
        connection_string = db_manager._build_sql_credentials_connection_string(async_mode=False)
        
        # Should contain PYODBC dialect for sync
        assert connection_string.startswith("mssql+pyodbc:///?odbc_connect=")

    @patch('app.db.Database.settings')
    def test_build_sql_credentials_connection_string_missing_config(self, mock_settings):
        """Test building SQL credentials connection string with missing configuration."""
        mock_settings.database_server = ""  # Missing
        mock_settings.database_name = "test-database"
        mock_settings.database_username = "test-user"
        mock_settings.database_password = "test-password"
        
        db_manager = DatabaseManager()
        
        with pytest.raises(DatabaseError) as exc_info:
            db_manager._build_sql_credentials_connection_string()
        
        assert exc_info.value.error_code == "SQL_CREDENTIALS_MISSING"
        assert "SQL credentials not configured" in exc_info.value.message

    @patch('app.db.Database.settings')
    def test_build_connection_string_with_sql_auth(self, mock_settings):
        """Test build_connection_string method with SQL authentication."""
        mock_settings.database_server = "test-server.database.windows.net"
        mock_settings.database_name = "test-database"
        mock_settings.database_username = "test-user"
        mock_settings.database_password = "test-password"
        
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, '_build_sql_credentials_connection_string') as mock_build_sql:
            mock_build_sql.return_value = "mssql+aioodbc://test-connection-string"
            
            connection_string = db_manager._build_connection_string(async_mode=True, use_sql_auth=True)
            
            assert connection_string == "mssql+aioodbc://test-connection-string"
            mock_build_sql.assert_called_once_with(True)

    @patch('app.db.Database.settings')
    def test_build_connection_string_with_database_url(self, mock_settings):
        """Test build_connection_string with provided database_url."""
        mock_settings.database_url = "mssql+aioodbc://test-url-connection"
        
        db_manager = DatabaseManager()
        connection_string = db_manager._build_connection_string(async_mode=True)
        
        assert connection_string == "mssql+aioodbc://test-url-connection"

    @patch('app.db.Database.settings')
    def test_build_connection_string_url_conversion_async_to_sync(self, mock_settings):
        """Test database URL conversion from async to sync."""
        mock_settings.database_url = "mssql+aioodbc://test-connection"
        
        db_manager = DatabaseManager()
        connection_string = db_manager._build_connection_string(async_mode=False)
        
        assert connection_string == "mssql+pyodbc://test-connection"

    @patch('app.db.Database.settings')
    def test_build_connection_string_azure_ad_auth(self, mock_settings):
        """Test build_connection_string with Azure AD authentication."""
        mock_settings.database_url = None
        mock_settings.database_server = "test-server.database.windows.net"
        mock_settings.database_name = "test-database"
        
        db_manager = DatabaseManager()
        connection_string = db_manager._build_connection_string(async_mode=True, use_sql_auth=False)
        
        assert connection_string.startswith("mssql+aioodbc:///?odbc_connect=")
        
        # Decode and check contents
        encoded_params = connection_string.split("=", 1)[1]
        decoded_params = urllib.parse.unquote(encoded_params)
        
        assert "test-server.database.windows.net" in decoded_params
        assert "test-database" in decoded_params
        # Should NOT contain username/password for Azure AD auth
        assert "Uid=" not in decoded_params
        assert "Pwd=" not in decoded_params

    @patch('app.db.Database.settings')
    def test_build_connection_string_missing_azure_config(self, mock_settings):
        """Test build_connection_string with missing Azure configuration."""
        mock_settings.database_url = None
        mock_settings.database_server = ""  # Missing
        mock_settings.database_name = "test-database"
        
        db_manager = DatabaseManager()
        
        with pytest.raises(DatabaseError) as exc_info:
            db_manager._build_connection_string(async_mode=True, use_sql_auth=False)
        
        assert exc_info.value.error_code == "DATABASE_CONFIG_MISSING"
        assert "Database connection not configured" in exc_info.value.message


class TestAzureAccessTokenConfiguration:
    """Test Azure AD access token configuration."""

    @patch('app.db.Database.azure_database_service')
    @patch('app.db.Database.event')
    @patch('app.db.Database.logger')
    def test_configure_azure_access_token_enabled(self, mock_logger, mock_event, mock_azure_service):
        """Test Azure access token configuration when enabled."""
        mock_azure_service.is_token_authentication_enabled.return_value = True
        mock_azure_service.get_connection_attrs.return_value = {"access_token": "test-token"}
        
        db_manager = DatabaseManager()
        mock_engine = MagicMock()
        mock_engine.sync_engine = MagicMock()
        
        db_manager._configure_azure_access_token(mock_engine)
        
        mock_azure_service.is_token_authentication_enabled.assert_called_once()
        mock_event.listens_for.assert_called_once_with(mock_engine.sync_engine, "do_connect")
        mock_logger.info.assert_called_with("Azure AD access token authentication configured")

    @patch('app.db.Database.azure_database_service')
    @patch('app.db.Database.logger')
    def test_configure_azure_access_token_disabled(self, mock_logger, mock_azure_service):
        """Test Azure access token configuration when disabled."""
        mock_azure_service.is_token_authentication_enabled.return_value = False
        
        db_manager = DatabaseManager()
        mock_engine = MagicMock()
        
        db_manager._configure_azure_access_token(mock_engine)
        
        mock_azure_service.is_token_authentication_enabled.assert_called_once()
        # Should return early without configuring
        mock_logger.info.assert_not_called()

    @patch('app.db.Database.azure_database_service')
    @patch('app.db.Database.event')
    @patch('app.db.Database.logger')
    def test_configure_azure_access_token_exception(self, mock_logger, mock_event, mock_azure_service):
        """Test Azure access token configuration with exception."""
        mock_azure_service.is_token_authentication_enabled.return_value = True
        mock_event.listens_for.side_effect = Exception("Configuration error")
        
        db_manager = DatabaseManager()
        mock_engine = MagicMock()
        
        # Should not raise exception, just log error
        db_manager._configure_azure_access_token(mock_engine)
        
        mock_logger.error.assert_called_with("Failed to configure Azure AD access token: Configuration error")


class TestAsyncEngineProperty:
    """Test async engine property."""

    @patch('app.db.Database.create_async_engine')
    @patch('app.db.Database.logger')
    def test_async_engine_creation(self, mock_logger, mock_create_engine):
        """Test async engine creation and configuration."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, '_build_connection_string') as mock_build_conn, \
             patch.object(db_manager, '_configure_azure_access_token') as mock_configure_token:
            
            mock_build_conn.return_value = "mssql+aioodbc://test-connection"
            
            engine = db_manager.async_engine
            
            assert engine == mock_engine
            assert db_manager._async_engine == mock_engine
            
            mock_build_conn.assert_called_once_with(async_mode=True)
            mock_create_engine.assert_called_once()
            mock_configure_token.assert_called_once_with(mock_engine)
            mock_logger.info.assert_called_with("Async database engine configured for Azure SQL")

    @patch('app.db.Database.create_async_engine')
    def test_async_engine_caching(self, mock_create_engine):
        """Test that async engine is cached after first creation."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, '_build_connection_string') as mock_build_conn, \
             patch.object(db_manager, '_configure_azure_access_token'):
            
            mock_build_conn.return_value = "mssql+aioodbc://test-connection"
            
            # First access
            engine1 = db_manager.async_engine
            # Second access
            engine2 = db_manager.async_engine
            
            assert engine1 is engine2
            # create_async_engine should only be called once
            mock_create_engine.assert_called_once()

    @patch('app.db.Database.create_async_engine')
    def test_async_engine_configuration_parameters(self, mock_create_engine):
        """Test async engine configuration parameters."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, '_build_connection_string') as mock_build_conn, \
             patch.object(db_manager, '_configure_azure_access_token'):
            
            mock_build_conn.return_value = "mssql+aioodbc://test-connection"
            
            db_manager.async_engine
            
            # Verify create_async_engine was called with correct parameters
            call_args = mock_create_engine.call_args
            assert call_args[0][0] == "mssql+aioodbc://test-connection"
            assert call_args[1]['echo'] == False
            assert call_args[1]['poolclass'] is sqlalchemy.pool.NullPool
            assert 'execution_options' in call_args[1]
            assert call_args[1]['execution_options']['isolation_level'] == "READ_COMMITTED"


class TestAsyncSessionFactory:
    """Test async session factory property."""

    def test_async_session_factory_creation(self):
        """Test async session factory creation."""
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, 'async_engine') as mock_engine:
            mock_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            
            with patch('app.db.Database.async_sessionmaker') as mock_sessionmaker:
                mock_factory = MagicMock()
                mock_sessionmaker.return_value = mock_factory
                
                factory = db_manager.async_session_factory
                
                assert factory == mock_factory
                assert db_manager._async_session_factory == mock_factory
                
                mock_sessionmaker.assert_called_once_with(
                    bind=mock_engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=True,
                    autocommit=False
                )

    def test_async_session_factory_caching(self):
        """Test that async session factory is cached."""
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, 'async_engine'), \
             patch('app.db.Database.async_sessionmaker') as mock_sessionmaker:
            
            mock_factory = MagicMock()
            mock_sessionmaker.return_value = mock_factory
            
            # First access
            factory1 = db_manager.async_session_factory
            # Second access
            factory2 = db_manager.async_session_factory
            
            assert factory1 is factory2
            # async_sessionmaker should only be called once
            mock_sessionmaker.assert_called_once()


class TestAsyncSessionContext:
    """Test async session context manager."""

    @pytest.mark.asyncio
    async def test_get_async_session_success(self):
        """Test successful async session context manager."""
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        
        with patch.object(db_manager, 'async_session_factory') as mock_factory:
            mock_factory.return_value = mock_session
            
            async with db_manager.get_async_session() as session:
                assert session == mock_session
            
            # Verify session lifecycle
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_async_session_exception_handling(self):
        """Test async session context manager exception handling."""
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        
        with patch.object(db_manager, 'async_session_factory') as mock_factory:
            mock_factory.return_value = mock_session
            
            with pytest.raises(DatabaseError) as exc_info:
                async with db_manager.get_async_session() as session:
                    raise ValueError("Test database error")
            
            # Verify exception handling
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.commit.assert_not_called()
            
            assert exc_info.value.error_code == "DB_SESSION_ERROR"
            assert "Database operation failed" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_async_session_commit_exception(self):
        """Test async session context manager with commit exception."""
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        mock_session.commit.side_effect = Exception("Commit failed")
        
        with patch.object(db_manager, 'async_session_factory') as mock_factory:
            mock_factory.return_value = mock_session
            
            with pytest.raises(DatabaseError):
                async with db_manager.get_async_session() as session:
                    pass  # No exception in user code
            
            # Should still attempt commit, then rollback on commit failure
            mock_session.commit.assert_called_once()
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()


class TestRLSContextManagement:
    """Test Row-Level Security context management."""

    @patch('app.db.Database.settings')
    @patch('app.db.Database.logger')
    @pytest.mark.asyncio
    async def test_set_rls_context_enabled(self, mock_logger, mock_settings):
        """Test setting RLS context when RLS is enabled."""
        mock_settings.enable_rls = True
        mock_session = AsyncMock()
        
        db_manager = DatabaseManager()
        context = {
            "organization_id": "org-123",
            "user_id": "user-456", 
            "is_superuser": True
        }
        
        await db_manager.set_rls_context(mock_session, context)
        
        # Verify all three context calls were made
        assert mock_session.execute.call_count == 3
        
        # Check organization ID call
        org_call = mock_session.execute.call_args_list[0]
        assert "OrganizationId" in str(org_call[0][0])
        assert org_call[1]["org_id"] == "org-123"
        
        # Check user ID call
        user_call = mock_session.execute.call_args_list[1]
        assert "UserId" in str(user_call[0][0])
        assert user_call[1]["user_id"] == "user-456"
        
        # Check superuser call
        super_call = mock_session.execute.call_args_list[2]
        assert "IsSuperUser" in str(super_call[0][0])
        assert super_call[1]["is_super"] == 1  # True converts to 1
        
        mock_logger.debug.assert_called_with(f"RLS context set: {context}")

    @patch('app.db.Database.settings')
    @pytest.mark.asyncio
    async def test_set_rls_context_disabled(self, mock_settings):
        """Test setting RLS context when RLS is disabled."""
        mock_settings.enable_rls = False
        mock_session = AsyncMock()
        
        db_manager = DatabaseManager()
        context = {"organization_id": "org-123"}
        
        await db_manager.set_rls_context(mock_session, context)
        
        # Should return early without executing any SQL
        mock_session.execute.assert_not_called()

    @patch('app.db.Database.settings')
    @pytest.mark.asyncio
    async def test_set_rls_context_partial_context(self, mock_settings):
        """Test setting RLS context with partial context data."""
        mock_settings.enable_rls = True
        mock_session = AsyncMock()
        
        db_manager = DatabaseManager()
        context = {"user_id": "user-456"}  # Only user_id, no org or superuser
        
        await db_manager.set_rls_context(mock_session, context)
        
        # Should only call execute once for user_id
        mock_session.execute.assert_called_once()
        user_call = mock_session.execute.call_args_list[0]
        assert "UserId" in str(user_call[0][0])
        assert user_call[1]["user_id"] == "user-456"

    @patch('app.db.Database.settings')
    @pytest.mark.asyncio
    async def test_set_rls_context_superuser_false(self, mock_settings):
        """Test setting RLS context with is_superuser=False."""
        mock_settings.enable_rls = True
        mock_session = AsyncMock()
        
        db_manager = DatabaseManager()
        context = {"is_superuser": False}
        
        await db_manager.set_rls_context(mock_session, context)
        
        mock_session.execute.assert_called_once()
        super_call = mock_session.execute.call_args_list[0]
        assert super_call[1]["is_super"] == 0  # False converts to 0

    @patch('app.db.Database.settings')
    @patch('app.db.Database.logger')
    @pytest.mark.asyncio
    async def test_set_rls_context_exception(self, mock_logger, mock_settings):
        """Test RLS context setting with database exception."""
        mock_settings.enable_rls = True
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("SQL execution failed")
        
        db_manager = DatabaseManager()
        context = {"organization_id": "org-123"}
        
        with pytest.raises(DatabaseError) as exc_info:
            await db_manager.set_rls_context(mock_session, context)
        
        assert exc_info.value.error_code == "DB_RLS_ERROR"
        assert "Failed to set security context" in exc_info.value.message
        mock_logger.error.assert_called()

    @patch('app.db.Database.settings')
    @patch('app.db.Database.logger')
    @pytest.mark.asyncio
    async def test_clear_rls_context_enabled(self, mock_logger, mock_settings):
        """Test clearing RLS context when RLS is enabled."""
        mock_settings.enable_rls = True
        mock_session = AsyncMock()
        
        db_manager = DatabaseManager()
        
        await db_manager.clear_rls_context(mock_session)
        
        # Should execute three clear statements
        assert mock_session.execute.call_count == 3
        
        # Verify all contexts are cleared (set to NULL or 0)
        calls = mock_session.execute.call_args_list
        assert "OrganizationId" in str(calls[0][0][0]) and "NULL" in str(calls[0][0][0])
        assert "UserId" in str(calls[1][0][0]) and "NULL" in str(calls[1][0][0])
        assert "IsSuperUser" in str(calls[2][0][0]) and "0" in str(calls[2][0][0])
        
        mock_logger.debug.assert_called_with("RLS context cleared")

    @patch('app.db.Database.settings')
    @pytest.mark.asyncio
    async def test_clear_rls_context_disabled(self, mock_settings):
        """Test clearing RLS context when RLS is disabled."""
        mock_settings.enable_rls = False
        mock_session = AsyncMock()
        
        db_manager = DatabaseManager()
        
        await db_manager.clear_rls_context(mock_session)
        
        # Should return early without executing any SQL
        mock_session.execute.assert_not_called()

    @patch('app.db.Database.settings')
    @patch('app.db.Database.logger')
    @pytest.mark.asyncio
    async def test_clear_rls_context_exception(self, mock_logger, mock_settings):
        """Test clearing RLS context with database exception."""
        mock_settings.enable_rls = True
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Clear failed")
        
        db_manager = DatabaseManager()
        
        # Should not raise exception, just log error
        await db_manager.clear_rls_context(mock_session)
        
        mock_logger.error.assert_called_with("Failed to clear RLS context: Clear failed")


class TestHealthCheck:
    """Test database health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful database health check."""
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result
        
        with patch.object(db_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None
            
            result = await db_manager.health_check()
            
            assert result is True
            mock_session.execute.assert_called_once()
            # Verify SELECT 1 query
            call_args = mock_session.execute.call_args[0][0]
            assert "SELECT 1" in str(call_args)

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test database health check failure."""
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, 'get_async_session') as mock_get_session, \
             patch('app.db.Database.logger') as mock_logger:
            
            mock_get_session.side_effect = Exception("Connection failed")
            
            result = await db_manager.health_check()
            
            assert result is False
            mock_logger.error.assert_called_with("Database health check failed: Connection failed")

    @pytest.mark.asyncio
    async def test_health_check_wrong_result(self):
        """Test database health check with unexpected result."""
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0  # Not 1
        mock_session.execute.return_value = mock_result
        
        with patch.object(db_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None
            
            result = await db_manager.health_check()
            
            assert result is False


class TestGetDatabaseInfo:
    """Test database information retrieval."""

    @patch('app.db.Database.azure_database_service')
    @patch('app.db.Database.settings')
    @pytest.mark.asyncio
    async def test_get_database_info_success(self, mock_settings, mock_azure_service):
        """Test successful database info retrieval."""
        mock_settings.enable_rls = True
        mock_azure_service.is_token_authentication_enabled.return_value = True
        
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        
        # Mock query results
        version_result = MagicMock()
        version_result.scalar.return_value = "Microsoft SQL Server 2019"
        
        db_name_result = MagicMock()
        db_name_result.scalar.return_value = "ScribeDatabase"
        
        user_result = MagicMock()
        user_result.scalar.return_value = "scribe@domain.com"
        
        mock_session.execute.side_effect = [version_result, db_name_result, user_result]
        
        with patch.object(db_manager, 'get_async_session') as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None
            
            info = await db_manager.get_database_info()
            
            expected_info = {
                "version": "Microsoft SQL Server 2019",
                "database_name": "ScribeDatabase", 
                "current_user": "scribe@domain.com",
                "azure_authentication": True,
                "rls_enabled": True,
                "connection_successful": True
            }
            
            assert info == expected_info
            
            # Verify all three queries were executed
            assert mock_session.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_get_database_info_exception(self):
        """Test database info retrieval with exception."""
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, 'get_async_session') as mock_get_session, \
             patch('app.db.Database.logger') as mock_logger:
            
            mock_get_session.side_effect = Exception("Database connection failed")
            
            info = await db_manager.get_database_info()
            
            expected_info = {
                "version": None,
                "database_name": None,
                "current_user": None,
                "azure_authentication": False,
                "rls_enabled": False,
                "connection_successful": False,
                "error": "Database connection failed"
            }
            
            assert info == expected_info
            mock_logger.error.assert_called_with("Failed to get database info: Database connection failed")

    @patch('app.db.Database.azure_database_service')
    @patch('app.db.Database.settings')
    @pytest.mark.asyncio
    async def test_get_database_info_partial_failure(self, mock_settings, mock_azure_service):
        """Test database info retrieval with partial query failure."""
        mock_settings.enable_rls = False
        mock_azure_service.is_token_authentication_enabled.return_value = False
        
        db_manager = DatabaseManager()
        mock_session = AsyncMock()
        
        # First query succeeds, second fails
        version_result = MagicMock()
        version_result.scalar.return_value = "Microsoft SQL Server 2019"
        
        mock_session.execute.side_effect = [
            version_result,
            Exception("Query failed"),  # DB name query fails
        ]
        
        with patch.object(db_manager, 'get_async_session') as mock_get_session, \
             patch('app.db.Database.logger') as mock_logger:
            
            mock_get_session.return_value.__aenter__.return_value = mock_session
            mock_get_session.return_value.__aexit__.return_value = None
            
            info = await db_manager.get_database_info()
            
            # Should return error info structure
            assert info["connection_successful"] is False
            assert "error" in info
            mock_logger.error.assert_called()


class TestDatabaseManagerIntegration:
    """Integration tests for DatabaseManager functionality."""

    def test_properties_create_instances_once(self):
        """Test that properties create instances only once."""
        db_manager = DatabaseManager()
        
        with patch('app.db.Database.create_async_engine') as mock_create_engine, \
             patch('app.db.Database.async_sessionmaker') as mock_sessionmaker, \
             patch.object(db_manager, '_build_connection_string') as mock_build_conn, \
             patch.object(db_manager, '_configure_azure_access_token'):
            
            mock_engine = MagicMock()
            mock_factory = MagicMock()
            mock_create_engine.return_value = mock_engine
            mock_sessionmaker.return_value = mock_factory
            mock_build_conn.return_value = "test-connection-string"
            
            # Access properties multiple times
            engine1 = db_manager.async_engine
            engine2 = db_manager.async_engine
            factory1 = db_manager.async_session_factory
            factory2 = db_manager.async_session_factory
            
            # Should return same instances
            assert engine1 is engine2 is mock_engine
            assert factory1 is factory2 is mock_factory
            
            # Should only create once
            mock_create_engine.assert_called_once()
            mock_sessionmaker.assert_called_once()

    @patch('app.db.Database.settings')
    def test_connection_string_building_integration(self, mock_settings):
        """Test integration between different connection string building methods."""
        # Test with provided database_url
        mock_settings.database_url = "mssql+aioodbc://test-url"
        
        db_manager = DatabaseManager()
        connection_string = db_manager._build_connection_string()
        
        assert connection_string == "mssql+aioodbc://test-url"
        
        # Test with individual settings (Azure AD auth)
        mock_settings.database_url = None
        mock_settings.database_server = "test-server.database.windows.net"
        mock_settings.database_name = "test-database"
        
        connection_string = db_manager._build_connection_string()
        
        assert connection_string.startswith("mssql+aioodbc:///?odbc_connect=")
        assert "test-server.database.windows.net" in connection_string

    @pytest.mark.asyncio
    async def test_session_and_rls_integration(self):
        """Test integration between session management and RLS context."""
        db_manager = DatabaseManager()
        
        with patch.object(db_manager, 'async_session_factory') as mock_factory, \
             patch('app.db.Database.settings') as mock_settings:
            
            mock_settings.enable_rls = True
            mock_session = AsyncMock()
            mock_factory.return_value = mock_session
            
            context = {"organization_id": "org-123", "user_id": "user-456"}
            
            async with db_manager.get_async_session() as session:
                await db_manager.set_rls_context(session, context)
                # Session operations would happen here
                await db_manager.clear_rls_context(session)
            
            # Verify session lifecycle
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
            
            # Verify RLS operations (2 sets + 3 clears)
            assert mock_session.execute.call_count == 5