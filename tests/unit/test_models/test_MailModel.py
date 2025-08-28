"""
test_MailModel.py - Unit tests for mail Pydantic models

Tests all mail-related models in app.models.MailModel including:
- Enums: BodyType, Importance, AttachmentType
- Core models: EmailAddress, Recipient, ItemBody, Message, MailFolder
- Attachment models: Attachment, FileAttachment, ItemAttachment, ReferenceAttachment
- Voice models: VoiceAttachment, StoredVoiceAttachment, etc.
- Request/Response models: CreateFolderRequest, MoveMessageRequest, etc.
- Statistics models: FolderStatistics, VoiceAttachmentStorageStatistics
- Search and filter models: SearchMessagesRequest, AttachmentFilter

Tests include validation, serialization, field constraints, default values, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pydantic import ValidationError

from app.models.MailModel import (
    # Enums
    BodyType, Importance, AttachmentType,
    # Core models
    EmailAddress, Recipient, ItemBody, Message, MailFolder,
    # Attachment models
    Attachment, FileAttachment, ItemAttachment, ReferenceAttachment,
    # Voice models
    VoiceAttachment, StoredVoiceAttachment, StoredVoiceAttachmentList,
    # Request/Response models
    MessageListResponse, CreateFolderRequest, MoveMessageRequest, UpdateMessageRequest,
    StoreVoiceAttachmentRequest, StoreVoiceAttachmentResponse,
    # Statistics models
    FolderStatistics, VoiceAttachmentStorageStatistics, VoiceAttachmentCleanupStats,
    # Organization models
    OrganizeVoiceRequest, OrganizeVoiceResponse,
    # Search models
    SearchMessagesRequest, AttachmentFilter,
    # Other models
    DeleteVoiceAttachmentResponse
)


class TestEnums:
    """Test cases for mail model enums."""

    def test_body_type_enum_values(self):
        """Test BodyType enum has correct values."""
        assert BodyType.TEXT == "text"
        assert BodyType.HTML == "html"
        
        # Test all members
        assert len(list(BodyType)) == 2
        assert BodyType.TEXT in BodyType
        assert BodyType.HTML in BodyType

    def test_importance_enum_values(self):
        """Test Importance enum has correct values."""
        assert Importance.LOW == "low"
        assert Importance.NORMAL == "normal"
        assert Importance.HIGH == "high"
        
        # Test all members
        assert len(list(Importance)) == 3
        assert all(level in Importance for level in [Importance.LOW, Importance.NORMAL, Importance.HIGH])

    def test_attachment_type_enum_values(self):
        """Test AttachmentType enum has correct values."""
        assert AttachmentType.FILE == "fileAttachment"
        assert AttachmentType.ITEM == "itemAttachment"
        assert AttachmentType.REFERENCE == "referenceAttachment"
        
        # Test all members
        assert len(list(AttachmentType)) == 3
        assert all(att_type in AttachmentType for att_type in 
                  [AttachmentType.FILE, AttachmentType.ITEM, AttachmentType.REFERENCE])

    @pytest.mark.parametrize("enum_class,expected_count", [
        (BodyType, 2),
        (Importance, 3),
        (AttachmentType, 3),
    ])
    def test_enum_member_counts(self, enum_class, expected_count):
        """Test that enums have expected member counts."""
        assert len(list(enum_class)) == expected_count


class TestEmailAddress:
    """Test cases for EmailAddress model."""

    def test_email_address_valid_data_creates_instance(self):
        """Test that valid data creates EmailAddress instance."""
        email_data = {
            "name": "John Doe",
            "address": "john.doe@example.com"
        }
        
        email_address = EmailAddress(**email_data)
        
        assert email_address.name == "John Doe"
        assert email_address.address == "john.doe@example.com"

    def test_email_address_minimal_data(self):
        """Test EmailAddress with minimal required data."""
        email_address = EmailAddress(address="minimal@example.com")
        
        assert email_address.name == ""  # Default value
        assert email_address.address == "minimal@example.com"

    def test_email_address_missing_required_field_raises_validation_error(self):
        """Test that missing address raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmailAddress(name="Test User")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("address",) for error in errors)

    def test_email_address_empty_address_validation(self):
        """Test EmailAddress with empty address."""
        email_address = EmailAddress(address="")
        assert email_address.address == ""


