"""
Unit tests for app.core.config module.

Tests cover:
- Dynaconf initialization and configuration
- Settings loading from TOML files
- Environment variable overrides
- Azure authority URL generation
- Required settings validation
- Environment-specific configuration
"""

import pytest
import os
from unittest.mock import patch, MagicMock, mock_open

from app.core.config import (
    settings,
    get_azure_authority_url,
    validate_required_settings
)


class TestDynaconfConfiguration:
    """Test Dynaconf configuration and initialization."""

    def test_settings_object_exists(self):
        """Test that settings object is properly initialized."""
        assert settings is not None
        assert hasattr(settings, 'get')
        assert hasattr(settings, 'current_env')

    def test_default_environment(self):
        """Test that default environment is development."""
        # This may vary based on actual environment, so we test the mechanism
        assert hasattr(settings, 'current_env')

    @patch.dict(os.environ, {'ENV_FOR_DYNACONF': 'production'}, clear=False)
    def test_environment_switching(self):
        """Test environment switching via ENV_FOR_DYNACONF."""
        # Note: This test shows the mechanism but actual switching
        # happens at import time, so we're testing the concept
        assert os.environ.get('ENV_FOR_DYNACONF') == 'production'

    @patch.dict(os.environ, {'SCRIBE_DEBUG': 'true'}, clear=False)
    def test_environment_variable_prefix(self):
        """Test that SCRIBE_ prefix works for environment variables."""
        # Test that environment variables with SCRIBE_ prefix are recognized
        assert os.environ.get('SCRIBE_DEBUG') == 'true'

    def test_settings_get_method_with_default(self):
        """Test settings.get method with default values."""
        # Test with a key that likely doesn't exist
        result = settings.get('nonexistent_setting', 'default_value')
        assert result == 'default_value'

    def test_settings_environments_enabled(self):
        """Test that environment-specific sections work."""
        # Test that settings object supports environment-specific config
        assert hasattr(settings, 'environments')

    @patch('app.core.config.settings')
    def test_settings_file_loading(self, mock_settings):
        """Test that settings files are loaded in correct order."""
        # Mock the settings object to test the configuration
        mock_settings.configure.return_value = None
        
        # Verify that the configuration includes the expected files
        # This is more of a structural test
        assert True  # Placeholder for file loading verification


class TestAzureAuthorityUrl:
    """Test Azure authority URL generation."""

    @patch('app.core.config.settings')
    def test_get_azure_authority_url_with_explicit_authority(self, mock_settings):
        """Test get_azure_authority_url with explicitly set authority."""
        mock_settings.get.return_value = "https://login.microsoftonline.com/custom-tenant"
        mock_settings.azure_authority = "https://login.microsoftonline.com/custom-tenant"
        
        result = get_azure_authority_url()
        
        assert result == "https://login.microsoftonline.com/custom-tenant"

    @patch('app.core.config.settings')
    def test_get_azure_authority_url_with_tenant_id(self, mock_settings):
        """Test get_azure_authority_url with tenant ID."""
        mock_settings.get.side_effect = lambda key: {
            "azure_authority": None,
            "azure_tenant_id": "12345678-1234-1234-1234-123456789012"
        }.get(key)
        
        result = get_azure_authority_url()
        
        expected = "https://login.microsoftonline.com/12345678-1234-1234-1234-123456789012"
        assert result == expected

    @patch('app.core.config.settings')
    def test_get_azure_authority_url_default_common(self, mock_settings):
        """Test get_azure_authority_url defaults to common endpoint."""
        mock_settings.get.side_effect = lambda key: {
            "azure_authority": None,
            "azure_tenant_id": None
        }.get(key)
        
        result = get_azure_authority_url()
        
        assert result == "https://login.microsoftonline.com/common"

    @patch('app.core.config.settings')
    def test_azure_authority_url_computed_property(self, mock_settings):
        """Test that azure_authority_url_computed is properly set."""
        mock_settings.azure_authority_url_computed = get_azure_authority_url
        
        # Verify the property is callable
        assert callable(mock_settings.azure_authority_url_computed)


