"""
Operational Models - Sync Status and Audit Logging

Following 3NF normalization:
- sync_status: Track synchronization status for entities
- audit_logs: Central audit trail (no audit fields in every table)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Index, ForeignKey, Text
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin, EntityType, SyncStatus as SyncStatusEnum

# Forward reference imports for relationships
if False:  # TYPE_CHECKING
    from .User import User


class SyncStatus(Base, UUIDMixin, TimestampMixin):
    """Track synchronization status for various entities."""
    __tablename__ = "sync_status"

    # Entity information
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type_enum"),
        nullable=False
    )
    entity_id: Mapped[str] = mapped_column(NVARCHAR(36), nullable=False)  # UUID of the entity
    
    # Sync information
    status: Mapped[SyncStatusEnum] = mapped_column(
        Enum(SyncStatusEnum, name="sync_status_enum"),
        nullable=False,
        default=SyncStatusEnum.PENDING
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Error information
    error_message: Mapped[Optional[str]] = mapped_column(NVARCHAR(1000), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Sync metadata
    sync_version: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    external_reference: Mapped[Optional[str]] = mapped_column(NVARCHAR(255), nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_sync_status_entity_type", "entity_type"),
        Index("ix_sync_status_entity_id", "entity_id"),
        Index("ix_sync_status_status", "status"),
        Index("ix_sync_status_last_sync", "last_sync_at"),
        Index("ix_sync_status_next_sync", "next_sync_at"),
        # Composite index for entity lookup
        Index("ix_sync_status_entity", "entity_type", "entity_id"),
        # Composite index for sync queue processing
        Index("ix_sync_status_queue", "status", "next_sync_at"),
    )

    def __repr__(self) -> str:
        return f"<SyncStatus(id='{self.id}', entity_type='{self.entity_type}', status='{self.status}')>"


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Central audit trail - replaces audit fields in individual tables."""
    __tablename__ = "audit_logs"

    # User information
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)  # Nullable for system actions
    
    # Action information
    action: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # CREATE, UPDATE, DELETE, etc.
    entity_type: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)  # Table/entity name
    entity_id: Mapped[str] = mapped_column(NVARCHAR(36), nullable=False)  # ID of affected entity
    
    # Change details
    old_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON of old values
    new_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON of new values
    
    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(NVARCHAR(45), nullable=True)  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(36), nullable=True)
    
    # Additional context
    description: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(NVARCHAR(36), nullable=True)  # For tracing related actions
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_entity_type", "entity_type"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_session_id", "session_id"),
        Index("ix_audit_logs_correlation_id", "correlation_id"),
        # Composite indexes for common queries
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_timeline", "created_at", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id='{self.id}', action='{self.action}', entity_type='{self.entity_type}', created_at={self.created_at})>"