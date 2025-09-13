# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI boilerplate built for async operations with SQLAlchemy, Pydantic 2, and comprehensive enterprise features. The project uses uv for dependency management and follows a modular architecture pattern.

## Common Development Commands

### Setup
```bash
uv sync                     # Install dependencies
source .venv/bin/activate   # Activate virtual environment (or use uv run)
```

### Running the Application
```bash
# Development mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# With Docker
docker-compose up web

# Background worker
arq app.core.worker.settings.WorkerSettings
```

### Testing
```bash
uv run pytest              # Run all tests
uv run pytest tests/test_user.py  # Run specific test file
```

### Code Quality
```bash
# Linting and formatting
ruff check --fix           # Fix linting issues
ruff format                # Format code
mypy src                   # Type checking

# Pre-commit hooks
pre-commit install          # Set up hooks
pre-commit run --all-files  # Run all hooks manually
```

### Database Operations
```bash
# Migrations are handled automatically on startup
# Manual migration commands available via alembic in src/
```

## Architecture Overview

### Core Structure
- **src/app/main.py**: Application entry point with lifespan management
- **src/app/core/**: Core functionality (config, database, security, utilities)
- **src/app/api/**: API layer with versioned endpoints (v1)
- **src/app/models/**: SQLAlchemy models with mixins (UUID, Timestamp, SoftDelete)
- **src/app/schemas/**: Pydantic schemas for request/response validation
- **src/app/crud/**: Database operations using FastCRUD
- **src/app/admin/**: CRUDAdmin interface for database management

### Key Components
- **Configuration**: Environment-based settings in `src/app/core/config.py` with multiple setting classes
- **Database**: Async PostgreSQL with SQLAlchemy 2.0, automatic table creation on startup
- **Authentication**: JWT-based with access/refresh tokens, role-based permissions
- **Caching**: Redis integration for caching, rate limiting, and session management
- **Background Tasks**: ARQ for async task processing with Redis backend
- **Admin Panel**: CRUDAdmin mounted at `/admin` (configurable) for database management

### API Structure
All endpoints are versioned under `/api/v1/`:
- `/api/v1/login` - Authentication
- `/api/v1/users` - User management
- `/api/v1/posts` - Post operations
- `/api/v1/tasks` - Background task management
- `/api/v1/tiers` - Tier/subscription management
- `/api/v1/rate_limits` - Rate limiting configuration

### Environment Configuration
The application supports multiple environments (LOCAL, STAGING, PRODUCTION) with:
- Environment-specific documentation access controls
- Configurable admin panel settings
- Multiple database configurations (PostgreSQL, MySQL, SQLite)
- Redis configuration for caching, queuing, and rate limiting

### Development Patterns
- All models inherit from mixins (UUIDMixin, TimestampMixin, SoftDeleteMixin)
- Use FastCRUD for standardized CRUD operations
- Async/await throughout the application
- Type hints enforced with mypy
- Environment variables loaded from `src/.env`
- Pre-commit hooks enforce code quality standards

### Docker Setup
- Multi-service setup with web, worker, database, and Redis
- Volume mounts for development with hot reload
- Optional services: pgAdmin, nginx
- Automatic superuser creation via `create_superuser` service