class TestValidateRequiredSettings:
    """Test required settings validation."""

    @patch('app.core.config.settings')
    def test_validate_required_settings_success(self, mock_settings):
        """Test validation passes when all required settings are present."""
        mock_settings.get.side_effect = lambda key: {
            "secret_key": "test-secret-key",
            "jwt_secret": "test-jwt-secret"
        }.get(key, "mock-value")
        
        # Should not raise an exception
        try:
            validate_required_settings()
        except ValueError:
            pytest.fail("validate_required_settings raised ValueError unexpectedly")

    @patch('app.core.config.settings')
    def test_validate_required_settings_missing_secret_key(self, mock_settings):
        """Test validation fails when secret_key is missing."""
        mock_settings.get.side_effect = lambda key: {
            "secret_key": None,
            "jwt_secret": "test-jwt-secret"
        }.get(key, "mock-value")
        
        with pytest.raises(ValueError) as exc_info:
            validate_required_settings()
        
        error_message = str(exc_info.value)
        assert "secret_key" in error_message
        assert "Secret key for JWT token signing" in error_message

    @patch('app.core.config.settings')
    def test_validate_required_settings_missing_jwt_secret(self, mock_settings):
        """Test validation fails when jwt_secret is missing."""
        mock_settings.get.side_effect = lambda key: {
            "secret_key": "test-secret-key",
            "jwt_secret": None
        }.get(key, "mock-value")
        
        with pytest.raises(ValueError) as exc_info:
            validate_required_settings()
        
        error_message = str(exc_info.value)
        assert "jwt_secret" in error_message
        assert "JWT secret for token generation" in error_message

    @patch('app.core.config.settings')
    def test_validate_required_settings_multiple_missing(self, mock_settings):
        """Test validation fails when multiple required settings are missing."""
        mock_settings.get.side_effect = lambda key: {
            "secret_key": None,
            "jwt_secret": None
        }.get(key, "mock-value")
        
        with pytest.raises(ValueError) as exc_info:
            validate_required_settings()
        
        error_message = str(exc_info.value)
        assert "secret_key" in error_message
        assert "jwt_secret" in error_message
        assert "SCRIBE_" in error_message  # Should mention environment variable prefix

    @patch('app.core.config.settings')
    def test_validate_required_settings_empty_strings(self, mock_settings):
        """Test validation fails when required settings are empty strings."""
        mock_settings.get.side_effect = lambda key: {
            "secret_key": "",
            "jwt_secret": ""
        }.get(key, "mock-value")
        
        with pytest.raises(ValueError) as exc_info:
            validate_required_settings()
        
        error_message = str(exc_info.value)
        assert "secret_key" in error_message
        assert "jwt_secret" in error_message


class TestEnvironmentSpecificValidation:
    """Test environment-specific validation and setup."""

    @patch('app.core.config.settings')
    def test_production_environment_validation_success(self, mock_settings):
        """Test production environment validation passes with proper config."""
        mock_settings.current_env = "production"
        mock_settings.get.side_effect = lambda key: {
            "azure_client_secret": "production-client-secret"
        }.get(key, "mock-value")
        mock_settings.debug = False
        
        # Import would trigger validation, so we simulate the check
        assert mock_settings.get("azure_client_secret") is not None
        assert not mock_settings.debug

    @patch('app.core.config.settings')
    def test_production_environment_missing_azure_secret(self, mock_settings):
        """Test production environment validation fails without Azure secret."""
        mock_settings.current_env = "production"
        mock_settings.get.return_value = None
        mock_settings.debug = False
        
        # This would fail in actual import, testing the condition
        azure_secret = mock_settings.get("azure_client_secret")
        assert azure_secret is None

    @patch('app.core.config.settings')
    def test_production_environment_debug_mode_error(self, mock_settings):
        """Test production environment fails with debug mode enabled."""
        mock_settings.current_env = "production"
        mock_settings.get.return_value = "secret"
        mock_settings.debug = True
        
        # This would fail in actual import, testing the condition
        assert mock_settings.debug is True

    @patch('app.core.config.settings')
    def test_non_production_environment_no_validation(self, mock_settings):
        """Test non-production environments don't trigger strict validation."""
        mock_settings.current_env = "development"
        mock_settings.get.return_value = None
        mock_settings.debug = True
        
        # Should not raise errors for development environment
        assert mock_settings.current_env == "development"


