"""
test_SharedMailboxModel.py - Unit tests for shared mailbox Pydantic models

Tests all shared mailbox models in app.models.SharedMailboxModel including:
- Enums: SharedMailboxAccessLevel, SharedMailboxType, DelegationType
- Core models: SharedMailbox, SharedMailboxPermission, SharedMailboxAccess
- Extended models: SharedMailboxMessage, SharedMailboxStatistics
- Request models: CreateSharedMailboxRequest, UpdateSharedMailboxRequest, etc.
- Permission models: GrantPermissionRequest, RevokePermissionRequest
- Communication models: SendAsSharedRequest
- Search models: SharedMailboxSearchRequest, SharedMailboxSearchResponse
- Organization models: OrganizeSharedMailboxRequest, OrganizeSharedMailboxResponse
- Audit models: SharedMailboxAuditEntry

Tests include validation, serialization, field constraints, default values, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pydantic import ValidationError

from app.models.SharedMailboxModel import (
    # Enums
    SharedMailboxAccessLevel, SharedMailboxType, DelegationType,
    # Core models
    SharedMailbox, SharedMailboxPermission, SharedMailboxAccess, SharedMailboxMessage,
    # Request models
    CreateSharedMailboxRequest, UpdateSharedMailboxRequest,
    GrantPermissionRequest, RevokePermissionRequest, SendAsSharedRequest,
    SharedMailboxAccessRequest,
    # Search models
    SharedMailboxSearchRequest, SharedMailboxSearchResponse,
    # Organization models
    OrganizeSharedMailboxRequest, OrganizeSharedMailboxResponse,
    # Statistics and list models
    SharedMailboxStatistics, SharedMailboxListResponse,
    # Audit model
    SharedMailboxAuditEntry
)
from app.models.MailModel import EmailAddress, Recipient


class TestEnums:
    """Test cases for shared mailbox enums."""

    def test_shared_mailbox_access_level_enum_values(self):
        """Test SharedMailboxAccessLevel enum has correct values."""
        assert SharedMailboxAccessLevel.OWNER == "owner"
        assert SharedMailboxAccessLevel.EDITOR == "editor"
        assert SharedMailboxAccessLevel.AUTHOR == "author"
        assert SharedMailboxAccessLevel.REVIEWER == "reviewer"
        assert SharedMailboxAccessLevel.CONTRIBUTOR == "contributor"
        assert SharedMailboxAccessLevel.NONE == "none"
        
        # Test all members
        assert len(list(SharedMailboxAccessLevel)) == 6

    def test_shared_mailbox_type_enum_values(self):
        """Test SharedMailboxType enum has correct values."""
        assert SharedMailboxType.SHARED == "shared"
        assert SharedMailboxType.RESOURCE == "resource"
        assert SharedMailboxType.EQUIPMENT == "equipment"
        assert SharedMailboxType.ROOM == "room"
        
        # Test all members
        assert len(list(SharedMailboxType)) == 4

    def test_delegation_type_enum_values(self):
        """Test DelegationType enum has correct values."""
        assert DelegationType.SEND_AS == "sendAs"
        assert DelegationType.SEND_ON_BEHALF == "sendOnBehalf"
        assert DelegationType.FULL_ACCESS == "fullAccess"
        assert DelegationType.READ_ONLY == "readOnly"
        
        # Test all members
        assert len(list(DelegationType)) == 4

    @pytest.mark.parametrize("enum_class,expected_count", [
        (SharedMailboxAccessLevel, 6),
        (SharedMailboxType, 4),
        (DelegationType, 4),
    ])
    def test_enum_member_counts(self, enum_class, expected_count):
        """Test that enums have expected member counts."""
        assert len(list(enum_class)) == expected_count


class TestSharedMailbox:
    """Test cases for SharedMailbox model."""

    def test_shared_mailbox_valid_data_creates_instance(self):
        """Test that valid data creates SharedMailbox instance."""
        mailbox_data = {
            "id": "mailbox-123",
            "displayName": "Sales Team",
            "emailAddress": "sales@example.com",
            "aliases": ["sales-team@example.com", "sales-support@example.com"],
            "mailboxType": SharedMailboxType.SHARED,
            "isActive": True,
            "description": "Main sales team communication",
            "createdDateTime": datetime(2023, 1, 15, 10, 0, 0),
            "department": "Sales",
            "companyName": "Acme Corp"
        }
        
        mailbox = SharedMailbox(**mailbox_data)
        
        assert mailbox.id == "mailbox-123"
        assert mailbox.displayName == "Sales Team"
        assert mailbox.emailAddress == "sales@example.com"
        assert len(mailbox.aliases) == 2
        assert mailbox.mailboxType == SharedMailboxType.SHARED
        assert mailbox.department == "Sales"

    def test_shared_mailbox_minimal_required_data(self):
        """Test SharedMailbox with minimal required data."""
        mailbox = SharedMailbox(
            id="minimal-123",
            displayName="Minimal Mailbox",
            emailAddress="minimal@example.com"
        )
        
        assert mailbox.id == "minimal-123"
        assert mailbox.displayName == "Minimal Mailbox"
        assert mailbox.aliases == []  # Default
        assert mailbox.mailboxType == SharedMailboxType.SHARED  # Default
        assert mailbox.isActive is True  # Default
        assert mailbox.description is None  # Default

    def test_shared_mailbox_resource_type(self):
        """Test SharedMailbox with resource type configuration."""
        mailbox_data = {
            "id": "conference-room-1",
            "displayName": "Conference Room A",
            "emailAddress": "conference-a@example.com",
            "mailboxType": SharedMailboxType.ROOM,
            "resourceCapacity": 10,
            "location": "Building 1, Floor 2",
            "phone": "+1-555-0123"
        }
        
        mailbox = SharedMailbox(**mailbox_data)
        
        assert mailbox.mailboxType == SharedMailboxType.ROOM
        assert mailbox.resourceCapacity == 10
        assert mailbox.location == "Building 1, Floor 2"

    def test_shared_mailbox_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        # Test missing id
        with pytest.raises(ValidationError) as exc_info:
            SharedMailbox(displayName="Test", emailAddress="test@example.com")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("id",) for error in errors)

        # Test missing displayName
        with pytest.raises(ValidationError) as exc_info:
            SharedMailbox(id="test-123", emailAddress="test@example.com")
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("displayName",) for error in errors)


class TestSharedMailboxPermission:
    """Test cases for SharedMailboxPermission model."""

    def test_shared_mailbox_permission_valid_data_creates_instance(self):
        """Test that valid data creates SharedMailboxPermission instance."""
        permission_data = {
            "mailboxId": "mailbox-456",
            "userId": "user-789",
            "userPrincipalName": "john.doe@example.com",
            "displayName": "John Doe",
            "accessLevel": SharedMailboxAccessLevel.EDITOR,
            "delegationType": [DelegationType.SEND_AS, DelegationType.FULL_ACCESS],
            "grantedDate": datetime(2023, 1, 10, 9, 0, 0),
            "grantedBy": "admin@example.com",
            "isInherited": False,
            "expiresOn": datetime(2023, 12, 31, 23, 59, 59)
        }
        
        permission = SharedMailboxPermission(**permission_data)
        
        assert permission.mailboxId == "mailbox-456"
        assert permission.userId == "user-789"
        assert permission.accessLevel == SharedMailboxAccessLevel.EDITOR
        assert len(permission.delegationType) == 2
        assert DelegationType.SEND_AS in permission.delegationType
        assert permission.isInherited is False

    def test_shared_mailbox_permission_minimal_data(self):
        """Test SharedMailboxPermission with minimal required data."""
        permission = SharedMailboxPermission(
            mailboxId="minimal-mailbox",
            userId="minimal-user",
            userPrincipalName="minimal@example.com",
            displayName="Minimal User",
            accessLevel=SharedMailboxAccessLevel.REVIEWER
        )
        
        assert permission.delegationType == []  # Default
        assert permission.isInherited is False  # Default
        assert permission.grantedDate is None   # Default
        assert permission.expiresOn is None     # Default

    @pytest.mark.parametrize("access_level", [
        SharedMailboxAccessLevel.OWNER,
        SharedMailboxAccessLevel.EDITOR,
        SharedMailboxAccessLevel.AUTHOR,
        SharedMailboxAccessLevel.REVIEWER,
        SharedMailboxAccessLevel.CONTRIBUTOR,
        SharedMailboxAccessLevel.NONE
    ])
    def test_shared_mailbox_permission_various_access_levels(self, access_level):
        """Test SharedMailboxPermission with various access levels."""
        permission = SharedMailboxPermission(
            mailboxId="test-mailbox",
            userId="test-user",
            userPrincipalName="test@example.com",
            displayName="Test User",
            accessLevel=access_level
        )
        
        assert permission.accessLevel == access_level


class TestSharedMailboxAccess:
    """Test cases for SharedMailboxAccess model."""

    def test_shared_mailbox_access_valid_data_creates_instance(self):
        """Test that valid data creates SharedMailboxAccess instance."""
        mailbox = SharedMailbox(
            id="access-mailbox",
            displayName="Access Test",
            emailAddress="access@example.com"
        )
        permission = SharedMailboxPermission(
            mailboxId="access-mailbox",
            userId="access-user",
            userPrincipalName="user@example.com",
            displayName="Access User",
            accessLevel=SharedMailboxAccessLevel.EDITOR
        )
        
        access_data = {
            "mailbox": mailbox,
            "permissions": [permission],
            "accessLevel": SharedMailboxAccessLevel.EDITOR,
            "canRead": True,
            "canWrite": True,
            "canSend": False,
            "canManage": False,
            "lastAccessed": datetime(2023, 1, 15, 14, 30, 0)
        }
        
        access = SharedMailboxAccess(**access_data)
        
        assert access.mailbox.id == "access-mailbox"
        assert len(access.permissions) == 1
        assert access.accessLevel == SharedMailboxAccessLevel.EDITOR
        assert access.canRead is True
        assert access.canWrite is True
        assert access.canSend is False
        assert access.canManage is False

    def test_shared_mailbox_access_owner_permissions(self):
        """Test SharedMailboxAccess with owner permissions."""
        mailbox = SharedMailbox(id="owner-test", displayName="Owner Test", emailAddress="owner@example.com")
        permission = SharedMailboxPermission(
            mailboxId="owner-test", userId="owner-user", userPrincipalName="owner@example.com",
            displayName="Owner User", accessLevel=SharedMailboxAccessLevel.OWNER
        )
        
        access = SharedMailboxAccess(
            mailbox=mailbox,
            permissions=[permission],
            accessLevel=SharedMailboxAccessLevel.OWNER,
            canRead=True,
            canWrite=True,
            canSend=True,
            canManage=True
        )
        
        # Owner should have all permissions
        assert access.canRead is True
        assert access.canWrite is True
        assert access.canSend is True
        assert access.canManage is True


class TestSharedMailboxMessage:
    """Test cases for SharedMailboxMessage model."""

    def test_shared_mailbox_message_extends_message_model(self):
        """Test that SharedMailboxMessage extends Message with additional fields."""
        message_data = {
            "id": "shared-message-123",
            "subject": "Shared Mailbox Test",
            "sharedMailboxId": "shared-123",
            "sharedMailboxName": "Test Shared",
            "sharedMailboxEmail": "shared@example.com",
            "onBehalfOf": "delegated-user@example.com",
            "delegatedBy": "admin@example.com"
        }
        
        shared_message = SharedMailboxMessage(**message_data)
        
        # Test Message inherited fields
        assert shared_message.id == "shared-message-123"
        assert shared_message.subject == "Shared Mailbox Test"
        
        # Test SharedMailboxMessage specific fields
        assert shared_message.sharedMailboxId == "shared-123"
        assert shared_message.sharedMailboxName == "Test Shared"
        assert shared_message.sharedMailboxEmail == "shared@example.com"
        assert shared_message.onBehalfOf == "delegated-user@example.com"

    def test_shared_mailbox_message_minimal_data(self):
        """Test SharedMailboxMessage with minimal required data."""
        shared_message = SharedMailboxMessage(
            id="minimal-shared",
            sharedMailboxId="minimal-mailbox",
            sharedMailboxName="Minimal",
            sharedMailboxEmail="minimal@example.com"
        )
        
        assert shared_message.onBehalfOf is None    # Optional
        assert shared_message.delegatedBy is None   # Optional


class TestRequestModels:
    """Test cases for request models."""

    def test_create_shared_mailbox_request_model(self):
        """Test CreateSharedMailboxRequest model."""
        request_data = {
            "displayName": "New Sales Team",
            "emailAddress": "newsales@example.com",
            "aliases": ["sales-new@example.com"],
            "mailboxType": SharedMailboxType.SHARED,
            "description": "New sales team mailbox",
            "location": "Office Building A",
            "phone": "+1-555-0199",
            "department": "Sales",
            "resourceCapacity": None
        }
        
        create_request = CreateSharedMailboxRequest(**request_data)
        
        assert create_request.displayName == "New Sales Team"
        assert create_request.emailAddress == "newsales@example.com"
        assert len(create_request.aliases) == 1
        assert create_request.department == "Sales"

    def test_create_shared_mailbox_request_validation(self):
        """Test CreateSharedMailboxRequest validation."""
        # Test minimum length for displayName
        with pytest.raises(ValidationError):
            CreateSharedMailboxRequest(displayName="", emailAddress="test@example.com")
        
        # Test maximum length for displayName
        long_name = "x" * 257
        with pytest.raises(ValidationError):
            CreateSharedMailboxRequest(displayName=long_name, emailAddress="test@example.com")
        
        # Test resource capacity validation
        with pytest.raises(ValidationError):
            CreateSharedMailboxRequest(
                displayName="Test", emailAddress="test@example.com", resourceCapacity=0
            )

    def test_update_shared_mailbox_request_model(self):
        """Test UpdateSharedMailboxRequest model."""
        update_data = {
            "displayName": "Updated Team Name",
            "description": "Updated description",
            "isActive": False
        }
        
        update_request = UpdateSharedMailboxRequest(**update_data)
        
        assert update_request.displayName == "Updated Team Name"
        assert update_request.description == "Updated description"
        assert update_request.isActive is False

    def test_grant_permission_request_model(self):
        """Test GrantPermissionRequest model."""
        grant_data = {
            "userPrincipalName": "newuser@example.com",
            "accessLevel": SharedMailboxAccessLevel.EDITOR,
            "delegationType": [DelegationType.SEND_AS],
            "expiresOn": datetime(2024, 12, 31, 23, 59, 59),
            "notify": True
        }
        
        grant_request = GrantPermissionRequest(**grant_data)
        
        assert grant_request.userPrincipalName == "newuser@example.com"
        assert grant_request.accessLevel == SharedMailboxAccessLevel.EDITOR
        assert DelegationType.SEND_AS in grant_request.delegationType
        assert grant_request.notify is True

    def test_revoke_permission_request_model(self):
        """Test RevokePermissionRequest model."""
        revoke_data = {
            "userPrincipalName": "revokeuser@example.com",
            "accessLevel": SharedMailboxAccessLevel.REVIEWER,
            "delegationType": [DelegationType.READ_ONLY],
            "notify": False
        }
        
        revoke_request = RevokePermissionRequest(**revoke_data)
        
        assert revoke_request.userPrincipalName == "revokeuser@example.com"
        assert revoke_request.accessLevel == SharedMailboxAccessLevel.REVIEWER
        assert revoke_request.notify is False

    def test_send_as_shared_request_model(self):
        """Test SendAsSharedRequest model."""
        send_data = {
            "to": ["recipient1@example.com", "recipient2@example.com"],
            "cc": ["cc@example.com"],
            "subject": "Test message from shared mailbox",
            "body": "<p>This is a test message</p>",
            "bodyType": "html",
            "importance": "high",
            "saveToSentItems": True,
            "requestReadReceipt": True
        }
        
        send_request = SendAsSharedRequest(**send_data)
        
        assert len(send_request.to) == 2
        assert len(send_request.cc) == 1
        assert send_request.subject == "Test message from shared mailbox"
        assert send_request.bodyType == "html"
        assert send_request.importance == "high"
        assert send_request.requestReadReceipt is True


class TestSearchModels:
    """Test cases for search models."""

    def test_shared_mailbox_search_request_model(self):
        """Test SharedMailboxSearchRequest model."""
        search_data = {
            "query": "quarterly report",
            "mailboxIds": ["mailbox-1", "mailbox-2"],
            "folderId": "inbox-folder",
            "hasAttachments": True,
            "hasVoiceAttachments": False,
            "dateFrom": datetime(2023, 1, 1),
            "dateTo": datetime(2023, 12, 31),
            "fromUsers": ["user1@example.com"],
            "importance": "high",
            "isRead": False,
            "top": 50,
            "skip": 10
        }
        
        search_request = SharedMailboxSearchRequest(**search_data)
        
        assert search_request.query == "quarterly report"
        assert len(search_request.mailboxIds) == 2
        assert search_request.hasAttachments is True
        assert search_request.top == 50
        assert search_request.skip == 10

    def test_shared_mailbox_search_request_validation(self):
        """Test SharedMailboxSearchRequest validation."""
        # Test minimum query length
        with pytest.raises(ValidationError):
            SharedMailboxSearchRequest(query="")
        
        # Test top parameter bounds
        with pytest.raises(ValidationError):
            SharedMailboxSearchRequest(query="test", top=0)
        
        with pytest.raises(ValidationError):
            SharedMailboxSearchRequest(query="test", top=101)

    def test_shared_mailbox_search_response_model(self):
        """Test SharedMailboxSearchResponse model."""
        response_data = {
            "query": "test search",
            "totalResults": 25,
            "searchedMailboxes": ["mailbox-1", "mailbox-2"],
            "results": [
                {"mailboxId": "mailbox-1", "messages": []},
                {"mailboxId": "mailbox-2", "messages": []}
            ],
            "executionTimeMs": 150
        }
        
        search_response = SharedMailboxSearchResponse(**response_data)
        
        assert search_response.query == "test search"
        assert search_response.totalResults == 25
        assert len(search_response.searchedMailboxes) == 2
        assert search_response.executionTimeMs == 150


class TestOrganizationModels:
    """Test cases for organization models."""

    def test_organize_shared_mailbox_request_model(self):
        """Test OrganizeSharedMailboxRequest model."""
        organize_data = {
            "targetFolderName": "Audio Messages",
            "createFolder": True,
            "messageType": "voice",
            "includeSubfolders": True,
            "preserveReadStatus": False
        }
        
        organize_request = OrganizeSharedMailboxRequest(**organize_data)
        
        assert organize_request.targetFolderName == "Audio Messages"
        assert organize_request.createFolder is True
        assert organize_request.messageType == "voice"
        assert organize_request.preserveReadStatus is False

    def test_organize_shared_mailbox_request_defaults(self):
        """Test OrganizeSharedMailboxRequest default values."""
        organize_request = OrganizeSharedMailboxRequest()
        
        assert organize_request.targetFolderName == "Voice Messages"  # Default
        assert organize_request.createFolder is True                  # Default
        assert organize_request.messageType == "voice"                # Default
        assert organize_request.includeSubfolders is False            # Default
        assert organize_request.preserveReadStatus is True            # Default

    def test_organize_shared_mailbox_response_model(self):
        """Test OrganizeSharedMailboxResponse model."""
        response_data = {
            "mailboxId": "organized-mailbox",
            "mailboxName": "Organized Mailbox",
            "messagesProcessed": 100,
            "messagesMoved": 75,
            "foldersCreated": 1,
            "targetFolderId": "voice-folder-123",
            "processingTimeMs": 2500,
            "errors": ["Failed to move message msg-999"]
        }
        
        organize_response = OrganizeSharedMailboxResponse(**response_data)
        
        assert organize_response.mailboxId == "organized-mailbox"
        assert organize_response.messagesProcessed == 100
        assert organize_response.messagesMoved == 75
        assert organize_response.foldersCreated == 1
        assert len(organize_response.errors) == 1


class TestStatisticsModels:
    """Test cases for statistics models."""

    def test_shared_mailbox_statistics_model(self):
        """Test SharedMailboxStatistics model."""
        stats_data = {
            "mailboxId": "stats-mailbox",
            "mailboxName": "Statistics Test",
            "emailAddress": "stats@example.com",
            "totalMessages": 500,
            "unreadMessages": 50,
            "messagesWithAttachments": 100,
            "voiceMessages": 25,
            "totalFolders": 15,
            "mailboxSizeMB": 250.5,
            "lastMessageDate": datetime(2023, 12, 15, 14, 30, 0),
            "mostActiveUsers": [
                {"user": "user1@example.com", "messageCount": 50},
                {"user": "user2@example.com", "messageCount": 30}
            ],
            "dailyMessageCounts": {"2023-12-15": 10, "2023-12-14": 8},
            "attachmentStatistics": {"totalSize": 100000000, "averageSize": 200000}
        }
        
        mailbox_stats = SharedMailboxStatistics(**stats_data)
        
        assert mailbox_stats.mailboxId == "stats-mailbox"
        assert mailbox_stats.totalMessages == 500
        assert mailbox_stats.voiceMessages == 25
        assert mailbox_stats.mailboxSizeMB == 250.5
        assert len(mailbox_stats.mostActiveUsers) == 2
        assert len(mailbox_stats.dailyMessageCounts) == 2

    def test_shared_mailbox_list_response_model(self):
        """Test SharedMailboxListResponse model."""
        mailbox1 = SharedMailbox(id="mb1", displayName="Mailbox 1", emailAddress="mb1@example.com")
        mailbox2 = SharedMailbox(id="mb2", displayName="Mailbox 2", emailAddress="mb2@example.com")
        
        list_data = {
            "value": [mailbox1, mailbox2],
            "totalCount": 10,
            "accessibleCount": 2,
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/mailboxes?$skip=10"
        }
        
        list_response = SharedMailboxListResponse(**list_data)
        
        assert len(list_response.value) == 2
        assert list_response.totalCount == 10
        assert list_response.accessibleCount == 2
        assert list_response.odata_nextLink is not None


class TestAuditModel:
    """Test cases for audit model."""

    def test_shared_mailbox_audit_entry_model(self):
        """Test SharedMailboxAuditEntry model."""
        audit_data = {
            "mailboxId": "audit-mailbox",
            "mailboxName": "Audit Test Mailbox",
            "userId": "audit-user",
            "userPrincipalName": "audit@example.com",
            "action": "READ_MESSAGE",
            "details": {"messageId": "msg-123", "folder": "Inbox"},
            "timestamp": datetime(2023, 12, 15, 10, 30, 0),
            "ipAddress": "192.168.1.100",
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "success": True,
            "errorMessage": None
        }
        
        audit_entry = SharedMailboxAuditEntry(**audit_data)
        
        assert audit_entry.mailboxId == "audit-mailbox"
        assert audit_entry.action == "READ_MESSAGE"
        assert audit_entry.details["messageId"] == "msg-123"
        assert audit_entry.success is True
        assert audit_entry.errorMessage is None

    def test_shared_mailbox_audit_entry_defaults(self):
        """Test SharedMailboxAuditEntry with default values."""
        audit_entry = SharedMailboxAuditEntry(
            mailboxId="default-test",
            mailboxName="Default Test",
            userId="default-user",
            userPrincipalName="default@example.com",
            action="LOGIN"
        )
        
        assert audit_entry.details == {}  # Default
        assert audit_entry.success is True  # Default
        assert isinstance(audit_entry.timestamp, datetime)  # Auto-generated

    def test_shared_mailbox_audit_entry_failed_action(self):
        """Test SharedMailboxAuditEntry for failed action."""
        audit_entry = SharedMailboxAuditEntry(
            mailboxId="fail-test",
            mailboxName="Fail Test",
            userId="fail-user",
            userPrincipalName="fail@example.com",
            action="DELETE_MESSAGE",
            success=False,
            errorMessage="Insufficient permissions"
        )
        
        assert audit_entry.success is False
        assert audit_entry.errorMessage == "Insufficient permissions"


class TestModelIntegration:
    """Integration tests for shared mailbox model interactions."""

    def test_complete_shared_mailbox_workflow(self):
        """Test complete shared mailbox workflow with all models."""
        # 1. Create shared mailbox
        create_request = CreateSharedMailboxRequest(
            displayName="Integration Test Mailbox",
            emailAddress="integration@example.com",
            aliases=["int-test@example.com"],
            description="Integration testing mailbox"
        )
        
        # 2. Created mailbox
        mailbox = SharedMailbox(
            id="integration-123",
            displayName=create_request.displayName,
            emailAddress=create_request.emailAddress,
            aliases=create_request.aliases,
            description=create_request.description
        )
        
        # 3. Grant permission
        grant_request = GrantPermissionRequest(
            userPrincipalName="testuser@example.com",
            accessLevel=SharedMailboxAccessLevel.EDITOR,
            delegationType=[DelegationType.SEND_AS]
        )
        
        # 4. Permission record
        permission = SharedMailboxPermission(
            mailboxId=mailbox.id,
            userId="test-user-id",
            userPrincipalName=grant_request.userPrincipalName,
            displayName="Test User",
            accessLevel=grant_request.accessLevel,
            delegationType=grant_request.delegationType
        )
        
        # 5. Access details
        access = SharedMailboxAccess(
            mailbox=mailbox,
            permissions=[permission],
            accessLevel=SharedMailboxAccessLevel.EDITOR,
            canRead=True,
            canWrite=True,
            canSend=True,
            canManage=False
        )
        
        # Verify workflow consistency
        assert mailbox.displayName == create_request.displayName
        assert permission.accessLevel == grant_request.accessLevel
        assert access.mailbox.id == mailbox.id
        assert access.canSend is True  # Editor with send_as should be able to send

    def test_shared_mailbox_message_handling(self):
        """Test shared mailbox message handling workflow."""
        # 1. Shared mailbox
        mailbox = SharedMailbox(
            id="message-mailbox",
            displayName="Message Test",
            emailAddress="messages@example.com"
        )
        
        # 2. Message in shared mailbox
        shared_message = SharedMailboxMessage(
            id="shared-msg-123",
            subject="Test message in shared mailbox",
            sharedMailboxId=mailbox.id,
            sharedMailboxName=mailbox.displayName,
            sharedMailboxEmail=mailbox.emailAddress,
            onBehalfOf="delegate@example.com"
        )
        
        # 3. Send as shared mailbox
        send_request = SendAsSharedRequest(
            to=["recipient@example.com"],
            subject="Reply from shared mailbox",
            body="This is a reply from the shared mailbox"
        )
        
        # Verify message context
        assert shared_message.sharedMailboxId == mailbox.id
        assert shared_message.sharedMailboxEmail == mailbox.emailAddress
        assert send_request.to == ["recipient@example.com"]

    def test_shared_mailbox_search_and_organization(self):
        """Test shared mailbox search and organization workflow."""
        # 1. Search request
        search_request = SharedMailboxSearchRequest(
            query="voice messages",
            mailboxIds=["search-mailbox-1", "search-mailbox-2"],
            hasVoiceAttachments=True,
            top=25
        )
        
        # 2. Search results
        search_response = SharedMailboxSearchResponse(
            query=search_request.query,
            totalResults=15,
            searchedMailboxes=search_request.mailboxIds,
            results=[{"mailboxId": "search-mailbox-1", "messageCount": 10}],
            executionTimeMs=200
        )
        
        # 3. Organization request based on search
        organize_request = OrganizeSharedMailboxRequest(
            targetFolderName="Found Voice Messages",
            messageType="voice",
            createFolder=True
        )
        
        # 4. Organization results
        organize_response = OrganizeSharedMailboxResponse(
            mailboxId="search-mailbox-1",
            mailboxName="Search Mailbox 1",
            messagesProcessed=search_response.totalResults,
            messagesMoved=12,
            foldersCreated=1,
            targetFolderId="voice-folder-new",
            processingTimeMs=1500,
            errors=[]
        )
        
        # Verify workflow consistency
        assert search_response.query == search_request.query
        assert organize_response.messagesProcessed == search_response.totalResults
        assert organize_response.foldersCreated == 1


class TestModelValidationEdgeCases:
    """Test edge cases and validation scenarios."""

    def test_string_length_validations(self):
        """Test string field length validations."""
        # Test CreateSharedMailboxRequest field lengths
        with pytest.raises(ValidationError):
            CreateSharedMailboxRequest(
                displayName="Test",
                emailAddress="test@example.com",
                description="x" * 1025  # Exceeds max length
            )
        
        # Test valid max lengths
        long_description = "x" * 1024  # At max length
        request = CreateSharedMailboxRequest(
            displayName="Test",
            emailAddress="test@example.com",
            description=long_description
        )
        assert len(request.description) == 1024

    def test_resource_capacity_validation(self):
        """Test resource capacity validation."""
        # Valid capacity
        request = CreateSharedMailboxRequest(
            displayName="Conference Room",
            emailAddress="conference@example.com",
            resourceCapacity=10
        )
        assert request.resourceCapacity == 10
        
        # Invalid capacity (negative)
        with pytest.raises(ValidationError):
            CreateSharedMailboxRequest(
                displayName="Conference Room",
                emailAddress="conference@example.com",
                resourceCapacity=-1
            )

    def test_list_fields_default_behavior(self):
        """Test list fields default to empty lists."""
        mailbox = SharedMailbox(id="list-test", displayName="Test", emailAddress="test@example.com")
        assert mailbox.aliases == []
        
        permission = SharedMailboxPermission(
            mailboxId="test", userId="test", userPrincipalName="test@example.com",
            displayName="Test", accessLevel=SharedMailboxAccessLevel.REVIEWER
        )
        assert permission.delegationType == []
        
        audit_entry = SharedMailboxAuditEntry(
            mailboxId="test", mailboxName="Test", userId="test",
            userPrincipalName="test@example.com", action="TEST"
        )
        assert audit_entry.details == {}

    def test_datetime_field_handling(self):
        """Test datetime field handling in models."""
        now = datetime.utcnow()
        
        permission = SharedMailboxPermission(
            mailboxId="datetime-test",
            userId="datetime-user",
            userPrincipalName="datetime@example.com",
            displayName="DateTime User",
            accessLevel=SharedMailboxAccessLevel.EDITOR,
            grantedDate=now,
            expiresOn=now + timedelta(days=30)
        )
        
        assert permission.grantedDate == now
        assert permission.expiresOn == now + timedelta(days=30)

    def test_optional_fields_none_values(self):
        """Test optional fields can be None."""
        mailbox = SharedMailbox(id="none-test", displayName="None Test", emailAddress="none@example.com")
        
        assert mailbox.description is None
        assert mailbox.createdDateTime is None
        assert mailbox.location is None
        assert mailbox.phone is None
        assert mailbox.department is None