"""
Transcription.py - Voice Transcription API Endpoints

Provides REST API endpoints for voice transcription operations using Azure AI Foundry.
This module handles:
- POST /transcriptions/voice/{voice_attachment_id}: Transcribe a specific voice attachment
- GET /transcriptions/voice/{voice_attachment_id}: Get transcription for a voice attachment
- GET /transcriptions/{transcription_id}: Get specific transcription details
- POST /transcriptions/batch: Batch transcribe multiple voice attachments
- GET /transcriptions: List user transcriptions with filtering and search
- DELETE /transcriptions/{transcription_id}: Delete a transcription
- GET /transcriptions/statistics/summary: Get transcription statistics
- GET /transcriptions/errors/list: Get transcription errors
- POST /transcriptions/errors/{error_id}/resolve: Resolve transcription error
- POST /transcriptions/voice/{voice_attachment_id}/retry: Retry failed transcription
- GET /transcriptions/models/supported: Get supported transcription models
- GET /transcriptions/health/status: Health check

Excel sync operations have been moved to ExcelSync.py endpoints.
All endpoints require authentication and integrate with TranscriptionService for business logic.
"""

from typing import List, Optional, Dict, Any
import logging

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field

from app.services.TranscriptionService import TranscriptionService
from app.dependencies.Auth import get_current_user_info_only
from app.dependencies.Transcription import get_transcription_service
from app.models.AuthModel import UserInfo
from app.core.Exceptions import ValidationError, AuthenticationError, DatabaseError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])


# Request/Response Models
class TranscribeVoiceRequest(BaseModel):
    """Request model for voice attachment transcription."""
    model_deployment: Optional[str] = Field(None, description="Model deployment name")
    language: Optional[str] = Field(None, description="Language code (ISO-639-1 format)")
    prompt: Optional[str] = Field(None, description="Optional prompt to guide transcription style")
    force_retranscribe: bool = Field(False, description="Force retranscription if already exists")


class BatchTranscribeRequest(BaseModel):
    """Request model for batch transcription."""
    voice_attachment_ids: List[str] = Field(..., description="List of voice attachment IDs")
    model_deployment: Optional[str] = Field(None, description="Model deployment name")
    language: Optional[str] = Field(None, description="Language code")
    max_concurrent: int = Field(3, ge=1, le=10, description="Maximum concurrent requests")
    force_retranscribe: bool = Field(False, description="Force retranscription if already exists")


class TranscriptionResponse(BaseModel):
    """Response model for transcription data."""
    id: str
    voice_attachment_id: str
    transcript_text: str
    language: Optional[str]
    confidence_score: Optional[float]
    transcription_status: str
    model_name: str
    response_format: str
    has_word_timestamps: bool
    has_segment_timestamps: bool
    audio_duration_seconds: Optional[float]
    processing_time_ms: Optional[int]
    created_at: str
    updated_at: str
    
    # Voice attachment info
    voice_attachment: Optional[Dict[str, Any]] = None
    
    # Segments (optional)
    segments: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


class TranscriptionListResponse(BaseModel):
    """Response model for transcription lists."""
    transcriptions: List[TranscriptionResponse]
    total_count: int
    page_size: int
    page_offset: int


class BatchTranscribeResponse(BaseModel):
    """Response model for batch transcription."""
    results: Dict[str, Any]  # Maps attachment_id to result or error
    successful_count: int
    failed_count: int
    total_count: int


class TranscriptionErrorResponse(BaseModel):
    """Response model for transcription errors."""
    id: str
    voice_attachment_id: str
    error_type: str
    error_code: Optional[str]
    error_message: str
    model_name: Optional[str]
    audio_format: Optional[str]
    is_resolved: bool
    retry_count: int
    created_at: str

    class Config:
        from_attributes = True


class ResolveErrorRequest(BaseModel):
    """Request model for resolving transcription errors."""
    resolution_notes: Optional[str] = Field(None, description="Optional resolution notes")


# API Endpoints

