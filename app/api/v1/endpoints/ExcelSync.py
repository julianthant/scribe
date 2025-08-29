"""
ExcelSync.py - Excel Synchronization API Endpoints

Provides REST API endpoints for Excel synchronization operations.
This module handles:
- POST /excel-sync/sync-month: Manually sync monthly transcriptions to Excel
- POST /excel-sync/sync/{transcription_id}: Manually sync specific transcription to Excel
- GET /excel-sync/health: Check Excel sync service health
- GET /excel-sync/statistics: Get Excel sync statistics
- GET /excel-sync/history: Get sync history
- POST /excel-sync/batch: Batch sync multiple transcriptions
- GET /excel-sync/files: List Excel files in OneDrive
- GET /excel-sync/worksheets/{file_id}: Get worksheets in an Excel file
- POST /excel-sync/create-worksheet: Create new worksheet
- DELETE /excel-sync/worksheet/{file_id}/{worksheet_id}: Delete worksheet

All endpoints require authentication and integrate with ExcelTranscriptionSyncService
and TranscriptionService for business logic.
"""

from typing import List, Optional, Dict, Any
import logging

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from app.services.TranscriptionService import TranscriptionService
from app.services.ExcelTranscriptionSyncService import ExcelTranscriptionSyncService
from app.dependencies.Auth import get_current_user_info_only
from app.dependencies.Transcription import get_transcription_service, get_excel_sync_service
from app.models.AuthModel import UserInfo
from app.core.Exceptions import ValidationError, AuthenticationError, DatabaseError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/excel-sync", tags=["excel-sync"])


# Request/Response Models
class SyncMonthRequest(BaseModel):
    """Request model for monthly sync."""
    month_year: Optional[str] = Field(None, description="Month/Year to sync (e.g., 'December 2024')")
    force_update: bool = Field(False, description="Force update if already exists")
    

class BatchSyncRequest(BaseModel):
    """Request model for batch sync."""
    transcription_ids: List[str] = Field(..., description="List of transcription IDs to sync")
    force_update: bool = Field(False, description="Force update if already exists")
    max_concurrent: int = Field(3, ge=1, le=10, description="Maximum concurrent syncs")


class CreateWorksheetRequest(BaseModel):
    """Request model for creating worksheets."""
    file_id: str = Field(..., description="Excel file ID")
    worksheet_name: str = Field(..., description="Name for the new worksheet")
    template_type: Optional[str] = Field(None, description="Template type for the worksheet")


class ExcelSyncHistoryResponse(BaseModel):
    """Response model for sync history."""
    id: str
    transcription_id: str
    worksheet_name: str
    sync_status: str
    rows_processed: int
    rows_created: int
    rows_updated: int
    errors: List[str]
    processing_time_ms: Optional[int]
    created_at: str
    completed_at: Optional[str]

    class Config:
        from_attributes = True


# API Endpoints

@router.post("/sync-month")
async def sync_month_to_excel(
    request: SyncMonthRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Manually trigger sync of monthly transcriptions to Excel.
    
    Args:
        request: Monthly sync request
        
    Returns:
        Sync results
        
    Raises:
        HTTPException: If sync fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        # or refresh it from stored refresh tokens. For now, this is a placeholder.
        access_token = None  # Would need to be retrieved from user session or refreshed
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for Excel sync. Please re-authenticate."
            )
        
        sync_result = await transcription_service.trigger_monthly_excel_sync(
            user_id=current_user.id,
            access_token=access_token,
            month_year=request.month_year,
            force_update=request.force_update
        )
        
        return sync_result
        
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.error(f"Authentication error syncing month to Excel: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error syncing month to Excel: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sync transcriptions to Excel")


