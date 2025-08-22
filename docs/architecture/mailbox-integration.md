# Mailbox Integration Architecture

## System Overview

The mailbox integration system provides comprehensive email management capabilities through a layered architecture that separates concerns between API presentation, business logic, data access, and external service integration.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Applications                     │
│  Web UI  │  Mobile App  │  External APIs  │  PowerBI      │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                      │
│  FastAPI Router  │  Authentication  │  Rate Limiting      │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                     API Endpoints Layer                     │
├─────────────────────────────────────────────────────────────┤
│  /api/v1/mail/*               │  /api/v1/shared-mailboxes/* │
│  • Folders (2 endpoints)      │  • Access (2 endpoints)     │
│  • Messages (5 endpoints)     │  • Messages (3 endpoints)   │
│  • Attachments (3 endpoints)  │  • Organization (2 endpoints)│
│  • Voice (6 endpoints)        │  • Search (1 endpoint)      │
│  • Search (1 endpoint)        │  • Analytics (2 endpoints)  │
│  • Statistics (2 endpoints)   │  • Voice (2 endpoints)      │
│  Total: 19 endpoints          │  Total: 12 endpoints        │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                      │
├─────────────────────────────────────────────────────────────┤
│  MailService                  │  SharedMailboxService        │
│  • Folder Operations          │  • Access Management         │
│  • Message Processing         │  • Permission Validation     │
│  • Voice Organization         │  • Cross-Mailbox Operations  │
│  • Statistics Generation      │  • Audit Logging             │
│                               │                              │
│  VoiceAttachmentService       │  CachingService              │
│  • Voice Detection            │  • Mailbox Metadata Cache    │
│  • Audio Format Processing    │  • Permission Cache          │
│  • Batch Organization         │  • Query Result Cache        │
│  • Metadata Extraction        │  • Performance Optimization  │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layer                         │
├─────────────────────────────────────────────────────────────┤
│  MailRepository               │  SharedMailboxRepository     │
│  • Graph API Integration      │  • Multi-Mailbox Access     │
│  • Message CRUD Operations    │  • Permission Queries       │
│  • Attachment Processing      │  • Delegation Management     │
│  • Search Implementation      │  • Audit Trail Persistence  │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                   External Services Layer                   │
├─────────────────────────────────────────────────────────────┤
│  Microsoft Graph API         │  Azure Active Directory     │
│  • Mailbox Operations         │  • Authentication Service   │
│  • Attachment Downloads       │  • Permission Management    │
│  • Search Queries             │  • Token Validation         │
│  • Batch Operations           │  • Role-Based Access        │
│                               │                              │
│  Redis Cache                  │  Application Insights       │
│  • Performance Caching        │  • Telemetry & Monitoring   │
│  • Session Storage            │  • Performance Metrics      │
│  • Rate Limit Tracking        │  • Error Tracking           │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. API Endpoints Layer

#### Personal Mailbox Endpoints (`app/api/v1/endpoints/mail.py`)
- **Responsibility**: HTTP request/response handling for personal mailbox operations
- **Key Features**:
  - Comprehensive CRUD operations for folders and messages
  - Advanced voice attachment processing endpoints
  - Flexible search and filtering capabilities
  - Statistics and analytics endpoints
- **Security**: JWT token validation, user context injection
- **Error Handling**: Structured error responses with appropriate HTTP status codes

#### Shared Mailbox Endpoints (`app/api/v1/endpoints/shared_mailbox.py`)
- **Responsibility**: HTTP request/response handling for shared mailbox operations
- **Key Features**:
  - Multi-mailbox access management
  - Cross-mailbox search capabilities
  - Send-as-shared-mailbox functionality
  - Usage analytics and reporting
- **Security**: Permission validation, access control enforcement
- **Audit**: Operation logging for compliance requirements

### 2. Business Logic Layer

#### MailService (`app/services/mail_service.py`)
- **Responsibility**: Core business logic for personal mailbox operations
- **Key Capabilities**:
  - Folder lifecycle management (create, organize, cleanup)
  - Message processing and organization workflows
  - Voice attachment detection and batch processing
  - Statistical analysis and reporting
- **Business Rules**:
  - Automatic folder creation for voice organization
  - Duplicate detection and handling
  - Message validation and sanitization
- **Performance**: Optimized for large mailbox processing

#### SharedMailboxService (`app/services/shared_mailbox_service.py`)
- **Responsibility**: Business logic for shared mailbox management
- **Key Capabilities**:
  - Access validation and permission enforcement
  - Cross-mailbox operations coordination
  - Delegation and send-as functionality
  - Comprehensive audit logging
- **Caching Strategy**:
  - Mailbox metadata caching (30 min TTL)
  - Permission caching (15 min TTL)
  - Query result caching for frequently accessed data
- **Concurrency**: Parallel processing for cross-mailbox operations

#### VoiceAttachmentService (`app/services/voice_attachment_service.py`)
- **Responsibility**: Specialized voice attachment processing
- **Audio Format Support**: 30+ audio formats including:
  - Standard formats (MP3, WAV, OGG, FLAC)
  - Voice-optimized formats (AMR, 3GPP)
  - Enterprise formats (WMA, WebM, AIFF)
- **Detection Algorithm**:
  ```python
  def is_voice_attachment(attachment):
      # Multi-layer detection approach
      return (
          mime_type_is_audio(attachment.contentType) or
          file_extension_is_audio(attachment.name) or
          content_analysis_indicates_audio(attachment)
      )
  ```
- **Processing Pipeline**:
  1. Detection and classification
  2. Metadata extraction
  3. Batch organization
  4. Statistics generation

### 3. Repository Layer

#### MailRepository (`app/repositories/mail_repository.py`)
- **Responsibility**: Data access layer for personal mailbox operations
- **Graph API Integration**:
  - Efficient pagination handling
  - Batch operation optimization
  - Connection pooling and retry logic
- **Query Optimization**:
  - Selective field retrieval
  - Filter pushdown to Graph API
  - Caching of frequently accessed data

#### SharedMailboxRepository (`app/repositories/shared_mailbox_repository.py`)
- **Responsibility**: Data access layer for shared mailbox operations
- **Multi-Tenant Support**: Handles access to multiple shared mailboxes
- **Permission Management**: Integrates with Azure AD for permission queries
- **Audit Trail**: Comprehensive operation logging for compliance

### 4. Data Models

#### Mail Models (`app/models/mail.py`)
- **Core Entities**:
  - `Message`: Email message with full metadata
  - `MailFolder`: Folder structure with hierarchy support
  - `Attachment`: Base attachment model with polymorphic support
  - `VoiceAttachment`: Specialized voice attachment with audio metadata
- **Request/Response Models**:
  - Validation-enabled input models
  - Structured response models with pagination support
  - Search and filter models for complex queries

#### Shared Mailbox Models (`app/models/shared_mailbox.py`)
- **Core Entities**:
  - `SharedMailbox`: Mailbox configuration and metadata
  - `SharedMailboxAccess`: Permission and access level information
  - `SharedMailboxStatistics`: Usage analytics and metrics
- **Permission Models**:
  - `SharedMailboxPermission`: User-specific permissions
  - `DelegationType`: Send-as and send-on-behalf permissions
  - `AccessLevel`: Hierarchical access control (Owner, Editor, Author, Reviewer)

## Design Patterns

### 1. Repository Pattern
```python
class BaseRepository(ABC, Generic[T]):
    @abstractmethod
    async def create(self, entity: T) -> T: ...
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]: ...
    
    @abstractmethod
    async def update(self, id: str, entity: T) -> Optional[T]: ...
```

**Benefits**:
- Clean separation of data access logic
- Testability through interface abstraction
- Consistent patterns across all repositories

### 2. Service Layer Pattern
```python
class MailService:
    def __init__(self, mail_repository: MailRepository):
        self.mail_repository = mail_repository
    
    async def organize_voice_messages(self, folder_name: str) -> OrganizeVoiceResponse:
        # Business logic orchestration
        folder = await self._ensure_voice_folder(folder_name)
        messages = await self._find_voice_messages()
        return await self._move_messages_to_folder(messages, folder)
```

**Benefits**:
- Business logic encapsulation
- Transaction boundary management
- Cross-cutting concern handling (logging, validation)

### 3. Dependency Injection
```python
def get_mail_service(
    mail_repository: MailRepository = Depends(get_mail_repository)
) -> MailService:
    return MailService(mail_repository)

@router.get("/messages")
async def list_messages(
    mail_service: MailService = Depends(get_mail_service)
):
    return await mail_service.get_messages()
```

**Benefits**:
- Loose coupling between components
- Easy testing with mock dependencies
- Configuration flexibility

## Performance Optimization

### 1. Caching Strategy

#### Multi-Level Caching
```python
# L1: In-Memory Application Cache
@lru_cache(maxsize=128)
def get_folder_hierarchy():
    return cached_hierarchy

# L2: Redis Distributed Cache  
@cache.memoize(timeout=1800)
async def get_shared_mailbox_permissions(email: str):
    return await repository.get_permissions(email)

# L3: Graph API Response Caching
headers = {"If-None-Match": etag}
```

#### Cache Invalidation Strategy
- **Time-based**: TTL for frequently changing data
- **Event-based**: Invalidation on write operations
- **Pattern-based**: Bulk invalidation using key patterns

### 2. Batch Processing

#### Voice Attachment Organization
```python
async def organize_voice_messages(self, batch_size: int = 100):
    total_processed = 0
    
    async for message_batch in self._get_messages_in_batches(batch_size):
        voice_messages = await self._filter_voice_messages(message_batch)
        await self._move_messages_batch(voice_messages)
        total_processed += len(voice_messages)
        
    return total_processed
```

#### Concurrent Processing
```python
async def search_shared_mailboxes(self, mailboxes: List[str]):
    tasks = [self._search_mailbox(mb) for mb in mailboxes]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return self._consolidate_results(results)
```

### 3. Query Optimization

#### Graph API Query Patterns
```python
# Efficient field selection
select_fields = "id,subject,sender,receivedDateTime,hasAttachments"

# Filter pushdown
filter_query = "hasAttachments eq true and receivedDateTime ge 2024-01-01"

# Batch requests
batch_requests = [
    {"id": "1", "method": "GET", "url": "/me/messages"},
    {"id": "2", "method": "GET", "url": "/me/mailFolders"}
]
```

## Security Architecture

### 1. Authentication Flow
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│  API Gateway │───▶│ Azure AD    │───▶│ Graph API   │
│ Application │    │  (FastAPI)  │    │ Validation  │    │ Operations  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │
                           ▼
                   ┌─────────────┐
                   │  User Context│
                   │  Injection  │
                   └─────────────┘
```

### 2. Permission Model

#### Shared Mailbox Access Levels
```python
class SharedMailboxAccessLevel(Enum):
    OWNER = "owner"          # Full management access
    EDITOR = "editor"        # Read/write access
    AUTHOR = "author"        # Create and send messages
    REVIEWER = "reviewer"    # Read-only access
    CONTRIBUTOR = "contributor" # Add content only
    NONE = "none"           # No access
```

#### Permission Validation
```python
async def _validate_mailbox_access(self, email: str, operation: str):
    access = await self.get_shared_mailbox_details(email)
    
    required_permissions = {
        "read": ["owner", "editor", "author", "reviewer"],
        "write": ["owner", "editor", "author"],
        "send": ["owner", "editor", "author"],
        "manage": ["owner"]
    }
    
    if access.accessLevel not in required_permissions[operation]:
        raise AuthorizationError(f"Insufficient permissions for {operation}")
```

### 3. Audit and Compliance

#### Audit Entry Structure
```python
class SharedMailboxAuditEntry(BaseModel):
    mailboxId: str
    userId: str
    action: str
    details: Dict[str, Any]
    timestamp: datetime
    ipAddress: Optional[str]
    userAgent: Optional[str]
    success: bool
    errorMessage: Optional[str]
```

#### Compliance Features
- **Data Retention**: Configurable audit log retention periods
- **Privacy Protection**: PII masking in audit logs  
- **Access Tracking**: Complete audit trail of all operations
- **Regulatory Compliance**: GDPR, SOX, HIPAA compliance features

## Scalability Considerations

### 1. Horizontal Scaling
- **Stateless Services**: All services designed as stateless components
- **Load Balancing**: Round-robin distribution across service instances
- **Database Sharding**: Partition data by tenant/mailbox for large deployments

### 2. Vertical Scaling
- **Memory Optimization**: Efficient object lifecycle management
- **CPU Optimization**: Async/await patterns for non-blocking operations
- **I/O Optimization**: Connection pooling and batch operations

### 3. Monitoring and Observability

#### Key Performance Indicators
```python
@metrics.histogram("voice_processing_duration")
@metrics.counter("voice_attachments_processed")
async def process_voice_attachments(self, messages: List[Message]):
    start_time = time.time()
    
    try:
        result = await self._process_attachments(messages)
        metrics.counter("voice_processing_success").inc()
        return result
    except Exception as e:
        metrics.counter("voice_processing_errors").inc()
        raise
    finally:
        duration = time.time() - start_time
        metrics.histogram("voice_processing_duration").observe(duration)
```

#### Health Checks
```python
@router.get("/health/mailbox")
async def mailbox_health_check():
    checks = {
        "graph_api": await check_graph_api_connectivity(),
        "cache_service": await check_cache_service(),
        "database": await check_database_connectivity()
    }
    
    overall_health = all(checks.values())
    
    return {
        "status": "healthy" if overall_health else "unhealthy",
        "checks": checks,
        "timestamp": datetime.utcnow()
    }
```

## Deployment Architecture

### 1. Container Strategy
```dockerfile
# Multi-stage build for optimization
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY ./app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Infrastructure Requirements
- **CPU**: Minimum 2 cores, recommended 4+ cores for voice processing
- **Memory**: Minimum 2GB RAM, recommended 4GB+ for large mailboxes
- **Storage**: SSD storage for temporary voice file processing
- **Network**: High bandwidth for Graph API operations

### 3. Configuration Management
```python
class MailboxSettings(BaseSettings):
    # Graph API Configuration
    graph_client_id: str
    graph_client_secret: str
    graph_tenant_id: str
    
    # Performance Settings
    voice_batch_size: int = 100
    cache_ttl: int = 3600
    max_concurrent_operations: int = 10
    
    # Feature Flags
    enable_voice_processing: bool = True
    enable_cross_mailbox_search: bool = True
    enable_audit_logging: bool = True
    
    class Config:
        env_file = ".env"
```

## Future Architectural Enhancements

### 1. Event-Driven Architecture
- **Event Sourcing**: Capture all mailbox operations as events
- **CQRS**: Separate read and write models for better performance
- **Event Bus**: Asynchronous processing of mailbox events

### 2. Microservices Evolution
- **Service Decomposition**: Split into focused microservices
- **API Gateway**: Centralized routing and cross-cutting concerns
- **Service Mesh**: Advanced networking and observability

### 3. Advanced Analytics
- **Machine Learning**: Intelligent email categorization and insights
- **Real-time Analytics**: Stream processing for live mailbox metrics
- **Predictive Analytics**: Forecast mailbox usage and optimization opportunities

---

*This architecture document provides the foundation for understanding, maintaining, and extending the mailbox integration system. Regular reviews and updates ensure the architecture remains aligned with business requirements and technology evolution.*