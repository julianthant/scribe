"""
test_ExcelTranscriptionSyncService.py - Unit Tests for Excel Transcription Sync Service

Tests for the ExcelTranscriptionSyncService class covering:
- Single transcription sync to Excel
- Monthly batch sync operations
- Error handling and retry logic
- Excel file and worksheet management
- Integration with Azure OneDrive service

Uses pytest with async support and mock Azure Graph API responses.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.services.ExcelTranscriptionSyncService import ExcelTranscriptionSyncService
from app.models.ExcelSync import ExcelSyncStatus, ExcelSyncResult, ExcelBatchSyncResult
from app.db.models.Transcription import VoiceTranscription
from app.db.models.VoiceAttachment import VoiceAttachment
from app.core.Exceptions import ValidationError, AuthenticationError


@pytest.fixture
def mock_transcription_repository():
    """Mock transcription repository."""
    return AsyncMock()


@pytest.fixture
def mock_excel_sync_repository():
    """Mock Excel sync repository."""
    return AsyncMock()


@pytest.fixture
def excel_sync_service(mock_transcription_repository, mock_excel_sync_repository):
    """ExcelTranscriptionSyncService instance with mocked dependencies."""
    return ExcelTranscriptionSyncService(
        transcription_repository=mock_transcription_repository,
        excel_sync_repository=mock_excel_sync_repository
    )


@pytest.fixture
def sample_transcription():
    """Sample VoiceTranscription for testing."""
    voice_attachment = Mock(spec=VoiceAttachment)
    voice_attachment.sender_name = "John Doe"
    voice_attachment.sender_email = "john.doe@example.com"
    voice_attachment.subject = "Test Voice Message"
    
    transcription = Mock(spec=VoiceTranscription)
    transcription.id = "trans-123"
    transcription.transcript_text = "This is a test transcription."
    transcription.confidence_score = 0.95
    transcription.language = "en"
    transcription.model_name = "whisper-1"
    transcription.audio_duration_seconds = 30.5
    transcription.processing_time_ms = 2500
    transcription.created_at = datetime.utcnow()
    transcription.voice_attachment = voice_attachment
    
    return transcription


class TestExcelTranscriptionSyncService:
    """Test cases for ExcelTranscriptionSyncService."""

    @pytest.mark.asyncio
    async def test_sync_transcription_to_excel_success(
        self,
        excel_sync_service,
        mock_transcription_repository,
        mock_excel_sync_repository,
        sample_transcription
    ):
        """Test successful single transcription sync to Excel."""
        # Arrange
        user_id = "user-123"
        transcription_id = "trans-123"
        access_token = "test-token"
        
        mock_transcription_repository.get_transcription.return_value = sample_transcription
        
        # Mock Excel file tracking
        mock_excel_file = Mock()
        mock_excel_file.id = "excel-file-123"
        mock_excel_file.onedrive_file_id = "onedrive-123"
        mock_excel_sync_repository.get_excel_file_by_user_and_name.return_value = mock_excel_file
        
        # Mock sync operation
        mock_sync_operation = Mock()
        mock_sync_operation.id = "sync-op-123"
        mock_excel_sync_repository.create_sync_operation.return_value = mock_sync_operation
        mock_excel_sync_repository.update_sync_operation_status.return_value = True
        mock_excel_sync_repository.increment_sync_stats.return_value = True
        
        # Mock OneDrive service
        with patch('app.services.ExcelTranscriptionSyncService.azure_onedrive_service') as mock_onedrive:
            mock_onedrive.get_or_create_worksheet.return_value = {"name": "December 2024", "id": "ws-123"}
            mock_onedrive.get_worksheet_data.return_value = [["ID", "Date", "Text"]]  # Header row only
            mock_onedrive.write_transcription_data.return_value = {
                "rows_written": 1,
                "range_address": "A2:K2"
            }
            mock_onedrive.format_worksheet.return_value = {"header_formatted": True}
            
            # Act
            result = await excel_sync_service.sync_transcription_to_excel(
                user_id=user_id,
                transcription_id=transcription_id,
                access_token=access_token
            )
            
            # Assert
            assert result.status == ExcelSyncStatus.COMPLETED
            assert result.rows_processed == 1
            assert result.rows_created == 1
            assert "December 2024" in result.worksheet_name
            assert len(result.errors) == 0
            
            # Verify repository calls
            mock_transcription_repository.get_transcription.assert_called_once_with(transcription_id, user_id)
            mock_excel_sync_repository.create_sync_operation.assert_called_once()
            mock_excel_sync_repository.update_sync_operation_status.assert_called()
            mock_excel_sync_repository.increment_sync_stats.assert_called_with(mock_excel_file.id, success=True)

    @pytest.mark.asyncio
    async def test_sync_transcription_to_excel_not_found(
        self,
        excel_sync_service,
        mock_transcription_repository
    ):
        """Test sync when transcription is not found."""
        # Arrange
        user_id = "user-123"
        transcription_id = "nonexistent-trans"
        access_token = "test-token"
        
        mock_transcription_repository.get_transcription.return_value = None
        
        # Act
        result = await excel_sync_service.sync_transcription_to_excel(
            user_id=user_id,
            transcription_id=transcription_id,
            access_token=access_token
        )
        
        # Assert
        assert result.status == ExcelSyncStatus.FAILED
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    @pytest.mark.asyncio
    async def test_sync_transcription_disabled(self, mock_transcription_repository, mock_excel_sync_repository):
        """Test sync when Excel sync is disabled."""
        # Arrange
        with patch('app.services.ExcelTranscriptionSyncService.settings') as mock_settings:
            mock_settings.excel_sync_enabled = False
            
            service = ExcelTranscriptionSyncService(
                transcription_repository=mock_transcription_repository,
                excel_sync_repository=mock_excel_sync_repository
            )
            
            # Act
            result = await service.sync_transcription_to_excel(
                user_id="user-123",
                transcription_id="trans-123",
                access_token="test-token"
            )
            
            # Assert
            assert result.status == ExcelSyncStatus.COMPLETED
            assert "Excel sync is disabled" in result.errors

    @pytest.mark.asyncio
    async def test_sync_month_transcriptions_success(
        self,
        excel_sync_service,
        mock_transcription_repository,
        mock_excel_sync_repository,
        sample_transcription
    ):
        """Test successful monthly batch sync."""
        # Arrange
        user_id = "user-123"
        month_year = "December 2024"
        access_token = "test-token"
        
        mock_transcription_repository.get_transcriptions_by_date_range.return_value = [sample_transcription]
        
        # Mock Excel file tracking
        mock_excel_file = Mock()
        mock_excel_file.id = "excel-file-123"
        mock_excel_file.onedrive_file_id = "onedrive-123"
        mock_excel_sync_repository.get_excel_file_by_user_and_name.return_value = mock_excel_file
        
        # Mock sync operation
        mock_sync_operation = Mock()
        mock_sync_operation.id = "batch-sync-op-123"
        mock_excel_sync_repository.create_sync_operation.return_value = mock_sync_operation
        mock_excel_sync_repository.update_sync_operation_status.return_value = True
        mock_excel_sync_repository.increment_sync_stats.return_value = True
        
        # Mock OneDrive service
        with patch('app.services.ExcelTranscriptionSyncService.azure_onedrive_service') as mock_onedrive:
            mock_onedrive.get_or_create_worksheet.return_value = {"name": month_year, "id": "ws-123"}
            mock_onedrive.get_worksheet_data.return_value = [["ID", "Date", "Text"]]  # Header row only
            mock_onedrive.write_transcription_data.return_value = {
                "rows_written": 1,
                "range_address": "A2:K2"
            }
            mock_onedrive.format_worksheet.return_value = {"header_formatted": True}
            
            # Act
            result = await excel_sync_service.sync_month_transcriptions(
                user_id=user_id,
                month_year=month_year,
                access_token=access_token
            )
            
            # Assert
            assert result.overall_status == ExcelSyncStatus.COMPLETED
            assert result.total_transcriptions == 1
            assert result.synced_transcriptions == 1
            assert result.month_year == month_year
            assert len(result.errors) == 0
            
            # Verify repository calls
            mock_transcription_repository.get_transcriptions_by_date_range.assert_called_once()
            mock_excel_sync_repository.create_sync_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_month_transcriptions_no_data(
        self,
        excel_sync_service,
        mock_transcription_repository
    ):
        """Test monthly sync when no transcriptions found."""
        # Arrange
        user_id = "user-123"
        month_year = "December 2024"
        access_token = "test-token"
        
        mock_transcription_repository.get_transcriptions_by_date_range.return_value = []
        
        # Act
        result = await excel_sync_service.sync_month_transcriptions(
            user_id=user_id,
            month_year=month_year,
            access_token=access_token
        )
        
        # Assert
        assert result.overall_status == ExcelSyncStatus.COMPLETED
        assert result.total_transcriptions == 0
        assert result.synced_transcriptions == 0

    @pytest.mark.asyncio
    async def test_health_check_success(
        self,
        excel_sync_service,
        mock_excel_sync_repository
    ):
        """Test successful health check."""
        # Arrange
        user_id = "user-123"
        access_token = "test-token"
        
        # Mock Excel files
        mock_excel_file = Mock()
        mock_excel_file.last_sync_at = datetime.utcnow()
        mock_excel_sync_repository.get_user_excel_files.return_value = [mock_excel_file]
        
        # Mock OneDrive service
        with patch('app.services.ExcelTranscriptionSyncService.azure_onedrive_service') as mock_onedrive:
            mock_onedrive.check_onedrive_access.return_value = {
                "accessible": True,
                "drive_id": "drive-123"
            }
            
            # Act
            result = await excel_sync_service.health_check(user_id, access_token)
            
            # Assert
            assert result["service_status"] == "healthy"
            assert result["excel_sync_enabled"] is True
            assert result["onedrive_accessible"] is True
            assert result["file_permissions"] is True
            assert result["last_sync_time"] is not None

    @pytest.mark.asyncio
    async def test_health_check_disabled(self, mock_transcription_repository, mock_excel_sync_repository):
        """Test health check when Excel sync is disabled."""
        # Arrange
        with patch('app.services.ExcelTranscriptionSyncService.settings') as mock_settings:
            mock_settings.excel_sync_enabled = False
            
            service = ExcelTranscriptionSyncService(
                transcription_repository=mock_transcription_repository,
                excel_sync_repository=mock_excel_sync_repository
            )
            
            # Act
            result = await service.health_check("user-123", "test-token")
            
            # Assert
            assert result["service_status"] == "disabled"
            assert result["excel_sync_enabled"] is False

    def test_get_worksheet_name(self, excel_sync_service):
        """Test worksheet name generation."""
        # Arrange
        test_date = datetime(2024, 12, 15, 10, 30, 0)
        
        # Act
        worksheet_name = excel_sync_service._get_worksheet_name(test_date)
        
        # Assert
        assert worksheet_name == "December 2024"

    def test_convert_transcription_to_row_data(self, excel_sync_service, sample_transcription):
        """Test transcription to Excel row data conversion."""
        # Act
        row_data = excel_sync_service._convert_transcription_to_row_data(sample_transcription)
        
        # Assert
        assert row_data.transcription_id == "trans-123"
        assert row_data.transcript_text == "This is a test transcription."
        assert row_data.confidence_score == 0.95
        assert row_data.language == "en"
        assert row_data.model_used == "whisper-1"
        assert row_data.sender_name == "John Doe"
        assert row_data.sender_email == "john.doe@example.com"
        assert row_data.subject == "Test Voice Message"
        assert row_data.audio_duration == 30.5
        assert row_data.processing_time_ms == 2500

    def test_parse_month_year_to_dates(self, excel_sync_service):
        """Test month/year string parsing to date range."""
        # Act
        start_date, end_date = excel_sync_service._parse_month_year_to_dates("December 2024")
        
        # Assert
        assert start_date.year == 2024
        assert start_date.month == 12
        assert start_date.day == 1
        assert start_date.hour == 0
        assert start_date.minute == 0
        assert start_date.second == 0
        
        assert end_date.year == 2024
        assert end_date.month == 12
        assert end_date.day == 31
        assert end_date.hour == 23
        assert end_date.minute == 59
        assert end_date.second == 59

    def test_parse_invalid_month_year(self, excel_sync_service):
        """Test parsing invalid month/year string."""
        # Act & Assert
        with pytest.raises(ValidationError):
            excel_sync_service._parse_month_year_to_dates("Invalid Date")