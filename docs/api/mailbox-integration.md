# Mailbox Integration API Reference

## Overview

The Scribe FastAPI application provides comprehensive email mailbox integration through Microsoft Graph API, supporting both personal mailboxes and shared mailboxes with advanced voice attachment processing capabilities.

## Authentication

All mailbox endpoints require valid Azure AD authentication. See [Authentication Guide](authentication.md) for setup details.

## Personal Mailbox API

Base path: `/api/v1/mail`

### Folder Operations

#### List Mail Folders
```http
GET /api/v1/mail/folders
```

**Response:**
```json
[
  {
    "id": "folder-id",
    "displayName": "Inbox",
    "parentFolderId": null,
    "childFolderCount": 0,
    "unreadItemCount": 5,
    "totalItemCount": 25,
    "isHidden": false
  }
]
```

#### Create Mail Folder
```http
POST /api/v1/mail/folders
```

**Request Body:**
```json
{
  "displayName": "Voice Messages",
  "parentFolderId": "optional-parent-id"
}
```

### Message Operations

#### List Messages
```http
GET /api/v1/mail/messages?folder_id={id}&has_attachments={bool}&top={int}&skip={int}
```

**Query Parameters:**
- `folder_id` (optional): Specific folder ID
- `has_attachments` (optional): Filter by attachment presence
- `top` (1-1000): Number of messages to return (default: 25)
- `skip` (≥0): Number of messages to skip (default: 0)

**Response:**
```json
{
  "value": [
    {
      "id": "message-id",
      "subject": "Meeting Recording",
      "bodyPreview": "Please find the recording...",
      "sender": {
        "emailAddress": {
          "name": "John Doe",
          "address": "john@example.com"
        }
      },
      "receivedDateTime": "2024-01-15T10:30:00Z",
      "hasAttachments": true,
      "isRead": false
    }
  ],
  "@odata.nextLink": "next-page-url",
  "@odata.count": 100
}
```

#### Get Message by ID
```http
GET /api/v1/mail/messages/{message_id}
```

#### Update Message
```http
PATCH /api/v1/mail/messages/{message_id}
```

**Request Body:**
```json
{
  "isRead": true,
  "importance": "high"
}
```

#### Move Message
```http
POST /api/v1/mail/messages/{message_id}/move
```

**Request Body:**
```json
{
  "destinationId": "folder-id-or-name"
}
```

### Attachment Operations

#### List Message Attachments
```http
GET /api/v1/mail/messages/{message_id}/attachments
```

**Response:**
```json
[
  {
    "id": "attachment-id",
    "name": "recording.mp3",
    "contentType": "audio/mpeg",
    "size": 1048576,
    "isInline": false,
    "lastModifiedDateTime": "2024-01-15T10:30:00Z"
  }
]
```

#### Download Attachment
```http
GET /api/v1/mail/messages/{message_id}/attachments/{attachment_id}/download
```

Returns binary attachment content with appropriate content-type headers.

### Voice Attachment Operations

#### Get Voice Messages
```http
GET /api/v1/mail/voice-messages?folder_id={id}&top={int}
```

#### List All Voice Attachments
```http
GET /api/v1/mail/voice-attachments?folder_id={id}&limit={int}
```

**Response:**
```json
[
  {
    "messageId": "message-id",
    "attachmentId": "attachment-id",
    "name": "voicemail.amr",
    "contentType": "audio/amr",
    "size": 524288,
    "duration": 45.5,
    "sampleRate": 8000,
    "bitRate": 12800
  }
]
```

#### Organize Voice Messages
```http
POST /api/v1/mail/organize-voice
```

**Request Body:**
```json
{
  "targetFolderName": "Voice Messages",
  "createFolder": true,
  "includeSubfolders": false
}
```

**Response:**
```json
{
  "messagesProcessed": 50,
  "messagesMoved": 12,
  "voiceAttachmentsFound": 18,
  "folderCreated": true,
  "targetFolderId": "folder-id",
  "errors": []
}
```

#### Get Voice Attachment Metadata
```http
GET /api/v1/mail/voice-attachments/{message_id}/{attachment_id}/metadata
```

#### Download Voice Attachment
```http
GET /api/v1/mail/voice-attachments/{message_id}/{attachment_id}/download
```

### Search Operations

#### Search Messages
```http
POST /api/v1/mail/search
```

