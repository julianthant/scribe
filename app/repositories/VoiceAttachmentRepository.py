"""
VoiceAttachmentRepository.py - Voice Attachment Data Access Layer

Provides data access operations for voice attachment blob storage metadata.
This repository handles:
- Voice attachment metadata persistence
- Download history tracking
- Expiration and cleanup queries
- User and organization-based filtering
- Analytics and reporting queries

The VoiceAttachmentRepository class follows the repository pattern
for clean separation between business logic and data access.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging

from sqlalchemy import and_, or_, func, desc, asc, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.VoiceAttachment import VoiceAttachment, VoiceAttachmentDownload
from app.repositories.BaseRepository import BaseRepository
from app.core.Exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)


class VoiceAttachmentRepository:
    """Repository for voice attachment metadata operations."""

    def __init__(self, db_session: AsyncSession):
        """Initialize repository with database session."""
        self.db_session = db_session
    
    async def create_voice_attachment(
        self,
        user_id: str,
        azure_message_id: str,
        azure_attachment_id: str,
        blob_name: str,
        blob_container: str,
        original_filename: str,
        content_type: str,
        size_bytes: int,
        sender_email: str,
        subject: str,
        received_at: datetime,
        **optional_fields
    ) -> VoiceAttachment:
        """Create a new voice attachment record.
        
        Args:
            user_id: User who stored the attachment
            azure_message_id: Graph API message ID
            azure_attachment_id: Graph API attachment ID
            blob_name: Unique blob storage name
            blob_container: Blob storage container name
            original_filename: Original file name
            content_type: MIME content type
            size_bytes: File size in bytes
            sender_email: Email sender
            subject: Email subject
            received_at: Email received timestamp
            **optional_fields: Additional optional fields
            
        Returns:
            Created voice attachment
            
        Raises:
            ValidationError: If validation fails
            DatabaseError: If database operation fails
        """
        try:
            # Check if attachment already exists for this user
            existing = await self.get_by_graph_api_ids(
                user_id, azure_message_id, azure_attachment_id
            )
            if existing:
                raise ValidationError(
                    f"Voice attachment already exists for message {azure_message_id}, attachment {azure_attachment_id}",
                    error_code="VOICE_ATTACHMENT_EXISTS"
                )
            
            # Create voice attachment
            voice_attachment = VoiceAttachment(
                user_id=user_id,
                azure_message_id=azure_message_id,
                azure_attachment_id=azure_attachment_id,
                blob_name=blob_name,
                blob_container=blob_container,
                original_filename=original_filename,
                content_type=content_type,
                size_bytes=size_bytes,
                sender_email=sender_email,
                subject=subject,
                received_at=received_at,
                **optional_fields
            )
            
            self.db_session.add(voice_attachment)
            await self.db_session.commit()
            await self.db_session.refresh(voice_attachment)
            return voice_attachment
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create voice attachment: {str(e)}")
            raise DatabaseError(f"Failed to create voice attachment: {str(e)}")
    
    async def get_by_blob_name(
        self,
        blob_name: str,
        user_id: Optional[str] = None
    ) -> Optional[VoiceAttachment]:
        """Get voice attachment by blob name.
        
        Args:
            blob_name: Blob storage name
            user_id: Optional user filter
            
        Returns:
            Voice attachment if found
        """
        try:
            stmt = select(VoiceAttachment).where(VoiceAttachment.blob_name == blob_name)
            
            if user_id:
                stmt = stmt.where(VoiceAttachment.user_id == user_id)
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get voice attachment by blob name {blob_name}: {str(e)}")
            return None
    
    async def get_by_graph_api_ids(
        self,
        user_id: str,
        azure_message_id: str,
        azure_attachment_id: str
    ) -> Optional[VoiceAttachment]:
        """Get voice attachment by Graph API identifiers.
        
        Args:
            user_id: User ID
            azure_message_id: Graph API message ID
            azure_attachment_id: Graph API attachment ID
            
        Returns:
            Voice attachment if found
        """
        try:
            stmt = select(VoiceAttachment).where(
                and_(
                    VoiceAttachment.user_id == user_id,
                    VoiceAttachment.azure_message_id == azure_message_id,
                    VoiceAttachment.azure_attachment_id == azure_attachment_id
                )
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get voice attachment by Graph API IDs: {str(e)}")
            return None
    
    async def list_user_attachments(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status_filter: Optional[str] = None,
        content_type_filter: Optional[str] = None,
        order_by: str = "received_at",
        order_direction: str = "desc"
    ) -> Tuple[List[VoiceAttachment], int]:
        """List voice attachments for a user.
        
        Args:
            user_id: User ID
            limit: Maximum results to return
            offset: Number of results to skip
            status_filter: Optional storage status filter
            content_type_filter: Optional content type filter
            order_by: Field to order by
            order_direction: Order direction (asc/desc)
            
        Returns:
            Tuple of (attachments list, total count)
        """
        try:
            # Build base query
            stmt = select(VoiceAttachment).where(VoiceAttachment.user_id == user_id)
            count_stmt = select(func.count(VoiceAttachment.id)).where(VoiceAttachment.user_id == user_id)
            
            # Apply filters
            if status_filter:
                stmt = stmt.where(VoiceAttachment.storage_status == status_filter)
                count_stmt = count_stmt.where(VoiceAttachment.storage_status == status_filter)
            
            if content_type_filter:
                stmt = stmt.where(VoiceAttachment.content_type.like(f"{content_type_filter}%"))
                count_stmt = count_stmt.where(VoiceAttachment.content_type.like(f"{content_type_filter}%"))
            
            # Apply ordering
            order_column = getattr(VoiceAttachment, order_by, VoiceAttachment.received_at)
            if order_direction.lower() == "desc":
                stmt = stmt.order_by(desc(order_column))
            else:
                stmt = stmt.order_by(asc(order_column))
            
            # Apply pagination
            stmt = stmt.limit(limit).offset(offset)
            
            # Execute queries
            result = await self.db_session.execute(stmt)
            attachments = result.scalars().all()
            
            count_result = await self.db_session.execute(count_stmt)
            total_count = count_result.scalar() or 0
            
            logger.info(f"Listed {len(attachments)} voice attachments for user {user_id} (total: {total_count})")
            return list(attachments), total_count
            
        except Exception as e:
            logger.error(f"Failed to list user attachments: {str(e)}")
            raise DatabaseError(f"Failed to list user attachments: {str(e)}")
    
    
    async def get_expired_attachments(
        self,
        cutoff_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[VoiceAttachment]:
        """Get expired voice attachments for cleanup.
        
        Args:
            cutoff_date: Date before which attachments are considered expired
            limit: Maximum results to return
            
        Returns:
            List of expired attachments
        """
        try:
            if cutoff_date is None:
                # Default to 90 days ago
                cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            stmt = select(VoiceAttachment).where(
                or_(
                    VoiceAttachment.expires_at <= datetime.utcnow(),
                    VoiceAttachment.created_at <= cutoff_date
                )
            ).where(
                VoiceAttachment.storage_status == "stored"
            ).limit(limit)
            
            result = await self.db_session.execute(stmt)
            expired_attachments = result.scalars().all()
            
            logger.info(f"Found {len(expired_attachments)} expired voice attachments")
            return list(expired_attachments)
            
        except Exception as e:
            logger.error(f"Failed to get expired attachments: {str(e)}")
            raise DatabaseError(f"Failed to get expired attachments: {str(e)}")
    
    async def mark_as_deleted(
        self,
        attachment_id: str
    ) -> bool:
        """Mark voice attachment as deleted.
        
        Args:
            attachment_id: Attachment ID
            
        Returns:
            True if successful
        """
        try:
            stmt = update(VoiceAttachment).where(
                VoiceAttachment.id == attachment_id
            ).values(
                storage_status="deleted",
                updated_at=datetime.utcnow()
            )
            
            result = await self.db_session.execute(stmt)
            return result.rowcount > 0
            
        except Exception as e:
            logger.error(f"Failed to mark attachment as deleted: {str(e)}")
            raise DatabaseError(f"Failed to mark attachment as deleted: {str(e)}")
    
    async def update_download_stats(
        self,
        attachment_id: str,
        increment_count: bool = True
    ) -> bool:
        """Update download statistics for an attachment.
        
        Args:
            attachment_id: Attachment ID
            increment_count: Whether to increment download count
            
        Returns:
            True if successful
        """
        try:
            updates = {
                "last_downloaded_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if increment_count:
                stmt = update(VoiceAttachment).where(
                    VoiceAttachment.id == attachment_id
                ).values(
                    download_count=VoiceAttachment.download_count + 1,
                    **updates
                )
            else:
                stmt = update(VoiceAttachment).where(
                    VoiceAttachment.id == attachment_id
                ).values(**updates)
            
            result = await self.db_session.execute(stmt)
            return result.rowcount > 0
            
        except Exception as e:
            logger.error(f"Failed to update download stats: {str(e)}")
            raise DatabaseError(f"Failed to update download stats: {str(e)}")
    
    async def get_statistics(
        self,
        user_id: Optional[str] = None,
        days_ago: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get voice attachment statistics.
        
        Args:
            user_id: Optional user filter
            days_ago: Optional filter for recent data
            
        Returns:
            Statistics dictionary
        """
        try:
            # Build base query conditions
            conditions = []
            if user_id:
                conditions.append(VoiceAttachment.user_id == user_id)
            if days_ago is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
                conditions.append(VoiceAttachment.received_at >= cutoff_date)
            
            # Build query with all conditions
            base_filter = and_(*conditions) if conditions else True
            
            # Get basic counts
            count_stmt = select(
                func.count(VoiceAttachment.id).label("total_count"),
                func.count(VoiceAttachment.id).filter(VoiceAttachment.storage_status == "stored").label("stored_count"),
                func.count(VoiceAttachment.id).filter(VoiceAttachment.storage_status == "deleted").label("deleted_count"),
                func.sum(VoiceAttachment.size_bytes).label("total_size"),
                func.sum(VoiceAttachment.download_count).label("total_downloads"),
                func.avg(VoiceAttachment.size_bytes).label("avg_size"),
                func.max(VoiceAttachment.received_at).label("latest_received"),
                func.min(VoiceAttachment.received_at).label("earliest_received")
            ).where(base_filter)
            
            result = await self.db_session.execute(count_stmt)
            stats_row = result.one()
            
            # Get content type breakdown
            content_type_stmt = select(
                VoiceAttachment.content_type,
                func.count(VoiceAttachment.id).label("count"),
                func.sum(VoiceAttachment.size_bytes).label("total_size")
            ).where(base_filter).group_by(VoiceAttachment.content_type)
            
            content_type_result = await self.db_session.execute(content_type_stmt)
            content_types = {
                row.content_type: {
                    "count": row.count,
                    "total_size": row.total_size or 0
                }
                for row in content_type_result
            }
            
            statistics = {
                "total_attachments": stats_row.total_count or 0,
                "stored_attachments": stats_row.stored_count or 0,
                "deleted_attachments": stats_row.deleted_count or 0,
                "total_size_bytes": stats_row.total_size or 0,
                "total_size_mb": round((stats_row.total_size or 0) / (1024 * 1024), 2),
                "total_downloads": stats_row.total_downloads or 0,
                "average_size_bytes": round(stats_row.avg_size or 0),
                "average_size_mb": round((stats_row.avg_size or 0) / (1024 * 1024), 2),
                "latest_received": stats_row.latest_received.isoformat() if stats_row.latest_received else None,
                "earliest_received": stats_row.earliest_received.isoformat() if stats_row.earliest_received else None,
                "content_types": content_types
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            raise DatabaseError(f"Failed to get statistics: {str(e)}")
    
    # Download history methods
    
    async def record_download(
        self,
        attachment_id: str,
        user_id: str,
        download_method: str,
        download_size_bytes: int,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        download_duration_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> VoiceAttachmentDownload:
        """Record a voice attachment download.
        
        Args:
            attachment_id: Voice attachment ID
            user_id: User who downloaded
            download_method: Download method used
            download_size_bytes: Size of download
            client_ip: Optional client IP
            user_agent: Optional user agent
            download_duration_ms: Optional download duration
            success: Whether download was successful
            error_message: Optional error message
            
        Returns:
            Created download record
        """
        try:
            download = VoiceAttachmentDownload(
                attachment_id=attachment_id,
                user_id=user_id,
                download_method=download_method,
                download_size_bytes=download_size_bytes,
                client_ip=client_ip,
                user_agent=user_agent,
                download_duration_ms=download_duration_ms,
                success=success,
                error_message=error_message
            )
            
            self.db_session.add(download)
            await self.db_session.flush()
            
            # Update attachment download stats
            await self.update_download_stats(attachment_id)
            
            return download
            
        except Exception as e:
            logger.error(f"Failed to record download: {str(e)}")
            raise DatabaseError(f"Failed to record download: {str(e)}")
    
    async def get_download_history(
        self,
        attachment_id: str,
        limit: int = 100
    ) -> List[VoiceAttachmentDownload]:
        """Get download history for an attachment.
        
        Args:
            attachment_id: Attachment ID
            limit: Maximum results
            
        Returns:
            List of download records
        """
        try:
            stmt = select(VoiceAttachmentDownload).where(
                VoiceAttachmentDownload.attachment_id == attachment_id
            ).order_by(desc(VoiceAttachmentDownload.created_at)).limit(limit)
            
            result = await self.db_session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Failed to get download history: {str(e)}")
            raise DatabaseError(f"Failed to get download history: {str(e)}")