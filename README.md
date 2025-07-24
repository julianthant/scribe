# 🎙️ Voice Email Processor (Scribe)

> **Production-Ready Azure Function for Automated Voice Message Transcription**

An intelligent Azure Function that automatically processes voice messages sent via email attachments, transcribes them using Azure Speech Services with continuous recognition, and organizes results in Excel with smart email folder management.

## 🎯 Overview

This production system automatically:

1. **📧 Monitors Inbox**: Checks your Outlook inbox every minute for voice attachments
2. **🎵 Smart Audio Processing**: Handles mu-law WAV files with Python-based conversion
3. **🎙️ Advanced Transcription**: Uses continuous speech recognition for complete capture
4. **📊 Excel Integration**: Logs structured data to OneDrive Excel file
5. **📁 Email Organization**: Moves processed emails to "Voice Messages Processed" folder
6. **🚫 Duplicate Prevention**: Prevents reprocessing through folder-based organization

## 🏗️ Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Email Inbox       │───▶│   Azure Function     │───▶│   Voice Processing   │
│   (Voice Messages)  │    │   (Timer: 1 minute)  │    │   (Continuous Recognition) │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
                                      │                           │
                                      ▼                           ▼
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│  Processed Folder   │◀───│   Email Organization │◀───│   Excel Logging     │
│  (Organized)        │    │   (Folder Management)│    │   (OneDrive)        │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
```

### Core Components:
- **🌩️ Azure Functions**: Serverless compute with 1-minute timer trigger
- **📱 Microsoft Graph API**: Personal email and OneDrive access with Mail.ReadWrite
- **🎤 Azure Speech Services**: Continuous speech recognition with mu-law support
- **💾 Azure Storage**: Blob storage for temporary voice files
- **🔐 Azure Key Vault**: Secure OAuth token management
- **📈 OneDrive Excel**: Structured data logging and reporting
- **Azure Key Vault**: Secure OAuth token storage
- **OneDrive Excel**: Results logging

## 📋 Prerequisites

### Software Requirements

- Python 3.12+
- Azure CLI
- Azure Functions Core Tools v4
- Git

### Azure Requirements

- Azure subscription
- Microsoft 365 account (personal or work)
- Azure AD app registration

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd voice-email-processor
```

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Azure CLI Authentication

```bash
az login
```

### 4. OAuth Setup

```bash
python3 oauth_refresh.py
```

This will:

- Open a browser for OAuth authentication
- Save tokens to `.oauth_tokens.json`
- Configure Microsoft Graph API access

### 5. Deploy to Azure

```bash
python3 deploy.py
```

This will:

- Create all required Azure resources
- Configure RBAC permissions
- Store OAuth tokens in Key Vault
- Deploy the function code

### 6. Test the Setup

```bash
python3 test_comprehensive.py
```

## 📁 Project Structure

```
voice-email-processor/
├── function_app.py              # Main Azure Function code
├── deploy.py                    # Deployment automation
├── oauth_refresh.py             # OAuth token management
├── test_comprehensive.py        # Complete test suite
├── local.settings.json          # Local configuration
├── requirements.txt             # Python dependencies
├── host.json                    # Function host settings
├── .funcignore                  # Files to exclude from deployment
├── ProcessEmails/               # Function definition
│   ├── __init__.py             # Function entry point
│   └── function.json           # Function binding configuration
└── README.md                   # This file
```

## ⚙️ Configuration

### Environment Variables

The function uses these configuration values (stored in Key Vault when deployed):

- `CLIENT_ID`: Azure AD app client ID
- `CLIENT_SECRET`: Azure AD app client secret
- `TENANT_ID`: Azure AD tenant ID
- `AZURE_STORAGE_CONNECTION_STRING`: Storage account connection
- `SPEECH_SERVICE_KEY`: Azure Speech Services API key
- `SPEECH_SERVICE_REGION`: Azure region (e.g., "eastus")
- `EXCEL_FILE_NAME`: Name of Excel file in OneDrive (default: "scribe.xlsx")
- `TARGET_USER_EMAIL`: Email to monitor (default: uses authenticated user)
- `KEY_VAULT_URL`: Azure Key Vault URL for token storage

### Excel File Setup

The function creates an Excel file in your OneDrive root with these columns:

- **Date**: When the email was received
- **From**: Email sender
- **Subject**: Email subject line
- **Filename**: Name of the voice attachment
- **Duration**: Audio duration (if available)
- **Transcription**: Speech-to-text result
- **Processing Time**: How long transcription took

## 🔧 Development

### Local Testing

