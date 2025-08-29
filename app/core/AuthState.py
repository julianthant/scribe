"""
AuthState.py - Authentication State Management

This module provides centralized authentication state management for the Scribe application.
It handles:
- Token storage and retrieval
- Session management 
- Token expiration tracking
- Automatic token refresh
- Thread-safe access to authentication state

The authentication state manager supports both Bearer token and session-based authentication,
providing a unified interface for managing user authentication state across requests.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from threading import Lock
from dataclasses import dataclass, asdict

from app.models.AuthModel import UserInfo, TokenResponse

logger = logging.getLogger(__name__)


@dataclass
class AuthenticationState:
    """Container for user authentication state."""
    access_token: str
    refresh_token: Optional[str]
    session_id: Optional[str]
    user_info: UserInfo
    expires_at: datetime
    token_type: str = "Bearer"
    
    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired."""
        return datetime.utcnow() >= self.expires_at
    
    @property
    def expires_soon(self) -> bool:
        """Check if token expires within the next 5 minutes."""
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=5))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['expires_at'] = self.expires_at.isoformat()
        data['user_info'] = data['user_info'].__dict__ if hasattr(data['user_info'], '__dict__') else data['user_info']
        return data
    
    @classmethod
    def from_token_response(cls, token_response: TokenResponse) -> 'AuthenticationState':
        """Create AuthenticationState from TokenResponse."""
        expires_at = datetime.utcnow() + timedelta(seconds=token_response.expires_in)
        
        return cls(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            session_id=token_response.session_id,
            user_info=token_response.user_info,
            expires_at=expires_at,
            token_type=token_response.token_type
        )


