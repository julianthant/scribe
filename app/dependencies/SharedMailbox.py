"""
shared_mailbox.py - Shared Mailbox Service Dependencies

Provides FastAPI dependency injection functions for shared mailbox services and repositories.
This module handles:
- get_shared_mailbox_service(): Creates SharedMailboxService instances with authentication
- get_shared_mailbox_repository(): Creates repository instances with access tokens
- User permission validation for shared mailbox access
- Service and repository lifecycle management
- Authentication token propagation to Graph API calls

These dependencies ensure that shared mailbox operations are properly authenticated
and that users have appropriate permissions for the requested mailbox operations.
"""

from typing import Optional, List
import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.repositories.SharedMailboxRepository import SharedMailboxRepository
from app.services.SharedMailboxService import SharedMailboxService
from app.dependencies.Auth import get_current_user
from app.models.AuthModel import UserInfo
from app.core.Exceptions import AuthenticationError

logger = logging.getLogger(__name__)


async def get_shared_mailbox_repository(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> SharedMailboxRepository:
    """Get shared mailbox repository instance with current user's access token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        SharedMailboxRepository: Repository instance configured with user's token
        
    Raises:
        HTTPException: If repository creation fails
    """
    try:
        # Extract access token from credentials
        logger.info(f"Shared mailbox dependency - credentials: {credentials is not None}")
        
        if not credentials:
            logger.error("No credentials available for shared mailbox operations")
            raise HTTPException(
                status_code=401,
                detail="Authentication required for shared mailbox operations"
            )
        
        access_token = credentials.credentials
        logger.info(f"Shared mailbox dependency - access_token length: {len(access_token) if access_token else 0}")
        
        if not access_token:
            logger.error("No access token available for shared mailbox operations")
            raise HTTPException(
                status_code=401,
                detail="Access token required for shared mailbox operations"
            )
        
        repository = SharedMailboxRepository(access_token)
        return repository
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create shared mailbox repository: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize shared mailbox repository"
        )


async def get_shared_mailbox_service(
    shared_mailbox_repository: SharedMailboxRepository = Depends(get_shared_mailbox_repository)
) -> SharedMailboxService:
    """Get shared mailbox service instance with injected repository.
    
    Args:
        shared_mailbox_repository: Injected repository instance
        
    Returns:
        SharedMailboxService: Service instance with business logic
        
    Raises:
        HTTPException: If service creation fails
    """
    try:
        service = SharedMailboxService(shared_mailbox_repository)
        return service
        
    except Exception as e:
        logger.error(f"Failed to create shared mailbox service: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize shared mailbox service"
        )


async def validate_shared_mailbox_access(
    email_address: str,
    operation: str = "read",
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> bool:
    """Validate user access to a specific shared mailbox for an operation.
    
    Args:
        email_address: Shared mailbox email address
        operation: Operation type (read, write, send, manage)
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        bool: True if access is allowed
        
    Raises:
        HTTPException: If access is denied or validation fails
    """
    try:
        # This would implement more sophisticated access validation
        # For now, we'll use the service's internal validation
        await shared_mailbox_service._validate_mailbox_access(email_address, operation)
        return True
        
    except AuthenticationError as e:
        logger.error(f"Access validation failed for {email_address}: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error validating access: {str(e)}")
        raise HTTPException(status_code=403, detail="Access denied")


async def get_shared_mailbox_with_access_check(
    email_address: str,
    operation: str = "read",
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> str:
    """Get shared mailbox email address after validating access.
    
    Args:
        email_address: Shared mailbox email address
        operation: Required operation type
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        str: Validated email address
        
    Raises:
        HTTPException: If access is denied or mailbox not found
    """
    try:
        # Validate that the mailbox exists and user has access
        await shared_mailbox_service.get_shared_mailbox_details(email_address)
        
        # Validate specific operation access
        await validate_shared_mailbox_access(
            email_address, operation, current_user, shared_mailbox_service
        )
        
        return email_address
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate mailbox access: {str(e)}")
        raise HTTPException(status_code=403, detail="Mailbox access denied")


# Convenience dependencies for specific operations
async def get_shared_mailbox_read_access(
    email_address: str,
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> str:
    """Validate read access to shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        str: Validated email address
        
    Raises:
        HTTPException: If read access is denied
    """
    return await get_shared_mailbox_with_access_check(
        email_address, "read", current_user, shared_mailbox_service
    )


async def get_shared_mailbox_write_access(
    email_address: str,
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> str:
    """Validate write access to shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        str: Validated email address
        
    Raises:
        HTTPException: If write access is denied
    """
    return await get_shared_mailbox_with_access_check(
        email_address, "write", current_user, shared_mailbox_service
    )


async def get_shared_mailbox_send_access(
    email_address: str,
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> str:
    """Validate send access to shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        str: Validated email address
        
    Raises:
        HTTPException: If send access is denied
    """
    return await get_shared_mailbox_with_access_check(
        email_address, "send", current_user, shared_mailbox_service
    )


async def get_shared_mailbox_manage_access(
    email_address: str,
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> str:
    """Validate manage access to shared mailbox.
    
    Args:
        email_address: Shared mailbox email address
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        str: Validated email address
        
    Raises:
        HTTPException: If manage access is denied
    """
    return await get_shared_mailbox_with_access_check(
        email_address, "manage", current_user, shared_mailbox_service
    )


# Additional utility dependencies
async def get_accessible_shared_mailbox_addresses(
    current_user: UserInfo = Depends(get_current_user),
    shared_mailbox_service: SharedMailboxService = Depends(get_shared_mailbox_service)
) -> List[str]:
    """Get list of shared mailbox email addresses the user can access.
    
    Args:
        current_user: Current authenticated user
        shared_mailbox_service: Shared mailbox service instance
        
    Returns:
        List[str]: Email addresses of accessible shared mailboxes
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        response = await shared_mailbox_service.get_accessible_shared_mailboxes()
        return [mailbox.emailAddress for mailbox in response.value]
        
    except Exception as e:
        logger.error(f"Failed to get accessible mailbox addresses: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve accessible mailboxes"
        )