"""
shared_mailbox.py - Shared Mailbox API Endpoints

Provides REST API endpoints for shared mailbox operations using Microsoft Graph API.
This module handles:
- GET /shared-mailboxes: List accessible shared mailboxes
- GET /shared-mailboxes/{mailbox_id}: Get specific shared mailbox details
- POST /shared-mailboxes: Create new shared mailboxes (admin only)
- PUT /shared-mailboxes/{mailbox_id}: Update shared mailbox settings
- GET /shared-mailboxes/{mailbox_id}/folders: List shared mailbox folders
- GET /shared-mailboxes/{mailbox_id}/messages: List messages in shared mailbox
- POST /shared-mailboxes/{mailbox_id}/send: Send email as shared mailbox
- POST /shared-mailboxes/search: Search across shared mailboxes
- POST /shared-mailboxes/{mailbox_id}/organize: Organize shared mailbox content
- GET /shared-mailboxes/{mailbox_id}/statistics: Get shared mailbox statistics
- GET /shared-mailboxes/{mailbox_id}/access: Get access permissions

All endpoints require authentication and proper permissions for shared mailbox access.
"""

from typing import List, Optional, Dict, Any
import logging

from fastapi import APIRouter, HTTPException, Depends, Query, Path

from app.services.shared_mailbox_service import SharedMailboxService
from app.dependencies.auth import get_current_user
from app.dependencies.shared_mailbox import get_shared_mailbox_service
from app.models.auth import UserInfo
from app.models.shared_mailbox import (
    SharedMailbox, SharedMailboxAccess, SharedMailboxListResponse,
    SharedMailboxStatistics, SharedMailboxSearchRequest, SharedMailboxSearchResponse,
    SendAsSharedRequest, OrganizeSharedMailboxRequest, OrganizeSharedMailboxResponse,
    CreateSharedMailboxRequest, UpdateSharedMailboxRequest
)
from app.models.mail import MailFolder, MessageListResponse
from app.core.exceptions import ValidationError, AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shared-mailboxes", tags=["shared-mailboxes"])


