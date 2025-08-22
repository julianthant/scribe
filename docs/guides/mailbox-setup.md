# Mailbox Integration Setup Guide

## Overview

This guide walks you through setting up the mailbox integration features in Scribe, including personal mailbox access, shared mailbox configuration, and voice attachment processing capabilities.

## Prerequisites

### Microsoft Graph API Access
- Azure AD tenant with appropriate permissions
- Application registration in Azure AD
- Required API permissions for mailbox operations
- Service principal with necessary roles

### Environment Setup
- Python 3.11 or higher
- Redis server for caching (recommended)
- Adequate storage for voice attachment processing
- Network connectivity to Microsoft Graph API

## Step 1: Azure AD Application Setup

### 1.1 Register Application in Azure AD

1. Navigate to Azure Portal → Azure Active Directory → App registrations
2. Click "New registration"
3. Configure the application:
   ```
   Name: Scribe Mailbox Integration
   Supported account types: Accounts in this organizational directory only
   Redirect URI: https://your-domain/auth/callback
   ```

### 1.2 Configure API Permissions

Add the following Microsoft Graph permissions:

#### Delegated Permissions (for user authentication)
```
Mail.Read                    # Read user mail
Mail.ReadWrite               # Read and write user mail  
Mail.Send                    # Send mail as user
MailboxSettings.Read         # Read mailbox settings
```

#### Application Permissions (for shared mailboxes)
```
Mail.Read                    # Read mail in all mailboxes
Mail.ReadWrite               # Read and write mail in all mailboxes
Mail.Send                    # Send mail from any mailbox
Directory.Read.All           # Read directory data
```

### 1.3 Grant Admin Consent

1. In the API permissions section, click "Grant admin consent"
2. Confirm the consent for all requested permissions

### 1.4 Create Client Secret

1. Navigate to "Certificates & secrets"
2. Click "New client secret"
3. Set description and expiration period
4. Copy the generated secret value (save securely)

## Step 2: Environment Configuration

### 2.1 Create Environment File

Create a `.env` file with the following configuration:

```bash
# Microsoft Graph API Configuration
GRAPH_CLIENT_ID=your_application_client_id
GRAPH_CLIENT_SECRET=your_client_secret_value
GRAPH_TENANT_ID=your_tenant_id
GRAPH_SCOPE=https://graph.microsoft.com/.default

# Redis Configuration (for caching)
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Voice Processing Configuration
VOICE_BATCH_SIZE=100
VOICE_PROCESSING_ENABLED=true
VOICE_TEMP_DIR=/tmp/voice_processing

# Shared Mailbox Configuration
SHARED_MAILBOX_CACHE_TTL=1800
MAX_CONCURRENT_MAILBOXES=5
ENABLE_CROSS_MAILBOX_SEARCH=true

# Performance Settings
MAX_MESSAGE_BATCH_SIZE=1000
DEFAULT_PAGE_SIZE=25
MAX_PAGE_SIZE=1000

# Security Settings
ENABLE_AUDIT_LOGGING=true
AUDIT_LOG_RETENTION_DAYS=90

# Feature Flags
ENABLE_VOICE_ORGANIZATION=true
ENABLE_ATTACHMENT_DOWNLOAD=true
ENABLE_MESSAGE_SEARCH=true
```

### 2.2 Install Dependencies

Install the required Python packages:

```bash
# Install base dependencies
pip install fastapi uvicorn

# Install Microsoft Graph SDK
pip install msgraph-sdk

# Install caching dependencies
pip install redis aioredis

# Install additional processing libraries
pip install python-multipart
pip install python-magic  # For file type detection
```

## Step 3: Service Configuration

### 3.1 Configure Authentication

Update your authentication configuration in `app/core/config.py`:

```python
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Microsoft Graph Configuration
    graph_client_id: str
    graph_client_secret: str
    graph_tenant_id: str
    graph_scope: str = "https://graph.microsoft.com/.default"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    
    # Voice Processing
    voice_batch_size: int = 100
    voice_processing_enabled: bool = True
    voice_temp_dir: str = "/tmp/voice_processing"
    
    # Shared Mailbox
    shared_mailbox_cache_ttl: int = 1800
    max_concurrent_mailboxes: int = 5
    enable_cross_mailbox_search: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### 3.2 Configure Dependency Injection

Ensure proper dependency injection setup in `app/dependencies/`:

```python
# app/dependencies/mail.py
from app.services.mail_service import MailService
from app.repositories.mail_repository import MailRepository
from app.core.config import settings

