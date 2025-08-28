"""Database test fixtures.

This module provides fixtures for database testing including:
- Test database session fixtures
- SQLite in-memory database setup
- Transaction rollback fixtures  
- Test data seeding fixtures
- Database model factories
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.Database import Base, get_async_session
from app.db.models.User import User
from app.db.models.MailAccount import MailAccount
from app.db.models.MailData import MailData
from app.db.models.VoiceAttachment import VoiceAttachment
from app.db.models.Operational import SystemSetting, AuditLog


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine using SQLite in-memory."""
    # Use SQLite in-memory database for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,  # Set to True to see SQL queries during testing
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with transaction rollback."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        # Start a transaction
        transaction = await session.begin()
        
        yield session
        
        # Rollback the transaction to clean up
        await transaction.rollback()


@pytest.fixture
async def test_session_commit(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session that commits changes (for integration tests)."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.commit()


@pytest.fixture
def sync_test_engine():
    """Create a synchronous test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    engine.dispose()


@pytest.fixture
def sync_test_session(sync_test_engine) -> Generator[Session, None, None]:
    """Create a synchronous test database session."""
    SessionLocal = sessionmaker(bind=sync_test_engine)
    session = SessionLocal()
    
    # Start a transaction
    transaction = session.begin()
    
    yield session
    
    # Rollback the transaction
    transaction.rollback()
    session.close()


# User fixtures
@pytest.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create a test user in the database."""
    user = User(
        azure_user_id="12345678-1234-1234-1234-123456789012",
        email="testuser@example.com",
        display_name="Test User",
        given_name="Test",
        surname="User",
        job_title="Software Engineer",
        office_location="Seattle",
        business_phones="+1 206 555 0109",
        mobile_phone="+1 425 555 0201",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(user)
    await test_session.flush()  # Flush to get the ID
    await test_session.refresh(user)
    
    return user


@pytest.fixture
async def inactive_test_user(test_session: AsyncSession) -> User:
    """Create an inactive test user."""
    user = User(
        azure_user_id="inactive-user-id-123",
        email="inactive@example.com",
        display_name="Inactive User",
        given_name="Inactive",
        surname="User",
        is_active=False,
        created_at=datetime.utcnow() - timedelta(days=30),
        updated_at=datetime.utcnow() - timedelta(days=30)
    )
    
    test_session.add(user)
    await test_session.flush()
    await test_session.refresh(user)
    
    return user


# Mail account fixtures
@pytest.fixture
async def test_mail_account(test_session: AsyncSession, test_user: User) -> MailAccount:
    """Create a test mail account."""
    mail_account = MailAccount(
        user_id=test_user.user_id,
        email_address="testuser@example.com",
        display_name="Test User Mailbox",
        account_type="user",
        is_shared=False,
        is_active=True,
        access_token_encrypted="encrypted_access_token",
        refresh_token_encrypted="encrypted_refresh_token",
        token_expires_at=datetime.utcnow() + timedelta(hours=1),
        last_sync_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(mail_account)
    await test_session.flush()
    await test_session.refresh(mail_account)
    
    return mail_account


@pytest.fixture
async def shared_mail_account(test_session: AsyncSession, test_user: User) -> MailAccount:
    """Create a test shared mail account."""
    shared_account = MailAccount(
        user_id=test_user.user_id,
        email_address="support@example.com",
        display_name="Support Team",
        account_type="shared",
        is_shared=True,
        is_active=True,
        access_token_encrypted="encrypted_shared_token",
        refresh_token_encrypted="encrypted_shared_refresh",
        token_expires_at=datetime.utcnow() + timedelta(hours=1),
        last_sync_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(shared_account)
    await test_session.flush()
    await test_session.refresh(shared_account)
    
    return shared_account


# Mail data fixtures
@pytest.fixture
async def test_mail_data(test_session: AsyncSession, test_mail_account: MailAccount) -> MailData:
    """Create test mail data."""
    mail_data = MailData(
        message_id="message-id-1",
        mail_account_id=test_mail_account.mail_account_id,
        folder_id="inbox-folder-id",
        folder_name="Inbox",
        subject="Test Email Subject",
        sender_email="sender@example.com",
        sender_name="Test Sender",
        received_datetime=datetime.utcnow(),
        has_attachments=True,
        is_read=False,
        importance="normal",
        body_preview="This is a test email...",
        internet_message_id="<message1@example.com>",
        conversation_id="conversation-id-1",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(mail_data)
    await test_session.flush()
    await test_session.refresh(mail_data)
    
    return mail_data


@pytest.fixture
async def voice_mail_data(test_session: AsyncSession, test_mail_account: MailAccount) -> MailData:
    """Create test voice mail data."""
    voice_mail = MailData(
        message_id="voice-message-id-1",
        mail_account_id=test_mail_account.mail_account_id,
        folder_id="voice-folder-id",
        folder_name="Voice Messages",
        subject="Voice Message: Important Call",
        sender_email="caller@example.com",
        sender_name="Important Caller",
        received_datetime=datetime.utcnow(),
        has_attachments=True,
        is_read=False,
        importance="high",
        body_preview="Voice message attached",
        internet_message_id="<voice1@example.com>",
        conversation_id="voice-conversation-id-1",
        is_voice_message=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(voice_mail)
    await test_session.flush()
    await test_session.refresh(voice_mail)
    
    return voice_mail


# Voice attachment fixtures
@pytest.fixture
async def test_voice_attachment(
    test_session: AsyncSession, 
    voice_mail_data: MailData
) -> VoiceAttachment:
    """Create a test voice attachment."""
    voice_attachment = VoiceAttachment(
        attachment_id="voice-attachment-id-1",
        mail_data_id=voice_mail_data.mail_data_id,
        filename="voice-recording.wav",
        content_type="audio/wav",
        size_bytes=1048576,
        duration_seconds=45.5,
        sample_rate=44100,
        channels=2,
        bitrate=192000,
        blob_name="voice-attachments/2025-01-15/voice-message-id-1_voice-attachment-id-1.wav",
        blob_url="https://teststorage.blob.core.windows.net/voice-attachments/voice-recording.wav",
        is_stored=True,
        storage_path="/voice-attachments/2025-01-15/",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(voice_attachment)
    await test_session.flush()
    await test_session.refresh(voice_attachment)
    
    return voice_attachment


# System setting fixtures  
@pytest.fixture
async def test_system_setting(test_session: AsyncSession) -> SystemSetting:
    """Create a test system setting."""
    setting = SystemSetting(
        setting_key="voice_folder_name",
        setting_value="Voice Messages",
        setting_type="string",
        description="Default name for voice message folders",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    test_session.add(setting)
    await test_session.flush()
    await test_session.refresh(setting)
    
    return setting


# Audit log fixtures
@pytest.fixture
async def test_audit_log(test_session: AsyncSession, test_user: User) -> AuditLog:
    """Create a test audit log entry."""
    audit_log = AuditLog(
        user_id=test_user.user_id,
        action="login",
        resource_type="auth",
        resource_id="auth-session-123",
        details={"ip_address": "127.0.0.1", "user_agent": "Test Browser"},
        timestamp=datetime.utcnow()
    )
    
    test_session.add(audit_log)
    await test_session.flush()
    await test_session.refresh(audit_log)
    
    return audit_log


# Data seeding fixtures
@pytest.fixture
async def seed_test_data(test_session: AsyncSession):
    """Seed the test database with comprehensive test data."""
    # Create multiple users
    users = [
        User(
            azure_user_id=f"user-{i}-id",
            email=f"user{i}@example.com",
            display_name=f"Test User {i}",
            given_name=f"User{i}",
            surname="Test",
            is_active=True,
            created_at=datetime.utcnow()
        )
        for i in range(1, 4)
    ]
    
    for user in users:
        test_session.add(user)
    
    await test_session.flush()
    
    # Create mail accounts for each user
    mail_accounts = []
    for i, user in enumerate(users, 1):
        account = MailAccount(
            user_id=user.user_id,
            email_address=f"user{i}@example.com",
            display_name=f"User {i} Mailbox",
            account_type="user",
            is_shared=False,
            is_active=True,
            created_at=datetime.utcnow()
        )
        test_session.add(account)
        mail_accounts.append(account)
    
    await test_session.flush()
    
    # Create mail data for each account
    for i, account in enumerate(mail_accounts, 1):
        for j in range(1, 4):
            mail_data = MailData(
                message_id=f"message-{i}-{j}",
                mail_account_id=account.mail_account_id,
                folder_id="inbox-folder-id",
                folder_name="Inbox",
                subject=f"Test Message {j} from User {i}",
                sender_email=f"sender{j}@example.com",
                sender_name=f"Sender {j}",
                received_datetime=datetime.utcnow() - timedelta(hours=j),
                has_attachments=j % 2 == 0,
                is_read=j == 1,
                created_at=datetime.utcnow()
            )
            test_session.add(mail_data)
    
    await test_session.commit()
    
    return {
        "users": users,
        "mail_accounts": mail_accounts
    }


@pytest.fixture
def database_test_config():
    """Test configuration for database functionality."""
    return {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 3600,
        "echo": False,
        "encryption_key": "test-encryption-key-32-chars-long!",
        "token_expiry_buffer_minutes": 5
    }


# Custom database assertion helpers
@pytest.fixture
def db_assertions():
    """Database-specific assertion helpers."""
    
    class DatabaseAssertions:
        @staticmethod
        async def assert_user_exists(session: AsyncSession, email: str):
            """Assert that a user with the given email exists."""
            from sqlalchemy import select
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            assert user is not None, f"User with email {email} does not exist"
            return user
            
        @staticmethod
        async def assert_mail_account_exists(session: AsyncSession, email: str):
            """Assert that a mail account exists."""
            from sqlalchemy import select
            result = await session.execute(
                select(MailAccount).where(MailAccount.email_address == email)
            )
            account = result.scalar_one_or_none()
            assert account is not None, f"Mail account {email} does not exist"
            return account
            
        @staticmethod
        async def assert_voice_attachment_stored(session: AsyncSession, attachment_id: str):
            """Assert that a voice attachment is stored."""
            from sqlalchemy import select
            result = await session.execute(
                select(VoiceAttachment).where(VoiceAttachment.attachment_id == attachment_id)
            )
            attachment = result.scalar_one_or_none()
            assert attachment is not None, f"Voice attachment {attachment_id} not found"
            assert attachment.is_stored, f"Voice attachment {attachment_id} is not stored"
            return attachment
    
    return DatabaseAssertions()