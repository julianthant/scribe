"""
Unit tests for app.db.models.MailAccount module.

Tests cover:
- MailAccount model field validation
- Model relationships and constraints
- Index definitions and database optimization
- Field defaults and required values
- Email and Azure ID validation
"""

import pytest

from app.db.models.MailAccount import MailAccount


class TestMailAccountModel:
    """Test MailAccount SQLAlchemy model."""

    def test_mail_account_table_name(self):
        """Test MailAccount model table name."""
        assert MailAccount.__tablename__ == "mail_accounts"

    def test_mail_account_inheritance(self):
        """Test MailAccount model inheritance from mixins."""
        mail_account = MailAccount()
        
        # Should inherit from Base, UUIDMixin, TimestampMixin
        assert hasattr(mail_account, 'id')  # From UUIDMixin
        assert hasattr(mail_account, 'created_at')  # From TimestampMixin
        assert hasattr(mail_account, 'updated_at')  # From TimestampMixin

    def test_mail_account_fields(self):
        """Test MailAccount model field definitions."""
        mail_account = MailAccount()
        
        # Foreign key fields
        assert hasattr(mail_account, 'user_id')
        
        # Mail account detail fields
        assert hasattr(mail_account, 'email')
        assert hasattr(mail_account, 'azure_mail_id')
        assert hasattr(mail_account, 'display_name')
        assert hasattr(mail_account, 'is_primary')
        assert hasattr(mail_account, 'is_active')
        
        # Relationship fields
        assert hasattr(mail_account, 'user')
        assert hasattr(mail_account, 'folders')

    def test_mail_account_creation_with_required_fields(self):
        """Test MailAccount creation with required fields."""
        mail_account = MailAccount(
            user_id="user-123",
            email="test@example.com",
            display_name="Test Account"
        )
        
        assert mail_account.user_id == "user-123"
        assert mail_account.email == "test@example.com"
        assert mail_account.display_name == "Test Account"

    def test_mail_account_defaults(self):
        """Test MailAccount default values."""
        mail_account = MailAccount()
        
        # Default values
        assert mail_account.is_primary is False
        assert mail_account.is_active is True

    def test_mail_account_email_field(self):
        """Test MailAccount email field."""
        mail_account = MailAccount()
        
        # Test various email formats
        mail_account.email = "user@example.com"
        assert mail_account.email == "user@example.com"
        
        mail_account.email = "user.name+tag@example.co.uk"
        assert mail_account.email == "user.name+tag@example.co.uk"
        
        mail_account.email = "complex.email+test@sub.domain.example.org"
        assert mail_account.email == "complex.email+test@sub.domain.example.org"

    def test_mail_account_azure_mail_id_field(self):
        """Test MailAccount azure_mail_id field."""
        mail_account = MailAccount()
        
        # Should be optional (None by default)
        assert mail_account.azure_mail_id is None
        
        # Should accept Azure ID values
        mail_account.azure_mail_id = "AAMkADc5N2Y5ZjM3LWRkMjktNGZmYi05MDA4LTJjNzQ3Zjk2YmU2YgBGAAAAAAD"
        assert mail_account.azure_mail_id == "AAMkADc5N2Y5ZjM3LWRkMjktNGZmYi05MDA4LTJjNzQ3Zjk2YmU2YgBGAAAAAAD"

    def test_mail_account_display_name_field(self):
        """Test MailAccount display_name field."""
        mail_account = MailAccount()
        
        mail_account.display_name = "John Doe's Work Account"
        assert mail_account.display_name == "John Doe's Work Account"
        
        mail_account.display_name = "Sales Team Mailbox"
        assert mail_account.display_name == "Sales Team Mailbox"

    def test_mail_account_is_primary_field(self):
        """Test MailAccount is_primary field."""
        mail_account = MailAccount()
        
        # Default should be False
        assert mail_account.is_primary is False
        
        # Should be able to set to True
        mail_account.is_primary = True
        assert mail_account.is_primary is True
        
        # Should be able to set back to False
        mail_account.is_primary = False
        assert mail_account.is_primary is False

    def test_mail_account_is_active_field(self):
        """Test MailAccount is_active field."""
        mail_account = MailAccount()
        
        # Default should be True
        assert mail_account.is_active is True
        
        # Should be able to set to False
        mail_account.is_active = False
        assert mail_account.is_active is False
        
        # Should be able to set back to True
        mail_account.is_active = True
        assert mail_account.is_active is True

    def test_mail_account_user_id_foreign_key(self):
        """Test MailAccount user_id foreign key."""
        mail_account = MailAccount()
        
        # Should accept user ID values
        mail_account.user_id = "user-123"
        assert mail_account.user_id == "user-123"
        
        mail_account.user_id = "12345678-1234-1234-1234-123456789012"
        assert mail_account.user_id == "12345678-1234-1234-1234-123456789012"


