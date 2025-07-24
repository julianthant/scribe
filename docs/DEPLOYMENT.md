# 🚀 Deployment Guide

## Prerequisites

### Azure Resources Required
- ✅ **Azure Function App** (Python 3.12 runtime)
- ✅ **Azure Storage Account** (for blob storage and function storage)
- ✅ **Azure Speech Services** (for audio transcription)
- ✅ **Azure Key Vault** (for secure token storage)
- ✅ **Azure App Registration** (with Mail.ReadWrite permissions)

### Local Development Tools
- ✅ **Azure Functions Core Tools** v4.x
- ✅ **Azure CLI** v2.x
- ✅ **Python** 3.12+
- ✅ **Git** (for version control)

## 🔧 Configuration Setup

### 1. Azure App Registration
```bash
# Required API Permissions:
- Microsoft Graph API:
  ✅ Mail.ReadWrite (Delegated)
  ✅ Files.ReadWrite.All (Delegated)
  ✅ User.Read (Delegated)
  ✅ offline_access (Delegated)

# Redirect URIs:
- http://localhost:8080/oauth/callback
- http://localhost:8080
```

### 2. OAuth Token Setup
```bash
# Run the token setup script
python scripts/get_new_token.py

# This will:
# 1. Open browser for consent
# 2. Generate access/refresh tokens
# 3. Save to .oauth_tokens.json
# 4. Test Mail.ReadWrite permissions
```

### 3. Environment Variables
Update `local.settings.json`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=...",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;...",
    "SPEECH_SERVICE_KEY": "your-speech-service-key",
    "SPEECH_SERVICE_REGION": "eastus",
    "EXCEL_FILE_NAME": "Scribe.xlsx",
    "TARGET_USER_EMAIL": "your-email@outlook.com",
    "KEY_VAULT_URL": "https://your-keyvault.vault.azure.net/"
  }
}
```

## 🏗️ Deployment Steps

### Method 1: Automated Deployment
```bash
# Run the deployment script
python scripts/deploy.py

# This handles:
# - Azure login verification
# - Function app deployment
# - Environment variable configuration
# - Token upload to Key Vault
```

### Method 2: Manual Deployment
```bash
# 1. Login to Azure
az login

# 2. Set subscription
az account set --subscription "your-subscription-id"

# 3. Deploy function
func azure functionapp publish your-function-app-name

# 4. Configure app settings
az functionapp config appsettings set \
  --name your-function-app-name \
  --resource-group your-resource-group \
  --settings @local.settings.json

# 5. Upload tokens to Key Vault
az keyvault secret set \
  --vault-name your-keyvault \
  --name "personal-account-access-token" \
  --value "your-access-token"
```

## ✅ Post-Deployment Verification

### 1. Function Health Check
```bash
# Check function status
az functionapp show \
  --name your-function-app-name \
  --resource-group your-resource-group \
  --query "state"

# Expected: "Running"
```

### 2. Timer Trigger Verification
```bash
# Check function logs
az functionapp logs tail \
  --name your-function-app-name \
  --resource-group your-resource-group

# Look for timer execution every minute
```

### 3. Test Email Processing
1. **Send Test Email**: Send an email with a voice attachment
2. **Monitor Logs**: Watch for processing in Azure portal
3. **Check Excel**: Verify entry in OneDrive Scribe.xlsx
4. **Check Folder**: Confirm email moved to "Voice Messages Processed"

## 🔍 Monitoring & Troubleshooting

### Application Insights
```bash
# Enable Application Insights
az functionapp config appsettings set \
  --name your-function-app-name \
  --resource-group your-resource-group \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=your-key"
```

### Common Issues

#### 1. OAuth Token Expired
```bash
# Symptoms: 401 Unauthorized errors
# Solution: Refresh tokens
python scripts/refresh_tokens.py
```

#### 2. Audio Conversion Failures
```bash
# Symptoms: "Audio format not supported"
# Solution: Check audio file format
python scripts/analyze_audio.py
```

#### 3. Mail.ReadWrite Permission Missing
```bash
# Symptoms: 403 Forbidden on folder operations
# Solution: Re-run token setup with new permissions
python scripts/get_new_token.py
```

## 🔄 Updates & Maintenance

### Updating Code
```bash
# 1. Test locally
python tests/test_local_processing.py

# 2. Deploy changes
python scripts/redeploy.py
```

### Token Refresh
```bash
# Tokens refresh automatically, but for manual refresh:
python scripts/refresh_tokens.py
```

### Monitoring Costs
- **Function Executions**: ~1440/day (1-minute timer)
- **Speech Service**: Per audio minute processed
- **Storage**: Minimal (temporary files only)
- **Graph API**: Within free tier limits

## 📊 Expected Performance

### Processing Times
- **Empty Check**: 2-3 seconds (no voice emails)
- **Voice Processing**: 30-60 seconds (depending on audio length)
- **Response Time**: ~1 minute from email arrival

### Reliability Features
- ✅ **Automatic Retry**: Built into Azure Functions
- ✅ **Error Handling**: Comprehensive exception handling
- ✅ **Logging**: Detailed logs for debugging
- ✅ **Duplicate Prevention**: Folder-based organization
- ✅ **Token Refresh**: Automatic OAuth token renewal
