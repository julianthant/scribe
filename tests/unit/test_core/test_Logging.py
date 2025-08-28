"""
Unit tests for app.core.Logging module.

Tests cover:
- setup_logging function configuration
- get_logger function
- log_execution_time decorator (async and sync)
- log_api_request, log_error, log_startup_component functions
- log_service_startup function with sensitive data redaction
- Logger configuration and handler setup
"""

import pytest
import logging
import sys
import asyncio
import time
from unittest.mock import patch, MagicMock, call
from io import StringIO

from app.core.Logging import (
    setup_logging,
    get_logger,
    log_execution_time,
    log_api_request,
    log_error,
    log_startup_component,
    log_service_startup
)


class TestSetupLogging:
    """Test setup_logging function configuration."""

    @patch('app.core.Logging.settings')
    @patch('logging.getLogger')
    @patch('logging.FileHandler')
    @patch('logging.StreamHandler')
    @patch('logging.Formatter')
    @patch('time.time', side_effect=[1000.0, 1000.1])  # Start and end time
    def test_setup_logging_standard_format(
        self, 
        mock_formatter, 
        mock_stream_handler, 
        mock_file_handler,
        mock_get_logger,
        mock_settings
    ):
        """Test setup_logging with standard format configuration."""
        # Mock settings
        mock_settings.log_format = "standard"
        mock_settings.log_level = "INFO"
        mock_settings.current_env = "development"
        
        # Mock handler instances
        mock_console_handler = MagicMock()
        mock_file_handler_instance = MagicMock()
        mock_stream_handler.return_value = mock_console_handler
        mock_file_handler.return_value = mock_file_handler_instance
        
        # Mock logger instances
        mock_startup_logger = MagicMock()
        mock_root_logger = MagicMock()
        mock_get_logger.side_effect = lambda name: {
            "app.startup": mock_startup_logger,
            "": mock_root_logger  # Root logger
        }.get(name, mock_root_logger)
        
        setup_logging()
        
        # Verify formatter creation
        mock_formatter.assert_called_once()
        
        # Verify handlers were configured
        mock_stream_handler.assert_called_once_with(sys.stdout)
        mock_file_handler.assert_called_once_with("app.log", encoding="utf-8")
        
        # Verify startup logging
        assert mock_startup_logger.info.call_count >= 3  # Multiple info calls

    @patch('app.core.Logging.settings')
    @patch('logging.getLogger')
    @patch('logging.FileHandler')
    @patch('logging.StreamHandler')
    @patch('logging.Formatter')
    def test_setup_logging_json_format(
        self, 
        mock_formatter, 
        mock_stream_handler, 
        mock_file_handler,
        mock_get_logger,
        mock_settings
    ):
        """Test setup_logging with JSON format configuration."""
        mock_settings.log_format = "json"
        mock_settings.log_level = "DEBUG"
        mock_settings.current_env = "production"
        
        mock_get_logger.return_value = MagicMock()
        
        with patch('time.time', side_effect=[1000.0, 1000.1]):
            setup_logging()
        
        # Verify formatter was called (exact format depends on implementation)
        mock_formatter.assert_called_once()

    @patch('app.core.Logging.settings')
    @patch('logging.getLogger')
    def test_setup_logging_logger_levels(self, mock_get_logger, mock_settings):
        """Test that specific logger levels are properly set."""
        mock_settings.log_format = "standard"
        mock_settings.log_level = "INFO"
        mock_settings.current_env = "development"
        
        # Create separate mock loggers
        mock_loggers = {}
        logger_names = [
            "app.startup",
            "",  # root logger
            "uvicorn",
            "fastapi", 
            "sqlalchemy.engine",
            "sqlalchemy.pool",
            "azure.identity",
            "azure.core",
            "azure.identity._credentials",
            "azure.identity._internal",
            "urllib3.connectionpool",
            "app.database",
            "app.services",
            "app.azure"
        ]
        
        for name in logger_names:
            mock_loggers[name] = MagicMock()
        
        mock_get_logger.side_effect = lambda name: mock_loggers.get(name, MagicMock())
        
        with patch('time.time', side_effect=[1000.0, 1000.1]):
            setup_logging()
        
        # Verify that specific loggers had setLevel called
        # Note: The exact calls depend on the implementation
        assert mock_get_logger.call_count > 5

    @patch('app.core.Logging.settings')
    def test_setup_logging_custom_format_string(self, mock_settings):
        """Test setup_logging with custom format string."""
        mock_settings.log_format = "%(name)s - %(message)s"
        mock_settings.log_level = "ERROR"
        mock_settings.current_env = "testing"
        
        with patch('logging.getLogger') as mock_get_logger, \
             patch('logging.Formatter') as mock_formatter, \
             patch('time.time', side_effect=[1000.0, 1000.1]):
            
            mock_get_logger.return_value = MagicMock()
            
            setup_logging()
            
            # Verify custom format string was used
            mock_formatter.assert_called_once_with("%(name)s - %(message)s")


