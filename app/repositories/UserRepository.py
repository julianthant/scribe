"""
UserRepository.py - User Data Access Layer

Provides data access operations for User, UserProfile, and Session entities.
This repository handles:
- User creation and retrieval by Azure ID
- User profile management
- Session management (create, update, revoke)
- Session cleanup and expiration handling

Following the established repository pattern with proper async session management.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.BaseRepository import BaseRepository
from app.db.models.User import User, UserProfile, Session, UserRole
from app.core.Exceptions import DatabaseError
from app.core.config import settings

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User, Dict[str, Any], Dict[str, Any]]):
    """Repository for User entity operations with profile and session management."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(User, db_session)
    
    def _determine_user_role(self, email: str) -> UserRole:
        """
        Determine user role based on email configuration.
        
        Args:
            email: User's email address
            
        Returns:
            UserRole: SUPERUSER if email is in superuser list, USER otherwise
        """
        try:
            superuser_emails = getattr(settings, 'superuser_emails', [])
            
            # Convert to lowercase for case-insensitive comparison
            email_lower = email.lower()
            superuser_emails_lower = [e.lower() for e in superuser_emails]
            
            if email_lower in superuser_emails_lower:
                logger.info(f"Assigning SUPERUSER role to {email}")
                return UserRole.SUPERUSER
            else:
                logger.debug(f"Assigning USER role to {email}")
                return UserRole.USER
                
        except Exception as e:
            logger.error(f"Error determining user role for {email}: {str(e)}")
            # Default to normal user if there's any error
            return UserRole.USER 
    
    async def update_user_role_if_changed(self, user: User) -> bool:
        """
        Check if user's role should be updated based on current configuration.
        
        Args:
            user: User instance to check
            
        Returns:
            bool: True if role was updated, False otherwise
        """
        try:
            expected_role = self._determine_user_role(user.email)
            
            if user.role != expected_role:
                old_role = user.role
                user.role = expected_role
                await self.db_session.commit()
                await self.db_session.refresh(user)
                
                logger.info(f"Updated user {user.email} role from {old_role.value} to {expected_role.value}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update user role for {user.email}: {str(e)}", exc_info=True)
            return False
    
    async def get_by_azure_id(self, azure_id: str) -> Optional[User]:
        """
        Get user by Azure AD ID with profile loaded.
        
        Args:
            azure_id: Azure AD object identifier
            
        Returns:
            User instance with profile loaded, or None if not found
        """
        try:
            result = await self.db_session.execute(
                select(User)
                .options(selectinload(User.profile))
                .where(User.azure_id == azure_id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get user by Azure ID {azure_id}: {str(e)}")
            return None
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address with profile loaded.
        
        Args:
            email: User's email address
            
        Returns:
            User instance with profile loaded, or None if not found
        """
        try:
            result = await self.db_session.execute(
                select(User)
                .options(selectinload(User.profile))
                .where(User.email == email)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {str(e)}")
            return None
    
    async def get_or_create_by_azure_id(
        self, 
        azure_id: str, 
        email: str
    ) -> User:
        """
        Get existing user by Azure ID or create a new one.
        
        Args:
            azure_id: Azure AD object identifier
            email: User's email address
            
        Returns:
            User instance (existing or newly created)
            
        Raises:
            DatabaseError: If user creation fails
        """
        try:
            # Try to find existing user
            user = await self.get_by_azure_id(azure_id)
            
            if user:
                # Update email if it changed
                if user.email != email:
                    user.email = email
                    await self.db_session.commit()
                    await self.db_session.refresh(user)
                    logger.info(f"Updated email for user {azure_id}: {email}")
                return user
            
            # Determine user role based on email
            user_role = self._determine_user_role(email)
            
            # Create new user
            user_data = {
                "azure_id": azure_id,
                "email": email,
                "is_active": True,
                "role": user_role
            }
            
            new_user = await self.create(user_data)
            logger.info(f"Created new user with Azure ID: {azure_id}, Role: {user_role.value}")
            return new_user
            
        except Exception as e:
            logger.error(f"Failed to get or create user {azure_id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                "Failed to get or create user",
                error_code="USER_GET_OR_CREATE_FAILED",
                details={"azure_id": azure_id, "email": email, "error": str(e)}
            )
    
    async def update_or_create_profile(
        self,
        user: User,
        profile_data: Dict[str, Any]
    ) -> UserProfile:
        """
        Update existing user profile or create a new one.
        
        Args:
            user: User instance
            profile_data: Profile information from Azure AD
            
        Returns:
            UserProfile instance (existing or newly created)
            
        Raises:
            DatabaseError: If profile update/creation fails
        """
        try:
            # Check if profile exists using explicit query to avoid lazy loading
            profile_query = select(UserProfile).where(UserProfile.user_id == user.id)
            profile_result = await self.db_session.execute(profile_query)
            existing_profile = profile_result.scalar_one_or_none()
            
            if existing_profile:
                # Update existing profile
                for key, value in profile_data.items():
                    if hasattr(existing_profile, key):
                        setattr(existing_profile, key, value)
                
                await self.db_session.commit()
                await self.db_session.refresh(existing_profile)
                logger.debug(f"Updated profile for user {user.id}")
                return existing_profile
            else:
                # Create new profile
                profile_data["user_id"] = user.id
                profile = UserProfile(**profile_data)
                
                self.db_session.add(profile)
                await self.db_session.commit()
                await self.db_session.refresh(profile)
                
                logger.debug(f"Created profile for user {user.id}")
                return profile
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update/create profile for user {user.id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                "Failed to update or create user profile",
                error_code="USER_PROFILE_UPDATE_FAILED",
                details={"user_id": user.id, "error": str(e)}
            )
    
    async def create_session(
        self,
        user: User,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Session:
        """
        Create a new user session.
        
        Args:
            user: User instance
            access_token: OAuth access token
            refresh_token: Optional OAuth refresh token
            expires_at: Token expiration timestamp
            ip_address: Optional client IP address
            user_agent: Optional client user agent
            
        Returns:
            Created Session instance
            
        Raises:
            DatabaseError: If session creation fails
        """
        try:
            session_data = {
                "user_id": user.id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "is_revoked": False,
                "ip_address": ip_address,
                "user_agent": user_agent
            }
            
            session = Session(**session_data)
            self.db_session.add(session)
            await self.db_session.commit()
            await self.db_session.refresh(session)
            
            logger.info(f"Created session for user {user.id}: {session.id}")
            return session
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to create session for user {user.id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                "Failed to create user session",
                error_code="SESSION_CREATE_FAILED",
                details={"user_id": user.id, "error": str(e)}
            )
    
    async def update_session(
        self,
        session_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[Session]:
        """
        Update session with new tokens and optional metadata.
        
        Args:
            session_id: Session ID to update
            access_token: New access token
            refresh_token: Optional new refresh token
            expires_at: Optional new expiration timestamp
            ip_address: Optional new IP address
            user_agent: Optional new user agent
            
        Returns:
            Updated Session instance or None if not found
            
        Raises:
            DatabaseError: If session update fails
        """
        try:
            update_data: Dict[str, Any] = {"access_token": access_token}
            
            if refresh_token:
                update_data["refresh_token"] = refresh_token
            if expires_at:
                update_data["expires_at"] = expires_at
            if ip_address:
                update_data["ip_address"] = ip_address
            if user_agent:
                update_data["user_agent"] = user_agent
            
            result = await self.db_session.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(**update_data)
                .returning(Session)
            )
            
            updated_session = result.scalar_one_or_none()
            if updated_session:
                await self.db_session.commit()
                await self.db_session.refresh(updated_session)
                logger.debug(f"Updated session {session_id}")
                return updated_session
            else:
                return None
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update session {session_id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                "Failed to update session",
                error_code="SESSION_UPDATE_FAILED",
                details={"session_id": session_id, "error": str(e)}
            )
    
    async def revoke_session(self, session_id: str) -> bool:
        """
        Revoke a user session.
        
        Args:
            session_id: Session ID to revoke
            
        Returns:
            True if session was revoked, False if not found
            
        Raises:
            DatabaseError: If session revocation fails
        """
        try:
            result = await self.db_session.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(is_revoked=True)
            )
            
            if result.rowcount > 0:
                await self.db_session.commit()
                logger.info(f"Revoked session {session_id}")
                return True
            else:
                return False
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to revoke session {session_id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                "Failed to revoke session",
                error_code="SESSION_REVOKE_FAILED",
                details={"session_id": session_id, "error": str(e)}
            )
    
    async def revoke_user_sessions(self, user_id: str) -> int:
        """
        Revoke all active sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of sessions revoked
            
        Raises:
            DatabaseError: If session revocation fails
        """
        try:
            result = await self.db_session.execute(
                update(Session)
                .where(and_(Session.user_id == user_id, Session.is_revoked == False))
                .values(is_revoked=True)
            )
            
            await self.db_session.commit()
            revoked_count = result.rowcount
            
            if revoked_count > 0:
                logger.info(f"Revoked {revoked_count} sessions for user {user_id}")
            
            return revoked_count
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to revoke sessions for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                "Failed to revoke user sessions",
                error_code="USER_SESSIONS_REVOKE_FAILED",
                details={"user_id": user_id, "error": str(e)}
            )
    
    async def get_active_sessions(self, user_id: str) -> List[Session]:
        """
        Get all active sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of active Session instances
        """
        try:
            result = await self.db_session.execute(
                select(Session)
                .where(and_(
                    Session.user_id == user_id,
                    Session.is_revoked == False,
                    Session.expires_at > datetime.utcnow()
                ))
                .order_by(Session.created_at.desc())
            )
            
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get active sessions for user {user_id}: {str(e)}")
            return []
    
    async def cleanup_expired_sessions(self, older_than_hours: int = 24) -> int:
        """
        Clean up expired and old revoked sessions.
        
        Args:
            older_than_hours: Remove sessions older than this many hours (default: 24)
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            
            # Remove sessions that are either:
            # 1. Expired (regardless of revoked status)
            # 2. Revoked and older than cutoff time
            result = await self.db_session.execute(
                select(Session.id)
                .where(
                    (Session.expires_at < datetime.utcnow()) |
                    (and_(Session.is_revoked == True, Session.created_at < cutoff_time))
                )
            )
            
            session_ids = [row[0] for row in result.fetchall()]
            
            if session_ids:
                # Delete the sessions
                from sqlalchemy import delete
                await self.db_session.execute(
                    delete(Session).where(Session.id.in_(session_ids))
                )
                await self.db_session.commit()
                
                logger.info(f"Cleaned up {len(session_ids)} expired sessions")
                return len(session_ids)
            else:
                return 0
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to cleanup expired sessions: {str(e)}", exc_info=True)
            return 0
    
    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """
        Get session by ID with user and user profile loaded.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session instance with user and profile loaded, or None if not found
        """
        try:
            result = await self.db_session.execute(
                select(Session)
                .options(selectinload(Session.user).selectinload(User.profile))
                .where(Session.id == session_id)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get session by ID {session_id}: {str(e)}")
            return None
    
    async def get_active_session_by_ip(self, user_id: str, ip_address: str) -> Optional[Session]:
        """
        Get active session for a user from a specific IP address.
        
        Args:
            user_id: User ID
            ip_address: Client IP address to match
            
        Returns:
            Active Session instance from the IP, or None if not found
        """
        try:
            result = await self.db_session.execute(
                select(Session)
                .options(selectinload(Session.user).selectinload(User.profile))
                .where(and_(
                    Session.user_id == user_id,
                    Session.ip_address == ip_address,
                    Session.is_revoked == False,
                    Session.expires_at > datetime.utcnow()
                ))
                .order_by(Session.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get active session by IP for user {user_id}, IP {ip_address}: {str(e)}")
            return None
    
    async def revoke_sessions_except_ip(self, user_id: str, keep_ip_address: str) -> int:
        """
        Revoke all active sessions for a user except those from a specific IP address.
        
        Args:
            user_id: User ID
            keep_ip_address: IP address to keep sessions for
            
        Returns:
            Number of sessions revoked
        """
        try:
            result = await self.db_session.execute(
                update(Session)
                .where(and_(
                    Session.user_id == user_id,
                    Session.is_revoked == False,
                    Session.ip_address != keep_ip_address
                ))
                .values(is_revoked=True)
            )
            
            await self.db_session.commit()
            revoked_count = result.rowcount
            
            if revoked_count > 0:
                logger.info(f"Revoked {revoked_count} sessions for user {user_id} from other IPs (kept IP: {keep_ip_address})")
            
            return revoked_count
                
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to revoke sessions except IP for user {user_id}: {str(e)}", exc_info=True)
            return 0