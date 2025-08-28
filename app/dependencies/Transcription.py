"""
Transcription.py - Transcription Dependency Injection

Provides FastAPI dependency injection for transcription-related services and repositories.
This module handles:
- TranscriptionRepository dependency
- TranscriptionService dependency
- VoiceAttachmentRepository integration for transcription workflow

All dependencies follow the standard FastAPI dependency injection pattern
and ensure proper database session management.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.Database import get_async_db
from app.repositories.TranscriptionRepository import TranscriptionRepository
from app.repositories.VoiceAttachmentRepository import VoiceAttachmentRepository
from app.repositories.ExcelSyncRepository import ExcelSyncRepository
from app.services.TranscriptionService import TranscriptionService
from app.services.ExcelTranscriptionSyncService import ExcelTranscriptionSyncService
from app.core.config import settings


def get_transcription_repository(
    db_session: AsyncSession = Depends(get_async_db)
) -> TranscriptionRepository:
    """
    Get TranscriptionRepository instance.
    
    Args:
        db_session: Database session
        
    Returns:
        TranscriptionRepository instance
    """
    return TranscriptionRepository(db_session)


def get_voice_attachment_repository(
    db_session: AsyncSession = Depends(get_async_db)
) -> VoiceAttachmentRepository:
    """
    Get VoiceAttachmentRepository instance for transcription workflow.
    
    Args:
        db_session: Database session
        
    Returns:
        VoiceAttachmentRepository instance
    """
    return VoiceAttachmentRepository(db_session)


def get_excel_sync_repository(
    db_session: AsyncSession = Depends(get_async_db)
) -> ExcelSyncRepository:
    """
    Get ExcelSyncRepository instance.
    
    Args:
        db_session: Database session
        
    Returns:
        ExcelSyncRepository instance
    """
    return ExcelSyncRepository(db_session)


def get_excel_sync_service(
    transcription_repository: TranscriptionRepository = Depends(get_transcription_repository),
    excel_sync_repository: ExcelSyncRepository = Depends(get_excel_sync_repository)
) -> ExcelTranscriptionSyncService:
    """
    Get ExcelTranscriptionSyncService instance with required dependencies.
    
    Args:
        transcription_repository: TranscriptionRepository instance
        excel_sync_repository: ExcelSyncRepository instance
        
    Returns:
        ExcelTranscriptionSyncService instance
    """
    return ExcelTranscriptionSyncService(
        transcription_repository=transcription_repository,
        excel_sync_repository=excel_sync_repository
    )


def get_transcription_service(
    transcription_repository: TranscriptionRepository = Depends(get_transcription_repository),
    voice_attachment_repository: VoiceAttachmentRepository = Depends(get_voice_attachment_repository),
    excel_sync_service: ExcelTranscriptionSyncService = Depends(get_excel_sync_service)
) -> TranscriptionService:
    """
    Get TranscriptionService instance with required dependencies.
    
    Args:
        transcription_repository: TranscriptionRepository instance
        voice_attachment_repository: VoiceAttachmentRepository instance
        excel_sync_service: ExcelTranscriptionSyncService instance
        
    Returns:
        TranscriptionService instance
    """
    # Only inject Excel sync service if it's enabled
    excel_sync = excel_sync_service if getattr(settings, 'excel_sync_enabled', True) else None
    
    return TranscriptionService(
        transcription_repository=transcription_repository,
        voice_attachment_repository=voice_attachment_repository,
        excel_sync_service=excel_sync
    )