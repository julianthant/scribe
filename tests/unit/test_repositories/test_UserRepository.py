"""
Unit tests for UserRepository.

Tests the user data access layer including:
- User CRUD operations
- User profile management
- Session management
- Query operations and filtering
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from app.repositories.UserRepository import UserRepository
from app.db.models.User import User, UserProfile, UserSession
from app.core.Exceptions import ValidationError, NotFoundError


class TestUserRepository:
    """Unit tests for UserRepository class."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.add = Mock()
        mock_session.delete = Mock()
        mock_session.merge = Mock()
        return mock_session

    @pytest.fixture
    def user_repository(self, mock_db_session):
        """Create UserRepository with mocked database session."""
        return UserRepository(mock_db_session)

    @pytest.fixture
    def mock_user(self):
        """Mock User model instance."""
        return User(
            user_id="user_12345",
            email="test@example.com",
            is_active=True,
            created_at=datetime(2024, 8, 28, 10, 0),
            updated_at=datetime(2024, 8, 28, 10, 0)
        )

    @pytest.fixture
    def mock_user_profile(self):
        """Mock UserProfile model instance."""
        return UserProfile(
            user_id="user_12345",
            display_name="Test User",
            given_name="Test",
            surname="User",
            role="user",
            is_superuser=False
        )

    @pytest.fixture
    def mock_session_record(self):
        """Mock UserSession model instance."""
        return UserSession(
            session_id="session_abc123",
            user_id="user_12345",
            access_token="token_xyz789",
            refresh_token="refresh_token_123",
            expires_at=datetime.now() + timedelta(hours=1),
            created_at=datetime.now()
        )

    # =====================================================================
    # User CRUD Operations Tests
    # =====================================================================

    async def test_create_user_success(self, user_repository, mock_db_session, mock_user):
        """Test creating user successfully."""
        result = await user_repository.create_user(mock_user)
        
        assert result == mock_user
        mock_db_session.add.assert_called_once_with(mock_user)
        mock_db_session.commit.assert_called_once()

    async def test_create_user_duplicate_email(self, user_repository, mock_db_session, mock_user):
        """Test creating user with duplicate email."""
        mock_db_session.commit.side_effect = IntegrityError("Duplicate key", None, None)
        
        with pytest.raises(ValidationError):
            await user_repository.create_user(mock_user)
        
        mock_db_session.rollback.assert_called_once()

    async def test_get_user_by_id_success(self, user_repository, mock_db_session, mock_user):
        """Test getting user by ID successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_user_by_id("user_12345")
        
        assert result == mock_user
        mock_db_session.execute.assert_called_once()

    async def test_get_user_by_id_not_found(self, user_repository, mock_db_session):
        """Test getting non-existent user by ID."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_user_by_id("nonexistent")
        
        assert result is None

    async def test_get_user_by_email_success(self, user_repository, mock_db_session, mock_user):
        """Test getting user by email successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_user_by_email("test@example.com")
        
        assert result == mock_user
        assert result.email == "test@example.com"

    async def test_get_user_by_email_case_insensitive(self, user_repository, mock_db_session, mock_user):
        """Test getting user by email with different case."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_user_by_email("TEST@EXAMPLE.COM")
        
        assert result == mock_user
        # Verify query was called with lowercase email
        mock_db_session.execute.assert_called_once()

    async def test_update_user_success(self, user_repository, mock_db_session, mock_user):
        """Test updating user successfully."""
        mock_user.email = "updated@example.com"
        mock_user.updated_at = datetime.now()
        
        result = await user_repository.update_user(mock_user)
        
        assert result == mock_user
        mock_db_session.merge.assert_called_once_with(mock_user)
        mock_db_session.commit.assert_called_once()

    async def test_delete_user_success(self, user_repository, mock_db_session, mock_user):
        """Test deleting user successfully."""
        # Mock finding the user first
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.delete_user("user_12345")
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_user)
        mock_db_session.commit.assert_called_once()

    async def test_delete_user_not_found(self, user_repository, mock_db_session):
        """Test deleting non-existent user."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.delete_user("nonexistent")
        
        assert result is False
        mock_db_session.delete.assert_not_called()

    # =====================================================================
    # User Profile Management Tests
    # =====================================================================

    async def test_create_user_profile_success(self, user_repository, mock_db_session, mock_user_profile):
        """Test creating user profile successfully."""
        result = await user_repository.create_user_profile(mock_user_profile)
        
        assert result == mock_user_profile
        mock_db_session.add.assert_called_once_with(mock_user_profile)
        mock_db_session.commit.assert_called_once()

    async def test_get_user_profile_success(self, user_repository, mock_db_session, mock_user_profile):
        """Test getting user profile successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user_profile
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_user_profile("user_12345")
        
        assert result == mock_user_profile
        assert result.display_name == "Test User"

    async def test_update_user_profile_success(self, user_repository, mock_db_session, mock_user_profile):
        """Test updating user profile successfully."""
        mock_user_profile.display_name = "Updated Name"
        
        result = await user_repository.update_user_profile(mock_user_profile)
        
        assert result == mock_user_profile
        mock_db_session.merge.assert_called_once_with(mock_user_profile)
        mock_db_session.commit.assert_called_once()

    # =====================================================================
    # Session Management Tests
    # =====================================================================

    async def test_create_session_success(self, user_repository, mock_db_session, mock_session_record):
        """Test creating user session successfully."""
        result = await user_repository.create_session(mock_session_record)
        
        assert result == mock_session_record
        mock_db_session.add.assert_called_once_with(mock_session_record)
        mock_db_session.commit.assert_called_once()

    async def test_get_session_by_id_success(self, user_repository, mock_db_session, mock_session_record):
        """Test getting session by ID successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_session_record
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_session_by_id("session_abc123")
        
        assert result == mock_session_record
        assert result.session_id == "session_abc123"

    async def test_get_session_by_id_with_user_profile(self, user_repository, mock_db_session, mock_session_record, mock_user_profile):
        """Test getting session with joined user profile."""
        # Mock session with joined user and profile
        mock_session_record.user = Mock()
        mock_session_record.user.profile = mock_user_profile
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_session_record
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_session_by_id("session_abc123")
        
        assert result == mock_session_record
        assert result.user.profile == mock_user_profile

    async def test_get_active_sessions_for_user(self, user_repository, mock_db_session):
        """Test getting active sessions for user."""
        mock_sessions = [
            Mock(session_id="session1", expires_at=datetime.now() + timedelta(hours=1)),
            Mock(session_id="session2", expires_at=datetime.now() + timedelta(hours=2))
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_sessions
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_active_sessions_for_user("user_12345")
        
        assert len(result) == 2
        assert result[0].session_id == "session1"

    async def test_update_session_success(self, user_repository, mock_db_session, mock_session_record):
        """Test updating session successfully."""
        mock_session_record.access_token = "new_token"
        
        result = await user_repository.update_session(mock_session_record)
        
        assert result == mock_session_record
        mock_db_session.merge.assert_called_once_with(mock_session_record)
        mock_db_session.commit.assert_called_once()

    async def test_delete_session_success(self, user_repository, mock_db_session, mock_session_record):
        """Test deleting session successfully."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_session_record
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.delete_session("session_abc123")
        
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_session_record)
        mock_db_session.commit.assert_called_once()

    async def test_delete_expired_sessions(self, user_repository, mock_db_session):
        """Test deleting expired sessions."""
        # Mock expired sessions
        expired_sessions = [
            Mock(session_id="expired1", expires_at=datetime.now() - timedelta(hours=1)),
            Mock(session_id="expired2", expires_at=datetime.now() - timedelta(hours=2))
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = expired_sessions
        mock_db_session.execute.return_value = mock_result
        
        deleted_count = await user_repository.delete_expired_sessions()
        
        assert deleted_count == 2
        assert mock_db_session.delete.call_count == 2
        mock_db_session.commit.assert_called_once()

    # =====================================================================
    # Query and Filtering Tests
    # =====================================================================

    async def test_list_users_with_pagination(self, user_repository, mock_db_session):
        """Test listing users with pagination."""
        mock_users = [
            Mock(user_id="user1", email="user1@example.com"),
            Mock(user_id="user2", email="user2@example.com")
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_users
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.list_users(limit=10, offset=0)
        
        assert len(result) == 2
        assert result[0].user_id == "user1"

    async def test_list_users_with_active_filter(self, user_repository, mock_db_session):
        """Test listing users filtered by active status."""
        mock_active_users = [
            Mock(user_id="active1", is_active=True),
            Mock(user_id="active2", is_active=True)
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_active_users
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.list_users(active_only=True)
        
        assert len(result) == 2
        assert all(user.is_active for user in result)

    async def test_search_users_by_email_pattern(self, user_repository, mock_db_session):
        """Test searching users by email pattern."""
        mock_matching_users = [
            Mock(email="admin@company.com"),
            Mock(email="support@company.com")
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_matching_users
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.search_users_by_email_pattern("@company.com")
        
        assert len(result) == 2
        assert all("@company.com" in user.email for user in result)

    async def test_get_user_count(self, user_repository, mock_db_session):
        """Test getting total user count."""
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 25
        mock_db_session.execute.return_value = mock_count_result
        
        count = await user_repository.get_user_count()
        
        assert count == 25

    async def test_get_active_user_count(self, user_repository, mock_db_session):
        """Test getting active user count."""
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 20
        mock_db_session.execute.return_value = mock_count_result
        
        count = await user_repository.get_active_user_count()
        
        assert count == 20

    # =====================================================================
    # Validation and Error Handling Tests
    # =====================================================================

    async def test_validate_user_data_success(self, user_repository):
        """Test validating valid user data."""
        valid_user_data = {
            "user_id": "user_12345",
            "email": "test@example.com",
            "is_active": True
        }
        
        # Should not raise exception
        user_repository._validate_user_data(valid_user_data)

    async def test_validate_user_data_invalid_email(self, user_repository):
        """Test validating user data with invalid email."""
        invalid_user_data = {
            "user_id": "user_12345",
            "email": "invalid-email",
            "is_active": True
        }
        
        with pytest.raises(ValidationError):
            user_repository._validate_user_data(invalid_user_data)

    async def test_validate_user_data_missing_required_fields(self, user_repository):
        """Test validating user data with missing fields."""
        incomplete_user_data = {
            "email": "test@example.com"
            # Missing user_id
        }
        
        with pytest.raises(ValidationError):
            user_repository._validate_user_data(incomplete_user_data)

    async def test_database_constraint_error_handling(self, user_repository, mock_db_session, mock_user):
        """Test handling database constraint errors."""
        mock_db_session.commit.side_effect = IntegrityError("Foreign key constraint", None, None)
        
        with pytest.raises(ValidationError) as exc_info:
            await user_repository.create_user(mock_user)
        
        assert "constraint" in str(exc_info.value).lower()
        mock_db_session.rollback.assert_called_once()

    async def test_database_connection_error_handling(self, user_repository, mock_db_session):
        """Test handling database connection errors."""
        mock_db_session.execute.side_effect = Exception("Connection lost")
        
        with pytest.raises(Exception) as exc_info:
            await user_repository.get_user_by_id("user_12345")
        
        assert "Connection lost" in str(exc_info.value)

    # =====================================================================
    # Performance and Optimization Tests
    # =====================================================================

    async def test_bulk_create_users(self, user_repository, mock_db_session):
        """Test bulk creating multiple users."""
        mock_users = [
            User(user_id=f"user_{i}", email=f"user{i}@example.com", is_active=True)
            for i in range(5)
        ]
        
        result = await user_repository.bulk_create_users(mock_users)
        
        assert len(result) == 5
        # Should call add for each user
        assert mock_db_session.add.call_count == 5
        # Should commit only once for performance
        mock_db_session.commit.assert_called_once()

    async def test_batch_update_user_status(self, user_repository, mock_db_session):
        """Test batch updating user status."""
        user_ids = ["user_1", "user_2", "user_3"]
        
        # Mock update result
        mock_result = Mock()
        mock_result.rowcount = 3
        mock_db_session.execute.return_value = mock_result
        
        updated_count = await user_repository.batch_update_user_status(user_ids, is_active=False)
        
        assert updated_count == 3
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()

    async def test_get_users_with_profiles_joined(self, user_repository, mock_db_session):
        """Test getting users with joined profiles for performance."""
        mock_users_with_profiles = [
            Mock(user_id="user1", profile=Mock(display_name="User One")),
            Mock(user_id="user2", profile=Mock(display_name="User Two"))
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_users_with_profiles
        mock_db_session.execute.return_value = mock_result
        
        result = await user_repository.get_users_with_profiles(limit=10)
        
        assert len(result) == 2
        assert all(hasattr(user, 'profile') for user in result)

    # =====================================================================
    # Session Cleanup and Maintenance Tests
    # =====================================================================

    async def test_cleanup_old_sessions_success(self, user_repository, mock_db_session):
        """Test cleaning up old sessions."""
        days_to_keep = 30
        
        # Mock old sessions
        old_sessions = [
            Mock(session_id="old1", created_at=datetime.now() - timedelta(days=35)),
            Mock(session_id="old2", created_at=datetime.now() - timedelta(days=40))
        ]
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = old_sessions
        mock_db_session.execute.return_value = mock_result
        
        deleted_count = await user_repository.cleanup_old_sessions(days_to_keep)
        
        assert deleted_count == 2
        assert mock_db_session.delete.call_count == 2

    async def test_get_session_statistics(self, user_repository, mock_db_session):
        """Test getting session statistics."""
        mock_stats = {
            "total_sessions": 100,
            "active_sessions": 75,
            "expired_sessions": 25
        }
        
        # Mock multiple query results
        mock_total_result = Mock()
        mock_total_result.scalar.return_value = 100
        
        mock_active_result = Mock()
        mock_active_result.scalar.return_value = 75
        
        mock_expired_result = Mock()
        mock_expired_result.scalar.return_value = 25
        
        mock_db_session.execute.side_effect = [
            mock_total_result,
            mock_active_result,
            mock_expired_result
        ]
        
        stats = await user_repository.get_session_statistics()
        
        assert stats["total_sessions"] == 100
        assert stats["active_sessions"] == 75
        assert stats["expired_sessions"] == 25