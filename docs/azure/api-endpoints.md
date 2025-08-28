# Azure AI Foundry Transcription API Endpoints

This document provides detailed information about all API endpoints for the Azure AI Foundry voice transcription system.

## Base URL

All transcription endpoints are prefixed with:
```
/api/v1/transcriptions
```

## Authentication

All endpoints require authentication via Bearer token:
```http
Authorization: Bearer <your-access-token>
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Common HTTP status codes:
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource not found)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error (system error)

## Endpoints

### 1. Transcribe Voice Attachment

Transcribe a specific voice attachment using Azure AI Foundry.

```http
POST /api/v1/transcriptions/voice/{voice_attachment_id}
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `voice_attachment_id` | string (UUID) | Yes | ID of the voice attachment to transcribe |

#### Request Body

```json
{
  "model_deployment": "whisper",
  "language": "en",
  "prompt": "Expected technical discussion about project updates",
  "force_retranscribe": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model_deployment` | string | No | `"whisper"` | Azure OpenAI model deployment name |
| `language` | string | No | `null` | Language code (ISO-639-1 format, e.g., "en", "es") |
| `prompt` | string | No | `null` | Optional text to guide transcription style |
| `force_retranscribe` | boolean | No | `false` | Force retranscription if already exists |

#### Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "voice_attachment_id": "550e8400-e29b-41d4-a716-446655440001",
  "transcript_text": "Hello everyone, this is a project update for Q4 2024. Our team has successfully completed the migration to Azure AI Foundry...",
  "language": "en",
  "confidence_score": 0.95,
  "transcription_status": "completed",
  "model_name": "whisper-1",
  "response_format": "verbose_json",
  "has_word_timestamps": true,
  "has_segment_timestamps": true,
  "audio_duration_seconds": 125.4,
  "processing_time_ms": 3420,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "voice_attachment": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "original_filename": "project_update.m4a",
    "content_type": "audio/m4a",
    "size_bytes": 1245760,
    "sender_email": "john.doe@company.com",
    "sender_name": "John Doe",
    "subject": "Q4 Project Update",
    "received_at": "2024-01-15T09:45:00Z"
  },
  "segments": [
    {
      "id": "segment-1",
      "segment_index": 0,
      "segment_type": "segment",
      "start_time_seconds": 0.0,
      "end_time_seconds": 4.2,
      "duration_seconds": 4.2,
      "text": "Hello everyone, this is a project update",
      "confidence_score": 0.98,
      "avg_logprob": -0.15
    },
    {
      "id": "segment-2",
      "segment_index": 1,
      "segment_type": "segment",
      "start_time_seconds": 4.2,
      "end_time_seconds": 8.7,
      "duration_seconds": 4.5,
      "text": "for Q4 2024. Our team has successfully",
      "confidence_score": 0.94,
      "avg_logprob": -0.23
    }
  ]
}
```

---

### 2. Get Transcription by Voice Attachment

Retrieve an existing transcription for a voice attachment.

```http
GET /api/v1/transcriptions/voice/{voice_attachment_id}
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `voice_attachment_id` | string (UUID) | Yes | ID of the voice attachment |

#### Response

Same structure as transcribe endpoint response.

---

### 3. Get Transcription by ID

Retrieve a specific transcription by its ID.

```http
GET /api/v1/transcriptions/{transcription_id}
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `transcription_id` | string (UUID) | Yes | ID of the transcription |

#### Response

Same structure as transcribe endpoint response.

---

### 4. Batch Transcribe Voice Attachments

Transcribe multiple voice attachments concurrently.

```http
POST /api/v1/transcriptions/batch
```

#### Request Body

```json
{
  "voice_attachment_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002",
    "550e8400-e29b-41d4-a716-446655440003"
  ],
  "model_deployment": "whisper",
  "language": "en",
  "max_concurrent": 3,
  "force_retranscribe": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `voice_attachment_ids` | array[string] | Yes | - | List of voice attachment IDs (max 20) |