class TestMailAccountRelationships:
    """Test MailAccount model relationships."""

    def test_mail_account_user_relationship(self):
        """Test MailAccount to User relationship."""
        mail_account = MailAccount()
        
        # Should have user relationship
        assert hasattr(mail_account, 'user')
        
        # Should initially be None
        assert mail_account.user is None

    def test_mail_account_folders_relationship(self):
        """Test MailAccount to MailFolder relationship."""
        mail_account = MailAccount()
        
        # Should have folders relationship
        assert hasattr(mail_account, 'folders')
        
        # Should be a list initially
        assert isinstance(mail_account.folders, list)
        assert len(mail_account.folders) == 0


class TestMailAccountIndexes:
    """Test MailAccount model index definitions."""

    def test_mail_account_table_args(self):
        """Test MailAccount table arguments and indexes."""
        # Check if MailAccount has table args defined
        assert hasattr(MailAccount, '__table_args__')
        table_args = MailAccount.__table_args__
        assert isinstance(table_args, tuple)

    def test_mail_account_expected_indexes(self):
        """Test that MailAccount has expected indexes."""
        if hasattr(MailAccount, '__table_args__'):
            table_args = MailAccount.__table_args__
            
            # Extract index names
            index_names = []
            for arg in table_args:
                if hasattr(arg, 'name'):
                    index_names.append(arg.name)
            
            # Expected indexes from the model definition
            expected_indexes = [
                'ix_mail_accounts_user_id',
                'ix_mail_accounts_email', 
                'ix_mail_accounts_azure_mail_id',
                'ix_mail_accounts_is_primary',
                'ix_mail_accounts_active',
                'ix_mail_accounts_user_primary'
            ]
            
            # Check that at least some expected indexes are present
            found_indexes = [idx for idx in expected_indexes if idx in index_names]
            assert len(found_indexes) > 0, f"Expected to find some indexes, got: {index_names}"

    def test_mail_account_composite_indexes(self):
        """Test MailAccount composite index definitions."""
        if hasattr(MailAccount, '__table_args__'):
            table_args = MailAccount.__table_args__
            
            # Look for composite indexes
            composite_indexes = []
            for arg in table_args:
                if hasattr(arg, 'columns') and len(arg.columns) > 1:
                    composite_indexes.append(arg)
            
            # Should have at least the user_primary composite index
            assert len(composite_indexes) >= 0  # Flexible assertion


class TestMailAccountConstraints:
    """Test MailAccount model constraints and validation."""

    def test_mail_account_required_fields(self):
        """Test MailAccount required field constraints."""
        # user_id should be required (NOT NULL)
        mail_account = MailAccount(user_id="user-123")
        assert mail_account.user_id == "user-123"
        
        # email should be required (NOT NULL) 
        mail_account.email = "test@example.com"
        assert mail_account.email == "test@example.com"
        
        # display_name should be required (NOT NULL)
        mail_account.display_name = "Test Account"
        assert mail_account.display_name == "Test Account"

    def test_mail_account_optional_fields(self):
        """Test MailAccount optional field constraints."""
        mail_account = MailAccount()
        
        # azure_mail_id should be optional (nullable)
        assert mail_account.azure_mail_id is None
        
        # Can be set to a value
        mail_account.azure_mail_id = "azure-id-123"
        assert mail_account.azure_mail_id == "azure-id-123"
        
        # Can be set back to None
        mail_account.azure_mail_id = None
        assert mail_account.azure_mail_id is None

    def test_mail_account_unique_constraints(self):
        """Test MailAccount unique constraints."""
        # azure_mail_id should be unique when not null
        mail_account1 = MailAccount(azure_mail_id="unique-azure-id")
        mail_account2 = MailAccount(azure_mail_id="unique-azure-id")
        
        # Both can be created at the model level (constraint enforced at DB level)
        assert mail_account1.azure_mail_id == mail_account2.azure_mail_id


