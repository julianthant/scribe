"""
Input validation decorators and utilities for API endpoints
Production-ready validation with comprehensive error handling
"""

import json
import logging
from functools import wraps
from typing import Dict, Any, Optional, Callable, List, Union
from datetime import datetime
import azure.functions as func

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error with details"""
    def __init__(self, message: str, field: str = None, details: Dict = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


def validation_error_response(error: Union[ValidationError, str], status_code: int = 400) -> func.HttpResponse:
    """Create standardized validation error response"""
    if isinstance(error, ValidationError):
        response_data = {
            "status": "validation_error",
            "timestamp": datetime.utcnow().isoformat(),
            "message": error.message,
            "field": error.field,
            "details": error.details
        }
    else:
        response_data = {
            "status": "validation_error", 
            "timestamp": datetime.utcnow().isoformat(),
            "message": str(error)
        }
    
    return func.HttpResponse(
        json.dumps(response_data, indent=2),
        status_code=status_code,
        headers={"Content-Type": "application/json"}
    )


class RequestValidator:
    """Request validation utilities"""
    
    @staticmethod
    def validate_json_body(req: func.HttpRequest, required_fields: List[str] = None) -> Dict[str, Any]:
        """
        Validate and parse JSON request body
        
        Args:
            req: Azure Functions HTTP request
            required_fields: List of required field names
            
        Returns:
            Dict: Parsed JSON data
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Check if request has body
            if not req.get_body():
                raise ValidationError("Request body is required", field="body")
            
            # Parse JSON
            try:
                data = req.get_json()
            except ValueError as e:
                raise ValidationError(f"Invalid JSON format: {str(e)}", field="body")
            
            if data is None:
                raise ValidationError("Request body must be valid JSON", field="body")
            
            # Validate required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    raise ValidationError(
                        f"Missing required fields: {', '.join(missing_fields)}",
                        field="required_fields",
                        details={"missing_fields": missing_fields}
                    )
            
            return data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            raise ValidationError(f"Request validation failed: {str(e)}")
    
    @staticmethod
    def validate_query_params(req: func.HttpRequest, allowed_params: Dict[str, Dict] = None) -> Dict[str, Any]:
        """
        Validate query parameters
        
        Args:
            req: Azure Functions HTTP request
            allowed_params: Dict of param_name -> validation rules
                          e.g., {"max_emails": {"type": int, "min": 1, "max": 100}}
                          
        Returns:
            Dict: Validated query parameters
            
        Raises:
            ValidationError: If validation fails
        """
        params = {}
        
        if not allowed_params:
            return params
        
        for param_name, rules in allowed_params.items():
            param_value = req.params.get(param_name)
            
            if param_value is None:
                if rules.get("required", False):
                    raise ValidationError(f"Required parameter '{param_name}' is missing", field=param_name)
                continue
            
            # Type conversion and validation
            try:
                if rules.get("type") == int:
                    param_value = int(param_value)
                    if "min" in rules and param_value < rules["min"]:
                        raise ValidationError(
                            f"Parameter '{param_name}' must be >= {rules['min']}", 
                            field=param_name
                        )
                    if "max" in rules and param_value > rules["max"]:
                        raise ValidationError(
                            f"Parameter '{param_name}' must be <= {rules['max']}", 
                            field=param_name
                        )
                
                elif rules.get("type") == str:
                    if "max_length" in rules and len(param_value) > rules["max_length"]:
                        raise ValidationError(
                            f"Parameter '{param_name}' must be <= {rules['max_length']} characters", 
                            field=param_name
                        )
                    if "allowed_values" in rules and param_value not in rules["allowed_values"]:
                        raise ValidationError(
                            f"Parameter '{param_name}' must be one of: {', '.join(rules['allowed_values'])}", 
                            field=param_name
                        )
                
                params[param_name] = param_value
                
            except ValueError:
                raise ValidationError(
                    f"Parameter '{param_name}' must be of type {rules.get('type', str).__name__}", 
                    field=param_name
                )
        
        return params
    
    @staticmethod
    def validate_content_type(req: func.HttpRequest, expected_type: str = "application/json"):
        """
        Validate request content type
        
        Args:
            req: Azure Functions HTTP request
            expected_type: Expected content type
            
        Raises:
            ValidationError: If content type is invalid
        """
        content_type = req.headers.get("content-type", "").lower()
        
        if expected_type.lower() not in content_type:
            raise ValidationError(
                f"Invalid content type. Expected '{expected_type}', got '{content_type}'",
                field="content-type"
            )


