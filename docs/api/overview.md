# API Overview

The Scribe API provides a comprehensive REST interface for mail management, authentication, and voice processing operations. Built on FastAPI, it offers high performance, automatic documentation, and type safety.

## Table of Contents

1. [API Design Principles](#api-design-principles)
2. [Base URL and Versioning](#base-url-and-versioning)
3. [Authentication](#authentication)
4. [Request/Response Format](#requestresponse-format)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Endpoint Categories](#endpoint-categories)
8. [OpenAPI Specification](#openapi-specification)

## API Design Principles

The Scribe API follows RESTful design principles and modern API best practices:

### REST Principles
- **Resource-Based URLs**: Each endpoint represents a resource or collection
- **HTTP Methods**: Proper use of GET, POST, PUT, DELETE methods
- **Stateless**: Each request is independent and contains all necessary information
- **Cacheable**: Responses include appropriate cache headers
- **Uniform Interface**: Consistent patterns across all endpoints

### Design Standards
- **Consistent Naming**: Use kebab-case for URLs (`/shared-mailbox`)
- **Plural Nouns**: Collection endpoints use plural forms (`/messages`)
- **Hierarchical Structure**: Related resources nested logically
- **Query Parameters**: Use for filtering, sorting, and pagination
- **HTTP Status Codes**: Meaningful status codes for all responses

## Base URL and Versioning

### Base URL Structure
```
https://api.scribe.company.com/api/v1
```

### Versioning Strategy
- **URL Path Versioning**: Version included in URL path (`/api/v1/`)
- **Backward Compatibility**: Maintain compatibility within major versions
- **Deprecation Policy**: 6-month notice before removing endpoints
- **Version Headers**: Accept `API-Version` header for flexibility

### Environment URLs
```bash
# Development
https://dev-api.scribe.company.com/api/v1

# Staging  
https://staging-api.scribe.company.com/api/v1

# Production
https://api.scribe.company.com/api/v1
```

## Authentication

### OAuth 2.0 Flow
The API uses Azure AD OAuth 2.0 for authentication:

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Azure_AD
    
    Client->>API: GET /auth/login
    API-->>Client: Redirect to Azure AD
    Client->>Azure_AD: User authenticates
    Azure_AD->>API: Callback with auth code
    API-->>Client: JWT access token
    Client->>API: API requests with Bearer token
    API-->>Client: Protected resource data
```

### Token Usage
```bash
# Include Bearer token in Authorization header
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJ..." \
     https://api.scribe.company.com/api/v1/mail/messages
```

### Token Lifecycle
- **Access Token**: 1 hour lifetime
- **Refresh Token**: 90 days lifetime
- **Token Refresh**: Automatic refresh before expiration
- **Session Management**: Server-side session tracking

## Request/Response Format

### Content Types
- **Request**: `application/json` (required for POST/PUT)
- **Response**: `application/json` (default)
- **File Upload**: `multipart/form-data`

### Request Headers
```http
Content-Type: application/json
Authorization: Bearer <access_token>
Accept: application/json
User-Agent: ScribeClient/1.0
```

### Response Headers
```http
Content-Type: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1635724800
Cache-Control: private, max-age=300
```

### Standard Response Structure
```json
{
  "data": {
    // Resource data
  },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-08-26T10:30:00Z",
    "version": "v1"
  }
}
```

### Collection Response Format
```json
{
  "data": [
    // Array of resources
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 150,
    "total_pages": 3,
    "has_next": true,
    "has_previous": false
  },
  "links": {
    "self": "/api/v1/messages?page=1",
    "next": "/api/v1/messages?page=2",
    "previous": null,
    "first": "/api/v1/messages?page=1",
    "last": "/api/v1/messages?page=3"
  },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-08-26T10:30:00Z"
  }
}
```

## Error Handling

### HTTP Status Codes

| Status Code | Meaning | Usage |
|-------------|---------|--------|
| 200 | OK | Successful GET, PUT, PATCH |
| 201 | Created | Successful POST that creates resource |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid request format or parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Valid auth but insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource conflict (duplicate, etc.) |
| 422 | Unprocessable Entity | Valid format but semantic errors |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
| 502 | Bad Gateway | Upstream service error |
| 503 | Service Unavailable | Temporary service outage |

### Error Response Format
```json
{
  "error": {
    "type": "validation_error",
    "message": "The request contained invalid parameters",
    "code": "INVALID_PARAMETERS",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format",
        "code": "INVALID_FORMAT"
      }
    ],
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-08-26T10:30:00Z",
    "documentation_url": "https://docs.scribe.company.com/errors/INVALID_PARAMETERS"
  }
}
```

### Error Categories

#### Client Errors (4xx)
```json
{
  "error": {
    "type": "authentication_error",
    "message": "Access token has expired",
    "code": "TOKEN_EXPIRED",
    "details": {
      "expired_at": "2025-08-26T09:30:00Z",
      "refresh_endpoint": "/api/v1/auth/refresh"
    }
  }
}
```

#### Server Errors (5xx)
```json
{
  "error": {
    "type": "internal_error",
    "message": "An unexpected error occurred",
    "code": "INTERNAL_ERROR",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "support_url": "https://support.scribe.company.com"
  }
}
```

## Rate Limiting

### Rate Limit Policy
- **Authenticated Users**: 1000 requests per hour
- **Per Endpoint**: Some endpoints have specific limits
- **Burst Allowance**: Short bursts up to 100 requests per minute
- **IP-Based Fallback**: 100 requests per hour for unauthenticated requests

### Rate Limit Headers
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1635724800
X-RateLimit-Window: 3600
```

### Rate Limit Response
```json
{
  "error": {
    "type": "rate_limit_error",
    "message": "Rate limit exceeded",
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {
      "limit": 1000,
      "window_seconds": 3600,
      "reset_at": "2025-08-26T11:30:00Z"
    }
  }
}
```

## Endpoint Categories

### 🔐 Authentication (`/auth`)
User authentication and session management:
- `GET /auth/login` - Initiate OAuth login
- `GET /auth/callback` - Handle OAuth callback
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Get current user info
- `POST /auth/logout` - Logout user

### 📧 Mail (`/mail`) 
Personal mailbox operations:
- `GET /mail/messages` - List messages
- `GET /mail/messages/{id}` - Get message details
- `GET /mail/folders` - List mail folders
- `POST /mail/send` - Send message
- `PUT /mail/messages/{id}` - Update message

### 🏢 Shared Mailbox (`/shared-mailbox`)
Shared mailbox management:
- `GET /shared-mailbox` - List accessible shared mailboxes
- `GET /shared-mailbox/{email}/messages` - Get shared mailbox messages
- `POST /shared-mailbox/{email}/send` - Send from shared mailbox
- `GET /shared-mailbox/{email}/folders` - Get shared mailbox folders

### 🎙️ Voice (`/voice`)
Voice attachment processing:
- `POST /voice/upload` - Upload voice file
- `GET /voice/{id}` - Get voice attachment info
- `GET /voice/{id}/transcription` - Get transcription results
- `GET /voice/{id}/download` - Download voice file
- `DELETE /voice/{id}` - Delete voice attachment

### 📊 System (`/system`)
System information and health:
- `GET /health` - Health check
- `GET /version` - API version info
- `GET /metrics` - System metrics (admin only)

## OpenAPI Specification

### Interactive Documentation
The API provides interactive documentation at:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`

### OpenAPI Features
- **Type Safety**: Full type definitions for all endpoints
- **Example Requests**: Working examples for every endpoint
- **Response Schemas**: Detailed response structure documentation
- **Authentication**: Built-in authentication testing
- **Try It Out**: Execute API calls directly from documentation

### Example OpenAPI Definition
```json
{
  "openapi": "3.0.2",
  "info": {
    "title": "Scribe API",
    "description": "A FastAPI application with strict coding standards",
    "version": "1.0.0"
  },
  "paths": {
    "/api/v1/auth/login": {
      "get": {
        "summary": "Initiate Login",
        "operationId": "initiate_login_auth_login_get",
        "responses": {
          "302": {
            "description": "Redirect to Azure AD"
          },
          "400": {
            "description": "Login initiation failed",
            "content": {
              "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
              }
            }
          }
        },
        "tags": ["authentication"]
      }
    }
  }
}
```

### Client Code Generation
The OpenAPI specification enables automatic client generation:
```bash
# Generate Python client
openapi-generator generate \
  -i http://localhost:8000/openapi.json \
  -g python \
  -o ./python-client

# Generate TypeScript client  
openapi-generator generate \
  -i http://localhost:8000/openapi.json \
  -g typescript-axios \
  -o ./typescript-client
```

### Postman Collection
Export Postman collection from OpenAPI:
```bash
# Install postman-to-openapi
npm install -g postman-to-openapi

# Convert OpenAPI to Postman collection
openapi-to-postman -s http://localhost:8000/openapi.json \
  -o scribe-api.postman_collection.json
```

---

**File References:**
- API Router: `app/api/v1/router.py:1-22`
- FastAPI App: `app/main.py:79-84`
- Error Handlers: `app/main.py:155-258`
- Base Models: `app/models/BaseModel.py:1-100`

**Related Documentation:**
- [Authentication API](authentication.md)
- [Mail API](mail.md)
- [Shared Mailbox API](shared-mailbox.md)
- [Voice API](transcription.md)
- [Architecture Overview](../architecture/overview.md)