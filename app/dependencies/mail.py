"""
mail.py - Mail Service Dependencies

Provides FastAPI dependency injection functions for mail-related services and repositories.
This module handles:
- get_mail_service(): Creates MailService instances with authenticated repositories
- get_voice_attachment_service(): Creates VoiceAttachmentService instances
- Token extraction and validation for service initialization
- Repository instantiation with proper access tokens
- Service lifecycle management through dependency injection

These dependencies ensure that mail services are properly initialized with valid
authentication tokens and are available throughout the mail API endpoints.
"""

from typing import Optional
import logging

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.MailService import MailService
from app.services.VoiceAttachmentService import VoiceAttachmentService
from app.repositories.MailRepository import MailRepository
from app.repositories.SharedMailboxRepository import SharedMailboxRepository
from app.repositories.VoiceAttachmentRepository import VoiceAttachmentRepository
from app.azure.AzureBlobService import AzureBlobService, azure_blob_service
from app.db.Database import get_async_db
from app.dependencies.Auth import get_current_user
from app.models.AuthModel import UserInfo

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_mail_repository(
    auth_data: tuple[UserInfo, str] = Depends(get_current_user)
) -> MailRepository:
    """Get mail repository with access token from enhanced authentication.
    
    Args:
        auth_data: Tuple of (UserInfo, access_token) from authentication
        
    Returns:
        MailRepository: Configured mail repository
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        current_user, access_token = auth_data
        
        # Validate the access token exists and is not empty
        if not access_token or not access_token.strip():
            logger.error(f"Empty or invalid access token for user: {current_user.email}")
            raise HTTPException(
                status_code=401,
                detail="Invalid access token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.debug(f"Creating mail repository for user: {current_user.email}, token length: {len(access_token)}")
        repository = MailRepository(access_token)
        
        return repository
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error creating mail repository: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize mail service"
        )


async def get_mail_service(
    mail_repository: MailRepository = Depends(get_mail_repository)
) -> MailService:
    """Get mail service with repository.
    
    Args:
        mail_repository: Mail repository instance
        
    Returns:
        MailService: Configured mail service
    """
    try:
        logger.debug("Creating mail service instance")
        service = MailService(mail_repository)
        return service
    except Exception as e:
        logger.error(f"Error creating mail service: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize mail service"
        )


def get_shared_mailbox_repository(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> SharedMailboxRepository:
    """Get shared mailbox repository with access token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        SharedMailboxRepository: Configured shared mailbox repository
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token = credentials.credentials
    return SharedMailboxRepository(access_token)


async def get_voice_attachment_repository(
    db_session: AsyncSession = Depends(get_async_db)
) -> VoiceAttachmentRepository:
    """Get voice attachment repository with database session.
    
    Args:
        db_session: Database session
        
    Returns:
        VoiceAttachmentRepository: Configured voice attachment repository
    """
    return VoiceAttachmentRepository(db_session)


def get_blob_service() -> AzureBlobService:
    """Get Azure blob service instance.
    
    Returns:
        AzureBlobService: Configured blob service
    """
    return azure_blob_service


def get_voice_attachment_service(
    mail_service: MailService = Depends(get_mail_service),
    mail_repository: MailRepository = Depends(get_mail_repository),
    voice_attachment_repository: VoiceAttachmentRepository = Depends(get_voice_attachment_repository),
    blob_service: AzureBlobService = Depends(get_blob_service),
    shared_mailbox_repository: Optional[SharedMailboxRepository] = Depends(get_shared_mailbox_repository)
) -> VoiceAttachmentService:
    """Get voice attachment service with dependencies.
    
    Args:
        mail_service: Mail service instance
        mail_repository: Mail repository instance
        voice_attachment_repository: Voice attachment repository instance
        blob_service: Azure blob service instance
        shared_mailbox_repository: Optional shared mailbox repository instance
        
    Returns:
        VoiceAttachmentService: Configured voice attachment service
    """
    return VoiceAttachmentService(
        mail_service=mail_service,
        mail_repository=mail_repository,
        voice_attachment_repository=voice_attachment_repository,
        blob_service=blob_service,
        shared_mailbox_repository=shared_mailbox_repository
    )