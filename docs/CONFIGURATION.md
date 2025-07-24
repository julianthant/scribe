# ⚙️ Configuration Guide

## 🔐 Security Configuration

### Azure Key Vault Setup

```bash
# Create Key Vault (if not exists)
az keyvault create \
  --name your-scribe-keyvault \
  --resource-group your-resource-group \
  --location eastus

# Grant Function App access
az keyvault set-policy \
  --name your-scribe-keyvault \
  --object-id $(az functionapp identity show \
    --name your-function-app \
    --resource-group your-resource-group \
    --query principalId -o tsv) \
  --secret-permissions get list
```

### Required Secrets in Key Vault

| Secret Name                      | Description                   | Example Value        |
| -------------------------------- | ----------------------------- | -------------------- |
| `personal-account-access-token`  | Microsoft Graph access token  | `eyJ0eXAiOiJKV1Q...` |
| `personal-account-refresh-token` | Microsoft Graph refresh token | `M.R3_BAY.-ChSP...`  |

## 📧 Microsoft Graph API Configuration

### App Registration Settings

```json
{
  "application_id": "your-app-id",
  "tenant_id": "common",
  "redirect_uri": "http://localhost:8080/oauth/callback",
  "scopes": [
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Files.ReadWrite.All",
    "https://graph.microsoft.com/User.Read",
    "offline_access"
  ]
}
```

### API Permissions Checklist

- [ ] **Mail.ReadWrite** - Required for moving emails to processed folder
- [ ] **Files.ReadWrite.All** - Required for Excel file operations on OneDrive
- [ ] **User.Read** - Basic user profile access
- [ ] **offline_access** - Required for refresh token functionality

## 🎵 Azure Speech Services Configuration

### Service Setup

```bash
# Create Speech Service
az cognitiveservices account create \
  --name your-speech-service \
  --resource-group your-resource-group \
  --kind SpeechServices \
  --sku S0 \
  --location eastus
```

### Supported Audio Formats

| Format | Sample Rate  | Channels    | Bit Depth | Notes                      |
| ------ | ------------ | ----------- | --------- | -------------------------- |
| WAV    | 16kHz        | Mono        | 16-bit    | Preferred format           |
| PCM    | 8kHz → 16kHz | Mono        | 16-bit    | Auto-converted from mu-law |
| MP3    | Various      | Mono/Stereo | Various   | Automatically handled      |

### Speech Recognition Settings

```python
speech_config = speechsdk.SpeechConfig(
    subscription=speech_key,
    region=speech_region
)
speech_config.speech_recognition_language = "en-US"
speech_config.enable_dictation()  # For better punctuation
```

## 📊 Excel File Configuration

### OneDrive File Structure

```
OneDrive Root/
├── Scribe.xlsx (Main transcription log)
└── Documents/
    └── Scribe/ (Optional: organized folder)
```

### Excel Sheet Schema

| Column | Type     | Description       | Example                            |
| ------ | -------- | ----------------- | ---------------------------------- |
| A      | DateTime | Timestamp         | `2024-12-19 10:30:00`              |
| B      | Text     | From Email        | `sender@example.com`               |
| C      | Text     | Subject           | `Voice Message`                    |
| D      | Text     | Transcription     | `Hello, this is a test message...` |
| E      | Number   | Audio Duration    | `21.5` (seconds)                   |
| F      | Text     | Processing Status | `Success`                          |

## ⏰ Timer Configuration

### Cron Expression Settings

```json
{
  "schedule": "0 */1 * * * *",
  "runOnStartup": false,
  "useMonitor": true
}
```

### Schedule Options

| Frequency           | Cron Expression      | Use Case                                   |
| ------------------- | -------------------- | ------------------------------------------ |
| Every minute        | `0 */1 * * * *`      | **Current setting** - Real-time processing |
| Every 5 minutes     | `0 */5 * * * *`      | Reduced costs, delayed processing          |
| Every hour          | `0 0 * * * *`        | Batch processing mode                      |
| Business hours only | `0 */1 8-17 * * 1-5` | M-F 8am-5pm processing                     |

## 🔧 Environment Variables

### Required Settings (local.settings.json)

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

### Azure Function App Settings

```bash
# Set all required environment variables
az functionapp config appsettings set \
  --name your-function-app \
  --resource-group your-resource-group \
  --settings \
    "SPEECH_SERVICE_KEY=your-key" \
    "SPEECH_SERVICE_REGION=eastus" \
    "EXCEL_FILE_NAME=Scribe.xlsx" \
    "TARGET_USER_EMAIL=your@email.com" \
    "KEY_VAULT_URL=https://your-vault.vault.azure.net/"
```

## 📁 Folder Organization

### Email Folder Structure

```
Inbox/
├── (Unprocessed voice emails)
└── Voice Messages Processed/
    ├── (Successfully processed emails)
    └── Subfolders/ (Optional organization)
```

### Folder Creation Logic

```python
# Automatic folder creation if not exists
folder_name = "Voice Messages Processed"
# Function will create folder with proper permissions
# Requires Mail.ReadWrite scope for folder operations
```

## 🔊 Audio Processing Configuration

### Mu-law to PCM Conversion

```python
# Automatic conversion for Outlook voice messages
# 8kHz mu-law → 16kHz PCM for Azure Speech
conversion_settings = {
    "input_format": "mu-law",
    "input_sample_rate": 8000,
    "output_format": "pcm",
    "output_sample_rate": 16000,
    "channels": 1,
    "bit_depth": 16
}
```

### Speech Recognition Settings

```python
# Continuous recognition for long voice messages
recognition_config = {
    "language": "en-US",
    "enable_dictation": True,
    "continuous_recognition": True,
    "session_timeout": 300,  # 5 minutes max
    "phrase_timeout": 30     # 30 seconds silence
}
```

## 💰 Cost Optimization

### Recommended Settings

| Resource        | Setting          | Cost Impact              |
| --------------- | ---------------- | ------------------------ |
| Function App    | Consumption Plan | Pay per execution        |
| Speech Service  | S0 Standard      | $1/hour of audio         |
| Storage Account | Standard LRS     | Minimal impact           |
| Key Vault       | Standard         | $0.03 per 10K operations |

### Cost Monitoring

```bash
# Set up cost alerts
az consumption budget create \
  --budget-name scribe-monthly-budget \
  --amount 50 \
  --time-grain Monthly \
  --start-date 2024-01-01
```

## 🔄 Backup & Recovery

### Configuration Backup

```bash
# Export app settings
az functionapp config appsettings list \
  --name your-function-app \
  --resource-group your-resource-group \
  > app-settings-backup.json

# Export Key Vault secrets (names only)
az keyvault secret list \
  --vault-name your-keyvault \
  > keyvault-secrets-backup.json
```

### Recovery Procedures

1. **Function App Recovery**: Redeploy from git repository
2. **Token Recovery**: Re-run OAuth setup script
3. **Configuration Recovery**: Restore from backup files
4. **Excel Recovery**: OneDrive built-in versioning