**Request Body:**
```json
{
  "query": "meeting recording",
  "folderId": "optional-folder-id",
  "hasAttachments": true,
  "hasVoiceAttachments": false,
  "dateFrom": "2024-01-01T00:00:00Z",
  "dateTo": "2024-01-31T23:59:59Z",
  "importance": "high",
  "isRead": false,
  "top": 25,
  "skip": 0
}
```

### Statistics

#### Get Mail Statistics
```http
GET /api/v1/mail/statistics?folder_id={id}
```

**Response:**
```json
{
  "folderId": "folder-id",
  "folderName": "Inbox",
  "totalMessages": 100,
  "unreadMessages": 5,
  "messagesWithAttachments": 25,
  "voiceMessages": 8,
  "totalAttachmentSize": 104857600
}
```

#### Get Voice Statistics
```http
GET /api/v1/mail/voice-statistics?folder_id={id}
```

## Shared Mailbox API

Base path: `/api/v1/shared-mailboxes`

### Mailbox Access

#### List Accessible Shared Mailboxes
```http
GET /api/v1/shared-mailboxes
```

**Response:**
```json
{
  "value": [
    {
      "id": "mailbox-id",
      "displayName": "Support Team",
      "emailAddress": "support@company.com",
      "aliases": ["help@company.com"],
      "mailboxType": "shared",
      "isActive": true,
      "description": "Customer support mailbox"
    }
  ],
  "totalCount": 10,
  "accessibleCount": 8
}
```

#### Get Shared Mailbox Details
```http
GET /api/v1/shared-mailboxes/{email_address}
```

**Response:**
```json
{
  "mailbox": {
    "id": "mailbox-id",
    "displayName": "Support Team",
    "emailAddress": "support@company.com"
  },
  "permissions": [],
  "accessLevel": "reviewer",
  "canRead": true,
  "canWrite": false,
  "canSend": false,
  "canManage": false,
  "lastAccessed": "2024-01-15T10:30:00Z"
}
```

### Folder Operations

#### List Shared Mailbox Folders
```http
GET /api/v1/shared-mailboxes/{email_address}/folders
```

#### Create Shared Mailbox Folder
```http
POST /api/v1/shared-mailboxes/{email_address}/folders?folder_name={name}&parent_id={id}
```

### Message Operations

#### List Shared Mailbox Messages
```http
GET /api/v1/shared-mailboxes/{email_address}/messages?folder_id={id}&has_attachments={bool}&top={int}&skip={int}
```

#### Send Message as Shared Mailbox
```http
POST /api/v1/shared-mailboxes/{email_address}/send
```

**Request Body:**
```json
{
  "to": ["recipient@example.com"],
  "cc": ["cc@example.com"],
  "bcc": ["bcc@example.com"],
  "subject": "Response from Support",
  "body": "Thank you for contacting us...",
  "bodyType": "html",
  "importance": "normal",
  "saveToSentItems": true,
  "requestDeliveryReceipt": false,
  "requestReadReceipt": false
}
```

### Organization Operations

#### Organize Shared Mailbox Messages
```http
POST /api/v1/shared-mailboxes/{email_address}/organize
```

**Request Body:**
```json
{
  "targetFolderName": "Voice Messages",
  "createFolder": true,
  "messageType": "voice",
  "includeSubfolders": false,
  "preserveReadStatus": true
}
```

#### Organize Voice Messages in Shared Mailbox
```http
POST /api/v1/shared-mailboxes/{email_address}/organize-voice?target_folder={name}&create_folder={bool}
```

### Cross-Mailbox Operations

#### Search Across Shared Mailboxes
```http
POST /api/v1/shared-mailboxes/search
```

**Request Body:**
```json
{
  "query": "urgent issue",
  "mailboxIds": ["support@company.com", "sales@company.com"],
  "folderId": "optional-folder-id",
  "hasAttachments": true,
  "dateFrom": "2024-01-01T00:00:00Z",
  "dateTo": "2024-01-31T23:59:59Z",
  "top": 25,
  "skip": 0
}
```

**Response:**
```json
{
  "query": "urgent issue",
  "totalResults": 45,
  "searchedMailboxes": ["support@company.com", "sales@company.com"],
  "results": [
    {
      "mailbox": "support@company.com",
      "results": [...],
      "count": 25
    }
  ],
  "executionTimeMs": 1250
}
```

#### Get Voice Messages Across Mailboxes
```http
GET /api/v1/shared-mailboxes/voice-messages/cross-mailbox?mailbox_addresses={emails}&top={int}
```

### Analytics

