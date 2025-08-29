"""
ExcelTranscriptionSyncService.py - Excel Transcription Synchronization Service

Orchestrates synchronization between voice transcriptions and Excel files in OneDrive.
This service handles:
- Single transcription sync to Excel
- Batch transcription sync for monthly worksheets
- Data consistency between database and Excel
- Error handling and retry logic
- Monthly worksheet creation and management
- Performance optimization with batch operations

The ExcelTranscriptionSyncService coordinates between Azure OneDrive service,
transcription repository, and Excel sync repository.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from calendar import month_name

from app.azure.AzureOneDriveService import azure_onedrive_service
from app.repositories.TranscriptionRepository import TranscriptionRepository
from app.repositories.ExcelSyncRepository import ExcelSyncRepository
from app.azure.AzureAuthService import azure_auth_service
from app.core.config import settings
from app.core.Exceptions import ValidationError, AuthenticationError, DatabaseError
from app.models.ExcelSync import (
    TranscriptionRowData, ExcelSyncRequest, ExcelSyncResult, ExcelSyncStatus,
    ExcelBatchSyncRequest, ExcelBatchSyncResult, ExcelFileInfo, ExcelWorksheetInfo
)
from app.db.models.Transcription import VoiceTranscription

logger = logging.getLogger(__name__)


class ExcelTranscriptionSyncService:
    """Service for synchronizing transcriptions with Excel files in OneDrive."""

    def __init__(
        self,
        transcription_repository: TranscriptionRepository,
        excel_sync_repository: ExcelSyncRepository
    ):
        """
        Initialize Excel sync service.
        
        Args:
            transcription_repository: Transcription repository instance
            excel_sync_repository: Excel sync repository instance
        """
        self.transcription_repository = transcription_repository
        self.excel_sync_repository = excel_sync_repository
        self.excel_sync_enabled = getattr(settings, 'excel_sync_enabled', True)
        self.excel_file_name = getattr(settings, 'excel_file_name', 'Transcripts')
        self.excel_auto_format = getattr(settings, 'excel_auto_format', True)
        self.excel_sync_batch_size = getattr(settings, 'excel_sync_batch_size', 100)
        self.worksheet_date_format = getattr(settings, 'excel_worksheet_date_format', '%B %Y')

    async def sync_transcription_to_excel(
        self,
        user_id: str,
        transcription_id: str,
        access_token: Optional[str] = None,
        force_update: bool = False
    ) -> ExcelSyncResult:
        """
        Sync a single transcription to Excel.
        
        Args:
            user_id: User ID
            transcription_id: Transcription ID to sync
            access_token: Optional access token (will be refreshed if needed)
            force_update: Whether to update if already exists
            
        Returns:
            ExcelSyncResult with sync status and details
            
        Raises:
            ValidationError: If validation fails
            AuthenticationError: If authentication fails
            DatabaseError: If database operation fails
        """
        if not self.excel_sync_enabled:
            logger.info("Excel sync is disabled")
            return ExcelSyncResult(
                status=ExcelSyncStatus.COMPLETED,
                file_info=None,
                worksheet_name="N/A",
                rows_processed=0,
                rows_updated=0,
                rows_created=0,
                errors=["Excel sync is disabled"],
                processing_time_ms=0,
                completed_at=datetime.utcnow()
            )

        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting Excel sync for transcription {transcription_id} by user {user_id}")

            # Get transcription data
            transcription = await self.transcription_repository.get_transcription_by_id(transcription_id, user_id)
            if not transcription:
                raise ValidationError(f"Transcription {transcription_id} not found")

            # Get or refresh access token
            if not access_token:
                # In a real implementation, you'd get this from the user's session or refresh token
                # For now, we'll need to pass it from the calling service
                raise ValidationError("Access token is required for Excel sync")

            # Get or create Excel file tracking
            excel_file = await self._get_or_create_excel_file_tracking(user_id, access_token)

            # Create sync operation record
            worksheet_name = self._get_worksheet_name(transcription.created_at)
            sync_operation = await self.excel_sync_repository.create_sync_operation(
                excel_file_id=excel_file.id,
                user_id=user_id,
                operation_type="single",
                worksheet_name=worksheet_name,
                transcription_id=transcription_id,
                force_update=force_update,
                apply_formatting=self.excel_auto_format
            )

            # Update operation status to in_progress
            await self.excel_sync_repository.update_sync_operation_status(
                sync_operation.id,
                "in_progress"
            )

            try:
                # Sync to Excel
                result = await self._sync_transcriptions_to_worksheet(
                    user_id=user_id,
                    access_token=access_token,
                    excel_file=excel_file,
                    transcriptions=[transcription],
                    worksheet_name=worksheet_name,
                    force_update=force_update
                )

                # Update operation status
                processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                await self.excel_sync_repository.update_sync_operation_status(
                    sync_operation.id,
                    "completed",
                    rows_processed=result.rows_processed,
                    rows_created=result.rows_created,
                    rows_updated=result.rows_updated,
                    processing_time_ms=processing_time_ms
                )

                # Update Excel file stats
                await self.excel_sync_repository.increment_sync_stats(excel_file.id, success=True)

                logger.info(f"Successfully synced transcription {transcription_id} to Excel")
                return result

            except Exception as sync_error:
                # Update operation status as failed
                await self.excel_sync_repository.update_sync_operation_status(
                    sync_operation.id,
                    "failed",
                    error_message=str(sync_error)
                )

                # Update Excel file stats
                await self.excel_sync_repository.increment_sync_stats(excel_file.id, success=False)

                # Create error record
                await self.excel_sync_repository.create_sync_error(
                    excel_file_id=excel_file.id,
                    user_id=user_id,
                    error_type="sync_error",
                    error_message=str(sync_error),
                    sync_operation_id=sync_operation.id,
                    operation_type="single",
                    worksheet_name=worksheet_name,
                    transcription_id=transcription_id
                )

                raise sync_error

        except Exception as e:
            logger.error(f"Error syncing transcription to Excel: {str(e)}")
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return ExcelSyncResult(
                status=ExcelSyncStatus.FAILED,
                file_info=None,
                worksheet_name=worksheet_name if 'worksheet_name' in locals() else "Unknown",
                rows_processed=0,
                rows_updated=0,
                rows_created=0,
                errors=[str(e)],
                processing_time_ms=processing_time_ms,
                completed_at=datetime.utcnow()
            )

    async def sync_month_transcriptions(
        self,
        user_id: str,
        month_year: str,
        access_token: str,
        force_full_sync: bool = False
    ) -> ExcelBatchSyncResult:
        """
        Sync all transcriptions for a specific month to Excel.
        
        Args:
            user_id: User ID
            month_year: Month and year string (e.g., "December 2024")
            access_token: Access token for OneDrive
            force_full_sync: Whether to sync all transcriptions for the month
            
        Returns:
            ExcelBatchSyncResult with batch sync status
        """
        if not self.excel_sync_enabled:
            logger.info("Excel sync is disabled")
            return ExcelBatchSyncResult(
                month_year=month_year,
                total_transcriptions=0,
                synced_transcriptions=0,
                skipped_transcriptions=0,
                overall_status=ExcelSyncStatus.COMPLETED,
                errors=["Excel sync is disabled"],
                completed_at=datetime.utcnow()
            )

        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting batch Excel sync for {month_year} by user {user_id}")

            # Parse month/year to get date range
            month_start, month_end = self._parse_month_year_to_dates(month_year)

            # Get transcriptions for the month
            transcriptions = await self.transcription_repository.get_transcriptions_by_date_range(
                user_id=user_id,
                start_date=month_start,
                end_date=month_end,
                limit=self.excel_sync_batch_size
            )

            if not transcriptions:
                logger.info(f"No transcriptions found for {month_year}")
                return ExcelBatchSyncResult(
                    month_year=month_year,
                    overall_status=ExcelSyncStatus.COMPLETED,
                    total_transcriptions=0,
                    synced_transcriptions=0,
                    skipped_transcriptions=0,
                    completed_at=datetime.utcnow()
                )

            # Get or create Excel file tracking
            excel_file = await self._get_or_create_excel_file_tracking(user_id, access_token)

            # Create batch sync operation
            sync_operation = await self.excel_sync_repository.create_sync_operation(
                excel_file_id=excel_file.id,
                user_id=user_id,
                operation_type="batch",
                worksheet_name=month_year,
                force_update=force_full_sync,
                apply_formatting=self.excel_auto_format
            )

            # Update operation status
            await self.excel_sync_repository.update_sync_operation_status(
                sync_operation.id,
                "in_progress"
            )

            try:
                # Sync all transcriptions to worksheet
                sync_result = await self._sync_transcriptions_to_worksheet(
                    user_id=user_id,
                    access_token=access_token,
                    excel_file=excel_file,
                    transcriptions=transcriptions,
                    worksheet_name=month_year,
                    force_update=force_full_sync
                )

                # Update operation status
                processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                await self.excel_sync_repository.update_sync_operation_status(
                    sync_operation.id,
                    "completed",
                    rows_processed=sync_result.rows_processed,
                    rows_created=sync_result.rows_created,
                    rows_updated=sync_result.rows_updated,
                    processing_time_ms=processing_time_ms
                )

                # Update Excel file stats
                await self.excel_sync_repository.increment_sync_stats(excel_file.id, success=True)

                return ExcelBatchSyncResult(
                    month_year=month_year,
                    total_transcriptions=len(transcriptions),
                    synced_transcriptions=sync_result.rows_processed,
                    skipped_transcriptions=0,
                    sync_results=[sync_result],
                    overall_status=ExcelSyncStatus.COMPLETED,
                    completed_at=datetime.utcnow()
                )

            except Exception as batch_error:
                # Update operation as failed
                await self.excel_sync_repository.update_sync_operation_status(
                    sync_operation.id,
                    "failed",
                    error_message=str(batch_error)
                )

                # Update Excel file stats
                await self.excel_sync_repository.increment_sync_stats(excel_file.id, success=False)

                # Create error record
                await self.excel_sync_repository.create_sync_error(
                    excel_file_id=excel_file.id,
                    user_id=user_id,
                    error_type="batch_sync_error",
                    error_message=str(batch_error),
                    sync_operation_id=sync_operation.id,
                    operation_type="batch",
                    worksheet_name=month_year
                )

                raise batch_error

        except Exception as e:
            logger.error(f"Error in batch Excel sync: {str(e)}")
            return ExcelBatchSyncResult(
                month_year=month_year,
                total_transcriptions=0,
                synced_transcriptions=0,
                skipped_transcriptions=0,
                overall_status=ExcelSyncStatus.FAILED,
                errors=[str(e)],
                completed_at=datetime.utcnow()
            )

    async def _get_or_create_excel_file_tracking(
        self,
        user_id: str,
        access_token: str
    ) -> Any:  # Returns ExcelFile model
        """
        Get or create Excel file tracking record.
        
        Args:
            user_id: User ID
            access_token: Access token for OneDrive
            
        Returns:
            ExcelFile tracking record
        """
        try:
            # Check if Excel file tracking exists
            excel_file = await self.excel_sync_repository.get_excel_file_by_user_and_name(
                user_id, self.excel_file_name
            )

            if excel_file:
                return excel_file

            # Get or create Excel file in OneDrive
            onedrive_file = await azure_onedrive_service.get_or_create_excel_file(
                access_token, self.excel_file_name
            )

            # Create tracking record
            excel_file = await self.excel_sync_repository.create_excel_file(
                user_id=user_id,
                file_name=self.excel_file_name,
                onedrive_file_id=onedrive_file["id"],
                onedrive_drive_id=onedrive_file.get("parentReference", {}).get("driveId"),
                web_url=onedrive_file.get("webUrl"),
                size_bytes=onedrive_file.get("size")
            )

            return excel_file

        except Exception as e:
            logger.error(f"Error getting/creating Excel file tracking: {str(e)}")
            raise

    async def _sync_transcriptions_to_worksheet(
        self,
        user_id: str,
        access_token: str,
        excel_file: Any,  # ExcelFile model
        transcriptions: List[VoiceTranscription],
        worksheet_name: str,
        force_update: bool = False
    ) -> ExcelSyncResult:
        """
        Sync transcriptions to specific worksheet.
        
        Args:
            user_id: User ID
            access_token: Access token
            excel_file: Excel file tracking record
            transcriptions: List of transcriptions to sync
            worksheet_name: Target worksheet name
            force_update: Whether to update existing rows
            
        Returns:
            ExcelSyncResult with sync details
        """
        try:
            # Get or create worksheet
            worksheet = await azure_onedrive_service.get_or_create_worksheet(
                access_token=access_token,
                file_id=excel_file.onedrive_file_id,
                worksheet_name=worksheet_name
            )

            # Check existing data in worksheet to avoid duplicates
            existing_data = []
            if not force_update:
                try:
                    existing_data = await azure_onedrive_service.get_worksheet_data(
                        access_token=access_token,
                        file_id=excel_file.onedrive_file_id,
                        worksheet_name=worksheet_name,
                        range_address="A:A"  # Get all IDs in column A
                    )
                    # Extract existing transcription IDs (skip header)
                    existing_ids = {row[0] for row in existing_data[1:] if row and len(row) > 0}
                except Exception:
                    # If worksheet is empty or doesn't exist yet, that's fine
                    existing_ids = set()
            else:
                existing_ids = set()

            # Filter out transcriptions that already exist (unless force_update)
            transcriptions_to_sync = []
            if force_update:
                transcriptions_to_sync = transcriptions
            else:
                transcriptions_to_sync = [
                    t for t in transcriptions 
                    if t.id not in existing_ids
                ]

            if not transcriptions_to_sync:
                logger.info(f"No new transcriptions to sync to worksheet {worksheet_name}")
                return ExcelSyncResult(
                    status=ExcelSyncStatus.COMPLETED,
                    file_info=None,
                    worksheet_name=worksheet_name,
                    rows_processed=0,
                    rows_created=0,
                    rows_updated=0,
                    errors=[],
                    processing_time_ms=0,
                    completed_at=datetime.utcnow()
                )

            # Convert transcriptions to Excel row data
            transcription_rows = []
            for transcription in transcriptions_to_sync:
                row_data = self._convert_transcription_to_row_data(transcription)
                transcription_rows.append(row_data)

            # Determine starting row (after header + existing data)
            start_row = len(existing_data) + 1 if existing_data else 2  # Start after header

            # Write data to Excel
            write_result = await azure_onedrive_service.write_transcription_data(
                access_token=access_token,
                file_id=excel_file.onedrive_file_id,
                worksheet_name=worksheet_name,
                transcriptions=transcription_rows,
                start_row=start_row
            )

            # Apply formatting if enabled and this is a new worksheet
            if self.excel_auto_format and len(existing_data) <= 1:  # New or empty worksheet
                await azure_onedrive_service.format_worksheet(
                    access_token=access_token,
                    file_id=excel_file.onedrive_file_id,
                    worksheet_name=worksheet_name
                )

            logger.info(f"Successfully synced {len(transcriptions_to_sync)} transcriptions to worksheet {worksheet_name}")

            return ExcelSyncResult(
                status=ExcelSyncStatus.COMPLETED,
                file_info=None,
                worksheet_name=worksheet_name,
                rows_processed=len(transcriptions_to_sync),
                rows_created=len(transcriptions_to_sync) if not force_update else 0,
                rows_updated=len(transcriptions_to_sync) if force_update else 0,
                errors=[],
                processing_time_ms=0,
                completed_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error syncing transcriptions to worksheet: {str(e)}")
            return ExcelSyncResult(
                status=ExcelSyncStatus.FAILED,
                file_info=None,
                worksheet_name=worksheet_name,
                rows_processed=0,
                rows_updated=0,
                rows_created=0,
                errors=[str(e)],
                processing_time_ms=0,
                completed_at=datetime.utcnow()
            )

    def _convert_transcription_to_row_data(self, transcription: VoiceTranscription) -> TranscriptionRowData:
        """
        Convert database transcription to Excel row data.
        
        Args:
            transcription: VoiceTranscription instance
            
        Returns:
            TranscriptionRowData for Excel
        """
        return TranscriptionRowData(
            transcription_id=transcription.id,
            date_time=transcription.created_at,
            sender_name=getattr(transcription.voice_attachment, 'sender_name', None) if hasattr(transcription, 'voice_attachment') else None,
            sender_email=getattr(transcription.voice_attachment, 'sender_email', '') if hasattr(transcription, 'voice_attachment') else '',
            subject=getattr(transcription.voice_attachment, 'subject', '') if hasattr(transcription, 'voice_attachment') else '',
            audio_duration=transcription.audio_duration_seconds,
            transcript_text=transcription.transcript_text,
            confidence_score=transcription.confidence_score,
            language=transcription.language,
            model_used=transcription.model_name,
            processing_time_ms=transcription.processing_time_ms
        )

    def _get_worksheet_name(self, date: datetime) -> str:
        """
        Generate worksheet name from date.
        
        Args:
            date: Date to generate worksheet name from
            
        Returns:
            Worksheet name (e.g., "December 2024")
        """
        return date.strftime(self.worksheet_date_format)

    def _parse_month_year_to_dates(self, month_year: str) -> Tuple[datetime, datetime]:
        """
        Parse month/year string to start and end dates.
        
        Args:
            month_year: Month year string (e.g., "December 2024")
            
        Returns:
            Tuple of (month_start, month_end) datetimes
        """
        try:
            # Parse "December 2024" format
            date = datetime.strptime(month_year, self.worksheet_date_format)
            
            # Get first day of month
            month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get last day of month
            if date.month == 12:
                next_month = month_start.replace(year=date.year + 1, month=1)
            else:
                next_month = month_start.replace(month=date.month + 1)
            
            month_end = next_month - timedelta(seconds=1)
            
            return month_start, month_end
            
        except ValueError as e:
            logger.error(f"Error parsing month/year string '{month_year}': {str(e)}")
            raise ValidationError(f"Invalid month/year format: {month_year}")

    async def health_check(self, user_id: str, access_token: str) -> Dict[str, Any]:
        """
        Check Excel sync service health.
        
        Args:
            user_id: User ID for testing
            access_token: Access token for OneDrive
            
        Returns:
            Health check result
        """
        try:
            health_result = {
                "service_status": "healthy",
                "excel_sync_enabled": self.excel_sync_enabled,
                "onedrive_accessible": False,
                "file_permissions": False,
                "last_sync_time": None,
                "error_message": None,
                "checked_at": datetime.utcnow().isoformat()
            }

            if not self.excel_sync_enabled:
                health_result["service_status"] = "disabled"
                return health_result

            # Check OneDrive access
            try:
                onedrive_check = await azure_onedrive_service.check_onedrive_access(access_token)
                health_result["onedrive_accessible"] = onedrive_check.get("accessible", False)
                
                if onedrive_check.get("accessible"):
                    health_result["file_permissions"] = True
                    
                    # Get last sync time from database
                    excel_files = await self.excel_sync_repository.get_user_excel_files(user_id)
                    if excel_files:
                        last_sync_times = [f.last_sync_at for f in excel_files if f.last_sync_at]
                        if last_sync_times:
                            health_result["last_sync_time"] = max(last_sync_times).isoformat()

            except Exception as e:
                health_result["service_status"] = "unhealthy"
                health_result["error_message"] = str(e)

            return health_result

        except Exception as e:
            logger.error(f"Error in Excel sync health check: {str(e)}")
            return {
                "service_status": "unhealthy",
                "error_message": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }