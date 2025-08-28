"""Mock factory for creating test objects and data.

This module provides factory patterns for creating consistent test data including:
- Database model factories
- API request/response factories  
- Azure service mock factories
- Test data builders
"""

import factory
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock
import uuid
import random
import string

from app.db.models.User import User
from app.db.models.MailAccount import MailAccount
from app.db.models.MailData import MailData
from app.db.models.VoiceAttachment import VoiceAttachment
from app.db.models.Operational import SystemSetting, AuditLog


class UserFactory(factory.Factory):
    """Factory for creating User model instances."""
    
    class Meta:
        model = User
    
    azure_user_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    display_name = factory.Faker("name")
    given_name = factory.Faker("first_name")
    surname = factory.Faker("last_name")
    job_title = factory.Faker("job")
    office_location = factory.Faker("city")
    business_phones = factory.Faker("phone_number")
    mobile_phone = factory.Faker("phone_number")
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class MailAccountFactory(factory.Factory):
    """Factory for creating MailAccount model instances."""
    
    class Meta:
        model = MailAccount
    
    user_id = factory.Sequence(lambda n: n)
    email_address = factory.Sequence(lambda n: f"mailbox{n}@example.com")
    display_name = factory.LazyAttribute(lambda obj: f"{obj.email_address} Mailbox")
    account_type = "user"
    is_shared = False
    is_active = True
    access_token_encrypted = factory.LazyFunction(lambda: "encrypted_" + "".join(random.choices(string.ascii_letters, k=20)))
    refresh_token_encrypted = factory.LazyFunction(lambda: "refresh_" + "".join(random.choices(string.ascii_letters, k=20)))
    token_expires_at = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(hours=1))
    last_sync_at = factory.LazyFunction(datetime.utcnow)
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class SharedMailAccountFactory(MailAccountFactory):
    """Factory for creating shared MailAccount instances."""
    
    account_type = "shared"
    is_shared = True
    email_address = factory.Sequence(lambda n: f"shared{n}@example.com")
    display_name = factory.Sequence(lambda n: f"Shared Team {n}")


class MailDataFactory(factory.Factory):
    """Factory for creating MailData model instances."""
    
    class Meta:
        model = MailData
    
    message_id = factory.LazyFunction(lambda: f"msg_{uuid.uuid4().hex[:8]}")
    mail_account_id = factory.Sequence(lambda n: n)
    folder_id = "inbox-folder-id"
    folder_name = "Inbox"
    subject = factory.Faker("sentence", nb_words=4)
    sender_email = factory.Faker("email")
    sender_name = factory.Faker("name")
    received_datetime = factory.LazyFunction(datetime.utcnow)
    has_attachments = factory.Faker("boolean", chance_of_getting_true=30)
    is_read = factory.Faker("boolean", chance_of_getting_true=60)
    importance = factory.Iterator(["low", "normal", "high"])
    body_preview = factory.Faker("text", max_nb_chars=100)
    internet_message_id = factory.LazyFunction(lambda: f"<{uuid.uuid4().hex}@example.com>")
    conversation_id = factory.LazyFunction(lambda: f"conv_{uuid.uuid4().hex[:8]}")
    is_voice_message = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class VoiceMailDataFactory(MailDataFactory):
    """Factory for creating voice message MailData instances."""
    
    folder_name = "Voice Messages"
    folder_id = "voice-folder-id"
    subject = factory.LazyFunction(lambda: f"Voice Message: {factory.Faker('sentence', nb_words=3).evaluate(None, None, {'locale': None})}")
    has_attachments = True
    is_voice_message = True
    body_preview = "Voice message attached"