```bash
# Start the function locally
func start

# Run comprehensive tests
python3 test_comprehensive.py

# Check specific components
python3 -c "
import requests
with open('.oauth_tokens.json') as f:
    tokens = json.load(f)
headers = {'Authorization': f'Bearer {tokens[\"access_token\"]}'}
response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
print('OAuth Status:', response.status_code)
"
```

### Making Changes

1. **Function Logic**: Edit `function_app.py`
2. **Dependencies**: Update `requirements.txt`
3. **Deployment**: Modify `deploy.py`
4. **Testing**: Add tests to `test_comprehensive.py`

### Redeployment

```bash
# Deploy code changes only
func azure functionapp publish scribe-personal-app

# Full redeployment
python3 deploy.py
```

## 📊 Monitoring

### Azure Portal

1. Go to Azure Portal → Function Apps → `scribe-personal-app`
2. Check **Functions** → **ProcessEmails** for execution history
3. View **Application Insights** for detailed logs and performance
4. Monitor **Invocations**, **Success Rate**, and **Duration**

### Command Line Monitoring

```bash
# View live logs
az functionapp log tail --name scribe-personal-app --resource-group scribe-personal

# Check function status
az functionapp show --name scribe-personal-app --resource-group scribe-personal --query "state"

# List recent executions
az monitor activity-log list --resource-group scribe-personal --max-events 10
```

### Function Schedule

- **Trigger**: Timer-based (every 15 minutes)
- **Schedule**: `0 */15 * * * *` (CRON expression)
- **Timezone**: UTC

## 🛠️ Troubleshooting

### Common Issues

#### "OAuth token expired"

```bash
python3 oauth_refresh.py
```

#### "Storage access denied"

Check storage account connection string in Azure Portal.

#### "Speech service quota exceeded"

Monitor Speech Services usage in Azure Portal. Free tier has limits.

#### "Excel file not found"

The function creates the Excel file automatically on first run.

### Debug Commands

```bash
# Test OAuth tokens
python3 test_comprehensive.py

# Check Azure resources
az resource list --resource-group scribe-personal --output table

# Verify function app settings
az functionapp config appsettings list --name scribe-personal-app --resource-group scribe-personal

# Test Speech Services
curl -X POST "https://eastus.api.cognitive.microsoft.com/speechtotext/v3.0/endpoints" \
  -H "Ocp-Apim-Subscription-Key: YOUR_SPEECH_KEY"
```

## 🔒 Security

### Best Practices Implemented

- **OAuth tokens stored in Azure Key Vault** (not in environment variables)
- **Managed Identity** for Azure service authentication
- **RBAC permissions** for least-privilege access
- **Connection strings** stored securely
- **No hardcoded secrets** in code

### Key Vault Secrets

The following secrets are stored in Azure Key Vault:

- `personal-account-access-token`
- `personal-account-refresh-token`
- `personal-account-client-id`
- `personal-account-client-secret`

### Permissions Required

The Azure AD app needs these Microsoft Graph permissions:

- `Mail.Read`: Read email messages
- `Files.ReadWrite.All`: Access OneDrive files
- `User.Read`: Read user profile

## 💰 Cost Estimation

**Monthly costs (estimated):**

- **Azure Functions**: ~$0.00 (within free tier for low volume)
- **Azure Storage**: ~$0.05 (minimal usage)
- **Azure Speech Services**: ~$0.00 (free tier: 5 hours/month)
- **Azure Key Vault**: ~$0.00 (within free operations)

**Total: < $0.10/month** for typical personal use.

## 🔄 Updates and Maintenance

### Regular Tasks

- **Weekly**: Check function execution logs
- **Monthly**: Review Azure costs and usage
- **Quarterly**: Update Python dependencies
- **Semi-annually**: Rotate OAuth secrets

### Update Process

```bash
# Update dependencies
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt

# Test locally
python3 test_comprehensive.py
func start

# Deploy updates
func azure functionapp publish scribe-personal-app
```

## 📞 Support

### Resources

- [Azure Functions Documentation](https://docs.microsoft.com/en-us/azure/azure-functions/)
- [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/)
- [Azure Speech Services](https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/)

### Getting Help

1. **Check logs**: Use `az functionapp log tail` or Azure Portal
2. **Run tests**: `python3 test_comprehensive.py`
3. **Check status**: Verify all Azure resources are running
4. **Review permissions**: Ensure OAuth and RBAC are configured

## 📝 License

This project is provided as-is for educational and personal use. See the Azure service terms for cloud resource usage.

## 🙏 Acknowledgments

- Built on Azure serverless platform
- Uses Microsoft Graph API for Office 365 integration
- Powered by Azure Cognitive Services for speech recognition

---

**Made with ❤️ for automating voice message transcription**
