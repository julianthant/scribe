# 📁 Project Structure

```
scribe/
├── 📄 README.md                    # Main project documentation
├── ⚙️ function_app.py             # Core Azure Function implementation
├── 🏠 host.json                   # Azure Functions host configuration
├── 📦 requirements.txt            # Python dependencies
├── 🔧 local.settings.json         # Local development configuration
├── 🚫 .funcignore                # Files to exclude from deployment
├── 🚫 .gitignore                 # Git ignore patterns
├── 🎯 ProcessEmails/              # Azure Function definition
│   ├── 📄 function.json          # Function trigger configuration (1-minute timer)
│   └── 📄 __init__.py            # Function entry point
├── 📝 docs/                      # Documentation
│   ├── 📄 PROJECT_STRUCTURE.md   # This file
│   ├── 📄 DEPLOYMENT.md          # Deployment instructions
│   ├── 📄 CONFIGURATION.md       # Configuration guide
│   └── 📄 task.md                # Original requirements
├── 🧪 tests/                     # Test scripts
│   ├── 📄 test_local_processing.py        # End-to-end local testing
│   ├── 📄 test_folder_organization.py     # Folder management testing
│   ├── 📄 test_python_conversion.py       # Audio conversion testing
│   ├── 📄 test_comprehensive.py           # Comprehensive system testing
│   ├── 📄 test_smart_detection.py         # Smart email detection testing
│   └── 📄 test_category_organization.py   # Alternative organization testing
├── 🔧 scripts/                   # Utility scripts
│   ├── 📄 get_new_token.py       # OAuth token setup with Mail.ReadWrite
│   ├── 📄 refresh_tokens.py      # Token refresh utility
│   ├── 📄 deploy.py              # Deployment automation
│   ├── 📄 redeploy.py            # Redeployment utility
│   ├── 📄 create_excel_file.py   # Excel file initialization
│   ├── 📄 create_onedrive_file.py # OneDrive file setup
│   ├── 📄 verify_onedrive.py     # OneDrive verification
│   ├── 📄 diagnose_services.py   # Service diagnostics
│   ├── 📄 analyze_audio.py       # Audio analysis utility
│   ├── 📄 check_voice_file.py    # Voice file validation
│   └── 📄 debug_converted_audio.py # Audio debugging
└── 🔒 .oauth_tokens.json         # OAuth tokens (gitignored)
```

## 📋 File Descriptions

### Core Application Files
- **`function_app.py`**: Main application logic with `EmailVoiceProcessorWithKeyVault` class
- **`host.json`**: Azure Functions runtime configuration
- **`requirements.txt`**: Python package dependencies for Azure deployment
- **`ProcessEmails/function.json`**: Timer trigger configuration (1-minute intervals)

### Configuration Files
- **`local.settings.json`**: Local development environment variables
- **`.oauth_tokens.json`**: OAuth access/refresh tokens for Microsoft Graph API
- **`.funcignore`**: Excludes test files and scripts from Azure deployment

### Test Suite
- **End-to-End Testing**: Complete workflow validation
- **Component Testing**: Individual feature validation
- **Integration Testing**: Service connectivity verification

### Utility Scripts
- **Token Management**: OAuth setup and refresh automation
- **Deployment**: Azure deployment and configuration
- **Diagnostics**: Service health checking and debugging
- **Setup**: Initial configuration and file creation

## 🔧 Key Components

### EmailVoiceProcessorWithKeyVault Class
```python
class EmailVoiceProcessorWithKeyVault:
    def __init__(self):
        # Initialize Azure services
    
    def process_emails(self):
        # Main processing workflow
    
    def _get_emails_with_voice_attachments(self):
        # Smart inbox monitoring
    
    def _transcribe_audio(self, blob_url):
        # Continuous speech recognition
    
    def _move_email_to_processed_folder(self, email_id):
        # Email organization
```

### Timer Configuration
```json
{
  "schedule": "0 */1 * * * *",  // Every minute
  "runOnStartup": false,
  "useMonitor": true
}
```

### Audio Processing Pipeline
1. **Download**: Azure SDK blob download (reliable for large files)
2. **Convert**: Python audioop mu-law to PCM conversion
3. **Resample**: 8kHz to 16kHz for Azure Speech Services
4. **Recognize**: Continuous speech recognition for complete capture

### Email Organization
1. **Inbox Monitoring**: Check only inbox for unprocessed emails
2. **Voice Detection**: Filter for audio attachments (.wav, .mp3, .m4a, etc.)
3. **Processing**: Transcribe and log to Excel
4. **Organization**: Move to "Voice Messages Processed" folder
5. **Duplicate Prevention**: Processed emails excluded from future scans
