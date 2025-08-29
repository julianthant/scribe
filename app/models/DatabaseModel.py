"""
DatabaseModel.py - Core Database Base Classes

Provides the fundamental SQLAlchemy base classes and mixins for the Scribe application.
This module is completely self-contained with no dependencies on other app modules
to prevent circular imports.

Classes:
- Base: Core declarative base with async support
- TimestampMixin: Automatic created_at/updated_at timestamps
- UUIDMixin: UUID primary key with SQL Server NEWID()
- SoftDeleteMixin: Soft delete functionality
- Enums: Core enums for controlled vocabularies
- Column factories: Standardized column creators

This module only imports from SQLAlchemy and standard library to maintain
a clean dependency tree and avoid circular imports.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, overload, Union, Literal

from sqlalchemy import Boolean, DateTime, Index, MetaData, func, text
from sqlalchemy.dialects.mssql import NVARCHAR, UNIQUEIDENTIFIER
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models with async support and naming conventions."""
    
    # Naming convention for constraints - Alembic best practices
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s", 
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    })
    
    # Common mapper configuration
    __mapper_args__ = {"eager_defaults": True}


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.getutcdate(),
        nullable=False,
        comment="Record creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.getutcdate(),
        onupdate=func.getutcdate(),
        nullable=False,
        comment="Record last update timestamp"
    )


class UUIDMixin:
    """Mixin for UUID primary keys."""
    
    id: Mapped[str] = mapped_column(
        UNIQUEIDENTIFIER,
        primary_key=True,
        server_default=text("NEWID()"),
        comment="Unique identifier"
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
        nullable=False,
        comment="Soft delete flag"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Soft delete timestamp"
    )


class UserRole(PyEnum):
    """User role enumeration - simple two-tier system."""
    USER = "user"
    SUPERUSER = "superuser"


class PermissionType(PyEnum):
    """Permission types for mailbox access."""
    READ = "read"
    SEND = "send"
    DELETE = "delete"
    MANAGE = "manage"


class SyncStatus(PyEnum):
    """Synchronization status enumeration."""
    PENDING = "pending"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"


class EntityType(PyEnum):
    """Entity types for audit and sync tracking."""
    MAIL_ACCOUNT = "mail_account"
    SHARED_MAILBOX = "shared_mailbox"


# Essential column factories for normalized design
def create_email_column(nullable: bool = False, unique: bool = False) -> Mapped[str]:
    """Create a standardized email column."""
    return mapped_column(
        NVARCHAR(320),  # RFC 5321 maximum length
        nullable=nullable,
        unique=unique,
        comment="Email address"
    )


@overload
def create_azure_id_column(nullable: Literal[True] = True, unique: bool = False) -> Mapped[Optional[str]]: ...

@overload  
def create_azure_id_column(nullable: Literal[False], unique: bool = False) -> Mapped[str]: ...

def create_azure_id_column(nullable: bool = True, unique: bool = False) -> Union[Mapped[str], Mapped[Optional[str]]]:
    """Create a column for Azure AD object IDs."""
    return mapped_column(
        NVARCHAR(36),  # Azure AD GUIDs are 36 characters
        nullable=nullable,
        unique=unique,
        comment="Azure AD object identifier"
    )


# Index creation helper
def create_composite_index(table_name: str, *column_names: str) -> Index:
    """Create a composite index with proper naming."""
    column_suffix = "_".join(column_names)
    return Index(
        f"ix_{table_name}_{column_suffix}",
        *column_names
    )