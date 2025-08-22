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

from app.services.mail_service import MailService
from app.services.voice_attachment_service import VoiceAttachmentService
from app.repositories.mail_repository import MailRepository
from app.repositories.shared_mailbox_repository import SharedMailboxRepository

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


def get_mail_repository(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> MailRepository:
    """Get mail repository with access token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        MailRepository: Configured mail repository
        
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
    return MailRepository(access_token)


def get_mail_service(
    mail_repository: MailRepository = Depends(get_mail_repository)
) -> MailService:
    """Get mail service with repository.
    
    Args:
        mail_repository: Mail repository instance
        
    Returns:
        MailService: Configured mail service
    """
    return MailService(mail_repository)


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


def get_voice_attachment_service(
    mail_service: MailService = Depends(get_mail_service),
    mail_repository: MailRepository = Depends(get_mail_repository),
    shared_mailbox_repository: Optional[SharedMailboxRepository] = Depends(get_shared_mailbox_repository)
) -> VoiceAttachmentService:
    """Get voice attachment service with dependencies.
    
    Args:
        mail_service: Mail service instance
        mail_repository: Mail repository instance
        shared_mailbox_repository: Optional shared mailbox repository instance
        
    Returns:
        VoiceAttachmentService: Configured voice attachment service
    """
    return VoiceAttachmentService(mail_service, mail_repository, shared_mailbox_repository)