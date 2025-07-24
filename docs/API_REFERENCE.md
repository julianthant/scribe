# 🎯 API Reference

## 📋 Table of Contents

- [Azure Functions Core](#azure-functions-core)
- [Microsoft Graph API](#microsoft-graph-api)
- [Azure Speech Services](#azure-speech-services)
- [Azure Storage](#azure-storage)
- [Azure Key Vault](#azure-key-vault)

## 🔧 Azure Functions Core

### EmailVoiceProcessorWithKeyVault Class

#### Main Methods

##### `process_emails(mytimer: func.TimerRequest)`

**Description**: Timer-triggered function that processes voice emails every minute.

**Parameters**:

- `mytimer` (func.TimerRequest): Azure Functions timer request object

**Returns**: None (logs results)

**Example Usage**:

```python
# Automatically triggered by Azure Functions runtime
# Schedule: Every minute (0 */1 * * * *)
```

##### `_get_access_token_from_keyvault()`

**Description**: Retrieves and refreshes Microsoft Graph access tokens from Azure Key Vault.

**Returns**:

- `str`: Valid access token
- `None`: If token retrieval/refresh fails

**Exception Handling**:

- Logs token refresh attempts
- Handles expired tokens automatically
- Falls back to refresh token if access token expired

##### `_get_voice_messages(access_token: str)`

**Description**: Retrieves unread emails with voice message attachments.

**Parameters**:

- `access_token` (str): Valid Microsoft Graph access token

**Returns**:

- `list`: Array of email objects with voice attachments
- `[]`: Empty array if no voice messages found

**API Call**:

```http
GET https://graph.microsoft.com/v1.0/me/messages
```

**Filter Criteria**:

- `isRead eq false`: Unread emails only
- `hasAttachments eq true`: Must have attachments
- Attachment filename contains audio extensions

##### `_download_attachment_to_blob(email_id: str, attachment_id: str, access_token: str)`

**Description**: Downloads email attachment and stores in Azure Blob Storage.

**Parameters**:

- `email_id` (str): Microsoft Graph email ID
- `attachment_id` (str): Microsoft Graph attachment ID
- `access_token` (str): Valid access token

**Returns**:

- `str`: Blob URL if successful
- `None`: If download fails

**Storage Details**:

- Container: `audio-files`
- Blob name: `{email_id}_{attachment_id}.wav`
- Temporary storage (deleted after processing)

##### `_transcribe_audio(blob_url: str)`

**Description**: Transcribes audio using Azure Speech Services with continuous recognition.

**Parameters**:

- `blob_url` (str): Azure Blob Storage URL

**Returns**:

- `str`: Complete transcription text
- `None`: If transcription fails

**Technical Details**:

- **Audio Conversion**: Mu-law to PCM (8kHz → 16kHz)
- **Recognition Type**: Continuous (captures full audio)
- **Language**: en-US with dictation enabled
- **Timeout**: 5 minutes maximum

##### `_update_excel_file(from_email: str, subject: str, transcription: str, access_token: str)`

**Description**: Appends transcription results to Excel file on OneDrive.

**Parameters**:

- `from_email` (str): Sender's email address
- `subject` (str): Email subject line
- `transcription` (str): Audio transcription text
- `access_token` (str): Valid access token

**Excel Schema**:
| Column | Content | Example |
|--------|---------|---------|
| A | Timestamp | `2024-12-19 10:30:00` |
| B | From Email | `sender@example.com` |
| C | Subject | `Voice Message` |
| D | Transcription | `Hello, this is a test...` |

##### `_move_email_to_processed_folder(email_id: str, access_token: str)`

**Description**: Moves processed email to "Voice Messages Processed" folder.

**Parameters**:

- `email_id` (str): Microsoft Graph email ID
- `access_token` (str): Valid access token

**Returns**:

- `bool`: True if successful, False otherwise

**Folder Management**:

- Creates folder if it doesn't exist
- Requires `Mail.ReadWrite` permission
- Prevents duplicate processing

## 📧 Microsoft Graph API

### Authentication

#### OAuth 2.0 Flow

```python
# Required scopes
scopes = [
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Files.ReadWrite.All",
    "https://graph.microsoft.com/User.Read",
    "offline_access"
]
```

#### Token Management

```python
# Access token (1 hour expiry)
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Refresh token (no expiry)
refresh_data = {
    "client_id": client_id,
    "refresh_token": refresh_token,
    "grant_type": "refresh_token"
}
```

### Email Operations

#### Get Unread Voice Messages

```http
GET /v1.0/me/messages?$filter=isRead eq false and hasAttachments eq true&$select=id,subject,from,attachments&$expand=attachments
```

**Response**:

```json
{
  "value": [
    {
      "id": "email-id",
      "subject": "Voice Message",
      "from": {
        "emailAddress": {
          "address": "sender@example.com"
        }
      },
      "attachments": [
        {
          "id": "attachment-id",
          "name": "audio.wav",
          "contentType": "audio/wav"
        }
      ]
    }
  ]
}
```

#### Download Attachment

```http
GET /v1.0/me/messages/{email-id}/attachments/{attachment-id}/$value
```

**Response**: Binary audio data

#### Move Email to Folder

```http
POST /v1.0/me/messages/{email-id}/move
Content-Type: application/json

{
  "destinationId": "folder-id"
}
```

### OneDrive Operations

#### Get Excel File

```http
GET /v1.0/me/drive/root:/{filename}.xlsx:/workbook/worksheets('Sheet1')/usedRange
```

#### Append to Excel

```http
POST /v1.0/me/drive/root:/{filename}.xlsx:/workbook/worksheets('Sheet1')/range(address='A{row}:D{row}')
Content-Type: application/json

{
  "values": [
    ["2024-12-19 10:30:00", "sender@example.com", "Voice Message", "Transcription text"]
  ]
}
```

## 🎤 Azure Speech Services

### Speech Configuration

```python
import azure.cognitiveservices.speech as speechsdk

speech_config = speechsdk.SpeechConfig(
    subscription=speech_key,
    region=speech_region
)
speech_config.speech_recognition_language = "en-US"
speech_config.enable_dictation()
```

### Audio Configuration

```python
# For continuous recognition
audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

# Create recognizer
speech_recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config,
    audio_config=audio_config
)
```

### Recognition Events

```python
def handle_recognized(evt):
    """Handle recognized speech segments"""
    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
        recognized_text.append(evt.result.text)

def handle_session_stopped(evt):
    """Handle session completion"""
    recognition_done.set()

# Event handlers
speech_recognizer.recognized.connect(handle_recognized)
speech_recognizer.session_stopped.connect(handle_session_stopped)
```

### Audio Format Conversion

```python
import audioop
import wave
import struct

def convert_mulaw_to_pcm(mulaw_data):
    """Convert mu-law audio to PCM format"""
    # Decode mu-law to linear PCM
    linear_data = audioop.ulaw2lin(mulaw_data, 2)

    # Resample from 8kHz to 16kHz
    resampled_data = audioop.ratecv(
        linear_data, 2, 1, 8000, 16000, None
    )[0]

    return resampled_data
```

## 💾 Azure Storage

### Blob Service Client

```python
from azure.storage.blob import BlobServiceClient

blob_service_client = BlobServiceClient.from_connection_string(
    connection_string
)

# Upload blob
blob_client = blob_service_client.get_blob_client(
    container="audio-files",
    blob=blob_name
)
blob_client.upload_blob(audio_data, overwrite=True)
```

### Blob Operations

```python
# Download blob
blob_data = blob_client.download_blob().readall()

# Delete blob
blob_client.delete_blob()

# Get blob URL
blob_url = blob_client.url
```

## 🔐 Azure Key Vault

### Key Vault Client

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(
    vault_url=key_vault_url,
    credential=credential
)
```

### Secret Operations

```python
# Get secret
secret = client.get_secret("secret-name")
secret_value = secret.value

# Set secret
client.set_secret("secret-name", "secret-value")

# List secrets
secrets = client.list_properties_of_secrets()
```

## 🚨 Error Handling

### Common Error Codes

#### Microsoft Graph API

| Error Code | Description       | Solution               |
| ---------- | ----------------- | ---------------------- |
| 401        | Unauthorized      | Refresh access token   |
| 403        | Forbidden         | Check API permissions  |
| 404        | Not Found         | Verify resource exists |
| 429        | Too Many Requests | Implement retry logic  |

#### Azure Speech Services

| Error Code | Description            | Solution                  |
| ---------- | ---------------------- | ------------------------- |
| 400        | Bad Request            | Check audio format        |
| 401        | Unauthorized           | Verify Speech Service key |
| 415        | Unsupported Media Type | Convert audio format      |

#### Azure Storage

| Error Code | Description    | Solution                  |
| ---------- | -------------- | ------------------------- |
| 404        | Blob Not Found | Check blob name/container |
| 409        | Conflict       | Handle concurrent access  |
| 403        | Forbidden      | Check storage permissions |

### Exception Handling Pattern

```python
try:
    # API operation
    result = api_call()
except Exception as e:
    logging.error(f"Operation failed: {str(e)}")
    # Handle specific error types
    if "401" in str(e):
        # Refresh token and retry
        pass
    elif "404" in str(e):
        # Resource not found
        pass
    else:
        # Generic error handling
        pass
```
