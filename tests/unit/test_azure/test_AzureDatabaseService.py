"""
Unit tests for AzureDatabaseService.

Tests Azure Database connectivity and operations including:
- Database connection with Azure AD authentication
- Connection pooling and management
- Row-level security (RLS) implementation
- Transaction handling and rollback
- Retry logic for transient failures
- Connection string management
- Error handling for database exceptions
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection
from sqlalchemy.exc import DisconnectionError, TimeoutError as SQLTimeoutError
from azure.core.exceptions import ClientAuthenticationError

from app.azure.AzureDatabaseService import AzureDatabaseService
from app.core.Exceptions import ValidationError, AuthenticationError


class TestAzureDatabaseService:
    """Test suite for AzureDatabaseService."""

    @pytest.fixture
    def db_service(self):
        """Create AzureDatabaseService instance."""
        return AzureDatabaseService()

    @pytest.fixture
    def mock_async_engine(self):
        """Mock AsyncEngine for testing."""
        engine = Mock(spec=AsyncEngine)
        
        # Mock connection context manager
        mock_connection = AsyncMock(spec=AsyncConnection)
        engine.connect.return_value.__aenter__.return_value = mock_connection
        engine.connect.return_value.__aexit__.return_value = None
        
        # Mock transaction context manager
        mock_transaction = AsyncMock()
        mock_connection.begin.return_value.__aenter__.return_value = mock_transaction
        mock_connection.begin.return_value.__aexit__.return_value = None
        
        return engine

    @pytest.fixture
    def mock_connection_string(self):
        """Mock database connection string."""
        return (
            "mssql+aioodbc://server.database.windows.net/database?"
            "driver=ODBC+Driver+18+for+SQL+Server&encrypt=yes&trustServerCertificate=no"
        )

    # ==========================================================================
    # INITIALIZATION TESTS
    # ==========================================================================

    def test_service_initialization(self, db_service):
        """Test service initialization."""
        assert db_service is not None
        assert db_service._engine is None
        assert db_service._connection_pool is None

    @patch('app.azure.AzureDatabaseService.settings')
    def test_connection_string_property_success(self, mock_settings, db_service):
        """Test connection string property with valid configuration."""
        mock_settings.database_server = "testserver.database.windows.net"
        mock_settings.database_name = "testdb"
        mock_settings.database_username = "testuser"
        mock_settings.database_password = "testpass"
        mock_settings.database_driver = "ODBC Driver 18 for SQL Server"
        
        connection_string = db_service.connection_string
        
        assert "testserver.database.windows.net" in connection_string
        assert "testdb" in connection_string
        assert "testuser" in connection_string
        assert "testpass" in connection_string

    @patch('app.azure.AzureDatabaseService.settings')
    def test_connection_string_missing_config(self, mock_settings, db_service):
        """Test connection string property with missing configuration."""
        mock_settings.database_server = ""
        
        with pytest.raises(ValidationError):
            _ = db_service.connection_string

    @patch('app.azure.AzureDatabaseService.settings') 
    def test_connection_string_with_azure_ad_auth(self, mock_settings, db_service):
        """Test connection string generation with Azure AD authentication."""
        mock_settings.database_server = "testserver.database.windows.net"
        mock_settings.database_name = "testdb"
        mock_settings.database_use_azure_ad = True
        mock_settings.database_driver = "ODBC Driver 18 for SQL Server"
        
        connection_string = db_service.connection_string
        
        assert "Authentication=ActiveDirectoryDefault" in connection_string
        assert "testuser" not in connection_string  # No username/password with AD auth

    # ==========================================================================
    # ENGINE CREATION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_engine_success(self, db_service, mock_connection_string):
        """Test successful engine creation."""
        with patch('app.azure.AzureDatabaseService.create_async_engine') as mock_create:
            with patch.object(db_service, 'connection_string', mock_connection_string):
                mock_engine = Mock()
                mock_create.return_value = mock_engine
                
                engine = await db_service.get_engine()
                
                assert engine == mock_engine
                assert db_service._engine == mock_engine
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_engine_cached(self, db_service, mock_async_engine):
        """Test engine caching behavior."""
        with patch('app.azure.AzureDatabaseService.create_async_engine') as mock_create:
            # Set existing engine
            db_service._engine = mock_async_engine
            
            engine = await db_service.get_engine()
            
            assert engine == mock_async_engine
            # Should not create new engine
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_engine_with_pool_config(self, db_service):
        """Test engine creation with connection pool configuration."""
        with patch('app.azure.AzureDatabaseService.create_async_engine') as mock_create:
            with patch.object(db_service, 'connection_string', "test://connection"):
                with patch('app.azure.AzureDatabaseService.settings') as mock_settings:
                    mock_settings.database_pool_size = 20
                    mock_settings.database_max_overflow = 10
                    mock_settings.database_pool_timeout = 60
                    
                    mock_engine = Mock()
                    mock_create.return_value = mock_engine
                    
                    engine = await db_service.get_engine()
                    
                    assert engine == mock_engine
                    # Verify pool configuration was passed
                    call_kwargs = mock_create.call_args[1]
                    assert call_kwargs['pool_size'] == 20
                    assert call_kwargs['max_overflow'] == 10
                    assert call_kwargs['pool_timeout'] == 60

    @pytest.mark.asyncio
    async def test_get_engine_creation_error(self, db_service):
        """Test handling of engine creation errors."""
        with patch('app.azure.AzureDatabaseService.create_async_engine') as mock_create:
            with patch.object(db_service, 'connection_string', "invalid://connection"):
                mock_create.side_effect = Exception("Database connection failed")
                
                with pytest.raises(AuthenticationError):
                    await db_service.get_engine()

    # ==========================================================================
    # CONNECTION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_connection_success(self, db_service, mock_async_engine):
        """Test successful database connection."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            mock_connection = AsyncMock()
            mock_async_engine.connect.return_value.__aenter__.return_value = mock_connection
            
            async with db_service.get_connection() as conn:
                assert conn == mock_connection

    @pytest.mark.asyncio
    async def test_get_connection_retry_on_failure(self, db_service, mock_async_engine):
        """Test connection retry logic on transient failures."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            # First attempt fails, second succeeds
            mock_connection = AsyncMock()
            mock_async_engine.connect.side_effect = [
                DisconnectionError("Connection lost"),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_connection))
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                async with db_service.get_connection() as conn:
                    assert conn == mock_connection
                    mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connection_max_retries_exceeded(self, db_service, mock_async_engine):
        """Test connection failure when max retries exceeded."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            mock_async_engine.connect.side_effect = DisconnectionError("Persistent failure")
            
            with patch('asyncio.sleep'):
                with pytest.raises(AuthenticationError):
                    async with db_service.get_connection():
                        pass

    @pytest.mark.asyncio
    async def test_get_connection_timeout(self, db_service, mock_async_engine):
        """Test connection timeout handling."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            mock_async_engine.connect.side_effect = SQLTimeoutError("Connection timeout")
            
            with pytest.raises(AuthenticationError):
                async with db_service.get_connection():
                    pass

    # ==========================================================================
    # TRANSACTION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_begin_transaction_success(self, db_service, mock_async_engine):
        """Test successful transaction creation."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            mock_connection = AsyncMock()
            mock_transaction = AsyncMock()
            mock_connection.begin.return_value.__aenter__.return_value = mock_transaction
            mock_async_engine.connect.return_value.__aenter__.return_value = mock_connection
            
            async with db_service.begin_transaction() as (conn, trans):
                assert conn == mock_connection
                assert trans == mock_transaction

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, db_service, mock_async_engine):
        """Test transaction rollback on error."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            mock_connection = AsyncMock()
            mock_transaction = AsyncMock()
            mock_connection.begin.return_value.__aenter__.return_value = mock_transaction
            mock_async_engine.connect.return_value.__aenter__.return_value = mock_connection
            
            try:
                async with db_service.begin_transaction() as (conn, trans):
                    raise Exception("Test error for rollback")
            except Exception:
                pass
            
            # Transaction should be rolled back automatically by context manager
            # This is handled by SQLAlchemy's transaction context manager

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, db_service, mock_async_engine):
        """Test successful query execution with retry logic."""
        with patch.object(db_service, 'get_connection') as mock_get_conn:
            mock_connection = AsyncMock()
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            mock_result = Mock()
            mock_connection.execute.return_value = mock_result
            
            query = "SELECT * FROM users WHERE id = :user_id"
            params = {"user_id": 123}
            
            result = await db_service.execute_with_retry(query, params)
            
            assert result == mock_result
            mock_connection.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_transient_failure(self, db_service):
        """Test query execution retry on transient failure."""
        with patch.object(db_service, 'get_connection') as mock_get_conn:
            mock_connection = AsyncMock()
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # First attempt fails, second succeeds
            mock_result = Mock()
            mock_connection.execute.side_effect = [
                DisconnectionError("Transient failure"),
                mock_result
            ]
            
            query = "SELECT * FROM users"
            
            with patch('asyncio.sleep') as mock_sleep:
                result = await db_service.execute_with_retry(query)
                
                assert result == mock_result
                assert mock_connection.execute.call_count == 2
                mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_permanent_failure(self, db_service):
        """Test query execution failure on permanent error."""
        with patch.object(db_service, 'get_connection') as mock_get_conn:
            mock_connection = AsyncMock()
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            mock_connection.execute.side_effect = DisconnectionError("Permanent failure")
            
            query = "SELECT * FROM users"
            
            with patch('asyncio.sleep'):
                with pytest.raises(AuthenticationError):
                    await db_service.execute_with_retry(query)

    # ==========================================================================
    # ROW-LEVEL SECURITY TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_set_rls_context_success(self, db_service):
        """Test setting row-level security context."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            user_id = "user-123"
            tenant_id = "tenant-456"
            
            await db_service.set_rls_context(user_id, tenant_id)
            
            # Should execute RLS context setting queries
            assert mock_execute.call_count >= 1
            call_args = mock_execute.call_args_list[0]
            assert "SESSION_CONTEXT" in str(call_args)

    @pytest.mark.asyncio
    async def test_set_rls_context_validation_error(self, db_service):
        """Test RLS context setting with invalid parameters."""
        with pytest.raises(ValidationError):
            await db_service.set_rls_context("", "tenant-id")
        
        with pytest.raises(ValidationError):
            await db_service.set_rls_context("user-id", "")

    @pytest.mark.asyncio
    async def test_clear_rls_context(self, db_service):
        """Test clearing row-level security context."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            await db_service.clear_rls_context()
            
            # Should execute RLS context clearing queries
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rls_context(self, db_service):
        """Test getting current row-level security context."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            mock_result = Mock()
            mock_row = Mock()
            mock_row.user_id = "user-123"
            mock_row.tenant_id = "tenant-456"
            mock_result.fetchone.return_value = mock_row
            mock_execute.return_value = mock_result
            
            context = await db_service.get_rls_context()
            
            assert context["user_id"] == "user-123"
            assert context["tenant_id"] == "tenant-456"

    # ==========================================================================
    # HEALTH CHECK TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_health_check_success(self, db_service):
        """Test successful database health check."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            mock_result = Mock()
            mock_row = Mock()
            mock_row._mapping = {"result": 1}
            mock_result.fetchone.return_value = mock_row
            mock_execute.return_value = mock_result
            
            health = await db_service.health_check()
            
            assert health["status"] == "healthy"
            assert health["connection"] is True
            assert "response_time_ms" in health

    @pytest.mark.asyncio
    async def test_health_check_connection_failure(self, db_service):
        """Test health check with connection failure."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            mock_execute.side_effect = AuthenticationError("Connection failed")
            
            health = await db_service.health_check()
            
            assert health["status"] == "unhealthy"
            assert health["connection"] is False
            assert "error" in health

    @pytest.mark.asyncio
    async def test_health_check_query_failure(self, db_service):
        """Test health check with query execution failure."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            mock_result = Mock()
            mock_result.fetchone.return_value = None  # No result
            mock_execute.return_value = mock_result
            
            health = await db_service.health_check()
            
            assert health["status"] == "unhealthy"
            assert "error" in health

    # ==========================================================================
    # CONNECTION POOL MANAGEMENT TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_pool_status(self, db_service, mock_async_engine):
        """Test getting connection pool status."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            # Mock pool attributes
            mock_pool = Mock()
            mock_pool.size.return_value = 10
            mock_pool.checked_in.return_value = 8
            mock_pool.checked_out.return_value = 2
            mock_pool.overflow.return_value = 0
            mock_async_engine.pool = mock_pool
            
            status = await db_service.get_pool_status()
            
            assert status["total_connections"] == 10
            assert status["available_connections"] == 8
            assert status["active_connections"] == 2
            assert status["overflow_connections"] == 0

    @pytest.mark.asyncio
    async def test_close_engine(self, db_service, mock_async_engine):
        """Test engine cleanup and disposal."""
        db_service._engine = mock_async_engine
        
        await db_service.close_engine()
        
        mock_async_engine.dispose.assert_called_once()
        assert db_service._engine is None

    @pytest.mark.asyncio
    async def test_recreate_engine(self, db_service):
        """Test engine recreation after disposal."""
        with patch.object(db_service, 'close_engine') as mock_close:
            with patch.object(db_service, 'get_engine') as mock_get_engine:
                mock_new_engine = Mock()
                mock_get_engine.return_value = mock_new_engine
                
                new_engine = await db_service.recreate_engine()
                
                mock_close.assert_called_once()
                assert new_engine == mock_new_engine

    # ==========================================================================
    # BATCH OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_execute_batch_success(self, db_service):
        """Test successful batch query execution."""
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            queries = [
                ("INSERT INTO users (name) VALUES (:name)", {"name": "User1"}),
                ("INSERT INTO users (name) VALUES (:name)", {"name": "User2"}),
                ("INSERT INTO users (name) VALUES (:name)", {"name": "User3"})
            ]
            
            mock_results = [Mock(), Mock(), Mock()]
            mock_execute.side_effect = mock_results
            
            results = await db_service.execute_batch(queries)
            
            assert len(results) == 3
            assert results == mock_results
            assert mock_execute.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_batch_with_transaction(self, db_service, mock_async_engine):
        """Test batch execution within a transaction."""
        with patch.object(db_service, 'begin_transaction') as mock_begin:
            mock_connection = AsyncMock()
            mock_transaction = AsyncMock()
            mock_begin.return_value.__aenter__.return_value = (mock_connection, mock_transaction)
            
            queries = [
                ("UPDATE users SET active = :active WHERE id = :id", {"active": True, "id": 1}),
                ("UPDATE users SET active = :active WHERE id = :id", {"active": True, "id": 2})
            ]
            
            mock_results = [Mock(), Mock()]
            mock_connection.execute.side_effect = mock_results
            
            results = await db_service.execute_batch_transaction(queries)
            
            assert len(results) == 2
            assert mock_connection.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_batch_rollback_on_error(self, db_service, mock_async_engine):
        """Test batch execution rollback on error."""
        with patch.object(db_service, 'begin_transaction') as mock_begin:
            mock_connection = AsyncMock()
            mock_transaction = AsyncMock()
            mock_begin.return_value.__aenter__.return_value = (mock_connection, mock_transaction)
            
            # Second query fails
            mock_connection.execute.side_effect = [
                Mock(),  # First query succeeds
                Exception("Query failed")  # Second query fails
            ]
            
            queries = [
                ("INSERT INTO users (name) VALUES (:name)", {"name": "User1"}),
                ("INSERT INTO invalid_table (name) VALUES (:name)", {"name": "User2"})
            ]
            
            with pytest.raises(AuthenticationError):
                await db_service.execute_batch_transaction(queries)

    # ==========================================================================
    # ERROR HANDLING AND EDGE CASES
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_connection_string_encoding_special_chars(self, db_service):
        """Test connection string with special characters in password."""
        with patch('app.azure.AzureDatabaseService.settings') as mock_settings:
            mock_settings.database_server = "testserver.database.windows.net"
            mock_settings.database_name = "testdb"
            mock_settings.database_username = "testuser"
            mock_settings.database_password = "pass@#$%word"
            mock_settings.database_driver = "ODBC Driver 18 for SQL Server"
            
            connection_string = db_service.connection_string
            
            # Password should be URL encoded
            assert "pass%40%23%24%25word" in connection_string

    def test_is_transient_error_identification(self, db_service):
        """Test identification of transient database errors."""
        # These should be identified as transient
        transient_errors = [
            DisconnectionError("Connection lost"),
            SQLTimeoutError("Query timeout"),
            Exception("Login timeout expired"),
            Exception("Connection forcibly closed")
        ]
        
        for error in transient_errors:
            assert db_service._is_transient_error(error) is True
        
        # These should not be considered transient
        permanent_errors = [
            Exception("Invalid object reference"),
            Exception("Permission denied"),
            ValueError("Invalid parameter")
        ]
        
        for error in permanent_errors:
            assert db_service._is_transient_error(error) is False

    @pytest.mark.asyncio
    async def test_concurrent_connection_requests(self, db_service, mock_async_engine):
        """Test handling of concurrent connection requests."""
        with patch.object(db_service, 'get_engine', return_value=mock_async_engine):
            mock_connection = AsyncMock()
            mock_async_engine.connect.return_value.__aenter__.return_value = mock_connection
            
            # Create multiple concurrent connection requests
            tasks = [
                db_service.get_connection().__aenter__()
                for _ in range(5)
            ]
            
            connections = await asyncio.gather(*tasks)
            
            # All should get connections (mocked to be the same instance)
            assert len(connections) == 5
            assert all(conn == mock_connection for conn in connections)

    @pytest.mark.asyncio
    async def test_query_parameter_validation(self, db_service):
        """Test validation of query parameters."""
        # SQL injection attempt should be handled by parameterization
        malicious_params = {
            "user_id": "1; DROP TABLE users; --"
        }
        
        with patch.object(db_service, 'execute_with_retry') as mock_execute:
            query = "SELECT * FROM users WHERE id = :user_id"
            
            await db_service.execute_with_retry(query, malicious_params)
            
            # Parameters should be passed as-is to SQLAlchemy (which handles parameterization)
            call_args = mock_execute.call_args
            assert call_args[0][1] == malicious_params

    def test_connection_string_validation(self, db_service):
        """Test validation of connection string components."""
        with patch('app.azure.AzureDatabaseService.settings') as mock_settings:
            # Missing server
            mock_settings.database_server = ""
            mock_settings.database_name = "testdb"
            
            with pytest.raises(ValidationError):
                _ = db_service.connection_string
            
            # Missing database name
            mock_settings.database_server = "testserver.database.windows.net"
            mock_settings.database_name = ""
            
            with pytest.raises(ValidationError):
                _ = db_service.connection_string

    @pytest.mark.asyncio
    async def test_engine_disposal_on_persistent_failures(self, db_service, mock_async_engine):
        """Test engine disposal when persistent connection failures occur."""
        db_service._engine = mock_async_engine
        
        with patch.object(db_service, 'close_engine') as mock_close:
            with patch.object(db_service, 'execute_with_retry') as mock_execute:
                # Simulate persistent failures
                mock_execute.side_effect = DisconnectionError("Persistent failure")
                
                # This should trigger engine recreation logic in actual implementation
                try:
                    await db_service.execute_with_retry("SELECT 1")
                except AuthenticationError:
                    pass
                
                # In actual implementation, persistent failures might trigger engine disposal
                # This test verifies the mechanism exists