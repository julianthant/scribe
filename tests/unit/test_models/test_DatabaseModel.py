"""
test_DatabaseModel.py - Unit tests for database models and mixins

Tests all database models and components in app.models.DatabaseModel including:
- Base: Core declarative base class with async support
- TimestampMixin: Automatic created_at/updated_at timestamps
- UUIDMixin: UUID primary key with SQL Server NEWID()
- SoftDeleteMixin: Soft delete functionality
- Enums: UserRole, PermissionType, SyncStatus, EntityType
- Column factories: create_email_column, create_azure_id_column
- Index helpers: create_composite_index

Tests include model structure, column definitions, enum values, and factory functions.
"""

import pytest
from datetime import datetime
from enum import Enum
from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.dialects.mssql import NVARCHAR, UNIQUEIDENTIFIER
from sqlalchemy.orm import Mapped
from unittest.mock import Mock, patch

from app.models.DatabaseModel import (
    Base,
    TimestampMixin,
    UUIDMixin,
    SoftDeleteMixin,
    UserRole,
    PermissionType,
    SyncStatus,
    EntityType,
    create_email_column,
    create_azure_id_column,
    create_composite_index
)


class TestBase:
    """Test cases for Base declarative class."""

    def test_base_is_declarative_base(self):
        """Test that Base is a proper SQLAlchemy DeclarativeBase."""
        # Act & Assert
        from sqlalchemy.orm import DeclarativeBase
        from sqlalchemy.ext.asyncio import AsyncAttrs
        
        assert issubclass(Base, DeclarativeBase)
        assert issubclass(Base, AsyncAttrs)

    def test_base_has_mapper_args(self):
        """Test that Base has proper mapper configuration."""
        # Act & Assert
        assert hasattr(Base, "__mapper_args__")
        assert Base.__mapper_args__.get("eager_defaults") is True

    def test_base_can_be_subclassed(self):
        """Test that Base can be used as parent class."""
        # Arrange & Act
        class TestModel(Base):
            __tablename__ = "test_model"
            
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

        # Assert
        assert TestModel.__tablename__ == "test_model"
        assert hasattr(TestModel, "id")
        assert hasattr(TestModel, "name")
        assert issubclass(TestModel, Base)


class TestTimestampMixin:
    """Test cases for TimestampMixin."""

    def test_timestamp_mixin_has_required_fields(self):
        """Test that TimestampMixin has created_at and updated_at fields."""
        # Act & Assert
        assert hasattr(TimestampMixin, "created_at")
        assert hasattr(TimestampMixin, "updated_at")

    def test_timestamp_mixin_created_at_configuration(self):
        """Test created_at field configuration."""
        # Arrange
        created_at_column = TimestampMixin.created_at

        # Act & Assert
        assert created_at_column.property.columns[0].type.python_type == datetime
        assert created_at_column.property.columns[0].nullable is False
        assert created_at_column.property.columns[0].comment == "Record creation timestamp"
        assert created_at_column.property.columns[0].server_default is not None

    def test_timestamp_mixin_updated_at_configuration(self):
        """Test updated_at field configuration."""
        # Arrange
        updated_at_column = TimestampMixin.updated_at

        # Act & Assert
        assert updated_at_column.property.columns[0].type.python_type == datetime
        assert updated_at_column.property.columns[0].nullable is False
        assert updated_at_column.property.columns[0].comment == "Record last update timestamp"
        assert updated_at_column.property.columns[0].server_default is not None
        assert updated_at_column.property.columns[0].onupdate is not None

    def test_timestamp_mixin_can_be_used_in_model(self):
        """Test that TimestampMixin can be used in a model class."""
        # Arrange & Act
        class TestTimestampModel(Base, TimestampMixin):
            __tablename__ = "test_timestamp_model"
            
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

        # Assert
        assert hasattr(TestTimestampModel, "created_at")
        assert hasattr(TestTimestampModel, "updated_at")
        assert hasattr(TestTimestampModel, "id")
        assert hasattr(TestTimestampModel, "name")


class TestUUIDMixin:
    """Test cases for UUIDMixin."""

    def test_uuid_mixin_has_id_field(self):
        """Test that UUIDMixin has id field."""
        # Act & Assert
        assert hasattr(UUIDMixin, "id")

    def test_uuid_mixin_id_configuration(self):
        """Test id field configuration."""
        # Arrange
        id_column = UUIDMixin.id

        # Act & Assert
        assert id_column.property.columns[0].type.__class__.__name__ == "UNIQUEIDENTIFIER"
        assert id_column.property.columns[0].primary_key is True
        assert id_column.property.columns[0].comment == "Unique identifier"
        assert id_column.property.columns[0].server_default is not None

    def test_uuid_mixin_can_be_used_in_model(self):
        """Test that UUIDMixin can be used in a model class."""
        # Arrange & Act
        class TestUUIDModel(Base, UUIDMixin):
            __tablename__ = "test_uuid_model"
            
            name: Mapped[str] = mapped_column(String(50))

        # Assert
        assert hasattr(TestUUIDModel, "id")
        assert hasattr(TestUUIDModel, "name")