@router.post("/sync/{transcription_id}")
async def sync_transcription_to_excel(
    transcription_id: str,
    force_update: bool = Query(False, description="Force update if already exists in Excel"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Manually sync a specific transcription to Excel.
    
    Args:
        transcription_id: ID of transcription to sync
        force_update: Whether to update if already exists
        
    Returns:
        Sync result
        
    Raises:
        HTTPException: If sync fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for Excel sync. Please re-authenticate."
            )
        
        # Get Excel sync service from transcription service
        if not hasattr(transcription_service, 'excel_sync_service') or not transcription_service.excel_sync_service:
            raise HTTPException(
                status_code=503,
                detail="Excel sync service not available"
            )
        
        sync_result = await transcription_service.excel_sync_service.sync_transcription_to_excel(
            user_id=current_user.id,
            transcription_id=transcription_id,
            access_token=access_token,
            force_update=force_update
        )
        
        return {
            "status": sync_result.status,
            "worksheet_name": sync_result.worksheet_name,
            "rows_processed": sync_result.rows_processed,
            "rows_created": sync_result.rows_created,
            "rows_updated": sync_result.rows_updated,
            "errors": sync_result.errors,
            "processing_time_ms": sync_result.processing_time_ms,
            "completed_at": sync_result.completed_at.isoformat() if sync_result.completed_at else None
        }
        
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.error(f"Authentication error syncing transcription: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error syncing transcription to Excel: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to sync transcription to Excel")


@router.post("/batch")
async def batch_sync_transcriptions_to_excel(
    request: BatchSyncRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    Batch sync multiple transcriptions to Excel.
    
    Args:
        request: Batch sync request
        
    Returns:
        Batch sync results
        
    Raises:
        HTTPException: If batch sync fails
    """
    try:
        if not request.transcription_ids:
            raise HTTPException(status_code=400, detail="No transcription IDs provided")
        
        if len(request.transcription_ids) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 transcriptions per batch")
        
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for Excel sync. Please re-authenticate."
            )
        
        results = await excel_sync_service.batch_sync_transcriptions_to_excel(
            user_id=current_user.id,
            transcription_ids=request.transcription_ids,
            access_token=access_token,
            force_update=request.force_update,
            max_concurrent=request.max_concurrent
        )
        
        # Process results for response
        processed_results = {}
        successful_count = 0
        failed_count = 0
        
        for transcription_id, result in results.items():
            if isinstance(result, Exception):
                processed_results[transcription_id] = {
                    "status": "failed",
                    "error": str(result)
                }
                failed_count += 1
            else:
                processed_results[transcription_id] = {
                    "status": "completed",
                    "sync_result": {
                        "worksheet_name": result.worksheet_name,
                        "rows_processed": result.rows_processed,
                        "rows_created": result.rows_created,
                        "rows_updated": result.rows_updated,
                        "errors": result.errors
                    }
                }
                successful_count += 1
        
        return {
            "results": processed_results,
            "successful_count": successful_count,
            "failed_count": failed_count,
            "total_count": len(request.transcription_ids)
        }
        
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.error(f"Authentication error in batch Excel sync: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in batch Excel sync: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process batch Excel sync")


@router.get("/health")
async def get_excel_sync_health(
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Check Excel sync service health.
    
    Returns:
        Excel sync health status
        
    Raises:
        HTTPException: If health check fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            return {
                "service_available": False,
                "error": "Access token required for Excel sync health check"
            }
        
        health_status = await transcription_service.get_excel_sync_health(
            user_id=current_user.id,
            access_token=access_token
        )
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error checking Excel sync health: {str(e)}")
        return {
            "service_available": False,
            "error": str(e)
        }


@router.get("/statistics")
async def get_excel_sync_statistics(
    days_ago: Optional[int] = Query(None, ge=1, le=365, description="Filter data from N days ago"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    Get Excel sync statistics for the current user.
    
    Args:
        days_ago: Optional filter for recent data
        
    Returns:
        Excel sync statistics
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # TODO: Implement get_sync_statistics method in ExcelTranscriptionSyncService
        statistics = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_rows": 0
        }
        
        return statistics
        
    except DatabaseError as e:
        logger.error(f"Database error getting Excel sync statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
    except Exception as e:
        logger.error(f"Unexpected error getting Excel sync statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/history")
async def get_excel_sync_history(
    status: Optional[str] = Query(None, description="Filter by sync status"),
    limit: int = Query(50, ge=1, le=200, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    order_by: str = Query("created_at", description="Field to order by"),
    order_direction: str = Query("desc", pattern="^(asc|desc)$", description="Order direction"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    Get Excel sync history for the current user.
    
    Returns:
        List of sync history records with pagination info
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # TODO: Implement get_sync_history method in ExcelTranscriptionSyncService  
        history_records: List[Dict[str, Any]] = []
        total_count = 0
        
        history_responses = [
            ExcelSyncHistoryResponse(
                id=record["id"],
                transcription_id=record["transcription_id"],
                worksheet_name=record["worksheet_name"],
                sync_status=record["sync_status"],
                rows_processed=record["rows_processed"],
                rows_created=record["rows_created"],
                rows_updated=record["rows_updated"],
                errors=record["errors"] or [],
                processing_time_ms=record["processing_time_ms"],
                created_at=record["created_at"].isoformat(),
                completed_at=record["completed_at"].isoformat() if record["completed_at"] else None
            )
            for record in history_records
        ]
        
        return {
            "history": history_responses,
            "total_count": total_count,
            "page_size": limit,
            "page_offset": offset
        }
        
    except DatabaseError as e:
        logger.error(f"Database error getting Excel sync history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync history")
    except Exception as e:
        logger.error(f"Unexpected error getting Excel sync history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve sync history")


@router.get("/files")
async def list_excel_files(
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    List Excel files available in OneDrive for sync.
    
    Returns:
        List of Excel files
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for OneDrive access. Please re-authenticate."
            )
        
        excel_files = await excel_sync_service.list_excel_files(
            user_id=current_user.id,
            access_token=access_token
        )
        
        return {"files": excel_files}
        
    except AuthenticationError as e:
        logger.error(f"Authentication error listing Excel files: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing Excel files: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list Excel files")


@router.get("/worksheets/{file_id}")
async def get_excel_worksheets(
    file_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    Get worksheets in an Excel file.
    
    Args:
        file_id: Excel file ID
        
    Returns:
        List of worksheets
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for OneDrive access. Please re-authenticate."
            )
        
        worksheets = await excel_sync_service.get_excel_worksheets(
            user_id=current_user.id,
            file_id=file_id,
            access_token=access_token
        )
        
        return {"worksheets": worksheets}
        
    except AuthenticationError as e:
        logger.error(f"Authentication error getting Excel worksheets: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error getting Excel worksheets: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting Excel worksheets: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get Excel worksheets")


@router.post("/create-worksheet")
async def create_excel_worksheet(
    request: CreateWorksheetRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    Create a new worksheet in an Excel file.
    
    Args:
        request: Worksheet creation request
        
    Returns:
        Created worksheet info
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for OneDrive access. Please re-authenticate."
            )
        
        worksheet = await excel_sync_service.create_excel_worksheet(
            user_id=current_user.id,
            file_id=request.file_id,
            worksheet_name=request.worksheet_name,
            access_token=access_token,
            template_type=request.template_type
        )
        
        return {
            "success": True,
            "worksheet": worksheet,
            "message": f"Worksheet '{request.worksheet_name}' created successfully"
        }
        
    except ValidationError as e:
        logger.error(f"Validation error creating Excel worksheet: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error creating Excel worksheet: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating Excel worksheet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create Excel worksheet")


@router.delete("/worksheet/{file_id}/{worksheet_id}")
async def delete_excel_worksheet(
    file_id: str,
    worksheet_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
):
    """
    Delete a worksheet from an Excel file.
    
    Args:
        file_id: Excel file ID
        worksheet_id: Worksheet ID to delete
        
    Returns:
        Deletion confirmation
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        # NOTE: In a real implementation, you would get the access token from the user's session
        access_token = None  # Would need to be retrieved from user session
        
        if not access_token:
            raise HTTPException(
                status_code=400, 
                detail="Access token required for OneDrive access. Please re-authenticate."
            )
        
        success = await excel_sync_service.delete_excel_worksheet(
            user_id=current_user.id,
            file_id=file_id,
            worksheet_id=worksheet_id,
            access_token=access_token
        )
        
        if success:
            return {
                "success": True,
                "message": f"Worksheet deleted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete worksheet")
        
    except ValidationError as e:
        logger.error(f"Validation error deleting Excel worksheet: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Worksheet not found")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error deleting Excel worksheet: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting Excel worksheet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete Excel worksheet")