def get_mail_repository() -> MailRepository:
    return MailRepository(
        client_id=settings.graph_client_id,
        client_secret=settings.graph_client_secret,
        tenant_id=settings.graph_tenant_id
    )

def get_mail_service(
    mail_repository: MailRepository = Depends(get_mail_repository)
) -> MailService:
    return MailService(mail_repository)
```

## Step 4: Redis Cache Setup

### 4.1 Install Redis Server

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### macOS (using Homebrew)
```bash
brew install redis
brew services start redis
```

#### Docker
```bash
docker run -d --name redis-cache -p 6379:6379 redis:latest
```

### 4.2 Configure Redis for Production

Create a Redis configuration file (`redis.conf`):

```ini
# Network configuration
bind 127.0.0.1
port 6379

# Memory configuration
maxmemory 1gb
maxmemory-policy allkeys-lru

# Persistence configuration
save 900 1
save 300 10
save 60 10000

# Security
requirepass your_redis_password
```

### 4.3 Test Redis Connection

```python
import redis
import asyncio
import aioredis

async def test_redis():
    redis_client = await aioredis.from_url("redis://localhost:6379")
    await redis_client.set("test_key", "test_value")
    value = await redis_client.get("test_key")
    print(f"Redis test: {value}")
    await redis_client.close()

asyncio.run(test_redis())
```

## Step 5: Voice Processing Setup

### 5.1 Create Voice Processing Directory

```bash
# Create directory for temporary voice file processing
sudo mkdir -p /opt/voice_processing
sudo chown $USER:$USER /opt/voice_processing
sudo chmod 755 /opt/voice_processing
```

### 5.2 Configure Voice Processing Settings

```python
# app/core/config.py additions
class VoiceProcessingSettings(BaseModel):
    enabled: bool = True
    batch_size: int = 100
    temp_directory: str = "/opt/voice_processing"
    supported_formats: List[str] = [
        "audio/mpeg", "audio/wav", "audio/amr",
        "audio/3gpp", "audio/ogg", "audio/m4a"
    ]
    max_file_size_mb: int = 50
    cleanup_interval_minutes: int = 60
```

### 5.3 Test Voice Detection

```python
from app.services.voice_attachment_service import VoiceAttachmentService

# Test voice attachment detection
test_attachments = [
    {"name": "recording.mp3", "contentType": "audio/mpeg"},
    {"name": "voicemail.amr", "contentType": "audio/amr"},
    {"name": "document.pdf", "contentType": "application/pdf"}
]

service = VoiceAttachmentService(None, None)
for attachment in test_attachments:
    is_voice = service.is_voice_attachment(attachment)
    print(f"{attachment['name']}: {is_voice}")
```

## Step 6: Shared Mailbox Configuration

### 6.1 Configure Shared Mailbox Access

Ensure your Azure AD application has the necessary permissions to access shared mailboxes:

1. **Application Permissions**: `Mail.Read`, `Mail.ReadWrite`, `Mail.Send`
2. **Directory Permissions**: `Directory.Read.All` for mailbox discovery
3. **Exchange Permissions**: Configure in Exchange Admin Center

### 6.2 Grant Shared Mailbox Permissions

In Exchange Online PowerShell:

```powershell
# Connect to Exchange Online
Connect-ExchangeOnline

# Grant application access to shared mailboxes
Add-MailboxPermission -Identity "support@company.com" -User "Scribe App" -AccessRights FullAccess
Add-RecipientPermission -Identity "support@company.com" -Trustee "Scribe App" -AccessRights SendAs

# List current permissions
Get-MailboxPermission -Identity "support@company.com"
```

### 6.3 Test Shared Mailbox Access

```python
from app.services.shared_mailbox_service import SharedMailboxService

async def test_shared_mailbox_access():
    service = SharedMailboxService(repository)
    
    # Test listing accessible mailboxes
    mailboxes = await service.get_accessible_shared_mailboxes()
    print(f"Found {len(mailboxes.value)} accessible shared mailboxes")
    
    # Test accessing specific mailbox
    if mailboxes.value:
        first_mailbox = mailboxes.value[0]
        details = await service.get_shared_mailbox_details(first_mailbox.emailAddress)
        print(f"Access level: {details.accessLevel}")
```

## Step 7: API Testing and Validation

### 7.1 Start the Application

```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 7.2 Test Core Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Authentication check (requires valid token)
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/mail/folders

# Voice messages endpoint
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/mail/voice-messages

