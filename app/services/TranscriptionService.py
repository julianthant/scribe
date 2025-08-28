"""
TranscriptionService.py - Voice Transcription Business Logic Service

Provides comprehensive business logic for voice transcription operations.
This service handles:
- Voice attachment transcription using Azure AI Foundry
- Batch transcription processing with concurrent operations
- Transcription result storage and retrieval
- Error handling and retry logic
- Integration with voice attachment workflow
- Statistics and analytics for transcription data

The TranscriptionService class orchestrates between the Azure AI Foundry service,
transcription repository, and voice attachment repository.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime

from app.azure.AzureAIFoundryService import azure_ai_foundry_service, TranscriptionResult
from app.repositories.TranscriptionRepository import TranscriptionRepository
from app.repositories.VoiceAttachmentRepository import VoiceAttachmentRepository
from app.azure.AzureBlobService import azure_blob_service
from app.core.Exceptions import ValidationError, AuthenticationError, DatabaseError
from app.db.models.Transcription import VoiceTranscription, TranscriptionError
from app.db.models.VoiceAttachment import VoiceAttachment
from app.core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Business logic service for voice transcription operations."""

    def __init__(
        self,
        transcription_repository: TranscriptionRepository,
        voice_attachment_repository: VoiceAttachmentRepository,
        excel_sync_service: Optional[Any] = None  # ExcelTranscriptionSyncService - optional to avoid circular imports
    ):
        """Initialize transcription service.
        
        Args:
            transcription_repository: Transcription repository instance
            voice_attachment_repository: Voice attachment repository instance
            excel_sync_service: Optional Excel sync service instance
        """
        self.transcription_repository = transcription_repository
        self.voice_attachment_repository = voice_attachment_repository
        self.excel_sync_service = excel_sync_service
        self.excel_sync_enabled = getattr(settings, 'excel_sync_enabled', True)

    async def transcribe_voice_attachment(
        self,
        voice_attachment_id: str,
        user_id: str,
        model_deployment: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        force_retranscribe: bool = False
    ) -> VoiceTranscription:
        """
        Transcribe a voice attachment using Azure AI Foundry.
        
        Args:
            voice_attachment_id: ID of the voice attachment
            user_id: ID of the user
            model_deployment: Model deployment name (optional)
            language: Language code (optional)
            prompt: Transcription prompt (optional)
            force_retranscribe: Whether to force retranscription if already exists
            
        Returns:
            VoiceTranscription instance
            
        Raises:
            ValidationError: If validation fails
            AuthenticationError: If transcription fails
            DatabaseError: If database operation fails
        """
        try:
            logger.info(f"Starting transcription for voice attachment {voice_attachment_id} by user {user_id}")
            
            # Check if voice attachment exists and belongs to user
            voice_attachment = await self.voice_attachment_repository.get_by_id_and_user(
                voice_attachment_id, user_id
            )
            if not voice_attachment:
                raise ValidationError(
                    f"Voice attachment {voice_attachment_id} not found or not accessible",
                    error_code="VOICE_ATTACHMENT_NOT_FOUND"
                )
            
            # Check if transcription already exists
            existing_transcription = await self.transcription_repository.get_transcription_by_voice_attachment(
                voice_attachment_id, user_id
            )
            
            if existing_transcription and not force_retranscribe:
                logger.info(f"Transcription already exists for voice attachment {voice_attachment_id}")
                return existing_transcription
            
            # Download audio content from blob storage
            try:
                audio_content = await azure_blob_service.download_voice_attachment(voice_attachment.blob_name)
            except Exception as e:
                await self._create_transcription_error(
                    voice_attachment_id=voice_attachment_id,
                    user_id=user_id,
                    error_type="blob_download",
                    error_message=f"Failed to download audio from blob storage: {str(e)}",
                    audio_format=voice_attachment.content_type,
                    audio_size_bytes=voice_attachment.size_bytes
                )
                raise AuthenticationError(f"Failed to download audio: {str(e)}")
            
            # Perform transcription using Azure AI Foundry
            try:
                transcription_result = await azure_ai_foundry_service.transcribe_audio(
                    audio_content=audio_content,
                    filename=voice_attachment.original_filename,
                    model_deployment=model_deployment,
                    language=language,
                    prompt=prompt,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"]
                )
                
                logger.info(f"Transcription completed for voice attachment {voice_attachment_id}")
                
            except Exception as e:
                await self._create_transcription_error(
                    voice_attachment_id=voice_attachment_id,
                    user_id=user_id,
                    error_type="transcription_api",
                    error_message=str(e),
                    model_name=model_deployment,
                    audio_format=voice_attachment.content_type,
                    audio_size_bytes=voice_attachment.size_bytes,
                    http_status_code=getattr(e, 'status_code', None)
                )
                raise
            
            # Delete existing transcription if force retranscribe
            if existing_transcription and force_retranscribe:
                await self.transcription_repository.delete_transcription(
                    existing_transcription.id, user_id
                )
            
            # Save transcription to database
            transcription = await self._save_transcription_result(
                transcription_result=transcription_result,
                voice_attachment_id=voice_attachment_id,
                user_id=user_id,
                prompt=prompt
            )
            
            # Update voice attachment transcription status
            await self.voice_attachment_repository.update_transcription_status(
                voice_attachment_id=voice_attachment_id,
                is_transcribed=True,
                transcription_confidence=transcription_result.confidence_score
            )
            
            logger.info(f"Successfully saved transcription {transcription.id} for voice attachment {voice_attachment_id}")
            
            # Trigger Excel sync if enabled and service is available
            if self.excel_sync_enabled and self.excel_sync_service:
                asyncio.create_task(self._sync_transcription_to_excel(transcription, user_id))
            
            return transcription
            
        except (ValidationError, AuthenticationError, DatabaseError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error transcribing voice attachment {voice_attachment_id}: {str(e)}")
            raise AuthenticationError(f"Transcription failed: {str(e)}")

    async def transcribe_voice_attachments_batch(
        self,
        voice_attachment_ids: List[str],
        user_id: str,
        model_deployment: Optional[str] = None,
        language: Optional[str] = None,
        max_concurrent: int = 3,
        force_retranscribe: bool = False
    ) -> Dict[str, Union[VoiceTranscription, Exception]]:
        """
        Transcribe multiple voice attachments concurrently.
        
        Args:
            voice_attachment_ids: List of voice attachment IDs
            user_id: User ID
            model_deployment: Model deployment name
            language: Language code
            max_concurrent: Maximum concurrent transcriptions
            force_retranscribe: Whether to force retranscription
            
        Returns:
            Dictionary mapping attachment IDs to results or exceptions
        """
        try:
            logger.info(f"Starting batch transcription of {len(voice_attachment_ids)} attachments for user {user_id}")
            
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def transcribe_single(attachment_id: str) -> Tuple[str, Union[VoiceTranscription, Exception]]:
                async with semaphore:
                    try:
                        result = await self.transcribe_voice_attachment(
                            voice_attachment_id=attachment_id,
                            user_id=user_id,
                            model_deployment=model_deployment,
                            language=language,
                            force_retranscribe=force_retranscribe
                        )
                        return attachment_id, result
                    except Exception as e:
                        logger.error(f"Failed to transcribe attachment {attachment_id}: {str(e)}")
                        return attachment_id, e
            
            # Execute all transcriptions concurrently
            tasks = [transcribe_single(attachment_id) for attachment_id in voice_attachment_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            batch_results = {}
            successful_count = 0
            failed_count = 0
            
            for result in results:
                if isinstance(result, Exception):
                    # Handle exceptions at the gather level
                    logger.error(f"Gather exception in batch transcription: {str(result)}")
                    failed_count += 1
                else:
                    attachment_id, transcription_or_error = result
                    batch_results[attachment_id] = transcription_or_error
                    
                    if isinstance(transcription_or_error, Exception):
                        failed_count += 1
                    else:
                        successful_count += 1
            
            logger.info(f"Batch transcription completed: {successful_count} successful, {failed_count} failed")
            return batch_results
            
        except Exception as e:
            logger.error(f"Batch transcription failed: {str(e)}")
            raise AuthenticationError(f"Batch transcription failed: {str(e)}")

    async def get_transcription(
        self,
        transcription_id: str,
        user_id: str,
        include_segments: bool = True
    ) -> Optional[VoiceTranscription]:
        """
        Get a transcription by ID.
        
        Args:
            transcription_id: Transcription ID
            user_id: User ID
            include_segments: Whether to include segments
            
        Returns:
            VoiceTranscription instance or None
        """
        try:
            transcription = await self.transcription_repository.get_transcription_by_id(
                transcription_id, user_id
            )
            
            if transcription:
                logger.debug(f"Retrieved transcription {transcription_id} for user {user_id}")
            
            return transcription
            
        except Exception as e:
            logger.error(f"Failed to get transcription {transcription_id}: {str(e)}")
            raise DatabaseError(f"Failed to get transcription: {str(e)}")

    async def get_transcription_by_voice_attachment(
        self,
        voice_attachment_id: str,
        user_id: str
    ) -> Optional[VoiceTranscription]:
        """
        Get transcription for a voice attachment.
        
        Args:
            voice_attachment_id: Voice attachment ID
            user_id: User ID
            
        Returns:
            VoiceTranscription instance or None
        """
        try:
            return await self.transcription_repository.get_transcription_by_voice_attachment(
                voice_attachment_id, user_id
            )
        except Exception as e:
            logger.error(f"Failed to get transcription for voice attachment {voice_attachment_id}: {str(e)}")
            raise DatabaseError(f"Failed to get transcription: {str(e)}")

    async def list_user_transcriptions(
        self,
        user_id: str,
        status_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        model_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_direction: str = "desc"
    ) -> Tuple[List[VoiceTranscription], int]:
        """
        List transcriptions for a user with filtering and search.
        
        Args:
            user_id: User ID
            status_filter: Filter by status
            language_filter: Filter by language
            model_filter: Filter by model
            search_text: Search in transcript text
            limit: Maximum results
            offset: Results to skip
            order_by: Field to order by
            order_direction: Order direction
            
        Returns:
            Tuple of (transcription list, total count)
        """
        try:
            if search_text:
                return await self.transcription_repository.search_transcriptions(
                    user_id=user_id,
                    search_text=search_text,
                    limit=limit,
                    offset=offset
                )
            else:
                return await self.transcription_repository.list_user_transcriptions(
                    user_id=user_id,
                    status_filter=status_filter,
                    language_filter=language_filter,
                    model_filter=model_filter,
                    limit=limit,
                    offset=offset,
                    order_by=order_by,
                    order_direction=order_direction
                )
                
        except Exception as e:
            logger.error(f"Failed to list transcriptions for user {user_id}: {str(e)}")
            raise DatabaseError(f"Failed to list transcriptions: {str(e)}")

    async def delete_transcription(
        self,
        transcription_id: str,
        user_id: str
    ) -> bool:
        """
        Delete a transcription.
        
        Args:
            transcription_id: Transcription ID
            user_id: User ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            # Get transcription to find associated voice attachment
            transcription = await self.transcription_repository.get_transcription_by_id(
                transcription_id, user_id
            )
            
            if not transcription:
                return False
            
            # Delete transcription
            deleted = await self.transcription_repository.delete_transcription(
                transcription_id, user_id
            )
            
            if deleted:
                # Update voice attachment transcription status
                await self.voice_attachment_repository.update_transcription_status(
                    voice_attachment_id=transcription.voice_attachment_id,
                    is_transcribed=False,
                    transcription_confidence=None
                )
                
                logger.info(f"Deleted transcription {transcription_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete transcription {transcription_id}: {str(e)}")
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
            return await self.transcription_repository.get_transcription_statistics(
                user_id=user_id,
                days_ago=days_ago
            )
        except Exception as e:
            logger.error(f"Failed to get transcription statistics: {str(e)}")
            raise DatabaseError(f"Failed to get transcription statistics: {str(e)}")

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
            limit: Maximum results
            offset: Results to skip
            
        Returns:
            Tuple of (error list, total count)
        """
        try:
            return await self.transcription_repository.get_transcription_errors(
                user_id=user_id,
                is_resolved=is_resolved,
                limit=limit,
                offset=offset
            )
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
        Resolve a transcription error.
        
        Args:
            error_id: Error ID
            user_id: User ID
            resolution_notes: Optional resolution notes
            
        Returns:
            Updated TranscriptionError or None
        """
        try:
            return await self.transcription_repository.resolve_transcription_error(
                error_id=error_id,
                user_id=user_id,
                resolution_notes=resolution_notes
            )
        except Exception as e:
            logger.error(f"Failed to resolve transcription error: {str(e)}")
            raise DatabaseError(f"Failed to resolve transcription error: {str(e)}")

    async def retry_failed_transcription(
        self,
        voice_attachment_id: str,
        user_id: str,
        model_deployment: Optional[str] = None,
        language: Optional[str] = None
    ) -> VoiceTranscription:
        """
        Retry a failed transcription.
        
        Args:
            voice_attachment_id: Voice attachment ID
            user_id: User ID
            model_deployment: Model deployment name
            language: Language code
            
        Returns:
            New VoiceTranscription instance
        """
        try:
            logger.info(f"Retrying transcription for voice attachment {voice_attachment_id}")
            
            return await self.transcribe_voice_attachment(
                voice_attachment_id=voice_attachment_id,
                user_id=user_id,
                model_deployment=model_deployment,
                language=language,
                force_retranscribe=True
            )
            
        except Exception as e:
            logger.error(f"Failed to retry transcription: {str(e)}")
            raise

    async def get_supported_models(self) -> List[Dict[str, Any]]:
        """
        Get supported transcription models.
        
        Returns:
            List of supported models
        """
        try:
            return await azure_ai_foundry_service.get_supported_models()
        except Exception as e:
            logger.error(f"Failed to get supported models: {str(e)}")
            raise AuthenticationError(f"Failed to get supported models: {str(e)}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check transcription service health.
        
        Returns:
            Health status dictionary
        """
        try:
            # Check Azure AI Foundry service health
            foundry_health = await azure_ai_foundry_service.health_check()
            
            return {
                "service": "TranscriptionService",
                "status": "healthy" if foundry_health.get("status") == "healthy" else "degraded",
                "azure_ai_foundry": foundry_health,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Transcription service health check failed: {str(e)}")
            return {
                "service": "TranscriptionService",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    # Private helper methods

    async def _save_transcription_result(
        self,
        transcription_result: TranscriptionResult,
        voice_attachment_id: str,
        user_id: str,
        prompt: Optional[str] = None
    ) -> VoiceTranscription:
        """Save transcription result to database."""
        try:
            # Create main transcription record
            transcription = await self.transcription_repository.create_transcription(
                voice_attachment_id=voice_attachment_id,
                user_id=user_id,
                transcript_text=transcription_result.text,
                model_name=transcription_result.model_name,
                language=transcription_result.language,
                confidence_score=transcription_result.confidence_score,
                avg_logprob=transcription_result.metadata.get("avg_logprob"),
                compression_ratio=transcription_result.metadata.get("compression_ratio"),
                no_speech_prob=transcription_result.metadata.get("no_speech_prob"),
                response_format=transcription_result.response_format,
                has_word_timestamps=bool(transcription_result.words),
                has_segment_timestamps=bool(transcription_result.segments),
                audio_duration_seconds=transcription_result.duration,
                processing_time_ms=int(transcription_result.metadata.get("processing_time_ms", 0)),
                transcription_prompt=prompt,
                azure_request_id=transcription_result.metadata.get("azure_request_id")
            )
            
            # Add segments if available
            if transcription_result.segments:
                await self.transcription_repository.add_transcription_segments(
                    transcription_id=transcription.id,
                    segments=transcription_result.segments
                )
                
            # Add word segments if available and different from regular segments
            if transcription_result.words and not transcription_result.segments:
                word_segments = [
                    {
                        "start": word.get("start", 0),
                        "end": word.get("end", 0),
                        "text": word.get("word", ""),
                        "confidence": word.get("confidence"),
                        "segment_type": "word"
                    }
                    for word in transcription_result.words
                ]
                
                await self.transcription_repository.add_transcription_segments(
                    transcription_id=transcription.id,
                    segments=word_segments
                )
            
            return transcription
            
        except Exception as e:
            logger.error(f"Failed to save transcription result: {str(e)}")
            raise DatabaseError(f"Failed to save transcription result: {str(e)}")

    async def _create_transcription_error(
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
        """Create a transcription error record."""
        try:
            return await self.transcription_repository.create_transcription_error(
                voice_attachment_id=voice_attachment_id,
                user_id=user_id,
                error_type=error_type,
                error_message=error_message,
                transcription_id=transcription_id,
                error_code=error_code,
                model_name=model_name,
                audio_format=audio_format,
                audio_size_bytes=audio_size_bytes,
                azure_request_id=azure_request_id,
                http_status_code=http_status_code,
                retry_count=retry_count
            )
        except Exception as e:
            logger.error(f"Failed to create transcription error: {str(e)}")
            # Don't raise here - we don't want to mask the original error
            return None

    async def _sync_transcription_to_excel(
        self,
        transcription: VoiceTranscription,
        user_id: str,
        access_token: Optional[str] = None
    ) -> None:
        """
        Asynchronously sync transcription to Excel.
        This method runs in the background and logs errors without raising them
        to avoid impacting the main transcription flow.
        
        Args:
            transcription: VoiceTranscription instance
            user_id: User ID
            access_token: Optional access token (would need to be passed from request context)
        """
        try:
            if not self.excel_sync_service:
                logger.debug("Excel sync service not available, skipping sync")
                return

            # NOTE: In a real implementation, you would need to get the access token
            # from the user's session, request context, or refresh it from stored tokens
            if not access_token:
                logger.info("No access token available for Excel sync, skipping")
                return

            logger.info(f"Starting background Excel sync for transcription {transcription.id}")
            
            sync_result = await self.excel_sync_service.sync_transcription_to_excel(
                user_id=user_id,
                transcription_id=transcription.id,
                access_token=access_token
            )
            
            if sync_result.status == "completed":
                logger.info(f"Successfully synced transcription {transcription.id} to Excel")
            else:
                logger.warning(f"Excel sync failed for transcription {transcription.id}: {sync_result.errors}")
                
        except Exception as e:
            # Log error but don't raise - this is a background operation
            logger.error(f"Background Excel sync failed for transcription {transcription.id}: {str(e)}")

    async def trigger_monthly_excel_sync(
        self,
        user_id: str,
        access_token: str,
        month_year: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Trigger manual sync of monthly transcriptions to Excel.
        
        Args:
            user_id: User ID
            access_token: Access token for OneDrive
            month_year: Optional month/year string (defaults to current month)
            
        Returns:
            Dictionary with sync results
        """
        try:
            if not self.excel_sync_service:
                raise ValidationError("Excel sync service not available")

            if not month_year:
                # Default to current month
                current_date = datetime.utcnow()
                month_year = current_date.strftime(getattr(settings, 'excel_worksheet_date_format', '%B %Y'))

            logger.info(f"Triggering monthly Excel sync for {month_year} by user {user_id}")
            
            batch_result = await self.excel_sync_service.sync_month_transcriptions(
                user_id=user_id,
                month_year=month_year,
                access_token=access_token,
                force_full_sync=True
            )
            
            return {
                "month_year": batch_result.month_year,
                "status": batch_result.overall_status,
                "total_transcriptions": batch_result.total_transcriptions,
                "synced_transcriptions": batch_result.synced_transcriptions,
                "skipped_transcriptions": batch_result.skipped_transcriptions,
                "errors": batch_result.errors,
                "completed_at": batch_result.completed_at.isoformat() if batch_result.completed_at else None
            }
            
        except Exception as e:
            logger.error(f"Error triggering monthly Excel sync: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    async def get_excel_sync_health(
        self,
        user_id: str,
        access_token: str
    ) -> Dict[str, Any]:
        """
        Check Excel sync service health.
        
        Args:
            user_id: User ID
            access_token: Access token for OneDrive
            
        Returns:
            Health check results
        """
        try:
            if not self.excel_sync_service:
                return {
                    "service_available": False,
                    "error": "Excel sync service not configured"
                }

            return await self.excel_sync_service.health_check(user_id, access_token)
            
        except Exception as e:
            logger.error(f"Error checking Excel sync health: {str(e)}")
            return {
                "service_available": False,
                "error": str(e)
            }