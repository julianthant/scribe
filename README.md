# 🎤 Scribe Voice Email Processor

**Autonomous voice message transcription system for Microsoft Outlook emails**

[![Azure Functions](https://img.shields.io/badge/Azure-Functions-blue)](https://azure.microsoft.com/en-us/services/functions/)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://www.python.org/)
[![Microsoft Graph](https://img.shields.io/badge/Microsoft-Graph-orange)](https://docs.microsoft.com/en-us/graph/)
[![Azure AI](https://img.shields.io/badge/Azure-AI%20Speech-purple)](https://azure.microsoft.com/en-us/services/cognitive-services/speech-services/)

## 📋 Overview

Scribe Voice Email Processor is a production-ready Azure Functions application that automatically:

- 📧 **Monitors your Outlook inbox** for voice message attachments
- 🎤 **Transcribes audio** using Azure AI Speech services
- 📊 **Saves transcriptions** to Excel files in OneDrive
- 💾 **Stores voice messages** in Azure Blob Storage
- 🔄 **Processes autonomously** every minute via timer triggers
- 📁 **Organizes emails** by moving processed messages to designated folders

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Outlook       │    │  Azure Functions │    │  Azure AI       │
│   Inbox         │───▶│  Timer Trigger   │───▶│  Speech Service │
│                 │    │  (Every Minute)  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Azure Blob     │    │   Workflow       │    │  OneDrive       │
│  Storage        │◀───│   Orchestrator   │───▶│  Excel Files    │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Azure Key Vault │
                       │  OAuth Tokens    │
                       │                  │
                       └──────────────────┘
```

## ✨ Features

### 🔄 **Autonomous Processing**
- **Timer-based execution**: Runs every minute automatically
- **Self-contained workflow**: No manual intervention required
- **Error recovery**: Comprehensive error handling and logging
- **Scalable architecture**: Production-ready Azure Functions

### 🔐 **Security & Authentication**
- **OAuth 2.0 authentication**: Secure Microsoft Graph integration
- **Azure Key Vault**: Encrypted token storage
- **Managed Identity**: Azure-native authentication
- **Input validation**: Security validation and sanitization
- **No hardcoded secrets**: All credentials stored securely

### 📊 **Data Processing**
- **Audio transcription**: High-accuracy speech-to-text
- **Excel integration**: Automatic spreadsheet updates
- **File organization**: Smart email folder management
- **Metadata tracking**: Comprehensive processing logs

### 🛠️ **Monitoring & Maintenance**
- **Health checks**: Built-in endpoint monitoring
- **Application Insights**: Detailed telemetry and logging
- **Error tracking**: Comprehensive exception handling
- **Production monitoring**: Real-time status checking

## 🚀 Quick Start

### Prerequisites

- **Azure Subscription** with the following services:
  - Azure Functions (Consumption or Premium plan)
  - Azure Key Vault
  - Azure Blob Storage
  - Azure AI Speech Services
  - Application Insights

- **Microsoft 365** account with:
  - Outlook email access
  - OneDrive for Business
  - Microsoft Graph API permissions

- **Development Environment**:
  - Python 3.11
  - Azure Functions Core Tools
  - Azure CLI
  - Git

### 🔧 Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/julianthant/scribe.git
   cd scribe
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure local settings**:
   ```bash
   cp local.settings.json.template local.settings.json
   # Edit local.settings.json with your configuration
   ```

4. **Run tests**:
   ```bash
   python tests/run_tests.py
   ```

5. **Start local development**:
   ```bash
   func start
   ```

### ☁️ Production Deployment

1. **Deploy to Azure Functions**:
   ```bash
   func azure functionapp publish scribe-vm-processor --python
   ```

2. **Configure environment variables** in Azure Portal or CLI

3. **Set up OAuth authentication** (see Authentication section)

4. **Verify deployment**:
   ```bash
   curl https://your-function-app.azurewebsites.net/api/health
   ```

## 🔐 Authentication Setup

### OAuth 2.0 Configuration

The system uses OAuth 2.0 with Microsoft Graph API for secure email and file access.

#### Required App Registration Permissions:
- `Mail.Read` - Read email messages
- `Files.ReadWrite` - Access OneDrive files
- `offline_access` - Maintain access when user is offline

#### Setup Steps:

1. **Create Azure AD App Registration**:
   ```bash
   az ad app create --display-name "Scribe Voice Message Processor" \
     --public-client-redirect-uris "http://localhost"
   ```

2. **Grant API Permissions**:
   - Microsoft Graph: `Mail.Read`, `Files.ReadWrite`, `offline_access`

3. **Generate OAuth Tokens**:
   - Use the provided OAuth setup script
   - Tokens are automatically stored in Azure Key Vault

4. **Configure Key Vault Access**:
   ```bash
   az role assignment create \
     --assignee [function-managed-identity] \
     --role "Key Vault Secrets User" \
     --scope [key-vault-resource-id]
   ```

## 📁 Project Structure

```
scribe/
├── 📄 README.md                          # This file
├── 📄 requirements.txt                   # Python dependencies
├── 📄 function_app.py                    # Azure Functions entry point
├── 📄 host.json                          # Function host configuration
├── 📄 local.settings.json                # Local development settings
├── 📁 src/                               # Source code
│   ├── 📁 api/                          # HTTP endpoint handlers
│   │   ├── 📄 handlers.py               # Request handlers
│   │   └── 📄 responses.py              # Response builders
│   ├── 📁 core/                         # Core business logic
│   │   ├── 📄 components.py             # Component management
│   │   ├── 📄 config.py                 # Configuration management
│   │   ├── 📄 exceptions.py             # Custom exceptions
│   │   ├── 📄 security.py               # Security validation
│   │   ├── 📄 workflow.py               # Main workflow orchestrator
│   │   └── 📄 workflow_refactored.py    # Production workflow
│   ├── 📁 processors/                   # Data processors
│   │   ├── 📄 email.py                  # Email processing
│   │   ├── 📄 excel.py                  # Excel file operations
│   │   └── 📄 transcription.py          # Audio transcription
│   ├── 📁 helpers/                      # Utility modules
│   │   ├── 📄 auth_selector.py          # Authentication routing
│   │   ├── 📄 keyvault_oauth_manager.py # Key Vault OAuth
│   │   ├── 📄 monitoring_manager.py     # System monitoring
│   │   └── 📄 deployment_manager.py     # Deployment utilities
│   ├── 📁 models/                       # Data models
│   │   └── 📄 data.py                   # Data structures
│   └── 📁 scripts/                      # Utility scripts
│       └── 📄 monitor_production.py     # Production monitoring
├── 📁 tests/                            # Test suites
│   ├── 📄 run_tests.py                  # Test runner
│   ├── 📄 test_current_system.py        # System integration tests
│   └── 📁 src/testing/                  # Unit tests
└── 📁 docs/                             # Documentation
    ├── 📄 SETUP_README.md               # Detailed setup guide
    └── 📄 CERTIFICATE_MIGRATION_GUIDE.md # Migration documentation
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `AUTH_METHOD` | Authentication method | Yes | `personal_oauth` |
| `CLIENT_ID` | Azure AD App Client ID | Yes | `f30e8115-820d-...` |
| `TENANT_ID` | Azure AD Tenant ID | Yes | `15e2c923-6344-...` |
| `KEY_VAULT_URL` | Azure Key Vault URL | Yes | `https://vault.vault.azure.net/` |
| `TARGET_USER_EMAIL` | Target email address | Yes | `me` or `user@domain.com` |
| `OUTLOOK_USERNAME` | Outlook username | Yes | `user@outlook.com` |
| `AI_FOUNDRY_API_KEY` | Azure AI Services key | Yes | `abc123...` |
| `SPEECH_ENDPOINT` | Speech service endpoint | Yes | `https://region.api.cognitive.microsoft.com` |
| `EXCEL_FILE_NAME` | Target Excel filename | Yes | `Scribe.xlsx` |
| `AZURE_STORAGE_CONTAINER_NAME` | Blob storage container | Yes | `voice-attachments` |

### Timer Configuration

The system uses Azure Functions timer triggers with CRON expressions:

- **Every minute**: `0 * * * * *`
- **Every 5 minutes**: `0 */5 * * * *`
- **Business hours only**: `0 * 8-17 1-5 * *`

## 🔍 Monitoring & Troubleshooting

### Health Checks

**Health Endpoint**: `GET /api/health`
```json
{
  "status": "healthy",
  "message": "✅ Scribe Voice Email Processor is healthy",
  "timestamp": "2025-07-29T11:49:59.028181Z",
  "version": "2.0.0"
}
```

**Authentication Status**: `GET /api/auth`
```json
{
  "status": "authenticated",
  "auth_method": "personal_oauth",
  "message": "✅ Authentication system operational",
  "timestamp": "2025-07-29T11:49:59.028181Z"
}
```

### Production Monitoring

Use the built-in monitoring script:
```bash
python src/scripts/monitor_production.py
```

### Common Issues & Solutions

#### 🔧 **Authentication Issues**

**Problem**: `Authentication initialization failed`
**Causes**:
- Expired OAuth tokens
- Missing Key Vault permissions
- Incorrect environment variables

**Solutions**:
1. Regenerate OAuth tokens using the setup script
2. Verify Key Vault RBAC permissions
3. Check environment variable configuration
4. Restart the Azure Function

**Commands**:
```bash
# Check Key Vault access
az keyvault secret show --vault-name scribe-vm-keyvault --name oauth-refresh-token

# Verify RBAC permissions
az role assignment list --assignee [function-managed-identity]

# Restart function app
az functionapp restart --resource-group [rg] --name [function-name]
```

#### 📧 **Email Processing Issues**

**Problem**: `No voice emails found`
**Causes**:
- Emails already processed
- Different email folder
- Permission issues
- Attachment format not recognized

**Solutions**:
1. Check inbox for unprocessed voice emails
2. Verify email has supported audio attachments (.wav, .mp3, .m4a)
3. Check processed/error folders
4. Verify Graph API permissions

#### 🎤 **Transcription Issues**

**Problem**: `Transcription service unavailable`
**Causes**:
- Invalid Speech API key
- Service quota exceeded
- Unsupported audio format
- Network connectivity

**Solutions**:
1. Verify Speech service API key
2. Check service quotas in Azure Portal
3. Ensure audio format is supported
4. Check network connectivity from function

#### 📊 **Excel Integration Issues**

**Problem**: `Failed to write to Excel`
**Causes**:
- File permissions
- OneDrive access issues
- Excel file corruption
- Concurrent access

**Solutions**:
1. Verify OneDrive permissions
2. Check Excel file accessibility
3. Create new monthly worksheet
4. Verify Graph API Files.ReadWrite permission

### Logging & Debugging

**Application Insights Query**:
```kusto
traces
| where timestamp > ago(1h)
| where message contains "Scheduled processing"
| order by timestamp desc
```

**Function Logs**:
```bash
az webapp log tail --resource-group [rg] --name [function-name]
```

## 🔄 Current Status & Known Issues

### ✅ **Working Components**
- ✅ **Local Development**: Fully functional
- ✅ **OAuth Authentication**: Tokens stored in Key Vault
- ✅ **Production Deployment**: Azure Functions deployed
- ✅ **Health Checks**: Endpoints responding correctly
- ✅ **Timer Function**: Configured for every-minute execution
- ✅ **Security**: Production-ready validation and error handling
- ✅ **Unit Tests**: 75% pass rate with comprehensive coverage

### ❌ **Known Issues**

#### 🔧 **Primary Issue: Production Authentication Timeout**
**Status**: In Progress  
**Description**: Production auth and email processing endpoints timeout  
**Impact**: Timer function may not process emails autonomously  
**Root Cause**: OAuth token refresh timing out in production environment  

**Workaround**: Local system processes emails correctly  
**Next Steps**: 
1. Investigate token refresh performance in production
2. Add async token handling
3. Implement retry logic with exponential backoff

#### 📊 **Secondary Issue: Excel Access Errors**
**Status**: Identified  
**Description**: 401 responses when accessing OneDrive Excel files  
**Impact**: Transcriptions complete but not saved to Excel  
**Root Cause**: Excel file permissions or concurrent access  

**Workaround**: Voice messages still transcribed and stored in Blob Storage  
**Next Steps**:
1. Verify OneDrive Excel file permissions
2. Implement Excel file locking mechanism
3. Create fallback CSV export option

### 🎯 **Immediate Fixes Needed**

1. **Production Token Refresh Optimization**
   ```python
   # Implement async token refresh with timeout handling
   async def refresh_token_async(self, timeout=30):
       # Add implementation
   ```

2. **Excel Access Debugging**
   ```bash
   # Verify Excel file permissions
   az storage blob show --account-name [storage] --container-name [container] --name Scribe.xlsx
   ```

3. **Enhanced Error Logging**
   ```python
   # Add detailed error context
   logger.error(f"Processing failed: {error}", extra={'context': context_data})
   ```

## 🔮 Future Enhancements

### 📈 **Planned Features**
- **Real-time processing**: Event-driven triggers via Logic Apps
- **Multi-language support**: Additional speech recognition languages  
- **Advanced analytics**: Processing statistics and insights
- **Mobile notifications**: Push notifications for processed messages
- **Batch processing**: Bulk email processing capabilities

### 🏗️ **Architecture Improvements**
- **Microservices split**: Separate transcription and Excel services
- **Message queuing**: Azure Service Bus for reliable processing
- **Caching layer**: Redis cache for improved performance
- **Load balancing**: Multiple function instances for high availability

## 📚 Additional Documentation

- 📖 **[Setup Guide](docs/SETUP_README.md)** - Detailed setup instructions
- 🔄 **[Migration Guide](docs/CERTIFICATE_MIGRATION_GUIDE.md)** - OAuth migration
- 🧪 **[Testing Guide](tests/README.md)** - Testing procedures
- 🔍 **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Support

For support and questions:
- 📧 **Email**: [Your email]
- 🐛 **Issues**: [GitHub Issues](https://github.com/julianthant/scribe/issues)
- 📖 **Documentation**: [Project Wiki](https://github.com/julianthant/scribe/wiki)

---

**🎤 Built with ❤️ for autonomous voice message processing**