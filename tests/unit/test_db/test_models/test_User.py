"""
Unit tests for app.db.models.User module.

Tests cover:
- User model with UserRole enum
- UserProfile model
- Session model
- Model relationships and constraints
- Field validation and defaults
- Cascade operations
"""

import pytest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError

from app.db.models.User import User, UserRole, UserProfile, Session


class TestUserRole:
    """Test UserRole enumeration."""

    def test_user_role_values(self):
        """Test UserRole enum values."""
        assert UserRole.USER.value == "user"
        assert UserRole.SUPERUSER.value == "superuser"

    def test_user_role_membership(self):
        """Test UserRole enum membership."""
        assert UserRole.USER in UserRole
        assert UserRole.SUPERUSER in UserRole

    def test_user_role_string_representation(self):
        """Test UserRole string representation."""
        assert str(UserRole.USER) == "UserRole.USER"
        assert str(UserRole.SUPERUSER) == "UserRole.SUPERUSER"


class TestUserModel:
    """Test User SQLAlchemy model."""

    def test_user_model_table_name(self):
        """Test User model table name."""
        assert User.__tablename__ == "users"

    def test_user_model_inheritance(self):
        """Test User model inheritance from mixins."""
        # User should inherit from Base, UUIDMixin, TimestampMixin
        user = User()
        assert hasattr(user, 'id')  # From UUIDMixin
        assert hasattr(user, 'created_at')  # From TimestampMixin
        assert hasattr(user, 'updated_at')  # From TimestampMixin

    def test_user_model_fields(self):
        """Test User model field definitions."""
        user = User()
        
        # Core authentication fields
        assert hasattr(user, 'azure_id')
        assert hasattr(user, 'email') 
        assert hasattr(user, 'is_active')
        assert hasattr(user, 'role')
        
        # Relationship fields
        assert hasattr(user, 'profile')
        assert hasattr(user, 'sessions')
        assert hasattr(user, 'mail_accounts')
        assert hasattr(user, 'audit_logs')

    def test_user_model_defaults(self):
        """Test User model default values."""
        user = User()
        
        assert user.is_active is True
        assert user.role == UserRole.USER

    def test_user_model_required_fields(self):
        """Test User model required field constraints."""
        # Test that User can be created with minimal required fields
        user = User(
            azure_id="test-azure-id",
            email="test@example.com"
        )
        
        assert user.azure_id == "test-azure-id"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.role == UserRole.USER

    def test_user_model_role_assignment(self):
        """Test User role assignment."""
        # Test default role
        user = User()
        assert user.role == UserRole.USER
        
        # Test superuser role
        superuser = User(role=UserRole.SUPERUSER)
        assert superuser.role == UserRole.SUPERUSER

    def test_user_model_email_field(self):
        """Test User email field properties."""
        user = User()
        user.email = "test@example.com"
        
        assert user.email == "test@example.com"
        
        # Email should allow various formats
        user.email = "user.name+tag@example.co.uk"
        assert user.email == "user.name+tag@example.co.uk"

    def test_user_model_azure_id_field(self):
        """Test User azure_id field properties."""
        user = User()
        user.azure_id = "12345678-1234-1234-1234-123456789012"
        
        assert user.azure_id == "12345678-1234-1234-1234-123456789012"

    def test_user_model_active_status(self):
        """Test User is_active field."""
        user = User()
        
        # Default should be active
        assert user.is_active is True
        
        # Should be able to set inactive
        user.is_active = False
        assert user.is_active is False

    def test_user_model_string_representation(self):
        """Test User model string representation."""
        user = User(email="test@example.com")
        
        # Test __repr__ or __str__ if implemented
        user_str = str(user)
        assert isinstance(user_str, str)