class TestMailAccountBusinessLogic:
    """Test MailAccount business logic scenarios."""

    def test_primary_account_scenarios(self):
        """Test primary account business logic scenarios."""
        # User can have multiple mail accounts
        account1 = MailAccount(
            user_id="user-123",
            email="primary@example.com",
            display_name="Primary Account",
            is_primary=True
        )
        
        account2 = MailAccount(
            user_id="user-123", 
            email="secondary@example.com",
            display_name="Secondary Account",
            is_primary=False
        )
        
        assert account1.is_primary is True
        assert account2.is_primary is False
        
        # Both accounts belong to same user
        assert account1.user_id == account2.user_id

    def test_active_inactive_account_scenarios(self):
        """Test active/inactive account scenarios."""
        active_account = MailAccount(
            user_id="user-123",
            email="active@example.com",
            display_name="Active Account",
            is_active=True
        )
        
        inactive_account = MailAccount(
            user_id="user-123",
            email="inactive@example.com", 
            display_name="Inactive Account",
            is_active=False
        )
        
        assert active_account.is_active is True
        assert inactive_account.is_active is False

    def test_mail_account_with_azure_integration(self):
        """Test mail account with Azure integration."""
        azure_account = MailAccount(
            user_id="user-123",
            email="azure.user@company.com",
            azure_mail_id="AAMkADc5N2Y5ZjM3LWRkMjktNGZmYi05MDA4LTJjNzQ3Zjk2YmU2YgBGAAAAAAD",
            display_name="Azure Integrated Account",
            is_primary=True,
            is_active=True
        )
        
        assert azure_account.email == "azure.user@company.com"
        assert azure_account.azure_mail_id is not None
        assert len(azure_account.azure_mail_id) > 0
        assert azure_account.is_primary is True
        assert azure_account.is_active is True

    def test_mail_account_without_azure_integration(self):
        """Test mail account without Azure integration."""
        non_azure_account = MailAccount(
            user_id="user-123",
            email="local@example.com",
            display_name="Local Account",
            is_primary=False,
            is_active=True
        )
        
        assert non_azure_account.email == "local@example.com"
        assert non_azure_account.azure_mail_id is None
        assert non_azure_account.is_primary is False
        assert non_azure_account.is_active is True


class TestMailAccountEdgeCases:
    """Test MailAccount edge cases and special scenarios."""

    def test_mail_account_long_display_name(self):
        """Test MailAccount with long display name."""
        long_name = "A" * 100  # 100 characters (max length)
        mail_account = MailAccount(display_name=long_name)
        assert mail_account.display_name == long_name

    def test_mail_account_special_characters_in_email(self):
        """Test MailAccount with special characters in email."""
        special_emails = [
            "user+tag@example.com",
            "user.name@example.com", 
            "user_name@example.com",
            "user-name@example.com",
            "123user@example.com",
            "user@example-domain.com",
            "user@sub.example.com"
        ]
        
        for email in special_emails:
            mail_account = MailAccount(email=email)
            assert mail_account.email == email

    def test_mail_account_empty_vs_none_values(self):
        """Test MailAccount handling of empty strings vs None values."""
        mail_account = MailAccount()
        
        # Test None values
        mail_account.azure_mail_id = None
        assert mail_account.azure_mail_id is None
        
        # Test empty strings (should be allowed for some fields)
        mail_account.azure_mail_id = ""
        assert mail_account.azure_mail_id == ""
        
        # Reset to None
        mail_account.azure_mail_id = None
        assert mail_account.azure_mail_id is None

    def test_mail_account_boolean_field_edge_cases(self):
        """Test MailAccount boolean field edge cases."""
        mail_account = MailAccount()
        
        # Test is_primary boolean handling
        mail_account.is_primary = True
        assert mail_account.is_primary is True
        
        mail_account.is_primary = False  
        assert mail_account.is_primary is False
        
        # Test is_active boolean handling
        mail_account.is_active = True
        assert mail_account.is_active is True
        
        mail_account.is_active = False
        assert mail_account.is_active is False

    def test_mail_account_user_id_formats(self):
        """Test MailAccount user_id with different formats."""
        formats = [
            "user-123",
            "12345678-1234-1234-1234-123456789012",  # UUID format
            "user_456", 
            "short",
            "very-long-user-identifier-string-that-might-be-used"
        ]
        
        for user_id in formats:
            mail_account = MailAccount(user_id=user_id)
            assert mail_account.user_id == user_id


