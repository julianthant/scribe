"""
Database Models Package

This package contains all SQLAlchemy database models for the Scribe application,
following Third Normal Form (3NF) normalization principles as defined in CLAUDE.md.

Design Principles:
- No redundancy: Each fact stored exactly once
- No JSON/array columns: Each cell contains atomic values
- No calculated fields: Don't store what can be computed
- Proper entity separation: Each table represents ONE subject
- UUID primary keys with SQL Server NEWID()
- Consistent naming: plural table names, singular column names

Models are organized by functional area:
- User: Authentication and user management (with role-based access control)
- MailAccount: Mail account and shared mailbox management
- MailData: Mail folders only (messages handled via Graph API)
- Operational: Sync status and audit logging
"""

# Import all models to ensure they are registered with Base.metadata
from .User import User, UserProfile, Session, UserRole
from .MailAccount import MailAccount, SharedMailbox
from .MailData import MailFolder
from .Operational import SyncStatus, AuditLog

__all__ = [
    # User models
    "User",
    "UserProfile", 
    "Session",
    "UserRole",
    # Mail account models
    "MailAccount",
    "SharedMailbox",
    # Mail data models
    "MailFolder",
    # Operational models
    "SyncStatus",
    "AuditLog",
]