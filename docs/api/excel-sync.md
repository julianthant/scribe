# Excel Sync API

REST API endpoints for managing Excel transcription synchronization with OneDrive, providing manual sync capabilities and health monitoring.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Endpoints](#endpoints)
4. [Request/Response Models](#requestresponse-models)
5. [Error Handling](#error-handling)
6. [Examples](#examples)
7. [Integration Guide](#integration-guide)
8. [Reference](#reference)

## Overview

The Excel Sync API provides three main endpoints for managing transcription synchronization with Excel files in OneDrive:

- **Monthly Sync**: Sync all transcriptions for a specific month
- **Single Sync**: Sync individual transcriptions
- **Health Check**: Monitor service health and OneDrive connectivity

### API Endpoints Summary

| Endpoint | Method | Purpose | Auto-Sync |
|----------|--------|---------|-----------|
| `/transcriptions/excel/sync-month` | POST | Monthly batch sync | No |
| `/transcriptions/excel/sync/{transcription_id}` | POST | Single transcription sync | No |
| `/transcriptions/excel/health` | GET | Service health check | N/A |

### Automatic vs Manual Sync

```mermaid
graph TB
    subgraph "Automatic Flow"
        VT[Voice Transcription] --> AS[Auto Sync]
        AS --> EX1[Excel Updated]
    end
    
    subgraph "Manual Sync Flow"
        API[API Request] --> MS[Manual Sync]
        MS --> EX2[Excel Updated]
    end
    
    subgraph "Health Monitoring"
        HC[Health Check] --> OD[OneDrive Status]
        HC --> PS[Permission Status]
        HC --> SS[Sync Statistics]
    end
    
    style VT fill:#e1f5fe
    style API fill:#f3e5f5
    style HC fill:#e8f5e8
```

## Authentication

All Excel sync endpoints require user authentication via Bearer token.

### Required Scopes

The user's access token must include the following OAuth scopes:

```
Files.ReadWrite    # OneDrive file access
User.Read          # User profile access
```

### Authentication Header

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...
Content-Type: application/json
```

### Token Requirements

- **Valid Azure AD token** with appropriate scopes
- **Non-expired token** (typically 1 hour lifetime)
- **Proper permissions** to user's OneDrive

## Endpoints

### 1. Monthly Sync Endpoint

Sync all transcriptions for a specific month to Excel.

#### Request

```http
POST /api/v1/transcriptions/excel/sync-month
Content-Type: application/json
Authorization: Bearer {access_token}

{
    "month_year": "December 2024"  // Optional, defaults to current month
}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `month_year` | string | No | Month/year in format "December 2024" |

#### Response

```json
{
    "month_year": "December 2024",
    "status": "completed",
    "total_transcriptions": 25,
    "synced_transcriptions": 23,
    "skipped_transcriptions": 2,
    "errors": [],
    "completed_at": "2024-12-15T10:30:45.123Z"
}
```

#### Use Cases

- **Initial Setup**: First-time Excel file creation
- **Monthly Maintenance**: Ensure all transcriptions are synced
- **Data Recovery**: Restore missing Excel data from database

### 2. Single Transcription Sync

Sync a specific transcription to Excel.

#### Request

```http
POST /api/v1/transcriptions/excel/sync/{transcription_id}?force_update=false
Authorization: Bearer {access_token}
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `transcription_id` | string | Yes | UUID of transcription to sync |
| `force_update` | boolean | No | Force update if already exists (default: false) |

#### Response

```json
{
    "status": "completed",
    "worksheet_name": "December 2024",
    "rows_processed": 1,
    "rows_created": 1,
    "rows_updated": 0,
    "errors": [],
    "processing_time_ms": 1240,
    "completed_at": "2024-12-15T10:30:45.123Z"
}
```

#### Use Cases

- **Manual Retry**: Retry failed automatic sync
- **Force Update**: Update existing Excel entry
- **Selective Sync**: Sync specific transcriptions only

### 3. Health Check Endpoint

Monitor Excel sync service health and OneDrive connectivity.

#### Request

```http
GET /api/v1/transcriptions/excel/health
Authorization: Bearer {access_token}
```

#### Response

```json
{
    "service_status": "healthy",
    "excel_sync_enabled": true,
    "onedrive_accessible": true,
    "file_permissions": true,
    "last_sync_time": "2024-12-15T09:45:30.456Z",
    "error_message": null,
    "checked_at": "2024-12-15T10:30:45.123Z"
}
```

#### Health Status Values

| Status | Description | Action Required |
|--------|-------------|-----------------|
| `healthy` | All systems operational | None |
| `unhealthy` | Service issues detected | Check error_message |
| `disabled` | Excel sync is disabled | Enable in configuration |

## Request/Response Models

### Monthly Sync Request

```json
{
    "month_year": "December 2024",  // Optional: "Month YYYY" format
    "force_full_sync": false        // Optional: force re-sync all transcriptions
}
```

### Monthly Sync Response

```json
{
    "month_year": "December 2024",
    "total_transcriptions": 25,
    "synced_transcriptions": 23,
    "skipped_transcriptions": 2,
    "sync_results": [
        {
            "status": "completed",
            "worksheet_name": "December 2024",
            "rows_processed": 23,
            "rows_created": 21,
            "rows_updated": 2,
            "processing_time_ms": 8450
        }
    ],
    "overall_status": "completed",
    "errors": [],
    "started_at": "2024-12-15T10:30:00.000Z",
    "completed_at": "2024-12-15T10:30:45.123Z"
}
```

### Single Sync Response

```json
{
    "status": "completed",           // completed, failed, pending
    "worksheet_name": "December 2024",
    "rows_processed": 1,
    "rows_created": 1,               // New rows added
    "rows_updated": 0,               // Existing rows modified
    "errors": [],                    // Array of error messages
    "processing_time_ms": 1240,
    "completed_at": "2024-12-15T10:30:45.123Z"
}
```

### Health Check Response

```json
{
    "service_status": "healthy",     // healthy, unhealthy, disabled
    "excel_sync_enabled": true,
    "onedrive_accessible": true,
    "file_permissions": true,
    "last_sync_time": "2024-12-15T09:45:30.456Z",
    "error_message": null,           // Error details if unhealthy
    "checked_at": "2024-12-15T10:30:45.123Z"
}
```

## Error Handling

### Error Response Format

All endpoints return errors in a consistent format:

```json
{
    "error": "validation_error",
    "message": "Access token required for Excel sync. Please re-authenticate.",
    "error_code": "MISSING_ACCESS_TOKEN",
    "details": {
        "endpoint": "/transcriptions/excel/sync-month",
        "required_scopes": ["Files.ReadWrite"]
    },
    "timestamp": "2024-12-15T10:30:45.123Z"
}
```

### Common Error Scenarios

#### 1. Missing Access Token

```json
{
    "error": "authentication_required",
    "message": "Access token required for Excel sync. Please re-authenticate.",
    "status_code": 400
}
```

**Resolution**: Ensure proper authentication headers are included.

#### 2. Insufficient Permissions

```json
{
    "error": "authorization_error", 
    "message": "Insufficient permissions to access OneDrive",
    "status_code": 403
}
```

**Resolution**: Update OAuth scopes to include `Files.ReadWrite`.

#### 3. Service Unavailable

```json
{
    "error": "service_unavailable",
    "message": "Excel sync service not available",
    "status_code": 503
}
```

**Resolution**: Check service configuration and dependencies.

#### 4. OneDrive API Error

```json
{
    "error": "external_service_error",
    "message": "Failed to access OneDrive API",
    "details": {
        "service": "Microsoft Graph",
        "status_code": 429,
        "retry_after": "60"
    },
    "status_code": 502
}
```

**Resolution**: Wait for rate limit reset or implement retry logic.

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Operation completed successfully |
| 400 | Bad Request | Missing/invalid parameters |
| 401 | Unauthorized | Invalid or expired token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Transcription not found |
| 429 | Rate Limited | Too many requests |
| 500 | Server Error | Internal service error |
| 502 | Bad Gateway | OneDrive API error |
| 503 | Service Unavailable | Excel sync disabled |

## Examples

### Complete Monthly Sync Workflow

```javascript
// 1. Check service health first
const healthResponse = await fetch('/api/v1/transcriptions/excel/health', {
    headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
    }
});

const healthData = await healthResponse.json();

if (healthData.service_status !== 'healthy') {
    console.error('Excel sync service is not healthy:', healthData.error_message);
    return;
}

// 2. Trigger monthly sync
const syncResponse = await fetch('/api/v1/transcriptions/excel/sync-month', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        month_year: 'December 2024'
    })
});

const syncData = await syncResponse.json();

console.log(`Synced ${syncData.synced_transcriptions} of ${syncData.total_transcriptions} transcriptions`);

if (syncData.errors.length > 0) {
    console.warn('Sync completed with errors:', syncData.errors);
}
```

### Single Transcription Sync with Retry

```javascript
async function syncTranscriptionWithRetry(transcriptionId, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            const response = await fetch(`/api/v1/transcriptions/excel/sync/${transcriptionId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Sync successful:', result);
                return result;
            }

            if (response.status === 429) {
                // Rate limited, wait and retry
                const retryAfter = response.headers.get('Retry-After') || 60;
                console.log(`Rate limited, waiting ${retryAfter} seconds...`);
                await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
                continue;
            }

            throw new Error(`HTTP ${response.status}: ${response.statusText}`);

        } catch (error) {
            console.error(`Attempt ${attempt} failed:`, error);
            
            if (attempt === maxRetries) {
                throw new Error(`Sync failed after ${maxRetries} attempts: ${error.message}`);
            }

            // Exponential backoff
            const delay = Math.pow(2, attempt) * 1000;
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
}
```

### Python Integration Example

```python
import httpx
import asyncio
from typing import Optional

class ExcelSyncClient:
    """Client for Excel sync API operations."""
    
    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    async def sync_month(self, month_year: Optional[str] = None) -> dict:
        """Sync transcriptions for a specific month."""
        url = f"{self.base_url}/api/v1/transcriptions/excel/sync-month"
        
        payload = {}
        if month_year:
            payload["month_year"] = month_year
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def sync_transcription(
        self, 
        transcription_id: str, 
        force_update: bool = False
    ) -> dict:
        """Sync a single transcription."""
        url = f"{self.base_url}/api/v1/transcriptions/excel/sync/{transcription_id}"
        params = {"force_update": force_update}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
    
    async def health_check(self) -> dict:
        """Check Excel sync service health."""
        url = f"{self.base_url}/api/v1/transcriptions/excel/health"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

# Usage example
async def main():
    client = ExcelSyncClient(
        base_url="https://api.scribe.com",
        access_token="eyJ0eXAi..."
    )
    
    # Check health
    health = await client.health_check()
    print(f"Service status: {health['service_status']}")
    
    # Sync current month
    if health["service_status"] == "healthy":
        result = await client.sync_month()
        print(f"Synced {result['synced_transcriptions']} transcriptions")

# Run
asyncio.run(main())
```

## Integration Guide

### Frontend Integration

#### React Hook Example

```javascript
import { useState, useCallback } from 'react';
import { useAuth } from './AuthContext';

export function useExcelSync() {
    const { accessToken } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const syncMonth = useCallback(async (monthYear = null) => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch('/api/v1/transcriptions/excel/sync-month', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ month_year: monthYear })
            });

            if (!response.ok) {
                throw new Error(`Sync failed: ${response.statusText}`);
            }

            const result = await response.json();
            return result;

        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, [accessToken]);

    const checkHealth = useCallback(async () => {
        try {
            const response = await fetch('/api/v1/transcriptions/excel/health', {
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });

            return await response.json();
        } catch (err) {
            console.error('Health check failed:', err);
            return { service_status: 'unhealthy', error_message: err.message };
        }
    }, [accessToken]);

    return {
        syncMonth,
        checkHealth,
        isLoading,
        error
    };
}
```

#### Usage in Component

```javascript
import React, { useState } from 'react';
import { useExcelSync } from './useExcelSync';

export function ExcelSyncPanel() {
    const { syncMonth, checkHealth, isLoading, error } = useExcelSync();
    const [syncResult, setSyncResult] = useState(null);

    const handleSyncCurrentMonth = async () => {
        try {
            const result = await syncMonth();
            setSyncResult(result);
        } catch (err) {
            console.error('Sync failed:', err);
        }
    };

    return (
        <div className="excel-sync-panel">
            <h3>Excel Sync</h3>
            
            <button 
                onClick={handleSyncCurrentMonth} 
                disabled={isLoading}
                className="sync-button"
            >
                {isLoading ? 'Syncing...' : 'Sync Current Month'}
            </button>

            {error && (
                <div className="error-message">
                    Error: {error}
                </div>
            )}

            {syncResult && (
                <div className="sync-result">
                    <p>✅ Synced {syncResult.synced_transcriptions} transcriptions</p>
                    <p>📁 Worksheet: {syncResult.sync_results[0]?.worksheet_name}</p>
                </div>
            )}
        </div>
    );
}
```

### Backend Service Integration

```python
from app.dependencies.Transcription import get_transcription_service
from fastapi import Depends

@app.post("/custom/sync-all-users")
async def sync_all_users_excel(
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """Admin endpoint to sync Excel for all users."""
    
    # Get all users with transcriptions
    users_with_transcriptions = await get_users_with_recent_transcriptions()
    
    results = []
    for user in users_with_transcriptions:
        try:
            # Get user's access token (from session or refresh)
            access_token = await get_user_access_token(user.id)
            
            # Trigger monthly sync
            sync_result = await transcription_service.trigger_monthly_excel_sync(
                user_id=user.id,
                access_token=access_token
            )
            
            results.append({
                "user_id": user.id,
                "status": sync_result["status"],
                "transcriptions_synced": sync_result.get("synced_transcriptions", 0)
            })
            
        except Exception as e:
            logger.error(f"Failed to sync Excel for user {user.id}: {str(e)}")
            results.append({
                "user_id": user.id,
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "total_users": len(users_with_transcriptions),
        "successful_syncs": sum(1 for r in results if r["status"] == "completed"),
        "failed_syncs": sum(1 for r in results if r["status"] == "failed"),
        "results": results
    }
```

## Reference

### API Endpoint Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/transcriptions/excel/sync-month` | POST | Required | Monthly batch sync |
| `/transcriptions/excel/sync/{id}` | POST | Required | Single transcription sync |
| `/transcriptions/excel/health` | GET | Required | Service health check |

### Query Parameters

| Parameter | Endpoints | Type | Description |
|-----------|-----------|------|-------------|
| `force_update` | Single sync | boolean | Force update existing entries |

### Response Status Values

| Status | Description | Next Action |
|--------|-------------|-------------|
| `completed` | Operation successful | None |
| `failed` | Operation failed | Check errors array |
| `pending` | Operation in progress | Poll for completion |

### Rate Limiting

| Endpoint | Rate Limit | Window |
|----------|------------|--------|
| All Excel endpoints | 10 requests | 60 seconds |
| Health check | 60 requests | 60 seconds |

### Service Dependencies

| Dependency | Required For | Failure Impact |
|------------|--------------|----------------|
| **Azure AD** | Authentication | All operations fail |
| **OneDrive API** | Excel operations | Sync operations fail |
| **Database** | Tracking/stats | Limited functionality |

---

**Last Updated**: December 2024  
**API Version**: 1.0.0  
**Base URL**: `/api/v1/transcriptions/excel`  
**Authentication**: Bearer Token Required