def validate_request(
    required_fields: List[str] = None,
    query_params: Dict[str, Dict] = None,
    content_type: str = "application/json",
    methods: List[str] = None
):
    """
    Decorator for comprehensive request validation
    
    Args:
        required_fields: List of required JSON body fields
        query_params: Dict of allowed query parameters with validation rules
        content_type: Expected content type
        methods: Allowed HTTP methods
        
    Usage:
        @validate_request(
            required_fields=["email", "message"],
            query_params={"max_results": {"type": int, "min": 1, "max": 100}},
            methods=["POST"]
        )
        def my_handler(req: func.HttpRequest) -> func.HttpResponse:
            # req.validated_data contains parsed JSON body
            # req.validated_params contains validated query parameters
            pass
    """
    def decorator(func_handler: Callable) -> Callable:
        @wraps(func_handler)
        def wrapper(req: func.HttpRequest) -> func.HttpResponse:
            try:
                # Validate HTTP method
                if methods and req.method.upper() not in [m.upper() for m in methods]:
                    raise ValidationError(
                        f"Method {req.method} not allowed. Allowed methods: {', '.join(methods)}",
                        field="method"
                    )
                
                # Validate content type for POST/PUT/PATCH requests
                if req.method.upper() in ["POST", "PUT", "PATCH"] and content_type:
                    RequestValidator.validate_content_type(req, content_type)
                
                # Validate JSON body if required
                validated_data = {}
                if req.method.upper() in ["POST", "PUT", "PATCH"] and (required_fields or content_type == "application/json"):
                    validated_data = RequestValidator.validate_json_body(req, required_fields)
                
                # Validate query parameters
                validated_params = RequestValidator.validate_query_params(req, query_params)
                
                # Add validated data to request object for handler use
                req.validated_data = validated_data
                req.validated_params = validated_params
                
                # Call the original handler
                return func_handler(req)
                
            except ValidationError as e:
                logger.warning(f"Validation error in {func_handler.__name__}: {e.message}")
                return validation_error_response(e)
            except Exception as e:
                logger.error(f"Unexpected error in validation decorator: {e}")
                return validation_error_response(f"Request validation failed: {str(e)}", 500)
        
        return wrapper
    return decorator


def validate_auth_required(func_handler: Callable) -> Callable:
    """
    Decorator to ensure authentication is initialized before processing request
    """
    @wraps(func_handler)
    def wrapper(req: func.HttpRequest) -> func.HttpResponse:
        try:
            from helpers.auth_manager import is_authenticated
            
            if not is_authenticated():
                return validation_error_response(
                    ValidationError(
                        "Authentication required. Please ensure authentication is properly configured.",
                        field="authentication"
                    ),
                    401
                )
            
            return func_handler(req)
            
        except Exception as e:
            logger.error(f"Authentication validation error: {e}")
            return validation_error_response(
                ValidationError(f"Authentication validation failed: {str(e)}", field="authentication"),
                401
            )
    
    return wrapper


# Common validation rules for reuse
COMMON_VALIDATION_RULES = {
    "max_emails": {"type": int, "min": 1, "max": 100, "required": False},
    "days_back": {"type": int, "min": 1, "max": 30, "required": False},
    "test_mode": {"type": str, "allowed_values": ["true", "false"], "required": False},
    "format": {"type": str, "allowed_values": ["json", "xml"], "required": False}
}


def get_processing_params_validation():
    """Get validation rules for email processing parameters"""
    return {
        "max_emails": COMMON_VALIDATION_RULES["max_emails"],
        "days_back": COMMON_VALIDATION_RULES["days_back"], 
        "test_mode": COMMON_VALIDATION_RULES["test_mode"]
    }


def get_file_listing_params_validation():
    """Get validation rules for file listing parameters"""
    return {
        "format": COMMON_VALIDATION_RULES["format"]
    }