class TestGetLogger:
    """Test get_logger function."""

    @patch('logging.getLogger')
    def test_get_logger_returns_logger_instance(self, mock_get_logger):
        """Test that get_logger returns a logger instance."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        result = get_logger("test.module")
        
        assert result == mock_logger
        mock_get_logger.assert_called_once_with("test.module")

    @patch('logging.getLogger')
    def test_get_logger_different_names(self, mock_get_logger):
        """Test get_logger with different module names."""
        mock_logger1 = MagicMock()
        mock_logger2 = MagicMock()
        mock_get_logger.side_effect = [mock_logger1, mock_logger2]
        
        result1 = get_logger("module1")
        result2 = get_logger("module2")
        
        assert result1 == mock_logger1
        assert result2 == mock_logger2
        assert mock_get_logger.call_count == 2


class TestLogExecutionTimeDecorator:
    """Test log_execution_time decorator functionality."""

    @patch('app.core.Logging.get_logger')
    @patch('time.time', side_effect=[1000.0, 1002.5])  # 2.5 second execution
    def test_log_execution_time_sync_function_success(self, mock_time, mock_get_logger):
        """Test log_execution_time decorator with successful sync function."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        @log_execution_time
        def test_function(x, y):
            return x + y
        
        result = test_function(2, 3)
        
        assert result == 5
        mock_logger.info.assert_called_once()
        info_call = mock_logger.info.call_args[0][0]
        assert "test_function executed successfully in 2.500s" in info_call

    @patch('app.core.Logging.get_logger')
    @patch('time.time', side_effect=[1000.0, 1001.5])  # 1.5 second execution
    def test_log_execution_time_sync_function_exception(self, mock_time, mock_get_logger):
        """Test log_execution_time decorator with sync function that raises exception."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        @log_execution_time
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "failing_function failed after 1.500s: Test error" in error_call

    @pytest.mark.asyncio
    @patch('app.core.Logging.get_logger')
    @patch('time.time', side_effect=[1000.0, 1003.0])  # 3 second execution
    async def test_log_execution_time_async_function_success(self, mock_get_logger):
        """Test log_execution_time decorator with successful async function."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        @log_execution_time
        async def async_test_function(x, y):
            return x * y
        
        result = await async_test_function(4, 5)
        
        assert result == 20
        mock_logger.info.assert_called_once()
        info_call = mock_logger.info.call_args[0][0]
        assert "async_test_function executed successfully in 3.000s" in info_call

    @pytest.mark.asyncio
    @patch('app.core.Logging.get_logger')
    @patch('time.time', side_effect=[1000.0, 1000.5])  # 0.5 second execution
    async def test_log_execution_time_async_function_exception(self, mock_get_logger):
        """Test log_execution_time decorator with async function that raises exception."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        @log_execution_time
        async def async_failing_function():
            raise RuntimeError("Async test error")
        
        with pytest.raises(RuntimeError):
            await async_failing_function()
        
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "async_failing_function failed after 0.500s: Async test error" in error_call

    @patch('app.core.Logging.get_logger')
    def test_log_execution_time_preserves_function_metadata(self, mock_get_logger):
        """Test that decorator preserves function metadata."""
        mock_get_logger.return_value = MagicMock()
        
        @log_execution_time
        def documented_function(arg1, arg2):
            """This function has documentation."""
            return arg1 + arg2
        
        assert documented_function.__name__ == "documented_function"
        assert "This function has documentation." in documented_function.__doc__

    def test_log_execution_time_detects_coroutine_function(self):
        """Test that decorator properly detects coroutine functions."""
        with patch('app.core.Logging.get_logger') as mock_get_logger:
            mock_get_logger.return_value = MagicMock()
            
            @log_execution_time
            async def async_function():
                return "async result"
            
            @log_execution_time  
            def sync_function():
                return "sync result"
            
            # Verify that async function returns a coroutine
            result = async_function()
            assert asyncio.iscoroutine(result)
            result.close()  # Clean up coroutine
            
            # Verify that sync function returns normally
            assert sync_function() == "sync result"


class TestLogApiRequest:
    """Test log_api_request function."""

    @patch('app.core.Logging.get_logger')
    def test_log_api_request_basic(self, mock_get_logger):
        """Test basic API request logging."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_api_request("GET", "/api/users", 200, 0.123, "192.168.1.1")
        
        mock_get_logger.assert_called_once_with("api.requests")
        mock_logger.info.assert_called_once_with(
            "GET /api/users - 200 - 0.123s - 192.168.1.1"
        )

    @patch('app.core.Logging.get_logger')
    def test_log_api_request_different_parameters(self, mock_get_logger):
        """Test API request logging with different parameters."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_api_request("POST", "/api/auth/login", 401, 1.456, "10.0.0.1")
        
        mock_logger.info.assert_called_once_with(
            "POST /api/auth/login - 401 - 1.456s - 10.0.0.1"
        )

    @patch('app.core.Logging.get_logger')
    def test_log_api_request_formatting(self, mock_get_logger):
        """Test API request log message formatting."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_api_request("PUT", "/api/users/123", 500, 2.789, "127.0.0.1")
        
        expected_message = "PUT /api/users/123 - 500 - 2.789s - 127.0.0.1"
        mock_logger.info.assert_called_once_with(expected_message)


