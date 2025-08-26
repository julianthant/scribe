"""
Mail Data Models - Mail Folders Only

Following 3NF normalization:
- mail_folders: Folder structure for both personal and shared mailboxes

Simplified model - mail messages, attachments, categories, and recipients 
are handled externally via Microsoft Graph API calls, not stored in database.
"""

from typing import List, Optional

from sqlalchemy import Boolean, Index, ForeignKey, CheckConstraint
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.DatabaseModel import Base, TimestampMixin, UUIDMixin, create_azure_id_column

# Forward reference imports for relationships
if False:  # TYPE_CHECKING
    from .MailAccount import MailAccount, SharedMailbox


class MailFolder(Base, UUIDMixin, TimestampMixin):
    """Mail folder structure for both personal and shared mailboxes."""
    __tablename__ = "mail_folders"

    # Foreign keys (nullable to support both personal and shared mailboxes)
    mail_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("mail_accounts.id"), nullable=True)
    shared_mailbox_id: Mapped[Optional[str]] = mapped_column(ForeignKey("shared_mailboxes.id"), nullable=True)
    parent_folder_id: Mapped[Optional[str]] = mapped_column(ForeignKey("mail_folders.id"), nullable=True)
    
    # Folder details
    name: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    azure_folder_id: Mapped[Optional[str]] = create_azure_id_column(nullable=True)
    is_system_folder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    folder_path: Mapped[str] = mapped_column(NVARCHAR(1000), nullable=False)  # Full path for efficient queries
    
    # Relationships
    mail_account: Mapped[Optional["MailAccount"]] = relationship("MailAccount", back_populates="folders")
    shared_mailbox: Mapped[Optional["SharedMailbox"]] = relationship("SharedMailbox", back_populates="folders")
    parent_folder: Mapped[Optional["MailFolder"]] = relationship("MailFolder", remote_side="MailFolder.id")
    child_folders: Mapped[List["MailFolder"]] = relationship("MailFolder")

    # Constraints and indexes
    __table_args__ = (
        # Ensure folder belongs to either personal account OR shared mailbox, not both
        CheckConstraint(
            "(mail_account_id IS NOT NULL AND shared_mailbox_id IS NULL) OR "
            "(mail_account_id IS NULL AND shared_mailbox_id IS NOT NULL)",
            name="ck_mail_folders_exclusive_ownership"
        ),
        Index("ix_mail_folders_mail_account_id", "mail_account_id"),
        Index("ix_mail_folders_shared_mailbox_id", "shared_mailbox_id"),
        Index("ix_mail_folders_parent_folder_id", "parent_folder_id"),
        Index("ix_mail_folders_azure_folder_id", "azure_folder_id"),
        Index("ix_mail_folders_system", "is_system_folder"),
        Index("ix_mail_folders_path", "folder_path"),
    )

    def __repr__(self) -> str:
        return f"<MailFolder(id='{self.id}', name='{self.name}', path='{self.folder_path}')>"