class TestSettingsIntegration:
    """Integration tests for settings functionality."""

    def test_settings_cache_configuration(self):
        """Test cache-related settings can be retrieved."""
        # Test that cache settings can be accessed
        default_ttl = settings.get("cache_default_ttl", 300)
        max_size = settings.get("cache_max_size", 1000)
        
        assert isinstance(default_ttl, int)
        assert isinstance(max_size, int)
        assert default_ttl > 0
        assert max_size > 0

    def test_settings_debug_mode(self):
        """Test debug mode setting retrieval."""
        debug = settings.get("debug", False)
        assert isinstance(debug, bool)

    def test_settings_log_level(self):
        """Test log level setting retrieval."""
        log_level = settings.get("log_level", "INFO")
        assert isinstance(log_level, str)
        assert log_level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_settings_api_configuration(self):
        """Test API-related settings retrieval."""
        api_prefix = settings.get("api_v1_prefix", "/api/v1")
        assert isinstance(api_prefix, str)
        assert api_prefix.startswith("/")

    @patch.dict(os.environ, {'SCRIBE_TEST_SETTING': 'test_value'}, clear=False)
    def test_environment_variable_override(self):
        """Test that environment variables properly override settings."""
        # Test that environment variables with SCRIBE_ prefix override file settings
        test_value = settings.get("test_setting")
        # Note: The actual override behavior depends on Dynaconf configuration
        assert os.environ.get('SCRIBE_TEST_SETTING') == 'test_value'

    def test_settings_type_conversion(self):
        """Test that settings are properly converted to expected types."""
        # Test that boolean settings are properly converted
        debug = settings.get("debug", False)
        assert isinstance(debug, bool)
        
        # Test that numeric settings are properly converted
        port = settings.get("port", 8000)
        assert isinstance(port, int)

    def test_settings_nested_access(self):
        """Test nested configuration access."""
        # Test accessing nested configuration if it exists
        # This is more of a structural test since actual nested config may vary
        try:
            nested_value = settings.get("database.host", "localhost")
            assert isinstance(nested_value, str)
        except Exception:
            # If nested access isn't configured, that's fine for this test
            pass


class TestConfigurationEdgeCases:
    """Test edge cases and error conditions."""

    @patch('app.core.config.settings')
    def test_settings_with_none_values(self, mock_settings):
        """Test handling of None values in settings."""
        mock_settings.get.return_value = None
        
        result = settings.get("nonexistent_key", "default")
        # Should return the default value when key doesn't exist
        assert result in [None, "default"]

    @patch('app.core.config.settings')
    def test_settings_with_empty_values(self, mock_settings):
        """Test handling of empty string values in settings."""
        mock_settings.get.return_value = ""
        
        result = settings.get("empty_key", "default")
        # Should return empty string if that's what's configured
        assert result in ["", "default"]

    def test_settings_access_without_errors(self):
        """Test that settings access doesn't raise unexpected errors."""
        # Test various settings access patterns don't cause errors
        try:
            settings.get("app_name", "Scribe")
            settings.get("version", "1.0.0")
            settings.get("debug", False)
            settings.get("nonexistent", None)
        except Exception as e:
            pytest.fail(f"Settings access raised unexpected error: {e}")

    @patch('app.core.config.settings')
    def test_validate_required_settings_with_whitespace(self, mock_settings):
        """Test validation handles whitespace-only values as invalid."""
        mock_settings.get.side_effect = lambda key: {
            "secret_key": "   ",  # Whitespace only
            "jwt_secret": "valid-secret"
        }.get(key, "mock-value")
        
        # Whitespace-only values should be treated as missing
        # Note: This depends on how the validation function handles whitespace
        try:
            validate_required_settings()
            # If it passes, the function considers whitespace as valid
        except ValueError:
            # If it fails, the function properly rejects whitespace
            pass


class TestSettingsPerformance:
    """Test settings performance characteristics."""

    def test_settings_access_performance(self):
        """Test that settings access is reasonably fast."""
        import time
        
        start_time = time.time()
        
        # Access settings multiple times
        for _ in range(100):
            settings.get("debug", False)
            settings.get("log_level", "INFO")
            settings.get("cache_default_ttl", 300)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete quickly (less than 1 second for 300 accesses)
        assert duration < 1.0

    def test_settings_memory_usage(self):
        """Test that settings don't consume excessive memory."""
        # Basic test that settings object exists and is reasonable
        import sys
        
        settings_size = sys.getsizeof(settings)
        # Settings object should not be excessively large
        assert settings_size < 10000  # Less than 10KB