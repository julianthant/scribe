"""
Mail Account Models - Personal and Shared Mailbox Management

Following 3NF normalization:
- mail_accounts: Individual user mail accounts
- shared_mailboxes: Company shared mailboxes (separate entity)
"""

from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Boolean, Index, ForeignKey
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin, create_email_column, create_azure_id_column

# Forward reference imports for relationships
if TYPE_CHECKING:
    from .User import User
    from .MailData import MailFolder


class MailAccount(Base, UUIDMixin, TimestampMixin):
    """Individual user mail accounts."""
    __tablename__ = "mail_accounts"

    # Foreign key to users table
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Mail account details
    email: Mapped[str] = create_email_column(nullable=False)
    azure_mail_id: Mapped[Optional[str]] = create_azure_id_column(nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="mail_accounts")
    folders: Mapped[List["MailFolder"]] = relationship("MailFolder", back_populates="mail_account", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_mail_accounts_user_id", "user_id"),
        Index("ix_mail_accounts_email", "email"),
        Index("ix_mail_accounts_azure_mail_id", "azure_mail_id"),
        Index("ix_mail_accounts_is_primary", "is_primary"),
        Index("ix_mail_accounts_active", "is_active"),
        Index("ix_mail_accounts_user_primary", "user_id", "is_primary"),  # Composite for user's primary account
    )

    def __repr__(self) -> str:
        return f"<MailAccount(id='{self.id}', email='{self.email}', is_primary={self.is_primary})>"


class SharedMailbox(Base, UUIDMixin, TimestampMixin):
    """Company shared mailboxes - separate entity from personal accounts."""
    __tablename__ = "shared_mailboxes"

    # Shared mailbox details
    email: Mapped[str] = create_email_column(nullable=False, unique=True)
    azure_mail_id: Mapped[Optional[str]] = create_azure_id_column(nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(NVARCHAR(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    folders: Mapped[List["MailFolder"]] = relationship("MailFolder", back_populates="shared_mailbox", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("ix_shared_mailboxes_email", "email"),
        Index("ix_shared_mailboxes_azure_mail_id", "azure_mail_id"),
        Index("ix_shared_mailboxes_active", "is_active"),
        Index("ix_shared_mailboxes_display_name", "display_name"),
    )

    def __repr__(self) -> str:
        return f"<SharedMailbox(id='{self.id}', email='{self.email}', display_name='{self.display_name}')>"