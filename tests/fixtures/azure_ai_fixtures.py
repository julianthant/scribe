"""
Azure AI Foundry test fixtures and mock responses.

This module provides comprehensive fixtures for testing Azure AI Foundry transcription
functionality including:
- Mock transcription responses in various formats
- Sample audio content for testing
- Error responses and edge cases
- Model metadata and configuration
- Token and authentication fixtures
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import base64
import json

# Sample WAV file header for testing
SAMPLE_WAV_HEADER = (
    b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00"
    b"\x44\xac\x00\x00\x10\xb1\x02\x00\x04\x00\x10\x00data\x00\x08\x00\x00"
)

# Mock transcription responses
TRANSCRIPTION_RESPONSES = {
    # Verbose JSON response with full metadata
    "verbose_json_success": {
        "task": "transcribe",
        "language": "en",
        "duration": 15.75,
        "text": "This is a test transcription of a voice message. The audio quality is good and the speaker is clear.",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 8.5,
                "text": "This is a test transcription of a voice message.",
                "tokens": [50364, 50365, 50366, 50367],
                "temperature": 0.0,
                "avg_logprob": -0.2456789,
                "compression_ratio": 1.234567,
                "no_speech_prob": 0.001234,
                "words": [
                    {"word": "This", "start": 0.0, "end": 0.32, "probability": 0.99},
                    {"word": "is", "start": 0.36, "end": 0.48, "probability": 0.98},
                    {"word": "a", "start": 0.52, "end": 0.6, "probability": 0.97},
                    {"word": "test", "start": 0.64, "end": 0.92, "probability": 0.99},
                    {"word": "transcription", "start": 0.96, "end": 1.68, "probability": 0.95},
                    {"word": "of", "start": 1.72, "end": 1.84, "probability": 0.98},
                    {"word": "a", "start": 1.88, "end": 1.96, "probability": 0.97},
                    {"word": "voice", "start": 2.0, "end": 2.32, "probability": 0.99},
                    {"word": "message.", "start": 2.36, "end": 2.8, "probability": 0.96}
                ]
            },
            {
                "id": 1,
                "seek": 850,
                "start": 8.5,
                "end": 15.75,
                "text": " The audio quality is good and the speaker is clear.",
                "tokens": [50789, 50790, 50791, 50792],
                "temperature": 0.0,
                "avg_logprob": -0.1876543,
                "compression_ratio": 1.345678,
                "no_speech_prob": 0.000987,
                "words": [
                    {"word": "The", "start": 8.5, "end": 8.66, "probability": 0.98},
                    {"word": "audio", "start": 8.7, "end": 9.02, "probability": 0.97},
                    {"word": "quality", "start": 9.06, "end": 9.54, "probability": 0.96},
                    {"word": "is", "start": 9.58, "end": 9.7, "probability": 0.99},
                    {"word": "good", "start": 9.74, "end": 10.02, "probability": 0.98},
                    {"word": "and", "start": 10.06, "end": 10.18, "probability": 0.97},
                    {"word": "the", "start": 10.22, "end": 10.34, "probability": 0.99},
                    {"word": "speaker", "start": 10.38, "end": 10.82, "probability": 0.96},
                    {"word": "is", "start": 10.86, "end": 10.98, "probability": 0.98},
                    {"word": "clear.", "start": 11.02, "end": 11.4, "probability": 0.97}
                ]
            }
        ]
    },

    # Simple JSON response
    "json_success": {
        "text": "This is a simple transcription without detailed metadata."
    },

    # Text format response (just a string)
    "text_success": "This is a plain text transcription response.",

    # SRT format response
    "srt_success": """1
00:00:00,000 --> 00:00:08,500
This is a test transcription of a voice message.

2
00:00:08,500 --> 00:00:15,750
The audio quality is good and the speaker is clear.
""",

    # VTT format response
    "vtt_success": """WEBVTT

