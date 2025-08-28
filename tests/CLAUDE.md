# Scribe Testing Standards and Guidelines

This document defines the comprehensive testing approach for the Scribe FastAPI application, establishing standards for unit tests, integration tests, and test infrastructure.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Coverage Requirements](#coverage-requirements)
4. [Naming Conventions](#naming-conventions)
5. [Testing Categories](#testing-categories)
6. [Mock Strategy](#mock-strategy)
7. [Database Testing](#database-testing)
8. [Azure Services Testing](#azure-services-testing)
9. [Test Data Management](#test-data-management)
10. [Performance Testing](#performance-testing)
11. [CI/CD Integration](#cicd-integration)
12. [Best Practices](#best-practices)

## Testing Philosophy

### Core Principles

1. **Comprehensive Coverage**: Minimum 80% code coverage, 95% for critical business logic
2. **Fast Execution**: Unit tests must run in under 10 seconds total
3. **Isolation**: Each test is independent and can run in any order
4. **Reliability**: Tests are deterministic and don't depend on external services
5. **Maintainability**: Tests are easy to understand and modify
6. **Documentation**: Tests serve as living documentation of expected behavior

### Testing Pyramid

```
    /\
   /  \     E2E Tests (Few)
  /____\    
 /      \   Integration Tests (Some)  
/________\  Unit Tests (Many)
```

- **Unit Tests (70%)**: Fast, isolated component testing
- **Integration Tests (25%)**: API endpoints and service integration
- **End-to-End Tests (5%)**: Critical user workflows

## Test Structure

### Directory Organization

```
tests/
├── CLAUDE.md                    # This file - testing documentation
├── conftest.py                  # Global pytest configuration
├── settings.test.toml           # Test environment configuration
├── .test.secrets.toml          # Test secrets (gitignored)
├── unit/                        # Unit tests (isolated components)
│   ├── test_azure/              # Azure services
│   ├── test_core/               # Core functionality
│   ├── test_db/                 # Database layer
│   ├── test_dependencies/       # Dependency injection
│   ├── test_models/             # Pydantic models
│   ├── test_repositories/       # Data access layer
│   └── test_services/           # Business logic
├── integration/                 # Integration tests
│   ├── test_api/                # API endpoints
│   ├── test_azure_integration.py # Azure service integration
│   └── test_database_integration.py # Database integration
├── fixtures/                    # Test data and mock responses
│   ├── auth_fixtures.py
│   ├── mail_fixtures.py
│   ├── database_fixtures.py
│   └── mock_responses.py
└── utils/                       # Testing utilities
    ├── mock_factory.py
    ├── test_helpers.py
    └── assertions.py
```

## Coverage Requirements

### Minimum Coverage Targets

- **Overall Application**: 80% minimum
- **Critical Business Logic**: 95% minimum
- **Azure Services**: 90% minimum
- **Database Models**: 85% minimum
- **API Endpoints**: 100% (all endpoints must have tests)

### Coverage Exclusions

Files excluded from coverage requirements:
- `__init__.py` files
- Migration scripts
- Configuration files
- Test files themselves

### Coverage Commands

```bash
# Run tests with coverage
pytest --cov=app --cov-report=html --cov-report=term

# Generate coverage badge
coverage-badge -o coverage.svg

# Check coverage requirements
pytest --cov=app --cov-fail-under=80
```

## Naming Conventions

### Test File Naming

- **Unit Tests**: `test_[ModuleName].py`
  - Example: `test_AzureAuthService.py`
- **Integration Tests**: `test_[feature]_endpoints.py`
  - Example: `test_auth_endpoints.py`

### Test Function Naming

Pattern: `test_[function]_[scenario]_[expected_result]`

Examples:
```python
def test_authenticate_user_valid_credentials_returns_token():
    pass

def test_authenticate_user_invalid_credentials_raises_error():
    pass

def test_get_mail_folders_no_auth_returns_401():
    pass
```

### Test Class Naming

Pattern: `Test[ClassName]`

Examples:
```python
class TestAzureAuthService:
    pass

class TestMailRepository:
    pass
```

## Testing Categories

### Unit Tests

**Purpose**: Test individual components in isolation

**Characteristics**:
- Fast execution (< 1 second per test)
- No external dependencies
- Use mocks for all dependencies
- Test single units of functionality

**Example Structure**:
```python
class TestAzureAuthService:
    @pytest.fixture
    def mock_msal_client(self):
        return Mock()
    
    @pytest.fixture  
    def auth_service(self, mock_msal_client):
        with patch('app.azure.AzureAuthService.msal.ConfidentialClientApplication', return_value=mock_msal_client):
            return AzureAuthService()
    
    def test_get_authorization_url_returns_valid_url(self, auth_service, mock_msal_client):
        # Test implementation
        pass
```

### Integration Tests

**Purpose**: Test component interactions and API endpoints

**Characteristics**:
- Test real integrations between components
- Use test database (SQLite in-memory)
- Mock external services only (Azure, Graph API)
- Test complete request/response cycles

**Example Structure**:
```python
class TestAuthEndpoints:
    async def test_login_endpoint_redirects_to_azure(self, async_client):
        response = await async_client.get("/api/v1/auth/login")
        assert response.status_code == 302
        assert "login.microsoftonline.com" in response.headers["location"]
```

## Mock Strategy

### What to Mock

**Always Mock**:
- External HTTP requests (Azure Graph API, MSAL)
- Azure services (Blob Storage, Database tokens)
- File system operations
- DateTime operations (use freezegun)
- Random number generation

**Never Mock**:
- Code under test
- Standard library functions (unless side effects)
- Database operations in integration tests
- Pydantic model validation

### Mock Implementation

**Azure MSAL Client**:
```python
@pytest.fixture
def mock_msal_client():
    client = Mock()
    client.initiate_auth_code_flow.return_value = {
        "auth_uri": "https://login.microsoftonline.com/auth",
        "flow": {"state": "test-state"}
    }
    client.acquire_token_by_auth_code_flow.return_value = {
        "access_token": "test-token",
        "id_token": "test-id-token"
    }
    return client
```

**Azure Graph API**:
```python
@pytest.fixture
def mock_graph_responses():
    return {
        "folders": {
            "value": [
                {"id": "folder1", "displayName": "Inbox"},
                {"id": "folder2", "displayName": "Sent Items"}
            ]
        }
    }
```

## Database Testing

### Unit Tests Database Strategy

**Use SQLite In-Memory**:
- Fast test execution
- No external dependencies
- Easy cleanup between tests
- Isolated test data

**Configuration**:
```python
# tests/conftest.py
@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine)
    async with async_session() as session:
        yield session
```

### Integration Tests Database Strategy

**Use Test Database Instance**:
- More realistic testing environment
- Test actual database constraints
- Test migrations and schema changes

### Database Test Patterns

**Transaction Rollback**:
```python
@pytest.fixture
async def test_transaction():
    async with test_db.begin() as transaction:
        yield test_db
        await transaction.rollback()
```

**Test Data Factories**:
```python
class UserFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "email": "test@example.com",
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        defaults.update(kwargs)
        return User(**defaults)
```

## Azure Services Testing

### Authentication Testing

**Mock MSAL Responses**:
```python
@pytest.fixture
def auth_success_response():
    return {
        "access_token": "eyJ0eXAiOiJKV1QiLCJub25jZSI6...",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "refresh_token_value",
        "scope": "User.Read Mail.Read"
    }
```

### Blob Storage Testing

**Mock Azure Blob Operations**:
```python
@pytest.fixture
def mock_blob_service():
    service = Mock()
    service.get_blob_client.return_value.upload_blob.return_value = None
    service.get_blob_client.return_value.download_blob.return_value = Mock(
        readall=Mock(return_value=b"test audio data")
    )
    return service
```

### Graph API Testing

**Mock HTTP Responses with respx**:
```python
@pytest.mark.asyncio
async def test_get_mail_folders(respx_mock):
    respx_mock.get("https://graph.microsoft.com/v1.0/me/mailFolders").mock(
        return_value=httpx.Response(200, json={"value": []})
    )
    # Test implementation
```

## Test Data Management

### Fixtures Strategy

**Hierarchical Fixtures**:
- Base fixtures in `conftest.py`
- Module-specific fixtures in test files
- Reusable fixtures in `fixtures/` directory

**Example Fixture Hierarchy**:
```python
# conftest.py - Global fixtures
@pytest.fixture
def test_user():
    return UserFactory.create()

# test_auth.py - Module-specific fixtures  
@pytest.fixture
def authenticated_user(test_user):
    test_user.is_authenticated = True
    return test_user
```

### Test Data Factories

**Using Factory Boy**:
```python
class UserFactory(factory.Factory):
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    is_active = True
    created_at = factory.LazyFunction(datetime.utcnow)
```

### Mock Data Management

**Centralized Mock Responses**:
```python
# fixtures/mock_responses.py
GRAPH_API_RESPONSES = {
    "mail_folders": {
        "value": [
            {"id": "inbox", "displayName": "Inbox", "unreadItemCount": 5},
            {"id": "sent", "displayName": "Sent Items", "unreadItemCount": 0}
        ]
    }
}
```

## Performance Testing

### Benchmark Tests

**Using pytest-benchmark**:
```python
def test_cache_performance(benchmark):
    cache = Cache()
    result = benchmark(cache.get, "test_key")
    assert result is not None
```

### Load Testing

**Using locust for API load testing**:
```python
class ApiUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login and get auth token
        pass
    
    @task
    def get_mail_folders(self):
        self.client.get("/api/v1/mail/folders")
```

### Memory Testing

**Memory leak detection**:
```python
def test_no_memory_leaks():
    import tracemalloc
    tracemalloc.start()
    
    # Run test operations
    for _ in range(1000):
        process_large_dataset()
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    assert current < 100 * 1024 * 1024  # Less than 100MB
```

## CI/CD Integration

### GitHub Actions Configuration

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/
        language: system
        pass_filenames: false
        always_run: true
```

## Best Practices

### Test Organization

1. **One test file per source file** for unit tests
2. **Group related tests** using test classes
3. **Use descriptive test names** that explain the scenario
4. **Keep tests small and focused** - test one thing at a time
5. **Use fixtures liberally** to reduce code duplication

### Test Writing Guidelines

1. **Arrange-Act-Assert pattern**:
   ```python
   def test_user_creation():
       # Arrange
       user_data = {"email": "test@example.com"}
       
       # Act
       user = create_user(user_data)
       
       # Assert
       assert user.email == "test@example.com"
   ```

2. **Test edge cases and error conditions**:
   ```python
   def test_invalid_email_raises_validation_error():
       with pytest.raises(ValidationError):
           create_user({"email": "invalid-email"})
   ```

3. **Use parameterized tests** for multiple similar scenarios:
   ```python
   @pytest.mark.parametrize("email,expected", [
       ("test@example.com", True),
       ("invalid-email", False),
       ("", False),
   ])
   def test_email_validation(email, expected):
       assert validate_email(email) == expected
   ```

### Common Patterns

**Testing Async Functions**:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

**Testing Exceptions**:
```python
def test_function_raises_specific_exception():
    with pytest.raises(SpecificException) as exc_info:
        function_that_raises()
    assert "expected message" in str(exc_info.value)
```

**Testing with Fixtures**:
```python
def test_with_database(test_db, test_user):
    test_db.add(test_user)
    test_db.commit()
    
    retrieved = test_db.query(User).filter_by(email=test_user.email).first()
    assert retrieved is not None
```

## Continuous Improvement

### Code Review Checklist

- [ ] All new code has corresponding tests
- [ ] Tests follow naming conventions
- [ ] Coverage targets are met
- [ ] No external dependencies in unit tests
- [ ] Mock objects are properly configured
- [ ] Test data is cleaned up appropriately
- [ ] Performance implications are considered

### Metrics and Monitoring

Track these testing metrics:
- **Code Coverage Percentage**
- **Test Execution Time**
- **Number of Flaky Tests**
- **Test Failure Rate**
- **Time to Fix Broken Tests**

### Test Maintenance

- **Regular Review**: Monthly review of test effectiveness
- **Refactoring**: Clean up tests when refactoring production code
- **Documentation**: Keep test documentation up to date
- **Monitoring**: Monitor test execution times and identify slow tests

---

**Last Updated**: August 2025  
**Version**: 1.0.0

For questions about testing standards or implementation, refer to the main project documentation or contact the development team.