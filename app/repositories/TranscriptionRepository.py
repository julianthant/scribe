"""
TranscriptionRepository.py - Voice Transcription Data Access Repository

Provides data access layer for voice transcription operations.
This repository handles:
- CRUD operations for transcription records
- Transcription segment and error management
- Query operations with filtering and pagination
- Statistics and analytics queries
- Bulk operations for batch processing

The TranscriptionRepository follows the repository pattern and provides
a clean interface between the business logic and database layers.
"""

from typing import List, Optional, Dict, Any, Tuple
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.models.Transcription import VoiceTranscription, TranscriptionSegment, TranscriptionError
from app.db.models.VoiceAttachment import VoiceAttachment
from app.core.Exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)


class TranscriptionRepository:
    """Repository for voice transcription data access."""

    def __init__(self, db_session: AsyncSession):
        """Initialize repository with database session."""
        self.db_session = db_session

    async def create_transcription(
        self,
        voice_attachment_id: str,
        user_id: str,
        transcript_text: str,
        model_name: str,
        language: Optional[str] = None,
        confidence_score: Optional[float] = None,
        avg_logprob: Optional[float] = None,
        compression_ratio: Optional[float] = None,
        no_speech_prob: Optional[float] = None,
        response_format: str = "verbose_json",
        has_word_timestamps: bool = False,
        has_segment_timestamps: bool = False,
        audio_duration_seconds: Optional[float] = None,
        processing_time_ms: Optional[int] = None,
        transcription_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        azure_request_id: Optional[str] = None,
        azure_model_deployment: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> VoiceTranscription:
        """
        Create a new transcription record.
        
        Args:
            voice_attachment_id: ID of the voice attachment
            user_id: ID of the user
            transcript_text: Transcribed text
            model_name: Name of the model used
            language: Language code (ISO-639-1)
            confidence_score: Overall confidence score (0-1)
            avg_logprob: Average log probability
            compression_ratio: Compression ratio
            no_speech_prob: Probability of no speech
            response_format: Response format used
            has_word_timestamps: Whether word timestamps are included
            has_segment_timestamps: Whether segment timestamps are included
            audio_duration_seconds: Duration of the audio
            processing_time_ms: Processing time in milliseconds
            transcription_prompt: Prompt used for transcription
            temperature: Sampling temperature used
            azure_request_id: Azure request ID
            azure_model_deployment: Azure model deployment name
            model_version: Model version used
            
        Returns:
            Created VoiceTranscription instance
            
        Raises:
            ValidationError: If validation fails
            DatabaseError: If database operation fails
        """
        try:
            transcription = VoiceTranscription(
                voice_attachment_id=voice_attachment_id,
                user_id=user_id,
                transcript_text=transcript_text,
                language=language,
                confidence_score=confidence_score,
                avg_logprob=avg_logprob,
                compression_ratio=compression_ratio,
                no_speech_prob=no_speech_prob,
                transcription_status="completed",
                model_name=model_name,
                model_version=model_version,
                response_format=response_format,
                has_word_timestamps=has_word_timestamps,
                has_segment_timestamps=has_segment_timestamps,
                audio_duration_seconds=audio_duration_seconds,
                processing_time_ms=processing_time_ms,
                transcription_prompt=transcription_prompt,
                temperature=temperature,
                azure_request_id=azure_request_id,
                azure_model_deployment=azure_model_deployment
            )
            
            self.db_session.add(transcription)
            await self.db_session.flush()  # Get the ID
            await self.db_session.refresh(transcription)
            
            logger.info(f"Created transcription {transcription.id} for voice attachment {voice_attachment_id}")
            return transcription
            
        except Exception as e:
            logger.error(f"Failed to create transcription: {str(e)}")
            raise DatabaseError(f"Failed to create transcription: {str(e)}")

    async def add_transcription_segments(
        self,
        transcription_id: str,
        segments: List[Dict[str, Any]]
    ) -> List[TranscriptionSegment]:
        """
        Add segments to a transcription.
        
        Args:
            transcription_id: ID of the transcription
            segments: List of segment dictionaries
            
        Returns:
            List of created TranscriptionSegment instances
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            segment_objects = []
            
            for i, segment in enumerate(segments):
                segment_obj = TranscriptionSegment(
                    transcription_id=transcription_id,
                    segment_index=i,
                    segment_type=segment.get("segment_type", "segment"),
                    start_time_seconds=segment["start"],
                    end_time_seconds=segment["end"],
                    duration_seconds=segment["end"] - segment["start"],
                    text=segment["text"],
                    confidence_score=segment.get("confidence"),
                    avg_logprob=segment.get("avg_logprob"),
                    compression_ratio=segment.get("compression_ratio"),
                    no_speech_prob=segment.get("no_speech_prob"),
                    token_count=len(segment.get("tokens", [])) if segment.get("tokens") else None,
                    seek_offset=segment.get("seek"),
                    temperature=segment.get("temperature")
                )
                segment_objects.append(segment_obj)
            
            self.db_session.add_all(segment_objects)
            await self.db_session.flush()
            
            logger.info(f"Added {len(segment_objects)} segments to transcription {transcription_id}")
            return segment_objects
            
        except Exception as e:
            logger.error(f"Failed to add transcription segments: {str(e)}")
            raise DatabaseError(f"Failed to add transcription segments: {str(e)}")

    async def create_transcription_error(
        self,
        voice_attachment_id: str,
        user_id: str,
        error_type: str,
        error_message: str,
        transcription_id: Optional[str] = None,
        error_code: Optional[str] = None,
        model_name: Optional[str] = None,
        audio_format: Optional[str] = None,
        audio_size_bytes: Optional[int] = None,
        azure_request_id: Optional[str] = None,
        http_status_code: Optional[int] = None,
        retry_count: int = 0
    ) -> TranscriptionError:
        """
        Create a transcription error record.
        
        Args:
            voice_attachment_id: ID of the voice attachment
            user_id: ID of the user
            error_type: Type of error
            error_message: Error message
            transcription_id: Optional transcription ID
            error_code: Optional error code
            model_name: Model name used
            audio_format: Audio format
            audio_size_bytes: Audio size in bytes
            azure_request_id: Azure request ID
            http_status_code: HTTP status code
            retry_count: Number of retries
            
        Returns:
            Created TranscriptionError instance
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            error = TranscriptionError(
                transcription_id=transcription_id,
                voice_attachment_id=voice_attachment_id,
                user_id=user_id,
                error_type=error_type,
                error_code=error_code,
                error_message=error_message,
                model_name=model_name,
                audio_format=audio_format,
                audio_size_bytes=audio_size_bytes,
                azure_request_id=azure_request_id,
                http_status_code=http_status_code,
                retry_count=retry_count
            )
            
            self.db_session.add(error)
            await self.db_session.flush()
            await self.db_session.refresh(error)
            
            logger.warning(f"Created transcription error {error.id} for voice attachment {voice_attachment_id}: {error_type}")
            return error
            
        except Exception as e:
            logger.error(f"Failed to create transcription error: {str(e)}")
            raise DatabaseError(f"Failed to create transcription error: {str(e)}")

    async def get_transcription_by_id(self, transcription_id: str, user_id: str) -> Optional[VoiceTranscription]:
        """
        Get transcription by ID for a specific user.
        
        Args:
            transcription_id: Transcription ID
            user_id: User ID
            
        Returns:
            VoiceTranscription instance or None
        """
        try:
            stmt = (
                select(VoiceTranscription)
                .options(
                    selectinload(VoiceTranscription.segments),
                    selectinload(VoiceTranscription.voice_attachment)
                )
                .where(
                    and_(
                        VoiceTranscription.id == transcription_id,
                        VoiceTranscription.user_id == user_id
                    )
                )
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get transcription {transcription_id}: {str(e)}")
            raise DatabaseError(f"Failed to get transcription: {str(e)}")

    async def get_transcription_by_voice_attachment(
        self, 
        voice_attachment_id: str, 
        user_id: str
    ) -> Optional[VoiceTranscription]:
        """
        Get transcription by voice attachment ID.
        
        Args:
            voice_attachment_id: Voice attachment ID
            user_id: User ID
            
        Returns:
            VoiceTranscription instance or None
        """
        try:
            stmt = (
                select(VoiceTranscription)
                .options(
                    selectinload(VoiceTranscription.segments),
                    selectinload(VoiceTranscription.voice_attachment)
                )
                .where(
                    and_(
                        VoiceTranscription.voice_attachment_id == voice_attachment_id,
                        VoiceTranscription.user_id == user_id
                    )
                )
            )
            
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get transcription for voice attachment {voice_attachment_id}: {str(e)}")
            raise DatabaseError(f"Failed to get transcription: {str(e)}")

    async def list_user_transcriptions(
        self,
        user_id: str,
        status_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        model_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_direction: str = "desc"
    ) -> Tuple[List[VoiceTranscription], int]:
        """
        List transcriptions for a user with filtering and pagination.
        
        Args:
            user_id: User ID
            status_filter: Filter by transcription status
            language_filter: Filter by language
            model_filter: Filter by model name
            limit: Maximum results to return
            offset: Number of results to skip
            order_by: Field to order by
            order_direction: Order direction ('asc' or 'desc')
            
        Returns:
            Tuple of (transcription list, total count)
        """
        try:
            # Build base query
            stmt = (
                select(VoiceTranscription)
                .options(
                    joinedload(VoiceTranscription.voice_attachment)
                )
                .where(VoiceTranscription.user_id == user_id)
            )
            
            # Apply filters
            if status_filter:
                stmt = stmt.where(VoiceTranscription.transcription_status == status_filter)
            
            if language_filter:
                stmt = stmt.where(VoiceTranscription.language == language_filter)
            
            if model_filter:
                stmt = stmt.where(VoiceTranscription.model_name == model_filter)
            
            # Get total count
            count_stmt = select(func.count(VoiceTranscription.id)).select_from(stmt.subquery())
            count_result = await self.db_session.execute(count_stmt)
            total_count = count_result.scalar() or 0
            
            # Apply ordering
            order_column = getattr(VoiceTranscription, order_by, VoiceTranscription.created_at)
            if order_direction.lower() == "desc":
                stmt = stmt.order_by(desc(order_column))
            else:
                stmt = stmt.order_by(asc(order_column))
            
            # Apply pagination
            stmt = stmt.offset(offset).limit(limit)
            
            # Execute query
            result = await self.db_session.execute(stmt)
            transcriptions = list(result.scalars().all())
            
            return transcriptions, total_count
            
        except Exception as e:
            logger.error(f"Failed to list user transcriptions: {str(e)}")
            raise DatabaseError(f"Failed to list transcriptions: {str(e)}")

    async def update_transcription_status(
        self,
        transcription_id: str,
        status: str,
        user_id: str
    ) -> Optional[VoiceTranscription]:
        """
        Update transcription status.
        
        Args:
            transcription_id: Transcription ID
            status: New status
            user_id: User ID (for access control)
            
        Returns:
            Updated VoiceTranscription instance or None
        """
        try:
            stmt = (
                update(VoiceTranscription)
                .where(
                    and_(
                        VoiceTranscription.id == transcription_id,
                        VoiceTranscription.user_id == user_id
                    )
                )
                .values(transcription_status=status, updated_at=func.getutcdate())
                .returning(VoiceTranscription)
            )
            
            result = await self.db_session.execute(stmt)
            updated_transcription = result.scalar_one_or_none()
            
            if updated_transcription:
                logger.info(f"Updated transcription {transcription_id} status to {status}")
            
            return updated_transcription
            
        except Exception as e:
            logger.error(f"Failed to update transcription status: {str(e)}")
            raise DatabaseError(f"Failed to update transcription status: {str(e)}")

    async def delete_transcription(self, transcription_id: str, user_id: str) -> bool:
        """
        Delete a transcription and all related data.
        
        Args:
            transcription_id: Transcription ID
            user_id: User ID (for access control)
            
        Returns:
            True if deleted, False if not found
        """
        try:
            # First check if transcription exists and belongs to user
            transcription = await self.get_transcription_by_id(transcription_id, user_id)
            if not transcription:
                return False
            
            # Delete the transcription (cascade will handle segments and errors)
            stmt = delete(VoiceTranscription).where(
                and_(
                    VoiceTranscription.id == transcription_id,
                    VoiceTranscription.user_id == user_id
                )
            )
            
            result = await self.db_session.execute(stmt)
            deleted = result.rowcount > 0
            
            if deleted:
                logger.info(f"Deleted transcription {transcription_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete transcription: {str(e)}")
            raise DatabaseError(f"Failed to delete transcription: {str(e)}")

    async def get_transcription_statistics(
        self,
        user_id: Optional[str] = None,
        days_ago: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get transcription statistics.
        
        Args:
            user_id: Optional user filter
            days_ago: Optional filter for recent data
            
        Returns:
            Statistics dictionary
        """
        try:
            # Build base query
            base_query = select(VoiceTranscription)
            
            if user_id:
                base_query = base_query.where(VoiceTranscription.user_id == user_id)
            
            if days_ago:
                cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
                base_query = base_query.where(VoiceTranscription.created_at >= cutoff_date)
            
            # Get basic counts
            total_stmt = select(func.count(VoiceTranscription.id)).select_from(base_query.subquery())
            total_result = await self.db_session.execute(total_stmt)
            total_transcriptions = total_result.scalar()
            
            # Get status breakdown
            status_stmt = (
                select(
                    VoiceTranscription.transcription_status,
                    func.count(VoiceTranscription.id).label("count")
                )
                .select_from(base_query.subquery())
                .group_by(VoiceTranscription.transcription_status)
            )
            status_result = await self.db_session.execute(status_stmt)
            status_counts = {row.transcription_status: row.count for row in status_result}
            
            # Get language breakdown
            language_stmt = (
                select(
                    VoiceTranscription.language,
                    func.count(VoiceTranscription.id).label("count")
                )
                .select_from(base_query.subquery())
                .where(VoiceTranscription.language.is_not(None))
                .group_by(VoiceTranscription.language)
            )
            language_result = await self.db_session.execute(language_stmt)
            language_counts = {row.language: row.count for row in language_result}
            
            # Get model breakdown
            model_stmt = (
                select(
                    VoiceTranscription.model_name,
                    func.count(VoiceTranscription.id).label("count")
                )
                .select_from(base_query.subquery())
                .group_by(VoiceTranscription.model_name)
            )
            model_result = await self.db_session.execute(model_stmt)
            model_counts = {row.model_name: row.count for row in model_result}
            
            # Get quality metrics
            quality_stmt = (
                select(
                    func.avg(VoiceTranscription.confidence_score).label("avg_confidence"),
                    func.avg(VoiceTranscription.processing_time_ms).label("avg_processing_time"),
                    func.avg(VoiceTranscription.audio_duration_seconds).label("avg_audio_duration"),
                    func.sum(VoiceTranscription.audio_duration_seconds).label("total_audio_duration")
                )
                .select_from(base_query.subquery())
                .where(VoiceTranscription.transcription_status == "completed")
            )
            quality_result = await self.db_session.execute(quality_stmt)
            quality_row = quality_result.first()
            
            return {
                "total_transcriptions": total_transcriptions,
                "status_breakdown": status_counts,
                "language_breakdown": language_counts,
                "model_breakdown": model_counts,
                "quality_metrics": {
                    "avg_confidence_score": float(quality_row.avg_confidence) if quality_row and quality_row.avg_confidence else None,
                    "avg_processing_time_ms": float(quality_row.avg_processing_time) if quality_row and quality_row.avg_processing_time else None,
                    "avg_audio_duration_seconds": float(quality_row.avg_audio_duration) if quality_row and quality_row.avg_audio_duration else None,
                    "total_audio_duration_seconds": float(quality_row.total_audio_duration) if quality_row and quality_row.total_audio_duration else None
                },
                "completed_transcriptions": status_counts.get("completed", 0),
                "failed_transcriptions": status_counts.get("failed", 0),
                "processing_transcriptions": status_counts.get("processing", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get transcription statistics: {str(e)}")
            raise DatabaseError(f"Failed to get transcription statistics: {str(e)}")

    async def search_transcriptions(
        self,
        user_id: str,
        search_text: str,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[VoiceTranscription], int]:
        """
        Search transcriptions by text content.
        
        Args:
            user_id: User ID
            search_text: Text to search for
            limit: Maximum results to return
            offset: Number of results to skip
            
        Returns:
            Tuple of (transcription list, total count)
        """
        try:
            # Build search query
            search_pattern = f"%{search_text}%"
            
            stmt = (
                select(VoiceTranscription)
                .options(joinedload(VoiceTranscription.voice_attachment))
                .where(
                    and_(
                        VoiceTranscription.user_id == user_id,
                        VoiceTranscription.transcript_text.ilike(search_pattern)
                    )
                )
                .order_by(desc(VoiceTranscription.created_at))
            )
            
            # Get total count
            count_stmt = select(func.count(VoiceTranscription.id)).select_from(stmt.subquery())
            count_result = await self.db_session.execute(count_stmt)
            total_count = count_result.scalar() or 0
            
            # Apply pagination
            stmt = stmt.offset(offset).limit(limit)
            
            # Execute query
            result = await self.db_session.execute(stmt)
            transcriptions = list(result.scalars().all())
            
            return transcriptions, total_count
            
        except Exception as e:
            logger.error(f"Failed to search transcriptions: {str(e)}")
            raise DatabaseError(f"Failed to search transcriptions: {str(e)}")

    async def get_transcription_errors(
        self,
        user_id: str,
        is_resolved: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[TranscriptionError], int]:
        """
        Get transcription errors for a user.
        
        Args:
            user_id: User ID
            is_resolved: Filter by resolution status
            limit: Maximum results to return
            offset: Number of results to skip
            
        Returns:
            Tuple of (error list, total count)
        """
        try:
            stmt = (
                select(TranscriptionError)
                .options(joinedload(TranscriptionError.voice_attachment))
                .where(TranscriptionError.user_id == user_id)
            )
            
            if is_resolved is not None:
                stmt = stmt.where(TranscriptionError.is_resolved == is_resolved)
            
            # Get total count
            count_stmt = select(func.count(TranscriptionError.id)).select_from(stmt.subquery())
            count_result = await self.db_session.execute(count_stmt)
            total_count = count_result.scalar() or 0
            
            # Apply ordering and pagination
            stmt = (
                stmt.order_by(desc(TranscriptionError.created_at))
                .offset(offset)
                .limit(limit)
            )
            
            # Execute query
            result = await self.db_session.execute(stmt)
            errors = list(result.scalars().all())
            
            return errors, total_count
            
        except Exception as e:
            logger.error(f"Failed to get transcription errors: {str(e)}")
            raise DatabaseError(f"Failed to get transcription errors: {str(e)}")

    async def resolve_transcription_error(
        self,
        error_id: str,
        user_id: str,
        resolution_notes: Optional[str] = None
    ) -> Optional[TranscriptionError]:
        """
        Mark a transcription error as resolved.
        
        Args:
            error_id: Error ID
            user_id: User ID (for access control)
            resolution_notes: Optional resolution notes
            
        Returns:
            Updated TranscriptionError instance or None
        """
        try:
            stmt = (
                update(TranscriptionError)
                .where(
                    and_(
                        TranscriptionError.id == error_id,
                        TranscriptionError.user_id == user_id
                    )
                )
                .values(
                    is_resolved=True,
                    resolved_at=func.getutcdate(),
                    resolution_notes=resolution_notes,
                    updated_at=func.getutcdate()
                )
                .returning(TranscriptionError)
            )
            
            result = await self.db_session.execute(stmt)
            updated_error = result.scalar_one_or_none()
            
            if updated_error:
                logger.info(f"Resolved transcription error {error_id}")
            
            return updated_error
            
        except Exception as e:
            logger.error(f"Failed to resolve transcription error: {str(e)}")
            raise DatabaseError(f"Failed to resolve transcription error: {str(e)}")

    async def get_transcriptions_by_date_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[VoiceTranscription]:
        """
        Get transcriptions within a date range.
        
        Args:
            user_id: User ID to filter by
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Optional maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of VoiceTranscription instances
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = (
                select(VoiceTranscription)
                .where(
                    and_(
                        VoiceTranscription.user_id == user_id,
                        VoiceTranscription.created_at >= start_date,
                        VoiceTranscription.created_at <= end_date
                    )
                )
                .options(selectinload(VoiceTranscription.voice_attachment))
                .order_by(desc(VoiceTranscription.created_at))
                .offset(offset)
            )
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.db_session.execute(stmt)
            transcriptions = list(result.scalars().all())
            
            logger.info(f"Retrieved {len(transcriptions)} transcriptions for date range {start_date} to {end_date}")
            return transcriptions
            
        except Exception as e:
            logger.error(f"Failed to get transcriptions by date range: {str(e)}")
            raise DatabaseError(f"Failed to get transcriptions by date range: {str(e)}")