#### Get Shared Mailbox Statistics
```http
GET /api/v1/shared-mailboxes/{email_address}/statistics
```

**Response:**
```json
{
  "mailboxId": "mailbox-id",
  "mailboxName": "Support",
  "emailAddress": "support@company.com",
  "totalMessages": 500,
  "unreadMessages": 25,
  "messagesWithAttachments": 100,
  "voiceMessages": 15,
  "totalFolders": 12,
  "mailboxSizeMB": 256.5,
  "lastMessageDate": "2024-01-15T10:30:00Z",
  "mostActiveUsers": [],
  "dailyMessageCounts": {},
  "attachmentStatistics": {}
}
```

#### Get Usage Analytics
```http
GET /api/v1/shared-mailboxes/analytics/usage?mailbox_addresses={emails}&days={int}
```

## Voice Attachment Processing

### Supported Audio Formats

The system automatically detects voice attachments across 30+ audio formats:

| Format | MIME Types | Extensions |
|--------|------------|------------|
| MP3 | `audio/mpeg`, `audio/mp3` | `.mp3` |
| WAV | `audio/wav`, `audio/wave` | `.wav`, `.wave` |
| AMR | `audio/amr`, `audio/amr-nb` | `.amr` |
| 3GPP | `audio/3gpp`, `audio/3gpp2` | `.3gp`, `.3gpp` |
| OGG | `audio/ogg`, `audio/vorbis` | `.ogg`, `.oga` |
| M4A | `audio/m4a`, `audio/aac` | `.m4a`, `.aac` |
| FLAC | `audio/flac`, `audio/x-flac` | `.flac` |
| WebM | `audio/webm` | `.webm` |

### Detection Algorithm

Voice attachments are detected using a multi-layer approach:

1. **MIME Type Analysis**: Direct content type matching
2. **File Extension Analysis**: Extension-based detection
3. **Content Type Parameters**: Parsing content type with codecs
4. **Fallback Patterns**: Generic `audio/*` pattern matching

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Validation error |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error |

### Error Response Format

```json
{
  "error": "ValidationError",
  "message": "Invalid folder name provided",
  "error_code": "INVALID_FOLDER_NAME",
  "details": {
    "field": "displayName",
    "value": ""
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common Error Codes

- `INVALID_FOLDER_NAME`: Folder name validation failed
- `FOLDER_NOT_FOUND`: Specified folder does not exist
- `MESSAGE_NOT_FOUND`: Message ID not found
- `ATTACHMENT_NOT_FOUND`: Attachment not found
- `INSUFFICIENT_PERMISSIONS`: User lacks required permissions
- `MAILBOX_ACCESS_DENIED`: Cannot access shared mailbox
- `VOICE_ATTACHMENT_NOT_SUPPORTED`: Attachment is not a voice file

## Rate Limits

- **Personal Mailbox**: 1000 requests per hour per user
- **Shared Mailbox**: 500 requests per hour per mailbox per user
- **Voice Processing**: 100 voice attachments per minute
- **Cross-Mailbox Search**: 10 concurrent searches per user

## Request/Response Examples

### Complete Voice Message Organization

```bash
# 1. List voice messages
curl -X GET "/api/v1/mail/voice-messages?top=100" \
  -H "Authorization: Bearer {token}"

# 2. Organize into dedicated folder
curl -X POST "/api/v1/mail/organize-voice" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "targetFolderName": "Voice Messages",
    "createFolder": true
  }'

# 3. Get statistics
curl -X GET "/api/v1/mail/voice-statistics" \
  -H "Authorization: Bearer {token}"
```

### Shared Mailbox Workflow

```bash
# 1. List accessible shared mailboxes
curl -X GET "/api/v1/shared-mailboxes" \
  -H "Authorization: Bearer {token}"

# 2. Get messages from specific mailbox
curl -X GET "/api/v1/shared-mailboxes/support@company.com/messages?has_attachments=true" \
  -H "Authorization: Bearer {token}"

# 3. Send response as shared mailbox
curl -X POST "/api/v1/shared-mailboxes/support@company.com/send" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "to": ["customer@example.com"],
    "subject": "Re: Support Request",
    "body": "Thank you for contacting support...",
    "bodyType": "html"
  }'
```

## OpenAPI Specification

See [openapi.yaml](openapi.yaml) for the complete OpenAPI 3.0 specification including all request/response schemas, parameter definitions, and authentication requirements.

---

*For implementation details and architecture information, see [Architecture Overview](../architecture/mailbox-integration.md).*