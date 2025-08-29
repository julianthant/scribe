# SQLAlchemy Relationship Patterns for Scribe

This document establishes the authoritative guidelines for implementing SQLAlchemy relationships in the Scribe application, based on SQLAlchemy 2.0+ best practices with annotated declarative mappings.

## Table of Contents

1. [Core Principles](#core-principles)
2. [Import Structure](#import-structure)
3. [Relationship Patterns](#relationship-patterns)
4. [Best Practices](#best-practices)
5. [Common Pitfalls](#common-pitfalls)
6. [Examples from Scribe](#examples-from-scribe)
7. [Migration Guidelines](#migration-guidelines)

## Core Principles

### 1. Consistency Above All
- **Always use bidirectional relationships** with `back_populates`
- **Use annotated declarative mappings** with `Mapped` annotations
- **Follow the same pattern across the entire codebase**

### 2. Type Safety
- **Use `TYPE_CHECKING` imports** for forward references
- **Specify collection types** with `List["Model"]`, `Set["Model"]`, etc.
- **Use `Optional["Model"]` for nullable relationships**

### 3. Clarity and Maintainability
- **Explicit is better than implicit** - always specify relationship parameters
- **Document relationship business logic** when complex
- **Group related relationships** with comments

## Import Structure

### Required Pattern
```python
from typing import List, Optional, TYPE_CHECKING

# ... other imports ...

# Forward reference imports for relationships
if TYPE_CHECKING:
    from .OtherModel import OtherModel, RelatedModel
```

### ❌ Anti-patterns
```python
# DON'T use this pattern
if False:  # TYPE_CHECKING
    from .OtherModel import OtherModel

# DON'T import models directly in module scope (causes circular imports)
from .OtherModel import OtherModel
```

## Relationship Patterns

### One-to-Many Relationships

The most common pattern in Scribe: one parent entity has many child entities.

```python
# Parent side (the "one")
class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    
    # ... columns ...
    
    # Relationships
    voice_attachments: Mapped[List["VoiceAttachment"]] = relationship(
        "VoiceAttachment", 
        back_populates="user",
        cascade="all, delete-orphan"  # Optional: delete children when parent deleted
    )

# Child side (the "many")  
class VoiceAttachment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "voice_attachments"
    
    # Foreign key to parent
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # ... other columns ...
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="voice_attachments")
```

**Key Points:**
- Foreign key always on the "many" side
- Use `List["ChildModel"]` on parent
- Use `Mapped["ParentModel"]` on child
- Always specify `back_populates` on both sides

### Many-to-One Relationships

The reverse perspective of one-to-many, focusing on the child's reference to parent.

```python
# Child side (many instances can reference one parent)
class MailFolder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "mail_folders"
    
    mail_account_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("mail_accounts.id"), 
        nullable=True
    )
    
    # Relationships
    mail_account: Mapped[Optional["MailAccount"]] = relationship(
        "MailAccount", 
        back_populates="folders"
    )

# Parent side
class MailAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "mail_accounts"
    
    # Relationships
    folders: Mapped[List["MailFolder"]] = relationship(
        "MailFolder", 
        back_populates="mail_account",
        cascade="all, delete-orphan"
    )
```

### One-to-One Relationships

When each instance of one entity relates to exactly one instance of another.

```python
class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    
    # Relationships
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile", 
        back_populates="user", 
        uselist=False  # Critical for one-to-one
    )

class UserProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_profiles"
    
    # Foreign key (can be on either side)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), 
        nullable=False, 
        unique=True  # Ensures one-to-one
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")
```

**Key Points:**
- Use `uselist=False` on one side (typically the parent)
- Add `unique=True` constraint on foreign key
- Consider if you really need separate tables vs. adding columns

### Self-Referential Relationships

When a model references itself (like folder hierarchies).

```python
class MailFolder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "mail_folders"
    
    parent_folder_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("mail_folders.id"), 
        nullable=True
    )
    
    # Relationships
    parent_folder: Mapped[Optional["MailFolder"]] = relationship(
        "MailFolder", 
        remote_side="MailFolder.id",  # Critical: specify which side is "remote"
        back_populates="child_folders"
    )
    child_folders: Mapped[List["MailFolder"]] = relationship(
        "MailFolder",
        back_populates="parent_folder"
    )
```

**Key Points:**
- Use `remote_side` parameter to specify the "one" side
- Use string notation: `remote_side="MailFolder.id"`
- Be careful with cascades to avoid infinite recursion

### Many-to-Many Relationships

When entities on both sides can relate to multiple entities on the other side.

> **Note:** Scribe currently doesn't use many-to-many relationships, preferring explicit junction tables with additional metadata. If you need many-to-many, consider an association object pattern instead.

```python
# Association table (if pure many-to-many needed)
association_table = Table(
    "user_mailbox_access",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("mailbox_id", ForeignKey("shared_mailboxes.id"), primary_key=True),
)

class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    
    # Relationships
    accessible_mailboxes: Mapped[List["SharedMailbox"]] = relationship(
        "SharedMailbox",
        secondary=association_table,
        back_populates="authorized_users"
    )

class SharedMailbox(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "shared_mailboxes"
    
    # Relationships  
    authorized_users: Mapped[List["User"]] = relationship(
        "User",
        secondary=association_table,
        back_populates="accessible_mailboxes"
    )
```

## Best Practices

### 1. Relationship Naming

**DO:**
```python
# Descriptive, plural for collections
voice_attachments: Mapped[List["VoiceAttachment"]] = relationship(...)
transcription_errors: Mapped[List["TranscriptionError"]] = relationship(...)

# Descriptive, singular for single objects  
voice_attachment: Mapped["VoiceAttachment"] = relationship(...)
parent_folder: Mapped[Optional["MailFolder"]] = relationship(...)
```

**DON'T:**
```python
# Generic, unclear names
items: Mapped[List["VoiceAttachment"]] = relationship(...)
data: Mapped["VoiceAttachment"] = relationship(...)

# Inconsistent naming
attachment: Mapped[List["VoiceAttachment"]] = relationship(...)  # Should be plural
```

### 2. Cascade Configuration

**Common Cascade Patterns:**
```python
# Delete children when parent is deleted
cascade="all, delete-orphan"

# Delete children only when explicitly deleted
cascade="all"

# No automatic deletion (default)
# cascade not specified or cascade="save-update, merge"
```

**Usage Guidelines:**
- Use `"all, delete-orphan"` for strongly owned relationships (e.g., User → Sessions)
- Use `"all"` for moderately coupled relationships (e.g., VoiceAttachment → Downloads)
- Don't specify cascade for lookup/reference relationships (e.g., User references)

### 3. Collection Types

**Scribe Standard:**
```python
# Default: List for ordered collections
items: Mapped[List["Item"]] = relationship(...)

# Use Set when order doesn't matter and duplicates should be prevented
tags: Mapped[Set["Tag"]] = relationship(...)

# Use Optional for nullable one-to-one or many-to-one
parent: Mapped[Optional["Parent"]] = relationship(...)
```

### 4. Lazy Loading Strategy

**Default Strategy:** Let SQLAlchemy choose (typically `select`)

**When to Customize:**
```python
# Use 'selectin' for collections frequently accessed together
relationship("Child", lazy='selectin')

# Use 'joined' for single objects frequently accessed together  
relationship("Parent", lazy='joined')

# Use 'noload' for relationships that should be explicitly loaded
relationship("HeavyData", lazy='noload')
```

## Common Pitfalls

### 1. Missing back_populates

❌ **Wrong:**
```python
class User(Base):
    sessions: Mapped[List["Session"]] = relationship("Session")

class Session(Base):
    user: Mapped["User"] = relationship("User")
```

✅ **Correct:**
```python
class User(Base):
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user")

class Session(Base):
    user: Mapped["User"] = relationship("User", back_populates="sessions")
```

### 2. Circular Import Issues

❌ **Wrong:**
```python
from .user import User  # Causes circular import

class VoiceAttachment(Base):
    user: Mapped[User] = relationship(User)
```

✅ **Correct:**
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User

class VoiceAttachment(Base):
    user: Mapped["User"] = relationship("User", back_populates="voice_attachments")
```

### 3. Self-Referential Syntax Errors

❌ **Wrong:**
```python
parent: Mapped[Optional["MailFolder"]] = relationship(
    "MailFolder", 
    remote_side=[id]  # Using bare 'id' variable
)
```

✅ **Correct:**
```python
parent: Mapped[Optional["MailFolder"]] = relationship(
    "MailFolder", 
    remote_side="MailFolder.id"  # String notation
)
```

### 4. One-to-One Configuration

❌ **Wrong:**
```python
# Missing uselist=False makes this one-to-many
profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="user")
```

✅ **Correct:**
```python
# Properly configured one-to-one
profile: Mapped[Optional["UserProfile"]] = relationship(
    "UserProfile", 
    back_populates="user", 
    uselist=False
)
```

## Examples from Scribe

### User → Voice Ecosystem
```python
class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    
    # Voice attachment relationships
    voice_attachments: Mapped[List["VoiceAttachment"]] = relationship(
        "VoiceAttachment", back_populates="user"
    )
    voice_attachment_downloads: Mapped[List["VoiceAttachmentDownload"]] = relationship(
        "VoiceAttachmentDownload", back_populates="user"
    )
    
    # Transcription relationships
    voice_transcriptions: Mapped[List["VoiceTranscription"]] = relationship(
        "VoiceTranscription", back_populates="user"
    )
    transcription_errors: Mapped[List["TranscriptionError"]] = relationship(
        "TranscriptionError", back_populates="user"
    )
```

### Voice Attachment → Transcription (One-to-One)
```python
class VoiceAttachment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "voice_attachments"
    
    transcription: Mapped[Optional["VoiceTranscription"]] = relationship(
        "VoiceTranscription", 
        back_populates="voice_attachment", 
        cascade="all, delete-orphan", 
        uselist=False  # One-to-one relationship
    )

class VoiceTranscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "voice_transcriptions"
    
    voice_attachment_id: Mapped[str] = mapped_column(
        ForeignKey("voice_attachments.id"), nullable=False
    )
    
    voice_attachment: Mapped["VoiceAttachment"] = relationship(
        "VoiceAttachment", back_populates="transcription"
    )
```

### Mail Folder Hierarchy (Self-Referential)
```python
class MailFolder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "mail_folders"
    
    parent_folder_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("mail_folders.id"), nullable=True
    )
    
    # Self-referential relationships
    parent_folder: Mapped[Optional["MailFolder"]] = relationship(
        "MailFolder", 
        remote_side="MailFolder.id",
        back_populates="child_folders"
    )
    child_folders: Mapped[List["MailFolder"]] = relationship(
        "MailFolder",
        back_populates="parent_folder"
    )
```

## Migration Guidelines

### When Adding New Relationships

1. **Add the relationship to both sides**
   ```python
   # Add to parent model
   new_children: Mapped[List["Child"]] = relationship("Child", back_populates="parent")
   
   # Add to child model  
   parent: Mapped["Parent"] = relationship("Parent", back_populates="new_children")
   ```

2. **Update TYPE_CHECKING imports**
   ```python
   if TYPE_CHECKING:
       from .parent import Parent  # Add new import
   ```

3. **Test the relationship**
   ```python
   # Verify both directions work
   parent = Parent()
   child = Child(parent=parent)
   assert parent.new_children[0] == child
   assert child.parent == parent
   ```

### When Modifying Existing Relationships

1. **Always update both sides simultaneously**
2. **Update any cascade behaviors carefully**
3. **Test data migration if relationships change**
4. **Update any related query patterns**

## Enforcement Checklist

For every relationship in the codebase:

- [ ] Uses proper `TYPE_CHECKING` imports
- [ ] Has `back_populates` on both sides
- [ ] Uses correct `Mapped` type annotations
- [ ] Follows naming conventions (plural for collections, singular for objects)
- [ ] Has appropriate cascade configuration
- [ ] Uses `uselist=False` for one-to-one relationships
- [ ] Uses `remote_side` correctly for self-referential relationships
- [ ] Has proper foreign key constraints in the database

---

**Last Updated:** August 2025
**Version:** 1.0
**Author:** Claude Code Assistant

This document is the authoritative source for SQLAlchemy relationship patterns in Scribe. All relationships must conform to these guidelines to ensure consistency, maintainability, and type safety.