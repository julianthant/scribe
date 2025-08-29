"""
Voice Attachment Storage Models - Voice attachment blob storage metadata

Following 3NF normalization:
- voice_attachments: Core voice attachment blob storage metadata
- voice_attachment_downloads: Track download history for analytics

No JSON arrays - proper normalized relationships.
"""

from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin, create_email_column, create_azure_id_column

# Forward reference imports for relationships
if TYPE_CHECKING:
    from .User import User
    from .Transcription import VoiceTranscription


class VoiceAttachment(Base, UUIDMixin, TimestampMixin):
    """Voice attachment blob storage metadata - normalized."""
    __tablename__ = "voice_attachments"

    # Foreign keys
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Graph API identifiers
    azure_message_id: Mapped[str] = create_azure_id_column(nullable=False)
    azure_attachment_id: Mapped[str] = create_azure_id_column(nullable=False)
    
    # Blob storage identifiers
    blob_name: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False, unique=True)
    blob_container: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    blob_url: Mapped[Optional[str]] = mapped_column(NVARCHAR(1000), nullable=True)
    
    # File metadata
    original_filename: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    content_type: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Audio metadata (nullable - may not be available)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bit_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Email context metadata
    sender_email: Mapped[str] = create_email_column(nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)
    subject: Mapped[str] = mapped_column(NVARCHAR(1000), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Storage metadata
    storage_status: Mapped[str] = mapped_column(NVARCHAR(20), default="stored", nullable=False)  # stored, failed, deleted
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Quality indicators
    is_transcribed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transcription_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="voice_attachments")
    downloads: Mapped[List["VoiceAttachmentDownload"]] = relationship("VoiceAttachmentDownload", back_populates="attachment", cascade="all, delete-orphan")
    transcription: Mapped[Optional["VoiceTranscription"]] = relationship("VoiceTranscription", back_populates="voice_attachment", cascade="all, delete-orphan", uselist=False)

    # Constraints and indexes
    __table_args__ = (
        # Ensure unique combination of Graph API identifiers per user
        UniqueConstraint("user_id", "azure_message_id", "azure_attachment_id", name="uq_voice_attachments_graph_api"),
        # Storage status constraint
        CheckConstraint(
            "storage_status IN ('stored', 'failed', 'deleted', 'pending')",
            name="ck_voice_attachments_status"
        ),
        # Size constraints
        CheckConstraint("size_bytes > 0", name="ck_voice_attachments_size_positive"),
        CheckConstraint("duration_seconds >= 0", name="ck_voice_attachments_duration_positive"),
        CheckConstraint("download_count >= 0", name="ck_voice_attachments_download_count_positive"),
        # Indexes
        Index("ix_voice_attachments_user_id", "user_id"),
        Index("ix_voice_attachments_azure_message_id", "azure_message_id"),
        Index("ix_voice_attachments_azure_attachment_id", "azure_attachment_id"),
        Index("ix_voice_attachments_blob_name", "blob_name"),
        Index("ix_voice_attachments_content_type", "content_type"),
        Index("ix_voice_attachments_sender_email", "sender_email"),
        Index("ix_voice_attachments_received_at", "received_at"),
        Index("ix_voice_attachments_storage_status", "storage_status"),
        Index("ix_voice_attachments_expires_at", "expires_at"),
        Index("ix_voice_attachments_download_count", "download_count"),
        Index("ix_voice_attachments_transcribed", "is_transcribed"),
        # Composite indexes for common queries
        Index("ix_voice_attachments_user_received", "user_id", "received_at"),
        Index("ix_voice_attachments_user_status", "user_id", "storage_status"),
        Index("ix_voice_attachments_expires_status", "expires_at", "storage_status"),
    )

    def __repr__(self) -> str:
        return f"<VoiceAttachment(id='{self.id}', filename='{self.original_filename}', blob='{self.blob_name}')>"


class VoiceAttachmentDownload(Base, UUIDMixin, TimestampMixin):
    """Track voice attachment download history for analytics."""
    __tablename__ = "voice_attachment_downloads"

    # Foreign keys
    attachment_id: Mapped[str] = mapped_column(ForeignKey("voice_attachments.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Download metadata
    download_method: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)  # api, sas_url, direct
    client_ip: Mapped[Optional[str]] = mapped_column(NVARCHAR(45), nullable=True)  # IPv4 or IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    download_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Performance metrics
    download_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    
    # Relationships
    attachment: Mapped["VoiceAttachment"] = relationship("VoiceAttachment", back_populates="downloads")
    user: Mapped["User"] = relationship("User", back_populates="voice_attachment_downloads")

    # Constraints and indexes
    __table_args__ = (
        # Download method constraint
        CheckConstraint(
            "download_method IN ('api', 'sas_url', 'direct', 'blob_stream')",
            name="ck_voice_attachment_downloads_method"
        ),
        # Size constraints
        CheckConstraint("download_size_bytes > 0", name="ck_voice_attachment_downloads_size_positive"),
        CheckConstraint("download_duration_ms >= 0", name="ck_voice_attachment_downloads_duration_positive"),
        # Indexes
        Index("ix_voice_attachment_downloads_attachment_id", "attachment_id"),
        Index("ix_voice_attachment_downloads_user_id", "user_id"),
        Index("ix_voice_attachment_downloads_method", "download_method"),
        Index("ix_voice_attachment_downloads_success", "success"),
        Index("ix_voice_attachment_downloads_created_at", "created_at"),
        # Composite indexes for analytics
        Index("ix_voice_attachment_downloads_attachment_created", "attachment_id", "created_at"),
        Index("ix_voice_attachment_downloads_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<VoiceAttachmentDownload(id='{self.id}', attachment_id='{self.attachment_id}', method='{self.download_method}')>"