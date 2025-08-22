"""
shared_mailbox.py - Shared Mailbox Data Models

Defines Pydantic models for shared mailbox operations and Microsoft Graph API responses.
This module provides:
- SharedMailbox: Shared mailbox configuration and metadata
- SharedMailboxAccess: Access permissions and user rights
- SharedMailboxStatistics: Usage and analytics data
- Request/Response models: CreateSharedMailboxRequest, SharedMailboxListResponse, etc.
- Enum types: SharedMailboxAccessLevel, SharedMailboxType
- Search and filter models for shared mailbox operations
- Organization and management request models
- Permission and delegation models

All models support shared mailbox operations including creation, access management,
content organization, and statistical reporting through the Graph API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

from app.models.mail import Message, MessageListResponse, MailFolder, FolderStatistics


class SharedMailboxAccessLevel(str, Enum):
    """Shared mailbox access levels."""
    OWNER = "owner"
    EDITOR = "editor"
    AUTHOR = "author"
    REVIEWER = "reviewer"
    CONTRIBUTOR = "contributor"
    NONE = "none"


class SharedMailboxType(str, Enum):
    """Shared mailbox types."""
    SHARED = "shared"
    RESOURCE = "resource"
    EQUIPMENT = "equipment"
    ROOM = "room"


class DelegationType(str, Enum):
    """Delegation permission types."""
    SEND_AS = "sendAs"
    SEND_ON_BEHALF = "sendOnBehalf"
    FULL_ACCESS = "fullAccess"
    READ_ONLY = "readOnly"


class SharedMailbox(BaseModel):
    """Shared mailbox model."""
    id: str = Field(..., description="Shared mailbox ID")
    displayName: str = Field(..., description="Display name")
    emailAddress: str = Field(..., description="Primary email address")
    aliases: List[str] = Field(default_factory=list, description="Email aliases")
    mailboxType: SharedMailboxType = Field(SharedMailboxType.SHARED, description="Mailbox type")
    isActive: bool = Field(True, description="Whether mailbox is active")
    description: Optional[str] = Field(None, description="Mailbox description")
    createdDateTime: Optional[datetime] = Field(None, description="Creation timestamp")
    lastModifiedDateTime: Optional[datetime] = Field(None, description="Last modified timestamp")
    resourceCapacity: Optional[int] = Field(None, description="Resource capacity (for room/equipment)")
    location: Optional[str] = Field(None, description="Physical location")
    phone: Optional[str] = Field(None, description="Contact phone number")
    department: Optional[str] = Field(None, description="Department or team")
    companyName: Optional[str] = Field(None, description="Company or organization")


class SharedMailboxPermission(BaseModel):
    """Shared mailbox permission model."""
    mailboxId: str = Field(..., description="Shared mailbox ID")
    userId: str = Field(..., description="User ID")
    userPrincipalName: str = Field(..., description="User principal name")
    displayName: str = Field(..., description="User display name")
    accessLevel: SharedMailboxAccessLevel = Field(..., description="Access level")
    delegationType: List[DelegationType] = Field(default_factory=list, description="Delegation permissions")
    grantedDate: Optional[datetime] = Field(None, description="When permission was granted")
    grantedBy: Optional[str] = Field(None, description="Who granted the permission")
    isInherited: bool = Field(False, description="Whether permission is inherited")
    expiresOn: Optional[datetime] = Field(None, description="Permission expiration date")


class SharedMailboxAccess(BaseModel):
    """Shared mailbox access details for current user."""
    mailbox: SharedMailbox = Field(..., description="Shared mailbox information")
    permissions: List[SharedMailboxPermission] = Field(..., description="User permissions")
    accessLevel: SharedMailboxAccessLevel = Field(..., description="Current user's access level")
    canRead: bool = Field(..., description="Can read messages")
    canWrite: bool = Field(..., description="Can create/modify messages")
    canSend: bool = Field(..., description="Can send messages")
    canManage: bool = Field(..., description="Can manage permissions")
    lastAccessed: Optional[datetime] = Field(None, description="Last access timestamp")


class SharedMailboxMessage(Message):
    """Extended message model for shared mailboxes."""
    sharedMailboxId: str = Field(..., description="Source shared mailbox ID")
    sharedMailboxName: str = Field(..., description="Source shared mailbox name")
    sharedMailboxEmail: str = Field(..., description="Source shared mailbox email")
    onBehalfOf: Optional[str] = Field(None, description="User acting on behalf of mailbox")
    delegatedBy: Optional[str] = Field(None, description="User who delegated access")


class CreateSharedMailboxRequest(BaseModel):
    """Request to create a shared mailbox."""
    displayName: str = Field(..., description="Display name", min_length=1, max_length=256)
    emailAddress: str = Field(..., description="Primary email address")
    aliases: List[str] = Field(default_factory=list, description="Additional email aliases")
    mailboxType: SharedMailboxType = Field(SharedMailboxType.SHARED, description="Mailbox type")
    description: Optional[str] = Field(None, description="Mailbox description", max_length=1024)
    location: Optional[str] = Field(None, description="Physical location", max_length=256)
    phone: Optional[str] = Field(None, description="Contact phone")
    department: Optional[str] = Field(None, description="Department", max_length=256)
    resourceCapacity: Optional[int] = Field(None, description="Capacity for room/equipment", ge=1)


class UpdateSharedMailboxRequest(BaseModel):
    """Request to update shared mailbox properties."""
    displayName: Optional[str] = Field(None, description="Display name", min_length=1, max_length=256)
    aliases: Optional[List[str]] = Field(None, description="Email aliases")
    description: Optional[str] = Field(None, description="Description", max_length=1024)
    location: Optional[str] = Field(None, description="Location", max_length=256)
    phone: Optional[str] = Field(None, description="Phone number")
    department: Optional[str] = Field(None, description="Department", max_length=256)
    resourceCapacity: Optional[int] = Field(None, description="Capacity", ge=1)
    isActive: Optional[bool] = Field(None, description="Active status")


class GrantPermissionRequest(BaseModel):
    """Request to grant permission to a shared mailbox."""
    userPrincipalName: str = Field(..., description="User to grant access to")
    accessLevel: SharedMailboxAccessLevel = Field(..., description="Access level to grant")
    delegationType: List[DelegationType] = Field(default_factory=list, description="Delegation types")
    expiresOn: Optional[datetime] = Field(None, description="Permission expiration date")
    notify: bool = Field(True, description="Send notification to user")


class RevokePermissionRequest(BaseModel):
    """Request to revoke permission from a shared mailbox."""
    userPrincipalName: str = Field(..., description="User to revoke access from")
    accessLevel: Optional[SharedMailboxAccessLevel] = Field(None, description="Specific access level to revoke")
    delegationType: Optional[List[DelegationType]] = Field(None, description="Specific delegation types to revoke")
    notify: bool = Field(True, description="Send notification to user")


class SendAsSharedRequest(BaseModel):
    """Request to send message as shared mailbox."""
    to: List[str] = Field(..., description="Recipient email addresses")
    cc: Optional[List[str]] = Field(None, description="CC recipients")
    bcc: Optional[List[str]] = Field(None, description="BCC recipients")
    subject: str = Field(..., description="Message subject")
    body: str = Field(..., description="Message body")
    bodyType: str = Field("html", description="Body content type")
    importance: Optional[str] = Field(None, description="Message importance")
    attachments: Optional[List[str]] = Field(None, description="Attachment IDs")
    saveToSentItems: bool = Field(True, description="Save copy to sent items")
    requestDeliveryReceipt: bool = Field(False, description="Request delivery receipt")
    requestReadReceipt: bool = Field(False, description="Request read receipt")


class SharedMailboxStatistics(BaseModel):
    """Statistics for a shared mailbox."""
    mailboxId: str = Field(..., description="Mailbox ID")
    mailboxName: str = Field(..., description="Mailbox name")
    emailAddress: str = Field(..., description="Primary email address")
    totalMessages: int = Field(0, description="Total messages")
    unreadMessages: int = Field(0, description="Unread messages")
    messagesWithAttachments: int = Field(0, description="Messages with attachments")
    voiceMessages: int = Field(0, description="Voice messages")
    totalFolders: int = Field(0, description="Total folders")
    mailboxSizeMB: float = Field(0.0, description="Mailbox size in MB")
    lastMessageDate: Optional[datetime] = Field(None, description="Last message received")
    mostActiveUsers: List[Dict[str, Any]] = Field(default_factory=list, description="Most active users")
    dailyMessageCounts: Dict[str, int] = Field(default_factory=dict, description="Daily message counts")
    attachmentStatistics: Dict[str, Any] = Field(default_factory=dict, description="Attachment statistics")


class SharedMailboxSearchRequest(BaseModel):
    """Request to search across shared mailboxes."""
    query: str = Field(..., description="Search query", min_length=1)
    mailboxIds: Optional[List[str]] = Field(None, description="Specific mailboxes to search")
    folderId: Optional[str] = Field(None, description="Specific folder to search in")
    hasAttachments: Optional[bool] = Field(None, description="Filter by attachment presence")
    hasVoiceAttachments: Optional[bool] = Field(None, description="Filter by voice attachment presence")
    dateFrom: Optional[datetime] = Field(None, description="Start date filter")
    dateTo: Optional[datetime] = Field(None, description="End date filter")
    fromUsers: Optional[List[str]] = Field(None, description="Filter by sender")
    importance: Optional[str] = Field(None, description="Filter by importance")
    isRead: Optional[bool] = Field(None, description="Filter by read status")
    top: int = Field(25, description="Number of results per mailbox", ge=1, le=100)
    skip: int = Field(0, description="Number of results to skip", ge=0)


class SharedMailboxSearchResponse(BaseModel):
    """Response from shared mailbox search."""
    query: str = Field(..., description="Original search query")
    totalResults: int = Field(0, description="Total results across all mailboxes")
    searchedMailboxes: List[str] = Field(..., description="Mailboxes that were searched")
    results: List[Dict[str, Any]] = Field(..., description="Search results grouped by mailbox")
    executionTimeMs: int = Field(..., description="Search execution time in milliseconds")


class OrganizeSharedMailboxRequest(BaseModel):
    """Request to organize messages in a shared mailbox."""
    targetFolderName: str = Field("Voice Messages", description="Target folder name")
    createFolder: bool = Field(True, description="Create folder if it doesn't exist")
    messageType: str = Field("voice", description="Type of messages to organize")
    includeSubfolders: bool = Field(False, description="Include subfolders in search")
    preserveReadStatus: bool = Field(True, description="Preserve read/unread status")


class OrganizeSharedMailboxResponse(BaseModel):
    """Response from organizing shared mailbox messages."""
    mailboxId: str = Field(..., description="Shared mailbox ID")
    mailboxName: str = Field(..., description="Shared mailbox name")
    messagesProcessed: int = Field(0, description="Number of messages processed")
    messagesMoved: int = Field(0, description="Number of messages moved")
    foldersCreated: int = Field(0, description="Number of folders created")
    targetFolderId: str = Field(..., description="Target folder ID")
    processingTimeMs: int = Field(..., description="Processing time in milliseconds")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class SharedMailboxListResponse(BaseModel):
    """Paginated response for shared mailbox list."""
    value: List[SharedMailbox] = Field(..., description="List of shared mailboxes")
    totalCount: int = Field(..., description="Total number of accessible mailboxes")
    accessibleCount: int = Field(..., description="Number of mailboxes user can access")
    odata_nextLink: Optional[str] = Field(None, alias="@odata.nextLink", description="Next page link")


class SharedMailboxAccessRequest(BaseModel):
    """Request to access a shared mailbox."""
    mailboxId: str = Field(..., description="Shared mailbox ID")
    justification: Optional[str] = Field(None, description="Access justification", max_length=500)
    accessLevel: SharedMailboxAccessLevel = Field(SharedMailboxAccessLevel.REVIEWER, description="Requested access level")
    duration: Optional[int] = Field(None, description="Access duration in days")


class SharedMailboxAuditEntry(BaseModel):
    """Audit entry for shared mailbox operations."""
    mailboxId: str = Field(..., description="Shared mailbox ID")
    mailboxName: str = Field(..., description="Shared mailbox name")
    userId: str = Field(..., description="User ID performing action")
    userPrincipalName: str = Field(..., description="User principal name")
    action: str = Field(..., description="Action performed")
    details: Dict[str, Any] = Field(default_factory=dict, description="Action details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Action timestamp")
    ipAddress: Optional[str] = Field(None, description="User IP address")
    userAgent: Optional[str] = Field(None, description="User agent string")
    success: bool = Field(True, description="Whether action was successful")
    errorMessage: Optional[str] = Field(None, description="Error message if action failed")