# Voice Email Processing - End-to-End Test Guide

## 🎯 Overview
This guide helps you run the complete end-to-end test using your real inbox with longer connection timeouts (60 seconds) for better reliability.

## 📋 Prerequisites Checklist

### ✅ Azure Services
- [x] Azure Speech Service API Key: `7e4c2a0696114bf0939646fc49e46094`
- [x] Azure Speech Region: `eastus`
- [x] Azure Foundry Endpoint: `https://ai-julianthant562797747914.cognitiveservices.azure.com`
- [ ] Azure Storage Connection String (you need to provide)

### 📧 Microsoft 365 / Office 365
- [ ] Tenant ID (your Microsoft 365 tenant)
- [ ] Client ID (from app registration)
- [ ] Client Secret (from app registration)
- [ ] Target Email Address (your email)

## 🔧 Setup Steps

### 1. Configure Environment Variables
```bash
# Edit setup_env.sh with your actual values
nano setup_env.sh

# Then source it
source setup_env.sh
```

### 2. Test Configuration
```bash
# Verify all settings are correct
python3 config_helper.py
```

### 3. Run End-to-End Test
```bash
# Run the complete workflow test
python3 run_e2e_test.py
```

## 🚀 What the E2E Test Does

1. **Connects to your real inbox** with 60-second timeouts
2. **Finds voice message attachments** from the last 7 days
3. **Downloads and transcribes** using Azure Foundry Fast Transcription (5.5x faster than real-time)
4. **Extracts structured data** with simple rule-based analysis
5. **Updates Excel file** in your OneDrive
6. **Moves processed emails** to a "Processed" folder

## ⚡ Connection Improvements

### Longer Timeouts
- All HTTP requests now use 60-second timeouts instead of default
- Email API calls: 60 seconds
- Attachment downloads: 60 seconds  
- Graph API operations: 60 seconds

### Retry Logic
The system will automatically retry failed operations and fall back to Speech SDK if Azure Foundry Fast Transcription fails.

## 📁 Files Updated for E2E Testing

- `src/azure_foundry_processor_class.py` - Clean class structure
- `src/azure_foundry_processor_functions.py` - All transcription functions
- `src/email_processor_functions.py` - Updated with longer timeouts
- `tests/test_real_workflow.py` - Updated to use Azure Foundry
- `main.py` - Updated for new processor architecture
- `run_e2e_test.py` - Complete E2E test runner
- `config_helper.py` - Configuration validation

## 🛠️ Quick Test Commands

```bash
# Test Azure Foundry only
python3 demo_foundry.py

# Test configuration
python3 config_helper.py

# Run full E2E test
python3 run_e2e_test.py

# Check test logs
ls -la test_run_*.log
```

## 📧 Required Microsoft App Registration Permissions

Your app registration needs these Graph API permissions:
- `Mail.Read` - Read email messages
- `Mail.ReadWrite` - Move emails to folders
- `Files.ReadWrite` - Update Excel files in OneDrive

## 🔍 Debugging Tips

1. **Check logs**: Test runs create detailed log files
2. **Test components**: Use `demo_foundry.py` to test transcription only
3. **Verify permissions**: Ensure your app registration has correct permissions
4. **Check timeouts**: 60-second timeouts should handle most connection issues

## 📈 Expected Performance

- **Transcription Speed**: 5.5x faster than real-time with Azure Foundry
- **Connection Timeout**: 60 seconds for all operations
- **Processing**: ~3-5 seconds per voice message
- **Total Time**: Depends on number of voice emails in inbox

Ready to test with your real inbox! 🚀
