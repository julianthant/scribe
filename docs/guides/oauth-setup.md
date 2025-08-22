# Azure AD OAuth Setup Guide

This guide walks through setting up Azure Active Directory OAuth authentication for the Scribe application.

## Prerequisites

- Azure AD tenant access (admin permissions)
- Application registration permissions
- Access to Azure Portal

## Azure AD App Registration

### Step 1: Create App Registration

1. Navigate to [Azure Portal](https://portal.azure.com)
2. Go to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Configure the application:
   - **Name**: `Scribe Voice Email Processor`
   - **Supported account types**: `Accounts in this organizational directory only`
   - **Redirect URI**: `Web` → `http://localhost:8001/api/v1/auth/callback`
5. Click **Register**

### Step 2: Configure Authentication

1. In your app registration, go to **Authentication**
2. Under **Redirect URIs**, add additional URIs for different environments:
   - Development: `http://localhost:8001/api/v1/auth/callback`
   - Staging: `https://staging.yourapp.com/api/v1/auth/callback`
   - Production: `https://yourapp.com/api/v1/auth/callback`
3. Under **Implicit grant and hybrid flows**, enable:
   - ✅ **ID tokens** (used for OpenID Connect)
4. Under **Advanced settings**:
   - ✅ **Allow public client flows**: No
   - ✅ **Enable the following mobile and desktop flows**: No
5. Click **Save**

### Step 3: Generate Client Secret

1. Go to **Certificates & secrets**
2. Under **Client secrets**, click **New client secret**
3. Configure the secret:
   - **Description**: `Scribe API Secret`
   - **Expires**: `24 months` (recommended)
4. Click **Add**
5. **Important**: Copy the secret value immediately - it won't be shown again

### Step 4: Configure API Permissions

1. Go to **API permissions**
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Choose **Delegated permissions**
5. Add the following permissions:
   - ✅ `User.Read` - Read user profile
   - ✅ `Mail.Read` - Read user mail (if needed for email processing)
   - ✅ `offline_access` - Maintain access to data
6. Click **Add permissions**
7. **Optional**: Click **Grant admin consent** if you have admin rights

### Step 5: Note Configuration Values

Record these values from your app registration:

- **Application (client) ID**: Found on the **Overview** page
- **Directory (tenant) ID**: Found on the **Overview** page
- **Client Secret**: The secret value you copied
- **Authority URL**: `https://login.microsoftonline.com/{tenant-id}`

## Environment Configuration

### Step 1: Update .env File

Update your `.env` file with the Azure AD configuration:

```env
# Azure AD OAuth Settings
AZURE_CLIENT_ID=your-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here
AZURE_TENANT_ID=your-tenant-id-here
AZURE_REDIRECT_URI=http://localhost:8001/api/v1/auth/callback
AZURE_AUTHORITY=https://login.microsoftonline.com/your-tenant-id-here
AZURE_SCOPES=["User.Read", "Mail.Read"]
```

### Step 2: Verify Configuration

Check that your `app/core/config.py` includes Azure AD settings:

```python
class Settings(BaseSettings):
    # ... other settings
    
    # Azure AD OAuth Settings
    azure_client_id: str
    azure_client_secret: str
    azure_tenant_id: str
    azure_redirect_uri: str
    azure_authority: str
    azure_scopes: List[str] = ["User.Read"]
    
    @property
    def azure_authority_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}"
```

## Testing the Setup

### Step 1: Start the Application

```bash
# Start the development server
uvicorn app.main:app --reload --reload-dir app --port 8001
```

### Step 2: Test Authentication Flow

1. Open browser to `http://localhost:8001/static/index.html`
2. Click **"Sign in with Azure AD"**
3. You should be redirected to Microsoft login page
4. After successful login, you should see your user information

### Step 3: Verify API Endpoints

Test the authentication endpoints directly:

```bash
# Test login initiation
curl -X GET http://localhost:8001/api/v1/auth/login

# Test authentication status
curl -X GET http://localhost:8001/api/v1/auth/status
```

## Environment-Specific Setup

### Development Environment

```env
AZURE_REDIRECT_URI=http://localhost:8001/api/v1/auth/callback
DEBUG=True
```

### Staging Environment

```env
AZURE_REDIRECT_URI=https://staging.yourapp.com/api/v1/auth/callback
DEBUG=False
```

### Production Environment

```env
AZURE_REDIRECT_URI=https://yourapp.com/api/v1/auth/callback
DEBUG=False
# Use Azure Key Vault or secure secret management
```

## Security Best Practices

### 1. Secret Management

- **Development**: Use `.env` file (never commit to git)
- **Production**: Use Azure Key Vault, AWS Secrets Manager, or similar
- **Rotation**: Rotate client secrets every 12-24 months

### 2. Redirect URI Validation

- Only register necessary redirect URIs
- Use HTTPS in production
- Validate redirect URIs match exactly

### 3. Scope Minimization

- Only request necessary OAuth scopes
- Review permissions regularly
- Use least-privilege principle

### 4. Token Storage

- Store tokens securely on client side
- Use httpOnly cookies when possible
- Implement proper token cleanup on logout

## Troubleshooting

### Common Issues

#### 1. "Invalid redirect URI" Error
- Verify the redirect URI in Azure AD matches exactly
- Check for trailing slashes or case sensitivity
- Ensure the URI is using the correct protocol (http/https)

#### 2. "Invalid client" Error
- Verify the client ID is correct
- Check that the client secret hasn't expired
- Ensure the application is enabled

#### 3. "Insufficient permissions" Error
- Check that required API permissions are granted
- Admin consent may be required for some permissions
- Verify user has access to the application

#### 4. Token Acquisition Failures
- Check network connectivity to Azure AD endpoints
- Verify system clock is synchronized
- Review application logs for detailed error messages

### Debug Mode

Enable debug logging for OAuth issues:

```python
# In app/core/config.py
LOG_LEVEL=DEBUG

# This will show detailed OAuth flow information
```

### Testing with Different Users

1. Test with various user types:
   - Internal organization users
   - Guest users (if applicable)
   - Users with different permission levels

2. Test edge cases:
   - First-time user login
   - Users who revoke permissions
   - Expired token scenarios

## Monitoring and Maintenance

### 1. Regular Checks

- Monitor authentication success rates
- Check for failed login attempts
- Review token expiration patterns

### 2. Certificate and Secret Management

- Set calendar reminders for secret rotation
- Monitor certificate expiration dates
- Plan for zero-downtime secret updates

### 3. Compliance

- Regular security audits
- Permission reviews
- Access logging and monitoring

## Additional Resources

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [Azure AD B2C Documentation](https://docs.microsoft.com/en-us/azure/active-directory-b2c/)
- [MSAL Python Documentation](https://msal-python.readthedocs.io/en/latest/)
- [OAuth 2.0 and OpenID Connect Protocols](https://oauth.net/2/)