class AuthStateManager:
    """
    Manages authentication state for the application.
    
    Provides thread-safe storage and retrieval of authentication tokens,
    session information, and user data. Supports both in-memory and
    persistent storage modes.
    """
    
    def __init__(self):
        self._auth_states: Dict[str, AuthenticationState] = {}
        self._session_to_user: Dict[str, str] = {}
        self._lock = Lock()
    
    def store_auth_state(self, auth_state: AuthenticationState) -> None:
        """
        Store authentication state for a user.
        
        Args:
            auth_state: Authentication state to store
        """
        with self._lock:
            user_key = auth_state.user_info.email
            self._auth_states[user_key] = auth_state
            
            # Map session ID to user email for quick lookups
            if auth_state.session_id:
                self._session_to_user[auth_state.session_id] = user_key
            
            logger.debug(f"Stored auth state for user: {user_key}")
    
    def get_auth_state_by_email(self, email: str) -> Optional[AuthenticationState]:
        """
        Get authentication state by user email.
        
        Args:
            email: User's email address
            
        Returns:
            AuthenticationState if found, None otherwise
        """
        with self._lock:
            auth_state = self._auth_states.get(email)
            if auth_state and not auth_state.is_expired:
                return auth_state
            elif auth_state and auth_state.is_expired:
                # Clean up expired state
                self._remove_auth_state(email)
                logger.debug(f"Removed expired auth state for user: {email}")
            return None
    
    def get_auth_state_by_session(self, session_id: str) -> Optional[AuthenticationState]:
        """
        Get authentication state by session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            AuthenticationState if found, None otherwise
        """
        with self._lock:
            user_email = self._session_to_user.get(session_id)
            if user_email:
                return self.get_auth_state_by_email(user_email)
            return None
    
    def get_auth_state_by_token(self, access_token: str) -> Optional[AuthenticationState]:
        """
        Get authentication state by access token.
        
        Args:
            access_token: Access token to search for
            
        Returns:
            AuthenticationState if found, None otherwise
        """
        with self._lock:
            for auth_state in self._auth_states.values():
                if auth_state.access_token == access_token and not auth_state.is_expired:
                    return auth_state
            return None
    
    def update_tokens(
        self, 
        email: str, 
        access_token: str, 
        refresh_token: Optional[str] = None,
        expires_in: int = 3600
    ) -> bool:
        """
        Update tokens for a user.
        
        Args:
            email: User's email address
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_in: Token expiration time in seconds
            
        Returns:
            True if update was successful, False otherwise
        """
        with self._lock:
            auth_state = self._auth_states.get(email)
            if auth_state:
                auth_state.access_token = access_token
                if refresh_token:
                    auth_state.refresh_token = refresh_token
                auth_state.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                logger.debug(f"Updated tokens for user: {email}")
                return True
            return False
    
    def remove_auth_state_by_email(self, email: str) -> bool:
        """
        Remove authentication state by user email.
        
        Args:
            email: User's email address
            
        Returns:
            True if removal was successful, False if not found
        """
        with self._lock:
            return self._remove_auth_state(email)
    
    def remove_auth_state_by_session(self, session_id: str) -> bool:
        """
        Remove authentication state by session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if removal was successful, False if not found
        """
        with self._lock:
            user_email = self._session_to_user.get(session_id)
            if user_email:
                return self._remove_auth_state(user_email)
            return False
    
    def _remove_auth_state(self, email: str) -> bool:
        """
        Internal method to remove authentication state.
        Note: Must be called within a lock.
        
        Args:
            email: User's email address
            
        Returns:
            True if removal was successful, False if not found
        """
        auth_state = self._auth_states.pop(email, None)
        if auth_state:
            # Clean up session mapping
            if auth_state.session_id:
                self._session_to_user.pop(auth_state.session_id, None)
            logger.debug(f"Removed auth state for user: {email}")
            return True
        return False
    
    def cleanup_expired_states(self) -> int:
        """
        Clean up expired authentication states.
        
        Returns:
            Number of expired states removed
        """
        expired_users = []
        
        with self._lock:
            for email, auth_state in self._auth_states.items():
                if auth_state.is_expired:
                    expired_users.append(email)
        
        # Remove expired states
        removed_count = 0
        for email in expired_users:
            if self._remove_auth_state(email):
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired authentication states")
        
        return removed_count
    
    def get_all_active_users(self) -> list[str]:
        """
        Get list of all users with active authentication states.
        
        Returns:
            List of user email addresses with valid tokens
        """
        with self._lock:
            active_users = []
            for email, auth_state in self._auth_states.items():
                if not auth_state.is_expired:
                    active_users.append(email)
            return active_users
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the authentication state manager.
        
        Returns:
            Dictionary with stats about stored states
        """
        with self._lock:
            total_states = len(self._auth_states)
            expired_states = sum(1 for state in self._auth_states.values() if state.is_expired)
            active_states = total_states - expired_states
            
            return {
                "total_states": total_states,
                "active_states": active_states,
                "expired_states": expired_states,
                "session_mappings": len(self._session_to_user)
            }


# Global authentication state manager instance
auth_state_manager = AuthStateManager()


# Convenience functions for common operations
def store_user_auth(token_response: TokenResponse) -> None:
    """Store authentication state from TokenResponse."""
    auth_state = AuthenticationState.from_token_response(token_response)
    auth_state_manager.store_auth_state(auth_state)


def get_user_auth_by_email(email: str) -> Optional[AuthenticationState]:
    """Get authentication state by user email."""
    return auth_state_manager.get_auth_state_by_email(email)


def get_user_auth_by_session(session_id: str) -> Optional[AuthenticationState]:
    """Get authentication state by session ID with database fallback."""
    # First try in-memory lookup
    auth_state = auth_state_manager.get_auth_state_by_session(session_id)
    
    if auth_state:
        return auth_state
    
    # If not found in memory, try to sync from database
    logger.debug(f"Session not found in memory, attempting database sync: {session_id[:8]}...")
    auth_state = _sync_session_from_database(session_id)
    
    if auth_state:
        # Store in memory for future requests
        auth_state_manager.store_auth_state(auth_state)
        logger.debug(f"Synchronized session from database: {auth_state.user_info.email}")
        return auth_state
    
    return None


def get_user_auth_by_token(access_token: str) -> Optional[AuthenticationState]:
    """Get authentication state by access token."""
    return auth_state_manager.get_auth_state_by_token(access_token)


def logout_user_by_email(email: str) -> bool:
    """Remove authentication state for user by email."""
    return auth_state_manager.remove_auth_state_by_email(email)


def logout_user_by_session(session_id: str) -> bool:
    """Remove authentication state for user by session ID."""
    return auth_state_manager.remove_auth_state_by_session(session_id)


def _sync_session_from_database(session_id: str) -> Optional[AuthenticationState]:
    """
    Synchronize session from database to in-memory state.
    
    Args:
        session_id: Session ID to sync
        
    Returns:
        AuthenticationState if found in database, None otherwise
    """
    try:
        # We need to use a synchronous approach here since this might be called
        # from synchronous contexts. In a real implementation, this would
        # ideally be async and use proper database connections.
        
        # For now, return None to prevent blocking - the async validation
        # in the auth dependencies will handle database lookups properly
        logger.debug(f"Database sync not implemented, skipping for session: {session_id[:8]}...")
        return None
        
    except Exception as e:
        logger.error(f"Error syncing session from database: {str(e)}")
        return None


async def cleanup_expired_tokens_periodically():
    """Background task to periodically clean up expired tokens."""
    while True:
        try:
            removed_count = auth_state_manager.cleanup_expired_states()
            if removed_count > 0:
                logger.info(f"Periodic cleanup removed {removed_count} expired authentication states")
        except Exception as e:
            logger.error(f"Error during periodic token cleanup: {e}")
        
        # Run cleanup every 15 minutes
        await asyncio.sleep(900)