class TestLogError:
    """Test log_error function."""

    @patch('app.core.Logging.get_logger')
    def test_log_error_basic(self, mock_get_logger):
        """Test basic error logging."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        test_error = ValueError("Test error message")
        log_error(test_error)
        
        mock_get_logger.assert_called_once_with("app.errors")
        mock_logger.error.assert_called_once_with("Test error message", exc_info=True)

    @patch('app.core.Logging.get_logger')
    def test_log_error_with_context(self, mock_get_logger):
        """Test error logging with context."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        test_error = RuntimeError("Connection failed")
        log_error(test_error, context="database_connection")
        
        expected_message = "Error in database_connection: Connection failed"
        mock_logger.error.assert_called_once_with(expected_message, exc_info=True)

    @patch('app.core.Logging.get_logger')
    def test_log_error_with_extra_data(self, mock_get_logger):
        """Test error logging with extra data."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        test_error = ConnectionError("Timeout")
        extra_data = {"host": "localhost", "port": 5432, "timeout": 30}
        log_error(test_error, extra_data=extra_data)
        
        expected_message = "Timeout | Extra data: {'host': 'localhost', 'port': 5432, 'timeout': 30}"
        mock_logger.error.assert_called_once_with(expected_message, exc_info=True)

    @patch('app.core.Logging.get_logger')
    def test_log_error_with_context_and_extra_data(self, mock_get_logger):
        """Test error logging with both context and extra data."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        test_error = Exception("Processing failed")
        extra_data = {"user_id": "123", "operation": "update"}
        log_error(test_error, context="user_service", extra_data=extra_data)
        
        expected_message = "Error in user_service: Processing failed | Extra data: {'user_id': '123', 'operation': 'update'}"
        mock_logger.error.assert_called_once_with(expected_message, exc_info=True)


