"""
User Models - Authentication and User Management

Following 3NF normalization:
- users: Core authentication data (no redundancy)
- user_profiles: Extended user information (separate from auth)
- sessions: Active user sessions (one-to-many with users)
"""

from datetime import datetime
from typing import List, Optional
from enum import Enum

from sqlalchemy import Boolean, DateTime, Index, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin, create_email_column, create_azure_id_column

# Forward reference imports for relationships
if False:  # TYPE_CHECKING
    from .MailAccount import MailAccount
    from .Operational import AuditLog


class UserRole(Enum):
    """User role enumeration for role-based access control."""
    USER = "user"
    SUPERUSER = "superuser"


class User(Base, UUIDMixin, TimestampMixin):
    """Core user authentication table - minimal, normalized data only."""
    __tablename__ = "users"

    # Core authentication fields
    azure_id: Mapped[Optional[str]] = create_azure_id_column(nullable=False, unique=True)
    email: Mapped[str] = create_email_column(nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum"),
        default=UserRole.USER,
        nullable=False
    )
    
    # Relationships
    profile: Mapped[Optional["UserProfile"]] = relationship("UserProfile", back_populates="user", uselist=False)
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    mail_accounts: Mapped[List["MailAccount"]] = relationship("MailAccount", back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")

    # Indexes
    __table_args__ = (
        Index("ix_users_azure_id", "azure_id"),
        Index("ix_users_email", "email"),
        Index("ix_users_active", "is_active"),
        Index("ix_users_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<User(id='{self.id}', email='{self.email}', is_active={self.is_active})>"


class UserProfile(Base, UUIDMixin, TimestampMixin):
    """Extended user information - separate from core auth data."""
    __tablename__ = "user_profiles"

    # Foreign key to users table
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    
    # Profile information
    first_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(50), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(NVARCHAR(100), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")

    # Indexes
    __table_args__ = (
        Index("ix_user_profiles_user_id", "user_id"),
        Index("ix_user_profiles_display_name", "display_name"),
    )

    def __repr__(self) -> str:
        return f"<UserProfile(id='{self.id}', display_name='{self.display_name}')>"


class Session(Base, UUIDMixin, TimestampMixin):
    """Active user sessions - one-to-many with users."""
    __tablename__ = "sessions"

    # Foreign key to users table
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Session data
    access_token: Mapped[str] = mapped_column(NVARCHAR(4000), nullable=False)  # JWT tokens can be long
    refresh_token: Mapped[Optional[str]] = mapped_column(NVARCHAR(4000), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Optional session metadata
    ip_address: Mapped[Optional[str]] = mapped_column(NVARCHAR(45), nullable=True)  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    # Indexes
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
        Index("ix_sessions_is_revoked", "is_revoked"),
        Index("ix_sessions_active", "user_id", "expires_at", "is_revoked"),  # Composite for active sessions
    )

    def __repr__(self) -> str:
        return f"<Session(id='{self.id}', user_id='{self.user_id}', expires_at={self.expires_at})>"