class TestRecipient:
    """Test cases for Recipient model."""

    def test_recipient_valid_data_creates_instance(self):
        """Test that valid data creates Recipient instance."""
        email_address = EmailAddress(name="Jane Smith", address="jane@example.com")
        recipient_data = {
            "emailAddress": email_address
        }
        
        recipient = Recipient(**recipient_data)
        
        assert recipient.emailAddress == email_address
        assert recipient.emailAddress.name == "Jane Smith"
        assert recipient.emailAddress.address == "jane@example.com"

    def test_recipient_with_nested_email_data(self):
        """Test Recipient with nested EmailAddress data."""
        recipient_data = {
            "emailAddress": {
                "name": "Bob Johnson",
                "address": "bob@example.com"
            }
        }
        
        recipient = Recipient(**recipient_data)
        
        assert recipient.emailAddress.name == "Bob Johnson"
        assert recipient.emailAddress.address == "bob@example.com"

    def test_recipient_missing_required_field_raises_validation_error(self):
        """Test that missing emailAddress raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Recipient()
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("emailAddress",) for error in errors)


class TestItemBody:
    """Test cases for ItemBody model."""

    def test_item_body_valid_data_creates_instance(self):
        """Test that valid data creates ItemBody instance."""
        body_data = {
            "contentType": BodyType.HTML,
            "content": "<p>This is HTML content</p>"
        }
        
        item_body = ItemBody(**body_data)
        
        assert item_body.contentType == BodyType.HTML
        assert item_body.content == "<p>This is HTML content</p>"

    def test_item_body_minimal_data(self):
        """Test ItemBody with minimal required data."""
        item_body = ItemBody(contentType=BodyType.TEXT)
        
        assert item_body.contentType == BodyType.TEXT
        assert item_body.content == ""  # Default value

    @pytest.mark.parametrize("content_type", [BodyType.TEXT, BodyType.HTML])
    def test_item_body_various_content_types(self, content_type):
        """Test ItemBody with various content types."""
        item_body = ItemBody(contentType=content_type, content="Test content")
        
        assert item_body.contentType == content_type
        assert item_body.content == "Test content"


class TestAttachmentModels:
    """Test cases for attachment models."""

    def test_attachment_base_model(self):
        """Test base Attachment model."""
        attachment_data = {
            "id": "attachment-123",
            "name": "document.pdf",
            "contentType": "application/pdf",
            "size": 1024,
            "isInline": False,
            "lastModifiedDateTime": datetime(2023, 1, 15, 10, 30, 0),
            "@odata.type": "#microsoft.graph.fileAttachment"
        }
        
        attachment = Attachment(**attachment_data)
        
        assert attachment.id == "attachment-123"
        assert attachment.name == "document.pdf"
        assert attachment.contentType == "application/pdf"
        assert attachment.size == 1024
        assert attachment.isInline is False
        assert attachment.odata_type == "#microsoft.graph.fileAttachment"

    def test_attachment_minimal_data(self):
        """Test Attachment with minimal required data."""
        attachment = Attachment(id="min-123", name="minimal.txt")
        
        assert attachment.id == "min-123"
        assert attachment.name == "minimal.txt"
        assert attachment.size == 0  # Default
        assert attachment.isInline is False  # Default
        assert attachment.contentType is None  # Default

    def test_file_attachment_model(self):
        """Test FileAttachment model."""
        file_data = {
            "id": "file-456",
            "name": "image.jpg",
            "contentType": "image/jpeg",
            "size": 2048,
            "contentBytes": "base64encodedcontent==",
            "contentId": "image-content-id"
        }
        
        file_attachment = FileAttachment(**file_data)
        
        assert file_attachment.id == "file-456"
        assert file_attachment.name == "image.jpg"
        assert file_attachment.contentBytes == "base64encodedcontent=="
        assert file_attachment.contentId == "image-content-id"

    def test_item_attachment_model(self):
        """Test ItemAttachment model."""
        item_data = {
            "id": "item-789",
            "name": "nested-email",
            "item": {"subject": "Nested email subject", "id": "nested-123"}
        }
        
        item_attachment = ItemAttachment(**item_data)
        
        assert item_attachment.id == "item-789"
        assert item_attachment.name == "nested-email"
        assert item_attachment.item["subject"] == "Nested email subject"

    def test_reference_attachment_model(self):
        """Test ReferenceAttachment model."""
        ref_data = {
            "id": "ref-101",
            "name": "cloud-document",
            "sourceUrl": "https://onedrive.com/document",
            "providerType": "OneDrive",
            "permission": "read"
        }
        
        ref_attachment = ReferenceAttachment(**ref_data)
        
        assert ref_attachment.id == "ref-101"
        assert ref_attachment.sourceUrl == "https://onedrive.com/document"
        assert ref_attachment.providerType == "OneDrive"
        assert ref_attachment.permission == "read"


class TestMessage:
    """Test cases for Message model."""

    def test_message_valid_data_creates_instance(self):
        """Test that valid data creates Message instance."""
        sender = Recipient(emailAddress=EmailAddress(name="Sender", address="sender@example.com"))
        message_data = {
            "id": "message-123",
            "subject": "Test Email",
            "bodyPreview": "This is a test email preview",
            "sender": sender,
            "receivedDateTime": datetime(2023, 1, 15, 10, 0, 0),
            "hasAttachments": True,
            "importance": Importance.HIGH,
            "isRead": False
        }
        
        message = Message(**message_data)
        
        assert message.id == "message-123"
        assert message.subject == "Test Email"
        assert message.sender == sender
        assert message.importance == Importance.HIGH
        assert message.hasAttachments is True
        assert message.isRead is False

    def test_message_minimal_required_data(self):
        """Test Message with minimal required data."""
        message = Message(id="minimal-message")
        
        assert message.id == "minimal-message"
        assert message.subject == ""  # Default
        assert message.importance == Importance.NORMAL  # Default
        assert message.hasAttachments is False  # Default
        assert message.toRecipients == []  # Default
        assert message.attachments == []  # Default

    def test_message_with_recipients(self):
        """Test Message with multiple recipients."""
        to_recipient = Recipient(emailAddress=EmailAddress(address="to@example.com"))
        cc_recipient = Recipient(emailAddress=EmailAddress(address="cc@example.com"))
        message_data = {
            "id": "recipients-test",
            "toRecipients": [to_recipient],
            "ccRecipients": [cc_recipient]
        }
        
        message = Message(**message_data)
        
        assert len(message.toRecipients) == 1
        assert len(message.ccRecipients) == 1
        assert message.toRecipients[0].emailAddress.address == "to@example.com"
        assert message.ccRecipients[0].emailAddress.address == "cc@example.com"

    def test_message_with_attachments(self):
        """Test Message with attachments."""
        attachment = Attachment(id="att-1", name="file.txt")
        message_data = {
            "id": "attachment-test",
            "hasAttachments": True,
            "attachments": [attachment]
        }
        
        message = Message(**message_data)
        
        assert len(message.attachments) == 1
        assert message.attachments[0].id == "att-1"
        assert message.hasAttachments is True

    def test_message_from_field_alias(self):
        """Test Message 'from' field alias handling."""
        from_recipient = Recipient(emailAddress=EmailAddress(address="from@example.com"))
        message_data = {
            "id": "from-test",
            "from": from_recipient
        }
        
        message = Message(**message_data)
        
        assert message.from_ == from_recipient
        assert message.from_.emailAddress.address == "from@example.com"


class TestMailFolder:
    """Test cases for MailFolder model."""

    def test_mail_folder_valid_data_creates_instance(self):
        """Test that valid data creates MailFolder instance."""
        folder_data = {
            "id": "folder-123",
            "displayName": "Important Emails",
            "parentFolderId": "parent-456",
            "childFolderCount": 3,
            "unreadItemCount": 15,
            "totalItemCount": 50,
            "isHidden": False
        }
        
        folder = MailFolder(**folder_data)
        
        assert folder.id == "folder-123"
        assert folder.displayName == "Important Emails"
        assert folder.parentFolderId == "parent-456"
        assert folder.childFolderCount == 3
        assert folder.unreadItemCount == 15
        assert folder.totalItemCount == 50
        assert folder.isHidden is False

    def test_mail_folder_minimal_data(self):
        """Test MailFolder with minimal required data."""
        folder = MailFolder(id="minimal-folder", displayName="Minimal")
        
        assert folder.id == "minimal-folder"
        assert folder.displayName == "Minimal"
        assert folder.childFolderCount == 0  # Default
        assert folder.unreadItemCount == 0   # Default
        assert folder.totalItemCount == 0    # Default
        assert folder.isHidden is False      # Default


class TestVoiceAttachmentModels:
    """Test cases for voice attachment models."""

    def test_voice_attachment_model(self):
        """Test VoiceAttachment model."""
        voice_data = {
            "messageId": "msg-123",
            "attachmentId": "att-456",
            "name": "voicemail.m4a",
            "contentType": "audio/m4a",
            "size": 512000,
            "duration": 30.5,
            "sampleRate": 44100,
            "bitRate": 128
        }
        
        voice_attachment = VoiceAttachment(**voice_data)
        
        assert voice_attachment.messageId == "msg-123"
        assert voice_attachment.attachmentId == "att-456"
        assert voice_attachment.name == "voicemail.m4a"
        assert voice_attachment.duration == 30.5
        assert voice_attachment.sampleRate == 44100

    def test_stored_voice_attachment_model(self):
        """Test StoredVoiceAttachment model."""
        stored_data = {
            "id": "stored-123",
            "blob_name": "voice_123456.m4a",
            "original_filename": "recording.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024000,
            "size_mb": 1.024,
            "duration_seconds": 45,
            "sender_email": "sender@example.com",
            "sender_name": "John Sender",
            "subject": "Voice message for you",
            "received_at": "2023-01-15T10:30:00Z",
            "stored_at": "2023-01-15T10:35:00Z",
            "download_count": 3,
            "last_downloaded_at": "2023-01-16T09:00:00Z"
        }
        
        stored_voice = StoredVoiceAttachment(**stored_data)
        
        assert stored_voice.id == "stored-123"
        assert stored_voice.blob_name == "voice_123456.m4a"
        assert stored_voice.size_mb == 1.024
        assert stored_voice.duration_seconds == 45
        assert stored_voice.download_count == 3

    def test_stored_voice_attachment_list_model(self):
        """Test StoredVoiceAttachmentList model."""
        attachment1 = StoredVoiceAttachment(
            id="1", blob_name="voice1.m4a", original_filename="v1.m4a",
            content_type="audio/m4a", size_bytes=1000, size_mb=0.001,
            sender_email="test@example.com", subject="Test", 
            received_at="2023-01-15T10:00:00Z", stored_at="2023-01-15T10:01:00Z"
        )
        
        list_data = {
            "attachments": [attachment1],
            "pagination": {"page": 1, "per_page": 10, "total": 1}
        }
        
        attachment_list = StoredVoiceAttachmentList(**list_data)
        
        assert len(attachment_list.attachments) == 1
        assert attachment_list.pagination["page"] == 1


class TestRequestResponseModels:
    """Test cases for request/response models."""

    def test_create_folder_request_model(self):
        """Test CreateFolderRequest model."""
        request_data = {
            "displayName": "New Folder",
            "parentFolderId": "parent-123"
        }
        
        create_request = CreateFolderRequest(**request_data)
        
        assert create_request.displayName == "New Folder"
        assert create_request.parentFolderId == "parent-123"

    def test_create_folder_request_validation(self):
        """Test CreateFolderRequest validation."""
        # Test minimum length
        with pytest.raises(ValidationError):
            CreateFolderRequest(displayName="")
        
        # Test maximum length
        long_name = "x" * 256
        with pytest.raises(ValidationError):
            CreateFolderRequest(displayName=long_name)

    def test_move_message_request_model(self):
        """Test MoveMessageRequest model."""
        move_request = MoveMessageRequest(destinationId="folder-456")
        
        assert move_request.destinationId == "folder-456"

    def test_update_message_request_model(self):
        """Test UpdateMessageRequest model."""
        update_data = {
            "isRead": True,
            "importance": Importance.HIGH
        }
        
        update_request = UpdateMessageRequest(**update_data)
        
        assert update_request.isRead is True
        assert update_request.importance == Importance.HIGH

    def test_update_message_request_optional_fields(self):
        """Test UpdateMessageRequest with optional fields."""
        update_request = UpdateMessageRequest()
        
        assert update_request.isRead is None
        assert update_request.importance is None

    def test_message_list_response_model(self):
        """Test MessageListResponse model."""
        message = Message(id="msg-1")
        response_data = {
            "value": [message],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages?$skip=10",
            "@odata.count": 100
        }
        
        list_response = MessageListResponse(**response_data)
        
        assert len(list_response.value) == 1
        assert list_response.odata_nextLink == "https://graph.microsoft.com/v1.0/me/messages?$skip=10"
        assert list_response.odata_count == 100


class TestStatisticsModels:
    """Test cases for statistics models."""

    def test_folder_statistics_model(self):
        """Test FolderStatistics model."""
        stats_data = {
            "folderId": "folder-123",
            "folderName": "Important",
            "totalMessages": 100,
            "unreadMessages": 25,
            "messagesWithAttachments": 15,
            "voiceMessages": 8,
            "totalAttachmentSize": 5000000
        }
        
        folder_stats = FolderStatistics(**stats_data)
        
        assert folder_stats.folderId == "folder-123"
        assert folder_stats.totalMessages == 100
        assert folder_stats.unreadMessages == 25
        assert folder_stats.voiceMessages == 8

    def test_voice_attachment_storage_statistics_model(self):
        """Test VoiceAttachmentStorageStatistics model."""
        stats_data = {
            "total_attachments": 50,
            "stored_attachments": 45,
            "deleted_attachments": 5,
            "total_size_bytes": 100000000,
            "total_size_mb": 95.37,
            "total_downloads": 150,
            "average_size_bytes": 2000000.0,
            "average_size_mb": 1.907,
            "content_types": {
                "audio/m4a": {"count": 30, "size_mb": 60.0},
                "audio/wav": {"count": 15, "size_mb": 35.37}
            }
        }
        
        storage_stats = VoiceAttachmentStorageStatistics(**stats_data)
        
        assert storage_stats.total_attachments == 50
        assert storage_stats.stored_attachments == 45
        assert storage_stats.total_size_mb == 95.37
        assert len(storage_stats.content_types) == 2

    def test_voice_attachment_cleanup_stats_model(self):
        """Test VoiceAttachmentCleanupStats model."""
        cleanup_data = {
            "expired_found": 10,
            "blobs_deleted": 8,
            "database_updated": 8,
            "errors": 2,
            "error_details": ["Blob not found", "Access denied"],
            "dry_run": False
        }
        
        cleanup_stats = VoiceAttachmentCleanupStats(**cleanup_data)
        
        assert cleanup_stats.expired_found == 10
        assert cleanup_stats.blobs_deleted == 8
        assert cleanup_stats.errors == 2
        assert len(cleanup_stats.error_details) == 2
        assert cleanup_stats.dry_run is False


class TestOrganizationModels:
    """Test cases for organization models."""

    def test_organize_voice_request_model(self):
        """Test OrganizeVoiceRequest model."""
        request_data = {
            "targetFolderName": "Audio Messages",
            "createFolder": False,
            "includeSubfolders": True
        }
        
        organize_request = OrganizeVoiceRequest(**request_data)
        
        assert organize_request.targetFolderName == "Audio Messages"
        assert organize_request.createFolder is False
        assert organize_request.includeSubfolders is True

    def test_organize_voice_request_defaults(self):
        """Test OrganizeVoiceRequest default values."""
        organize_request = OrganizeVoiceRequest()
        
        assert organize_request.targetFolderName == "Voice Messages"  # Default
        assert organize_request.createFolder is True                  # Default
        assert organize_request.includeSubfolders is False            # Default

    def test_organize_voice_response_model(self):
        """Test OrganizeVoiceResponse model."""
        response_data = {
            "messagesProcessed": 50,
            "messagesMoved": 25,
            "voiceAttachmentsFound": 30,
            "folderCreated": True,
            "targetFolderId": "folder-voice-123",
            "errors": ["Failed to move message msg-456"]
        }
        
        organize_response = OrganizeVoiceResponse(**response_data)
        
        assert organize_response.messagesProcessed == 50
        assert organize_response.messagesMoved == 25
        assert organize_response.folderCreated is True
        assert len(organize_response.errors) == 1


class TestSearchModels:
    """Test cases for search models."""

    def test_search_messages_request_model(self):
        """Test SearchMessagesRequest model."""
        search_data = {
            "query": "important meeting",
            "folderId": "folder-123",
            "hasAttachments": True,
            "hasVoiceAttachments": False,
            "dateFrom": datetime(2023, 1, 1),
            "dateTo": datetime(2023, 12, 31),
            "importance": Importance.HIGH,
            "isRead": False,
            "top": 50,
            "skip": 10
        }
        
        search_request = SearchMessagesRequest(**search_data)
        
        assert search_request.query == "important meeting"
        assert search_request.folderId == "folder-123"
        assert search_request.hasAttachments is True
        assert search_request.importance == Importance.HIGH
        assert search_request.top == 50
        assert search_request.skip == 10

    def test_search_messages_request_validation(self):
        """Test SearchMessagesRequest validation."""
        # Test minimum query length
        with pytest.raises(ValidationError):
            SearchMessagesRequest(query="")
        
        # Test top parameter bounds
        with pytest.raises(ValidationError):
            SearchMessagesRequest(query="test", top=0)
        
        with pytest.raises(ValidationError):
            SearchMessagesRequest(query="test", top=1001)
        
        # Test skip parameter bounds
        with pytest.raises(ValidationError):
            SearchMessagesRequest(query="test", skip=-1)

    def test_attachment_filter_model(self):
        """Test AttachmentFilter model."""
        filter_data = {
            "contentTypes": ["audio/m4a", "audio/wav"],
            "hasVoiceAttachments": True,
            "minSize": 1000,
            "maxSize": 10000000
        }
        
        attachment_filter = AttachmentFilter(**filter_data)
        
        assert len(attachment_filter.contentTypes) == 2
        assert attachment_filter.hasVoiceAttachments is True
        assert attachment_filter.minSize == 1000
        assert attachment_filter.maxSize == 10000000


class TestModelIntegration:
    """Integration tests for mail model interactions."""

    def test_complete_email_message_structure(self):
        """Test complete email message with all components."""
        # Create nested structure
        sender = Recipient(emailAddress=EmailAddress(name="John Sender", address="john@example.com"))
        recipient = Recipient(emailAddress=EmailAddress(name="Jane Recipient", address="jane@example.com"))
        body = ItemBody(contentType=BodyType.HTML, content="<p>Email content</p>")
        attachment = FileAttachment(
            id="att-1", name="document.pdf", contentType="application/pdf", 
            size=2048, contentBytes="base64content=="
        )
        
        message = Message(
            id="complete-message",
            subject="Complete Test Email",
            body=body,
            sender=sender,
            toRecipients=[recipient],
            hasAttachments=True,
            attachments=[attachment],
            importance=Importance.HIGH,
            receivedDateTime=datetime.utcnow()
        )
        
        # Verify complete structure
        assert message.sender.emailAddress.name == "John Sender"
        assert message.toRecipients[0].emailAddress.address == "jane@example.com"
        assert message.body.contentType == BodyType.HTML
        assert message.attachments[0].contentBytes == "base64content=="
        assert message.importance == Importance.HIGH

    def test_voice_attachment_workflow(self):
        """Test complete voice attachment workflow models."""
        # 1. Voice attachment detected
        voice_attachment = VoiceAttachment(
            messageId="msg-voice-123",
            attachmentId="att-voice-456",
            name="recording.m4a",
            contentType="audio/m4a",
            size=1024000,
            duration=30.0
        )
        
        # 2. Store request
        store_request = StoreVoiceAttachmentRequest(
            sender_name="Voice Sender",
            subject="Voice Message",
            received_at="2023-01-15T10:00:00Z"
        )
        
        # 3. Store response
        store_response = StoreVoiceAttachmentResponse(
            success=True,
            message="Voice attachment stored successfully",
            blob_name="voice_123456.m4a",
            message_id="msg-voice-123",
            attachment_id="att-voice-456"
        )
        
        # 4. Stored attachment record
        stored_attachment = StoredVoiceAttachment(
            id="stored-789",
            blob_name="voice_123456.m4a",
            original_filename="recording.m4a",
            content_type="audio/m4a",
            size_bytes=1024000,
            size_mb=1.024,
            sender_email="sender@example.com",
            subject="Voice Message",
            received_at="2023-01-15T10:00:00Z",
            stored_at="2023-01-15T10:01:00Z"
        )
        
        # Verify workflow consistency
        assert voice_attachment.name == "recording.m4a"
        assert store_response.blob_name == stored_attachment.blob_name
        assert voice_attachment.size == stored_attachment.size_bytes
        assert store_request.subject == "Voice Message"

    def test_folder_organization_workflow(self):
        """Test folder organization workflow with statistics."""
        # 1. Organize request
        organize_request = OrganizeVoiceRequest(
            targetFolderName="Voice Recordings",
            createFolder=True,
            includeSubfolders=True
        )
        
        # 2. Organize response
        organize_response = OrganizeVoiceResponse(
            messagesProcessed=100,
            messagesMoved=25,
            voiceAttachmentsFound=30,
            folderCreated=True,
            targetFolderId="folder-voice-new",
            errors=[]
        )
        
        # 3. Folder statistics
        folder_stats = FolderStatistics(
            folderId="folder-voice-new",
            folderName="Voice Recordings",
            totalMessages=25,
            unreadMessages=10,
            voiceMessages=25,  # All messages have voice
            messagesWithAttachments=25
        )
        
        # Verify consistency
        assert organize_request.targetFolderName == folder_stats.folderName
        assert organize_response.messagesMoved == folder_stats.totalMessages
        assert organize_response.targetFolderId == folder_stats.folderId


class TestModelValidationEdgeCases:
    """Test edge cases and validation scenarios."""

    @pytest.mark.parametrize("size_value", [
        0, 1, 1000, 1000000, 2**31 - 1
    ])
    def test_attachment_size_validation(self, size_value):
        """Test attachment size validation with various values."""
        attachment = Attachment(id="size-test", name="test.txt", size=size_value)
        assert attachment.size == size_value

    def test_datetime_field_handling(self):
        """Test datetime field handling in messages."""
        now = datetime.utcnow()
        message = Message(
            id="datetime-test",
            receivedDateTime=now,
            sentDateTime=now,
            createdDateTime=now,
            lastModifiedDateTime=now
        )
        
        assert message.receivedDateTime == now
        assert message.sentDateTime == now
        assert message.createdDateTime == now
        assert message.lastModifiedDateTime == now

    def test_list_fields_default_behavior(self):
        """Test list fields default to empty lists."""
        message = Message(id="list-test")
        
        assert message.toRecipients == []
        assert message.ccRecipients == []
        assert message.bccRecipients == []
        assert message.attachments == []
        
        organize_response = OrganizeVoiceResponse(targetFolderId="test")
        assert organize_response.errors == []

    def test_optional_fields_none_values(self):
        """Test optional fields can be None."""
        message = Message(id="none-test")
        
        assert message.body is None
        assert message.sender is None
        assert message.parentFolderId is None
        assert message.conversationId is None
        
        attachment = Attachment(id="none-att", name="test.txt")
        assert attachment.contentType is None
        assert attachment.lastModifiedDateTime is None

    def test_string_enum_validation(self):
        """Test string enum validation."""
        # Valid enum values
        body = ItemBody(contentType=BodyType.TEXT)
        assert body.contentType == "text"
        
        # Test with string value
        body_dict = {"contentType": "html", "content": "test"}
        body = ItemBody(**body_dict)
        assert body.contentType == BodyType.HTML