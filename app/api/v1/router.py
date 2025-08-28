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

from app.api.v1.endpoints import auth, Mail, SharedMailbox, Transcription, VoiceAttachment, ExcelSync

router = APIRouter()

router.include_router(auth.router)
router.include_router(Mail.router)
router.include_router(SharedMailbox.router)
router.include_router(Transcription.router)
router.include_router(VoiceAttachment.router)
router.include_router(ExcelSync.router)