@router.get("", response_model=SharedMailboxListResponse)
async def list_accessible_shared_mailboxes(
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get all shared mailboxes the current user has access to.
    
    Returns:
        List of accessible shared mailboxes with access information
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        response = await shared_mailbox_service.get_accessible_shared_mailboxes()
        return response
    except AuthenticationError as e:
        logger.error(f"Authentication error listing shared mailboxes: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing shared mailboxes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve shared mailboxes")


@router.get("/{email_address}", response_model=SharedMailboxAccess)
async def get_shared_mailbox_details(
    email_address: str = Path(..., description="Shared mailbox email address"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get detailed information about a specific shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        
    Returns:
        Detailed shared mailbox information with current user's permissions
        
    Raises:
        HTTPException: If retrieval fails or access denied
    """
    try:
        access = await shared_mailbox_service.get_shared_mailbox_details(email_address)
        return access
    except ValidationError as e:
        logger.error(f"Validation error getting mailbox details: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error accessing mailbox: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error getting mailbox details: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting mailbox details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve shared mailbox details")


@router.get("/{email_address}/folders", response_model=List[MailFolder])
async def list_shared_mailbox_folders(
    email_address: str = Path(..., description="Shared mailbox email address"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get all folders from a shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        
    Returns:
        List of mail folders
        
    Raises:
        HTTPException: If retrieval fails or access denied
    """
    try:
        folders = await shared_mailbox_service.get_shared_mailbox_folders(email_address)
        return folders
    except ValidationError as e:
        logger.error(f"Validation error getting folders: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error accessing folders: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error getting folders: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting folders: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve folders")


@router.post("/{email_address}/folders", response_model=MailFolder)
async def create_shared_mailbox_folder(
    folder_name: str,
    email_address: str = Path(..., description="Shared mailbox email address"),
    parent_id: Optional[str] = Query(None, description="Parent folder ID"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Create a new folder in a shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        folder_name: Name for the new folder
        parent_id: Optional parent folder ID
        
    Returns:
        Created mail folder
        
    Raises:
        HTTPException: If creation fails or access denied
    """
    try:
        folder = await shared_mailbox_service.create_shared_mailbox_folder(
            email_address, folder_name, parent_id
        )
        return folder
    except ValidationError as e:
        logger.error(f"Validation error creating folder: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error creating folder: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error creating folder: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating folder: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create folder")


@router.get("/{email_address}/messages", response_model=MessageListResponse)
async def list_shared_mailbox_messages(
    email_address: str = Path(..., description="Shared mailbox email address"),
    folder_id: Optional[str] = Query(None, description="Folder ID to list messages from"),
    has_attachments: Optional[bool] = Query(None, description="Filter by attachment presence"),
    top: int = Query(25, ge=1, le=1000, description="Number of messages to return"),
    skip: int = Query(0, ge=0, description="Number of messages to skip"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get messages from a shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        folder_id: Optional folder ID
        has_attachments: Optional filter for messages with attachments
        top: Number of messages to return
        skip: Number of messages to skip
        
    Returns:
        Message list response with pagination
        
    Raises:
        HTTPException: If retrieval fails or access denied
    """
    try:
        messages = await shared_mailbox_service.get_shared_mailbox_messages(
            email_address=email_address,
            folder_id=folder_id,
            has_attachments=has_attachments,
            top=top,
            skip=skip
        )
        return messages
    except ValidationError as e:
        logger.error(f"Validation error getting messages: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error accessing messages: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error getting messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")


@router.post("/{email_address}/send", response_model=Dict[str, Any])
async def send_shared_mailbox_message(
    request: SendAsSharedRequest,
    email_address: str = Path(..., description="Shared mailbox email address"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Send a message from a shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        request: Message sending request
        
    Returns:
        Send result with status
        
    Raises:
        HTTPException: If sending fails or access denied
    """
    try:
        result = await shared_mailbox_service.send_shared_mailbox_message(
            email_address, request
        )
        return result
    except ValidationError as e:
        logger.error(f"Validation error sending message: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error sending message: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error sending message: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error sending message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/{email_address}/organize", response_model=OrganizeSharedMailboxResponse)
async def organize_shared_mailbox_messages(
    request: OrganizeSharedMailboxRequest,
    email_address: str = Path(..., description="Shared mailbox email address"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Organize messages in a shared mailbox (e.g., voice messages into a folder).
    
    Args:
        email_address: Shared mailbox email address
        request: Organization request with target folder and criteria
        
    Returns:
        Organization response with statistics
        
    Raises:
        HTTPException: If organization fails or access denied
    """
    try:
        response = await shared_mailbox_service.organize_shared_mailbox_messages(
            email_address, request
        )
        return response
    except ValidationError as e:
        logger.error(f"Validation error organizing messages: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error organizing messages: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error organizing messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error organizing messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to organize messages")


@router.post("/search", response_model=SharedMailboxSearchResponse)
async def search_shared_mailboxes(
    request: SharedMailboxSearchRequest,
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Search across multiple shared mailboxes.
    
    Args:
        request: Search request with query and filters
        
    Returns:
        Search response with results from all accessible mailboxes
        
    Raises:
        HTTPException: If search fails
    """
    try:
        response = await shared_mailbox_service.search_shared_mailboxes(request)
        return response
    except ValidationError as e:
        logger.error(f"Validation error in search: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error in search: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in search: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/{email_address}/statistics", response_model=SharedMailboxStatistics)
async def get_shared_mailbox_statistics(
    email_address: str = Path(..., description="Shared mailbox email address"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get comprehensive statistics for a shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        
    Returns:
        Detailed mailbox statistics including message counts, sizes, and trends
        
    Raises:
        HTTPException: If statistics generation fails or access denied
    """
    try:
        statistics = await shared_mailbox_service.get_shared_mailbox_statistics(email_address)
        return statistics
    except ValidationError as e:
        logger.error(f"Validation error getting statistics: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error accessing statistics: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error getting statistics: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/voice-messages/cross-mailbox")
async def get_voice_messages_across_mailboxes(
    mailbox_addresses: List[str] = Query(..., description="List of mailbox email addresses"),
    top: int = Query(50, ge=1, le=200, description="Maximum messages to check per mailbox"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get voice messages from multiple shared mailboxes.
    
    Args:
        mailbox_addresses: List of shared mailbox email addresses
        top: Maximum number of messages to check per mailbox
        
    Returns:
        Voice messages from all specified mailboxes
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # This would integrate with voice attachment detection across mailboxes
        # For now, return a placeholder response
        results = []
        
        for email_address in mailbox_addresses:
            try:
                # Get messages with attachments and filter for voice
                messages = await shared_mailbox_service.get_shared_mailbox_messages(
                    email_address=email_address,
                    has_attachments=True,
                    top=top
                )
                
                # Would filter for voice attachments here
                voice_messages = [msg for msg in messages.value if msg.hasAttachments]
                
                if voice_messages:
                    results.append({
                        "mailbox": email_address,
                        "voiceMessages": [msg.dict() for msg in voice_messages],
                        "count": len(voice_messages)
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to get voice messages from {email_address}: {str(e)}")
                continue
        
        return {
            "mailboxes": results,
            "totalVoiceMessages": sum(r["count"] for r in results),
            "searchedMailboxes": len(mailbox_addresses),
            "successfulMailboxes": len(results)
        }
        
    except ValidationError as e:
        logger.error(f"Validation error getting voice messages: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error getting voice messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting voice messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve voice messages")


@router.post("/{email_address}/organize-voice")
async def organize_voice_messages_in_shared_mailbox(
    email_address: str = Path(..., description="Shared mailbox email address"),
    target_folder: str = Query("Voice Messages", description="Target folder name"),
    create_folder: bool = Query(True, description="Create folder if it doesn't exist"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Auto-organize voice messages in a shared mailbox into a dedicated folder.
    
    Args:
        email_address: Shared mailbox email address
        target_folder: Name of folder to organize voice messages into
        create_folder: Whether to create the folder if it doesn't exist
        
    Returns:
        Organization response with statistics
        
    Raises:
        HTTPException: If organization fails or access denied
    """
    try:
        request = OrganizeSharedMailboxRequest(
            targetFolderName=target_folder,
            createFolder=create_folder,
            messageType="voice"
        )
        
        response = await shared_mailbox_service.organize_shared_mailbox_messages(
            email_address, request
        )
        return response
        
    except ValidationError as e:
        logger.error(f"Validation error organizing voice messages: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AuthorizationError as e:
        logger.error(f"Authorization error organizing voice messages: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))
    except AuthenticationError as e:
        logger.error(f"Authentication error organizing voice messages: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error organizing voice messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to organize voice messages")


@router.get("/analytics/usage")
async def get_shared_mailboxes_usage_analytics(
    mailbox_addresses: Optional[List[str]] = Query(None, description="Specific mailboxes to analyze"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
):
    """Get usage analytics across shared mailboxes.
    
    Args:
        mailbox_addresses: Optional list of specific mailboxes to analyze
        days: Number of days to analyze
        
    Returns:
        Usage analytics including activity patterns and top users
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # This would be a more comprehensive analytics feature
        # For now, return a placeholder response
        
        if not mailbox_addresses:
            # Get all accessible mailboxes
            accessible_response = await shared_mailbox_service.get_accessible_shared_mailboxes()
            mailbox_addresses = [mb.emailAddress for mb in accessible_response.value]
        
        analytics = {
            "period": {
                "days": days,
                "startDate": f"{days} days ago",
                "endDate": "now"
            },
            "mailboxes": {
                "total": len(mailbox_addresses),
                "analyzed": len(mailbox_addresses),
                "active": len(mailbox_addresses)  # Simplified
            },
            "activity": {
                "totalMessages": 0,
                "averageMessagesPerDay": 0,
                "peakActivityDay": "Monday",  # Placeholder
                "quietestDay": "Sunday"  # Placeholder
            },
            "topMailboxes": [],
            "trends": {
                "messageVolumeChange": "+5%",  # Placeholder
                "attachmentVolumeChange": "+2%"  # Placeholder
            }
        }
        
        # Get statistics for each mailbox
        for email_address in mailbox_addresses[:10]:  # Limit for performance
            try:
                stats = await shared_mailbox_service.get_shared_mailbox_statistics(email_address)
                analytics["activity"]["totalMessages"] += stats.totalMessages
                analytics["topMailboxes"].append({
                    "mailbox": email_address,
                    "messages": stats.totalMessages,
                    "unread": stats.unreadMessages
                })
            except Exception as e:
                logger.warning(f"Failed to get analytics for {email_address}: {str(e)}")
                continue
        
        analytics["activity"]["averageMessagesPerDay"] = analytics["activity"]["totalMessages"] // days
        
        return analytics
        
    except AuthenticationError as e:
        logger.error(f"Authentication error getting analytics: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve analytics")