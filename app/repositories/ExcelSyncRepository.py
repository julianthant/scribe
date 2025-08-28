"""
ExcelSyncRepository.py - Excel Sync Tracking Data Access Repository

Provides data access layer for Excel sync tracking operations.
This repository handles:
- Excel file metadata CRUD operations
- Sync operation tracking and history
- Error logging and resolution
- Performance metrics and statistics
- Batch operations for sync management

The ExcelSyncRepository follows the repository pattern and provides
a clean interface between the business logic and database layers.
"""

from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.models.ExcelSyncTracking import ExcelFile, ExcelSyncOperation, ExcelSyncError
from app.core.Exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)


class ExcelSyncRepository:
    """Repository for Excel sync tracking data access."""

    def __init__(self, db_session: AsyncSession):
        """Initialize repository with database session."""
        self.db_session = db_session

    # Excel File Operations

    async def create_excel_file(
        self,
        user_id: str,
        file_name: str,
        onedrive_file_id: Optional[str] = None,
        onedrive_drive_id: Optional[str] = None,
        web_url: Optional[str] = None,
        size_bytes: Optional[int] = None
    ) -> ExcelFile:
        """
        Create a new Excel file record.
        
        Args:
            user_id: User ID who owns the file
            file_name: Excel file name (without extension)
            onedrive_file_id: OneDrive file ID
            onedrive_drive_id: OneDrive drive ID
            web_url: Web URL to the file
            size_bytes: File size in bytes
            
        Returns:
            Created ExcelFile instance
            
        Raises:
            ValidationError: If validation fails
            DatabaseError: If database operation fails
        """
        try:
            excel_file = ExcelFile(
                user_id=user_id,
                file_name=file_name,
                onedrive_file_id=onedrive_file_id,
                onedrive_drive_id=onedrive_drive_id,
                web_url=web_url,
                size_bytes=size_bytes,
                file_status="active"
            )
            
            self.db_session.add(excel_file)
            await self.db_session.commit()
            await self.db_session.refresh(excel_file)
            
            logger.info(f"Created Excel file record: {file_name} for user {user_id}")
            return excel_file
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating Excel file: {str(e)}")
            raise DatabaseError(f"Failed to create Excel file: {str(e)}")

    async def get_excel_file_by_user_and_name(
        self,
        user_id: str,
        file_name: str
    ) -> Optional[ExcelFile]:
        """
        Get Excel file by user ID and file name.
        
        Args:
            user_id: User ID
            file_name: File name
            
        Returns:
            ExcelFile instance if found, None otherwise
        """
        try:
            stmt = select(ExcelFile).where(
                and_(
                    ExcelFile.user_id == user_id,
                    ExcelFile.file_name == file_name,
                    ExcelFile.file_status == "active"
                )
            )
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting Excel file: {str(e)}")
            raise DatabaseError(f"Failed to retrieve Excel file: {str(e)}")

    async def update_excel_file_metadata(
        self,
        excel_file_id: str,
        onedrive_file_id: Optional[str] = None,
        onedrive_drive_id: Optional[str] = None,
        web_url: Optional[str] = None,
        size_bytes: Optional[int] = None,
        last_modified_at: Optional[datetime] = None
    ) -> bool:
        """
        Update Excel file metadata.
        
        Args:
            excel_file_id: Excel file ID
            onedrive_file_id: Updated OneDrive file ID
            onedrive_drive_id: Updated OneDrive drive ID
            web_url: Updated web URL
            size_bytes: Updated file size
            last_modified_at: Last modification timestamp
            
        Returns:
            True if updated successfully, False if not found
        """
        try:
            update_data = {"last_accessed_at": datetime.utcnow()}
            
            if onedrive_file_id is not None:
                update_data["onedrive_file_id"] = onedrive_file_id
            if onedrive_drive_id is not None:
                update_data["onedrive_drive_id"] = onedrive_drive_id
            if web_url is not None:
                update_data["web_url"] = web_url
            if size_bytes is not None:
                update_data["size_bytes"] = size_bytes
            if last_modified_at is not None:
                update_data["last_modified_at"] = last_modified_at
            
            stmt = update(ExcelFile).where(
                ExcelFile.id == excel_file_id
            ).values(**update_data)
            
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating Excel file metadata: {str(e)}")
            raise DatabaseError(f"Failed to update Excel file: {str(e)}")

    async def increment_sync_stats(
        self,
        excel_file_id: str,
        success: bool = True
    ) -> bool:
        """
        Increment sync statistics for an Excel file.
        
        Args:
            excel_file_id: Excel file ID
            success: Whether the sync was successful
            
        Returns:
            True if updated successfully
        """
        try:
            if success:
                stmt = update(ExcelFile).where(
                    ExcelFile.id == excel_file_id
                ).values(
                    total_sync_operations=ExcelFile.total_sync_operations + 1,
                    successful_syncs=ExcelFile.successful_syncs + 1,
                    last_sync_at=datetime.utcnow()
                )
            else:
                stmt = update(ExcelFile).where(
                    ExcelFile.id == excel_file_id
                ).values(
                    total_sync_operations=ExcelFile.total_sync_operations + 1,
                    failed_syncs=ExcelFile.failed_syncs + 1
                )
            
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating sync stats: {str(e)}")
            raise DatabaseError(f"Failed to update sync stats: {str(e)}")

    # Sync Operation Operations

    async def create_sync_operation(
        self,
        excel_file_id: str,
        user_id: str,
        operation_type: str,
        worksheet_name: str,
        transcription_id: Optional[str] = None,
        force_update: bool = False,
        apply_formatting: bool = True,
        max_retries: int = 3
    ) -> ExcelSyncOperation:
        """
        Create a new sync operation record.
        
        Args:
            excel_file_id: Excel file ID
            user_id: User ID
            operation_type: Type of operation (single, batch, full_sync)
            worksheet_name: Target worksheet name
            transcription_id: Optional transcription ID for single operations
            force_update: Whether to force update existing rows
            apply_formatting: Whether to apply formatting
            max_retries: Maximum retry attempts
            
        Returns:
            Created ExcelSyncOperation instance
        """
        try:
            sync_operation = ExcelSyncOperation(
                excel_file_id=excel_file_id,
                user_id=user_id,
                operation_type=operation_type,
                worksheet_name=worksheet_name,
                transcription_id=transcription_id,
                operation_status="pending",
                force_update=force_update,
                apply_formatting=apply_formatting,
                max_retries=max_retries,
                started_at=datetime.utcnow()
            )
            
            self.db_session.add(sync_operation)
            await self.db_session.commit()
            await self.db_session.refresh(sync_operation)
            
            logger.info(f"Created sync operation: {operation_type} for worksheet {worksheet_name}")
            return sync_operation
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating sync operation: {str(e)}")
            raise DatabaseError(f"Failed to create sync operation: {str(e)}")

    async def update_sync_operation_status(
        self,
        sync_operation_id: str,
        status: str,
        rows_processed: Optional[int] = None,
        rows_created: Optional[int] = None,
        rows_updated: Optional[int] = None,
        processing_time_ms: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update sync operation status and metrics.
        
        Args:
            sync_operation_id: Sync operation ID
            status: New operation status
            rows_processed: Number of rows processed
            rows_created: Number of rows created
            rows_updated: Number of rows updated
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
            
        Returns:
            True if updated successfully
        """
        try:
            update_data = {"operation_status": status}
            
            if rows_processed is not None:
                update_data["rows_processed"] = rows_processed
            if rows_created is not None:
                update_data["rows_created"] = rows_created
            if rows_updated is not None:
                update_data["rows_updated"] = rows_updated
            if processing_time_ms is not None:
                update_data["processing_time_ms"] = processing_time_ms
            if error_message is not None:
                update_data["error_message"] = error_message
            
            if status in ["completed", "failed"]:
                update_data["completed_at"] = datetime.utcnow()
            
            stmt = update(ExcelSyncOperation).where(
                ExcelSyncOperation.id == sync_operation_id
            ).values(**update_data)
            
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating sync operation: {str(e)}")
            raise DatabaseError(f"Failed to update sync operation: {str(e)}")

    async def increment_sync_operation_retry(
        self,
        sync_operation_id: str
    ) -> bool:
        """
        Increment retry count for a sync operation.
        
        Args:
            sync_operation_id: Sync operation ID
            
        Returns:
            True if updated successfully
        """
        try:
            stmt = update(ExcelSyncOperation).where(
                ExcelSyncOperation.id == sync_operation_id
            ).values(
                retry_count=ExcelSyncOperation.retry_count + 1,
                operation_status="retrying"
            )
            
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error incrementing retry count: {str(e)}")
            raise DatabaseError(f"Failed to increment retry count: {str(e)}")

    async def get_pending_sync_operations(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ExcelSyncOperation]:
        """
        Get pending sync operations.
        
        Args:
            user_id: Optional user ID filter
            limit: Maximum number of operations to return
            
        Returns:
            List of pending sync operations
        """
        try:
            stmt = select(ExcelSyncOperation).where(
                ExcelSyncOperation.operation_status.in_(["pending", "retrying"])
            ).order_by(ExcelSyncOperation.started_at).limit(limit)
            
            if user_id:
                stmt = stmt.where(ExcelSyncOperation.user_id == user_id)
            
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting pending sync operations: {str(e)}")
            raise DatabaseError(f"Failed to retrieve pending sync operations: {str(e)}")

    # Error Operations

    async def create_sync_error(
        self,
        excel_file_id: str,
        user_id: str,
        error_type: str,
        error_message: str,
        sync_operation_id: Optional[str] = None,
        error_code: Optional[str] = None,
        operation_type: Optional[str] = None,
        worksheet_name: Optional[str] = None,
        transcription_id: Optional[str] = None,
        http_status_code: Optional[int] = None,
        api_request_id: Optional[str] = None,
        retry_attempt: int = 0,
        stack_trace: Optional[str] = None
    ) -> ExcelSyncError:
        """
        Create a new sync error record.
        
        Args:
            excel_file_id: Excel file ID
            user_id: User ID
            error_type: Type of error
            error_message: Error message
            sync_operation_id: Optional sync operation ID
            error_code: Optional error code
            operation_type: Type of operation that failed
            worksheet_name: Worksheet name
            transcription_id: Optional transcription ID
            http_status_code: HTTP status code
            api_request_id: API request ID
            retry_attempt: Retry attempt number
            stack_trace: Stack trace for debugging
            
        Returns:
            Created ExcelSyncError instance
        """
        try:
            sync_error = ExcelSyncError(
                excel_file_id=excel_file_id,
                user_id=user_id,
                sync_operation_id=sync_operation_id,
                error_type=error_type,
                error_code=error_code,
                error_message=error_message,
                operation_type=operation_type,
                worksheet_name=worksheet_name,
                transcription_id=transcription_id,
                http_status_code=http_status_code,
                api_request_id=api_request_id,
                retry_attempt=retry_attempt,
                stack_trace=stack_trace
            )
            
            self.db_session.add(sync_error)
            await self.db_session.commit()
            await self.db_session.refresh(sync_error)
            
            logger.info(f"Created sync error record: {error_type} - {error_message}")
            return sync_error
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating sync error: {str(e)}")
            raise DatabaseError(f"Failed to create sync error: {str(e)}")

    async def resolve_sync_error(
        self,
        error_id: str,
        resolution_notes: Optional[str] = None
    ) -> bool:
        """
        Mark a sync error as resolved.
        
        Args:
            error_id: Error ID
            resolution_notes: Optional resolution notes
            
        Returns:
            True if updated successfully
        """
        try:
            stmt = update(ExcelSyncError).where(
                ExcelSyncError.id == error_id
            ).values(
                is_resolved=True,
                resolved_at=datetime.utcnow(),
                resolution_notes=resolution_notes
            )
            
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error resolving sync error: {str(e)}")
            raise DatabaseError(f"Failed to resolve sync error: {str(e)}")

    # Statistics and Analytics

    async def get_sync_statistics(
        self,
        user_id: str,
        days_ago: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get sync statistics for a user.
        
        Args:
            user_id: User ID
            days_ago: Optional filter for recent data
            
        Returns:
            Dictionary containing sync statistics
        """
        try:
            # Base queries
            excel_file_query = select(ExcelFile).where(ExcelFile.user_id == user_id)
            sync_ops_query = select(ExcelSyncOperation).where(ExcelSyncOperation.user_id == user_id)
            errors_query = select(ExcelSyncError).where(ExcelSyncError.user_id == user_id)
            
            # Apply date filter if specified
            if days_ago:
                cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
                sync_ops_query = sync_ops_query.where(ExcelSyncOperation.started_at >= cutoff_date)
                errors_query = errors_query.where(ExcelSyncError.created_at >= cutoff_date)
            
            # Execute queries
            excel_files_result = await self.db_session.execute(excel_file_query)
            excel_files = excel_files_result.scalars().all()
            
            sync_ops_result = await self.db_session.execute(sync_ops_query)
            sync_operations = sync_ops_result.scalars().all()
            
            errors_result = await self.db_session.execute(errors_query)
            errors = errors_result.scalars().all()
            
            # Calculate statistics
            total_files = len(excel_files)
            total_sync_operations = len(sync_operations)
            successful_syncs = len([op for op in sync_operations if op.operation_status == "completed"])
            failed_syncs = len([op for op in sync_operations if op.operation_status == "failed"])
            pending_syncs = len([op for op in sync_operations if op.operation_status in ["pending", "in_progress", "retrying"]])
            
            total_errors = len(errors)
            resolved_errors = len([err for err in errors if err.is_resolved])
            unresolved_errors = total_errors - resolved_errors
            
            # Calculate success rate
            success_rate = (successful_syncs / total_sync_operations * 100) if total_sync_operations > 0 else 0
            
            # Calculate average processing time
            completed_ops = [op for op in sync_operations if op.operation_status == "completed" and op.processing_time_ms]
            avg_processing_time = sum(op.processing_time_ms for op in completed_ops) / len(completed_ops) if completed_ops else 0
            
            # Get most recent sync
            last_sync = max([f.last_sync_at for f in excel_files if f.last_sync_at], default=None)
            
            return {
                "total_excel_files": total_files,
                "total_sync_operations": total_sync_operations,
                "successful_syncs": successful_syncs,
                "failed_syncs": failed_syncs,
                "pending_syncs": pending_syncs,
                "success_rate_percent": round(success_rate, 2),
                "total_errors": total_errors,
                "resolved_errors": resolved_errors,
                "unresolved_errors": unresolved_errors,
                "avg_processing_time_ms": round(avg_processing_time, 2) if avg_processing_time else None,
                "last_sync_at": last_sync.isoformat() if last_sync else None,
                "period_days": days_ago
            }
            
        except Exception as e:
            logger.error(f"Error getting sync statistics: {str(e)}")
            raise DatabaseError(f"Failed to retrieve sync statistics: {str(e)}")

    async def get_user_excel_files(
        self,
        user_id: str,
        include_inactive: bool = False
    ) -> List[ExcelFile]:
        """
        Get all Excel files for a user.
        
        Args:
            user_id: User ID
            include_inactive: Whether to include inactive files
            
        Returns:
            List of ExcelFile instances
        """
        try:
            stmt = select(ExcelFile).where(ExcelFile.user_id == user_id)
            
            if not include_inactive:
                stmt = stmt.where(ExcelFile.file_status == "active")
            
            result = await self.db_session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting user Excel files: {str(e)}")
            raise DatabaseError(f"Failed to retrieve Excel files: {str(e)}")