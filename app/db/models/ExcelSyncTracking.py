"""
ExcelSyncTracking.py - Excel Sync Tracking Models

Database models for tracking Excel synchronization operations.
This module handles:
- Excel file metadata tracking
- Sync operation history
- Error logging and retry tracking
- Performance metrics

Following 3NF normalization:
- excel_files: Excel file metadata and OneDrive info
- excel_sync_operations: Individual sync operations
- excel_sync_errors: Error tracking for failed operations

No JSON arrays - proper normalized relationships.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, Float, ForeignKey, UniqueConstraint, CheckConstraint, Text
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin

# Forward reference imports for relationships
if False:  # TYPE_CHECKING
    from .User import User
    from .Transcription import VoiceTranscription


class ExcelFile(Base, UUIDMixin, TimestampMixin):
    """Excel file metadata and OneDrive information."""
    __tablename__ = "excel_files"

    # Owner
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # File identification
    file_name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)  # "Transcripts"
    onedrive_file_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    onedrive_drive_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    
    # File metadata
    web_url: Mapped[Optional[str]] = mapped_column(NVARCHAR(1000), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status tracking
    file_status: Mapped[str] = mapped_column(NVARCHAR(20), default="active", nullable=False)  # active, deleted, error
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Sync statistics
    total_sync_operations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_syncs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_syncs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    sync_operations: Mapped[List["ExcelSyncOperation"]] = relationship("ExcelSyncOperation", back_populates="excel_file", cascade="all, delete-orphan")
    sync_errors: Mapped[List["ExcelSyncError"]] = relationship("ExcelSyncError", back_populates="excel_file", cascade="all, delete-orphan")

    # Constraints and indexes
    __table_args__ = (
        # Ensure unique file name per user
        UniqueConstraint("user_id", "file_name", name="uq_excel_files_user_name"),
        # File status constraint
        CheckConstraint(
            "file_status IN ('active', 'deleted', 'error')",
            name="ck_excel_files_status"
        ),
        # Size constraints
        CheckConstraint("size_bytes >= 0", name="ck_excel_files_size_positive"),
        CheckConstraint("total_sync_operations >= 0", name="ck_excel_files_total_syncs_positive"),
        CheckConstraint("successful_syncs >= 0", name="ck_excel_files_successful_syncs_positive"),
        CheckConstraint("failed_syncs >= 0", name="ck_excel_files_failed_syncs_positive"),
        CheckConstraint("successful_syncs + failed_syncs <= total_sync_operations", name="ck_excel_files_sync_totals"),
        # Indexes
        Index("ix_excel_files_user_id", "user_id"),
        Index("ix_excel_files_file_name", "file_name"),
        Index("ix_excel_files_onedrive_file_id", "onedrive_file_id"),
        Index("ix_excel_files_file_status", "file_status"),
        Index("ix_excel_files_last_sync_at", "last_sync_at"),
        # Composite indexes for common queries
        Index("ix_excel_files_user_status", "user_id", "file_status"),
        Index("ix_excel_files_user_last_sync", "user_id", "last_sync_at"),
    )

    def __repr__(self) -> str:
        return f"<ExcelFile(id='{self.id}', name='{self.file_name}', status='{self.file_status}')>"


class ExcelSyncOperation(Base, UUIDMixin, TimestampMixin):
    """Individual Excel sync operation tracking."""
    __tablename__ = "excel_sync_operations"

    # Foreign keys
    excel_file_id: Mapped[str] = mapped_column(ForeignKey("excel_files.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    transcription_id: Mapped[Optional[str]] = mapped_column(ForeignKey("voice_transcriptions.id"), nullable=True)  # Null for batch operations
    
    # Operation details
    operation_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)  # single, batch, full_sync
    worksheet_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    operation_status: Mapped[str] = mapped_column(NVARCHAR(20), default="pending", nullable=False)  # pending, in_progress, completed, failed
    
    # Processing metrics
    rows_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Error handling
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Configuration
    force_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    apply_formatting: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    excel_file: Mapped["ExcelFile"] = relationship("ExcelFile", back_populates="sync_operations")
    user: Mapped["User"] = relationship("User")
    transcription: Mapped[Optional["VoiceTranscription"]] = relationship("VoiceTranscription")
    errors: Mapped[List["ExcelSyncError"]] = relationship("ExcelSyncError", back_populates="sync_operation", cascade="all, delete-orphan")

    # Constraints and indexes
    __table_args__ = (
        # Operation type constraint
        CheckConstraint(
            "operation_type IN ('single', 'batch', 'full_sync')",
            name="ck_excel_sync_operations_type"
        ),
        # Status constraint
        CheckConstraint(
            "operation_status IN ('pending', 'in_progress', 'completed', 'failed', 'retrying')",
            name="ck_excel_sync_operations_status"
        ),
        # Positive constraints
        CheckConstraint("rows_processed >= 0", name="ck_excel_sync_operations_rows_processed_positive"),
        CheckConstraint("rows_created >= 0", name="ck_excel_sync_operations_rows_created_positive"),
        CheckConstraint("rows_updated >= 0", name="ck_excel_sync_operations_rows_updated_positive"),
        CheckConstraint("processing_time_ms >= 0", name="ck_excel_sync_operations_processing_time_positive"),
        CheckConstraint("retry_count >= 0", name="ck_excel_sync_operations_retry_count_positive"),
        CheckConstraint("max_retries >= 0", name="ck_excel_sync_operations_max_retries_positive"),
        CheckConstraint("retry_count <= max_retries", name="ck_excel_sync_operations_retry_within_max"),
        CheckConstraint("rows_created + rows_updated <= rows_processed", name="ck_excel_sync_operations_row_totals"),
        # Indexes
        Index("ix_excel_sync_operations_excel_file_id", "excel_file_id"),
        Index("ix_excel_sync_operations_user_id", "user_id"),
        Index("ix_excel_sync_operations_transcription_id", "transcription_id"),
        Index("ix_excel_sync_operations_operation_type", "operation_type"),
        Index("ix_excel_sync_operations_operation_status", "operation_status"),
        Index("ix_excel_sync_operations_worksheet_name", "worksheet_name"),
        Index("ix_excel_sync_operations_started_at", "started_at"),
        Index("ix_excel_sync_operations_completed_at", "completed_at"),
        # Composite indexes for common queries
        Index("ix_excel_sync_operations_file_status", "excel_file_id", "operation_status"),
        Index("ix_excel_sync_operations_user_status", "user_id", "operation_status"),
        Index("ix_excel_sync_operations_user_worksheet", "user_id", "worksheet_name"),
        Index("ix_excel_sync_operations_status_started", "operation_status", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<ExcelSyncOperation(id='{self.id}', type='{self.operation_type}', status='{self.operation_status}')>"


class ExcelSyncError(Base, UUIDMixin, TimestampMixin):
    """Error tracking for Excel sync operations."""
    __tablename__ = "excel_sync_errors"

    # Foreign keys
    excel_file_id: Mapped[str] = mapped_column(ForeignKey("excel_files.id"), nullable=False)
    sync_operation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("excel_sync_operations.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Error details
    error_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # network, authentication, api_limit, file_locked, etc.
    error_code: Mapped[Optional[str]] = mapped_column(NVARCHAR(20), nullable=True)  # HTTP status or API error code
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Context information
    operation_type: Mapped[Optional[str]] = mapped_column(NVARCHAR(20), nullable=True)
    worksheet_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    transcription_id: Mapped[Optional[str]] = mapped_column(ForeignKey("voice_transcriptions.id"), nullable=True)
    
    # Request details
    http_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    api_request_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    retry_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Resolution
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    
    # Stack trace for debugging
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    excel_file: Mapped["ExcelFile"] = relationship("ExcelFile", back_populates="sync_errors")
    sync_operation: Mapped[Optional["ExcelSyncOperation"]] = relationship("ExcelSyncOperation", back_populates="errors")
    user: Mapped["User"] = relationship("User")
    transcription: Mapped[Optional["VoiceTranscription"]] = relationship("VoiceTranscription")

    # Constraints and indexes
    __table_args__ = (
        # Constraints
        CheckConstraint("retry_attempt >= 0", name="ck_excel_sync_errors_retry_positive"),
        CheckConstraint("http_status_code >= 100 AND http_status_code <= 599", name="ck_excel_sync_errors_http_status"),
        # Indexes
        Index("ix_excel_sync_errors_excel_file_id", "excel_file_id"),
        Index("ix_excel_sync_errors_sync_operation_id", "sync_operation_id"),
        Index("ix_excel_sync_errors_user_id", "user_id"),
        Index("ix_excel_sync_errors_transcription_id", "transcription_id"),
        Index("ix_excel_sync_errors_error_type", "error_type"),
        Index("ix_excel_sync_errors_error_code", "error_code"),
        Index("ix_excel_sync_errors_is_resolved", "is_resolved"),
        Index("ix_excel_sync_errors_http_status_code", "http_status_code"),
        # Composite indexes for common queries
        Index("ix_excel_sync_errors_user_resolved", "user_id", "is_resolved"),
        Index("ix_excel_sync_errors_type_created", "error_type", "created_at"),
        Index("ix_excel_sync_errors_resolved_created", "is_resolved", "created_at"),
        Index("ix_excel_sync_errors_file_type", "excel_file_id", "error_type"),
    )

    def __repr__(self) -> str:
        return f"<ExcelSyncError(id='{self.id}', type='{self.error_type}', resolved={self.is_resolved})>"