# Scribe API

A production-ready FastAPI application built with strict coding standards and comprehensive architecture.

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-red.svg)](https://pydantic.dev)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Features

- **Modern FastAPI** with Pydantic v2 validation
- **Layered Architecture** with clear separation of concerns
- **Comprehensive Testing** with 80%+ coverage requirement
- **Type Safety** with full type hints and mypy validation
- **Production Ready** with proper error handling and logging
- **Developer Experience** with auto-generated OpenAPI docs
- **Code Quality** with automated formatting and linting

## Quick Start

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd scribe
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   # Development
   pip install -r requirements/development.txt
   
   # Production
   pip install -r requirements/production.txt
   ```

4. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running the Application

```bash
# Development server with auto-reload
uvicorn app.main:app --reload

# Production server
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

The API will be available at:
- **Main application**: http://127.0.0.1:8000
- **Interactive docs**: http://127.0.0.1:8000/docs
- **Alternative docs**: http://127.0.0.1:8000/redoc

## API Overview

### Core Endpoints
- `GET /` - Welcome message with API information
- `GET /health` - Health check with system status

### Authentication API (`/api/v1/auth/`)
- `GET /api/v1/auth/login` - Initiate OAuth login flow
- `GET /api/v1/auth/callback` - Handle OAuth callback
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/me` - Get current user info
- `GET /api/v1/auth/status` - Get authentication status

### Example Usage

```bash
# Initiate login
curl "http://127.0.0.1:8000/api/v1/auth/login"

# Get current user (requires Bearer token)
curl "http://127.0.0.1:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Check authentication status
curl "http://127.0.0.1:8000/api/v1/auth/status"
```

## Architecture

The application follows a **layered architecture** pattern:

```
┌─────────────────────────────────────────┐
│             API Layer                   │  ← FastAPI endpoints
├─────────────────────────────────────────┤
│           Service Layer                 │  ← Business logic
├─────────────────────────────────────────┤
│          Repository Layer               │  ← Data access
├─────────────────────────────────────────┤
│            Core Layer                   │  ← Configuration, logging
└─────────────────────────────────────────┘
```

### Project Structure

```
scribe/
├── app/                        # Application code
│   ├── api/                   # API layer
│   │   └── v1/               # API version 1
│   │       ├── endpoints/    # Route handlers
│   │       └── router.py     # Router configuration
│   ├── core/                 # Core utilities
│   │   ├── config.py        # Configuration management
│   │   ├── exceptions.py    # Custom exceptions
│   │   └── logging.py       # Logging setup
│   ├── dependencies/         # Dependency injection
│   │   └── auth.py          # Authentication dependencies
│   ├── models/              # Data models
│   │   ├── auth.py          # Authentication models
│   │   ├── default.py       # Default FastAPI models (health, error, etc.)
│   │   └── enums.py        # Enumerations
│   ├── repositories/        # Data access layer
│   │   └── base_repository.py
│   ├── services/           # Business logic layer
│   │   └── oauth_service.py
│   └── main.py            # FastAPI application
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── performance/      # Performance tests
├── docs/                 # Documentation
│   ├── api/             # OpenAPI specs
│   ├── architecture/    # System design
│   └── guides/         # How-to guides
├── configs/            # Environment configs
├── requirements/       # Dependency files
└── CLAUDE.md          # Development standards
```

## Development

### Code Quality

The project enforces strict code quality standards:

```bash
# Format code
black app/ tests/
isort app/ tests/

# Lint code
flake8 app/ tests/
mypy app/

# Run all quality checks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test types
pytest tests/unit/
pytest tests/integration/
```

### Environment Configurations

- **Development**: `configs/development.env`
- **Testing**: `configs/testing.env` 
- **Production**: `configs/production.env`

## Documentation

- **[Getting Started](docs/guides/getting-started.md)** - Setup and development guide
- **[Architecture Overview](docs/architecture/overview.md)** - System design and patterns
- **[API Documentation](docs/api/openapi.yaml)** - OpenAPI specification
- **[Development Standards](CLAUDE.md)** - Coding standards and best practices
- **[Changelog](docs/changelog/CHANGELOG.md)** - Version history

## Contributing

1. Read the [development standards](CLAUDE.md)
2. Set up the development environment
3. Write tests for your changes
4. Ensure all quality checks pass
5. Submit a pull request

## Technology Stack

- **Framework**: FastAPI 0.116+
- **Validation**: Pydantic v2
- **Server**: Uvicorn (dev) / Gunicorn (prod)
- **Testing**: Pytest with async support
- **Code Quality**: Black, isort, flake8, mypy
- **Documentation**: OpenAPI 3.0

## License

This project is licensed under the MIT License - see the LICENSE file for details.