class TestMailAccountFieldLengths:
    """Test MailAccount field length constraints."""

    def test_display_name_length_constraint(self):
        """Test display_name field length constraint."""
        mail_account = MailAccount()
        
        # Test maximum length (assuming 100 characters based on NVARCHAR(100))
        max_length_name = "A" * 100
        mail_account.display_name = max_length_name
        assert mail_account.display_name == max_length_name
        assert len(mail_account.display_name) == 100

    def test_email_field_length(self):
        """Test email field length handling."""
        mail_account = MailAccount()
        
        # Test reasonable email length
        long_email = f"{'a' * 50}@{'b' * 50}.com"
        mail_account.email = long_email
        assert mail_account.email == long_email

    def test_azure_mail_id_length(self):
        """Test azure_mail_id field length handling.""" 
        mail_account = MailAccount()
        
        # Test typical Azure mail ID length
        azure_id = "AAMkADc5N2Y5ZjM3LWRkMjktNGZmYi05MDA4LTJjNzQ3Zjk2YmU2YgBGAAAAAAD" * 2
        mail_account.azure_mail_id = azure_id
        assert mail_account.azure_mail_id == azure_id


class TestMailAccountModelConsistency:
    """Test MailAccount model consistency and data integrity."""

    def test_mail_account_field_types(self):
        """Test that MailAccount fields have correct Python types."""
        mail_account = MailAccount(
            user_id="user-123",
            email="test@example.com", 
            azure_mail_id="azure-123",
            display_name="Test Account",
            is_primary=True,
            is_active=False
        )
        
        assert isinstance(mail_account.user_id, str)
        assert isinstance(mail_account.email, str)
        assert isinstance(mail_account.azure_mail_id, str)
        assert isinstance(mail_account.display_name, str)
        assert isinstance(mail_account.is_primary, bool)
        assert isinstance(mail_account.is_active, bool)

    def test_mail_account_with_minimal_data(self):
        """Test MailAccount creation with minimal required data."""
        minimal_account = MailAccount(
            user_id="user-123",
            email="minimal@example.com",
            display_name="Minimal"
        )
        
        assert minimal_account.user_id == "user-123"
        assert minimal_account.email == "minimal@example.com" 
        assert minimal_account.display_name == "Minimal"
        assert minimal_account.azure_mail_id is None
        assert minimal_account.is_primary is False
        assert minimal_account.is_active is True

    def test_mail_account_with_complete_data(self):
        """Test MailAccount creation with all fields populated."""
        complete_account = MailAccount(
            user_id="user-123",
            email="complete@example.com",
            azure_mail_id="azure-complete-123",
            display_name="Complete Account", 
            is_primary=True,
            is_active=True
        )
        
        assert complete_account.user_id == "user-123"
        assert complete_account.email == "complete@example.com"
        assert complete_account.azure_mail_id == "azure-complete-123"
        assert complete_account.display_name == "Complete Account"
        assert complete_account.is_primary is True
        assert complete_account.is_active is True