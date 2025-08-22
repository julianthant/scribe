"""
router.py - API v1 Main Router

Aggregates and configures all v1 API endpoints into a single router.
This module:
- Imports endpoint routers from the endpoints package
- Creates the main v1 APIRouter instance
- Includes authentication, mail, and shared mailbox endpoint routers
- Serves as the central routing configuration for API version 1

The router is included in the main FastAPI application with the /api/v1 prefix.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, mail, shared_mailbox

router = APIRouter()

router.include_router(auth.router)
router.include_router(mail.router)
router.include_router(shared_mailbox.router)