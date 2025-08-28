"""
AzureAIFoundryService.py - Azure AI Foundry Transcription Service

Provides Azure AI Foundry operations for voice transcription using the OpenAI audio API.
This service handles:
- Audio transcription using Whisper and GPT-4o models
- Support for various audio formats and languages
- Detailed transcription with timestamps and confidence scores
- Error handling and retry logic
- Authentication via Azure AD

The AzureAIFoundryService class provides comprehensive transcription
capabilities for the Scribe voice attachment system.
"""

from typing import Optional, Dict, Any, List, Union, Tuple
import logging
import io
import httpx
import asyncio
from datetime import datetime, timedelta

from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

from app.core.config import settings
from app.core.Exceptions import ValidationError, AuthenticationError

logger = logging.getLogger(__name__)


class TranscriptionResult:
    """Represents the result of an audio transcription operation."""
    
    def __init__(
        self,
        text: str,
        language: Optional[str] = None,
        duration: Optional[float] = None,
        segments: Optional[List[Dict[str, Any]]] = None,
        words: Optional[List[Dict[str, Any]]] = None,
        confidence_score: Optional[float] = None,
        model_name: str = "whisper-1",
        response_format: str = "verbose_json",
        **metadata
    ):
        self.text = text
        self.language = language
        self.duration = duration
        self.segments = segments or []
        self.words = words or []
        self.confidence_score = confidence_score
        self.model_name = model_name
        self.response_format = response_format
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "segments": self.segments,
            "words": self.words,
            "confidence_score": self.confidence_score,
            "model_name": self.model_name,
            "response_format": self.response_format,
            **self.metadata
        }