class TestSoftDeleteMixin:
    """Test cases for SoftDeleteMixin."""

    def test_soft_delete_mixin_has_required_fields(self):
        """Test that SoftDeleteMixin has is_deleted and deleted_at fields."""
        # Act & Assert
        assert hasattr(SoftDeleteMixin, "is_deleted")
        assert hasattr(SoftDeleteMixin, "deleted_at")

    def test_soft_delete_mixin_is_deleted_configuration(self):
        """Test is_deleted field configuration."""
        # Arrange
        is_deleted_column = SoftDeleteMixin.is_deleted

        # Act & Assert
        assert is_deleted_column.property.columns[0].type.python_type == bool
        assert is_deleted_column.property.columns[0].nullable is False
        assert is_deleted_column.property.columns[0].comment == "Soft delete flag"
        assert is_deleted_column.property.columns[0].server_default is not None

    def test_soft_delete_mixin_deleted_at_configuration(self):
        """Test deleted_at field configuration."""
        # Arrange
        deleted_at_column = SoftDeleteMixin.deleted_at

        # Act & Assert
        assert deleted_at_column.property.columns[0].type.python_type == datetime
        assert deleted_at_column.property.columns[0].nullable is True
        assert deleted_at_column.property.columns[0].comment == "Soft delete timestamp"

    def test_soft_delete_mixin_can_be_used_in_model(self):
        """Test that SoftDeleteMixin can be used in a model class."""
        # Arrange & Act
        class TestSoftDeleteModel(Base, SoftDeleteMixin):
            __tablename__ = "test_soft_delete_model"
            
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

        # Assert
        assert hasattr(TestSoftDeleteModel, "is_deleted")
        assert hasattr(TestSoftDeleteModel, "deleted_at")
        assert hasattr(TestSoftDeleteModel, "id")
        assert hasattr(TestSoftDeleteModel, "name")


class TestUserRole:
    """Test cases for UserRole enum."""

    def test_user_role_is_enum(self):
        """Test that UserRole is a proper enum."""
        # Act & Assert
        from enum import Enum
        assert issubclass(UserRole, Enum)

    def test_user_role_has_correct_values(self):
        """Test that UserRole has correct enum values."""
        # Act & Assert
        assert UserRole.USER.value == "user"
        assert UserRole.SUPERUSER.value == "superuser"

    def test_user_role_has_only_expected_members(self):
        """Test that UserRole has only expected members."""
        # Act
        members = list(UserRole)

        # Assert
        assert len(members) == 2
        assert UserRole.USER in members
        assert UserRole.SUPERUSER in members

    def test_user_role_string_representation(self):
        """Test UserRole string representation."""
        # Act & Assert
        assert str(UserRole.USER) == "UserRole.USER"
        assert str(UserRole.SUPERUSER) == "UserRole.SUPERUSER"

    def test_user_role_comparison(self):
        """Test UserRole enum comparison."""
        # Act & Assert
        assert UserRole.USER == UserRole.USER
        assert UserRole.SUPERUSER == UserRole.SUPERUSER
        assert UserRole.USER != UserRole.SUPERUSER


class TestPermissionType:
    """Test cases for PermissionType enum."""

    def test_permission_type_is_enum(self):
        """Test that PermissionType is a proper enum."""
        # Act & Assert
        from enum import Enum
        assert issubclass(PermissionType, Enum)

    def test_permission_type_has_correct_values(self):
        """Test that PermissionType has correct enum values."""
        # Act & Assert
        assert PermissionType.READ.value == "read"
        assert PermissionType.SEND.value == "send"
        assert PermissionType.DELETE.value == "delete"
        assert PermissionType.MANAGE.value == "manage"

    def test_permission_type_has_only_expected_members(self):
        """Test that PermissionType has only expected members."""
        # Act
        members = list(PermissionType)

        # Assert
        assert len(members) == 4
        assert PermissionType.READ in members
        assert PermissionType.SEND in members
        assert PermissionType.DELETE in members
        assert PermissionType.MANAGE in members

    @pytest.mark.parametrize("permission,expected_value", [
        (PermissionType.READ, "read"),
        (PermissionType.SEND, "send"),
        (PermissionType.DELETE, "delete"),
        (PermissionType.MANAGE, "manage"),
    ])
    def test_permission_type_values(self, permission, expected_value):
        """Test PermissionType enum values."""
        # Act & Assert
        assert permission.value == expected_value


