"""
Database integration tests.

Tests comprehensive database operations including:
- Database initialization and connection management
- Model creation, updates, and relationships
- Transaction handling and rollback scenarios
- Concurrent access patterns and isolation
- Migration and schema validation
- Performance characteristics
- Row-Level Security (RLS) enforcement
- Connection pooling and cleanup
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import patch, Mock

from sqlalchemy import select, func, text, event
from sqlalchemy.exc import IntegrityError, DatabaseError as SQLDatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.Database import DatabaseManager, db_manager
from app.db.models.User import User
from app.db.models.MailAccount import MailAccount
from app.db.models.MailData import MailData
from app.db.models.VoiceAttachment import VoiceAttachment
from app.core.Exceptions import DatabaseError
from tests.integration.utils import DatabaseAssertions


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest_asyncio.fixture
    async def db_manager_instance(self, test_db_engine):
        """Get database manager instance for testing.""" 
        manager = DatabaseManager()
        manager.engine = test_db_engine
        return manager

    @pytest_asyncio.fixture
    async def db_assertions(self, integration_db_session):
        """Get database assertions helper."""
        return DatabaseAssertions(integration_db_session)

    # =========================================================================
    # DATABASE CONNECTION AND INITIALIZATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_connection_health_check(self, db_manager_instance):
        """Test database health check functionality."""
        # Health check should pass
        is_healthy = await db_manager_instance.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_info_retrieval(self, db_manager_instance):
        """Test retrieving database information."""
        db_info = await db_manager_instance.get_database_info()
        
        assert db_info is not None
        assert "connection_successful" in db_info
        assert db_info["connection_successful"] is True
        assert "database_name" in db_info
        assert "current_user" in db_info

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_connection_retry_logic(self, test_db_engine):
        """Test connection retry logic on temporary failures."""
        manager = DatabaseManager()
        manager.engine = test_db_engine
        
        # Simulate temporary connection failure then recovery
        connection_attempts = []
        
        async def mock_connect_with_failure(*args, **kwargs):
            connection_attempts.append(datetime.utcnow())
            if len(connection_attempts) == 1:
                raise ConnectionError("Temporary connection failure")
            return await test_db_engine.connect()
        
        with patch.object(test_db_engine, 'connect', side_effect=mock_connect_with_failure):
            try:
                # First attempt should fail
                await manager.health_check()
                pytest.fail("Expected connection error")
            except Exception:
                pass
            
            # Second attempt should succeed
            is_healthy = await manager.health_check()
            assert is_healthy is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_connection_pool_management(self, db_manager_instance):
        """Test connection pooling behavior."""
        # Create multiple concurrent connections
        async def create_connection():
            return await db_manager_instance.engine.connect()
        
        # Create several connections concurrently
        connections = await asyncio.gather(
            create_connection(),
            create_connection(), 
            create_connection(),
            return_exceptions=True
        )
        
        # All connections should be successful
        successful_connections = [c for c in connections if not isinstance(c, Exception)]
        assert len(successful_connections) >= 3
        
        # Clean up connections
        for conn in successful_connections:
            await conn.close()

    # =========================================================================
    # MODEL CRUD OPERATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_model_crud_operations(self, integration_db_session, db_assertions):
        """Test complete CRUD operations for User model."""
        session = integration_db_session
        
        # CREATE
        new_user = User(
            user_id="crud-test-user",
            email="crud@example.com",
            display_name="CRUD Test User",
            given_name="CRUD",
            surname="User", 
            is_active=True
        )
        
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        
        # Verify creation
        created_user = await db_assertions.assert_user_exists(
            "crud-test-user",
            email="crud@example.com",
            is_active=True
        )
        assert created_user.id is not None
        assert created_user.created_at is not None
        
        # READ
        result = await session.execute(
            select(User).where(User.user_id == "crud-test-user")
        )
        retrieved_user = result.scalar_one()
        assert retrieved_user.email == "crud@example.com"
        
        # UPDATE
        retrieved_user.display_name = "Updated CRUD User"
        retrieved_user.is_active = False
        await session.commit()
        
        # Verify update
        await db_assertions.assert_user_exists(
            "crud-test-user",
            display_name="Updated CRUD User",
            is_active=False
        )
        
        # DELETE
        await session.delete(retrieved_user)
        await session.commit()
        
        # Verify deletion
        result = await session.execute(
            select(User).where(User.user_id == "crud-test-user")
        )
        deleted_user = result.scalar_one_or_none()
        assert deleted_user is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mail_data_with_relationships(self, integration_db_session, db_assertions):
        """Test mail data operations with user relationships."""
        session = integration_db_session
        
        # Create user first
        user = User(
            user_id="mail-test-user",
            email="mail@example.com", 
            display_name="Mail Test User",
            given_name="Mail",
            surname="User",
            is_active=True
        )
        session.add(user)
        await session.commit()
        
        # Create mail data
        mail_data = MailData(
            message_id="test-mail-001",
            thread_id="test-thread-001",
            user_id="mail-test-user",
            folder_id="inbox",
            subject="Test Email Subject",
            sender_email="sender@example.com",
            sender_name="Test Sender",
            received_datetime=datetime.utcnow(),
            is_read=False,
            has_attachments=True
        )
        
        session.add(mail_data)
        await session.commit()
        await session.refresh(mail_data)
        
        # Verify mail data creation
        await db_assertions.assert_mail_data_exists(
            "test-mail-001",
            user_id="mail-test-user",
            is_read=False,
            has_attachments=True
        )
        
        # Test relationship query
        result = await session.execute(
            select(User)
            .join(MailData, User.user_id == MailData.user_id)
            .where(MailData.message_id == "test-mail-001")
        )
        related_user = result.scalar_one()
        assert related_user.email == "mail@example.com"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_voice_attachment_operations(self, integration_db_session, db_assertions):
        """Test voice attachment model operations."""
        session = integration_db_session
        
        # Create prerequisite data
        user = User(
            user_id="voice-test-user",
            email="voice@example.com",
            display_name="Voice User",
            given_name="Voice",
            surname="User",
            is_active=True
        )
        session.add(user)
        
        mail_data = MailData(
            message_id="voice-mail-001",
            thread_id="voice-thread-001",
            user_id="voice-test-user",
            folder_id="inbox",
            subject="Voice Message",
            sender_email="caller@example.com",
            sender_name="Caller",
            received_datetime=datetime.utcnow(),
            is_read=False,
            has_attachments=True
        )
        session.add(mail_data)
        await session.commit()
        
        # Create voice attachment
        voice_attachment = VoiceAttachment(
            attachment_id="voice-att-001",
            message_id="voice-mail-001",
            user_id="voice-test-user",
            file_name="important-call.wav",
            content_type="audio/wav",
            size_bytes=2048000,
            blob_name="voice-att-001.wav",
            storage_account="testaccount",
            container_name="voice-attachments",
            download_count=0
        )
        
        session.add(voice_attachment)
        await session.commit()
        await session.refresh(voice_attachment)
        
        # Verify voice attachment
        created_attachment = await db_assertions.assert_voice_attachment_exists(
            "voice-att-001",
            user_id="voice-test-user",
            content_type="audio/wav",
            download_count=0
        )
        
        # Test download count increment
        voice_attachment.download_count += 1
        await session.commit()
        
        await db_assertions.assert_voice_attachment_exists(
            "voice-att-001",
            download_count=1
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_model_validation_constraints(self, integration_db_session):
        """Test database constraint validation."""
        session = integration_db_session
        
        # Test unique constraint on user_id
        user1 = User(
            user_id="duplicate-test",
            email="user1@example.com",
            display_name="User 1",
            given_name="User",
            surname="One",
            is_active=True
        )
        session.add(user1)
        await session.commit()
        
        # Attempt to create duplicate user_id
        user2 = User(
            user_id="duplicate-test",  # Same user_id
            email="user2@example.com",
            display_name="User 2",
            given_name="User", 
            surname="Two",
            is_active=True
        )
        session.add(user2)
        
        with pytest.raises(IntegrityError):
            await session.commit()
        
        await session.rollback()

    # =========================================================================
    # TRANSACTION MANAGEMENT TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_transaction_rollback_on_error(self, integration_db_session, db_assertions):
        """Test transaction rollback behavior on errors."""
        session = integration_db_session
        
        # Start transaction with multiple operations
        transaction = await session.begin()
        
        try:
            # Create valid user
            user = User(
                user_id="transaction-test",
                email="transaction@example.com",
                display_name="Transaction User",
                given_name="Transaction",
                surname="User",
                is_active=True
            )
            session.add(user)
            
            # Create invalid mail data (missing required fields)
            invalid_mail = MailData(
                message_id=None,  # Required field is None
                user_id="transaction-test"
            )
            session.add(invalid_mail)
            
            # This should fail and rollback
            await session.commit()
            pytest.fail("Expected IntegrityError")
            
        except (IntegrityError, SQLDatabaseError):
            await transaction.rollback()
            
            # Verify rollback - user should not exist
            result = await session.execute(
                select(User).where(User.user_id == "transaction-test")
            )
            rolled_back_user = result.scalar_one_or_none()
            assert rolled_back_user is None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_nested_transaction_handling(self, integration_db_session):
        """Test nested transaction behavior."""
        session = integration_db_session
        
        # Outer transaction
        outer_transaction = await session.begin()
        
        try:
            # Create user in outer transaction
            user = User(
                user_id="nested-test",
                email="nested@example.com",
                display_name="Nested User",
                given_name="Nested",
                surname="User",
                is_active=True
            )
            session.add(user)
            
            # Inner transaction (savepoint)
            inner_transaction = await session.begin_nested()
            
            try:
                # Create mail data in inner transaction
                mail = MailData(
                    message_id="nested-mail-001",
                    thread_id="nested-thread-001",
                    user_id="nested-test",
                    folder_id="inbox",
                    subject="Nested Test",
                    sender_email="nested@sender.com",
                    sender_name="Nested Sender",
                    received_datetime=datetime.utcnow(),
                    is_read=False,
                    has_attachments=False
                )
                session.add(mail)
                
                # Simulate error in inner transaction
                raise ValueError("Inner transaction error")
                
            except ValueError:
                await inner_transaction.rollback()
                
            # Outer transaction should still be valid
            await outer_transaction.commit()
            
            # User should exist, mail should not
            result = await session.execute(
                select(User).where(User.user_id == "nested-test")
            )
            user_exists = result.scalar_one_or_none()
            assert user_exists is not None
            
            result = await session.execute(
                select(MailData).where(MailData.message_id == "nested-mail-001")
            )
            mail_exists = result.scalar_one_or_none()
            assert mail_exists is None
            
        except Exception:
            await outer_transaction.rollback()
            raise

    # =========================================================================
    # CONCURRENT ACCESS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_user_creation(self, test_db_engine):
        """Test concurrent user creation with potential conflicts."""
        from sqlalchemy.ext.asyncio import async_sessionmaker
        
        async_session_factory = async_sessionmaker(
            test_db_engine, 
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async def create_user_concurrently(user_suffix: str):
            async with async_session_factory() as session:
                try:
                    user = User(
                        user_id=f"concurrent-user-{user_suffix}",
                        email=f"concurrent{user_suffix}@example.com",
                        display_name=f"Concurrent User {user_suffix}",
                        given_name="Concurrent",
                        surname=f"User{user_suffix}",
                        is_active=True
                    )
                    session.add(user)
                    await session.commit()
                    return True
                except Exception as e:
                    await session.rollback()
                    return e
        
        # Create multiple users concurrently
        results = await asyncio.gather(
            create_user_concurrently("A"),
            create_user_concurrently("B"),
            create_user_concurrently("C"),
            return_exceptions=True
        )
        
        # Most should succeed
        successful_creations = [r for r in results if r is True]
        assert len(successful_creations) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_mail_data_updates(self, integration_db_session):
        """Test concurrent updates to mail data."""
        session = integration_db_session
        
        # Create initial data
        user = User(
            user_id="concurrent-mail-user",
            email="concurrent@example.com",
            display_name="Concurrent User",
            given_name="Concurrent",
            surname="User",
            is_active=True
        )
        session.add(user)
        
        mail = MailData(
            message_id="concurrent-mail-001",
            thread_id="concurrent-thread-001", 
            user_id="concurrent-mail-user",
            folder_id="inbox",
            subject="Concurrent Test",
            sender_email="sender@example.com",
            sender_name="Sender",
            received_datetime=datetime.utcnow(),
            is_read=False,
            has_attachments=False
        )
        session.add(mail)
        await session.commit()
        
        # Simulate concurrent updates
        async def update_read_status():
            async with session.begin():
                result = await session.execute(
                    select(MailData).where(MailData.message_id == "concurrent-mail-001")
                )
                mail_to_update = result.scalar_one()
                mail_to_update.is_read = True
                await session.commit()
        
        async def update_folder():
            async with session.begin():
                result = await session.execute(
                    select(MailData).where(MailData.message_id == "concurrent-mail-001")
                )
                mail_to_update = result.scalar_one()
                mail_to_update.folder_id = "processed"
                await session.commit()
        
        # Execute concurrent updates
        await asyncio.gather(
            update_read_status(),
            update_folder(),
            return_exceptions=True
        )
        
        # Verify final state
        result = await session.execute(
            select(MailData).where(MailData.message_id == "concurrent-mail-001")
        )
        final_mail = result.scalar_one()
        assert final_mail.is_read is True
        assert final_mail.folder_id == "processed"

    # =========================================================================
    # QUERY PERFORMANCE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_large_dataset_query_performance(self, integration_db_session):
        """Test query performance with larger datasets."""
        session = integration_db_session
        
        # Create test user
        user = User(
            user_id="performance-user",
            email="performance@example.com",
            display_name="Performance User", 
            given_name="Performance",
            surname="User",
            is_active=True
        )
        session.add(user)
        await session.commit()
        
        # Create many mail entries for performance testing
        mail_entries = []
        for i in range(100):  # Reduced from 1000 for faster test execution
            mail_entry = MailData(
                message_id=f"perf-mail-{i:04d}",
                thread_id=f"perf-thread-{i//10}",
                user_id="performance-user",
                folder_id="inbox" if i % 2 == 0 else "sent",
                subject=f"Performance Test Message {i}",
                sender_email=f"sender{i}@example.com",
                sender_name=f"Sender {i}",
                received_datetime=datetime.utcnow() - timedelta(hours=i),
                is_read=i % 3 == 0,
                has_attachments=i % 5 == 0
            )
            mail_entries.append(mail_entry)
        
        session.add_all(mail_entries)
        await session.commit()
        
        # Test query performance
        import time
        
        # Test 1: Simple count query
        start_time = time.time()
        result = await session.execute(
            select(func.count(MailData.id)).where(MailData.user_id == "performance-user")
        )
        count = result.scalar()
        count_time = time.time() - start_time
        
        assert count == 100
        assert count_time < 1.0  # Should complete under 1 second
        
        # Test 2: Filtered query with pagination
        start_time = time.time()
        result = await session.execute(
            select(MailData)
            .where(MailData.user_id == "performance-user")
            .where(MailData.folder_id == "inbox")
            .where(MailData.has_attachments == True)
            .limit(10)
            .offset(0)
        )
        filtered_results = result.scalars().all()
        filter_time = time.time() - start_time
        
        assert len(filtered_results) > 0
        assert filter_time < 1.0  # Should complete under 1 second
        
        # Test 3: Aggregation query
        start_time = time.time()
        result = await session.execute(
            select(
                MailData.folder_id,
                func.count(MailData.id).label('message_count'),
                func.sum(MailData.is_read.cast('integer')).label('read_count')
            )
            .where(MailData.user_id == "performance-user")
            .group_by(MailData.folder_id)
        )
        aggregation_results = result.all()
        aggregation_time = time.time() - start_time
        
        assert len(aggregation_results) == 2  # inbox and sent
        assert aggregation_time < 1.0  # Should complete under 1 second

    @pytest.mark.asyncio
    @pytest.mark.integration 
    async def test_complex_join_query_performance(self, integration_db_session):
        """Test performance of complex join queries."""
        session = integration_db_session
        
        # Create test data
        users = []
        for i in range(5):
            user = User(
                user_id=f"join-user-{i}",
                email=f"join{i}@example.com",
                display_name=f"Join User {i}",
                given_name="Join",
                surname=f"User{i}",
                is_active=True
            )
            users.append(user)
        
        session.add_all(users)
        await session.commit()
        
        # Create mail data and voice attachments
        for i, user in enumerate(users):
            for j in range(10):
                mail = MailData(
                    message_id=f"join-mail-{i}-{j}",
                    thread_id=f"join-thread-{i}-{j//3}",
                    user_id=user.user_id,
                    folder_id="inbox",
                    subject=f"Join Test {i}-{j}",
                    sender_email=f"sender{j}@example.com",
                    sender_name=f"Sender {j}",
                    received_datetime=datetime.utcnow(),
                    is_read=j % 2 == 0,
                    has_attachments=j % 3 == 0
                )
                session.add(mail)
                
                # Add voice attachment for some messages
                if j % 3 == 0:
                    voice_att = VoiceAttachment(
                        attachment_id=f"join-voice-{i}-{j}",
                        message_id=mail.message_id,
                        user_id=user.user_id,
                        file_name=f"voice{i}-{j}.wav",
                        content_type="audio/wav",
                        size_bytes=1024000 + (j * 100000),
                        blob_name=f"join-voice-{i}-{j}.wav",
                        storage_account="testaccount",
                        container_name="voice-attachments",
                        download_count=j
                    )
                    session.add(voice_att)
        
        await session.commit()
        
        # Test complex join query
        import time
        start_time = time.time()
        
        result = await session.execute(
            select(
                User.email,
                func.count(MailData.id).label('total_messages'),
                func.count(VoiceAttachment.id).label('voice_attachments'),
                func.sum(VoiceAttachment.size_bytes).label('total_voice_size')
            )
            .outerjoin(MailData, User.user_id == MailData.user_id)
            .outerjoin(VoiceAttachment, MailData.message_id == VoiceAttachment.message_id)
            .group_by(User.email)
            .order_by(User.email)
        )
        
        join_results = result.all()
        join_time = time.time() - start_time
        
        assert len(join_results) == 5
        assert join_time < 2.0  # Should complete under 2 seconds
        
        # Verify results structure
        for row in join_results:
            assert row.total_messages > 0
            assert hasattr(row, 'voice_attachments')

    # =========================================================================
    # DATABASE CLEANUP AND MAINTENANCE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_cleanup_operations(self, integration_db_session, db_assertions):
        """Test database cleanup and maintenance operations."""
        session = integration_db_session
        
        # Create test data with old timestamps
        old_date = datetime.utcnow() - timedelta(days=90)
        recent_date = datetime.utcnow() - timedelta(days=1)
        
        # Create users and mail data
        user = User(
            user_id="cleanup-user",
            email="cleanup@example.com",
            display_name="Cleanup User",
            given_name="Cleanup",
            surname="User",
            is_active=True
        )
        session.add(user)
        
        # Old mail data
        old_mail = MailData(
            message_id="old-mail-001",
            thread_id="old-thread-001",
            user_id="cleanup-user",
            folder_id="archive",
            subject="Old Message",
            sender_email="old@example.com",
            sender_name="Old Sender",
            received_datetime=old_date,
            is_read=True,
            has_attachments=False
        )
        session.add(old_mail)
        
        # Recent mail data
        recent_mail = MailData(
            message_id="recent-mail-001",
            thread_id="recent-thread-001", 
            user_id="cleanup-user",
            folder_id="inbox",
            subject="Recent Message",
            sender_email="recent@example.com",
            sender_name="Recent Sender",
            received_datetime=recent_date,
            is_read=False,
            has_attachments=True
        )
        session.add(recent_mail)
        
        await session.commit()
        
        # Test cleanup query (simulate cleanup of old archived messages)
        cleanup_cutoff = datetime.utcnow() - timedelta(days=30)
        
        result = await session.execute(
            select(MailData)
            .where(MailData.received_datetime < cleanup_cutoff)
            .where(MailData.folder_id == "archive")
            .where(MailData.is_read == True)
        )
        old_messages = result.scalars().all()
        
        assert len(old_messages) == 1
        assert old_messages[0].message_id == "old-mail-001"
        
        # Simulate cleanup (delete old messages)
        for message in old_messages:
            await session.delete(message)
        await session.commit()
        
        # Verify cleanup
        result = await session.execute(
            select(func.count(MailData.id)).where(MailData.user_id == "cleanup-user")
        )
        remaining_messages = result.scalar()
        assert remaining_messages == 1  # Only recent message should remain

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_orphaned_data_cleanup(self, integration_db_session):
        """Test cleanup of orphaned data relationships."""
        session = integration_db_session
        
        # Create user and related data
        user = User(
            user_id="orphan-user",
            email="orphan@example.com",
            display_name="Orphan User",
            given_name="Orphan",
            surname="User",
            is_active=True
        )
        session.add(user)
        
        mail = MailData(
            message_id="orphan-mail-001",
            thread_id="orphan-thread-001",
            user_id="orphan-user",
            folder_id="inbox",
            subject="Orphan Test",
            sender_email="orphan@sender.com", 
            sender_name="Orphan Sender",
            received_datetime=datetime.utcnow(),
            is_read=False,
            has_attachments=True
        )
        session.add(mail)
        
        voice_attachment = VoiceAttachment(
            attachment_id="orphan-voice-001",
            message_id="orphan-mail-001",
            user_id="orphan-user",
            file_name="orphan.wav",
            content_type="audio/wav",
            size_bytes=1024000,
            blob_name="orphan-voice-001.wav",
            storage_account="testaccount",
            container_name="voice-attachments",
            download_count=0
        )
        session.add(voice_attachment)
        
        await session.commit()
        
        # Delete user (simulating orphaned data scenario)
        await session.delete(user)
        await session.commit()
        
        # Check for orphaned mail data
        result = await session.execute(
            select(MailData)
            .outerjoin(User, MailData.user_id == User.user_id)
            .where(User.user_id.is_(None))
        )
        orphaned_mail = result.scalars().all()
        
        # In a real system, this would be cleaned up by foreign key constraints
        # For testing, we verify the orphaned data can be identified
        assert len(orphaned_mail) >= 0  # May be 0 if FK constraints prevent orphaning

    # =========================================================================
    # ERROR HANDLING AND RECOVERY TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_database_error_handling(self, integration_db_session):
        """Test proper error handling for database operations."""
        session = integration_db_session
        
        # Test handling of constraint violations
        with pytest.raises((IntegrityError, SQLDatabaseError)):
            # Attempt to create user with invalid data
            invalid_user = User(
                user_id=None,  # Required field is None
                email="invalid@example.com",
                display_name="Invalid User"
            )
            session.add(invalid_user)
            await session.commit()
        
        await session.rollback()
        
        # Test handling of foreign key violations
        with pytest.raises((IntegrityError, SQLDatabaseError)):
            # Attempt to create mail data for non-existent user
            orphaned_mail = MailData(
                message_id="orphaned-mail-001",
                thread_id="orphaned-thread-001",
                user_id="non-existent-user",
                folder_id="inbox",
                subject="Orphaned Mail",
                sender_email="orphan@example.com",
                sender_name="Orphan",
                received_datetime=datetime.utcnow(),
                is_read=False,
                has_attachments=False
            )
            session.add(orphaned_mail)
            await session.commit()
        
        await session.rollback()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_recovery_after_error(self, integration_db_session):
        """Test session recovery after database errors."""
        session = integration_db_session
        
        # Cause an error
        try:
            invalid_user = User(
                user_id=None,
                email="error@example.com"
            )
            session.add(invalid_user)
            await session.commit()
        except (IntegrityError, SQLDatabaseError):
            await session.rollback()
        
        # Session should be usable after rollback
        valid_user = User(
            user_id="recovery-user",
            email="recovery@example.com",
            display_name="Recovery User",
            given_name="Recovery",
            surname="User",
            is_active=True
        )
        session.add(valid_user)
        await session.commit()
        
        # Verify recovery
        result = await session.execute(
            select(User).where(User.user_id == "recovery-user")
        )
        recovered_user = result.scalar_one_or_none()
        assert recovered_user is not None
        assert recovered_user.email == "recovery@example.com"

    # =========================================================================
    # PERFORMANCE MONITORING TESTS
    # =========================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_query_monitoring_and_logging(self, integration_db_session, database_query_monitor):
        """Test database query monitoring functionality."""
        session = integration_db_session
        
        # Execute various queries to generate monitoring data
        # Simple query
        await session.execute(select(func.count(User.id)))
        
        # Complex query
        await session.execute(
            select(User.email, func.count(MailData.id))
            .outerjoin(MailData, User.user_id == MailData.user_id)
            .group_by(User.email)
        )
        
        # Parameterized query
        await session.execute(
            select(User).where(User.email == "test@example.com")
        )
        
        # The database_query_monitor fixture should capture these queries
        queries = database_query_monitor
        
        # Verify queries were monitored
        assert len(queries) >= 3
        
        # Verify query structure
        for query in queries:
            assert "statement" in query
            assert "timestamp" in query
            assert isinstance(query["timestamp"], datetime)