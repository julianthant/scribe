"""
VoiceAttachment.py - Voice Attachment API Endpoints

Provides REST API endpoints for voice attachment operations and management.
This module handles:
- GET /voice-attachments: Get all voice attachments across the mailbox
- GET /voice-messages: Get all messages containing voice attachments
- POST /organize-voice: Organize voice messages into dedicated folders
- GET /voice-attachments/{message_id}/{attachment_id}/metadata: Get voice attachment metadata
- GET /voice-attachments/{message_id}/{attachment_id}/download: Download voice attachment
- GET /messages/{message_id}/voice-attachments: Get voice attachments from specific message
- GET /voice-statistics: Get voice attachment statistics

Voice Attachment Blob Storage Operations:
- POST /voice-attachments/store/{message_id}/{attachment_id}: Store voice attachment in blob
- GET /voice-attachments/stored: List stored voice attachments
- GET /voice-attachments/blob/{blob_name}: Download from blob storage
- DELETE /voice-attachments/blob/{blob_name}: Delete stored voice attachment
- GET /voice-attachments/storage-statistics: Get storage statistics
- POST /voice-attachments/cleanup: Cleanup expired voice attachments

All endpoints require authentication and integrate with VoiceAttachmentService for business logic.
"""

from typing import List, Optional
import logging
from io import BytesIO

from fastapi import APIRouter, HTTPException, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.services.MailService import MailService
from app.services.VoiceAttachmentService import VoiceAttachmentService
from app.dependencies.Auth import get_current_user
from app.dependencies.mail import get_mail_service, get_voice_attachment_service
from app.models.AuthModel import UserInfo
from app.models.MailModel import (
    MessageListResponse, OrganizeVoiceRequest, OrganizeVoiceResponse,
    VoiceAttachment
)
from app.core.Exceptions import ValidationError, AuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice-attachments", tags=["voice-attachments"])