class TestSyncStatus:
    """Test cases for SyncStatus enum."""

    def test_sync_status_is_enum(self):
        """Test that SyncStatus is a proper enum."""
        # Act & Assert
        from enum import Enum
        assert issubclass(SyncStatus, Enum)

    def test_sync_status_has_correct_values(self):
        """Test that SyncStatus has correct enum values."""
        # Act & Assert
        assert SyncStatus.PENDING.value == "pending"
        assert SyncStatus.SYNCING.value == "syncing"
        assert SyncStatus.SUCCESS.value == "success"
        assert SyncStatus.ERROR.value == "error"

    def test_sync_status_has_only_expected_members(self):
        """Test that SyncStatus has only expected members."""
        # Act
        members = list(SyncStatus)

        # Assert
        assert len(members) == 4
        assert SyncStatus.PENDING in members
        assert SyncStatus.SYNCING in members
        assert SyncStatus.SUCCESS in members
        assert SyncStatus.ERROR in members

    def test_sync_status_workflow_progression(self):
        """Test typical sync status workflow progression."""
        # Arrange - Typical workflow states
        workflow = [
            SyncStatus.PENDING,
            SyncStatus.SYNCING,
            SyncStatus.SUCCESS  # or ERROR
        ]

        # Act & Assert
        assert workflow[0] == SyncStatus.PENDING
        assert workflow[1] == SyncStatus.SYNCING
        assert workflow[2] in [SyncStatus.SUCCESS, SyncStatus.ERROR]


class TestEntityType:
    """Test cases for EntityType enum."""

    def test_entity_type_is_enum(self):
        """Test that EntityType is a proper enum."""
        # Act & Assert
        from enum import Enum
        assert issubclass(EntityType, Enum)

    def test_entity_type_has_correct_values(self):
        """Test that EntityType has correct enum values."""
        # Act & Assert
        assert EntityType.MAIL_ACCOUNT.value == "mail_account"
        assert EntityType.SHARED_MAILBOX.value == "shared_mailbox"

    def test_entity_type_has_only_expected_members(self):
        """Test that EntityType has only expected members."""
        # Act
        members = list(EntityType)

        # Assert
        assert len(members) == 2
        assert EntityType.MAIL_ACCOUNT in members
        assert EntityType.SHARED_MAILBOX in members


class TestCreateEmailColumn:
    """Test cases for create_email_column factory function."""

    def test_create_email_column_default_parameters(self):
        """Test create_email_column with default parameters."""
        # Act
        column = create_email_column()

        # Assert
        assert column.property.columns[0].type.__class__.__name__ == "NVARCHAR"
        assert column.property.columns[0].type.length == 320  # RFC 5321 max length
        assert column.property.columns[0].nullable is False  # Default
        assert column.property.columns[0].unique is False     # Default
        assert column.property.columns[0].comment == "Email address"

    def test_create_email_column_nullable_parameter(self):
        """Test create_email_column with nullable parameter."""
        # Act
        nullable_column = create_email_column(nullable=True)
        non_nullable_column = create_email_column(nullable=False)

        # Assert
        assert nullable_column.property.columns[0].nullable is True
        assert non_nullable_column.property.columns[0].nullable is False

    def test_create_email_column_unique_parameter(self):
        """Test create_email_column with unique parameter."""
        # Act
        unique_column = create_email_column(unique=True)
        non_unique_column = create_email_column(unique=False)

        # Assert
        assert unique_column.property.columns[0].unique is True
        assert non_unique_column.property.columns[0].unique is False

    def test_create_email_column_combined_parameters(self):
        """Test create_email_column with combined parameters."""
        # Act
        column = create_email_column(nullable=True, unique=True)

        # Assert
        assert column.property.columns[0].nullable is True
        assert column.property.columns[0].unique is True
        assert column.property.columns[0].type.length == 320

    @pytest.mark.parametrize("nullable,unique", [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ])
    def test_create_email_column_parameter_combinations(self, nullable, unique):
        """Test create_email_column with various parameter combinations."""
        # Act
        column = create_email_column(nullable=nullable, unique=unique)

        # Assert
        assert column.property.columns[0].nullable == nullable
        assert column.property.columns[0].unique == unique