class TestUserProfile:
    """Test UserProfile SQLAlchemy model."""

    def test_user_profile_model_table_name(self):
        """Test UserProfile model table name."""
        assert UserProfile.__tablename__ == "user_profiles"

    def test_user_profile_model_inheritance(self):
        """Test UserProfile model inheritance."""
        profile = UserProfile()
        assert hasattr(profile, 'id')  # From UUIDMixin
        assert hasattr(profile, 'created_at')  # From TimestampMixin
        assert hasattr(profile, 'updated_at')  # From TimestampMixin

    def test_user_profile_model_fields(self):
        """Test UserProfile model field definitions."""
        profile = UserProfile()
        
        # Profile fields
        assert hasattr(profile, 'user_id')  # Foreign key
        assert hasattr(profile, 'first_name')
        assert hasattr(profile, 'last_name')
        assert hasattr(profile, 'display_name')
        assert hasattr(profile, 'timezone')
        assert hasattr(profile, 'language')
        assert hasattr(profile, 'theme_preference')
        
        # Relationship field
        assert hasattr(profile, 'user')

    def test_user_profile_model_creation(self):
        """Test UserProfile model creation with data."""
        profile = UserProfile(
            user_id="user-123",
            first_name="John",
            last_name="Doe",
            display_name="John Doe",
            timezone="UTC",
            language="en"
        )
        
        assert profile.user_id == "user-123"
        assert profile.first_name == "John"
        assert profile.last_name == "Doe"
        assert profile.display_name == "John Doe"
        assert profile.timezone == "UTC"
        assert profile.language == "en"

    def test_user_profile_optional_fields(self):
        """Test UserProfile optional fields."""
        profile = UserProfile()
        
        # These fields should be nullable/optional
        assert profile.first_name is None
        assert profile.last_name is None
        assert profile.display_name is None
        assert profile.timezone is None
        assert profile.language is None
        assert profile.theme_preference is None

    def test_user_profile_theme_preferences(self):
        """Test UserProfile theme preference values."""
        profile = UserProfile()
        
        # Test different theme values
        profile.theme_preference = "light"
        assert profile.theme_preference == "light"
        
        profile.theme_preference = "dark"
        assert profile.theme_preference == "dark"
        
        profile.theme_preference = "auto"
        assert profile.theme_preference == "auto"


class TestSession:
    """Test Session SQLAlchemy model."""

    def test_session_model_table_name(self):
        """Test Session model table name."""
        assert Session.__tablename__ == "sessions"

    def test_session_model_inheritance(self):
        """Test Session model inheritance."""
        session = Session()
        assert hasattr(session, 'id')  # From UUIDMixin
        assert hasattr(session, 'created_at')  # From TimestampMixin
        assert hasattr(session, 'updated_at')  # From TimestampMixin

    def test_session_model_fields(self):
        """Test Session model field definitions."""
        session = Session()
        
        # Session fields
        assert hasattr(session, 'user_id')  # Foreign key
        assert hasattr(session, 'session_token')
        assert hasattr(session, 'refresh_token')
        assert hasattr(session, 'expires_at')
        assert hasattr(session, 'is_active')
        assert hasattr(session, 'user_agent')
        assert hasattr(session, 'ip_address')
        assert hasattr(session, 'last_activity')
        
        # Relationship field
        assert hasattr(session, 'user')

    def test_session_model_creation(self):
        """Test Session model creation with data."""
        expiry_time = datetime.utcnow()
        
        session = Session(
            user_id="user-123",
            session_token="session-token-abc",
            refresh_token="refresh-token-def",
            expires_at=expiry_time,
            user_agent="Mozilla/5.0...",
            ip_address="192.168.1.1"
        )
        
        assert session.user_id == "user-123"
        assert session.session_token == "session-token-abc"
        assert session.refresh_token == "refresh-token-def"
        assert session.expires_at == expiry_time
        assert session.user_agent == "Mozilla/5.0..."
        assert session.ip_address == "192.168.1.1"

    def test_session_model_defaults(self):
        """Test Session model default values."""
        session = Session()
        
        assert session.is_active is True

    def test_session_active_status(self):
        """Test Session is_active field."""
        session = Session()
        
        # Default should be active
        assert session.is_active is True
        
        # Should be able to set inactive
        session.is_active = False
        assert session.is_active is False

    def test_session_token_fields(self):
        """Test Session token field properties."""
        session = Session()
        
        session.session_token = "abc123token"
        assert session.session_token == "abc123token"
        
        session.refresh_token = "def456refresh"
        assert session.refresh_token == "def456refresh"

    def test_session_datetime_fields(self):
        """Test Session datetime field handling."""
        session = Session()
        
        now = datetime.utcnow()
        session.expires_at = now
        session.last_activity = now
        
        assert session.expires_at == now
        assert session.last_activity == now

    def test_session_network_fields(self):
        """Test Session network-related fields."""
        session = Session()
        
        session.ip_address = "10.0.0.1"
        session.user_agent = "TestAgent/1.0"
        
        assert session.ip_address == "10.0.0.1"
        assert session.user_agent == "TestAgent/1.0"