class AzureAIFoundryService:
    """Azure AI Foundry service for audio transcription."""

    def __init__(self):
        """Initialize Azure AI Foundry service."""
        self._credential: Optional[DefaultAzureCredential] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # Log service initialization
        logger.info("[SERVICE] Azure AI Foundry Service initializing...")
        try:
            endpoint = getattr(settings, 'azure_openai_endpoint', None)
            api_version = getattr(settings, 'azure_openai_api_version', '2024-10-21')
            model = getattr(settings, 'transcription_model_deployment', 'whisper')
            
            if endpoint:
                logger.info(f"[CONFIG] Azure OpenAI endpoint: {endpoint}")
                logger.info(f"[CONFIG] API version: {api_version}")
                logger.info(f"[CONFIG] Default model deployment: {model}")
                logger.info("[OK] Azure AI Foundry Service initialized successfully")
            else:
                logger.warning("[WARNING] Azure OpenAI endpoint not configured")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize Azure AI Foundry Service: {str(e)}")

    @property
    def endpoint(self) -> str:
        """Get Azure OpenAI endpoint."""
        endpoint = getattr(settings, 'azure_openai_endpoint', '')
        if not endpoint:
            raise ValidationError(
                "Azure OpenAI endpoint not configured. Set azure_openai_endpoint in settings.toml",
                error_code="AZURE_OPENAI_CONFIG_MISSING"
            )
        return endpoint.rstrip('/')

    @property
    def api_version(self) -> str:
        """Get API version for Azure OpenAI."""
        return getattr(settings, 'azure_openai_api_version', '2024-10-21')

    @property
    def default_model_deployment(self) -> str:
        """Get default model deployment name for transcription."""
        return getattr(settings, 'transcription_model_deployment', 'whisper')

    @property
    def credential(self) -> DefaultAzureCredential:
        """Get or create Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        """Get valid access token for Azure OpenAI."""
        now = datetime.utcnow()
        
        # Check if we need to refresh the token
        if (
            force_refresh or 
            self._access_token is None or 
            self._token_expires_at is None or 
            now >= self._token_expires_at - timedelta(minutes=5)  # Refresh 5 minutes early
        ):
            try:
                # Get token for Azure Cognitive Services
                token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
                self._access_token = token.token
                self._token_expires_at = datetime.fromtimestamp(token.expires_on)
                
                logger.debug("Successfully refreshed Azure OpenAI access token")
                
            except Exception as e:
                logger.error(f"Failed to get access token: {str(e)}")
                raise AuthenticationError(f"Failed to authenticate with Azure: {str(e)}")
        
        return self._access_token

    async def transcribe_audio(
        self,
        audio_content: bytes,
        filename: Optional[str] = None,
        model_deployment: Optional[str] = None,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "verbose_json",
        temperature: float = 0.0,
        timestamp_granularities: Optional[List[str]] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio content using Azure AI Foundry.
        
        Args:
            audio_content: Audio file content as bytes
            filename: Original filename (for content type detection)
            model_deployment: Model deployment name (defaults to configured model)
            language: Language code in ISO-639-1 format (e.g., 'en', 'es')
            prompt: Optional text to guide the model's style
            response_format: Response format ('json', 'verbose_json', 'text', 'srt', 'vtt')
            temperature: Sampling temperature (0.0 to 1.0)
            timestamp_granularities: List of timestamp granularities ('word', 'segment')
            
        Returns:
            TranscriptionResult with transcription text and metadata
            
        Raises:
            ValidationError: If input validation fails
            AuthenticationError: If transcription fails
        """
        try:
            # Validate inputs
            if not audio_content:
                raise ValidationError("Audio content is empty")
            
            if len(audio_content) > 25 * 1024 * 1024:  # 25MB limit
                raise ValidationError("Audio file exceeds 25MB limit")
            
            # Set defaults
            model_deployment = model_deployment or self.default_model_deployment
            filename = filename or "audio.wav"
            timestamp_granularities = timestamp_granularities or ["segment"]
            
            # Build API URL
            url = f"{self.endpoint}/openai/deployments/{model_deployment}/audio/transcriptions"
            
            # Get access token
            access_token = await self._get_access_token()
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {access_token}",
            }
            
            # Prepare form data
            files = {
                "file": (filename, io.BytesIO(audio_content), self._get_content_type(filename))
            }
            
            data = {
                "response_format": response_format,
                "temperature": str(temperature)
            }
            
            if language:
                data["language"] = language
            
            if prompt:
                data["prompt"] = prompt
                
            # Add timestamp granularities for verbose_json format
            if response_format == "verbose_json" and timestamp_granularities:
                for granularity in timestamp_granularities:
                    data[f"timestamp_granularities[]"] = granularity
            
            # Add API version parameter
            params = {"api-version": self.api_version}
            
            # Make the API request
            start_time = datetime.utcnow()
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
                response = await client.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    params=params
                )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Handle response based on status code
            if response.status_code == 200:
                return await self._parse_transcription_response(
                    response,
                    model_deployment,
                    response_format,
                    processing_time
                )
            elif response.status_code == 401:
                # Try refreshing token once
                logger.warning("Received 401, refreshing access token")
                access_token = await self._get_access_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {access_token}"
                
                async with httpx.AsyncClient(timeout=300.0) as client:
                    retry_response = await client.post(
                        url,
                        headers=headers,
                        files=files,
                        data=data,
                        params=params
                    )
                
                if retry_response.status_code == 200:
                    return await self._parse_transcription_response(
                        retry_response,
                        model_deployment,
                        response_format,
                        processing_time
                    )
                else:
                    raise AuthenticationError(f"Authentication failed: {retry_response.text}")
            else:
                error_text = response.text
                logger.error(f"Transcription API error {response.status_code}: {error_text}")
                raise AuthenticationError(f"Transcription failed: {error_text}")
                
        except (ValidationError, AuthenticationError):
            raise
        except httpx.TimeoutException:
            raise AuthenticationError("Transcription request timed out")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during transcription: {str(e)}")
            raise AuthenticationError(f"Transcription failed: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {str(e)}")
            raise AuthenticationError(f"Transcription failed: {str(e)}")

    async def _parse_transcription_response(
        self,
        response: httpx.Response,
        model_name: str,
        response_format: str,
        processing_time_ms: float
    ) -> TranscriptionResult:
        """Parse transcription response based on format."""
        try:
            if response_format in ["json", "verbose_json"]:
                data = response.json()
                
                # Extract basic information
                text = data.get("text", "")
                language = data.get("language")
                duration = data.get("duration")
                
                # Extract segments and words if available
                segments = data.get("segments", [])
                words = []
                
                # Calculate overall confidence from segments
                confidence_score = None
                if segments:
                    segment_confidences = [
                        seg.get("avg_logprob", 0) for seg in segments 
                        if seg.get("avg_logprob") is not None
                    ]
                    if segment_confidences:
                        # Convert log probabilities to confidence scores
                        confidence_score = sum(segment_confidences) / len(segment_confidences)
                        # Normalize to 0-1 range (rough approximation)
                        confidence_score = max(0, min(1, (confidence_score + 1) / 2))
                
                # Extract words from segments if available
                for segment in segments:
                    if "words" in segment:
                        words.extend(segment["words"])
                
                return TranscriptionResult(
                    text=text,
                    language=language,
                    duration=duration,
                    segments=segments,
                    words=words,
                    confidence_score=confidence_score,
                    model_name=model_name,
                    response_format=response_format,
                    processing_time_ms=processing_time_ms,
                    task=data.get("task"),
                    avg_logprob=data.get("avg_logprob"),
                    compression_ratio=data.get("compression_ratio"),
                    no_speech_prob=data.get("no_speech_prob")
                )
                
            else:  # text, srt, vtt formats
                text = response.text
                return TranscriptionResult(
                    text=text,
                    model_name=model_name,
                    response_format=response_format,
                    processing_time_ms=processing_time_ms
                )
                
        except Exception as e:
            logger.error(f"Failed to parse transcription response: {str(e)}")
            raise AuthenticationError(f"Failed to parse transcription response: {str(e)}")

    async def transcribe_audio_batch(
        self,
        audio_files: List[Tuple[bytes, str]],  # (content, filename) pairs
        model_deployment: Optional[str] = None,
        language: Optional[str] = None,
        max_concurrent: int = 3
    ) -> List[Tuple[str, Union[TranscriptionResult, Exception]]]:
        """
        Transcribe multiple audio files concurrently.
        
        Args:
            audio_files: List of (audio_content, filename) tuples
            model_deployment: Model deployment name
            language: Language code for all files
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of (filename, result_or_exception) tuples
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def transcribe_single(audio_content: bytes, filename: str) -> Tuple[str, Union[TranscriptionResult, Exception]]:
            async with semaphore:
                try:
                    result = await self.transcribe_audio(
                        audio_content=audio_content,
                        filename=filename,
                        model_deployment=model_deployment,
                        language=language
                    )
                    return filename, result
                except Exception as e:
                    logger.error(f"Failed to transcribe {filename}: {str(e)}")
                    return filename, e
        
        tasks = [
            transcribe_single(content, filename) 
            for content, filename in audio_files
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions at the gather level
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                filename = audio_files[i][1]
                processed_results.append((filename, result))
            else:
                processed_results.append(result)
        
        return processed_results

    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension."""
        if not filename:
            return "audio/wav"
        
        extension = filename.lower().split('.')[-1] if '.' in filename else ""
        
        content_type_map = {
            "wav": "audio/wav",
            "wave": "audio/wav", 
            "mp3": "audio/mpeg",
            "mpeg": "audio/mpeg",
            "mp4": "audio/mp4",
            "m4a": "audio/m4a",
            "aac": "audio/aac",
            "ogg": "audio/ogg",
            "opus": "audio/opus",
            "webm": "audio/webm",
            "flac": "audio/flac",
            "aiff": "audio/aiff",
            "amr": "audio/amr",
            "3gp": "audio/3gpp",
            "3gpp": "audio/3gpp",
            "wma": "audio/x-ms-wma"
        }
        
        return content_type_map.get(extension, "audio/wav")

    async def get_supported_models(self) -> List[Dict[str, Any]]:
        """Get list of supported transcription models."""
        return [
            {
                "id": "whisper-1",
                "name": "Whisper v1",
                "description": "General-purpose speech recognition model",
                "max_file_size_mb": 25,
                "supported_formats": ["mp3", "wav", "m4a", "ogg", "webm", "mp4", "mpeg", "mpga"]
            },
            {
                "id": "gpt-4o-transcribe", 
                "name": "GPT-4o Transcribe",
                "description": "Speech to text powered by GPT-4o",
                "max_file_size_mb": 25,
                "supported_formats": ["mp3", "wav", "m4a", "ogg", "webm", "mp4", "mpeg", "mpga"]
            },
            {
                "id": "gpt-4o-mini-transcribe",
                "name": "GPT-4o Mini Transcribe", 
                "description": "Speech to text powered by GPT-4o mini",
                "max_file_size_mb": 25,
                "supported_formats": ["mp3", "wav", "m4a", "ogg", "webm", "mp4", "mpeg", "mpga"]
            }
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Check service health and connectivity."""
        try:
            # Try to get access token
            start_time = datetime.utcnow()
            token = await self._get_access_token()
            token_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "endpoint": self.endpoint,
                "api_version": self.api_version,
                "default_model": self.default_model_deployment,
                "token_acquisition_time_ms": token_time,
                "authenticated": bool(token),
                "token_expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None
            }
            
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e),
                "endpoint": getattr(self, 'endpoint', 'unknown'),
                "authenticated": False
            }


# Global instance
azure_ai_foundry_service = AzureAIFoundryService()