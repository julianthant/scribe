# Scribe FastAPI Development Standards

This document serves as the authoritative guide for all development practices, organizational structure, and coding standards for the Scribe FastAPI application.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Configuration Management](#configuration-management)
3. [Naming Conventions](#naming-conventions)
4. [Coding Standards](#coding-standards)
5. [Code Patterns](#code-patterns)
6. [Documentation Requirements](#documentation-requirements)
7. [Security Standards](#security-standards)
8. [Testing Requirements](#testing-requirements)
9. [Error Handling](#error-handling)
10. [Development Workflow](#development-workflow)
11. [Performance Guidelines](#performance-guidelines)

## Project Structure

### Directory Organization

```
scribe/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API endpoints & routing
│   │   ├── __init__.py
│   │   └── v1/                 # API version 1
│   │       ├── __init__.py
│   │       ├── endpoints/      # Route handlers
│   │       │   ├── __init__.py
│   │       │   ├── Auth.py     # Authentication endpoints
│   │       │   ├── Mail.py     # Mail endpoints
│   │       │   └── SharedMailbox.py # Shared mailbox endpoints
│   │       └── router.py       # Main router for v1
│   ├── azure/                  # Azure services integration
│   │   ├── __init__.py
│   │   ├── AzureAuthService.py # Azure AD authentication
│   │   ├── AzureGraphService.py # Graph API base operations
│   │   └── AzureMailService.py # Mail-specific operations
│   ├── core/                   # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration settings (Dynaconf)
│   │   ├── Cache.py            # Caching utilities
│   │   ├── Logging.py          # Logging configuration
│   │   └── Exceptions.py       # Custom exceptions
│   ├── dependencies/           # Dependency injection
│   │   ├── __init__.py
│   │   ├── Auth.py            # Authentication dependencies
│   │   ├── Mail.py            # Mail dependencies
│   │   └── SharedMailbox.py   # Shared mailbox dependencies
│   ├── models/                 # Pydantic models & schemas
│   │   ├── __init__.py
│   │   ├── Auth.py             # Authentication models
│   │   ├── Default.py          # Default FastAPI models
│   │   ├── Mail.py             # Mail models
│   │   └── SharedMailbox.py    # Shared mailbox models
│   ├── services/              # Business logic layer
│   │   ├── __init__.py
│   │   ├── OAuthService.py     # OAuth authentication service
│   │   ├── MailService.py      # Mail operations service
│   │   ├── SharedMailboxService.py # Shared mailbox service
│   │   └── VoiceAttachmentService.py # Voice attachment service
│   ├── repositories/          # Data access layer
│   │   ├── __init__.py
│   │   ├── MailRepository.py   # Mail data access
│   │   └── SharedMailboxRepository.py # Shared mailbox data access
│   ├── utils/                 # Utility functions & helpers
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   └── helpers.py
│   └── middleware/            # Custom middleware
│       ├── __init__.py
│       ├── cors.py
│       └── rate_limiting.py
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration
│   ├── unit/                 # Unit tests
│   │   └── __init__.py
│   └── integration/          # Integration tests
│       └── __init__.py
├── docs/                     # Documentation
│   ├── api/                  # OpenAPI specifications
│   ├── architecture/         # System design documents
│   ├── guides/              # How-to guides
│   ├── changelog/           # Version history
│   └── decisions/           # Architecture Decision Records (ADRs)
├── scripts/                 # Utility scripts
│   ├── migrate.py
│   └── seed_data.py
├── migrations/              # Database migrations (Alembic)
├── settings.toml            # Non-sensitive configuration (TOML format)
├── .secrets.toml            # Sensitive credentials (gitignored)
├── .env.example             # Environment variable template (optional)
├── .secrets.example         # Secrets template for onboarding
├── .gitignore
├── requirements.txt
├── pyproject.toml          # Project configuration
├── README.md
└── CLAUDE.md               # This file
```

## Configuration Management

### Dynaconf Configuration Best Practices

The Scribe application uses **Dynaconf** with a **TOML-only approach** for robust, maintainable configuration management. This approach follows 12-factor app principles while maintaining clear separation between sensitive and non-sensitive data.

#### Core Configuration Philosophy

1. **Clear Separation**: Sensitive data (passwords, secrets) vs non-sensitive data (hosts, ports, features)
2. **TOML Format**: Use TOML for all configuration files (more readable than .env for complex structures)
3. **Environment-Specific**: Support for development, production, testing environments
4. **Override Hierarchy**: Files → Environment Variables → Runtime
5. **Version Control Safety**: Never commit sensitive data

#### Configuration Files

**settings.toml** - Non-sensitive application settings
```toml
[default]
# Application metadata
app_name = "Scribe API"
app_version = "1.0.0"
debug = false
api_v1_prefix = "/api/v1"

# Database connection info (NO credentials)
database_server = "scribe.database.windows.net"
database_name = "scribev-vm-database"
database_pool_size = 10

# In-Memory Cache Configuration (Azure Functions optimized)
cache_default_ttl = 300
cache_max_size = 1000
cache_cleanup_interval = 180

# Feature flags and business logic
enable_rls = true
enable_multi_tenant = true

[development]
debug = true
log_level = "DEBUG"
database_echo = true

[production]  
debug = false
log_level = "INFO"
log_async_enabled = true
```

**.secrets.toml** - Sensitive credentials only (gitignored)
```toml
[default]
# Core security secrets (empty in repo, set via env vars in production)
secret_key = ""           # Set via SCRIBE_SECRET_KEY
jwt_secret = ""           # Set via SCRIBE_JWT_SECRET

# Database credentials
database_username = ""     # Set via SCRIBE_DATABASE_USERNAME
database_password = ""     # Set via SCRIBE_DATABASE_PASSWORD

# Azure AD OAuth secrets
azure_client_secret = ""  # Set via SCRIBE_AZURE_CLIENT_SECRET

[development]
# Development-only secrets (safe for local development)
secret_key = "dev-secret-key-change-this"
jwt_secret = "dev-jwt-secret-change-this"
azure_client_id = "your-dev-azure-client-id"
azure_client_secret = "your-dev-azure-client-secret"

[production]
# Production secrets MUST be set via environment variables
secret_key = ""           # MUST be set via SCRIBE_SECRET_KEY
```

#### Environment Variables Override

All settings can be overridden using the `SCRIBE_` prefix:

```bash
# Environment switching
export ENV_FOR_DYNACONF=production

# Override any setting with SCRIBE_ prefix
export SCRIBE_DEBUG=false
export SCRIBE_LOG_LEVEL=INFO
export SCRIBE_SECRET_KEY="production-secret-key"
export SCRIBE_DATABASE_PASSWORD="production-db-password"

# Nested settings use double underscores
export SCRIBE_AZURE__CLIENT_SECRET="production-azure-secret"
```

#### What Goes Where

**settings.toml** (Non-sensitive settings):
- ✅ Application metadata (name, version)
- ✅ Server hostnames and ports
- ✅ Database server names (no credentials)
- ✅ Feature flags and business logic settings
- ✅ Timeout and retry configurations
- ✅ CORS origins (development can be permissive)
- ✅ Logging levels and formats
- ✅ Cache TTL settings
- ✅ Azure AD non-sensitive settings (tenant ID, scopes)

**.secrets.toml** (Sensitive data only):
- 🔒 Passwords and connection strings
- 🔒 API keys and tokens
- 🔒 Encryption keys
- 🔒 OAuth client secrets
- 🔒 Database passwords
- 🔒 Any credential that could compromise security

#### Environment-Specific Configuration

```toml
[default]
# Base configuration that applies to all environments
log_level = "INFO"
debug = false

[development]
# Development-specific overrides
debug = true
log_level = "DEBUG"
database_echo = true        # Log all SQL queries
migration_allow_drops = true  # Allow destructive operations

[production]
# Production-specific overrides  
debug = false
log_level = "WARNING"
log_async_enabled = true
migration_allow_drops = false  # Safety: no destructive operations

[testing]
# Test-specific overrides
log_level = "ERROR"
cache_max_size = 100       # Smaller cache for tests
```

#### Security Best Practices

1. **Never Commit Secrets**: `.secrets.toml` is in `.gitignore`
2. **Production Secrets**: Always use environment variables in production
3. **Development Safety**: Use non-production secrets in development environment
4. **Principle of Least Privilege**: Only grant necessary permissions
5. **Regular Rotation**: Rotate secrets regularly
6. **Audit Trail**: Log configuration access (but never log secret values)

#### Configuration Loading

```python
# app/core/config.py
from dynaconf import Dynaconf

settings = Dynaconf(
    environments=True,                    # Enable [development], [production] sections
    settings_files=["settings.toml", ".secrets.toml"],  # Load order
    envvar_prefix="SCRIBE",              # Environment variable prefix
    load_dotenv=False,                   # Don't load .env files
    merge_enabled=True,                  # Enable merging of nested structures
    env_switcher="ENV_FOR_DYNACONF",     # Variable to switch environments
    env="development"                    # Default environment
)

# Access settings
app_name = settings.app_name
debug_mode = settings.debug
secret_key = settings.secret_key
```

#### Common Configuration Patterns

**Database Configuration**:
```toml
[default]
database_server = "myserver.database.windows.net"
database_name = "myapp"
database_pool_size = 10
database_timeout = 30
# NO passwords or usernames here!

# In .secrets.toml
[default]
database_username = ""  # Set via SCRIBE_DATABASE_USERNAME
database_password = ""  # Set via SCRIBE_DATABASE_PASSWORD
```

**Feature Flags**:
```toml
[default]
enable_feature_x = false
feature_rollout_percentage = 0

[development]
enable_feature_x = true  # Enable for development
feature_rollout_percentage = 100

[production]
enable_feature_x = true
feature_rollout_percentage = 10  # Gradual rollout
```

**Environment-Specific URLs**:
```toml
[development]
api_base_url = "http://localhost:8000"
frontend_url = "http://localhost:3000"

[production]
api_base_url = "https://api.example.com"
frontend_url = "https://app.example.com"
```

#### Validation and Error Handling

```python
def validate_required_settings():
    """Validate that all required settings are present."""
    required = ["secret_key", "jwt_secret"]
    missing = [key for key in required if not settings.get(key)]
    
    if missing:
        raise ValueError(
            f"Missing required settings: {', '.join(missing)}. "
            f"Set via environment variables with SCRIBE_ prefix or .secrets.toml"
        )

# Call validation on startup
validate_required_settings()
```

#### Migration from .env to TOML

If migrating from `.env` files:

1. **Convert format**: `.env` key=value → TOML `key = "value"`
2. **Categorize settings**: Separate sensitive from non-sensitive
3. **Update imports**: Change Dynaconf initialization
4. **Test thoroughly**: Verify all settings load correctly
5. **Update documentation**: Update deployment guides

#### Testing Configuration

```toml
[testing]
# Use smaller cache for tests
cache_max_size = 100
database_name = "myapp_test"

# Faster timeouts for tests
request_timeout = 1
retry_attempts = 1

# Disable external services in tests
enable_external_api = false
```

#### Deployment Considerations

**Development**:
- Use `.secrets.toml` with development-safe values
- Enable debug mode and verbose logging
- Allow permissive CORS for frontend development

**Production**:
- NEVER use `.secrets.toml` for production secrets
- Set all sensitive values via environment variables
- Use restrictive CORS origins
- Enable async logging for performance
- Implement proper monitoring and alerting

**Environment Variables in Production**:
```bash
# Required in production environment
export ENV_FOR_DYNACONF=production
export SCRIBE_SECRET_KEY="$(openssl rand -hex 32)"
export SCRIBE_JWT_SECRET="$(openssl rand -hex 32)"
export SCRIBE_DATABASE_PASSWORD="$DATABASE_PASSWORD"
export SCRIBE_AZURE_CLIENT_SECRET="$AZURE_CLIENT_SECRET"
```

## Naming Conventions

### Files and Directories

- **Python application files**: `PascalCase.py` (e.g., `AuthService.py`, `MailRepository.py`)
- **Configuration/utility files**: `snake_case.py` (e.g., `main.py`, `config.py`)
- **Directories**: `snake_case` (e.g., `api`, `services`, `models`)
- **Special Python files**: `__init__.py`, `main.py`, `config.py` remain as-is

### Code Elements

- **Classes**: `PascalCase`

  ```python
  class AuthService:
      pass

  class UserCreateRequest:
      pass
  ```

- **Functions and Variables**: `snake_case`

  ```python
  def get_user_by_id(user_id: int):
      pass

  user_name = "John Doe"
  is_active = True
  ```

- **Constants**: `UPPER_SNAKE_CASE`

  ```python
  MAX_RETRY_ATTEMPTS = 3
  DEFAULT_PAGE_SIZE = 20
  API_VERSION = "v1"
  ```

- **Private attributes/methods**: Prefix with single underscore
  ```python
  class UserService:
      def _validate_user_data(self, data: dict):
          pass
  ```

### API and Database

- **API Routes**: `kebab-case`

  ```
  /api/v1/users
  /api/v1/user-profiles
  /api/v1/reset-password
  ```

- **Database Tables**: `snake_case`

  ```sql
  users
  user_profiles
  password_reset_tokens
  ```

- **Environment Variables**: `UPPER_SNAKE_CASE`
  ```
  DATABASE_URL
  SECRET_KEY
  REDIS_HOST
  ```

## Azure Services Architecture

### Service Separation

Azure functionality is split into specialized services in the `app/azure/` directory:

#### AzureAuthService
- OAuth 2.0 authorization flow
- Token acquisition and refresh  
- User profile retrieval
- Token validation

```python
from app.azure.AzureAuthService import azure_auth_service

# Usage
auth_data = azure_auth_service.get_authorization_url()
token_data = azure_auth_service.acquire_token_by_auth_code(callback_url)
```

#### AzureGraphService  
- Base Microsoft Graph API operations
- Mail folder management
- Message operations (get, move, update)
- Attachment handling

```python
from app.azure.AzureGraphService import azure_graph_service

# Usage
folders = await azure_graph_service.get_mail_folders(access_token)
messages = await azure_graph_service.get_messages(access_token, folder_id)
```

#### AzureMailService
- Shared mailbox operations
- Shared mailbox message management
- Permission handling
- Mail sending from shared mailboxes

```python
from app.azure.AzureMailService import azure_mail_service

# Usage  
mailboxes = await azure_mail_service.get_shared_mailboxes(access_token)
messages = await azure_mail_service.get_shared_mailbox_messages(access_token, mailbox_email)
```

## Authentication Flow

### Direct OAuth Redirect

The `/login` endpoint directly redirects to Azure AD instead of returning JSON:

```python
@router.get("/login")
async def initiate_login():
    """Redirect directly to Azure AD authorization URL."""
    auth_data = oauth_service.initiate_login()
    return RedirectResponse(url=auth_data["auth_uri"])
```

This eliminates the need for static pages and provides a streamlined authentication experience.

## Coding Standards

### General Principles

1. **Configuration Management**: Use Dynaconf for all configuration
2. **File Naming**: PascalCase for application files, snake_case for utilities
3. **Code Readability**: Write self-documenting code with minimal comments
4. **DRY Principle**: Don't Repeat Yourself - eliminate code duplication
5. **Single Responsibility**: Each function/class should have one reason to change
6. **SOLID Principles**: Apply all SOLID design principles

### Code Formatting

- **Line Length**: Maximum 88 characters (Black formatter standard)
- **Indentation**: 4 spaces (no tabs)
- **Imports**: Group imports using isort

  ```python
  # Standard library imports
  import os
  from datetime import datetime

  # Third-party imports
  from fastapi import FastAPI
  from pydantic import BaseModel

  # Local application imports
  from app.core.config import settings
  from app.models.Auth import UserSchema
  ```

### Function Guidelines

- **Maximum Function Length**: 50 lines
- **Cyclomatic Complexity**: Maximum 10
- **Parameters**: Maximum 5 parameters per function
- **Return Statements**: Maximum 3 return statements per function

```python
def get_user_by_email(
    email: str,
    db_session: Session,
    include_inactive: bool = False
) -> Optional[User]:
    """
    Retrieve a user by their email address.

    Args:
        email: The user's email address
        db_session: Database session
        include_inactive: Whether to include inactive users

    Returns:
        User object if found, None otherwise

    Raises:
        ValidationError: If email format is invalid
    """
    if not email or not _is_valid_email(email):
        raise ValidationError("Invalid email format")

    query = db_session.query(User).filter(User.email == email)

    if not include_inactive:
        query = query.filter(User.is_active == True)

    return query.first()
```

### Type Hints

- **Required**: All function parameters and return types
- **Variables**: Use type hints for complex variables
- **Generic Types**: Use from `typing` module

```python
from typing import List, Dict, Optional, Union
from datetime import datetime

def process_user_data(
    users: List[Dict[str, Union[str, int]]]
) -> Dict[str, List[str]]:
    """Process user data and return categorized results."""
    pass
```

### Documentation

- **Docstrings**: Required for all public functions and classes
- **Format**: Google-style docstrings
- **Type Information**: Include in docstrings when complex

```python
class AuthService:
    """Service for managing authentication operations.

    This service handles all authentication-related business logic including
    OAuth flows, token management, and user session handling.

    Attributes:
        auth_repository: AuthRepository instance for data access
        token_validator: TokenValidator for token validation
    """

    def authenticate_user(
        self,
        auth_request: AuthRequest
    ) -> AuthResponse:
        """Authenticate a user with the provided credentials.

        Args:
            auth_request: Authentication request containing credentials

        Returns:
            AuthResponse: Authentication result with tokens and user info

        Raises:
            AuthenticationError: If authentication fails
            ValidationError: If request data is invalid
        """
        pass
```

## Code Patterns

### Repository Pattern

Use the Repository pattern for data access to separate business logic from data access logic:

```python
# repositories/BaseRepository.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    """Base repository interface."""

    @abstractmethod
    async def create(self, entity: T) -> T:
        pass

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        pass

# repositories/UserRepository.py
class UserRepository(BaseRepository[User]):
    """Repository for User entity operations."""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    async def create(self, user: User) -> User:
        self.db_session.add(user)
        await self.db_session.commit()
        await self.db_session.refresh(user)
        return user
```

### Service Layer Pattern

Implement business logic in service classes:

```python
# services/AuthService.py
class AuthService:
    """Service for authentication business logic."""

    def __init__(self, auth_repository: AuthRepository):
        self.auth_repository = auth_repository

    async def authenticate_user(
        self,
        auth_request: AuthRequest
    ) -> AuthResponse:
        """Authenticate user with validation and business rules."""
        # Validate business rules
        await self._validate_auth_request(auth_request)

        # Perform authentication
        user = await self.auth_repository.authenticate(auth_request)

        # Return response model
        return AuthResponse.from_orm(user)
```

### Dependency Injection

Use FastAPI's dependency injection system:

```python
# dependencies/Auth.py
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repositories.AuthRepository import AuthRepository
from app.services.AuthService import AuthService

def get_auth_repository(
    db_session: Session = Depends(get_db_session)
) -> AuthRepository:
    return AuthRepository(db_session)

def get_auth_service(
    auth_repository: AuthRepository = Depends(get_auth_repository)
) -> AuthService:
    return AuthService(auth_repository)

# api/v1/endpoints/Auth.py
@router.post("/login", response_model=AuthResponse)
async def login(
    auth_request: AuthRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    return await auth_service.authenticate_user(auth_request)
```

## Security Standards

### Input Validation

- **Validate All Inputs**: Use Pydantic models for validation
- **Sanitization**: Sanitize user inputs to prevent XSS
- **SQL Injection Prevention**: Use parameterized queries (SQLAlchemy ORM)

```python
from pydantic import BaseModel, Field, validator

class UserCreateRequest(BaseModel):
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8, max_length=128)

    @validator('password')
    def validate_password_strength(cls, v):
        # Implement password strength validation
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', v):
            raise ValueError('Password must contain uppercase, lowercase, and digit')
        return v
```

### Configuration Security

- **Secrets Management**: Use `.secrets` file for sensitive data
- **Environment Separation**: Different configs for different environments
- **Never commit secrets**: `.secrets` file is in `.gitignore`

```python
# Configuration access
from app.core.config import settings

# Non-sensitive settings
app_name = settings.app_name
debug_mode = settings.debug

# Sensitive settings (from .secrets file)
secret_key = settings.secret_key
azure_client_secret = settings.azure_client_secret
```

## Testing Requirements

### Coverage Requirements

- **Minimum Coverage**: 80% overall code coverage
- **Critical Paths**: 95% coverage for business logic
- **Integration Tests**: All API endpoints must have integration tests

### Test Structure

```python
# tests/unit/test_services/test_AuthService.py
import pytest
from unittest.mock import Mock, AsyncMock

from app.services.AuthService import AuthService
from app.models.Auth import AuthRequest

class TestAuthService:
    @pytest.fixture
    def mock_auth_repository(self):
        return Mock()

    @pytest.fixture
    def auth_service(self, mock_auth_repository):
        return AuthService(mock_auth_repository)

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_service, mock_auth_repository):
        # Arrange
        auth_request = AuthRequest(
            email="test@example.com",
            password="TestPassword123"
        )
        mock_auth_repository.authenticate = AsyncMock(return_value=Mock())

        # Act
        result = await auth_service.authenticate_user(auth_request)

        # Assert
        assert result is not None
        mock_auth_repository.authenticate.assert_called_once()
```

## Error Handling

### Exception Hierarchy

```python
# core/Exceptions.py
class ScribeBaseException(Exception):
    """Base exception for Scribe application."""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)

class ValidationError(ScribeBaseException):
    """Raised when input validation fails."""
    pass

class AuthenticationError(ScribeBaseException):
    """Raised when authentication fails."""
    pass
```

### Error Response Format

```python
# models/Default.py
class ErrorResponse(BaseModel):
    error: str
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

## Development Workflow

### Git Workflow

- **Branch Naming**: `feature/feature-name`, `bugfix/bug-name`, `hotfix/issue-name`
- **Commit Messages**: Follow conventional commits format
- **Pull Requests**: Required for all changes to main branch

### Code Quality

- **Pre-commit Hooks**: Run linting and formatting on commit
- **Code Review**: All code must be reviewed before merge
- **Automated Testing**: CI/CD pipeline runs all tests

### Development Commands

```bash
# Start development server
fastapi dev app/main.py

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black app/
isort app/

# Type checking
mypy app/
```

## Performance Guidelines

### Database Optimization

- **Query Optimization**: Use appropriate indexes and query patterns
- **Connection Pooling**: Configure database connection pools
- **Lazy Loading**: Use lazy loading for relationships

### Caching Strategy

**Azure Functions Optimized In-Memory Caching**:
- **In-Memory Cache**: LRU-based cache with size limits for optimal Azure Functions performance
- **TTL-Based Expiration**: Automatic cleanup of expired entries (default 5 minutes)
- **Size Limits**: Configurable maximum entries to prevent memory issues (default 1000 entries)
- **LRU Eviction**: Least Recently Used items are evicted when cache reaches capacity
- **Cache Warmup**: Built-in warmup function for cold start optimization

**Why In-Memory Over Redis for Azure Functions**:
- **Cost Efficiency**: No external Azure Cache for Redis required
- **Performance**: ~100x faster access than network-based Redis calls
- **Simplicity**: No connection management or network failure handling
- **Azure Functions Alignment**: Stateless functions benefit from request-scoped caching

**Configuration**:
```toml
cache_default_ttl = 300        # 5 minutes default TTL
cache_max_size = 1000          # Maximum cached entries
cache_cleanup_interval = 180   # Cleanup frequency (3 minutes)
```

### Async/Await Best Practices

```python
import asyncio
from typing import List

async def process_users_concurrently(
    user_ids: List[int]
) -> List[UserResponse]:
    """Process multiple users concurrently."""
    tasks = [process_single_user(user_id) for user_id in user_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions appropriately
    valid_results = [
        result for result in results
        if not isinstance(result, Exception)
    ]

    return valid_results
```

### Monitoring and Logging

```python
# core/Logging.py
import logging
import sys
from functools import wraps

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def log_execution_time(func):
    """Decorator to log function execution time."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        import time
        start_time = time.time()
        result = await func(*args, **kwargs)
        execution_time = time.time() - start_time
        logging.info(f"{func.__name__} executed in {execution_time:.2f}s")
        return result
    return wrapper
```

## Maintenance and Updates

### Regular Tasks

1. **Dependency Updates**: Weekly security updates, monthly feature updates
2. **Configuration Review**: Regular review of environment configurations
3. **Code Review**: All changes must be peer-reviewed
4. **Documentation Updates**: Update docs with every feature change
5. **Performance Monitoring**: Weekly performance reviews
6. **Security Audits**: Monthly security scans

### Version Control

- **Semantic Versioning**: Follow semver (MAJOR.MINOR.PATCH)
- **Release Notes**: Maintain detailed release notes
- **Migration Guides**: Provide upgrade instructions for breaking changes

---

## Enforcement

This document is living and should be updated as the project evolves. All team members are expected to follow these standards, and adherence will be checked during code reviews and automated CI/CD processes.

For questions or suggestions regarding these standards, please create an issue in the project repository or contact the development team lead.

**Last Updated**: August 2025
**Version**: 2.0.0