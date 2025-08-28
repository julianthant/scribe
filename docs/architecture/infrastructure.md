# Infrastructure Architecture

This document describes the infrastructure components, deployment architecture, and Azure services integration for the Scribe application.

## Table of Contents

1. [Infrastructure Overview](#infrastructure-overview)
2. [Azure Services Architecture](#azure-services-architecture)
3. [Deployment Models](#deployment-models)
4. [Network Architecture](#network-architecture)
5. [Data Storage Architecture](#data-storage-architecture)
6. [Security Infrastructure](#security-infrastructure)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Disaster Recovery](#disaster-recovery)

## Infrastructure Overview

Scribe is designed as a cloud-native application optimized for Azure infrastructure, supporting both traditional VM deployment and serverless Azure Functions deployment.

```mermaid
graph TB
    subgraph "Azure Cloud"
        subgraph "Identity & Access"
            AAD[Azure Active Directory]
            RBAC[Role-Based Access Control]
        end
        
        subgraph "Compute Services"
            VM[Azure Virtual Machines]
            FUNC[Azure Functions]
            CONTAINER[Container Instances]
        end
        
        subgraph "Data Services"
            SQL[Azure SQL Database]
            BLOB[Azure Blob Storage]
            CACHE[In-Memory Cache]
        end
        
        subgraph "AI/ML Services"
            AI[Azure AI Foundry]
            SPEECH[Speech Services]
        end
        
        subgraph "Integration Services"
            GRAPH[Microsoft Graph API]
            MONITOR[Azure Monitor]
            LOGS[Log Analytics]
        end
    end
    
    subgraph "External Services"
        O365[Office 365]
        TEAMS[Microsoft Teams]
    end
    
    VM --> SQL
    FUNC --> SQL
    VM --> BLOB
    FUNC --> BLOB
    VM --> AAD
    FUNC --> AAD
    
    AAD --> GRAPH
    GRAPH --> O365
    GRAPH --> TEAMS
    
    AI --> SPEECH
    FUNC --> AI
    VM --> AI
    
    VM --> MONITOR
    FUNC --> MONITOR
    MONITOR --> LOGS
```

## Azure Services Architecture

### Core Azure Services

#### Azure Active Directory (AAD)
**Purpose**: Identity and access management
**Configuration**:
- App registrations for OAuth 2.0
- User and group management
- Conditional access policies
- Multi-factor authentication

**Integration Points**:
```python
# File: app/core/config.py (settings configuration)
azure_tenant_id = "your-tenant-id"
azure_client_id = "your-client-id" 
azure_client_secret = "your-client-secret"  # From Key Vault
azure_redirect_uri = "https://your-app.com/auth/callback"
```

#### Azure SQL Database
**Purpose**: Primary data storage with normalized schema
**Configuration**:
- Standard S2 tier (50 DTU minimum for development)
- Always Encrypted for sensitive data
- Row-Level Security (RLS) enabled
- Automated backups with 7-day retention

**Schema Design**:
```sql
-- Normalized tables following 3NF
CREATE TABLE users (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    azure_id NVARCHAR(100) NOT NULL UNIQUE,
    email NVARCHAR(255) NOT NULL UNIQUE,
    is_active BIT DEFAULT 1,
    role NVARCHAR(20) DEFAULT 'user',
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);
```

#### Azure Blob Storage
**Purpose**: Voice attachment and file storage
**Configuration**:
- Hot tier for active files
- Cool tier for archived files
- Lifecycle management for automatic tiering
- SAS tokens for secure access

**Container Structure**:
```
scribe-storage/
├── voice-attachments/
│   ├── {user-id}/
│   │   ├── {attachment-id}.wav
│   │   └── {attachment-id}.mp3
└── transcriptions/
    └── {user-id}/
        └── {transcription-id}.json
```

### AI and Integration Services

#### Azure AI Foundry
**Purpose**: Voice transcription and AI processing
**Features**:
- Speech-to-text conversion
- Multiple audio format support
- Real-time and batch processing
- Custom vocabulary support

#### Microsoft Graph API
**Purpose**: Office 365 integration
**Scopes Required**:
- `https://graph.microsoft.com/Mail.Read`
- `https://graph.microsoft.com/Mail.ReadWrite`
- `https://graph.microsoft.com/Mail.Send`
- `https://graph.microsoft.com/User.Read`

## Deployment Models

### Azure Functions Deployment (Recommended)

```mermaid
graph TB
    subgraph "Azure Functions"
        FA[Function App]
        PLAN[Consumption Plan]
        SLOT[Deployment Slots]
    end
    
    subgraph "Supporting Services"
        STORAGE[Storage Account]
        APPINS[Application Insights]
        KEYVAULT[Key Vault]
    end
    
    subgraph "External Dependencies"
        SQL[Azure SQL Database]
        BLOB[Blob Storage]
        AAD[Azure AD]
    end
    
    FA --> STORAGE
    FA --> APPINS
    FA --> KEYVAULT
    FA --> SQL
    FA --> BLOB
    FA --> AAD
    
    PLAN --> FA
    SLOT --> FA
```

**Advantages**:
- Automatic scaling based on demand
- Pay-per-execution pricing model
- Built-in monitoring and diagnostics
- Integrated with Azure ecosystem
- No server management overhead

**Configuration**:
```python
# File: requirements.txt (Azure Functions specific)
azure-functions==1.18.0
azure-functions-worker==1.0.15
azure-identity==1.15.0
azure-keyvault-secrets==4.7.0
```

### Virtual Machine Deployment

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Azure Load Balancer]
        HEALTH[Health Probes]
    end
    
    subgraph "VM Scale Set"
        VM1[VM Instance 1]
        VM2[VM Instance 2]
        VM3[VM Instance N]
    end
    
    subgraph "Storage"
        DISK[Managed Disks]
        BACKUP[VM Backup]
    end
    
    LB --> VM1
    LB --> VM2
    LB --> VM3
    
    HEALTH --> VM1
    HEALTH --> VM2
    HEALTH --> VM3
    
    VM1 --> DISK
    VM2 --> DISK
    VM3 --> DISK
    
    DISK --> BACKUP
```

**Use Cases**:
- High-traffic scenarios requiring dedicated resources
- Custom runtime requirements
- Legacy integration needs
- Specific compliance requirements

### Container Deployment

```mermaid
graph TB
    subgraph "Azure Container Instances"
        ACI[Container Group]
        APP[FastAPI Container]
        SIDECAR[Logging Sidecar]
    end
    
    subgraph "Container Registry"
        ACR[Azure Container Registry]
        IMAGE[Application Images]
    end
    
    ACR --> ACI
    IMAGE --> APP
    APP --> ACI
    SIDECAR --> ACI
```

**Docker Configuration**:
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Network Architecture

### Network Security Groups

```mermaid
graph TB
    subgraph "Internet"
        CLIENT[Client Applications]
    end
    
    subgraph "Azure Virtual Network"
        subgraph "Public Subnet"
            LB[Load Balancer]
            APPGW[Application Gateway]
        end
        
        subgraph "Private Subnet"
            APP[Application Tier]
            API[API Endpoints]
        end
        
        subgraph "Data Subnet"
            SQL[SQL Database]
            STORAGE[Storage Services]
        end
    end
    
    CLIENT --> LB
    CLIENT --> APPGW
    LB --> APP
    APPGW --> API
    APP --> SQL
    API --> STORAGE
```

**Security Rules**:
- Inbound HTTPS (443) from Internet to Load Balancer
- Inbound HTTP (80) redirects to HTTPS
- Internal communication on required ports only
- Outbound access to Azure services and Graph API

### Private Endpoints

```mermaid
graph LR
    subgraph "VNet"
        APP[Application]
        PE[Private Endpoint]
    end
    
    subgraph "Azure Services"
        SQL[SQL Database]
        BLOB[Blob Storage]
        VAULT[Key Vault]
    end
    
    APP --> PE
    PE -.->|Private Link| SQL
    PE -.->|Private Link| BLOB
    PE -.->|Private Link| VAULT
```

## Data Storage Architecture

### Database Design

```mermaid
erDiagram
    User ||--o{ Session : has
    User ||--o{ MailAccount : owns
    User ||--o{ UserProfile : has
    User ||--o{ VoiceAttachment : creates
    VoiceAttachment ||--o{ VoiceTranscription : generates
    VoiceTranscription ||--o{ TranscriptionSegment : contains
    VoiceTranscription ||--o{ TranscriptionError : may_have
    User ||--o{ AuditLog : triggers
    
    User {
        uniqueidentifier id PK
        nvarchar azure_id UK
        nvarchar email UK
        bit is_active
        nvarchar role
        datetime2 created_at
        datetime2 updated_at
    }
    
    Session {
        uniqueidentifier id PK
        uniqueidentifier user_id FK
        nvarchar access_token
        nvarchar refresh_token
        datetime2 expires_at
        bit is_revoked
    }
    
    VoiceAttachment {
        uniqueidentifier id PK
        uniqueidentifier user_id FK
        nvarchar file_name
        nvarchar blob_url
        bigint file_size
        nvarchar status
    }
```

### Storage Strategy

#### Hot Data (Frequent Access)
- **User sessions**: In-memory cache + database
- **Recent mail data**: 5-minute TTL cache
- **Active transcriptions**: Database with status tracking

#### Warm Data (Regular Access)
- **User profiles**: Database with 1-hour cache TTL
- **Mail folder structure**: Database + blob storage
- **Completed transcriptions**: Database + blob results

#### Cold Data (Archive)
- **Old voice files**: Cool blob storage tier
- **Historical audit logs**: Log Analytics long-term retention
- **Archived transcriptions**: Archive blob storage tier

## Security Infrastructure

### Identity and Access Management

```mermaid
graph TB
    subgraph "Azure AD"
        USER[User Identity]
        GROUP[Security Groups]
        APP[App Registration]
        RBAC[RBAC Roles]
    end
    
    subgraph "Application Security"
        AUTH[Authentication Service]
        AUTHZ[Authorization Service]
        TOKEN[Token Validation]
    end
    
    subgraph "Data Security"
        ENCRYPT[Always Encrypted]
        RLS[Row-Level Security]
        AUDIT[SQL Audit]
    end
    
    USER --> AUTH
    GROUP --> AUTHZ
    APP --> TOKEN
    RBAC --> AUTHZ
    
    AUTH --> ENCRYPT
    AUTHZ --> RLS
    TOKEN --> AUDIT
```

### Key Management

```mermaid
graph TB
    subgraph "Azure Key Vault"
        SECRETS[Application Secrets]
        KEYS[Encryption Keys]
        CERTS[SSL Certificates]
    end
    
    subgraph "Application"
        CONFIG[Configuration]
        CRYPTO[Cryptographic Operations]
        TLS[TLS Termination]
    end
    
    SECRETS --> CONFIG
    KEYS --> CRYPTO
    CERTS --> TLS
```

**Key Vault Configuration**:
```python
# File: app/core/config.py
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://scribe-vault.vault.azure.net/", credential=credential)

# Retrieve secrets at startup
secret_key = client.get_secret("secret-key").value
database_password = client.get_secret("database-password").value
```

## Monitoring and Observability

### Application Performance Monitoring

```mermaid
graph TB
    subgraph "Application"
        API[API Endpoints]
        SERVICES[Business Services]
        DATA[Data Layer]
    end
    
    subgraph "Azure Monitor"
        APPINS[Application Insights]
        METRICS[Custom Metrics]
        TRACES[Distributed Tracing]
        LOGS[Structured Logging]
    end
    
    subgraph "Alerting"
        ALERTS[Alert Rules]
        ACTION[Action Groups]
        NOTIFY[Notifications]
    end
    
    API --> APPINS
    SERVICES --> METRICS
    DATA --> TRACES
    
    APPINS --> LOGS
    METRICS --> ALERTS
    TRACES --> ALERTS
    LOGS --> ALERTS
    
    ALERTS --> ACTION
    ACTION --> NOTIFY
```

**Telemetry Configuration**:
```python
# File: app/core/Logging.py
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace, metrics

configure_azure_monitor(
    connection_string="InstrumentationKey=your-key;IngestionEndpoint=https://...",
    enable_live_metrics=True,
    enable_logging=True,
    enable_tracing=True,
    enable_metrics=True
)
```

### Health Check Architecture

```mermaid
graph LR
    subgraph "Health Checks"
        API[API Health]
        DB[Database Health]
        AZURE[Azure Services Health]
        CACHE[Cache Health]
    end
    
    subgraph "Monitoring Systems"
        LB[Load Balancer]
        MONITOR[Azure Monitor]
        EXTERNAL[External Monitoring]
    end
    
    API --> LB
    DB --> MONITOR
    AZURE --> MONITOR
    CACHE --> EXTERNAL
    
    LB --> |Remove from rotation| APP[Application Instance]
    MONITOR --> |Alert on failure| TEAM[Operations Team]
```

## Disaster Recovery

### Backup Strategy

```mermaid
graph TB
    subgraph "Production Environment"
        PROD_DB[Production Database]
        PROD_BLOB[Production Blob Storage]
        PROD_VAULT[Production Key Vault]
    end
    
    subgraph "Backup Systems"
        AUTO_BACKUP[Automated SQL Backups]
        BLOB_REPLICA[Blob Storage Replication]
        VAULT_BACKUP[Key Vault Backup]
    end
    
    subgraph "Secondary Region"
        SEC_DB[Secondary Database]
        SEC_BLOB[Secondary Blob Storage]
        SEC_VAULT[Secondary Key Vault]
    end
    
    PROD_DB --> AUTO_BACKUP
    PROD_BLOB --> BLOB_REPLICA
    PROD_VAULT --> VAULT_BACKUP
    
    AUTO_BACKUP --> SEC_DB
    BLOB_REPLICA --> SEC_BLOB
    VAULT_BACKUP --> SEC_VAULT
```

### Recovery Procedures

**RTO (Recovery Time Objective)**: 4 hours
**RPO (Recovery Point Objective)**: 1 hour

**Recovery Steps**:
1. **Database Recovery**: Restore from automated backup or geo-replica
2. **Blob Storage**: Switch to secondary region if needed
3. **Application Deployment**: Redeploy to secondary region
4. **DNS Failover**: Update DNS to point to secondary region
5. **Validation**: Run health checks and smoke tests

---

**Configuration References:**
- Azure Settings: `settings.toml:20-40`
- Database Connection: `app/db/Database.py:25-60`
- Key Vault Integration: `app/core/config.py:15-30`
- Monitoring Setup: `app/core/Logging.py:1-50`

**Related Documentation:**
- [Configuration Guide](../guides/configuration.md)
- [Deployment Guide](../guides/deployment.md)
- [Security Guide](../guides/security.md)
- [Monitoring Guide](../guides/monitoring.md)