| `model_deployment` | string | No | `"whisper"` | Model deployment name |
| `language` | string | No | `null` | Language code for all files |
| `max_concurrent` | integer | No | `3` | Maximum concurrent requests (1-10) |
| `force_retranscribe` | boolean | No | `false` | Force retranscription |

#### Response

```json
{
  "results": {
    "550e8400-e29b-41d4-a716-446655440001": {
      "status": "completed",
      "transcription": {
        "id": "transcription-uuid-1",
        "transcript_text": "First voice message content...",
        "confidence_score": 0.95
      }
    },
    "550e8400-e29b-41d4-a716-446655440002": {
      "status": "failed",
      "error": "Audio format not supported"
    },
    "550e8400-e29b-41d4-a716-446655440003": {
      "status": "completed",
      "transcription": {
        "id": "transcription-uuid-3",
        "transcript_text": "Third voice message content...",
        "confidence_score": 0.89
      }
    }
  },
  "successful_count": 2,
  "failed_count": 1,
  "total_count": 3
}
```

---

### 5. List Transcriptions

Retrieve transcriptions with filtering, searching, and pagination.

```http
GET /api/v1/transcriptions
```

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | - | Filter by status (`completed`, `failed`, `processing`) |
| `language` | string | No | - | Filter by language code |
| `model` | string | No | - | Filter by model name |
| `search` | string | No | - | Search in transcript text |
| `limit` | integer | No | `50` | Results per page (1-200) |
| `offset` | integer | No | `0` | Results to skip |
| `order_by` | string | No | `created_at` | Field to order by |
| `order_direction` | string | No | `desc` | Order direction (`asc` or `desc`) |

#### Example Request

```http
GET /api/v1/transcriptions?search=project&status=completed&limit=20&offset=0
```

#### Response

```json
{
  "transcriptions": [
    {
      "id": "transcription-uuid-1",
      "transcript_text": "Project update for Q4 2024...",
      "confidence_score": 0.95,
      "created_at": "2024-01-15T10:30:00Z",
      "voice_attachment": {
        "original_filename": "update.m4a",
        "sender_email": "john@company.com"
      }
    }
  ],
  "total_count": 45,
  "page_size": 20,
  "page_offset": 0
}
```

---

### 6. Delete Transcription

Delete a transcription and all associated data.

```http
DELETE /api/v1/transcriptions/{transcription_id}
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `transcription_id` | string (UUID) | Yes | ID of the transcription to delete |

#### Response

```json
{
  "message": "Transcription 550e8400-e29b-41d4-a716-446655440000 deleted successfully"
}
```

---

### 7. Get Transcription Statistics

Retrieve transcription analytics and statistics.

```http
GET /api/v1/transcriptions/statistics/summary
```

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `days_ago` | integer | No | - | Filter data from N days ago (1-365) |

#### Example Request

```http
GET /api/v1/transcriptions/statistics/summary?days_ago=30
```

#### Response

```json
{
  "total_transcriptions": 1250,
  "status_breakdown": {
    "completed": 1200,
    "failed": 35,
    "processing": 15
  },
  "language_breakdown": {
    "en": 800,
    "es": 300,
    "fr": 100,
    "de": 50
  },
  "model_breakdown": {
    "whisper-1": 750,
    "gpt-4o-transcribe": 400,
    "gpt-4o-mini-transcribe": 100
  },
  "quality_metrics": {
    "avg_confidence_score": 0.92,
    "avg_processing_time_ms": 2850,
    "avg_audio_duration_seconds": 45.2,
    "total_audio_duration_seconds": 56500
  },
  "completed_transcriptions": 1200,
  "failed_transcriptions": 35,
  "processing_transcriptions": 15
}
```

---

### 8. Get Transcription Errors

Retrieve transcription errors for troubleshooting.

```http
GET /api/v1/transcriptions/errors/list
```

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `resolved` | boolean | No | - | Filter by resolution status |
| `limit` | integer | No | `50` | Results per page (1-200) |
| `offset` | integer | No | `0` | Results to skip |

#### Example Request

```http
GET /api/v1/transcriptions/errors/list?resolved=false&limit=10
```

#### Response

```json
{
  "errors": [
    {
      "id": "error-uuid-1",
      "voice_attachment_id": "attachment-uuid-1",
      "error_type": "transcription_api",
      "error_code": "AUDIO_FORMAT_UNSUPPORTED",
      "error_message": "The audio format 'audio/wav' is not supported by the current model",
      "model_name": "whisper-1",
      "audio_format": "audio/wav",
      "is_resolved": false,
      "retry_count": 2,
      "created_at": "2024-01-15T10:15:00Z"
    }
  ],
  "total_count": 15,
  "page_size": 10,
  "page_offset": 0
}
```

---

### 9. Resolve Transcription Error

Mark a transcription error as resolved.

```http
POST /api/v1/transcriptions/errors/{error_id}/resolve
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `error_id` | string (UUID) | Yes | ID of the error to resolve |

