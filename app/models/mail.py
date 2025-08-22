"""
mail.py - Mail Data Models

Defines Pydantic models for email-related data structures and Microsoft Graph API responses.
This module provides:
- Message: Email message model with headers, body, and metadata
- MailFolder: Mail folder structure with hierarchy and statistics
- Attachment models: FileAttachment, VoiceAttachment, ItemAttachment
- Request/Response models: CreateFolderRequest, MessageListResponse, etc.
- Enum types: BodyType, Importance, AttachmentType
- EmailAddress and Recipient models for sender/receiver information
- Filter and search models for message querying
- Statistics models for folder analytics

All models include validation, serialization, and documentation for mail API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class BodyType(str, Enum):
    """Email body content types."""
    TEXT = "text"
    HTML = "html"


class Importance(str, Enum):
    """Email importance levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class AttachmentType(str, Enum):
    """Attachment types."""
    FILE = "fileAttachment"
    ITEM = "itemAttachment"
    REFERENCE = "referenceAttachment"


class EmailAddress(BaseModel):
    """Email address model."""
    name: str = Field("", description="Display name")
    address: str = Field(..., description="Email address")


class Recipient(BaseModel):
    """Email recipient model."""
    emailAddress: EmailAddress = Field(..., description="Email address details")


class ItemBody(BaseModel):
    """Email body content model."""
    contentType: BodyType = Field(..., description="Content type")
    content: str = Field("", description="Body content")


class Attachment(BaseModel):
    """Base attachment model."""
    id: str = Field(..., description="Attachment ID")
    name: str = Field(..., description="Attachment name")
    contentType: Optional[str] = Field(None, description="MIME content type")
    size: int = Field(0, description="Attachment size in bytes")
    isInline: bool = Field(False, description="Whether attachment is inline")
    lastModifiedDateTime: Optional[datetime] = Field(None, description="Last modified time")
    odata_type: Optional[str] = Field(None, validation_alias="@odata.type", serialization_alias="@odata.type", description="OData type")


class FileAttachment(Attachment):
    """File attachment model."""
    contentBytes: Optional[str] = Field(None, description="Base64 encoded content")
    contentId: Optional[str] = Field(None, description="Content ID")
    contentLocation: Optional[str] = Field(None, description="Content location")


class ItemAttachment(Attachment):
    """Item attachment model (for nested Outlook items)."""
    item: Optional[Dict[str, Any]] = Field(None, description="Nested item data")


class ReferenceAttachment(Attachment):
    """Reference attachment model (cloud links)."""
    sourceUrl: Optional[str] = Field(None, description="Source URL")
    providerType: Optional[str] = Field(None, description="Provider type")
    permission: Optional[str] = Field(None, description="Permission level")


class MailFolder(BaseModel):
    """Mail folder model."""
    id: str = Field(..., description="Folder ID")
    displayName: str = Field(..., description="Folder display name")
    parentFolderId: Optional[str] = Field(None, description="Parent folder ID")
    childFolderCount: int = Field(0, description="Number of child folders")
    unreadItemCount: int = Field(0, description="Number of unread items")
    totalItemCount: int = Field(0, description="Total number of items")
    isHidden: bool = Field(False, description="Whether folder is hidden")


class Message(BaseModel):
    """Email message model."""
    id: str = Field(..., description="Message ID")
    subject: str = Field("", description="Message subject")
    body: Optional[ItemBody] = Field(None, description="Message body")
    bodyPreview: str = Field("", description="Message body preview")
    sender: Optional[Recipient] = Field(None, description="Message sender")
    from_: Optional[Recipient] = Field(None, alias="from", description="Message from")
    toRecipients: List[Recipient] = Field(default_factory=list, description="To recipients")
    ccRecipients: List[Recipient] = Field(default_factory=list, description="CC recipients")
    bccRecipients: List[Recipient] = Field(default_factory=list, description="BCC recipients")
    receivedDateTime: Optional[datetime] = Field(None, description="Received timestamp")
    sentDateTime: Optional[datetime] = Field(None, description="Sent timestamp")
    createdDateTime: Optional[datetime] = Field(None, description="Created timestamp")
    lastModifiedDateTime: Optional[datetime] = Field(None, description="Last modified timestamp")
    hasAttachments: bool = Field(False, description="Whether message has attachments")
    importance: Importance = Field(Importance.NORMAL, description="Message importance")
    isRead: bool = Field(False, description="Whether message is read")
    isDraft: bool = Field(False, description="Whether message is a draft")
    parentFolderId: Optional[str] = Field(None, description="Parent folder ID")
    conversationId: Optional[str] = Field(None, description="Conversation ID")
    internetMessageId: Optional[str] = Field(None, description="Internet message ID")
    webLink: Optional[str] = Field(None, description="Web link to message")
    attachments: List[Attachment] = Field(default_factory=list, description="Message attachments")