@router.post("/voice/{voice_attachment_id}", response_model=TranscriptionResponse)
async def transcribe_voice_attachment(
    voice_attachment_id: str,
    request: TranscribeVoiceRequest = Body(...),
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Transcribe a voice attachment using Azure AI Foundry.
    
    Args:
        voice_attachment_id: ID of the voice attachment to transcribe
        request: Transcription request parameters
        
    Returns:
        Transcription result
        
    Raises:
        HTTPException: If transcription fails
    """
    try:
        transcription = await transcription_service.transcribe_voice_attachment(
            voice_attachment_id=voice_attachment_id,
            user_id=current_user.id,
            model_deployment=request.model_deployment,
            language=request.language,
            prompt=request.prompt,
            force_retranscribe=request.force_retranscribe
        )
        
        return _convert_transcription_to_response(transcription)
        
    except ValidationError as e:
        logger.error(f"Validation error transcribing voice attachment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error transcribing voice attachment: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error transcribing voice attachment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to transcribe voice attachment")


@router.get("/voice/{voice_attachment_id}", response_model=TranscriptionResponse)
async def get_transcription_by_voice_attachment(
    voice_attachment_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Get transcription for a voice attachment.
    
    Args:
        voice_attachment_id: ID of the voice attachment
        
    Returns:
        Transcription data
        
    Raises:
        HTTPException: If transcription not found
    """
    try:
        transcription = await transcription_service.get_transcription_by_voice_attachment(
            voice_attachment_id=voice_attachment_id,
            user_id=current_user.id
        )
        
        if not transcription:
            raise HTTPException(
                status_code=404, 
                detail=f"No transcription found for voice attachment {voice_attachment_id}"
            )
        
        return _convert_transcription_to_response(transcription)
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error getting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcription")
    except Exception as e:
        logger.error(f"Unexpected error getting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcription")


@router.get("/{transcription_id}", response_model=TranscriptionResponse)
async def get_transcription(
    transcription_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Get transcription by ID.
    
    Args:
        transcription_id: ID of the transcription
        
    Returns:
        Transcription data
        
    Raises:
        HTTPException: If transcription not found
    """
    try:
        transcription = await transcription_service.get_transcription(
            transcription_id=transcription_id,
            user_id=current_user.id
        )
        
        if not transcription:
            raise HTTPException(
                status_code=404, 
                detail=f"Transcription {transcription_id} not found"
            )
        
        return _convert_transcription_to_response(transcription)
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error getting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcription")
    except Exception as e:
        logger.error(f"Unexpected error getting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcription")


@router.post("/batch", response_model=BatchTranscribeResponse)
async def batch_transcribe_voice_attachments(
    request: BatchTranscribeRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Transcribe multiple voice attachments concurrently.
    
    Args:
        request: Batch transcription request
        
    Returns:
        Batch transcription results
        
    Raises:
        HTTPException: If batch transcription fails
    """
    try:
        if not request.voice_attachment_ids:
            raise HTTPException(status_code=400, detail="No voice attachment IDs provided")
        
        if len(request.voice_attachment_ids) > 20:
            raise HTTPException(status_code=400, detail="Maximum 20 voice attachments per batch")
        
        results = await transcription_service.transcribe_voice_attachments_batch(
            voice_attachment_ids=request.voice_attachment_ids,
            user_id=current_user.id,
            model_deployment=request.model_deployment,
            language=request.language,
            max_concurrent=request.max_concurrent,
            force_retranscribe=request.force_retranscribe
        )
        
        # Process results for response
        processed_results: Dict[str, Any] = {}
        successful_count = 0
        failed_count = 0
        
        for attachment_id, result in results.items():
            if isinstance(result, Exception):
                processed_results[attachment_id] = {
                    "status": "failed",
                    "error": str(result)
                }
                failed_count += 1
            else:
                processed_results[attachment_id] = {
                    "status": "completed",
                    "transcription": _convert_transcription_to_response(result).model_dump()
                }
                successful_count += 1
        
        return BatchTranscribeResponse(
            results=processed_results,
            successful_count=successful_count,
            failed_count=failed_count,
            total_count=len(request.voice_attachment_ids)
        )
        
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.error(f"Authentication error in batch transcription: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in batch transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process batch transcription")


@router.get("", response_model=TranscriptionListResponse)
async def list_transcriptions(
    status: Optional[str] = Query(None, description="Filter by transcription status"),
    language: Optional[str] = Query(None, description="Filter by language"),
    model: Optional[str] = Query(None, description="Filter by model"),
    search: Optional[str] = Query(None, description="Search in transcript text"),
    limit: int = Query(50, ge=1, le=200, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    order_by: str = Query("created_at", description="Field to order by"),
    order_direction: str = Query("desc", pattern="^(asc|desc)$", description="Order direction"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    List transcriptions for the current user with filtering and search.
    
    Returns:
        List of transcriptions with pagination info
    """
    try:
        transcriptions, total_count = await transcription_service.list_user_transcriptions(
            user_id=current_user.id,
            status_filter=status,
            language_filter=language,
            model_filter=model,
            search_text=search,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_direction=order_direction
        )
        
        transcription_responses = [
            _convert_transcription_to_response(t) for t in transcriptions
        ]
        
        return TranscriptionListResponse(
            transcriptions=transcription_responses,
            total_count=total_count,
            page_size=limit,
            page_offset=offset
        )
        
    except DatabaseError as e:
        logger.error(f"Database error listing transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcriptions")
    except Exception as e:
        logger.error(f"Unexpected error listing transcriptions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve transcriptions")


@router.delete("/{transcription_id}")
async def delete_transcription(
    transcription_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Delete a transcription.
    
    Args:
        transcription_id: ID of the transcription to delete
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        deleted = await transcription_service.delete_transcription(
            transcription_id=transcription_id,
            user_id=current_user.id
        )
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription {transcription_id} not found"
            )
        
        return {"message": f"Transcription {transcription_id} deleted successfully"}
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error deleting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete transcription")
    except Exception as e:
        logger.error(f"Unexpected error deleting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete transcription")


@router.get("/statistics/summary")
async def get_transcription_statistics(
    days_ago: Optional[int] = Query(None, ge=1, le=365, description="Filter data from N days ago"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Get transcription statistics for the current user.
    
    Args:
        days_ago: Optional filter for recent data
        
    Returns:
        Transcription statistics
    """
    try:
        statistics = await transcription_service.get_transcription_statistics(
            user_id=current_user.id,
            days_ago=days_ago
        )
        
        return statistics
        
    except DatabaseError as e:
        logger.error(f"Database error getting transcription statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
    except Exception as e:
        logger.error(f"Unexpected error getting transcription statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/errors/list")
async def get_transcription_errors(
    resolved: Optional[bool] = Query(None, description="Filter by resolution status"),
    limit: int = Query(50, ge=1, le=200, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Get transcription errors for the current user.
    
    Returns:
        List of transcription errors
    """
    try:
        errors, total_count = await transcription_service.get_transcription_errors(
            user_id=current_user.id,
            is_resolved=resolved,
            limit=limit,
            offset=offset
        )
        
        error_responses = [
            TranscriptionErrorResponse(
                id=error.id,
                voice_attachment_id=error.voice_attachment_id,
                error_type=error.error_type,
                error_code=error.error_code,
                error_message=error.error_message,
                model_name=error.model_name,
                audio_format=error.audio_format,
                is_resolved=error.is_resolved,
                retry_count=error.retry_count,
                created_at=error.created_at.isoformat()
            )
            for error in errors
        ]
        
        return {
            "errors": error_responses,
            "total_count": total_count,
            "page_size": limit,
            "page_offset": offset
        }
        
    except DatabaseError as e:
        logger.error(f"Database error getting transcription errors: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve errors")
    except Exception as e:
        logger.error(f"Unexpected error getting transcription errors: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve errors")


@router.post("/errors/{error_id}/resolve")
async def resolve_transcription_error(
    error_id: str,
    request: ResolveErrorRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Resolve a transcription error.
    
    Args:
        error_id: ID of the error to resolve
        request: Resolution request
        
    Returns:
        Success message
    """
    try:
        resolved_error = await transcription_service.resolve_transcription_error(
            error_id=error_id,
            user_id=current_user.id,
            resolution_notes=request.resolution_notes
        )
        
        if not resolved_error:
            raise HTTPException(
                status_code=404,
                detail=f"Transcription error {error_id} not found"
            )
        
        return {"message": f"Transcription error {error_id} resolved successfully"}
        
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Database error resolving transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to resolve error")
    except Exception as e:
        logger.error(f"Unexpected error resolving transcription error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to resolve error")


@router.post("/voice/{voice_attachment_id}/retry", response_model=TranscriptionResponse)
async def retry_failed_transcription(
    voice_attachment_id: str,
    model_deployment: Optional[str] = Body(None),
    language: Optional[str] = Body(None),
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Retry transcription for a failed voice attachment.
    
    Args:
        voice_attachment_id: ID of the voice attachment
        model_deployment: Optional model deployment name
        language: Optional language code
        
    Returns:
        New transcription result
    """
    try:
        transcription = await transcription_service.retry_failed_transcription(
            voice_attachment_id=voice_attachment_id,
            user_id=current_user.id,
            model_deployment=model_deployment,
            language=language
        )
        
        return _convert_transcription_to_response(transcription)
        
    except ValidationError as e:
        logger.error(f"Validation error retrying transcription: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error retrying transcription: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error retrying transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retry transcription")


@router.get("/models/supported")
async def get_supported_models(
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Get supported transcription models.
    
    Returns:
        List of supported models
    """
    try:
        models = await transcription_service.get_supported_models()
        return {"models": models}
        
    except AuthenticationError as e:
        logger.error(f"Authentication error getting supported models: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting supported models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve supported models")


@router.get("/health/status")
async def get_transcription_health(
    current_user: UserInfo = Depends(get_current_user_info_only),
    transcription_service: TranscriptionService = Depends(get_transcription_service)
):
    """
    Check transcription service health.
    
    Returns:
        Health status
    """
    try:
        health_status = await transcription_service.health_check()
        return health_status
        
    except Exception as e:
        logger.error(f"Error checking transcription health: {str(e)}")
        return {
            "service": "TranscriptionService",
            "status": "unhealthy",
            "error": str(e)
        }


# Helper Functions

def _convert_transcription_to_response(transcription) -> TranscriptionResponse:
    """Convert database transcription to API response model."""
    
    # Convert voice attachment if available
    voice_attachment_data = None
    if hasattr(transcription, 'voice_attachment') and transcription.voice_attachment:
        va = transcription.voice_attachment
        voice_attachment_data = {
            "id": va.id,
            "blob_name": va.blob_name,
            "original_filename": va.original_filename,
            "content_type": va.content_type,
            "size_bytes": va.size_bytes,
            "sender_email": va.sender_email,
            "sender_name": va.sender_name,
            "subject": va.subject,
            "received_at": va.received_at.isoformat()
        }
    
    # Convert segments if available
    segments_data = None
    if hasattr(transcription, 'segments') and transcription.segments:
        segments_data = [
            {
                "id": segment.id,
                "segment_index": segment.segment_index,
                "segment_type": segment.segment_type,
                "start_time_seconds": segment.start_time_seconds,
                "end_time_seconds": segment.end_time_seconds,
                "duration_seconds": segment.duration_seconds,
                "text": segment.text,
                "confidence_score": segment.confidence_score,
                "avg_logprob": segment.avg_logprob
            }
            for segment in transcription.segments
        ]
    
    return TranscriptionResponse(
        id=transcription.id,
        voice_attachment_id=transcription.voice_attachment_id,
        transcript_text=transcription.transcript_text,
        language=transcription.language,
        confidence_score=transcription.confidence_score,
        transcription_status=transcription.transcription_status,
        model_name=transcription.model_name,
        response_format=transcription.response_format,
        has_word_timestamps=transcription.has_word_timestamps,
        has_segment_timestamps=transcription.has_segment_timestamps,
        audio_duration_seconds=transcription.audio_duration_seconds,
        processing_time_ms=transcription.processing_time_ms,
        created_at=transcription.created_at.isoformat(),
        updated_at=transcription.updated_at.isoformat(),
        voice_attachment=voice_attachment_data,
        segments=segments_data
    )