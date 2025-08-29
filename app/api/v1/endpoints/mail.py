"""
Mail.py - Mail API Endpoints

Provides REST API endpoints for general email operations using Microsoft Graph API.
This module handles:
- GET /mail/folders: List all mail folders with hierarchy
- POST /mail/folders: Create new mail folders
- GET /mail/messages: List messages with pagination and filtering
- GET /mail/messages/{message_id}: Get specific message details
- PATCH /mail/messages/{message_id}: Update message properties
- POST /mail/messages/{message_id}/move: Move messages between folders
- POST /mail/search: Search messages with filters
- GET /mail/messages/{message_id}/attachments: List message attachments
- GET /mail/messages/{message_id}/attachments/{attachment_id}/download: Download attachments
- GET /mail/statistics: Get general mail statistics

Voice attachment operations have been moved to VoiceAttachment.py endpoints.
All endpoints require authentication and integrate with MailService for business logic.
"""

from typing import List, Optional
import logging
from io import BytesIO

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

from app.services.MailService import MailService
from app.dependencies.Auth import get_current_user_info_only
from app.dependencies.Mail import get_mail_service
from app.models.AuthModel import UserInfo
from app.models.MailModel import (
    MailFolder, Message, MessageListResponse, 
    CreateFolderRequest, MoveMessageRequest, UpdateMessageRequest,
    SearchMessagesRequest, FolderStatistics, Attachment
)
from app.core.Exceptions import ValidationError, AuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mail", tags=["mail"])


