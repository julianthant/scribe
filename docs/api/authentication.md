# Authentication API

This document describes the authentication endpoints and OAuth2 flow implementation using Azure Active Directory (Azure AD).

## Overview

The Scribe API uses OAuth 2.0 with Azure Active Directory for user authentication. The implementation follows the Authorization Code flow with PKCE (Proof Key for Code Exchange) for enhanced security.

## Endpoints

### Base URL
```
/api/v1/auth
```

## Authentication Flow

### 1. Initiate Login

Initiates the OAuth login flow with Azure AD.

**Endpoint:** `GET /api/v1/auth/login`

**Response:** `200 OK`
```json
{
  "auth_url": "https://login.microsoftonline.com/.../oauth2/v2.0/authorize?...",
  "state": "random-state-parameter"
}
```

**Response Fields:**
- `auth_url` (string): URL to redirect user for Azure AD authentication
- `state` (string): CSRF protection state parameter

**Error Responses:**
- `400 Bad Request`: Login initiation failed
- `500 Internal Server Error`: Unexpected error

### 2. Handle OAuth Callback

Processes the OAuth callback from Azure AD and exchanges authorization code for tokens.

**Endpoint:** `GET /api/v1/auth/callback`

**Query Parameters:**
- `code` (string, required): Authorization code from Azure AD
- `state` (string, optional): State parameter for CSRF validation
- `error` (string, optional): Error code if authentication failed
- `error_description` (string, optional): Detailed error description

**Response:** `200 OK`
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJ...",
  "refresh_token": "1.AWMBI8niFURjXESt...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "User.Read openid profile offline_access",
  "user_info": {
    "id": "68d8969c-5d12-4dd7-b439-2bdc7b2454a1",
    "display_name": "Julian Zaw",
    "email": "julianthant@outlook.com",
    "given_name": "Julian",
    "surname": "Zaw"
  }
}
```

**Response Fields:**
- `access_token` (string): JWT access token for API authentication
- `refresh_token` (string): Token for refreshing expired access tokens
- `token_type` (string): Always "Bearer"
- `expires_in` (integer): Token expiration time in seconds
- `scope` (string): Granted OAuth scopes
- `user_info` (object): User profile information

**Error Responses:**
- `400 Bad Request`: Invalid callback parameters or validation failure
- `401 Unauthorized`: Authentication failed
- `500 Internal Server Error`: Unexpected error

### 3. Refresh Token

Refreshes an expired access token using a valid refresh token.

**Endpoint:** `POST /api/v1/auth/refresh`

**Request Body:**
```json
{
  "refresh_token": "1.AWMBI8niFURjXESt..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJ...",
  "refresh_token": "1.AWMBI8niFURjXESt...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "User.Read openid profile offline_access",
  "user_info": {
    "id": "68d8969c-5d12-4dd7-b439-2bdc7b2454a1",
    "display_name": "Julian Zaw",
    "email": "julianthant@outlook.com",
    "given_name": "Julian",
    "surname": "Zaw"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or expired refresh token
- `500 Internal Server Error`: Token refresh failed

### 4. Get Current User

Retrieves information about the currently authenticated user.

**Endpoint:** `GET /api/v1/auth/me`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "id": "68d8969c-5d12-4dd7-b439-2bdc7b2454a1",
  "display_name": "Julian Zaw",
  "email": "julianthant@outlook.com",
  "given_name": "Julian",
  "surname": "Zaw"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or expired access token
- `500 Internal Server Error`: Unable to retrieve user information

### 5. Get Authentication Status

Checks the current authentication status without requiring authentication.

**Endpoint:** `GET /api/v1/auth/status`

**Response:** `200 OK`
```json
{
  "is_authenticated": true,
  "user_info": {
    "id": "68d8969c-5d12-4dd7-b439-2bdc7b2454a1",
    "display_name": "Julian Zaw",
    "email": "julianthant@outlook.com",
    "given_name": "Julian",
    "surname": "Zaw"
  },
  "expires_at": null
}
```

**Response (Unauthenticated):**
```json
{
  "is_authenticated": false,
  "user_info": null,
  "expires_at": null
}
```

### 6. Logout

Logs out the user and cleans up the session.

**Endpoint:** `POST /api/v1/auth/logout`

**Request Body (Optional):**
```json
{
  "session_id": "optional-session-identifier"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Successfully logged out"
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Logout failed"
}
```

## Authentication Headers

For protected endpoints, include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

## OAuth Scopes

The application requests the following OAuth 2.0 scopes:

- `User.Read`: Read basic user profile information
- `openid`: OpenID Connect authentication
- `profile`: Access to user's profile information  
- `offline_access`: Ability to refresh tokens

## Error Handling

All authentication endpoints return consistent error responses:

```json
{
  "error": "Authentication Error",
  "message": "Detailed error message",
  "error_code": "AUTH_001",
  "details": {
    "operation": "token_exchange"
  },
  "timestamp": "2025-08-22T05:52:23.120Z"
}
```

**Common Error Codes:**
- `AUTH_001`: Invalid credentials
- `AUTH_002`: Token expired
- `AUTH_003`: Insufficient permissions
- `AUTH_004`: Invalid OAuth callback
- `AUTH_005`: Session expired

## Rate Limiting

Authentication endpoints are subject to rate limiting:
- Login initiation: 10 requests per minute per IP
- Token refresh: 30 requests per minute per user
- Status checks: 100 requests per minute per IP

## Security Considerations

1. **PKCE**: All OAuth flows use Proof Key for Code Exchange
2. **State Parameter**: CSRF protection via state parameter validation
3. **Token Storage**: Tokens should be stored securely on the client side
4. **HTTPS Only**: All authentication must use HTTPS in production
5. **Token Expiration**: Access tokens expire after 1 hour
6. **Refresh Rotation**: Refresh tokens may rotate on use

## Integration Examples

### Frontend Integration

```javascript
// Initiate login
const loginResponse = await fetch('/api/v1/auth/login');
const { auth_url } = await loginResponse.json();
window.location.href = auth_url;

// Check authentication status
const statusResponse = await fetch('/api/v1/auth/status');
const { is_authenticated, user_info } = await statusResponse.json();

// Make authenticated requests
const apiResponse = await fetch('/api/v1/protected-endpoint', {
  headers: {
    'Authorization': `Bearer ${access_token}`
  }
});
```

### Token Refresh

```javascript
async function refreshToken(refreshToken) {
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  
  if (response.ok) {
    return await response.json();
  } else {
    // Redirect to login
    window.location.href = '/login';
  }
}
```