class MessageListResponse(BaseModel):
    """Paginated message list response."""
    value: List[Message] = Field(..., description="List of messages")
    odata_nextLink: Optional[str] = Field(None, alias="@odata.nextLink", description="Next page link")
    odata_count: Optional[int] = Field(None, alias="@odata.count", description="Total count")


class CreateFolderRequest(BaseModel):
    """Request to create a new mail folder."""
    displayName: str = Field(..., description="Folder name", min_length=1, max_length=255)
    parentFolderId: Optional[str] = Field(None, description="Parent folder ID")


class MoveMessageRequest(BaseModel):
    """Request to move a message to a folder."""
    destinationId: str = Field(..., description="Destination folder ID or name")


class UpdateMessageRequest(BaseModel):
    """Request to update message properties."""
    isRead: Optional[bool] = Field(None, description="Mark as read/unread")
    importance: Optional[Importance] = Field(None, description="Set importance level")


class AttachmentFilter(BaseModel):
    """Filter for searching attachments."""
    contentTypes: Optional[List[str]] = Field(None, description="Filter by content types")
    hasVoiceAttachments: Optional[bool] = Field(None, description="Filter messages with voice attachments")
    minSize: Optional[int] = Field(None, description="Minimum attachment size in bytes")
    maxSize: Optional[int] = Field(None, description="Maximum attachment size in bytes")


class VoiceAttachment(BaseModel):
    """Voice attachment details."""
    messageId: str = Field(..., description="Parent message ID")
    attachmentId: str = Field(..., description="Attachment ID")
    name: str = Field(..., description="Attachment filename")
    contentType: str = Field(..., description="Audio content type")
    size: int = Field(..., description="File size in bytes")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    sampleRate: Optional[int] = Field(None, description="Audio sample rate")
    bitRate: Optional[int] = Field(None, description="Audio bit rate")


class FolderStatistics(BaseModel):
    """Folder statistics model."""
    folderId: str = Field(..., description="Folder ID")
    folderName: str = Field(..., description="Folder name")
    totalMessages: int = Field(0, description="Total messages")
    unreadMessages: int = Field(0, description="Unread messages")
    messagesWithAttachments: int = Field(0, description="Messages with attachments")
    voiceMessages: int = Field(0, description="Messages with voice attachments")
    totalAttachmentSize: int = Field(0, description="Total attachment size in bytes")


class OrganizeVoiceRequest(BaseModel):
    """Request to organize voice messages."""
    targetFolderName: str = Field("Voice Messages", description="Target folder name")
    createFolder: bool = Field(True, description="Create folder if it doesn't exist")
    includeSubfolders: bool = Field(False, description="Include subfolders in search")


class OrganizeVoiceResponse(BaseModel):
    """Response from organizing voice messages."""
    messagesProcessed: int = Field(0, description="Number of messages processed")
    messagesMoved: int = Field(0, description="Number of messages moved")
    voiceAttachmentsFound: int = Field(0, description="Number of voice attachments found")
    folderCreated: bool = Field(False, description="Whether target folder was created")
    targetFolderId: str = Field(..., description="Target folder ID")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")


class SearchMessagesRequest(BaseModel):
    """Request to search messages."""
    query: str = Field(..., description="Search query", min_length=1)
    folderId: Optional[str] = Field(None, description="Folder to search in")
    hasAttachments: Optional[bool] = Field(None, description="Filter by attachment presence")
    hasVoiceAttachments: Optional[bool] = Field(None, description="Filter by voice attachment presence")
    dateFrom: Optional[datetime] = Field(None, description="Start date filter")
    dateTo: Optional[datetime] = Field(None, description="End date filter")
    importance: Optional[Importance] = Field(None, description="Filter by importance")
    isRead: Optional[bool] = Field(None, description="Filter by read status")
    top: int = Field(25, description="Number of results to return", ge=1, le=1000)
    skip: int = Field(0, description="Number of results to skip", ge=0)