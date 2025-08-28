# Data Flow Architecture

This document describes how data flows through the Scribe system for various operations, including detailed sequence diagrams and process flows.

## Table of Contents

1. [Authentication Data Flow](#authentication-data-flow)
2. [Mail Operations Data Flow](#mail-operations-data-flow)
3. [Shared Mailbox Data Flow](#shared-mailbox-data-flow)
4. [Voice Processing Data Flow](#voice-processing-data-flow)
5. [Caching Data Flow](#caching-data-flow)
6. [Error Handling Flow](#error-handling-flow)

## Authentication Data Flow

### OAuth Login Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI App
    participant AUTH as Auth Endpoint
    participant OAUTH as OAuth Service
    participant AZURE_AUTH as Azure Auth Service
    participant AAD as Azure AD
    participant GRAPH as Microsoft Graph
    participant USER_REPO as User Repository
    participant DB as Database
    
    Note over C,DB: Login Initiation
    C->>API: GET /auth/login
    API->>AUTH: Route to auth endpoint
    AUTH->>OAUTH: initiate_login()
    OAUTH->>OAUTH: Generate CSRF state
    OAUTH->>AZURE_AUTH: get_authorization_url(state)
    AZURE_AUTH->>AAD: Request authorization URL
    AAD-->>AZURE_AUTH: Return auth URL + parameters
    AZURE_AUTH-->>OAUTH: Auth data with URL
    OAUTH->>OAUTH: Store state in session
    OAUTH-->>AUTH: Return auth data
    AUTH-->>API: RedirectResponse(auth_url)
    API-->>C: HTTP 302 Redirect to Azure AD
    
    Note over C,DB: User Authentication at Azure
    C->>AAD: User authenticates
    AAD->>API: GET /auth/callback?code=xxx&state=yyy
    
    Note over C,DB: Token Exchange
    API->>AUTH: Route callback
    AUTH->>OAUTH: handle_callback(callback_url, state)
    OAUTH->>OAUTH: Validate CSRF state
    OAUTH->>AZURE_AUTH: acquire_token_by_auth_code(callback_url)
    AZURE_AUTH->>AAD: POST token exchange
    AAD-->>AZURE_AUTH: Access + refresh tokens
    AZURE_AUTH-->>OAUTH: Token data
    
    Note over C,DB: User Profile & Session Creation
    OAUTH->>AZURE_AUTH: get_user_profile(access_token)
    AZURE_AUTH->>GRAPH: GET /me
    GRAPH-->>AZURE_AUTH: User profile data
    AZURE_AUTH-->>OAUTH: User profile
    OAUTH->>USER_REPO: get_or_create_by_azure_id()
    USER_REPO->>DB: Query/Insert user
    DB-->>USER_REPO: User record
    USER_REPO-->>OAUTH: User entity
    OAUTH->>USER_REPO: create_session(user, tokens)
    USER_REPO->>DB: Insert session record
    DB-->>USER_REPO: Session record
    USER_REPO-->>OAUTH: Session entity
    OAUTH-->>AUTH: TokenResponse
    AUTH-->>API: Return TokenResponse
    API-->>C: JSON with tokens and user info
```

### Token Refresh Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI App
    participant AUTH as Auth Endpoint
    participant OAUTH as OAuth Service
    participant AZURE_AUTH as Azure Auth Service
    participant AAD as Azure AD
    participant USER_REPO as User Repository
    participant DB as Database
    
    C->>API: POST /auth/refresh
    API->>AUTH: Route to refresh endpoint
    AUTH->>OAUTH: refresh_user_token(refresh_token, session_id)
    OAUTH->>AZURE_AUTH: refresh_token(refresh_token)
    AZURE_AUTH->>AAD: POST token refresh
    AAD-->>AZURE_AUTH: New access + refresh tokens
    AZURE_AUTH-->>OAUTH: Updated token data
    
    alt Session ID provided
        OAUTH->>USER_REPO: update_session(session_id, new_tokens)
        USER_REPO->>DB: Update session record
        DB-->>USER_REPO: Success
        USER_REPO-->>OAUTH: Updated session
    end
    
    OAUTH-->>AUTH: TokenResponse with new tokens
    AUTH-->>API: Return TokenResponse
    API-->>C: JSON with refreshed tokens
```

## Mail Operations Data Flow

### Personal Mail Access Flow

```mermaid
flowchart TD
    A[Client Request] --> B{Valid Access Token?}
    B -->|No| C[Return 401 Unauthorized]
    B -->|Yes| D[Extract User Info from Token]
    D --> E{Check Cache}
    E -->|Hit| F[Return Cached Data]
    E -->|Miss| G[Call Microsoft Graph API]
    G --> H{API Success?}
    H -->|No| I[Handle API Error]
    H -->|Yes| J[Process API Response]
    J --> K[Transform Data Format]
    K --> L[Update Cache]
    L --> M[Return Data to Client]
    I --> N[Log Error]
    N --> O[Return Error Response]
```

### Mail Message Retrieval Sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Mail Endpoint
    participant MAIL_SVC as Mail Service
    participant CACHE as In-Memory Cache
    participant AZURE_GRAPH as Azure Graph Service
    participant GRAPH as Microsoft Graph API
    participant MAIL_REPO as Mail Repository
    participant DB as Database
    
    C->>API: GET /mail/messages?folder=inbox&$top=50
    API->>API: Validate access token
    API->>MAIL_SVC: get_messages(user, folder, params)
    
    Note over MAIL_SVC,CACHE: Check Cache First
    MAIL_SVC->>CACHE: get(cache_key)
    CACHE-->>MAIL_SVC: Cache miss
    
    Note over MAIL_SVC,GRAPH: Fetch from Graph API
    MAIL_SVC->>AZURE_GRAPH: get_messages(access_token, folder, params)
    AZURE_GRAPH->>GRAPH: GET /me/mailFolders/{id}/messages
    GRAPH-->>AZURE_GRAPH: Message data (JSON)
    AZURE_GRAPH-->>MAIL_SVC: Transformed messages
    
    Note over MAIL_SVC,DB: Update Cache & Database
    MAIL_SVC->>CACHE: set(cache_key, messages, ttl=300)
    MAIL_SVC->>MAIL_REPO: update_folder_sync_status()
    MAIL_REPO->>DB: Update sync timestamp
    DB-->>MAIL_REPO: Success
    
    MAIL_SVC-->>API: Messages response
    API-->>C: JSON response with messages
```

## Shared Mailbox Data Flow

### Shared Mailbox Discovery Flow

```mermaid
flowchart TD
    A[Request Shared Mailboxes] --> B[Validate User Permissions]
    B --> C{User Has Access?}
    C -->|No| D[Return 403 Forbidden]
    C -->|Yes| E[Get Configured Mailboxes]
    E --> F[Test Access to Each Mailbox]
    F --> G[Filter Accessible Mailboxes]
    G --> H[Return Available Mailboxes]
```

### Shared Mailbox Message Access

```mermaid
sequenceDiagram
    participant C as Client
    participant API as SharedMailbox Endpoint
    participant SM_SVC as SharedMailbox Service
    participant AZURE_MAIL as Azure Mail Service
    participant GRAPH as Microsoft Graph API
    participant SM_REPO as SharedMailbox Repository
    participant DB as Database
    
    C->>API: GET /shared-mailbox/{email}/messages
    API->>API: Validate user access token
    
    Note over API,DB: Permission Check
    API->>SM_SVC: get_messages(user, mailbox_email, params)
    SM_SVC->>SM_REPO: validate_user_access(user, mailbox_email)
    SM_REPO->>DB: Query user permissions
    DB-->>SM_REPO: Permission status
    SM_REPO-->>SM_SVC: Access granted/denied
    
    alt Access Denied
        SM_SVC-->>API: AuthorizationError
        API-->>C: 403 Forbidden
    end
    
    Note over API,GRAPH: Fetch Messages
    SM_SVC->>AZURE_MAIL: get_shared_mailbox_messages(token, email, params)
    AZURE_MAIL->>GRAPH: GET /users/{email}/messages
    GRAPH-->>AZURE_MAIL: Message data
    AZURE_MAIL-->>SM_SVC: Processed messages
    
    Note over API,DB: Audit Logging
    SM_SVC->>SM_REPO: log_access(user, mailbox, action="read")
    SM_REPO->>DB: Insert audit record
    
    SM_SVC-->>API: Messages response
    API-->>C: JSON with shared mailbox messages
```

## Voice Processing Data Flow

### Voice Attachment Upload and Processing

```mermaid
flowchart TD
    A[Voice File Upload] --> B[Store in Azure Blob Storage]
    B --> C[Generate Blob URL]
    C --> D[Create VoiceAttachment Record]
    D --> E[Extract Audio Metadata]
    E --> F[Queue for Transcription]
    F --> G[Update Status: Processing]
    
    G --> H[Azure AI Foundry Processing]
    H --> I{Transcription Success?}
    I -->|Yes| J[Parse Transcription Results]
    I -->|No| K[Log Error & Retry]
    
    J --> L[Create Transcription Record]
    L --> M[Create Transcription Segments]
    M --> N[Update Status: Completed]
    N --> O[Notify User]
    
    K --> P{Max Retries Exceeded?}
    P -->|No| H
    P -->|Yes| Q[Update Status: Failed]
    Q --> R[Create Error Record]
    R --> S[Notify User of Failure]
```

### Voice Processing Sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Voice Endpoint
    participant VA_SVC as VoiceAttachment Service
    participant BLOB as Azure Blob Service
    participant AI as Azure AI Foundry Service
    participant TRANS_SVC as Transcription Service
    participant VA_REPO as VoiceAttachment Repository
    participant TRANS_REPO as Transcription Repository
    participant DB as Database
    
    Note over C,DB: File Upload
    C->>API: POST /voice/upload (multipart/form-data)
    API->>VA_SVC: upload_voice_file(user, file)
    VA_SVC->>BLOB: upload_blob(file_data, container)
    BLOB-->>VA_SVC: Blob URL + metadata
    VA_SVC->>VA_REPO: create_voice_attachment(user, blob_info)
    VA_REPO->>DB: Insert voice_attachment record
    DB-->>VA_REPO: VoiceAttachment entity
    VA_REPO-->>VA_SVC: VoiceAttachment
    VA_SVC-->>API: Upload response
    API-->>C: JSON with attachment ID
    
    Note over C,DB: Transcription Processing (Async)
    VA_SVC->>TRANS_SVC: process_transcription(voice_attachment)
    TRANS_SVC->>AI: submit_transcription_job(blob_url)
    AI-->>TRANS_SVC: Job ID + status
    TRANS_SVC->>TRANS_REPO: create_transcription(voice_attachment, job_id)
    TRANS_REPO->>DB: Insert transcription record
    
    Note over C,DB: Polling/Webhook for Results
    loop Every 30 seconds
        TRANS_SVC->>AI: get_transcription_status(job_id)
        AI-->>TRANS_SVC: Status + results (if complete)
    end
    
    alt Transcription Complete
        TRANS_SVC->>TRANS_REPO: update_transcription_results(results)
        TRANS_REPO->>DB: Update transcription + create segments
        TRANS_SVC->>VA_REPO: update_status(attachment_id, "completed")
        VA_REPO->>DB: Update status
    else Transcription Failed
        TRANS_SVC->>TRANS_REPO: create_transcription_error(error_details)
        TRANS_REPO->>DB: Insert error record
        TRANS_SVC->>VA_REPO: update_status(attachment_id, "failed")
        VA_REPO->>DB: Update status
    end
```

## Caching Data Flow

### In-Memory Cache Strategy

```mermaid
flowchart TD
    A[API Request] --> B{Check Cache}
    B -->|Hit| C[Return Cached Data]
    B -->|Miss| D[Fetch from Source]
    D --> E[Process Data]
    E --> F{Cache Size Check}
    F -->|Within Limit| G[Store in Cache]
    F -->|Over Limit| H[Evict LRU Items]
    H --> G
    G --> I[Return Data]
    C --> I
    
    J[Background Process] --> K[Check TTL Expiration]
    K --> L{Items Expired?}
    L -->|Yes| M[Remove Expired Items]
    L -->|No| N[Wait Next Interval]
    M --> N
```

### Cache Operations Sequence

```mermaid
sequenceDiagram
    participant SVC as Service Layer
    participant CACHE as In-Memory Cache
    participant SRC as Data Source
    
    Note over SVC,SRC: Cache Read Operation
    SVC->>CACHE: get(key)
    alt Cache Hit
        CACHE-->>SVC: Cached value
    else Cache Miss
        CACHE-->>SVC: None
        SVC->>SRC: fetch_data()
        SRC-->>SVC: Fresh data
        SVC->>CACHE: set(key, data, ttl)
        CACHE-->>SVC: Success
    end
    
    Note over SVC,SRC: Cache Write Operation
    SVC->>CACHE: set(key, value, ttl)
    alt Cache Full
        CACHE->>CACHE: Evict LRU items
        CACHE->>CACHE: Store new value
    else Cache Available
        CACHE->>CACHE: Store new value
    end
    CACHE-->>SVC: Success/Failure
    
    Note over SVC,SRC: Cache Maintenance
    CACHE->>CACHE: Background cleanup
    CACHE->>CACHE: Remove expired items
    CACHE->>CACHE: Update access timestamps
```

## Error Handling Flow

### Global Error Handling

```mermaid
flowchart TD
    A[API Request] --> B[Endpoint Handler]
    B --> C{Exception Thrown?}
    C -->|No| D[Normal Response]
    C -->|Yes| E{Exception Type}
    
    E -->|ValidationError| F[400 Bad Request]
    E -->|AuthenticationError| G[401 Unauthorized]
    E -->|AuthorizationError| H[403 Forbidden]
    E -->|NotFoundError| I[404 Not Found]
    E -->|DatabaseError| J[500 Internal Error]
    E -->|RateLimitError| K[429 Too Many Requests]
    E -->|ScribeBaseException| L[500 Internal Error]
    E -->|UnhandledException| M[500 Generic Error]
    
    F --> N[Log Error Details]
    G --> N
    H --> N
    I --> N
    J --> O[Log Error + Hide Details]
    K --> N
    L --> O
    M --> O
    
    N --> P[Return Error Response]
    O --> P
    D --> Q[Return Success Response]
    P --> R[Client Receives Response]
    Q --> R
```

---

**File References:**
- OAuth Service Flow: `app/services/OAuthService.py:45-204`
- Mail Service Operations: `app/services/MailService.py:1-300`
- Cache Implementation: `app/core/Cache.py:1-200`
- Error Handlers: `app/main.py:155-258`

**Related Documentation:**
- [Architecture Overview](overview.md)
- [Components Detail](components.md)
- [API Documentation](../api/)
- [Service Documentation](../services/)