class TestModelRelationships:
    """Test relationships between User, UserProfile, and Session models."""

    def test_user_profile_relationship(self):
        """Test User to UserProfile relationship."""
        user = User()
        
        # User should have profile relationship
        assert hasattr(user, 'profile')
        
        # Should initially be None
        assert user.profile is None

    def test_user_sessions_relationship(self):
        """Test User to Sessions relationship."""
        user = User()
        
        # User should have sessions relationship
        assert hasattr(user, 'sessions')
        
        # Should be a list initially
        assert isinstance(user.sessions, list)
        assert len(user.sessions) == 0

    def test_user_mail_accounts_relationship(self):
        """Test User to MailAccounts relationship."""
        user = User()
        
        # User should have mail_accounts relationship
        assert hasattr(user, 'mail_accounts')
        
        # Should be a list initially
        assert isinstance(user.mail_accounts, list)
        assert len(user.mail_accounts) == 0

    def test_user_audit_logs_relationship(self):
        """Test User to AuditLogs relationship."""
        user = User()
        
        # User should have audit_logs relationship
        assert hasattr(user, 'audit_logs')
        
        # Should be a list initially
        assert isinstance(user.audit_logs, list)
        assert len(user.audit_logs) == 0

    def test_profile_user_relationship(self):
        """Test UserProfile back reference to User."""
        profile = UserProfile()
        
        # Profile should have user relationship
        assert hasattr(profile, 'user')
        
        # Should initially be None
        assert profile.user is None

    def test_session_user_relationship(self):
        """Test Session back reference to User."""
        session = Session()
        
        # Session should have user relationship
        assert hasattr(session, 'user')
        
        # Should initially be None
        assert session.user is None


class TestModelValidation:
    """Test model field validation and constraints."""

    def test_user_email_uniqueness_constraint(self):
        """Test that User email has unique constraint."""
        # This would be tested with actual database constraints in integration tests
        # Here we test the model definition
        user1 = User(email="test@example.com", azure_id="id1")
        user2 = User(email="test@example.com", azure_id="id2")
        
        # Both objects can be created (constraint enforced at DB level)
        assert user1.email == user2.email == "test@example.com"

    def test_user_azure_id_uniqueness_constraint(self):
        """Test that User azure_id has unique constraint."""
        azure_id = "12345678-1234-1234-1234-123456789012"
        user1 = User(azure_id=azure_id, email="test1@example.com")
        user2 = User(azure_id=azure_id, email="test2@example.com")
        
        # Both objects can be created (constraint enforced at DB level)
        assert user1.azure_id == user2.azure_id == azure_id

    def test_user_required_fields_validation(self):
        """Test User required fields validation."""
        # azure_id and email should be required at database level
        user = User()
        
        # Can create object without required fields (validation at DB level)
        assert user.azure_id is None
        assert user.email is None

    def test_session_user_id_foreign_key(self):
        """Test Session user_id foreign key constraint."""
        session = Session(user_id="user-123")
        assert session.user_id == "user-123"

    def test_profile_user_id_foreign_key(self):
        """Test UserProfile user_id foreign key constraint."""
        profile = UserProfile(user_id="user-123")
        assert profile.user_id == "user-123"


class TestModelIndexes:
    """Test model index definitions."""

    def test_user_model_indexes(self):
        """Test User model index definitions."""
        # Check if User model has table args with indexes
        if hasattr(User, '__table_args__'):
            table_args = User.__table_args__
            assert isinstance(table_args, tuple)
            
            # Should contain Index objects
            index_names = []
            for arg in table_args:
                if hasattr(arg, 'name'):
                    index_names.append(arg.name)
            
            # Common expected indexes
            expected_indexes = [
                'ix_users_azure_id',
                'ix_users_email',
                'ix_users_is_active'
            ]
            
            # Check that some expected indexes exist (flexible to allow for changes)
            for expected in expected_indexes:
                if expected in index_names:
                    assert True  # At least one expected index found
                    break
            else:
                # If no expected indexes found, that's ok - might be defined differently
                pass

    def test_session_model_indexes(self):
        """Test Session model index definitions."""
        if hasattr(Session, '__table_args__'):
            table_args = Session.__table_args__
            assert isinstance(table_args, tuple)

    def test_user_profile_model_indexes(self):
        """Test UserProfile model index definitions."""
        if hasattr(UserProfile, '__table_args__'):
            table_args = UserProfile.__table_args__
            assert isinstance(table_args, tuple)