00:00:00.000 --> 00:00:08.500
This is a test transcription of a voice message.

00:00:08.500 --> 00:00:15.750
The audio quality is good and the speaker is clear.
""",

    # Empty transcription (no speech detected)
    "no_speech": {
        "task": "transcribe",
        "language": None,
        "duration": 5.0,
        "text": "",
        "segments": [],
        "avg_logprob": -5.0,
        "compression_ratio": 0.5,
        "no_speech_prob": 0.95
    },

    # Long transcription with multiple segments
    "long_transcription": {
        "task": "transcribe",
        "language": "en",
        "duration": 120.5,
        "text": "This is a longer transcription example. It contains multiple sentences and segments. The content discusses various topics including business strategies, technical implementations, and future planning. Each segment represents a natural pause or topic change in the original audio.",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 25.0,
                "text": "This is a longer transcription example. It contains multiple sentences and segments.",
                "avg_logprob": -0.15,
                "compression_ratio": 1.5,
                "no_speech_prob": 0.01
            },
            {
                "id": 1,
                "seek": 2500,
                "start": 25.0,
                "end": 60.0,
                "text": " The content discusses various topics including business strategies, technical implementations.",
                "avg_logprob": -0.18,
                "compression_ratio": 1.4,
                "no_speech_prob": 0.02
            },
            {
                "id": 2,
                "seek": 6000,
                "start": 60.0,
                "end": 120.5,
                "text": " Each segment represents a natural pause or topic change in the original audio.",
                "avg_logprob": -0.12,
                "compression_ratio": 1.6,
                "no_speech_prob": 0.01
            }
        ]
    },

    # Non-English transcription
    "spanish_transcription": {
        "task": "transcribe", 
        "language": "es",
        "duration": 12.3,
        "text": "Esta es una transcripción en español. La calidad del audio es buena.",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 12.3,
                "text": "Esta es una transcripción en español. La calidad del audio es buena.",
                "avg_logprob": -0.22,
                "compression_ratio": 1.3,
                "no_speech_prob": 0.005
            }
        ]
    },

    # Translation task response
    "translation_response": {
        "task": "translate",
        "language": "es",
        "duration": 10.5,
        "text": "This is an English translation of the Spanish audio.",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 10.5,
                "text": "This is an English translation of the Spanish audio.",
                "avg_logprob": -0.25,
                "compression_ratio": 1.2,
                "no_speech_prob": 0.01
            }
        ]
    },

    # Low quality audio response
    "low_quality_audio": {
        "task": "transcribe",
        "language": "en",
        "duration": 8.0,
        "text": "This transcription has lower confidence due to audio quality issues.",
        "segments": [
            {
                "id": 0,
                "seek": 0,
                "start": 0.0,
                "end": 8.0,
                "text": "This transcription has lower confidence due to audio quality issues.",
                "avg_logprob": -1.5,  # Lower confidence
                "compression_ratio": 0.8,
                "no_speech_prob": 0.3  # Higher no-speech probability
            }
        ]
    }
}

# Error responses from Azure OpenAI API
TRANSCRIPTION_ERRORS = {
    "invalid_model": {
        "error": {
            "message": "The model deployment 'invalid-whisper' was not found.",
            "type": "invalid_request_error",
            "param": "model",
            "code": "DeploymentNotFound"
        }
    },

    "file_too_large": {
        "error": {
            "message": "File size exceeds the maximum allowed size of 25MB.",
            "type": "invalid_request_error",
            "param": "file",
            "code": "FileSizeExceeded"
        }
    },

    "unsupported_format": {
        "error": {
            "message": "Unsupported audio format. Supported formats are: mp3, wav, m4a, ogg, webm, mp4, mpeg, mpga.",
            "type": "invalid_request_error",
            "param": "file",
            "code": "UnsupportedFormat"
        }
    },

    "quota_exceeded": {
        "error": {
            "message": "Rate limit exceeded. Please retry after 60 seconds.",
            "type": "rate_limit_error",
            "param": null,
            "code": "RateLimitExceeded"
        }
    },

    "authentication_failed": {
        "error": {
            "message": "Invalid authentication credentials.",
            "type": "authentication_error", 
            "param": null,
            "code": "InvalidAuth"
        }
    },

    "service_unavailable": {
        "error": {
            "message": "The transcription service is temporarily unavailable.",
            "type": "service_error",
            "param": null,
            "code": "ServiceUnavailable"
        }
    },

    "corrupted_audio": {
        "error": {
            "message": "The audio file appears to be corrupted or unreadable.",
            "type": "invalid_request_error",
            "param": "file", 
            "code": "CorruptedFile"
        }
    },

    "timeout_error": {
        "error": {
            "message": "Request timed out. The audio file may be too long or complex.",
            "type": "timeout_error",
            "param": null,
            "code": "RequestTimeout"
        }
    }
}

# Model information responses
MODEL_RESPONSES = {
    "whisper_models": [
        {
            "id": "whisper-1",
            "name": "Whisper v1",
            "description": "General-purpose speech recognition model",
            "max_file_size_mb": 25,
            "supported_formats": ["mp3", "wav", "m4a", "ogg", "webm", "mp4", "mpeg", "mpga"],
            "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"],
            "capabilities": ["transcription", "translation"]
        },
        {
            "id": "gpt-4o-transcribe",
            "name": "GPT-4o Transcribe",
            "description": "Advanced speech-to-text powered by GPT-4o",
            "max_file_size_mb": 25,
            "supported_formats": ["mp3", "wav", "m4a", "ogg", "webm", "mp4", "mpeg", "mpga"],
            "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"],
            "capabilities": ["transcription", "enhanced_punctuation", "speaker_diarization"]
        },
        {
            "id": "gpt-4o-mini-transcribe", 
            "name": "GPT-4o Mini Transcribe",
            "description": "Fast and efficient speech-to-text powered by GPT-4o mini",
            "max_file_size_mb": 25,
            "supported_formats": ["mp3", "wav", "m4a", "ogg", "webm", "mp4", "mpeg", "mpga"],
            "supported_languages": ["en", "es", "fr", "de", "it", "pt"],
            "capabilities": ["transcription", "enhanced_punctuation"]
        }
    ]
}

# Health check responses
HEALTH_CHECK_RESPONSES = {
    "healthy": {
        "status": "healthy",
        "endpoint": "https://test-openai.openai.azure.com",
        "api_version": "2024-10-21",
        "default_model": "whisper",
        "token_acquisition_time_ms": 245.6,
        "authenticated": True,
        "token_expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    },

    "unhealthy_auth": {
        "status": "unhealthy",
        "error": "Authentication failed: Invalid credentials",
        "endpoint": "https://test-openai.openai.azure.com",
        "authenticated": False
    },

    "unhealthy_endpoint": {
        "status": "unhealthy", 
        "error": "Endpoint configuration missing",
        "endpoint": "unknown",
        "authenticated": False
    }
}

# Sample audio content for different formats
SAMPLE_AUDIO_DATA = {
    "wav": SAMPLE_WAV_HEADER + b"audio_data_placeholder" * 100,
    "mp3": b"\xff\xfb\x90\x00" + b"mp3_audio_data_placeholder" * 100,  # MP3 header
    "m4a": b"\x00\x00\x00\x20ftypM4A " + b"m4a_audio_data" * 100,  # M4A header
    "ogg": b"OggS\x00\x02\x00\x00" + b"ogg_audio_data" * 100,  # OGG header
    "webm": b"\x1a\x45\xdf\xa3" + b"webm_audio_data" * 100,  # WebM header
    "large_file": b"x" * (26 * 1024 * 1024),  # 26MB file (exceeds limit)
    "empty": b"",
    "corrupted": b"not_valid_audio_content"
}


@pytest.fixture
def sample_wav_content():
    """Provide sample WAV audio content for testing."""
    return SAMPLE_AUDIO_DATA["wav"]


@pytest.fixture
def sample_mp3_content():
    """Provide sample MP3 audio content for testing."""
    return SAMPLE_AUDIO_DATA["mp3"]


@pytest.fixture
def large_audio_content():
    """Provide large audio content that exceeds size limits."""
    return SAMPLE_AUDIO_DATA["large_file"]


@pytest.fixture
def corrupted_audio_content():
    """Provide corrupted audio content for error testing."""
    return SAMPLE_AUDIO_DATA["corrupted"]


@pytest.fixture
def transcription_responses():
    """Provide all transcription response fixtures."""
    return TRANSCRIPTION_RESPONSES


@pytest.fixture
def transcription_errors():
    """Provide all transcription error response fixtures."""
    return TRANSCRIPTION_ERRORS


@pytest.fixture
def supported_models_response():
    """Provide supported models response."""
    return MODEL_RESPONSES["whisper_models"]


@pytest.fixture
def health_check_responses():
    """Provide health check response fixtures."""
    return HEALTH_CHECK_RESPONSES


@pytest.fixture
def mock_azure_credential():
    """Mock Azure DefaultAzureCredential."""
    from unittest.mock import Mock
    from datetime import datetime, timedelta
    
    credential = Mock()
    
    # Mock token with future expiration
    mock_token = Mock()
    mock_token.token = "mock-azure-ai-token"
    mock_token.expires_on = (datetime.utcnow() + timedelta(hours=1)).timestamp()
    
    credential.get_token.return_value = mock_token
    
    return credential


@pytest.fixture
def mock_transcription_success_response(transcription_responses):
    """Mock successful HTTP response for transcription."""
    from unittest.mock import Mock
    
    response = Mock()
    response.status_code = 200
    response.json.return_value = transcription_responses["verbose_json_success"]
    
    return response


@pytest.fixture
def mock_transcription_text_response():
    """Mock successful HTTP response for text format transcription."""
    from unittest.mock import Mock
    
    response = Mock()
    response.status_code = 200
    response.text = "This is a mock text transcription response."
    
    return response


@pytest.fixture
def mock_transcription_error_response(transcription_errors):
    """Mock error HTTP response for transcription."""
    from unittest.mock import Mock
    
    response = Mock()
    response.status_code = 400
    response.json.return_value = transcription_errors["invalid_model"]
    response.text = "Bad Request"
    
    return response


@pytest.fixture
def mock_transcription_401_response():
    """Mock 401 unauthorized HTTP response."""
    from unittest.mock import Mock
    
    response = Mock()
    response.status_code = 401
    response.json.return_value = TRANSCRIPTION_ERRORS["authentication_failed"]
    response.text = "Unauthorized"
    
    return response


@pytest.fixture
def mock_transcription_429_response():
    """Mock 429 rate limit HTTP response."""
    from unittest.mock import Mock
    
    response = Mock()
    response.status_code = 429
    response.headers = {"Retry-After": "60"}
    response.json.return_value = TRANSCRIPTION_ERRORS["quota_exceeded"]
    response.text = "Too Many Requests"
    
    return response


@pytest.fixture
def mock_httpx_client_success(mock_transcription_success_response):
    """Mock httpx.AsyncClient for successful requests."""
    from unittest.mock import AsyncMock
    
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = mock_transcription_success_response
    
    return client


@pytest.fixture
def mock_httpx_client_error(mock_transcription_error_response):
    """Mock httpx.AsyncClient for error responses."""
    from unittest.mock import AsyncMock
    
    client = AsyncMock()
    client.__aenter__.return_value.post.return_value = mock_transcription_error_response
    
    return client


@pytest.fixture
def batch_transcription_files(sample_wav_content):
    """Provide sample files for batch transcription testing."""
    return [
        (sample_wav_content, "audio1.wav"),
        (sample_wav_content, "audio2.wav"),
        (sample_wav_content, "audio3.wav")
    ]


@pytest.fixture
def comprehensive_ai_responses():
    """Provide comprehensive response collection for complex testing scenarios."""
    return {
        "transcription_responses": TRANSCRIPTION_RESPONSES,
        "transcription_errors": TRANSCRIPTION_ERRORS,
        "model_responses": MODEL_RESPONSES,
        "health_check_responses": HEALTH_CHECK_RESPONSES,
        "sample_audio_data": SAMPLE_AUDIO_DATA
    }


def create_mock_transcription_result(
    text: str = "Mock transcription text",
    language: str = "en",
    duration: float = 10.0,
    segments: Optional[List[Dict[str, Any]]] = None,
    confidence_score: Optional[float] = 0.95
):
    """Factory function to create mock TranscriptionResult objects."""
    from app.azure.AzureAIFoundryService import TranscriptionResult
    
    if segments is None:
        segments = [
            {
                "id": 0,
                "start": 0.0,
                "end": duration,
                "text": text,
                "avg_logprob": -0.1
            }
        ]
    
    return TranscriptionResult(
        text=text,
        language=language,
        duration=duration,
        segments=segments,
        confidence_score=confidence_score
    )


def create_mock_batch_results(count: int = 3, include_errors: bool = False):
    """Factory function to create mock batch transcription results."""
    from app.azure.AzureAIFoundryService import TranscriptionResult
    
    results = []
    
    for i in range(count):
        filename = f"audio{i+1}.wav"
        
        if include_errors and i == count - 1:  # Last item is an error
            error = Exception(f"Transcription failed for {filename}")
            results.append((filename, error))
        else:
            result = TranscriptionResult(
                text=f"Mock transcription text for audio file {i+1}",
                language="en",
                duration=10.0 + i
            )
            results.append((filename, result))
    
    return results


# Content type validation test cases
CONTENT_TYPE_TEST_CASES = [
    ("test.wav", "audio/wav"),
    ("test.mp3", "audio/mpeg"),
    ("test.m4a", "audio/m4a"),
    ("test.aac", "audio/aac"),
    ("test.ogg", "audio/ogg"),
    ("test.opus", "audio/opus"),
    ("test.webm", "audio/webm"),
    ("test.flac", "audio/flac"),
    ("test.aiff", "audio/aiff"),
    ("test.amr", "audio/amr"),
    ("test.3gp", "audio/3gpp"),
    ("test.wma", "audio/x-ms-wma"),
    ("unknown.xyz", "audio/wav"),  # Default fallback
    ("", "audio/wav"),  # Empty filename
    ("no_extension", "audio/wav")  # No extension
]


@pytest.fixture(params=CONTENT_TYPE_TEST_CASES)
def content_type_test_case(request):
    """Parametrized fixture for content type detection testing."""
    return request.param


# Language code test cases
LANGUAGE_TEST_CASES = [
    ("en", "English"),
    ("es", "Spanish"), 
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("zh", "Chinese"),
    ("invalid", "Invalid")
]


@pytest.fixture(params=LANGUAGE_TEST_CASES)
def language_test_case(request):
    """Parametrized fixture for language code testing."""
    return request.param


# Response format test cases
RESPONSE_FORMAT_TEST_CASES = [
    "json",
    "verbose_json", 
    "text",
    "srt",
    "vtt"
]


@pytest.fixture(params=RESPONSE_FORMAT_TEST_CASES)
def response_format_test_case(request):
    """Parametrized fixture for response format testing.""" 
    return request.param


# Temperature test cases (valid range 0.0 to 1.0)
TEMPERATURE_TEST_CASES = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]


@pytest.fixture(params=TEMPERATURE_TEST_CASES)
def temperature_test_case(request):
    """Parametrized fixture for temperature parameter testing."""
    return request.param