"""
Integration tests for ExcelSync API endpoints.

Tests all Excel synchronization endpoints including:
- POST /excel-sync/sync-month - Sync transcriptions for a month
- POST /excel-sync/sync/{transcription_id} - Sync specific transcription
- POST /excel-sync/batch - Batch sync multiple transcriptions
- GET /excel-sync/health - Health check for Excel sync service
- GET /excel-sync/statistics - Get Excel sync statistics
- GET /excel-sync/history - Get Excel sync history
- GET /excel-sync/files - List Excel files
- GET /excel-sync/worksheets/{file_id} - Get worksheets from file
- POST /excel-sync/create-worksheet - Create new worksheet
- DELETE /excel-sync/worksheet/{file_id}/{worksheet_id} - Delete worksheet
"""

import pytest
import httpx
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from tests.integration.utils import (
    IntegrationAPIClient,
    ResponseAssertions,
    DatabaseAssertions,
    TestWorkflows
)

class TestExcelSyncEndpoints:
    """Integration tests for Excel sync endpoints."""

    @pytest.fixture
    async def api_client(self, async_client):
        """Create API client for Excel sync operations."""
        return IntegrationAPIClient(async_client)

    @pytest.fixture
    async def db_assertions(self, test_db):
        """Create database assertions helper."""
        return DatabaseAssertions(test_db)

    @pytest.fixture
    def mock_excel_sync_result(self):
        """Mock Excel sync result data."""
        return {
            "status": "completed",
            "file_info": {
                "name": "Voice Transcriptions 2024",
                "file_id": "file_12345",
                "web_url": "https://example.sharepoint.com/file.xlsx",
                "created_at": "2024-08-01T00:00:00Z",
                "modified_at": "2024-08-28T10:00:00Z"
            },
            "worksheet_name": "August 2024",
            "rows_processed": 25,
            "rows_updated": 5,
            "rows_created": 20,
            "errors": [],
            "processing_time_ms": 3250,
            "started_at": "2024-08-28T10:00:00Z",
            "completed_at": "2024-08-28T10:00:03.250Z"
        }

    @pytest.fixture
    def mock_batch_sync_result(self):
        """Mock batch Excel sync result."""
        return {
            "month_year": "August 2024",
            "total_transcriptions": 50,
            "synced_transcriptions": 45,
            "skipped_transcriptions": 5,
            "sync_results": [
                {
                    "status": "completed",
                    "worksheet_name": "August 2024",
                    "rows_created": 45,
                    "errors": []
                }
            ],
            "overall_status": "completed",
            "errors": ["5 transcriptions skipped due to missing data"],
            "started_at": "2024-08-28T10:00:00Z",
            "completed_at": "2024-08-28T10:05:30Z"
        }

    @pytest.fixture
    def mock_excel_files(self):
        """Mock Excel files list."""
        return [
            {
                "name": "Voice Transcriptions 2024",
                "file_id": "file_12345",
                "drive_id": "drive_abc",
                "web_url": "https://example.sharepoint.com/file1.xlsx",
                "created_at": "2024-01-01T00:00:00Z",
                "modified_at": "2024-08-28T10:00:00Z",
                "size_bytes": 2048576,
                "worksheets": [
                    {"name": "January 2024", "row_count": 30},
                    {"name": "February 2024", "row_count": 25}
                ]
            },
            {
                "name": "Archive Transcriptions 2023",
                "file_id": "file_67890", 
                "drive_id": "drive_abc",
                "web_url": "https://example.sharepoint.com/file2.xlsx",
                "created_at": "2023-01-01T00:00:00Z",
                "modified_at": "2023-12-31T23:59:59Z",
                "size_bytes": 15728640,
                "worksheets": [
                    {"name": "December 2023", "row_count": 45}
                ]
            }
        ]

    @pytest.fixture
    def mock_sync_history(self):
        """Mock Excel sync history."""
        return [
            {
                "id": "sync_1",
                "worksheet_name": "August 2024",
                "status": "completed",
                "transcriptions_synced": 25,
                "started_at": "2024-08-28T09:00:00Z",
                "completed_at": "2024-08-28T09:05:00Z",
                "created_by": "user@example.com"
            },
            {
                "id": "sync_2",
                "worksheet_name": "July 2024",
                "status": "completed", 
                "transcriptions_synced": 30,
                "started_at": "2024-07-31T10:00:00Z",
                "completed_at": "2024-07-31T10:08:00Z",
                "created_by": "user@example.com"
            }
        ]

    # =====================================================================
    # POST /excel-sync/sync-month - Sync transcriptions for a month
    # =====================================================================

    async def test_sync_month_success(self, api_client, mock_batch_sync_result, authenticated_user):
        """Test syncing transcriptions for a specific month."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_month') as mock_service:
            mock_service.return_value = mock_batch_sync_result
            
            request_data = {
                "month_year": "August 2024",
                "force_full_sync": False,
                "max_batch_size": 100
            }
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/sync-month",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["month_year"] == "August 2024"
            assert data["total_transcriptions"] == 50
            assert data["synced_transcriptions"] == 45
            assert data["overall_status"] == "completed"
            assert len(data["sync_results"]) == 1

    async def test_sync_month_invalid_format(self, api_client, authenticated_user):
        """Test syncing month with invalid month/year format."""
        request_data = {
            "month_year": "invalid-format",
            "force_full_sync": False
        }
        
        response = await api_client.client.post(
            "/api/v1/excel-sync/sync-month",
            json=request_data,
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code in [400, 422]

    async def test_sync_month_unauthenticated(self, api_client):
        """Test syncing month without authentication."""
        response = await api_client.client.post(
            "/api/v1/excel-sync/sync-month",
            json={"month_year": "August 2024"}
        )
        ResponseAssertions.assert_authentication_error(response)

    # =====================================================================
    # POST /excel-sync/sync/{transcription_id} - Sync specific transcription
    # =====================================================================

    async def test_sync_transcription_success(self, api_client, mock_excel_sync_result, authenticated_user):
        """Test syncing specific transcription to Excel."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_transcription') as mock_service:
            mock_service.return_value = mock_excel_sync_result
            
            request_data = {
                "worksheet_name": "August 2024",
                "force_update": False,
                "apply_formatting": True
            }
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/sync/trans_12345",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "completed"
            assert data["worksheet_name"] == "August 2024"
            assert data["rows_processed"] == 25
            assert data["rows_created"] == 20

    async def test_sync_transcription_not_found(self, api_client, authenticated_user):
        """Test syncing non-existent transcription."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_transcription') as mock_service:
            mock_service.side_effect = Exception("Transcription not found")
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/sync/invalid_id",
                json={"worksheet_name": "August 2024"},
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    async def test_sync_transcription_with_force_update(self, api_client, mock_excel_sync_result, authenticated_user):
        """Test syncing transcription with force update enabled."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_transcription') as mock_service:
            # Mock showing rows updated instead of created
            updated_result = mock_excel_sync_result.copy()
            updated_result["rows_updated"] = 15
            updated_result["rows_created"] = 0
            mock_service.return_value = updated_result
            
            request_data = {
                "worksheet_name": "August 2024",
                "force_update": True,
                "apply_formatting": True
            }
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/sync/trans_12345",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["rows_updated"] == 15
            assert data["rows_created"] == 0

    # =====================================================================
    # POST /excel-sync/batch - Batch sync multiple transcriptions
    # =====================================================================

    async def test_batch_sync_success(self, api_client, mock_batch_sync_result, authenticated_user):
        """Test batch syncing multiple transcriptions."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.batch_sync') as mock_service:
            mock_service.return_value = mock_batch_sync_result
            
            request_data = {
                "transcription_ids": ["trans_1", "trans_2", "trans_3"],
                "worksheet_name": "August 2024",
                "create_worksheet": True,
                "apply_formatting": True
            }
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/batch",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["overall_status"] == "completed"
            assert data["synced_transcriptions"] == 45
            assert len(data["sync_results"]) == 1

    async def test_batch_sync_empty_list(self, api_client, authenticated_user):
        """Test batch sync with empty transcription list."""
        request_data = {
            "transcription_ids": [],
            "worksheet_name": "August 2024"
        }
        
        response = await api_client.client.post(
            "/api/v1/excel-sync/batch",
            json=request_data,
            headers=authenticated_user["headers"]
        )
        
        ResponseAssertions.assert_validation_error(response)

    async def test_batch_sync_large_batch(self, api_client, authenticated_user):
        """Test batch sync with large batch size."""
        large_transcription_list = [f"trans_{i}" for i in range(201)]  # Over limit
        
        request_data = {
            "transcription_ids": large_transcription_list,
            "worksheet_name": "August 2024"
        }
        
        response = await api_client.client.post(
            "/api/v1/excel-sync/batch",
            json=request_data,
            headers=authenticated_user["headers"]
        )
        
        assert response.status_code in [400, 422]  # Should validate batch size

    # =====================================================================
    # GET /excel-sync/health - Health check for Excel sync service
    # =====================================================================

    async def test_excel_sync_health_check_healthy(self, api_client, authenticated_user):
        """Test Excel sync service health check when healthy."""
        mock_health = {
            "service_status": "healthy",
            "onedrive_accessible": True,
            "file_permissions": True,
            "last_sync_time": "2024-08-28T09:55:00Z",
            "error_message": None,
            "checked_at": "2024-08-28T10:00:00Z"
        }
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.health_check') as mock_service:
            mock_service.return_value = mock_health
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/health",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["service_status"] == "healthy"
            assert data["onedrive_accessible"] is True
            assert data["file_permissions"] is True

    async def test_excel_sync_health_check_unhealthy(self, api_client, authenticated_user):
        """Test Excel sync service health check when unhealthy."""
        mock_health = {
            "service_status": "unhealthy",
            "onedrive_accessible": False,
            "file_permissions": False,
            "last_sync_time": "2024-08-27T10:00:00Z",
            "error_message": "Unable to access OneDrive. Check authentication.",
            "checked_at": "2024-08-28T10:00:00Z"
        }
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.health_check') as mock_service:
            mock_service.return_value = mock_health
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/health",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["service_status"] == "unhealthy"
            assert data["onedrive_accessible"] is False
            assert "error_message" in data

    # =====================================================================
    # GET /excel-sync/statistics - Get Excel sync statistics
    # =====================================================================

    async def test_get_excel_sync_statistics_success(self, api_client, authenticated_user):
        """Test getting Excel sync statistics."""
        mock_stats = {
            "total_syncs": 150,
            "successful_syncs": 142,
            "failed_syncs": 8,
            "total_transcriptions_synced": 3750,
            "average_sync_time_ms": 4250,
            "most_active_worksheet": "August 2024",
            "syncs_by_status": {
                "completed": 142,
                "failed": 8
            },
            "syncs_by_month": [
                {"month": "2024-08", "count": 45},
                {"month": "2024-07", "count": 52}
            ],
            "average_transcriptions_per_sync": 25.0
        }
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.get_statistics') as mock_service:
            mock_service.return_value = mock_stats
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/statistics",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["total_syncs"] == 150
            assert data["successful_syncs"] == 142
            assert data["most_active_worksheet"] == "August 2024"
            assert "syncs_by_month" in data

    # =====================================================================
    # GET /excel-sync/history - Get Excel sync history
    # =====================================================================

    async def test_get_excel_sync_history_success(self, api_client, mock_sync_history, authenticated_user):
        """Test getting Excel sync history."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.get_sync_history') as mock_service:
            mock_service.return_value = mock_sync_history
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/history",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 2
            assert data[0]["id"] == "sync_1"
            assert data[0]["status"] == "completed"
            assert data[1]["worksheet_name"] == "July 2024"

    async def test_get_excel_sync_history_with_filters(self, api_client, mock_sync_history, authenticated_user):
        """Test getting Excel sync history with filters."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.get_sync_history') as mock_service:
            # Return filtered results
            mock_service.return_value = [mock_sync_history[0]]
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/history",
                params={
                    "status": "completed",
                    "limit": 10,
                    "offset": 0
                },
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 1
            assert data[0]["status"] == "completed"

    # =====================================================================
    # GET /excel-sync/files - List Excel files
    # =====================================================================

    async def test_list_excel_files_success(self, api_client, mock_excel_files, authenticated_user):
        """Test listing Excel files."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.list_excel_files') as mock_service:
            mock_service.return_value = mock_excel_files
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/files",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 2
            assert data[0]["name"] == "Voice Transcriptions 2024"
            assert data[0]["file_id"] == "file_12345"
            assert len(data[0]["worksheets"]) == 2

    async def test_list_excel_files_with_search(self, api_client, mock_excel_files, authenticated_user):
        """Test listing Excel files with search filter."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.list_excel_files') as mock_service:
            # Return filtered results
            mock_service.return_value = [mock_excel_files[0]]
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/files",
                params={"search": "2024"},
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 1
            assert "2024" in data[0]["name"]

    # =====================================================================
    # GET /excel-sync/worksheets/{file_id} - Get worksheets from file
    # =====================================================================

    async def test_get_worksheets_success(self, api_client, authenticated_user):
        """Test getting worksheets from Excel file."""
        mock_worksheets = [
            {
                "name": "January 2024",
                "id": "worksheet_1",
                "created_at": "2024-01-01T00:00:00Z",
                "last_updated": "2024-01-31T23:59:59Z",
                "row_count": 30,
                "has_header": True
            },
            {
                "name": "February 2024",
                "id": "worksheet_2",
                "created_at": "2024-02-01T00:00:00Z", 
                "last_updated": "2024-02-29T23:59:59Z",
                "row_count": 25,
                "has_header": True
            }
        ]
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.get_worksheets') as mock_service:
            mock_service.return_value = mock_worksheets
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/worksheets/file_12345",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert len(data) == 2
            assert data[0]["name"] == "January 2024"
            assert data[0]["row_count"] == 30
            assert data[1]["name"] == "February 2024"

    async def test_get_worksheets_file_not_found(self, api_client, authenticated_user):
        """Test getting worksheets from non-existent file."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.get_worksheets') as mock_service:
            mock_service.side_effect = Exception("File not found")
            
            response = await api_client.client.get(
                "/api/v1/excel-sync/worksheets/invalid_file_id",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    # =====================================================================
    # POST /excel-sync/create-worksheet - Create new worksheet
    # =====================================================================

    async def test_create_worksheet_success(self, api_client, authenticated_user):
        """Test creating new worksheet in Excel file."""
        mock_result = {
            "status": "created",
            "worksheet": {
                "name": "September 2024",
                "id": "worksheet_new",
                "created_at": "2024-08-28T10:00:00Z",
                "has_header": True,
                "row_count": 0
            },
            "file_info": {
                "name": "Voice Transcriptions 2024",
                "file_id": "file_12345"
            }
        }
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.create_worksheet') as mock_service:
            mock_service.return_value = mock_result
            
            request_data = {
                "worksheet_name": "September 2024",
                "file_id": "file_12345",
                "apply_formatting": True,
                "create_header": True
            }
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/create-worksheet",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "created"
            assert data["worksheet"]["name"] == "September 2024"
            assert data["worksheet"]["has_header"] is True

    async def test_create_worksheet_duplicate_name(self, api_client, authenticated_user):
        """Test creating worksheet with duplicate name."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.create_worksheet') as mock_service:
            mock_service.side_effect = Exception("Worksheet name already exists")
            
            request_data = {
                "worksheet_name": "August 2024",  # Existing name
                "file_id": "file_12345"
            }
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/create-worksheet",
                json=request_data,
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [400, 409, 500]

    # =====================================================================
    # DELETE /excel-sync/worksheet/{file_id}/{worksheet_id} - Delete worksheet
    # =====================================================================

    async def test_delete_worksheet_success(self, api_client, authenticated_user):
        """Test deleting worksheet from Excel file."""
        mock_result = {
            "status": "deleted",
            "worksheet_id": "worksheet_old",
            "worksheet_name": "Old Transcriptions",
            "deleted_at": "2024-08-28T10:00:00Z"
        }
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.delete_worksheet') as mock_service:
            mock_service.return_value = mock_result
            
            response = await api_client.client.delete(
                "/api/v1/excel-sync/worksheet/file_12345/worksheet_old",
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["status"] == "deleted"
            assert data["worksheet_id"] == "worksheet_old"
            assert data["worksheet_name"] == "Old Transcriptions"

    async def test_delete_worksheet_not_found(self, api_client, authenticated_user):
        """Test deleting non-existent worksheet."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.delete_worksheet') as mock_service:
            mock_service.side_effect = Exception("Worksheet not found")
            
            response = await api_client.client.delete(
                "/api/v1/excel-sync/worksheet/file_12345/invalid_worksheet",
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [404, 500]

    # =====================================================================
    # Error Handling Tests
    # =====================================================================

    async def test_onedrive_service_unavailable(self, api_client, authenticated_user):
        """Test handling OneDrive service unavailable errors."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_month') as mock_service:
            mock_service.side_effect = Exception("OneDrive service temporarily unavailable")
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/sync-month",
                json={"month_year": "August 2024"},
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code == 500

    async def test_excel_file_permissions_error(self, api_client, authenticated_user):
        """Test handling Excel file permission errors."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_transcription') as mock_service:
            mock_service.side_effect = Exception("Insufficient permissions to modify Excel file")
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/sync/trans_12345",
                json={"worksheet_name": "August 2024"},
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [403, 500]

    async def test_excel_file_locked_error(self, api_client, authenticated_user):
        """Test handling Excel file locked by another user."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.batch_sync') as mock_service:
            mock_service.side_effect = Exception("Excel file is currently locked by another user")
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/batch",
                json={
                    "transcription_ids": ["trans_1", "trans_2"],
                    "worksheet_name": "August 2024"
                },
                headers=authenticated_user["headers"]
            )
            
            assert response.status_code in [423, 500]

    async def test_large_excel_file_handling(self, api_client, authenticated_user):
        """Test handling large Excel files with many rows."""
        mock_result = {
            "status": "completed",
            "worksheet_name": "Large Dataset",
            "rows_processed": 10000,
            "rows_created": 10000,
            "processing_time_ms": 45000,  # 45 seconds
            "warnings": ["Large file processing took longer than usual"]
        }
        
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.batch_sync') as mock_service:
            mock_service.return_value = mock_result
            
            # Large batch of transcriptions
            large_batch = [f"trans_{i}" for i in range(100)]
            
            response = await api_client.client.post(
                "/api/v1/excel-sync/batch",
                json={
                    "transcription_ids": large_batch,
                    "worksheet_name": "Large Dataset"
                },
                headers=authenticated_user["headers"]
            )
            
            ResponseAssertions.assert_success_response(response)
            data = response.json()
            
            assert data["rows_processed"] == 10000
            assert data["processing_time_ms"] == 45000

    async def test_concurrent_sync_operations(self, api_client, mock_excel_sync_result, authenticated_user):
        """Test handling multiple concurrent sync operations."""
        with patch('app.services.ExcelTranscriptionSyncService.ExcelTranscriptionSyncService.sync_transcription') as mock_service:
            mock_service.return_value = mock_excel_sync_result
            
            # Send multiple concurrent sync requests
            tasks = []
            for i in range(3):
                task = api_client.client.post(
                    f"/api/v1/excel-sync/sync/trans_{i}",
                    json={"worksheet_name": f"Test Worksheet {i}"},
                    headers=authenticated_user["headers"]
                )
                tasks.append(task)
            
            # All should complete successfully (service should handle concurrency)
            import asyncio
            responses = await asyncio.gather(*tasks)
            
            for response in responses:
                assert response.status_code in [200, 202]  # Either completed or accepted for processing