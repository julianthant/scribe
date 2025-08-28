"""
test_BaseModel.py - Unit tests for base Pydantic models

Tests all base models in app.models.BaseModel including:
- ErrorResponse: Standard error response model
- WelcomeResponse: Welcome endpoint response model
- HealthResponse: Health check response model

Tests include validation, serialization, field constraints, default values, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from pydantic import ValidationError

from app.models.BaseModel import (
    ErrorResponse,
    WelcomeResponse,
    HealthResponse
)


class TestErrorResponse:
    """Test cases for ErrorResponse model."""

    def test_error_response_valid_data_creates_instance(self):
        """Test that valid data creates ErrorResponse instance."""
        # Arrange
        error_data = {
            "error": "ValidationError",
            "message": "Invalid input data provided",
            "error_code": "E001",
            "details": {"field": "email", "issue": "Invalid format"}
        }

        # Act
        error_response = ErrorResponse(**error_data)

        # Assert
        assert error_response.error == "ValidationError"
        assert error_response.message == "Invalid input data provided"
        assert error_response.error_code == "E001"
        assert error_response.details == {"field": "email", "issue": "Invalid format"}
        assert isinstance(error_response.timestamp, datetime)

    def test_error_response_minimal_required_data(self):
        """Test ErrorResponse with only required fields."""
        # Arrange
        minimal_data = {
            "error": "NotFound",
            "message": "Resource not found"
        }

        # Act
        error_response = ErrorResponse(**minimal_data)

        # Assert
        assert error_response.error == "NotFound"
        assert error_response.message == "Resource not found"
        assert error_response.error_code is None  # Default
        assert error_response.details is None     # Default
        assert isinstance(error_response.timestamp, datetime)

    def test_error_response_timestamp_auto_generated(self):
        """Test that timestamp is automatically generated."""
        # Arrange
        before_creation = datetime.utcnow()
        
        # Act
        error_response = ErrorResponse(
            error="TestError",
            message="Test message"
        )
        
        after_creation = datetime.utcnow()

        # Assert
        assert before_creation <= error_response.timestamp <= after_creation

    def test_error_response_timestamp_can_be_overridden(self):
        """Test that timestamp can be explicitly set."""
        # Arrange
        custom_timestamp = datetime(2023, 1, 15, 12, 0, 0)
        error_data = {
            "error": "CustomError",
            "message": "Custom message",
            "timestamp": custom_timestamp
        }

        # Act
        error_response = ErrorResponse(**error_data)

        # Assert
        assert error_response.timestamp == custom_timestamp

    def test_error_response_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing error
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse(message="Test message")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("error",) for error in errors)

        # Test missing message
        with pytest.raises(ValidationError) as exc_info:
            ErrorResponse(error="TestError")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("message",) for error in errors)

    def test_error_response_with_complex_details(self):
        """Test ErrorResponse with complex details object."""
        # Arrange
        complex_details = {
            "validation_errors": [
                {"field": "email", "message": "Invalid format"},
                {"field": "age", "message": "Must be positive"}
            ],
            "request_id": "req-123",
            "user_context": {"user_id": "user-456", "role": "user"}
        }
        error_data = {
            "error": "MultipleValidationErrors",
            "message": "Multiple validation errors occurred",
            "details": complex_details
        }

        # Act
        error_response = ErrorResponse(**error_data)

        # Assert
        assert error_response.details == complex_details
        assert len(error_response.details["validation_errors"]) == 2
        assert error_response.details["request_id"] == "req-123"

    def test_error_response_empty_strings_validation(self):
        """Test ErrorResponse with empty string values."""
        # Arrange
        error_data = {
            "error": "",
            "message": ""
        }

        # Act - Should create instance with empty strings
        error_response = ErrorResponse(**error_data)

        # Assert
        assert error_response.error == ""
        assert error_response.message == ""

    def test_error_response_serialization(self):
        """Test ErrorResponse serialization to dict."""
        # Arrange
        error_data = {
            "error": "SerializationTest",
            "message": "Test serialization",
            "error_code": "S001"
        }
        error_response = ErrorResponse(**error_data)

        # Act
        serialized = error_response.model_dump()

        # Assert
        assert serialized["error"] == "SerializationTest"
        assert serialized["message"] == "Test serialization"
        assert serialized["error_code"] == "S001"
        assert "timestamp" in serialized

    def test_error_response_json_serialization(self):
        """Test ErrorResponse JSON serialization."""
        # Arrange
        error_response = ErrorResponse(
            error="JSONTest",
            message="JSON test message"
        )

        # Act
        json_str = error_response.model_dump_json()

        # Assert
        assert '"error":"JSONTest"' in json_str
        assert '"message":"JSON test message"' in json_str
        assert '"timestamp"' in json_str


class TestWelcomeResponse:
    """Test cases for WelcomeResponse model."""

    def test_welcome_response_valid_data_creates_instance(self):
        """Test that valid data creates WelcomeResponse instance."""
        # Arrange
        welcome_data = {
            "message": "Welcome to Scribe API",
            "version": "1.0.0",
            "docs_url": "https://api.example.com/docs"
        }

        # Act
        welcome_response = WelcomeResponse(**welcome_data)

        # Assert
        assert welcome_response.message == "Welcome to Scribe API"
        assert welcome_response.version == "1.0.0"
        assert welcome_response.docs_url == "https://api.example.com/docs"

    def test_welcome_response_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing message
        with pytest.raises(ValidationError) as exc_info:
            WelcomeResponse(version="1.0.0", docs_url="https://example.com/docs")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("message",) for error in errors)

        # Test missing version
        with pytest.raises(ValidationError) as exc_info:
            WelcomeResponse(message="Welcome", docs_url="https://example.com/docs")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("version",) for error in errors)

        # Test missing docs_url
        with pytest.raises(ValidationError) as exc_info:
            WelcomeResponse(message="Welcome", version="1.0.0")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("docs_url",) for error in errors)

    def test_welcome_response_empty_strings_validation(self):
        """Test WelcomeResponse with empty string values."""
        # Arrange
        welcome_data = {
            "message": "",
            "version": "",
            "docs_url": ""
        }

        # Act - Should create instance with empty strings
        welcome_response = WelcomeResponse(**welcome_data)

        # Assert
        assert welcome_response.message == ""
        assert welcome_response.version == ""
        assert welcome_response.docs_url == ""

    def test_welcome_response_with_development_data(self):
        """Test WelcomeResponse with development environment data."""
        # Arrange
        dev_data = {
            "message": "Welcome to Scribe API - Development Environment",
            "version": "1.0.0-dev",
            "docs_url": "http://localhost:8000/docs"
        }

        # Act
        welcome_response = WelcomeResponse(**dev_data)

        # Assert
        assert "Development Environment" in welcome_response.message
        assert "dev" in welcome_response.version
        assert "localhost" in welcome_response.docs_url

    def test_welcome_response_serialization(self):
        """Test WelcomeResponse serialization to dict."""
        # Arrange
        welcome_data = {
            "message": "API Welcome",
            "version": "2.0.0",
            "docs_url": "https://api.scribe.com/docs"
        }
        welcome_response = WelcomeResponse(**welcome_data)

        # Act
        serialized = welcome_response.model_dump()

        # Assert
        assert serialized["message"] == "API Welcome"
        assert serialized["version"] == "2.0.0"
        assert serialized["docs_url"] == "https://api.scribe.com/docs"

    def test_welcome_response_json_serialization(self):
        """Test WelcomeResponse JSON serialization."""
        # Arrange
        welcome_response = WelcomeResponse(
            message="JSON Welcome Test",
            version="1.5.0",
            docs_url="/docs"
        )

        # Act
        json_str = welcome_response.model_dump_json()

        # Assert
        assert '"message":"JSON Welcome Test"' in json_str
        assert '"version":"1.5.0"' in json_str
        assert '"docs_url":"/docs"' in json_str


class TestHealthResponse:
    """Test cases for HealthResponse model."""

    def test_health_response_valid_data_creates_instance(self):
        """Test that valid data creates HealthResponse instance."""
        # Arrange
        health_data = {
            "status": "healthy",
            "version": "1.0.0"
        }

        # Act
        health_response = HealthResponse(**health_data)

        # Assert
        assert health_response.status == "healthy"
        assert health_response.version == "1.0.0"

    def test_health_response_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing status
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(version="1.0.0")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

        # Test missing version
        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(status="healthy")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("version",) for error in errors)

    @pytest.mark.parametrize("status", [
        "healthy",
        "unhealthy",
        "degraded",
        "maintenance",
        "starting",
        "stopping"
    ])
    def test_health_response_various_status_values(self, status):
        """Test HealthResponse with various status values."""
        # Arrange & Act
        health_response = HealthResponse(status=status, version="1.0.0")

        # Assert
        assert health_response.status == status

    def test_health_response_with_version_patterns(self):
        """Test HealthResponse with various version patterns."""
        # Test semantic versioning
        versions = [
            "1.0.0",
            "2.1.3-alpha",
            "3.0.0-beta.1",
            "1.0.0-rc.1+build.123",
            "dev-snapshot",
            "latest"
        ]

        for version in versions:
            # Act
            health_response = HealthResponse(status="healthy", version=version)

            # Assert
            assert health_response.version == version

    def test_health_response_unhealthy_status(self):
        """Test HealthResponse with unhealthy status."""
        # Arrange
        health_data = {
            "status": "unhealthy",
            "version": "1.0.0"
        }

        # Act
        health_response = HealthResponse(**health_data)

        # Assert
        assert health_response.status == "unhealthy"
        assert health_response.version == "1.0.0"

    def test_health_response_empty_strings_validation(self):
        """Test HealthResponse with empty string values."""
        # Arrange
        health_data = {
            "status": "",
            "version": ""
        }

        # Act - Should create instance with empty strings
        health_response = HealthResponse(**health_data)

        # Assert
        assert health_response.status == ""
        assert health_response.version == ""

    def test_health_response_serialization(self):
        """Test HealthResponse serialization to dict."""
        # Arrange
        health_data = {
            "status": "degraded",
            "version": "1.2.3"
        }
        health_response = HealthResponse(**health_data)

        # Act
        serialized = health_response.model_dump()

        # Assert
        assert serialized["status"] == "degraded"
        assert serialized["version"] == "1.2.3"

    def test_health_response_json_serialization(self):
        """Test HealthResponse JSON serialization."""
        # Arrange
        health_response = HealthResponse(
            status="maintenance",
            version="2.0.0-maintenance"
        )

        # Act
        json_str = health_response.model_dump_json()

        # Assert
        assert '"status":"maintenance"' in json_str
        assert '"version":"2.0.0-maintenance"' in json_str


class TestModelIntegration:
    """Integration tests for base model interactions."""

    def test_error_response_with_health_check_failure(self):
        """Test ErrorResponse for health check failure scenario."""
        # Arrange
        health_error = ErrorResponse(
            error="HealthCheckFailed",
            message="Service health check failed",
            error_code="HEALTH_001",
            details={
                "service": "database",
                "status": "unhealthy",
                "last_success": "2023-01-15T10:30:00Z"
            }
        )

        # Act & Assert
        assert health_error.error == "HealthCheckFailed"
        assert health_error.details["service"] == "database"
        assert health_error.details["status"] == "unhealthy"

    def test_all_models_json_serializable(self):
        """Test that all base models can be serialized to JSON."""
        # Arrange
        error_response = ErrorResponse(error="Test", message="Test message")
        welcome_response = WelcomeResponse(
            message="Welcome", version="1.0.0", docs_url="/docs"
        )
        health_response = HealthResponse(status="healthy", version="1.0.0")

        # Act & Assert - Should not raise exceptions
        error_json = error_response.model_dump_json()
        welcome_json = welcome_response.model_dump_json()
        health_json = health_response.model_dump_json()

        assert isinstance(error_json, str)
        assert isinstance(welcome_json, str)
        assert isinstance(health_json, str)

    def test_models_can_be_created_from_dict(self):
        """Test that models can be created from dictionary data."""
        # Arrange
        error_dict = {"error": "DictTest", "message": "Dictionary creation test"}
        welcome_dict = {"message": "Dict Welcome", "version": "1.0", "docs_url": "/docs"}
        health_dict = {"status": "healthy", "version": "1.0"}

        # Act
        error_response = ErrorResponse(**error_dict)
        welcome_response = WelcomeResponse(**welcome_dict)
        health_response = HealthResponse(**health_dict)

        # Assert
        assert error_response.error == "DictTest"
        assert welcome_response.message == "Dict Welcome"
        assert health_response.status == "healthy"


class TestModelValidationEdgeCases:
    """Test edge cases and validation scenarios."""

    def test_error_response_with_none_details(self):
        """Test ErrorResponse with explicit None details."""
        # Arrange
        error_data = {
            "error": "NoneTest",
            "message": "Test with None details",
            "details": None
        }

        # Act
        error_response = ErrorResponse(**error_data)

        # Assert
        assert error_response.details is None

    def test_error_response_with_nested_dict_details(self):
        """Test ErrorResponse with deeply nested details."""
        # Arrange
        nested_details = {
            "level1": {
                "level2": {
                    "level3": {
                        "deep_value": "found",
                        "array": [1, 2, 3],
                        "bool_val": True
                    }
                }
            }
        }
        error_data = {
            "error": "NestedTest",
            "message": "Test with nested details",
            "details": nested_details
        }

        # Act
        error_response = ErrorResponse(**error_data)

        # Assert
        assert error_response.details["level1"]["level2"]["level3"]["deep_value"] == "found"
        assert error_response.details["level1"]["level2"]["level3"]["array"] == [1, 2, 3]
        assert error_response.details["level1"]["level2"]["level3"]["bool_val"] is True

    def test_timestamp_field_behavior(self):
        """Test timestamp field default factory behavior."""
        # Arrange & Act
        error1 = ErrorResponse(error="Time1", message="First error")
        error2 = ErrorResponse(error="Time2", message="Second error")

        # Assert - Timestamps should be different (created at different times)
        assert error1.timestamp != error2.timestamp
        assert isinstance(error1.timestamp, datetime)
        assert isinstance(error2.timestamp, datetime)

    @pytest.mark.parametrize("field_value", [
        "normal_string",
        "",
        " ",
        "string with spaces",
        "string-with-dashes",
        "string_with_underscores",
        "string.with.dots",
        "STRING_WITH_CAPS",
        "123456",
        "mixed123ABC"
    ])
    def test_string_fields_handle_various_formats(self, field_value):
        """Test that string fields handle various formats."""
        # Test with ErrorResponse
        error_response = ErrorResponse(error=field_value, message=field_value)
        assert error_response.error == field_value
        assert error_response.message == field_value

        # Test with WelcomeResponse
        welcome_response = WelcomeResponse(
            message=field_value, version=field_value, docs_url=field_value
        )
        assert welcome_response.message == field_value
        assert welcome_response.version == field_value
        assert welcome_response.docs_url == field_value

        # Test with HealthResponse
        health_response = HealthResponse(status=field_value, version=field_value)
        assert health_response.status == field_value
        assert health_response.version == field_value