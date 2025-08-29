"""
Unit tests for AzureAIFoundryService.

Tests Azure AI Foundry transcription functionality including:
- Audio transcription using Whisper and GPT-4o models
- Support for various audio formats and languages
- Batch transcription operations
- Response parsing for different formats (json, verbose_json, text)
- Token acquisition and refresh for Azure Cognitive Services
- Error handling for authentication and transcription failures
- Content type detection and validation
- Health check and model discovery
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import httpx
import io
import json
import base64

from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ClientAuthenticationError

from app.azure.AzureAIFoundryService import AzureAIFoundryService, TranscriptionResult
from app.core.Exceptions import ValidationError, AuthenticationError


class TestTranscriptionResult:
    """Test suite for TranscriptionResult class."""

    def test_transcription_result_initialization(self):
        """Test TranscriptionResult initialization with basic parameters."""
        text = "This is a test transcription."
        language = "en"
        duration = 15.5
        
        result = TranscriptionResult(text=text, language=language, duration=duration)
        
        assert result.text == text
        assert result.language == language
        assert result.duration == duration
        assert result.segments == []
        assert result.words == []
        assert result.model_name == "whisper-1"
        assert result.response_format == "verbose_json"

    def test_transcription_result_with_segments_and_words(self):
        """Test TranscriptionResult with detailed segments and words."""
        text = "Hello world."
        segments = [
            {"id": 0, "start": 0.0, "end": 2.0, "text": "Hello world.", "avg_logprob": -0.3}
        ]
        words = [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.6, "end": 1.2}
        ]
        
        result = TranscriptionResult(
            text=text, 
            segments=segments, 
            words=words,
            confidence_score=0.85
        )
        
        assert result.text == text
        assert result.segments == segments
        assert result.words == words
        assert result.confidence_score == 0.85

    def test_transcription_result_to_dict(self):
        """Test TranscriptionResult conversion to dictionary."""
        result = TranscriptionResult(
            text="Test text",
            language="en",
            duration=10.0,
            model_name="whisper-1",
            processing_time_ms=1500.0
        )
        
        dict_result = result.to_dict()
        
        assert dict_result["text"] == "Test text"
        assert dict_result["language"] == "en"
        assert dict_result["duration"] == 10.0
        assert dict_result["model_name"] == "whisper-1"
        assert dict_result["processing_time_ms"] == 1500.0


class TestAzureAIFoundryService:
    """Test suite for AzureAIFoundryService."""

    @pytest.fixture
    def ai_service(self):
        """Create AzureAIFoundryService instance."""
        return AzureAIFoundryService()

    @pytest.fixture
    def sample_audio_content(self):
        """Sample audio content for testing."""
        # WAV header + some audio data
        return b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x22V\x00\x00" * 50

    @pytest.fixture
    def mock_transcription_response(self):
        """Mock successful transcription response."""
        return {
            "text": "This is a test transcription of an audio file.",
            "task": "transcribe",
            "language": "en",
            "duration": 12.5,
            "segments": [
                {
                    "id": 0,
                    "seek": 0,
                    "start": 0.0,
                    "end": 5.0,
                    "text": "This is a test transcription",
                    "avg_logprob": -0.25,
                    "words": [
                        {"word": "This", "start": 0.0, "end": 0.3},
                        {"word": "is", "start": 0.4, "end": 0.6}
                    ]
                },
                {
                    "id": 1,
                    "seek": 500,
                    "start": 5.0,
                    "end": 12.5,
                    "text": " of an audio file.",
                    "avg_logprob": -0.3,
                    "words": [
                        {"word": "of", "start": 5.0, "end": 5.2},
                        {"word": "an", "start": 5.3, "end": 5.5}
                    ]
                }
            ]
        }

    # ==========================================================================
    # INITIALIZATION AND CONFIGURATION TESTS
    # ==========================================================================

    def test_service_initialization(self, ai_service):
        """Test service initialization."""
        assert ai_service is not None
        assert ai_service._credential is None
        assert ai_service._access_token is None
        assert ai_service._token_expires_at is None

    @patch('app.azure.AzureAIFoundryService.settings')
    def test_endpoint_property_success(self, mock_settings, ai_service):
        """Test endpoint property with valid configuration."""
        mock_settings.azure_openai_endpoint = "https://test-openai.openai.azure.com"
        
        endpoint = ai_service.endpoint
        
        assert endpoint == "https://test-openai.openai.azure.com"

    @patch('app.azure.AzureAIFoundryService.settings')
    def test_endpoint_property_missing_config(self, mock_settings, ai_service):
        """Test endpoint property with missing configuration."""
        mock_settings.azure_openai_endpoint = ""
        
        with pytest.raises(ValidationError):
            _ = ai_service.endpoint

    @patch('app.azure.AzureAIFoundryService.settings')
    def test_api_version_property(self, mock_settings, ai_service):
        """Test API version property."""
        mock_settings.azure_openai_api_version = "2024-12-01"
        
        version = ai_service.api_version
        
        assert version == "2024-12-01"

    @patch('app.azure.AzureAIFoundryService.settings')
    def test_default_model_deployment_property(self, mock_settings, ai_service):
        """Test default model deployment property."""
        mock_settings.transcription_model_deployment = "whisper-deployment"
        
        model = ai_service.default_model_deployment
        
        assert model == "whisper-deployment"

    def test_credential_property_lazy_loading(self, ai_service):
        """Test lazy loading of DefaultAzureCredential."""
        with patch('app.azure.AzureAIFoundryService.DefaultAzureCredential') as mock_credential:
            mock_instance = Mock()
            mock_credential.return_value = mock_instance
            
            # First access creates the credential
            cred1 = ai_service.credential
            assert cred1 == mock_instance
            
            # Second access returns the same instance
            cred2 = ai_service.credential
            assert cred2 == cred1
            
            # Credential should only be created once
            mock_credential.assert_called_once()

    # ==========================================================================
    # TOKEN MANAGEMENT TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_access_token_success(self, ai_service):
        """Test successful access token acquisition."""
        with patch.object(ai_service, '_credential') as mock_credential:
            future_time = datetime.utcnow() + timedelta(hours=1)
            mock_token = Mock()
            mock_token.token = "test-access-token"
            mock_token.expires_on = future_time.timestamp()
            
            mock_credential.get_token.return_value = mock_token
            
            token = await ai_service._get_access_token()
            
            assert token == "test-access-token"
            assert ai_service._access_token == "test-access-token"
            mock_credential.get_token.assert_called_once_with("https://cognitiveservices.azure.com/.default")

    @pytest.mark.asyncio
    async def test_get_access_token_caching(self, ai_service):
        """Test access token caching behavior."""
        with patch.object(ai_service, '_credential') as mock_credential:
            future_time = datetime.utcnow() + timedelta(hours=1)
            mock_token = Mock()
            mock_token.token = "cached-token"
            mock_token.expires_on = future_time.timestamp()
            
            mock_credential.get_token.return_value = mock_token
            
            # First call
            token1 = await ai_service._get_access_token()
            
            # Second call should use cached token
            token2 = await ai_service._get_access_token()
            
            assert token1 == token2 == "cached-token"
            # Should only call get_token once due to caching
            mock_credential.get_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_token_refresh_before_expiry(self, ai_service):
        """Test token refresh before expiry (5 minutes buffer)."""
        with patch.object(ai_service, '_credential') as mock_credential:
            # Token expires in 3 minutes (less than 5 minute buffer)
            near_expiry = datetime.utcnow() + timedelta(minutes=3)
            mock_token = Mock()
            mock_token.token = "refreshed-token"
            mock_token.expires_on = near_expiry.timestamp()
            
            mock_credential.get_token.return_value = mock_token
            
            # Set existing token that's about to expire
            ai_service._access_token = "old-token"
            ai_service._token_expires_at = near_expiry
            
            token = await ai_service._get_access_token()
            
            assert token == "refreshed-token"
            mock_credential.get_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_token_force_refresh(self, ai_service):
        """Test forced token refresh."""
        with patch.object(ai_service, '_credential') as mock_credential:
            future_time = datetime.utcnow() + timedelta(hours=1)
            mock_token = Mock()
            mock_token.token = "force-refreshed-token"
            mock_token.expires_on = future_time.timestamp()
            
            mock_credential.get_token.return_value = mock_token
            
            # Set existing valid token
            ai_service._access_token = "existing-token"
            ai_service._token_expires_at = future_time
            
            # Force refresh
            token = await ai_service._get_access_token(force_refresh=True)
            
            assert token == "force-refreshed-token"
            mock_credential.get_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_token_credential_error(self, ai_service):
        """Test handling of credential acquisition errors."""
        with patch.object(ai_service, '_credential') as mock_credential:
            mock_credential.get_token.side_effect = ClientAuthenticationError("Auth failed")
            
            with pytest.raises(AuthenticationError):
                await ai_service._get_access_token()

    # ==========================================================================
    # TRANSCRIPTION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, ai_service, sample_audio_content, 
                                          mock_transcription_response):
        """Test successful audio transcription."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_transcription_response
                
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                result = await ai_service.transcribe_audio(
                    audio_content=sample_audio_content,
                    filename="test-audio.wav"
                )
                
                assert isinstance(result, TranscriptionResult)
                assert result.text == "This is a test transcription of an audio file."
                assert result.language == "en"
                assert result.duration == 12.5
                assert len(result.segments) == 2
                assert len(result.words) == 4  # Total words from both segments

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_custom_parameters(self, ai_service, sample_audio_content,
                                                          mock_transcription_response):
        """Test transcription with custom parameters."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = mock_transcription_response
                
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                result = await ai_service.transcribe_audio(
                    audio_content=sample_audio_content,
                    filename="test-audio.wav",
                    model_deployment="gpt-4o-transcribe",
                    language="es",
                    prompt="This is a business meeting",
                    temperature=0.1,
                    timestamp_granularities=["word", "segment"]
                )
                
                assert isinstance(result, TranscriptionResult)
                # Verify that custom parameters were used in the request
                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                assert "data" in call_args.kwargs
                data = call_args.kwargs["data"]
                assert data["language"] == "es"
                assert data["prompt"] == "This is a business meeting"
                assert float(data["temperature"]) == 0.1

    @pytest.mark.asyncio
    async def test_transcribe_audio_text_format(self, ai_service, sample_audio_content):
        """Test transcription with text response format."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = "Plain text transcription result"
                
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                result = await ai_service.transcribe_audio(
                    audio_content=sample_audio_content,
                    filename="test-audio.wav",
                    response_format="text"
                )
                
                assert isinstance(result, TranscriptionResult)
                assert result.text == "Plain text transcription result"
                assert result.response_format == "text"

    @pytest.mark.asyncio
    async def test_transcribe_audio_empty_content(self, ai_service):
        """Test transcription with empty audio content."""
        with pytest.raises(ValidationError, match="Audio content is empty"):
            await ai_service.transcribe_audio(
                audio_content=b"",
                filename="empty.wav"
            )

    @pytest.mark.asyncio
    async def test_transcribe_audio_file_too_large(self, ai_service):
        """Test transcription with file exceeding size limit."""
        # Create content larger than 25MB limit
        large_content = b"x" * (26 * 1024 * 1024)
        
        with pytest.raises(ValidationError, match="exceeds 25MB limit"):
            await ai_service.transcribe_audio(
                audio_content=large_content,
                filename="large.wav"
            )

    @pytest.mark.asyncio
    async def test_transcribe_audio_401_retry(self, ai_service, sample_audio_content,
                                             mock_transcription_response):
        """Test transcription with 401 error and token refresh retry."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                # First call returns old token, second call returns refreshed token
                mock_get_token.side_effect = ["old-token", "refreshed-token"]
                
                # First response is 401, second is success
                unauthorized_response = Mock()
                unauthorized_response.status_code = 401
                
                success_response = Mock()
                success_response.status_code = 200
                success_response.json.return_value = mock_transcription_response
                
                mock_client.return_value.__aenter__.return_value.post.side_effect = [
                    unauthorized_response,
                    success_response
                ]
                
                result = await ai_service.transcribe_audio(
                    audio_content=sample_audio_content,
                    filename="test-audio.wav"
                )
                
                assert isinstance(result, TranscriptionResult)
                # Should have called get_access_token twice (initial + refresh)
                assert mock_get_token.call_count == 2
                # Should have made two POST requests
                assert mock_client.return_value.__aenter__.return_value.post.call_count == 2

    @pytest.mark.asyncio
    async def test_transcribe_audio_api_error(self, ai_service, sample_audio_content):
        """Test transcription with API error response."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_response = Mock()
                mock_response.status_code = 400
                mock_response.text = "Invalid request parameters"
                
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                with pytest.raises(AuthenticationError):
                    await ai_service.transcribe_audio(
                        audio_content=sample_audio_content,
                        filename="test-audio.wav"
                    )

    @pytest.mark.asyncio
    async def test_transcribe_audio_timeout(self, ai_service, sample_audio_content):
        """Test transcription with timeout error."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.TimeoutException("Request timeout")
                
                with pytest.raises(AuthenticationError, match="timed out"):
                    await ai_service.transcribe_audio(
                        audio_content=sample_audio_content,
                        filename="test-audio.wav"
                    )

    # ==========================================================================
    # BATCH TRANSCRIPTION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_transcribe_audio_batch_success(self, ai_service, sample_audio_content,
                                                 mock_transcription_response):
        """Test successful batch transcription."""
        with patch.object(ai_service, 'transcribe_audio') as mock_transcribe:
            # Mock successful transcription results
            result1 = TranscriptionResult(text="First transcription", model_name="whisper-1")
            result2 = TranscriptionResult(text="Second transcription", model_name="whisper-1")
            
            mock_transcribe.side_effect = [result1, result2]
            
            audio_files = [
                (sample_audio_content, "audio1.wav"),
                (sample_audio_content, "audio2.wav")
            ]
            
            results = await ai_service.transcribe_audio_batch(audio_files)
            
            assert len(results) == 2
            assert results[0][0] == "audio1.wav"
            assert isinstance(results[0][1], TranscriptionResult)
            assert results[1][0] == "audio2.wav"
            assert isinstance(results[1][1], TranscriptionResult)

    @pytest.mark.asyncio
    async def test_transcribe_audio_batch_with_failures(self, ai_service, sample_audio_content):
        """Test batch transcription with some failures."""
        with patch.object(ai_service, 'transcribe_audio') as mock_transcribe:
            result1 = TranscriptionResult(text="Success", model_name="whisper-1")
            error2 = AuthenticationError("Transcription failed")
            
            mock_transcribe.side_effect = [result1, error2]
            
            audio_files = [
                (sample_audio_content, "success.wav"),
                (sample_audio_content, "failure.wav")
            ]
            
            results = await ai_service.transcribe_audio_batch(audio_files)
            
            assert len(results) == 2
            assert results[0][0] == "success.wav"
            assert isinstance(results[0][1], TranscriptionResult)
            assert results[1][0] == "failure.wav"
            assert isinstance(results[1][1], Exception)

    @pytest.mark.asyncio
    async def test_transcribe_audio_batch_concurrency_limit(self, ai_service, sample_audio_content):
        """Test batch transcription with concurrency limiting."""
        with patch.object(ai_service, 'transcribe_audio') as mock_transcribe:
            with patch('asyncio.Semaphore') as mock_semaphore:
                mock_sem_instance = AsyncMock()
                mock_semaphore.return_value = mock_sem_instance
                
                mock_transcribe.return_value = TranscriptionResult(text="Test", model_name="whisper-1")
                
                audio_files = [(sample_audio_content, "test.wav")]
                max_concurrent = 2
                
                await ai_service.transcribe_audio_batch(audio_files, max_concurrent=max_concurrent)
                
                # Verify semaphore was created with correct limit
                mock_semaphore.assert_called_once_with(max_concurrent)

    # ==========================================================================
    # RESPONSE PARSING TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_parse_transcription_response_verbose_json(self, ai_service, mock_transcription_response):
        """Test parsing verbose JSON response."""
        mock_response = Mock()
        mock_response.json.return_value = mock_transcription_response
        
        result = await ai_service._parse_transcription_response(
            mock_response, "whisper-1", "verbose_json", 1500.0
        )
        
        assert isinstance(result, TranscriptionResult)
        assert result.text == "This is a test transcription of an audio file."
        assert result.language == "en"
        assert result.duration == 12.5
        assert len(result.segments) == 2
        assert result.model_name == "whisper-1"
        assert result.metadata["processing_time_ms"] == 1500.0

    @pytest.mark.asyncio
    async def test_parse_transcription_response_simple_json(self, ai_service):
        """Test parsing simple JSON response."""
        simple_response = {"text": "Simple transcription result"}
        
        mock_response = Mock()
        mock_response.json.return_value = simple_response
        
        result = await ai_service._parse_transcription_response(
            mock_response, "whisper-1", "json", 1000.0
        )
        
        assert isinstance(result, TranscriptionResult)
        assert result.text == "Simple transcription result"
        assert result.language is None
        assert result.duration is None

    @pytest.mark.asyncio
    async def test_parse_transcription_response_text_format(self, ai_service):
        """Test parsing text format response."""
        mock_response = Mock()
        mock_response.text = "Text format transcription"
        
        result = await ai_service._parse_transcription_response(
            mock_response, "whisper-1", "text", 800.0
        )
        
        assert isinstance(result, TranscriptionResult)
        assert result.text == "Text format transcription"
        assert result.response_format == "text"

    @pytest.mark.asyncio
    async def test_parse_transcription_response_with_confidence(self, ai_service):
        """Test parsing response with confidence score calculation."""
        response_with_logprobs = {
            "text": "Test with confidence",
            "segments": [
                {"avg_logprob": -0.1},
                {"avg_logprob": -0.3},
                {"avg_logprob": -0.2}
            ]
        }
        
        mock_response = Mock()
        mock_response.json.return_value = response_with_logprobs
        
        result = await ai_service._parse_transcription_response(
            mock_response, "whisper-1", "verbose_json", 1200.0
        )
        
        assert result.confidence_score is not None
        assert 0 <= result.confidence_score <= 1  # Should be normalized

    @pytest.mark.asyncio
    async def test_parse_transcription_response_parse_error(self, ai_service):
        """Test handling of response parsing errors."""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        with pytest.raises(AuthenticationError):
            await ai_service._parse_transcription_response(
                mock_response, "whisper-1", "json", 1000.0
            )

    # ==========================================================================
    # CONTENT TYPE DETECTION TESTS
    # ==========================================================================

    def test_get_content_type_wav(self, ai_service):
        """Test content type detection for WAV files."""
        content_type = ai_service._get_content_type("audio.wav")
        assert content_type == "audio/wav"

    def test_get_content_type_mp3(self, ai_service):
        """Test content type detection for MP3 files."""
        content_type = ai_service._get_content_type("audio.mp3")
        assert content_type == "audio/mpeg"

    def test_get_content_type_various_formats(self, ai_service):
        """Test content type detection for various audio formats."""
        test_cases = [
            ("audio.m4a", "audio/m4a"),
            ("audio.aac", "audio/aac"),
            ("audio.ogg", "audio/ogg"),
            ("audio.flac", "audio/flac"),
            ("audio.webm", "audio/webm"),
            ("unknown.xyz", "audio/wav")  # Default fallback
        ]
        
        for filename, expected_type in test_cases:
            content_type = ai_service._get_content_type(filename)
            assert content_type == expected_type

    def test_get_content_type_no_extension(self, ai_service):
        """Test content type detection for files without extension."""
        content_type = ai_service._get_content_type("audiofile")
        assert content_type == "audio/wav"  # Default

    def test_get_content_type_empty_filename(self, ai_service):
        """Test content type detection for empty filename."""
        content_type = ai_service._get_content_type("")
        assert content_type == "audio/wav"  # Default

    # ==========================================================================
    # MODEL DISCOVERY TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_supported_models(self, ai_service):
        """Test getting list of supported transcription models."""
        models = await ai_service.get_supported_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        
        # Check that all models have required fields
        for model in models:
            assert "id" in model
            assert "name" in model
            assert "description" in model
            assert "max_file_size_mb" in model
            assert "supported_formats" in model

    @pytest.mark.asyncio
    async def test_get_supported_models_contains_expected(self, ai_service):
        """Test that supported models contain expected models."""
        models = await ai_service.get_supported_models()
        
        model_ids = [model["id"] for model in models]
        
        assert "whisper-1" in model_ids
        assert "gpt-4o-transcribe" in model_ids
        assert "gpt-4o-mini-transcribe" in model_ids

    # ==========================================================================
    # HEALTH CHECK TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_health_check_success(self, ai_service):
        """Test successful health check."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            mock_get_token.return_value = "health-check-token"
            ai_service._token_expires_at = datetime.utcnow() + timedelta(hours=1)
            
            with patch('app.azure.AzureAIFoundryService.settings') as mock_settings:
                mock_settings.azure_openai_endpoint = "https://test.openai.azure.com"
                mock_settings.azure_openai_api_version = "2024-10-21"
                mock_settings.transcription_model_deployment = "whisper"
                
                result = await ai_service.health_check()
                
                assert result["status"] == "healthy"
                assert result["endpoint"] == "https://test.openai.azure.com"
                assert result["api_version"] == "2024-10-21"
                assert result["default_model"] == "whisper"
                assert result["authenticated"] is True
                assert "token_acquisition_time_ms" in result
                assert "token_expires_at" in result

    @pytest.mark.asyncio
    async def test_health_check_failure(self, ai_service):
        """Test health check with failure."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            mock_get_token.side_effect = AuthenticationError("Token acquisition failed")
            
            result = await ai_service.health_check()
            
            assert result["status"] == "unhealthy"
            assert "error" in result
            assert result["authenticated"] is False

    # ==========================================================================
    # EDGE CASES AND ERROR HANDLING
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_transcribe_with_network_error(self, ai_service, sample_audio_content):
        """Test transcription with network connectivity issues."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.ConnectError("Network unreachable")
                
                with pytest.raises(AuthenticationError):
                    await ai_service.transcribe_audio(
                        audio_content=sample_audio_content,
                        filename="test-audio.wav"
                    )

    @pytest.mark.asyncio
    async def test_transcribe_with_http_status_error(self, ai_service, sample_audio_content):
        """Test transcription with HTTP status error."""
        with patch.object(ai_service, '_get_access_token') as mock_get_token:
            with patch('httpx.AsyncClient') as mock_client:
                mock_get_token.return_value = "test-access-token"
                
                mock_response = Mock()
                mock_response.status_code = 500
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Server error", request=Mock(), response=mock_response
                )
                
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                with pytest.raises(AuthenticationError):
                    await ai_service.transcribe_audio(
                        audio_content=sample_audio_content,
                        filename="test-audio.wav"
                    )

    def test_validate_audio_content_types(self, ai_service):
        """Test content type detection from filenames."""
        # Test content type detection from filenames
        test_cases = [
            ("test.wav", "audio/wav"),
            ("test.mp3", "audio/mpeg"),
            ("test.m4a", "audio/m4a"),
            ("test.ogg", "audio/ogg")
        ]
        
        for filename, expected_content_type in test_cases:
            # This method exists and returns content type from filename
            result = ai_service._get_content_type(filename)
            assert result == expected_content_type

    def test_content_type_edge_cases(self, ai_service):
        """Test content type detection for edge cases."""
        edge_cases = [
            ("test", "audio/wav"),  # No extension -> defaults to audio/wav
            ("test.txt", "audio/wav"),  # Non-audio file -> defaults to audio/wav
            ("TEST.WAV", "audio/wav"),  # Uppercase extension
            ("file.with.dots.mp3", "audio/mpeg"),  # Multiple dots
            ("", "audio/wav"),  # Empty filename -> returns audio/wav
        ]
        
        for filename, expected_content_type in edge_cases:
            result = ai_service._get_content_type(filename)
            assert result == expected_content_type