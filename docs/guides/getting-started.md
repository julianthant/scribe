# Getting Started with Scribe API

This guide will help you set up and run the Scribe API locally for development.

## Prerequisites

- Python 3.9+ installed on your system
- pip (Python package manager)
- Git (for version control)
- Optional: Virtual environment tool (venv, conda, etc.)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd scribe
```

### 2. Create Virtual Environment

```bash
# Using venv (recommended)
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# For development
pip install -r requirements/development.txt

# For production
pip install -r requirements/production.txt

# For testing
pip install -r requirements/testing.txt
```

### 4. Environment Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` file with your configuration:

```env
# Application Settings
APP_NAME="Scribe API"
DEBUG=True
SECRET_KEY="your-development-secret-key"

# API Configuration
API_V1_PREFIX="/api/v1"

# CORS Settings (for development)
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]
```

## Running the Application

### Development Server

```bash
# Using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# The API will be available at:
# - Main application: http://127.0.0.1:8000
# - Interactive docs: http://127.0.0.1:8000/docs
# - Alternative docs: http://127.0.0.1:8000/redoc
```

### Production Server

```bash
# Using gunicorn (production)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Documentation

Once the server is running, you can access the interactive API documentation:

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## Testing the API

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00.000Z",
  "version": "1.0.0"
}
```

### Create an Item

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/items/" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My First Item",
    "description": "This is a test item",
    "is_active": true
  }'
```

### Get All Items

```bash
curl http://127.0.0.1:8000/api/v1/items/
```

## Development Workflow

### Code Quality Tools

The project uses several tools to maintain code quality:

```bash
# Format code with Black
black app/ tests/

# Sort imports with isort
isort app/ tests/

# Lint with flake8
flake8 app/ tests/

# Type checking with mypy
mypy app/

# Run all quality checks
pre-commit run --all-files
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_services/test_item_service.py

# Run tests in parallel
pytest -n auto
```

### Test Coverage

View the coverage report:

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# Open coverage report
# Windows:
start htmlcov/index.html
# macOS:
open htmlcov/index.html
# Linux:
xdg-open htmlcov/index.html
```

## Project Structure

```
scribe/
├── app/                    # Main application code
│   ├── api/               # API routes and dependencies
│   │   └── v1/           # API version 1
│   ├── core/             # Core functionality
│   ├── models/           # Data models and schemas
│   ├── repositories/     # Data access layer
│   └── services/         # Business logic layer
├── tests/                # Test suite
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── performance/     # Performance tests
├── docs/                # Documentation
├── configs/             # Environment configurations
└── requirements/        # Dependency files
```

## Making Changes

### Adding a New Feature

1. **Create a branch**:
   ```bash
   git checkout -b feature/new-feature-name
   ```

2. **Follow the coding standards** (see CLAUDE.md)

3. **Write tests** for your feature

4. **Update documentation** if necessary

5. **Run quality checks**:
   ```bash
   pre-commit run --all-files
   pytest
   ```

6. **Commit and push**:
   ```bash
   git add .
   git commit -m "Add new feature: description"
   git push origin feature/new-feature-name
   ```

### Code Style Guidelines

- Follow PEP 8 for Python code style
- Use type hints for all functions
- Maximum line length: 88 characters
- Use descriptive variable names
- Write docstrings for all public functions
- Keep functions under 50 lines

### Debugging

#### Logging

The application uses structured logging:

```python
from app.core.logging import get_logger

logger = get_logger(__name__)

# Log levels
logger.debug("Debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
```

#### Common Issues

1. **ModuleNotFoundError**: Make sure virtual environment is activated
2. **Port already in use**: Kill existing process or use different port
3. **Environment variables not loaded**: Check `.env` file exists and is properly formatted

## Next Steps

- Read the [Architecture Overview](../architecture/overview.md)
- Review the [API Documentation](../api/openapi.yaml)
- Check out the [Contributing Guidelines](contributing.md)
- Explore the [Deployment Guide](deployment.md)

## Getting Help

- Check existing issues in the repository
- Review the documentation in the `docs/` folder
- Look at the test files for usage examples
- Ask questions in team channels or create an issue