@router.get("", response_model=List[VoiceAttachment])
async def get_voice_attachments(
    folder_id: Optional[str] = Query(None, description="Folder ID to search within"),
    limit: int = Query(100, ge=1, le=500, description="Maximum messages to check"),
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Get all voice attachments across the mailbox.
    
    Args:
        folder_id: Optional folder ID to search within
        limit: Maximum number of messages to check
        
    Returns:
        List of voice attachments
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        voice_messages = await voice_service.find_all_voice_messages(folder_id, limit)
        all_voice_attachments = []
        
        for message in voice_messages:
            voice_attachments = await voice_service.extract_voice_attachments_from_message(message.id)
            all_voice_attachments.extend(voice_attachments)
        
        return all_voice_attachments
    except AuthenticationError as e:
        logger.error(f"Authentication error getting voice attachments: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting voice attachments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve voice attachments")


@router.get("/voice-messages", response_model=MessageListResponse)
async def get_voice_messages(
    folder_id: Optional[str] = Query(None, description="Folder ID to search within"),
    top: int = Query(100, ge=1, le=500, description="Maximum messages to check"),
    current_user: UserInfo = Depends(get_current_user),
    mail_service: MailService = Depends(get_mail_service)
):
    """Get all messages containing voice attachments.
    
    Args:
        folder_id: Optional folder ID to search within
        top: Maximum number of messages to check
        
    Returns:
        Message list response with voice messages
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        messages_response, _ = await mail_service.get_messages_with_voice_attachments(
            folder_id=folder_id, top=top
        )
        return messages_response
    except AuthenticationError as e:
        logger.error(f"Authentication error getting voice messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting voice messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve voice messages")


@router.post("/organize-voice", response_model=OrganizeVoiceResponse)
async def organize_voice_messages(
    request: OrganizeVoiceRequest,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Auto-organize voice messages into a dedicated folder.
    
    Args:
        request: Organization request with target folder name
        
    Returns:
        Organization response with statistics
        
    Raises:
        HTTPException: If organization fails
    """
    try:
        response = await voice_service.organize_voice_messages(request.targetFolderName)
        return response
    except AuthenticationError as e:
        logger.error(f"Authentication error organizing voice messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error organizing voice messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to organize voice messages")


@router.get("/{message_id}/{attachment_id}/metadata")
async def get_voice_attachment_metadata(
    message_id: str,
    attachment_id: str,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Get detailed metadata for a voice attachment.
    
    Args:
        message_id: Message ID
        attachment_id: Attachment ID
        
    Returns:
        Voice attachment metadata
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        metadata = await voice_service.get_voice_attachment_metadata(message_id, attachment_id)
        return metadata
    except ValidationError as e:
        logger.error(f"Validation error getting voice metadata: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error getting voice metadata: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Attachment not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting voice metadata: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve voice attachment metadata")


@router.get("/{message_id}/{attachment_id}/download")
async def download_voice_attachment(
    message_id: str,
    attachment_id: str,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Download a voice attachment.
    
    Args:
        message_id: Message ID
        attachment_id: Attachment ID
        
    Returns:
        Streaming response with voice attachment content
        
    Raises:
        HTTPException: If download fails
    """
    try:
        # Get metadata first
        metadata = await voice_service.get_voice_attachment_metadata(message_id, attachment_id)
        
        # Download content
        content = await voice_service.mail_service.download_voice_attachment(message_id, attachment_id)
        
        # Prepare response
        media_type = metadata.get("contentType", "audio/mpeg")
        filename = metadata.get("name", f"voice_{attachment_id}.audio")
        
        return StreamingResponse(
            BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
        
    except ValidationError as e:
        logger.error(f"Validation error downloading voice attachment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error downloading voice attachment: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Voice attachment not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error downloading voice attachment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download voice attachment")


@router.get("/messages/{message_id}", response_model=List[VoiceAttachment])
async def get_message_voice_attachments(
    message_id: str,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Get voice attachments from a specific message.
    
    Args:
        message_id: Message ID
        
    Returns:
        List of voice attachments
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        voice_attachments = await voice_service.extract_voice_attachments_from_message(message_id)
        return voice_attachments
    except AuthenticationError as e:
        logger.error(f"Authentication error getting voice attachments for {message_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting voice attachments for {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve voice attachments")


@router.get("/statistics")
async def get_voice_statistics(
    folder_id: Optional[str] = Query(None, description="Folder ID (if None, analyzes entire mailbox)"),
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Get comprehensive voice attachment statistics.
    
    Args:
        folder_id: Optional folder ID
        
    Returns:
        Voice attachment statistics
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        statistics = await voice_service.get_voice_statistics(folder_id)
        return statistics
    except AuthenticationError as e:
        logger.error(f"Authentication error getting voice statistics: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting voice statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve voice statistics")


# Voice Attachment Blob Storage Endpoints

@router.post("/store/{message_id}/{attachment_id}")
async def store_voice_attachment(
    message_id: str,
    attachment_id: str,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Download voice attachment from email and store in blob storage.
    
    Args:
        message_id: Graph API message ID
        attachment_id: Graph API attachment ID
        
    Returns:
        Storage confirmation with blob name
        
    Raises:
        HTTPException: If storage fails
    """
    try:
        blob_name = await voice_service.store_voice_attachment_in_blob(
            message_id=message_id,
            attachment_id=attachment_id,
            user_id=current_user.id
        )
        
        return {
            "success": True,
            "message": "Voice attachment stored successfully",
            "blob_name": blob_name,
            "message_id": message_id,
            "attachment_id": attachment_id
        }
        
    except ValidationError as e:
        logger.error(f"Validation error storing voice attachment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error storing voice attachment: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error storing voice attachment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to store voice attachment")


@router.get("/stored")
async def list_stored_voice_attachments(
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    content_type: Optional[str] = Query(None, description="Filter by content type (e.g., 'audio/mpeg')"),
    order_by: str = Query("received_at", description="Field to order by"),
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """List stored voice attachments for the current user.
    
    Args:
        limit: Maximum results to return
        offset: Number of results to skip
        content_type: Optional content type filter
        order_by: Field to order by
        
    Returns:
        List of stored voice attachments with pagination
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        attachments, total_count = await voice_service.list_stored_voice_attachments(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            content_type_filter=content_type,
            order_by=order_by
        )
        
        return {
            "attachments": attachments,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        }
        
    except AuthenticationError as e:
        logger.error(f"Authentication error listing stored attachments: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing stored attachments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list stored voice attachments")


@router.get("/blob/{blob_name}")
async def download_voice_attachment_from_blob(
    blob_name: str,
    request: Request,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Download voice attachment from blob storage.
    
    Args:
        blob_name: Blob storage identifier
        
    Returns:
        Streaming response with voice attachment content
        
    Raises:
        HTTPException: If download fails
    """
    try:
        # Get client IP and user agent for analytics
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        content, metadata = await voice_service.download_voice_attachment_from_blob(
            blob_name=blob_name,
            user_id=current_user.id,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        return StreamingResponse(
            BytesIO(content),
            media_type=metadata.get("content_type", "audio/mpeg"),
            headers={
                "Content-Disposition": f"attachment; filename=\"{metadata.get('filename', blob_name)}\"",
                "X-Download-Count": str(metadata.get("download_count", 0))
            }
        )
        
    except ValidationError as e:
        logger.error(f"Validation error downloading blob: {str(e)}")
        if "not found" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(status_code=404, detail="Voice attachment not found")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error downloading blob: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error downloading blob: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download voice attachment")


@router.delete("/blob/{blob_name}")
async def delete_stored_voice_attachment(
    blob_name: str,
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Delete stored voice attachment from blob storage.
    
    Args:
        blob_name: Blob storage identifier
        
    Returns:
        Deletion confirmation
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        success = await voice_service.delete_stored_voice_attachment(
            blob_name=blob_name,
            user_id=current_user.id
        )
        
        if success:
            return {
                "success": True,
                "message": f"Voice attachment {blob_name} deleted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete voice attachment")
        
    except ValidationError as e:
        logger.error(f"Validation error deleting voice attachment: {str(e)}")
        if "not found" in str(e).lower() or "access denied" in str(e).lower():
            raise HTTPException(status_code=404, detail="Voice attachment not found")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error deleting voice attachment: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting voice attachment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete voice attachment")


@router.get("/storage-statistics")
async def get_voice_attachment_storage_statistics(
    days_ago: Optional[int] = Query(None, ge=1, le=365, description="Filter for recent data (days)"),
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Get voice attachment storage statistics for the current user.
    
    Args:
        days_ago: Optional filter for recent data
        
    Returns:
        Storage statistics
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        statistics = await voice_service.get_voice_attachment_storage_statistics(
            user_id=current_user.id,
            days_ago=days_ago
        )
        
        return statistics
        
    except AuthenticationError as e:
        logger.error(f"Authentication error getting storage statistics: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting storage statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve storage statistics")


@router.post("/cleanup")
async def cleanup_expired_voice_attachments(
    max_age_days: Optional[int] = Query(None, ge=1, le=365, description="Maximum age in days"),
    dry_run: bool = Query(True, description="If true, only return count without deleting"),
    current_user: UserInfo = Depends(get_current_user),
    voice_service: VoiceAttachmentService = Depends(get_voice_attachment_service)
):
    """Clean up expired voice attachments (admin function - requires superuser).
    
    Args:
        max_age_days: Maximum age in days
        dry_run: If true, only return count without deleting
        
    Returns:
        Cleanup statistics
        
    Raises:
        HTTPException: If cleanup fails or user lacks permissions
    """
    try:
        # Check if user has admin privileges (this would need to be implemented in the auth system)
        # For now, we'll allow all authenticated users to run cleanup on their own data
        if not hasattr(current_user, 'is_superuser') or not current_user.is_superuser:
            # Allow user-specific cleanup only
            if dry_run:
                # Allow dry run for all users
                pass
            else:
                raise HTTPException(
                    status_code=403, 
                    detail="Only administrators can perform actual cleanup operations"
                )
        
        cleanup_stats = await voice_service.cleanup_expired_voice_attachments(
            max_age_days=max_age_days,
            dry_run=dry_run
        )
        
        return cleanup_stats
        
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.error(f"Authentication error during cleanup: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to cleanup voice attachments")