class TestCreateAzureIdColumn:
    """Test cases for create_azure_id_column factory function."""

    def test_create_azure_id_column_default_parameters(self):
        """Test create_azure_id_column with default parameters."""
        # Act
        column = create_azure_id_column()

        # Assert
        assert column.property.columns[0].type.__class__.__name__ == "NVARCHAR"
        assert column.property.columns[0].type.length == 36  # Azure AD GUID length
        assert column.property.columns[0].nullable is True   # Default
        assert column.property.columns[0].unique is False    # Default
        assert column.property.columns[0].comment == "Azure AD object identifier"

    def test_create_azure_id_column_nullable_parameter(self):
        """Test create_azure_id_column with nullable parameter."""
        # Act
        nullable_column = create_azure_id_column(nullable=True)
        non_nullable_column = create_azure_id_column(nullable=False)

        # Assert
        assert nullable_column.property.columns[0].nullable is True
        assert non_nullable_column.property.columns[0].nullable is False

    def test_create_azure_id_column_unique_parameter(self):
        """Test create_azure_id_column with unique parameter."""
        # Act
        unique_column = create_azure_id_column(unique=True)
        non_unique_column = create_azure_id_column(unique=False)

        # Assert
        assert unique_column.property.columns[0].unique is True
        assert non_unique_column.property.columns[0].unique is False

    def test_create_azure_id_column_combined_parameters(self):
        """Test create_azure_id_column with combined parameters."""
        # Act
        column = create_azure_id_column(nullable=False, unique=True)

        # Assert
        assert column.property.columns[0].nullable is False
        assert column.property.columns[0].unique is True
        assert column.property.columns[0].type.length == 36

    def test_create_azure_id_column_guid_length_validation(self):
        """Test that Azure ID column has correct GUID length."""
        # Act
        column = create_azure_id_column()

        # Assert - Azure AD GUIDs are 36 characters (including hyphens)
        assert column.property.columns[0].type.length == 36


class TestCreateCompositeIndex:
    """Test cases for create_composite_index helper function."""

    def test_create_composite_index_single_column(self):
        """Test create_composite_index with single column."""
        # Act
        index = create_composite_index("users", "email")

        # Assert
        assert isinstance(index, Index)
        assert index.name == "ix_users_email"
        assert len(index.columns) == 1

    def test_create_composite_index_multiple_columns(self):
        """Test create_composite_index with multiple columns."""
        # Act
        index = create_composite_index("users", "tenant_id", "email")

        # Assert
        assert isinstance(index, Index)
        assert index.name == "ix_users_tenant_id_email"
        assert len(index.columns) == 2

    def test_create_composite_index_many_columns(self):
        """Test create_composite_index with many columns."""
        # Act
        index = create_composite_index("audit_logs", "entity_type", "entity_id", "action", "timestamp")

        # Assert
        assert isinstance(index, Index)
        assert index.name == "ix_audit_logs_entity_type_entity_id_action_timestamp"
        assert len(index.columns) == 4

    @pytest.mark.parametrize("table_name,columns,expected_name", [
        ("users", ["id"], "ix_users_id"),
        ("mail_accounts", ["user_id", "provider"], "ix_mail_accounts_user_id_provider"),
        ("sync_operations", ["entity_type", "status"], "ix_sync_operations_entity_type_status"),
        ("shared_mailbox_permissions", ["mailbox_id", "user_id", "permission_type"], 
         "ix_shared_mailbox_permissions_mailbox_id_user_id_permission_type"),
    ])
    def test_create_composite_index_naming_convention(self, table_name, columns, expected_name):
        """Test create_composite_index naming convention."""
        # Act
        index = create_composite_index(table_name, *columns)

        # Assert
        assert index.name == expected_name


class TestMixinCombinations:
    """Test cases for combining multiple mixins."""

    def test_all_mixins_combined(self):
        """Test combining all mixins in a single model."""
        # Arrange & Act
        class FullFeatureModel(Base, TimestampMixin, UUIDMixin, SoftDeleteMixin):
            __tablename__ = "full_feature_model"
            
            name: Mapped[str] = mapped_column(String(100))

        # Assert
        assert hasattr(FullFeatureModel, "id")          # UUIDMixin
        assert hasattr(FullFeatureModel, "created_at")   # TimestampMixin
        assert hasattr(FullFeatureModel, "updated_at")   # TimestampMixin
        assert hasattr(FullFeatureModel, "is_deleted")   # SoftDeleteMixin
        assert hasattr(FullFeatureModel, "deleted_at")   # SoftDeleteMixin
        assert hasattr(FullFeatureModel, "name")         # Custom field

    def test_selective_mixin_combination(self):
        """Test combining selective mixins."""
        # Arrange & Act
        class SelectiveModel(Base, TimestampMixin, SoftDeleteMixin):
            __tablename__ = "selective_model"
            
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(100))

        # Assert
        assert hasattr(SelectiveModel, "id")          # Custom field (not UUID)
        assert hasattr(SelectiveModel, "created_at")   # TimestampMixin
        assert hasattr(SelectiveModel, "updated_at")   # TimestampMixin
        assert hasattr(SelectiveModel, "is_deleted")   # SoftDeleteMixin
        assert hasattr(SelectiveModel, "deleted_at")   # SoftDeleteMixin
        assert hasattr(SelectiveModel, "name")         # Custom field


