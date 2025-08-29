"""
router.py - API v1 Main Router

Aggregates and configures all v1 API endpoints into a single router.
This module:
- Imports endpoint routers from the endpoints package
- Creates the main v1 APIRouter instance
- Includes all endpoint routers:
  - auth: Authentication endpoints
  - mail: General mail operations
  - SharedMailbox: Shared mailbox operations
  - Transcription: Voice transcription operations
  - VoiceAttachment: Voice attachment management
  - ExcelSync: Excel synchronization operations
- Serves as the central routing configuration for API version 1

The router is included in the main FastAPI application with the /api/v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import Auth
from app.api.v1.endpoints.mail import router as mail_router
from app.api.v1.endpoints.SharedMailbox import router as shared_mailbox_router
from app.api.v1.endpoints.Transcription import router as transcription_router
from app.api.v1.endpoints.VoiceAttachment import router as voice_attachment_router
from app.api.v1.endpoints.ExcelSync import router as excel_sync_router

router = APIRouter()

router.include_router(Auth.router)
router.include_router(mail_router)
router.include_router(shared_mailbox_router)
router.include_router(transcription_router)
router.include_router(voice_attachment_router)
router.include_router(excel_sync_router)