#### Request Body

```json
{
  "resolution_notes": "Audio file was converted to MP3 format and retranscribed successfully"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resolution_notes` | string | No | Optional notes about the resolution |

#### Response

```json
{
  "message": "Transcription error 550e8400-e29b-41d4-a716-446655440000 resolved successfully"
}
```

---

### 10. Retry Failed Transcription

Retry transcription for a failed voice attachment.

```http
POST /api/v1/transcriptions/voice/{voice_attachment_id}/retry
```

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `voice_attachment_id` | string (UUID) | Yes | ID of the voice attachment |

#### Request Body

```json
{
  "model_deployment": "gpt-4o-transcribe",
  "language": "en"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model_deployment` | string | No | Different model to try |
| `language` | string | No | Language code |

#### Response

Same structure as transcribe endpoint response.

---

### 11. Get Supported Models

Retrieve list of supported transcription models.

```http
GET /api/v1/transcriptions/models/supported
```

#### Response

```json
{
  "models": [
    {
      "id": "whisper-1",
      "name": "Whisper v1",
      "description": "General-purpose speech recognition model",
      "max_file_size_mb": 25,
      "supported_formats": ["mp3", "wav", "m4a", "aac", "ogg", "webm", "mp4", "mpeg", "mpga"]
    },
    {
      "id": "gpt-4o-transcribe",
      "name": "GPT-4o Transcribe",
      "description": "Speech to text powered by GPT-4o",
      "max_file_size_mb": 25,
      "supported_formats": ["mp3", "wav", "m4a", "aac", "ogg", "webm", "mp4", "mpeg", "mpga"]
    },
    {
      "id": "gpt-4o-mini-transcribe",
      "name": "GPT-4o Mini Transcribe",
      "description": "Speech to text powered by GPT-4o mini",
      "max_file_size_mb": 25,
      "supported_formats": ["mp3", "wav", "m4a", "aac", "ogg", "webm", "mp4", "mpeg", "mpga"]
    }
  ]
}
```

---

### 12. Health Check

Check the health status of the transcription service.

```http
GET /api/v1/transcriptions/health/status
```

#### Response