class VoiceAttachmentFactory(factory.Factory):
    """Factory for creating VoiceAttachment model instances."""
    
    class Meta:
        model = VoiceAttachment
    
    attachment_id = factory.LazyFunction(lambda: f"att_{uuid.uuid4().hex[:8]}")
    mail_data_id = factory.Sequence(lambda n: n)
    filename = factory.LazyFunction(lambda: f"voice_recording_{random.randint(1000, 9999)}.wav")
    content_type = factory.Iterator(["audio/wav", "audio/mp3", "audio/mpeg", "audio/m4a"])
    size_bytes = factory.LazyFunction(lambda: random.randint(100000, 2000000))  # 100KB - 2MB
    duration_seconds = factory.LazyFunction(lambda: round(random.uniform(10.0, 300.0), 1))  # 10s - 5min
    sample_rate = factory.Iterator([44100, 48000, 22050])
    channels = factory.Iterator([1, 2])
    bitrate = factory.Iterator([128000, 192000, 256000, 320000])
    blob_name = factory.LazyAttribute(
        lambda obj: f"voice-attachments/{datetime.now().strftime('%Y-%m-%d')}/{obj.attachment_id}_{obj.filename}"
    )
    blob_url = factory.LazyAttribute(
        lambda obj: f"https://teststorage.blob.core.windows.net/{obj.blob_name}"
    )
    is_stored = True
    storage_path = factory.LazyAttribute(
        lambda obj: f"/voice-attachments/{datetime.now().strftime('%Y-%m-%d')}/"
    )
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class SystemSettingFactory(factory.Factory):
    """Factory for creating SystemSetting model instances."""
    
    class Meta:
        model = SystemSetting
    
    setting_key = factory.Sequence(lambda n: f"test_setting_{n}")
    setting_value = factory.Faker("word")
    setting_type = factory.Iterator(["string", "integer", "boolean", "json"])
    description = factory.Faker("sentence")
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class AuditLogFactory(factory.Factory):
    """Factory for creating AuditLog model instances."""
    
    class Meta:
        model = AuditLog
    
    user_id = factory.Sequence(lambda n: n)
    action = factory.Iterator(["login", "logout", "create", "update", "delete", "view"])
    resource_type = factory.Iterator(["user", "mail", "attachment", "folder", "setting"])
    resource_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    details = factory.LazyFunction(
        lambda: {
            "ip_address": f"192.168.1.{random.randint(1, 254)}",
            "user_agent": "Mozilla/5.0 (Test Browser)"
        }
    )
    timestamp = factory.LazyFunction(datetime.utcnow)