class TestModelIntegration:
    """Integration tests for database model components."""

    def test_realistic_user_model_example(self):
        """Test a realistic user model using the components."""
        # Arrange & Act
        class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
            __tablename__ = "users"
            
            email: Mapped[str] = create_email_column(nullable=False, unique=True)
            azure_id: Mapped[str] = create_azure_id_column(nullable=False, unique=True)
            role: Mapped[UserRole] = mapped_column(default=UserRole.USER)

        # Assert - Model structure
        assert User.__tablename__ == "users"
        assert hasattr(User, "id")
        assert hasattr(User, "email")
        assert hasattr(User, "azure_id")
        assert hasattr(User, "role")
        assert hasattr(User, "created_at")
        assert hasattr(User, "updated_at")
        assert hasattr(User, "is_deleted")
        assert hasattr(User, "deleted_at")

    def test_realistic_mailbox_model_example(self):
        """Test a realistic mailbox model using the components."""
        # Arrange & Act
        class SharedMailbox(Base, UUIDMixin, TimestampMixin):
            __tablename__ = "shared_mailboxes"
            
            email: Mapped[str] = create_email_column(nullable=False, unique=True)
            azure_id: Mapped[str] = create_azure_id_column(nullable=False, unique=True)
            sync_status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.PENDING)

        # Assert
        assert SharedMailbox.__tablename__ == "shared_mailboxes"
        assert hasattr(SharedMailbox, "email")
        assert hasattr(SharedMailbox, "azure_id")
        assert hasattr(SharedMailbox, "sync_status")

    def test_enum_usage_in_models(self):
        """Test that enums can be used properly in models."""
        # Arrange & Act
        class TestModel(Base):
            __tablename__ = "test_enum_model"
            
            id: Mapped[int] = mapped_column(primary_key=True)
            user_role: Mapped[UserRole] = mapped_column(default=UserRole.USER)
            permission: Mapped[PermissionType] = mapped_column(default=PermissionType.READ)
            sync_status: Mapped[SyncStatus] = mapped_column(default=SyncStatus.PENDING)
            entity_type: Mapped[EntityType] = mapped_column(default=EntityType.MAIL_ACCOUNT)

        # Assert
        assert hasattr(TestModel, "user_role")
        assert hasattr(TestModel, "permission")
        assert hasattr(TestModel, "sync_status")
        assert hasattr(TestModel, "entity_type")


class TestDatabaseModelDocumentation:
    """Test that models have proper documentation and structure."""

    def test_all_enums_have_proper_values(self):
        """Test that all enums have expected string values."""
        # User roles
        assert all(isinstance(role.value, str) for role in UserRole)
        
        # Permission types
        assert all(isinstance(perm.value, str) for perm in PermissionType)
        
        # Sync statuses
        assert all(isinstance(status.value, str) for status in SyncStatus)
        
        # Entity types
        assert all(isinstance(entity.value, str) for entity in EntityType)

    def test_column_factories_return_mapped_columns(self):
        """Test that column factories return proper Mapped types."""
        # Act
        email_column = create_email_column()
        azure_id_column = create_azure_id_column()

        # Assert
        assert hasattr(email_column, "property")
        assert hasattr(azure_id_column, "property")

    def test_mixins_have_proper_column_types(self):
        """Test that mixins define columns with correct types."""
        # TimestampMixin
        assert TimestampMixin.created_at.property.columns[0].type.__class__.__name__ == "DateTime"
        assert TimestampMixin.updated_at.property.columns[0].type.__class__.__name__ == "DateTime"
        
        # UUIDMixin
        assert UUIDMixin.id.property.columns[0].type.__class__.__name__ == "UNIQUEIDENTIFIER"
        
        # SoftDeleteMixin
        assert SoftDeleteMixin.is_deleted.property.columns[0].type.__class__.__name__ == "Boolean"
        assert SoftDeleteMixin.deleted_at.property.columns[0].type.__class__.__name__ == "DateTime"