"""
ExcelSync.py - Pydantic Models for Excel Transcription Sync

Provides data models for Excel synchronization operations including:
- Excel file metadata
- Worksheet information
- Transcription row data
- Sync status tracking
- Formatting specifications

These models ensure type safety and validation for Excel sync operations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, validator


class ExcelSyncStatus(str, Enum):
    """Excel sync status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class ExcelColumnFormat(BaseModel):
    """Excel column formatting specification."""
    name: str = Field(..., description="Column name")
    width: Optional[int] = Field(None, description="Column width in characters")
    wrap_text: bool = Field(False, description="Whether to wrap text in column")
    bold: bool = Field(False, description="Whether column should be bold")
    alignment: Optional[str] = Field("left", description="Text alignment (left, center, right)")


class ExcelWorksheetInfo(BaseModel):
    """Excel worksheet information."""
    name: str = Field(..., description="Worksheet name")
    id: Optional[str] = Field(None, description="Worksheet ID from Graph API")
    created_at: Optional[datetime] = Field(None, description="When worksheet was created")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")
    row_count: int = Field(0, description="Number of data rows (excluding header)")
    has_header: bool = Field(False, description="Whether worksheet has header row")


class ExcelFileInfo(BaseModel):
    """Excel file information."""
    name: str = Field(..., description="File name without extension")
    file_id: Optional[str] = Field(None, description="OneDrive file ID")
    drive_id: Optional[str] = Field(None, description="OneDrive drive ID")
    web_url: Optional[str] = Field(None, description="Web URL to file")
    created_at: Optional[datetime] = Field(None, description="File creation timestamp")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    worksheets: List[ExcelWorksheetInfo] = Field(default_factory=list, description="List of worksheets")


class TranscriptionRowData(BaseModel):
    """Data for a single transcription row in Excel."""
    transcription_id: str = Field(..., description="Transcription ID")
    date_time: datetime = Field(..., description="Transcription creation timestamp")
    sender_name: Optional[str] = Field(None, description="Voice message sender name")
    sender_email: str = Field(..., description="Voice message sender email")
    subject: str = Field(..., description="Email subject containing voice message")
    audio_duration: Optional[float] = Field(None, description="Audio duration in seconds")
    transcript_text: str = Field(..., description="Transcribed text content")
    confidence_score: Optional[float] = Field(None, description="Transcription confidence (0-1)")
    language: Optional[str] = Field(None, description="Detected language code")
    model_used: str = Field(..., description="AI model used for transcription")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")

    @validator('confidence_score')
    def validate_confidence_score(cls, v):
        """Validate confidence score is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Confidence score must be between 0 and 1')
        return v

    @validator('audio_duration')
    def validate_audio_duration(cls, v):
        """Validate audio duration is positive."""
        if v is not None and v < 0:
            raise ValueError('Audio duration must be positive')
        return v

    @validator('processing_time_ms')
    def validate_processing_time(cls, v):
        """Validate processing time is positive."""
        if v is not None and v < 0:
            raise ValueError('Processing time must be positive')
        return v


class ExcelSyncRequest(BaseModel):
    """Request model for Excel sync operations."""
    transcription_ids: List[str] = Field(..., description="List of transcription IDs to sync")
    worksheet_name: Optional[str] = Field(None, description="Target worksheet name")
    force_update: bool = Field(False, description="Whether to update existing rows")
    create_worksheet: bool = Field(True, description="Whether to create worksheet if not exists")
    apply_formatting: bool = Field(True, description="Whether to apply formatting")


class ExcelSyncResult(BaseModel):
    """Result model for Excel sync operations."""
    status: ExcelSyncStatus = Field(..., description="Sync operation status")
    file_info: Optional[ExcelFileInfo] = Field(None, description="Excel file information")
    worksheet_name: str = Field(..., description="Target worksheet name")
    rows_processed: int = Field(0, description="Number of rows processed")
    rows_updated: int = Field(0, description="Number of rows updated")
    rows_created: int = Field(0, description="Number of rows created")
    errors: List[str] = Field(default_factory=list, description="List of error messages")
    processing_time_ms: Optional[int] = Field(None, description="Total processing time")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Sync start time")
    completed_at: Optional[datetime] = Field(None, description="Sync completion time")


class ExcelBatchSyncRequest(BaseModel):
    """Request model for batch Excel sync operations."""
    month_year: str = Field(..., description="Month/year for worksheet (e.g., 'December 2024')")
    user_id: str = Field(..., description="User ID for transcription filtering")
    force_full_sync: bool = Field(False, description="Whether to sync all transcriptions for the month")
    max_batch_size: int = Field(100, description="Maximum number of transcriptions to process")


class ExcelBatchSyncResult(BaseModel):
    """Result model for batch Excel sync operations."""
    month_year: str = Field(..., description="Month/year processed")
    total_transcriptions: int = Field(0, description="Total transcriptions found for month")
    synced_transcriptions: int = Field(0, description="Number of transcriptions synced")
    skipped_transcriptions: int = Field(0, description="Number of transcriptions skipped")
    sync_results: List[ExcelSyncResult] = Field(default_factory=list, description="Individual sync results")
    overall_status: ExcelSyncStatus = Field(..., description="Overall batch sync status")
    errors: List[str] = Field(default_factory=list, description="Batch-level errors")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Batch sync start time")
    completed_at: Optional[datetime] = Field(None, description="Batch sync completion time")


class ExcelFormatting(BaseModel):
    """Excel formatting configuration."""
    columns: List[ExcelColumnFormat] = Field(..., description="Column formatting specifications")
    header_style: Dict[str, Any] = Field(
        default_factory=lambda: {
            "bold": True,
            "background_color": "#4472C4",
            "font_color": "#FFFFFF",
            "freeze_panes": True
        },
        description="Header row styling"
    )
    data_style: Dict[str, Any] = Field(
        default_factory=lambda: {
            "wrap_text": False,
            "auto_fit": True,
            "borders": True
        },
        description="Data row styling"
    )
    conditional_formatting: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conditional formatting rules"
    )


class ExcelHealthCheck(BaseModel):
    """Excel service health check result."""
    service_status: str = Field(..., description="Service availability status")
    onedrive_accessible: bool = Field(..., description="Whether OneDrive is accessible")
    file_permissions: bool = Field(..., description="Whether file permissions are valid")
    last_sync_time: Optional[datetime] = Field(None, description="Last successful sync time")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")
    checked_at: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")