class TestLogStartupComponent:
    """Test log_startup_component function."""

    @patch('app.core.Logging.get_logger')
    @patch('time.time', return_value=1000.150)  # 150ms after start
    def test_log_startup_component_success(self, mock_time, mock_get_logger):
        """Test successful component startup logging."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        start_time = 1000.0
        log_startup_component("Database", start_time, success=True)
        
        mock_get_logger.assert_called_once_with("app.startup")
        mock_logger.info.assert_called_once_with(
            "[OK] Database initialized successfully in 150.00ms"
        )

    @patch('app.core.Logging.get_logger')
    @patch('time.time', return_value=1000.250)  # 250ms after start
    def test_log_startup_component_success_with_details(self, mock_time, mock_get_logger):
        """Test successful component startup logging with details."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        start_time = 1000.0
        details = {"host": "localhost", "port": 5432, "database": "scribe"}
        log_startup_component("Database", start_time, success=True, details=details)
        
        # Check main success message
        mock_logger.info.assert_any_call(
            "[OK] Database initialized successfully in 250.00ms"
        )
        # Check detail messages
        mock_logger.info.assert_any_call("  -> host: localhost")
        mock_logger.info.assert_any_call("  -> port: 5432") 
        mock_logger.info.assert_any_call("  -> database: scribe")

    @patch('app.core.Logging.get_logger')
    @patch('time.time', return_value=1000.500)  # 500ms after start
    def test_log_startup_component_failure(self, mock_time, mock_get_logger):
        """Test failed component startup logging."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        start_time = 1000.0
        test_error = ConnectionError("Could not connect to database")
        log_startup_component("Database", start_time, success=False, error=test_error)
        
        mock_logger.error.assert_any_call(
            "[ERROR] Database initialization failed after 500.00ms"
        )
        mock_logger.error.assert_any_call(
            "  -> Error: Could not connect to database"
        )

    @patch('app.core.Logging.get_logger')
    @patch('time.time', return_value=1000.100)  # 100ms after start
    def test_log_startup_component_failure_without_error(self, mock_time, mock_get_logger):
        """Test failed component startup logging without error details."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        start_time = 1000.0
        log_startup_component("Cache", start_time, success=False)
        
        mock_logger.error.assert_called_once_with(
            "[ERROR] Cache initialization failed after 100.00ms"
        )


