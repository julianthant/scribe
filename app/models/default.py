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