# Shared mailboxes endpoint
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/shared-mailboxes
```

### 7.3 Test Voice Organization

```bash
# Organize voice messages
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"targetFolderName": "Voice Messages", "createFolder": true}' \
  http://localhost:8000/api/v1/mail/organize-voice
```

## Step 8: Monitoring and Logging

### 8.1 Configure Application Logging

```python
# app/core/logging.py
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    # Create logger
    logger = logging.getLogger("scribe_mailbox")
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        "logs/mailbox.log", 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
```

### 8.2 Configure Health Checks

```python
# app/api/health.py
from fastapi import APIRouter
from app.services.mail_service import MailService
from app.core.cache import get_cache

router = APIRouter()

@router.get("/health/mailbox")
async def mailbox_health():
    checks = {
        "graph_api": await _check_graph_api(),
        "redis_cache": await _check_redis(),
        "voice_processing": await _check_voice_processing()
    }
    
    overall_healthy = all(checks.values())
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "checks": checks
    }
```

## Step 9: Production Deployment

### 9.1 Docker Configuration

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Create voice processing directory
RUN mkdir -p /opt/voice_processing

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.2 Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  scribe-mailbox:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GRAPH_CLIENT_ID=${GRAPH_CLIENT_ID}
      - GRAPH_CLIENT_SECRET=${GRAPH_CLIENT_SECRET}
      - GRAPH_TENANT_ID=${GRAPH_TENANT_ID}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    volumes:
      - voice_processing:/opt/voice_processing
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

volumes:
  voice_processing:
  redis_data:
```

### 9.3 Deploy to Production

```bash
# Build and start services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f scribe-mailbox

# Scale if needed
docker-compose up -d --scale scribe-mailbox=3
```

## Step 10: Security Hardening

### 10.1 Environment Security

```bash
# Secure environment file
chmod 600 .env
chown root:root .env

# Use secrets management in production
# - Azure Key Vault
# - AWS Secrets Manager  
# - Kubernetes Secrets
```

### 10.2 Network Security

```yaml
# docker-compose.yml network configuration
networks:
  scribe-internal:
    internal: true
  scribe-external:

services:
  scribe-mailbox:
    networks:
      - scribe-internal
      - scribe-external
  
  redis:
    networks:
      - scribe-internal
```

### 10.3 Application Security

```python
# Add rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

## Troubleshooting

### Common Issues

#### 1. Authentication Failures
```bash
# Check token validity
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://graph.microsoft.com/v1.0/me

# Verify permissions in Azure AD
# Check token scopes and expiration
```

#### 2. Voice Detection Issues
```python
# Debug voice attachment detection
from app.services.voice_attachment_service import VoiceAttachmentService

service = VoiceAttachmentService(None, None)
attachment = {"contentType": "audio/mpeg", "name": "test.mp3"}
is_voice = service.is_voice_attachment(attachment)
print(f"Voice detected: {is_voice}")
```

#### 3. Redis Connection Issues
```bash
# Test Redis connectivity
redis-cli ping

# Check Redis logs
docker-compose logs redis

# Test from application
python -c "import redis; r=redis.Redis(); print(r.ping())"
```

#### 4. Shared Mailbox Access Issues
- Verify application permissions in Azure AD
- Check Exchange Online permissions
- Validate shared mailbox configuration
- Review audit logs for access attempts

### Performance Optimization

#### 1. Batch Size Tuning
```python
# Adjust batch sizes based on mailbox size
VOICE_BATCH_SIZE=50   # For large mailboxes
VOICE_BATCH_SIZE=200  # For small mailboxes
```

#### 2. Cache Configuration
```python
# Optimize cache TTL values
SHARED_MAILBOX_CACHE_TTL=3600    # 1 hour for stable data
FOLDER_CACHE_TTL=1800            # 30 minutes for folder structure
```

#### 3. Memory Management
```python
# Monitor memory usage
import psutil
print(f"Memory usage: {psutil.virtual_memory().percent}%")
```

## Next Steps

After successful setup:

1. **Configure monitoring and alerting**
2. **Set up automated backups for configuration**
3. **Implement log aggregation and analysis**
4. **Plan for scaling based on usage patterns**
5. **Schedule regular security reviews and updates**

For additional support and advanced configurations, refer to:
- [API Reference](../api/mailbox-integration.md)
- [Architecture Overview](../architecture/mailbox-integration.md)
- [OAuth Setup Guide](oauth-setup.md)

---

*This setup guide provides a comprehensive foundation for deploying mailbox integration capabilities. Regular updates ensure compatibility with Microsoft Graph API changes and security best practices.*