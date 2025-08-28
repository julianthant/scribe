# Authentication API Documentation

This document describes the authentication endpoints provided by the Scribe API, including OAuth flow management, token operations, and user session handling.

## Table of Contents

1. [Overview](#overview)
2. [Authentication Flow](#authentication-flow)
3. [Endpoints](#endpoints)
4. [Request/Response Models](#requestresponse-models)
5. [Error Handling](#error-handling)
6. [Security Considerations](#security-considerations)
7. [Examples](#examples)

## Overview

The authentication API provides OAuth 2.0 integration with Azure Active Directory for secure user authentication and authorization. All endpoints are located under the `/auth` prefix.

**Base URL**: `/api/v1/auth`

### Authentication Flow Summary

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Scribe API
    participant AAD as Azure AD
    
    Note over C,AAD: Login Flow
    C->>API: GET /auth/login
    API-->>C: HTTP 302 → Azure AD
    C->>AAD: User Authentication
    AAD->>API: GET /auth/callback?code=xxx
    API-->>C: JSON: TokenResponse
    
    Note over C,AAD: API Access
    C->>API: GET /api/v1/mail/messages<br/>Authorization: Bearer <token>
    API-->>C: JSON: Mail Data
    
    Note over C,AAD: Token Refresh
    C->>API: POST /auth/refresh
    API-->>C: JSON: New TokenResponse
```

## Authentication Flow

### 1. Login Initiation

The authentication process starts with a direct redirect to Azure AD:

```mermaid
graph LR
    A[Client] -->|GET /auth/login| B[Scribe API]
    B -->|HTTP 302 Redirect| C[Azure AD Login]
    C -->|User Authenticates| D[Azure AD Callback]
    D -->|GET /auth/callback| B
    B -->|TokenResponse| A
```

### 2. Token Management

Tokens have expiration times and must be refreshed periodically:
- **Access Token**: 1 hour default lifetime
- **Refresh Token**: 90 days default lifetime  
- **Session**: Tracked in database with metadata

## Endpoints

### GET /auth/login

Initiates OAuth login flow by redirecting to Azure AD.

**Method**: `GET`  
**Path**: `/auth/login`  
**Authentication**: None required

**Response**: 
- **302 Found**: Redirects to Azure AD authorization URL
- **400 Bad Request**: If login initiation fails

**Example Request**:
```bash
curl -X GET "https://api.example.com/api/v1/auth/login" \
  -H "Accept: application/json"
```

**Example Response**:
```http
HTTP/1.1 302 Found
Location: https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize?client_id=...&response_type=code&redirect_uri=...&scope=...&state=...
```

---

### GET /auth/callback

Handles OAuth callback from Azure AD and exchanges authorization code for tokens.

**Method**: `GET`  
**Path**: `/auth/callback`  
**Authentication**: None required

**Query Parameters**:
- `code` (string, required): Authorization code from Azure AD
- `state` (string, optional): CSRF protection state parameter
- `error` (string, optional): Error code if authentication failed
- `error_description` (string, optional): Detailed error description

**Response Model**: `TokenResponse`

**Example Request**:
```bash
# This request is typically made by Azure AD, not directly by clients
curl -X GET "https://api.example.com/api/v1/auth/callback?code=M.C507_BL2.0.U.-CUx&state=abc123..." \
  -H "Accept: application/json"
```

**Example Success Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs...",
  "refresh_token": "M.C507_BL2.0.U.-CUx8T7JvGgwQ9z...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read",
  "user_info": {
    "id": "12345678-1234-1234-1234-123456789012",
    "display_name": "John Doe",
    "email": "john.doe@company.com",
    "given_name": "John",
    "surname": "Doe",
    "role": "user",
    "is_superuser": false
  },
  "session_id": "87654321-4321-4321-4321-210987654321"
}
```

**Example Error Response**:
```json
{
  "error": "Authentication Error",
  "message": "Authorization code is required",
  "error_code": "MISSING_AUTH_CODE",
  "details": null,
  "timestamp": "2025-08-26T10:30:00Z"
}
```

---

### POST /auth/refresh

Refreshes an expired access token using a refresh token.

**Method**: `POST`  
**Path**: `/auth/refresh`  
**Authentication**: None required (uses refresh token)

**Request Model**: `RefreshTokenRequest`

**Response Model**: `TokenResponse`

**Example Request**:
```bash
curl -X POST "https://api.example.com/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "refresh_token": "M.C507_BL2.0.U.-CUx8T7JvGgwQ9z...",
    "session_id": "87654321-4321-4321-4321-210987654321"
  }'
```

**Example Success Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs...",
  "refresh_token": "M.C507_BL2.0.U.-CUx8T7JvGgwQ9z...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "https://graph.microsoft.com/Mail.Read https://graph.microsoft.com/User.Read",
  "user_info": {
    "id": "12345678-1234-1234-1234-123456789012",
    "display_name": "John Doe",
    "email": "john.doe@company.com",
    "given_name": "John",
    "surname": "Doe",
    "role": "user",
    "is_superuser": false
  },
  "session_id": "87654321-4321-4321-4321-210987654321"
}
```

---

### GET /auth/me

Returns information about the currently authenticated user.

**Method**: `GET`  
**Path**: `/auth/me`  
**Authentication**: Required (Bearer token)

**Response Model**: `UserInfo`

**Example Request**:
```bash
curl -X GET "https://api.example.com/api/v1/auth/me" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs..." \
  -H "Accept: application/json"
```

**Example Response**:
```json
{
  "id": "12345678-1234-1234-1234-123456789012",
  "display_name": "John Doe",
  "email": "john.doe@company.com",
  "given_name": "John",
  "surname": "Doe",
  "role": "user",
  "is_superuser": false
}
```

---

### GET /auth/status

Returns current authentication status for the request.

**Method**: `GET`  
**Path**: `/auth/status`  
**Authentication**: Optional (Bearer token)

**Response Model**: `AuthStatus`

**Example Request**:
```bash
curl -X GET "https://api.example.com/api/v1/auth/status" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs..." \
  -H "Accept: application/json"
```

**Example Authenticated Response**:
```json
{
  "is_authenticated": true,
  "user_info": {
    "id": "12345678-1234-1234-1234-123456789012",
    "display_name": "John Doe",
    "email": "john.doe@company.com",
    "given_name": "John",
    "surname": "Doe",
    "role": "user",
    "is_superuser": false
  },
  "expires_at": null
}
```

**Example Unauthenticated Response**:
```json
{
  "is_authenticated": false,
  "user_info": null,
  "expires_at": null
}
```

---

### POST /auth/logout

Logs out the current user and revokes the session.

**Method**: `POST`  
**Path**: `/auth/logout`  
**Authentication**: None required

**Request Parameters**:
- `session_id` (string, optional): Session identifier to revoke

**Response Model**: `LogoutResponse`

**Example Request**:
```bash
curl -X POST "https://api.example.com/api/v1/auth/logout" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "session_id": "87654321-4321-4321-4321-210987654321"
  }'
```

**Example Response**:
```json
{
  "success": true,
  "message": "Successfully logged out"
}
```

## Request/Response Models

### TokenResponse
```python
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    scope: str
    user_info: UserInfo
    session_id: Optional[str] = None
```

### UserInfo
```python
class UserInfo(BaseModel):
    id: str  # Azure AD object ID
    display_name: str
    email: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    role: UserRole = UserRole.USER
    is_superuser: bool = False
```

### RefreshTokenRequest
```python
class RefreshTokenRequest(BaseModel):
    refresh_token: str
    session_id: Optional[str] = None
```

### AuthStatus
```python
class AuthStatus(BaseModel):
    is_authenticated: bool
    user_info: Optional[UserInfo] = None
    expires_at: Optional[datetime] = None
```

### LogoutResponse
```python
class LogoutResponse(BaseModel):
    success: bool
    message: str
```

## Error Handling

### HTTP Status Codes

| Status Code | Description | When It Occurs |
|-------------|-------------|----------------|
| 200 | Success | Request processed successfully |
| 302 | Found | Login redirect to Azure AD |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Invalid or expired access token |
| 403 | Forbidden | Insufficient permissions |
| 500 | Internal Server Error | Server-side error |

### Error Response Format

All error responses follow this standard format:

```json
{
  "error": "Error Type",
  "message": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "details": {
    "additional": "error details"
  },
  "timestamp": "2025-08-26T10:30:00Z"
}
```

### Common Error Codes

| Error Code | Description | Resolution |
|------------|-------------|------------|
| `MISSING_AUTH_CODE` | Authorization code not provided | Check OAuth callback parameters |
| `INVALID_STATE` | CSRF state validation failed | Restart login flow |
| `SESSION_EXPIRED` | OAuth state session expired | Restart login flow |
| `TOKEN_REFRESH_FAILED` | Cannot refresh access token | Re-authenticate user |
| `INVALID_REFRESH_TOKEN` | Refresh token is invalid or expired | Re-authenticate user |

## Security Considerations

### CSRF Protection
- All OAuth flows use cryptographically secure state parameters
- State parameters expire after 10 minutes
- State validation is enforced on callback

### Token Security
- Access tokens are short-lived (1 hour default)
- Refresh tokens are securely stored in database
- All token operations are logged for audit

### Session Management
- Sessions include IP address and user agent for tracking
- Expired sessions are automatically cleaned up
- Sessions can be explicitly revoked

### HTTPS Requirements
- All authentication endpoints require HTTPS in production
- Tokens are transmitted securely
- CORS policies restrict cross-origin access

## Examples

### Complete Authentication Flow

```bash
#!/bin/bash

# 1. Initiate login (this will redirect to Azure AD)
echo "Step 1: Initiating login..."
curl -i -X GET "https://api.example.com/api/v1/auth/login"

# 2. After user authenticates, Azure AD will call callback
# The response will be a TokenResponse JSON

# 3. Use the access token for API calls
ACCESS_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs..."

echo "Step 3: Making authenticated API call..."
curl -X GET "https://api.example.com/api/v1/mail/messages" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Accept: application/json"

# 4. Refresh token when needed
REFRESH_TOKEN="M.C507_BL2.0.U.-CUx8T7JvGgwQ9z..."
SESSION_ID="87654321-4321-4321-4321-210987654321"

echo "Step 4: Refreshing token..."
curl -X POST "https://api.example.com/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\",\"session_id\":\"$SESSION_ID\"}"
```

### JavaScript Client Example

```javascript
class ScribeAuth {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.accessToken = localStorage.getItem('scribe_access_token');
        this.refreshToken = localStorage.getItem('scribe_refresh_token');
        this.sessionId = localStorage.getItem('scribe_session_id');
    }

    async login() {
        // Redirect to login endpoint
        window.location.href = `${this.baseUrl}/api/v1/auth/login`;
    }

    async handleCallback() {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const error = urlParams.get('error');

        if (error) {
            throw new Error(`Authentication failed: ${error}`);
        }

        if (!code) {
            throw new Error('No authorization code received');
        }

        // The API will handle the callback automatically
        // Tokens will be in the response JSON
    }

    async refreshAccessToken() {
        if (!this.refreshToken) {
            throw new Error('No refresh token available');
        }

        const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                refresh_token: this.refreshToken,
                session_id: this.sessionId
            })
        });

        if (!response.ok) {
            throw new Error('Token refresh failed');
        }

        const data = await response.json();
        this.storeTokens(data);
        return data;
    }

    async makeAuthenticatedRequest(url, options = {}) {
        if (!this.accessToken) {
            throw new Error('No access token available');
        }

        const response = await fetch(url, {
            ...options,
            headers: {
                ...options.headers,
                'Authorization': `Bearer ${this.accessToken}`,
                'Content-Type': 'application/json',
            }
        });

        // Auto-refresh token if expired
        if (response.status === 401 && this.refreshToken) {
            await this.refreshAccessToken();
            
            // Retry original request
            return fetch(url, {
                ...options,
                headers: {
                    ...options.headers,
                    'Authorization': `Bearer ${this.accessToken}`,
                    'Content-Type': 'application/json',
                }
            });
        }

        return response;
    }

    storeTokens(tokenResponse) {
        this.accessToken = tokenResponse.access_token;
        this.refreshToken = tokenResponse.refresh_token;
        this.sessionId = tokenResponse.session_id;

        localStorage.setItem('scribe_access_token', this.accessToken);
        localStorage.setItem('scribe_refresh_token', this.refreshToken);
        localStorage.setItem('scribe_session_id', this.sessionId);
    }

    async logout() {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/logout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: this.sessionId
            })
        });

        // Clear local storage regardless of response
        localStorage.removeItem('scribe_access_token');
        localStorage.removeItem('scribe_refresh_token');
        localStorage.removeItem('scribe_session_id');

        this.accessToken = null;
        this.refreshToken = null;
        this.sessionId = null;

        return response.ok;
    }
}

// Usage example
const auth = new ScribeAuth('https://api.example.com');

// Login
await auth.login();

// Make authenticated request
const response = await auth.makeAuthenticatedRequest('/api/v1/mail/messages');
const mailData = await response.json();

// Logout
await auth.logout();
```

---

**File References:**
- Auth Endpoints: `app/api/v1/endpoints/auth.py:1-234`
- Auth Models: `app/models/AuthModel.py:1-150`
- OAuth Service: `app/services/OAuthService.py:1-415`
- Dependencies: `app/dependencies/Auth.py:1-100`

**Related Documentation:**
- [OAuth Service](../services/oauth-service.md)
- [Azure Integration](../azure/auth-service.md)
- [Security Guide](../guides/security.md)
- [Architecture Overview](../architecture/overview.md)