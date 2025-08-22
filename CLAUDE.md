# Scribe FastAPI Development Standards

This document serves as the authoritative guide for all development practices, organizational structure, and coding standards for the Scribe FastAPI application.

## Table of Contents

1. [Project Structure](#project-structure)
2. [Naming Conventions](#naming-conventions)
3. [Coding Standards](#coding-standards)
4. [Code Patterns](#code-patterns)
5. [Documentation Requirements](#documentation-requirements)
6. [Security Standards](#security-standards)
7. [Testing Requirements](#testing-requirements)
8. [Error Handling](#error-handling)
9. [Development Workflow](#development-workflow)
10. [Performance Guidelines](#performance-guidelines)

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
│   │       │   ├── auth.py
│   │       │   └── users.py
│   │       └── router.py       # Main router for v1
│   ├── core/                   # Core functionality
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration settings
│   │   ├── security.py         # Security utilities
│   │   ├── database.py         # Database connection
│   │   └── logging.py          # Logging configuration
│   ├── dependencies/           # Dependency injection
│   │   ├── __init__.py
│   │   └── auth.py            # Authentication dependencies
│   ├── models/                 # Pydantic models & schemas
│   │   ├── __init__.py
│   │   ├── database.py         # Database models (SQLAlchemy)
│   │   ├── default.py          # Default FastAPI models (health, error, etc.)
│   │   └── enums.py           # Enum definitions
│   ├── services/              # Business logic layer
│   │   ├── __init__.py
│   │   └── user_service.py
│   ├── repositories/          # Data access layer
│   │   ├── __init__.py
│   │   ├── base_repository.py
│   │   └── user_repository.py
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
│   ├── integration/          # Integration tests
│   │   └── __init__.py
│   └── performance/          # Performance tests
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
├── .env                     # Environment variables (local)
├── .env.example
├── .gitignore
├── pyproject.toml          # Project configuration
├── README.md
├── CLAUDE.md               # This file
└── requirements.txt
```

## Naming Conventions

### Files and Directories

- **Python files**: `snake_case.py`
- **Directories**: `snake_case`
- **Configuration files**: `snake_case.env`, `snake_case.yaml`

### Code Elements

- **Classes**: `PascalCase`

  ```python
  class UserRepository:
      pass

  class ItemCreateRequest:
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

## Coding Standards

### General Principles

1. **Industry-Specific Standards**: Follow Python PEP 8 and FastAPI best practices
2. **Code Readability**: Write self-documenting code with minimal comments
3. **DRY Principle**: Don't Repeat Yourself - eliminate code duplication
4. **Single Responsibility**: Each function/class should have one reason to change
5. **SOLID Principles**: Apply all SOLID design principles

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
  from app.models.schemas import UserSchema
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
- **File Summaries**: When writing or modifying files, provide a brief summary of the file's purpose and main changes

```python
class UserService:
    """Service for managing user operations.

    This service handles all user-related business logic including
    creation, validation, and authentication.

    Attributes:
        repository: UserRepository instance for data access
        validator: UserValidator for data validation
    """

    def create_user(
        self,
        user_data: UserCreateRequest
    ) -> UserResponse:
        """Create a new user account.

        Args:
            user_data: User creation data containing email, password, etc.

        Returns:
            UserResponse: Created user information

        Raises:
            ValidationError: If user data is invalid
            DuplicateUserError: If user already exists
            DatabaseError: If database operation fails
        """
        pass
```

## Code Patterns

### Repository Pattern

Use the Repository pattern for data access to separate business logic from data access logic:

```python
# repositories/base_repository.py
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

    @abstractmethod
    async def get_all(self) -> List[T]:
        pass

    @abstractmethod
    async def update(self, id: int, entity: T) -> Optional[T]:
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        pass

# repositories/user_repository.py
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
# services/user_service.py
class UserService:
    """Service for user business logic."""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def create_user(
        self,
        user_data: UserCreateRequest
    ) -> UserResponse:
        """Create a new user with validation and business rules."""
        # Validate business rules
        await self._validate_user_creation(user_data)

        # Create user entity
        user = User(**user_data.dict())
        created_user = await self.user_repository.create(user)

        # Return response model
        return UserResponse.from_orm(created_user)
```

### Dependency Injection

Use FastAPI's dependency injection system:

```python
# dependencies/auth.py
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

def get_user_repository(
    db_session: Session = Depends(get_db_session)
) -> UserRepository:
    return UserRepository(db_session)

def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository)
) -> UserService:
    return UserService(user_repository)

# api/v1/endpoints/users.py
@router.post("/users/", response_model=UserResponse)
async def create_user(
    user_data: UserCreateRequest,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.create_user(user_data)
```

## Documentation Requirements

### API Documentation

- **OpenAPI Specs**: Maintain in `docs/api/`
- **Endpoint Documentation**: Include examples for all endpoints
- **Schema Documentation**: Document all request/response models

### Code Documentation

- **README Updates**: Update after every major feature
- **Changelog**: Maintain in `docs/changelog/`
- **ADRs**: Document architectural decisions in `docs/decisions/`

### Documentation Structure

```
docs/
├── api/
│   ├── openapi.yaml          # OpenAPI 3.0 specification
│   └── examples/             # Request/response examples
├── architecture/
│   ├── overview.md           # System architecture overview
│   ├── database-design.md    # Database schema documentation
│   └── security-model.md     # Security architecture
├── guides/
│   ├── getting-started.md    # Development setup guide
│   ├── deployment.md         # Deployment instructions
│   └── contributing.md       # Contribution guidelines
├── changelog/
│   └── CHANGELOG.md          # Version history
└── decisions/
    ├── 001-database-choice.md
    ├── 002-authentication-method.md
    └── template.md           # ADR template
```

### Documentation Update Workflow

1. **Feature Development**: Update relevant docs during development
2. **Code Review**: Include documentation review
3. **Release**: Update changelog and version documentation
4. **API Changes**: Update OpenAPI specifications
5. **Architecture Changes**: Create ADR (Architecture Decision Record)

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

### Authentication & Authorization

- **JWT Tokens**: Use for stateless authentication
- **Password Hashing**: Use bcrypt or Argon2
- **Rate Limiting**: Implement on sensitive endpoints

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

### Environment Variables

- **Secrets Management**: Never commit secrets to version control
- **Environment Separation**: Use different configs for different environments

```python
# core/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    redis_url: str
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

## Testing Requirements

### Coverage Requirements

- **Minimum Coverage**: 80% overall code coverage
- **Critical Paths**: 95% coverage for business logic
- **Integration Tests**: All API endpoints must have integration tests

### Test Structure

```python
# tests/unit/test_services/test_user_service.py
import pytest
from unittest.mock import Mock, AsyncMock

from app.services.user_service import UserService
from app.models.schemas import UserCreateRequest

class TestUserService:
    @pytest.fixture
    def mock_user_repository(self):
        return Mock()

    @pytest.fixture
    def user_service(self, mock_user_repository):
        return UserService(mock_user_repository)

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, mock_user_repository):
        # Arrange
        user_data = UserCreateRequest(
            email="test@example.com",
            password="TestPassword123"
        )
        mock_user_repository.create = AsyncMock(return_value=Mock())

        # Act
        result = await user_service.create_user(user_data)

        # Assert
        assert result is not None
        mock_user_repository.create.assert_called_once()
```

### Test Types

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Test complete user workflows
4. **Performance Tests**: Test response times and load handling

## Error Handling

### Exception Hierarchy

```python
# core/exceptions.py
class ScribeBaseException(Exception):
    """Base exception for Scribe application."""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)

class ValidationError(ScribeBaseException):
    """Raised when input validation fails."""
    pass

class NotFoundError(ScribeBaseException):
    """Raised when requested resource is not found."""
    pass

class AuthenticationError(ScribeBaseException):
    """Raised when authentication fails."""
    pass
```

### Error Response Format

```python
# models/schemas.py
class ErrorResponse(BaseModel):
    error: str
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Exception Handling

```python
# main.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request,
    exc: ValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Validation Error",
            message=exc.message,
            error_code=exc.error_code
        ).dict()
    )
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

### Tools Configuration

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py39']

[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "--cov=app --cov-report=html --cov-report=term-missing"

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/venv/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError"
]
```

## Performance Guidelines

### Database Optimization

- **Query Optimization**: Use appropriate indexes and query patterns
- **Connection Pooling**: Configure database connection pools
- **Lazy Loading**: Use lazy loading for relationships

### Caching Strategy

- **Redis**: Use for session storage and frequently accessed data
- **Application Caching**: Cache expensive computations
- **HTTP Caching**: Use appropriate cache headers

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
# core/logging.py
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
2. **Code Review**: All changes must be peer-reviewed
3. **Documentation Updates**: Update docs with every feature change
4. **Performance Monitoring**: Weekly performance reviews
5. **Security Audits**: Monthly security scans

### Version Control

- **Semantic Versioning**: Follow semver (MAJOR.MINOR.PATCH)
- **Release Notes**: Maintain detailed release notes
- **Migration Guides**: Provide upgrade instructions for breaking changes

---

## Enforcement

This document is living and should be updated as the project evolves. All team members are expected to follow these standards, and adherence will be checked during code reviews and automated CI/CD processes.

For questions or suggestions regarding these standards, please create an issue in the project repository or contact the development team lead.

**Last Updated**: $(date)
**Version**: 1.0.0

- use fastapi dev app/main.py to start the dev server