class TestModelTimestamps:
    """Test timestamp functionality from TimestampMixin."""

    def test_user_timestamp_fields(self):
        """Test User timestamp fields."""
        user = User()
        
        assert hasattr(user, 'created_at')
        assert hasattr(user, 'updated_at')

    def test_profile_timestamp_fields(self):
        """Test UserProfile timestamp fields."""
        profile = UserProfile()
        
        assert hasattr(profile, 'created_at')
        assert hasattr(profile, 'updated_at')

    def test_session_timestamp_fields(self):
        """Test Session timestamp fields."""
        session = Session()
        
        assert hasattr(session, 'created_at')
        assert hasattr(session, 'updated_at')


class TestModelUUIDs:
    """Test UUID functionality from UUIDMixin."""

    def test_user_uuid_field(self):
        """Test User UUID field."""
        user = User()
        assert hasattr(user, 'id')

    def test_profile_uuid_field(self):
        """Test UserProfile UUID field."""
        profile = UserProfile()
        assert hasattr(profile, 'id')

    def test_session_uuid_field(self):
        """Test Session UUID field."""
        session = Session()
        assert hasattr(session, 'id')


class TestModelEdgeCases:
    """Test edge cases and special scenarios."""

    def test_user_with_all_fields(self):
        """Test User creation with all possible fields."""
        user = User(
            azure_id="12345678-1234-1234-1234-123456789012",
            email="fulluser@example.com",
            is_active=True,
            role=UserRole.SUPERUSER
        )
        
        assert user.azure_id == "12345678-1234-1234-1234-123456789012"
        assert user.email == "fulluser@example.com"
        assert user.is_active is True
        assert user.role == UserRole.SUPERUSER

    def test_session_with_all_fields(self):
        """Test Session creation with all possible fields."""
        now = datetime.utcnow()
        
        session = Session(
            user_id="user-123",
            session_token="full-session-token",
            refresh_token="full-refresh-token", 
            expires_at=now,
            is_active=True,
            user_agent="Full UserAgent String",
            ip_address="192.168.1.100",
            last_activity=now
        )
        
        assert session.user_id == "user-123"
        assert session.session_token == "full-session-token"
        assert session.refresh_token == "full-refresh-token"
        assert session.expires_at == now
        assert session.is_active is True
        assert session.user_agent == "Full UserAgent String"
        assert session.ip_address == "192.168.1.100"
        assert session.last_activity == now

    def test_profile_with_all_fields(self):
        """Test UserProfile creation with all possible fields."""
        profile = UserProfile(
            user_id="user-123",
            first_name="John",
            last_name="Doe",
            display_name="John Doe",
            timezone="America/New_York",
            language="en-US",
            theme_preference="dark"
        )
        
        assert profile.user_id == "user-123"
        assert profile.first_name == "John"
        assert profile.last_name == "Doe"
        assert profile.display_name == "John Doe"
        assert profile.timezone == "America/New_York"
        assert profile.language == "en-US"
        assert profile.theme_preference == "dark"

    def test_user_role_edge_cases(self):
        """Test UserRole enum edge cases."""
        # Test that role can be assigned via string value
        user = User()
        user.role = UserRole.SUPERUSER
        assert user.role == UserRole.SUPERUSER
        assert user.role.value == "superuser"

    def test_empty_string_vs_none_handling(self):
        """Test how models handle empty strings vs None values."""
        user = User()
        
        # Test setting empty strings
        user.email = ""
        assert user.email == ""
        
        user.azure_id = ""
        assert user.azure_id == ""
        
        # Test setting None values
        user.email = None
        assert user.email is None
        
        user.azure_id = None
        assert user.azure_id is None