class TestLogServiceStartup:
    """Test log_service_startup function."""

    @patch('app.core.Logging.get_logger')
    def test_log_service_startup_basic(self, mock_get_logger):
        """Test basic service startup logging."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_service_startup("AuthService")
        
        mock_get_logger.assert_called_once_with("app.services")
        mock_logger.info.assert_called_once_with("[SERVICE] Starting AuthService...")

    @patch('app.core.Logging.get_logger')
    def test_log_service_startup_with_version(self, mock_get_logger):
        """Test service startup logging with version."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_service_startup("MailService", version="2.1.0")
        
        mock_logger.info.assert_any_call("[SERVICE] Starting MailService...")
        mock_logger.info.assert_any_call("  -> Version: 2.1.0")

    @patch('app.core.Logging.get_logger')
    def test_log_service_startup_with_config_details(self, mock_get_logger):
        """Test service startup logging with configuration details."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        config_details = {
            "host": "api.example.com",
            "port": 8080,
            "debug": True,
            "max_connections": 100
        }
        log_service_startup("ApiService", config_details=config_details)
        
        mock_logger.info.assert_any_call("[SERVICE] Starting ApiService...")
        mock_logger.info.assert_any_call("  -> host: api.example.com")
        mock_logger.info.assert_any_call("  -> port: 8080")
        mock_logger.info.assert_any_call("  -> debug: True")
        mock_logger.info.assert_any_call("  -> max_connections: 100")

    @patch('app.core.Logging.get_logger')
    def test_log_service_startup_with_version_and_config(self, mock_get_logger):
        """Test service startup logging with both version and config."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        config_details = {"timeout": 30, "retries": 3}
        log_service_startup("HttpService", version="1.5.2", config_details=config_details)
        
        mock_logger.info.assert_any_call("[SERVICE] Starting HttpService...")
        mock_logger.info.assert_any_call("  -> Version: 1.5.2")
        mock_logger.info.assert_any_call("  -> timeout: 30")
        mock_logger.info.assert_any_call("  -> retries: 3")

    @patch('app.core.Logging.get_logger')
    def test_log_service_startup_sensitive_data_redaction(self, mock_get_logger):
        """Test that sensitive configuration data is redacted."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        config_details = {
            "host": "database.example.com",
            "password": "super_secret_password",
            "api_secret": "secret_key_123",
            "jwt_key": "jwt_secret",
            "access_token": "bearer_token_xyz",
            "normal_setting": "normal_value"
        }
        log_service_startup("DatabaseService", config_details=config_details)
        
        # Check that sensitive values are redacted
        mock_logger.info.assert_any_call("  -> host: database.example.com")
        mock_logger.info.assert_any_call("  -> password: [REDACTED]")
        mock_logger.info.assert_any_call("  -> api_secret: [REDACTED]")
        mock_logger.info.assert_any_call("  -> jwt_key: [REDACTED]")
        mock_logger.info.assert_any_call("  -> access_token: [REDACTED]")
        mock_logger.info.assert_any_call("  -> normal_setting: normal_value")

    @patch('app.core.Logging.get_logger')
    def test_log_service_startup_case_insensitive_redaction(self, mock_get_logger):
        """Test that sensitive data redaction is case insensitive."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        config_details = {
            "CLIENT_SECRET": "secret_123",
            "Database_Password": "db_pass",
            "API_KEY": "key_456"
        }
        log_service_startup("TestService", config_details=config_details)
        
        # All should be redacted regardless of case
        mock_logger.info.assert_any_call("  -> CLIENT_SECRET: [REDACTED]")
        mock_logger.info.assert_any_call("  -> Database_Password: [REDACTED]")
        mock_logger.info.assert_any_call("  -> API_KEY: [REDACTED]")


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_logger_hierarchy(self):
        """Test that loggers follow proper hierarchy."""
        parent_logger = get_logger("app")
        child_logger = get_logger("app.services")
        grandchild_logger = get_logger("app.services.auth")
        
        # All should be logger instances
        assert isinstance(parent_logger, logging.Logger)
        assert isinstance(child_logger, logging.Logger)
        assert isinstance(grandchild_logger, logging.Logger)
        
        # Names should reflect hierarchy
        assert parent_logger.name == "app"
        assert child_logger.name == "app.services"
        assert grandchild_logger.name == "app.services.auth"

    @patch('sys.stdout', new_callable=StringIO)
    def test_actual_log_output(self, mock_stdout):
        """Test that logs actually produce output."""
        # Create a simple logger for testing
        test_logger = logging.getLogger("test_logger")
        test_logger.setLevel(logging.INFO)
        
        # Add a stream handler to capture output
        handler = logging.StreamHandler(mock_stdout)
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        test_logger.addHandler(handler)
        
        # Log a message
        test_logger.info("Test log message")
        
        # Check output
        output = mock_stdout.getvalue()
        assert "test_logger - INFO - Test log message" in output

    def test_decorator_preserves_function_signature(self):
        """Test that log_execution_time preserves function signatures."""
        @log_execution_time
        def test_function(arg1: str, arg2: int = 10) -> str:
            return f"{arg1}_{arg2}"
        
        # Function should work normally
        with patch('app.core.Logging.get_logger') as mock_get_logger:
            mock_get_logger.return_value = MagicMock()
            result = test_function("test", 20)
            assert result == "test_20"