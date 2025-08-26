"""
default.py - Default Response Models

Defines common Pydantic models for standard API responses and system endpoints.
This module provides:
- ErrorResponse: Standardized error response structure with error codes and details
- WelcomeResponse: Root endpoint welcome message with API information
- HealthResponse: Health check endpoint response with system status

These models ensure consistent response formats across all API endpoints and
provide standardized error handling and system information responses.
"""

from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WelcomeResponse(BaseModel):
    """Welcome endpoint response."""
    message: str
    version: str
    docs_url: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str