# Mock Data Builders
class MockDataBuilder:
    """Builder for creating complex mock data structures."""
    
    @staticmethod
    def create_graph_user_profile(
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Microsoft Graph user profile response."""
        user_id = user_id or str(uuid.uuid4())
        email = email or "testuser@example.com"
        name = name or "Test User"
        
        return {
            "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users/$entity",
            "id": user_id,
            "businessPhones": ["+1 206 555 0109"],
            "displayName": name,
            "givenName": name.split()[0],
            "surname": name.split()[-1] if " " in name else "User",
            "mail": email,
            "userPrincipalName": email,
            "jobTitle": random.choice(["Engineer", "Manager", "Analyst", "Coordinator"]),
            "officeLocation": random.choice(["Seattle", "New York", "Austin", "Remote"])
        }
    
    @staticmethod
    def create_graph_mail_folder(
        folder_id: Optional[str] = None,
        display_name: Optional[str] = None,
        unread_count: Optional[int] = None,
        total_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a Microsoft Graph mail folder response."""
        folder_id = folder_id or f"folder_{uuid.uuid4().hex[:8]}"
        display_name = display_name or random.choice(["Inbox", "Sent Items", "Drafts", "Voice Messages"])
        unread_count = unread_count if unread_count is not None else random.randint(0, 50)
        total_count = total_count if total_count is not None else unread_count + random.randint(0, 100)
        
        return {
            "id": folder_id,
            "displayName": display_name,
            "parentFolderId": "msgfolderroot",
            "childFolderCount": random.randint(0, 5),
            "unreadItemCount": unread_count,
            "totalItemCount": total_count,
            "sizeInBytes": random.randint(1000, 50000000),
            "isHidden": False
        }
    
    @staticmethod
    def create_graph_message(
        message_id: Optional[str] = None,
        subject: Optional[str] = None,
        sender_email: Optional[str] = None,
        has_attachments: bool = False,
        is_voice_message: bool = False
    ) -> Dict[str, Any]:
        """Create a Microsoft Graph message response."""
        message_id = message_id or f"msg_{uuid.uuid4().hex[:8]}"
        subject = subject or ("Voice Message: " if is_voice_message else "") + factory.Faker('sentence', nb_words=4).evaluate(None, None, {'locale': None})
        sender_email = sender_email or factory.Faker('email').evaluate(None, None, {'locale': None})
        sender_name = sender_email.split('@')[0].replace('.', ' ').title()
        
        return {
            "id": message_id,
            "createdDateTime": datetime.utcnow().isoformat() + "Z",
            "receivedDateTime": datetime.utcnow().isoformat() + "Z",
            "sentDateTime": (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z",
            "hasAttachments": has_attachments,
            "internetMessageId": f"<{uuid.uuid4().hex}@example.com>",
            "subject": subject,
            "bodyPreview": "Voice message attached" if is_voice_message else factory.Faker('text', max_nb_chars=50).evaluate(None, None, {'locale': None}),
            "importance": random.choice(["low", "normal", "high"]),
            "parentFolderId": "voice-folder-id" if is_voice_message else "inbox",
            "conversationId": f"conv_{uuid.uuid4().hex[:8]}",
            "isRead": random.choice([True, False]),
            "isDraft": False,
            "sender": {
                "emailAddress": {
                    "name": sender_name,
                    "address": sender_email
                }
            },
            "from": {
                "emailAddress": {
                    "name": sender_name,
                    "address": sender_email
                }
            },
            "toRecipients": [
                {
                    "emailAddress": {
                        "name": "Test User",
                        "address": "testuser@example.com"
                    }
                }
            ]
        }
    
    @staticmethod
    def create_graph_attachment(
        attachment_id: Optional[str] = None,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a Microsoft Graph attachment response."""
        attachment_id = attachment_id or f"att_{uuid.uuid4().hex[:8]}"
        filename = filename or f"voice_recording_{random.randint(1000, 9999)}.wav"
        content_type = content_type or "audio/wav"
        size = size or random.randint(100000, 2000000)
        
        return {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "id": attachment_id,
            "lastModifiedDateTime": datetime.utcnow().isoformat() + "Z",
            "name": filename,
            "contentType": content_type,
            "size": size,
            "isInline": False,
            "contentId": None,
            "contentLocation": None,
            "contentBytes": "UklGRiQIAABXQVZFZm10IBAAAAABAAIAFEABAABA=="  # Basic WAV header
        }


# Mock Service Factories
class MockServiceFactory:
    """Factory for creating mock service instances."""
    
    @staticmethod
    def create_msal_client(
        success: bool = True,
        token_response: Optional[Dict] = None
    ) -> Mock:
        """Create a mock MSAL client."""
        client = Mock()
        
        # Mock initiate_auth_code_flow
        client.initiate_auth_code_flow.return_value = {
            "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "flow": {
                "state": f"state_{uuid.uuid4().hex[:8]}",
                "code_verifier": f"verifier_{uuid.uuid4().hex[:16]}"
            }
        }
        
        if success and token_response:
            client.acquire_token_by_auth_code_flow.return_value = token_response
        elif success:
            client.acquire_token_by_auth_code_flow.return_value = {
                "access_token": f"token_{uuid.uuid4().hex[:16]}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": f"refresh_{uuid.uuid4().hex[:16]}",
                "scope": "User.Read Mail.Read Mail.ReadWrite"
            }
        else:
            client.acquire_token_by_auth_code_flow.return_value = {
                "error": "invalid_grant",
                "error_description": "The provided authorization grant is invalid"
            }
        
        return client
    
    @staticmethod
    def create_azure_blob_client(success: bool = True) -> Mock:
        """Create a mock Azure Blob client."""
        client = Mock()
        blob_client = Mock()
        
        if success:
            blob_client.upload_blob.return_value = None
            blob_client.download_blob.return_value = Mock(
                readall=Mock(return_value=b"mock audio data")
            )
            blob_client.exists.return_value = True
            blob_client.get_blob_properties.return_value = Mock(
                size=1048576,
                last_modified=datetime.utcnow(),
                content_settings=Mock(content_type="audio/wav")
            )
        else:
            blob_client.upload_blob.side_effect = Exception("Upload failed")
            blob_client.download_blob.side_effect = Exception("Download failed")
            blob_client.exists.return_value = False
        
        client.get_blob_client.return_value = blob_client
        return client
    
    @staticmethod
    def create_async_http_client(responses: Dict[str, Any]) -> AsyncMock:
        """Create a mock async HTTP client with predefined responses."""
        client = AsyncMock()
        
        async def mock_request(method: str, url: str, **kwargs) -> Mock:
            response = Mock()
            
            # Match URL patterns to responses
            for pattern, response_data in responses.items():
                if pattern in url:
                    response.status_code = 200
                    response.json.return_value = response_data
                    response.text = str(response_data)
                    return response
            
            # Default not found response
            response.status_code = 404
            response.json.return_value = {"error": {"code": "NotFound"}}
            return response
        
        client.request = mock_request
        client.get = lambda url, **kwargs: mock_request("GET", url, **kwargs)
        client.post = lambda url, **kwargs: mock_request("POST", url, **kwargs)
        client.patch = lambda url, **kwargs: mock_request("PATCH", url, **kwargs)
        client.delete = lambda url, **kwargs: mock_request("DELETE", url, **kwargs)
        
        return client


# Batch Data Creators
class BatchDataCreator:
    """Create batches of test data for complex scenarios."""
    
    @staticmethod
    def create_user_with_mailbox_and_messages(
        num_messages: int = 5,
        num_voice_messages: int = 2
    ) -> Dict[str, List]:
        """Create a complete user with mailbox and messages."""
        user = UserFactory()
        mailbox = MailAccountFactory(user_id=user.user_id, email_address=user.email)
        
        messages = []
        voice_attachments = []
        
        # Create regular messages
        for _ in range(num_messages):
            message = MailDataFactory(mail_account_id=mailbox.mail_account_id)
            messages.append(message)
        
        # Create voice messages with attachments
        for _ in range(num_voice_messages):
            voice_message = VoiceMailDataFactory(mail_account_id=mailbox.mail_account_id)
            messages.append(voice_message)
            
            attachment = VoiceAttachmentFactory(mail_data_id=voice_message.mail_data_id)
            voice_attachments.append(attachment)
        
        return {
            "user": user,
            "mailbox": mailbox,
            "messages": messages,
            "voice_attachments": voice_attachments
        }
    
    @staticmethod
    def create_shared_mailbox_scenario(
        num_users: int = 3,
        num_shared_mailboxes: int = 2
    ) -> Dict[str, List]:
        """Create a scenario with multiple users and shared mailboxes."""
        users = [UserFactory() for _ in range(num_users)]
        shared_mailboxes = []
        messages = []
        
        for i in range(num_shared_mailboxes):
            # Each shared mailbox is associated with the first user as owner
            shared_mailbox = SharedMailAccountFactory(
                user_id=users[0].user_id,
                email_address=f"shared{i+1}@example.com",
                display_name=f"Shared Team {i+1}"
            )
            shared_mailboxes.append(shared_mailbox)
            
            # Create messages in each shared mailbox
            for j in range(3):
                message = MailDataFactory(
                    mail_account_id=shared_mailbox.mail_account_id,
                    sender_email=users[j % len(users)].email
                )
                messages.append(message)
        
        return {
            "users": users,
            "shared_mailboxes": shared_mailboxes,
            "messages": messages
        }