```json
{
  "service": "TranscriptionService",
  "status": "healthy",
  "azure_ai_foundry": {
    "status": "healthy",
    "endpoint": "https://scribe-openai.openai.azure.com",
    "api_version": "2024-10-21",
    "default_model": "whisper",
    "token_acquisition_time_ms": 245,
    "authenticated": true,
    "token_expires_at": "2024-01-15T11:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Rate Limits

The API implements rate limiting to ensure fair usage:

| Endpoint Type | Rate Limit | Window |
|---------------|------------|---------|
| Individual Transcription | 10 requests/minute | Per user |
| Batch Transcription | 3 requests/minute | Per user |
| List/Search Operations | 100 requests/minute | Per user |
| Statistics | 20 requests/minute | Per user |
| Health Checks | 60 requests/minute | Per user |

## Best Practices

### Request Optimization

1. **Batch Processing**: Use batch endpoint for multiple files
2. **Language Specification**: Provide language code when known
3. **Model Selection**: Choose appropriate model for use case
4. **Prompt Engineering**: Use descriptive prompts for better accuracy

### Error Handling

1. **Retry Logic**: Implement exponential backoff for retries
2. **Error Monitoring**: Monitor error rates and types
3. **Graceful Degradation**: Handle service unavailability
4. **User Feedback**: Provide meaningful error messages

### Performance

1. **Pagination**: Use appropriate page sizes for list operations
2. **Filtering**: Apply filters to reduce response size
3. **Caching**: Cache results when appropriate
4. **Concurrent Requests**: Respect rate limits and concurrency settings

## SDK Examples

### Python

```python
import httpx
import asyncio

class TranscriptionClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
    
    async def transcribe_voice_attachment(
        self, 
        voice_attachment_id: str, 
        model_deployment: str = "whisper",
        language: str = None
    ):
        url = f"{self.base_url}/api/v1/transcriptions/voice/{voice_attachment_id}"
        data = {
            "model_deployment": model_deployment,
            "language": language,
            "force_retranscribe": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()
    
    async def list_transcriptions(
        self, 
        search: str = None, 
        limit: int = 50, 
        offset: int = 0
    ):
        url = f"{self.base_url}/api/v1/transcriptions"
        params = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()

# Usage example
async def main():
    client = TranscriptionClient(
        base_url="https://your-api-domain.com",
        token="your-access-token"
    )
    
    # Transcribe a voice attachment
    result = await client.transcribe_voice_attachment(
        voice_attachment_id="550e8400-e29b-41d4-a716-446655440001",
        language="en"
    )
    print(f"Transcription: {result['transcript_text']}")
    
    # Search transcriptions
    transcriptions = await client.list_transcriptions(search="project")
    print(f"Found {transcriptions['total_count']} transcriptions")

if __name__ == "__main__":
    asyncio.run(main())
```

### JavaScript/TypeScript

```typescript
interface TranscriptionClient {
  baseUrl: string;
  token: string;
}

class TranscriptionAPI implements TranscriptionClient {
  constructor(public baseUrl: string, public token: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  private get headers() {
    return {
      'Authorization': `Bearer ${this.token}`,
      'Content-Type': 'application/json'
    };
  }

  async transcribeVoiceAttachment(
    voiceAttachmentId: string,
    options: {
      modelDeployment?: string;
      language?: string;
      forceRetranscribe?: boolean;
    } = {}
  ) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/transcriptions/voice/${voiceAttachmentId}`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify({
          model_deployment: options.modelDeployment || 'whisper',
          language: options.language,
          force_retranscribe: options.forceRetranscribe || false
        })
      }
    );

    if (!response.ok) {
      throw new Error(`Transcription failed: ${response.statusText}`);
    }

    return response.json();
  }

  async listTranscriptions(params: {
    search?: string;
    status?: string;
    limit?: number;
    offset?: number;
  } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.set(key, value.toString());
      }
    });

    const response = await fetch(
      `${this.baseUrl}/api/v1/transcriptions?${searchParams}`,
      { headers: this.headers }
    );

    if (!response.ok) {
      throw new Error(`Failed to list transcriptions: ${response.statusText}`);
    }

    return response.json();
  }
}

// Usage example
const client = new TranscriptionAPI(
  'https://your-api-domain.com',
  'your-access-token'
);

client.transcribeVoiceAttachment('voice-attachment-id')
  .then(result => console.log('Transcription:', result.transcript_text))
  .catch(error => console.error('Error:', error));
```

This comprehensive API documentation provides all the information needed to integrate with the Azure AI Foundry transcription system, including detailed request/response formats, error handling, and practical code examples.