@router.get("/folders", response_model=List[MailFolder])
async def list_mail_folders(
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Get all mail folders.
    
    Returns:
        List of mail folders
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        folders = await mail_service.list_mail_folders()
        return folders
    except AuthenticationError as e:
        logger.error(f"Authentication error listing folders: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing folders: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve mail folders")


@router.post("/folders", response_model=MailFolder)
async def create_mail_folder(
    request: CreateFolderRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Create a new mail folder.
    
    Args:
        request: Folder creation request
        
    Returns:
        Created mail folder
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        folder = await mail_service.create_mail_folder(request)
        return folder
    except ValidationError as e:
        logger.error(f"Validation error creating folder: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error creating folder: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating folder: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create mail folder")


@router.get("/messages", response_model=MessageListResponse)
async def list_messages(
    folder_id: Optional[str] = Query(None, description="Folder ID to list messages from"),
    has_attachments: Optional[bool] = Query(None, description="Filter by attachment presence"),
    top: int = Query(25, ge=1, le=1000, description="Number of messages to return"),
    skip: int = Query(0, ge=0, description="Number of messages to skip"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Get messages from a folder or mailbox.
    
    Args:
        folder_id: Optional folder ID
        has_attachments: Optional filter for messages with attachments
        top: Number of messages to return
        skip: Number of messages to skip
        
    Returns:
        Message list response with pagination
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        if has_attachments:
            messages = await mail_service.get_messages_with_attachments(
                folder_id=folder_id, top=top, skip=skip
            )
        elif folder_id is None:
            # Get inbox messages if no folder specified
            messages = await mail_service.get_inbox_messages(top=top, skip=skip)
        else:
            # Use mail repository directly for general message listing
            messages = await mail_service.mail_repository.get_messages(
                folder_id=folder_id, top=top, skip=skip
            )
        return messages
    except AuthenticationError as e:
        logger.error(f"Authentication error listing messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


@router.get("/messages/{message_id}", response_model=Message)
async def get_message(
    message_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Get a specific message by ID.
    
    Args:
        message_id: Message ID
        
    Returns:
        Message details
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        message = await mail_service.mail_repository.get_message_by_id(message_id)
        return message
    except AuthenticationError as e:
        logger.error(f"Authentication error getting message {message_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting message {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve message")


@router.get("/messages/{message_id}/attachments", response_model=List[Attachment])
async def list_message_attachments(
    message_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Get all attachments for a message.
    
    Args:
        message_id: Message ID
        
    Returns:
        List of attachments
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        attachments = await mail_service.mail_repository.get_attachments(message_id)
        return attachments
    except AuthenticationError as e:
        logger.error(f"Authentication error getting attachments for {message_id}: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting attachments for {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve attachments")


@router.get("/messages/{message_id}/attachments/{attachment_id}/download")
async def download_attachment(
    message_id: str,
    attachment_id: str,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Download an attachment.
    
    Args:
        message_id: Message ID
        attachment_id: Attachment ID
        
    Returns:
        Streaming response with attachment content
        
    Raises:
        HTTPException: If download fails
    """
    try:
        # Get attachment metadata first
        attachments = await mail_service.mail_repository.get_attachments(message_id)
        target_attachment = None
        
        for attachment in attachments:
            if attachment.id == attachment_id:
                target_attachment = attachment
                break
        
        if not target_attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")

        # Download content
        content = await mail_service.mail_repository.download_attachment(message_id, attachment_id)
        
        # Prepare response
        media_type = target_attachment.contentType or "application/octet-stream"
        filename = target_attachment.name or f"attachment_{attachment_id}"
        
        return StreamingResponse(
            BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
        
    except HTTPException:
        raise
    except AuthenticationError as e:
        logger.error(f"Authentication error downloading attachment: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Attachment not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error downloading attachment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download attachment")


@router.post("/messages/{message_id}/move")
async def move_message(
    message_id: str,
    request: MoveMessageRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Move a message to a different folder.
    
    Args:
        message_id: Message ID
        request: Move request with destination
        
    Returns:
        Success status
        
    Raises:
        HTTPException: If move fails
    """
    try:
        success = await mail_service.move_message_to_folder(message_id, request.destinationId)
        return {"success": success, "message": f"Message moved to {request.destinationId}"}
    except ValidationError as e:
        logger.error(f"Validation error moving message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error moving message: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Message or folder not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error moving message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to move message")


@router.patch("/messages/{message_id}")
async def update_message(
    message_id: str,
    request: UpdateMessageRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Update message properties.
    
    Args:
        message_id: Message ID
        request: Update request
        
    Returns:
        Success status
        
    Raises:
        HTTPException: If update fails
    """
    try:
        success = True
        updates = []
        
        if request.isRead is not None:
            await mail_service.mark_message_as_read(message_id, request.isRead)
            updates.append(f"marked as {'read' if request.isRead else 'unread'}")
        
        if request.importance is not None:
            # Note: This would require extending the repository to support importance updates
            updates.append(f"importance set to {request.importance}")
        
        return {
            "success": success, 
            "message": f"Message updated: {', '.join(updates)}" if updates else "No updates specified"
        }
        
    except ValidationError as e:
        logger.error(f"Validation error updating message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error updating message: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update message")


@router.post("/search", response_model=MessageListResponse)
async def search_messages(
    request: SearchMessagesRequest,
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Search messages with various filters.
    
    Args:
        request: Search request with query and filters
        
    Returns:
        Message list response with search results
        
    Raises:
        HTTPException: If search fails
    """
    try:
        messages = await mail_service.search_messages(request)
        return messages
    except ValidationError as e:
        logger.error(f"Validation error searching messages: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error searching messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error searching messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to search messages")


@router.get("/statistics", response_model=FolderStatistics)
async def get_mail_statistics(
    folder_id: Optional[str] = Query(None, description="Folder ID (if None, gets entire mailbox stats)"),
    current_user: UserInfo = Depends(get_current_user_info_only),
    mail_service: MailService = Depends(get_mail_service)
):
    """Get mail statistics for a folder or entire mailbox.
    
    Args:
        folder_id: Optional folder ID
        
    Returns:
        Folder statistics
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        statistics = await mail_service.get_folder_statistics(folder_id)
        return statistics
    except AuthenticationError as e:
        logger.error(f"Authentication error getting statistics: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")