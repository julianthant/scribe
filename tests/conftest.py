"""
Test configuration and shared fixtures for Scribe Voice Email Processor
Provides both mocked and real-data testing capabilities for comprehensive validation
"""

import pytest
import os
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any
import tempfile
import json

# Import production components
from src.core import (
    ScribeConfigurationManager,
    ScribeServiceInitializer,
    ScribeErrorHandler,
    ScribeLogger
)


@pytest.fixture
def production_config():
    """
    Configuration for testing with real Azure services and data
    Uses actual endpoints but mocked authentication for safety
    """
    return {
        # Real Azure endpoints
        'target_email': 'julianthant@gmail.com',
        'excel_file_name': 'Scribe.xlsx',
        'storage_account': 'scribepersonal20798',
        'key_vault_url': 'https://scribe-personal-vault.vault.azure.net/',
        'ai_foundry_url': 'https://eastus.api.azureml.ms/mlflow/v1.0/subscriptions/66f46848-fa31-40af-9eed-f3b759e5ed15/resourceGroups/scribe-voice-processor-rg/providers/Microsoft.MachineLearningServices/workspaces/scribe-ai-project',
        
        # Test configuration
        'use_real_services': True,
        'mock_authentication': True,
        'max_test_emails': 3,
        'test_timeout': 300  # 5 minutes
    }


@pytest.fixture
def mock_azure_services():
    """
    Comprehensive mock setup for all Azure services
    Use for unit testing without external dependencies
    """
    mocks = {
        # Authentication mocks
        'graph_token': 'mock-graph-token-12345',
        'managed_identity': Mock(),
        
        # Storage mocks
        'blob_client': Mock(),
        'blob_service': Mock(),
        
        # Key Vault mocks
        'key_vault_client': Mock(),
        
        # AI Foundry mocks
        'ai_foundry_client': Mock(),
        'transcription_response': {
            'status': 'completed',
            'transcript': 'This is a test transcription.',
            'confidence': 0.95,
            'duration': 30.5
        }
    }
    
    # Configure blob client mock
    mocks['blob_client'].upload_blob.return_value = Mock(url='https://test-blob-url.com/audio.wav')
    mocks['blob_client'].download_blob.return_value = Mock(content_as_bytes=lambda: b'mock-audio-data')
    
    return mocks


@pytest.fixture
def temp_excel_file():
    """
    Create a temporary Excel file for testing
    Mimics the structure of the real Scribe.xlsx file
    """
    import openpyxl
    
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
        # Create workbook with expected structure
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Voice Messages"
        
        # Add headers matching expected Scribe.xlsx structure
        headers = [
            'Date', 'Sender', 'Subject', 'Audio File', 
            'Transcription', 'Duration', 'Confidence', 'Status'
        ]
        
        for i, header in enumerate(headers, 1):
            ws.cell(row=1, column=i, value=header)
        
        wb.save(temp_file.name)
        yield temp_file.name
        
        # Cleanup
        os.unlink(temp_file.name)


@pytest.fixture
def mock_email_data():
    """
    Sample email data for testing email processing
    Includes voice attachments with various formats
    """
    return [
        {
            'message_id': 'test-email-001',
            'sender': 'test@example.com',
            'subject': 'Voice Message Test 1',
            'received_date': '2025-01-24T10:00:00Z',
            'voice_attachments': [
                {
                    'filename': 'voice_message_001.wav',
                    'content_type': 'audio/wav',
                    'size': 256000,
                    'attachment_id': 'att_001'
                }
            ]
        },
        {
            'message_id': 'test-email-002', 
            'sender': 'colleague@company.com',
            'subject': 'Important Voice Note',
            'received_date': '2025-01-24T11:30:00Z',
            'voice_attachments': [
                {
                    'filename': 'recording.m4a',
                    'content_type': 'audio/m4a',
                    'size': 512000,
                    'attachment_id': 'att_002'
                }
            ]
        }
    ]


@pytest.fixture
def core_services(production_config):
    """
    Initialize core production services for integration testing
    Uses dependency injection pattern from production architecture
    """
    # Create core services
    config_manager = ScribeConfigurationManager()
    logger = ScribeLogger()
    error_handler = ScribeErrorHandler(logger)
    service_initializer = ScribeServiceInitializer(config_manager)
    
    return {
        'config_manager': config_manager,
        'logger': logger,
        'error_handler': error_handler,
        'service_initializer': service_initializer
    }


@pytest.fixture
def environment_setup():
    """
    Setup test environment variables
    Ensures tests have proper configuration
    """
    test_env = {
        'CLIENT_ID': 'd8977d26-41f6-45aa-8527-11db1d7d6716',
        'TENANT_ID': 'common',
        'KEY_VAULT_URL': 'https://scribe-personal-vault.vault.azure.net/',
        'AI_FOUNDRY_PROJECT_URL': 'https://eastus.api.azureml.ms/mlflow/v1.0/subscriptions/66f46848-fa31-40af-9eed-f3b759e5ed15/resourceGroups/scribe-voice-processor-rg/providers/Microsoft.MachineLearningServices/workspaces/scribe-ai-project',
        'EXCEL_FILE_NAME': 'Scribe.xlsx',
        'TARGET_USER_EMAIL': 'julianthant@gmail.com',
        'AZURE_FUNCTIONS_ENVIRONMENT': 'Testing'
    }
    
    # Set environment variables
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield test_env
    
    # Restore original environment
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


@pytest.fixture
def sample_audio_data():
    """
    Generate sample audio data for transcription testing
    Returns bytes that can be used as mock audio content
    """
    # This would contain actual audio bytes in a real scenario
    # For testing, we use placeholder data
    return b'RIFF\x00\x00\x00\x00WAVE' + b'\x00' * 1000  # Mock WAV header + data


@pytest.fixture
def expected_transcription_result():
    """
    Expected structure of transcription results from Azure AI Foundry
    Used for validating processor outputs
    """
    return {
        'status': 'completed',
        'transcript': 'Hello, this is a test voice message for the Scribe application.',
        'confidence': 0.92,
        'duration': 8.5,
        'language': 'en-US',
        'created_time': '2025-01-24T12:00:00Z',
        'processing_time': 2.3
    }


# Helper functions for test validation
def assert_processor_success(result: Dict[str, Any]) -> None:
    """Assert that a processor operation completed successfully"""
    assert result.get('success') is True, f"Processor failed: {result.get('error', 'Unknown error')}"
    assert 'processing_time' in result
    assert result['processing_time'] > 0


def assert_structured_logging(logger_mock: Mock, expected_events: list) -> None:
    """Assert that structured logging events were recorded"""
    call_args_list = logger_mock.log_info.call_args_list
    logged_events = [call[0][0] for call in call_args_list]
    
    for expected_event in expected_events:
        assert any(expected_event in event for event in logged_events), \
            f"Expected log event '{expected_event}' not found"


def assert_error_handling(error_handler_mock: Mock, error_types: list) -> None:
    """Assert that error handling was triggered for specific error types"""
    call_args_list = error_handler_mock.handle_error.call_args_list
    handled_errors = [call[0][0].__class__.__name__ for call in call_args_list]
    
    for error_type in error_types:
        assert error_type in handled_errors, \
            f"Expected error type '{error_type}' was not handled"
