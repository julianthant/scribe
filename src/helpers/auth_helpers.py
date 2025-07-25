"""
Authentication helper functions for token management
"""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from azure.identity import ManagedIdentityCredential


def validate_token_expiry(token: str, buffer_minutes: int = 5) -> bool:
    """
    Check if a JWT token is valid and not expiring soon
    
    Args:
        token: JWT token to validate
        buffer_minutes: Minutes before expiry to consider token as expired
        
    Returns:
        bool: True if token is valid and not expiring soon
    """
    try:
        # Decode without verification to check expiry
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        if 'exp' not in decoded:
            return False
        
        # Check if token expires within buffer period
        exp_timestamp = decoded['exp']
        exp_datetime = datetime.fromtimestamp(exp_timestamp)
        buffer_time = datetime.now() + timedelta(minutes=buffer_minutes)
        
        return exp_datetime > buffer_time
        
    except Exception as e:
        logging.getLogger(__name__).warning(f"Token validation failed: {str(e)}")
        return False


def refresh_token_if_needed(current_token: Optional[str], 
                           token_refresh_func: callable,
                           buffer_minutes: int = 5) -> Optional[str]:
    """
    Refresh token if it's expired or expiring soon
    
    Args:
        current_token: Current access token
        token_refresh_func: Function to call for token refresh
        buffer_minutes: Minutes before expiry to refresh token
        
    Returns:
        Optional[str]: New token if refreshed, current token if still valid, None if refresh failed
    """
    logger = logging.getLogger(__name__)
    
    if not current_token:
        logger.info("🔑 No current token, attempting refresh...")
        try:
            return token_refresh_func()
        except Exception as e:
            logger.error(f"❌ Token refresh failed: {str(e)}")
            return None
    
    if validate_token_expiry(current_token, buffer_minutes):
        logger.debug("🔑 Current token is still valid")
        return current_token
    
    logger.info("🔄 Token is expired or expiring soon, refreshing...")
    try:
        new_token = token_refresh_func()
        if new_token:
            logger.info("✅ Token refreshed successfully")
            return new_token
        else:
            logger.warning("⚠️ Token refresh returned empty token")
            return current_token
    except Exception as e:
        logger.error(f"❌ Token refresh failed: {str(e)}")
        return current_token


def get_managed_identity_token(resource: str, credential: Optional[ManagedIdentityCredential] = None) -> Optional[str]:
    """
    Get access token using Managed Identity
    
    Args:
        resource: Azure resource to get token for
        credential: Optional pre-initialized credential
        
    Returns:
        Optional[str]: Access token if successful
    """
    logger = logging.getLogger(__name__)
    
    try:
        if not credential:
            credential = ManagedIdentityCredential()
        
        logger.debug(f"🔑 Getting managed identity token for resource: {resource}")
        token = credential.get_token(resource)
        
        if token and token.token:
            logger.info("✅ Managed identity token obtained successfully")
            return token.token
        else:
            logger.error("❌ Managed identity token request returned empty token")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get managed identity token: {str(e)}")
        return None
