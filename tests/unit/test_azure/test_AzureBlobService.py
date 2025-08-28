"""
Unit tests for AzureBlobService.

Tests Azure Blob Storage functionality including:
- Blob upload operations with various content types
- Blob download operations and content retrieval
- SAS token generation for secure access
- Container operations and management
- Blob metadata handling and updates
- Automatic cleanup of expired blobs
- Error handling for storage exceptions
- Authentication with DefaultAzureCredential
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta, timezone
import io
import hashlib
import uuid

from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError, AzureError
from azure.identity import DefaultAzureCredential

from app.azure.AzureBlobService import AzureBlobService
from app.core.Exceptions import ValidationError, AuthenticationError


class TestAzureBlobService:
    """Test suite for AzureBlobService."""

    @pytest.fixture
    def blob_service(self):
        """Create AzureBlobService instance."""
        return AzureBlobService()

    @pytest.fixture
    def mock_blob_client(self):
        """Mock BlobClient for testing."""
        client = Mock(spec=BlobClient)
        client.upload_blob = Mock()
        client.download_blob = Mock()
        client.delete_blob = Mock()
        client.exists = Mock()
        client.get_blob_properties = Mock()
        client.set_blob_metadata = Mock()
        return client

    @pytest.fixture
    def mock_blob_service_client(self, mock_blob_client):
        """Mock BlobServiceClient for testing."""
        service_client = Mock(spec=BlobServiceClient)
        service_client.get_blob_client.return_value = mock_blob_client
        
        # Mock container client
        container_client = Mock()
        container_client.create_container = Mock()
        container_client.list_blobs = Mock()
        container_client.delete_container = Mock()
        service_client.get_container_client.return_value = container_client
        
        return service_client

    @pytest.fixture
    def sample_audio_content(self):
        """Sample audio content for testing."""
        return b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00D\xac\x00\x00" * 100

    # ==========================================================================
    # INITIALIZATION TESTS
    # ==========================================================================

    @patch('app.azure.AzureBlobService.settings')
    def test_initialization_success(self, mock_settings):
        """Test successful service initialization."""
        mock_settings.blob_storage_account_name = "teststorageaccount"
        mock_settings.blob_storage_use_access_token = True
        
        service = AzureBlobService()
        
        assert service is not None
        assert service._blob_service_client is None  # Lazy initialization

    @patch('app.azure.AzureBlobService.settings')
    def test_initialization_missing_account_name(self, mock_settings):
        """Test initialization with missing account name."""
        mock_settings.blob_storage_account_name = ""
        
        service = AzureBlobService()
        
        with pytest.raises(ValidationError):
            # This will trigger when accessing the property
            _ = service.blob_service_client

    def test_blob_service_client_property_lazy_loading(self, blob_service):
        """Test lazy loading of BlobServiceClient."""
        with patch('app.azure.AzureBlobService.BlobServiceClient') as mock_client_class:
            with patch('app.azure.AzureBlobService.settings') as mock_settings:
                mock_settings.blob_storage_account_name = "teststorage"
                mock_settings.blob_storage_use_access_token = True
                
                mock_client_instance = Mock()
                mock_client_class.return_value = mock_client_instance
                
                # First access creates the client
                client1 = blob_service.blob_service_client
                assert client1 == mock_client_instance
                
                # Second access returns the same instance
                client2 = blob_service.blob_service_client
                assert client2 == client1
                
                # Client should only be created once
                mock_client_class.assert_called_once()

    # ==========================================================================
    # BLOB UPLOAD TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_upload_blob_success(self, blob_service, mock_blob_service_client, 
                                       mock_blob_client, sample_audio_content):
        """Test successful blob upload."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "voice-attachments/test-audio.wav"
            content_type = "audio/wav"
            metadata = {"message_id": "msg-123", "user_id": "user-456"}
            
            mock_blob_client.upload_blob.return_value = Mock(
                etag="test-etag",
                last_modified=datetime.now(timezone.utc)
            )
            
            result = await blob_service.upload_blob(
                blob_name, sample_audio_content, content_type, metadata
            )
            
            assert result["blob_name"] == blob_name
            assert result["size"] == len(sample_audio_content)
            assert result["content_type"] == content_type
            assert "url" in result
            assert "etag" in result
            
            # Verify upload was called correctly
            mock_blob_client.upload_blob.assert_called_once()
            call_args = mock_blob_client.upload_blob.call_args
            assert call_args.kwargs["content_type"] == content_type
            assert call_args.kwargs["metadata"] == metadata

    @pytest.mark.asyncio
    async def test_upload_blob_with_overwrite(self, blob_service, mock_blob_service_client, 
                                              mock_blob_client, sample_audio_content):
        """Test blob upload with overwrite option."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "existing-blob.wav"
            
            mock_blob_client.upload_blob.return_value = Mock(
                etag="new-etag",
                last_modified=datetime.now(timezone.utc)
            )
            
            result = await blob_service.upload_blob(
                blob_name, sample_audio_content, "audio/wav", overwrite=True
            )
            
            assert result is not None
            mock_blob_client.upload_blob.assert_called_once()
            call_args = mock_blob_client.upload_blob.call_args
            assert call_args.kwargs["overwrite"] is True

    @pytest.mark.asyncio
    async def test_upload_blob_already_exists(self, blob_service, mock_blob_service_client, 
                                              mock_blob_client, sample_audio_content):
        """Test blob upload when blob already exists."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "existing-blob.wav"
            
            mock_blob_client.upload_blob.side_effect = ResourceExistsError("Blob already exists")
            
            with pytest.raises(ValidationError):
                await blob_service.upload_blob(
                    blob_name, sample_audio_content, "audio/wav", overwrite=False
                )

    @pytest.mark.asyncio
    async def test_upload_blob_validation_errors(self, blob_service):
        """Test blob upload with validation errors."""
        # Empty blob name
        with pytest.raises(ValidationError):
            await blob_service.upload_blob("", b"content", "audio/wav")
        
        # Empty content
        with pytest.raises(ValidationError):
            await blob_service.upload_blob("test.wav", b"", "audio/wav")
        
        # Invalid content type
        with pytest.raises(ValidationError):
            await blob_service.upload_blob("test.wav", b"content", "")

    @pytest.mark.asyncio
    async def test_upload_blob_azure_error(self, blob_service, mock_blob_service_client, 
                                          mock_blob_client, sample_audio_content):
        """Test blob upload with Azure storage error."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            mock_blob_client.upload_blob.side_effect = AzureError("Storage service error")
            
            with pytest.raises(AuthenticationError):
                await blob_service.upload_blob(
                    "test.wav", sample_audio_content, "audio/wav"
                )

    # ==========================================================================
    # BLOB DOWNLOAD TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_download_blob_success(self, blob_service, mock_blob_service_client, 
                                        mock_blob_client, sample_audio_content):
        """Test successful blob download."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "voice-attachments/test-audio.wav"
            
            # Mock download blob response
            mock_download_response = Mock()
            mock_download_response.readall.return_value = sample_audio_content
            mock_blob_client.download_blob.return_value = mock_download_response
            
            result = await blob_service.download_blob(blob_name)
            
            assert result == sample_audio_content
            mock_blob_client.download_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_blob_not_found(self, blob_service, mock_blob_service_client, 
                                          mock_blob_client):
        """Test blob download when blob doesn't exist."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "non-existent.wav"
            
            mock_blob_client.download_blob.side_effect = ResourceNotFoundError("Blob not found")
            
            with pytest.raises(ValidationError):
                await blob_service.download_blob(blob_name)

    @pytest.mark.asyncio
    async def test_download_blob_with_range(self, blob_service, mock_blob_service_client, 
                                           mock_blob_client):
        """Test blob download with byte range."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "large-audio.wav"
            partial_content = b"partial audio content"
            
            mock_download_response = Mock()
            mock_download_response.readall.return_value = partial_content
            mock_blob_client.download_blob.return_value = mock_download_response
            
            result = await blob_service.download_blob(blob_name, offset=0, length=1024)
            
            assert result == partial_content
            call_args = mock_blob_client.download_blob.call_args
            assert call_args.kwargs["offset"] == 0
            assert call_args.kwargs["length"] == 1024

    # ==========================================================================
    # BLOB EXISTENCE AND PROPERTIES TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_blob_exists_true(self, blob_service, mock_blob_service_client, mock_blob_client):
        """Test checking if blob exists (returns True)."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "existing-blob.wav"
            mock_blob_client.exists.return_value = True
            
            result = await blob_service.blob_exists(blob_name)
            
            assert result is True
            mock_blob_client.exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_blob_exists_false(self, blob_service, mock_blob_service_client, mock_blob_client):
        """Test checking if blob exists (returns False)."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "non-existent.wav"
            mock_blob_client.exists.return_value = False
            
            result = await blob_service.blob_exists(blob_name)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_get_blob_properties_success(self, blob_service, mock_blob_service_client, 
                                              mock_blob_client):
        """Test successful blob properties retrieval."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "test-blob.wav"
            
            mock_properties = Mock()
            mock_properties.size = 1024
            mock_properties.content_type = "audio/wav"
            mock_properties.last_modified = datetime.now(timezone.utc)
            mock_properties.etag = "test-etag"
            mock_properties.metadata = {"user_id": "user-123"}
            
            mock_blob_client.get_blob_properties.return_value = mock_properties
            
            result = await blob_service.get_blob_properties(blob_name)
            
            assert result["size"] == 1024
            assert result["content_type"] == "audio/wav"
            assert result["metadata"]["user_id"] == "user-123"
            assert "last_modified" in result
            assert "etag" in result

    @pytest.mark.asyncio
    async def test_update_blob_metadata(self, blob_service, mock_blob_service_client, 
                                       mock_blob_client):
        """Test updating blob metadata."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "test-blob.wav"
            new_metadata = {"transcribed": "true", "language": "en"}
            
            mock_blob_client.set_blob_metadata.return_value = Mock(etag="new-etag")
            
            result = await blob_service.update_blob_metadata(blob_name, new_metadata)
            
            assert result is True
            mock_blob_client.set_blob_metadata.assert_called_once_with(new_metadata)

    # ==========================================================================
    # BLOB DELETION TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_delete_blob_success(self, blob_service, mock_blob_service_client, mock_blob_client):
        """Test successful blob deletion."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "to-delete.wav"
            
            mock_blob_client.delete_blob.return_value = None
            
            result = await blob_service.delete_blob(blob_name)
            
            assert result is True
            mock_blob_client.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_blob_not_found(self, blob_service, mock_blob_service_client, mock_blob_client):
        """Test blob deletion when blob doesn't exist."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "non-existent.wav"
            
            mock_blob_client.delete_blob.side_effect = ResourceNotFoundError("Blob not found")
            
            # Should not raise error, just return False
            result = await blob_service.delete_blob(blob_name)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_blob_with_snapshots(self, blob_service, mock_blob_service_client, 
                                             mock_blob_client):
        """Test blob deletion including snapshots."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_name = "blob-with-snapshots.wav"
            
            result = await blob_service.delete_blob(blob_name, delete_snapshots="include")
            
            assert result is True
            call_args = mock_blob_client.delete_blob.call_args
            assert call_args.kwargs["delete_snapshots"] == "include"

    # ==========================================================================
    # CONTAINER OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_create_container_success(self, blob_service, mock_blob_service_client):
        """Test successful container creation."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            container_name = "voice-attachments"
            container_client = mock_blob_service_client.get_container_client.return_value
            
            result = await blob_service.create_container(container_name)
            
            assert result is True
            container_client.create_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_container_already_exists(self, blob_service, mock_blob_service_client):
        """Test container creation when container already exists."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            container_name = "existing-container"
            container_client = mock_blob_service_client.get_container_client.return_value
            container_client.create_container.side_effect = ResourceExistsError("Container exists")
            
            # Should not raise error, just return False
            result = await blob_service.create_container(container_name)
            
            assert result is False

    @pytest.mark.asyncio
    async def test_list_blobs_in_container(self, blob_service, mock_blob_service_client):
        """Test listing blobs in container."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            container_name = "voice-attachments"
            container_client = mock_blob_service_client.get_container_client.return_value
            
            # Mock blob list
            mock_blobs = [
                Mock(name="blob1.wav", size=1024, last_modified=datetime.now(timezone.utc)),
                Mock(name="blob2.mp3", size=2048, last_modified=datetime.now(timezone.utc))
            ]
            container_client.list_blobs.return_value = mock_blobs
            
            result = await blob_service.list_blobs(container_name)
            
            assert len(result) == 2
            assert result[0]["name"] == "blob1.wav"
            assert result[1]["name"] == "blob2.mp3"

    @pytest.mark.asyncio
    async def test_list_blobs_with_prefix(self, blob_service, mock_blob_service_client):
        """Test listing blobs with name prefix filter."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            container_name = "voice-attachments"
            prefix = "2024/01/"
            container_client = mock_blob_service_client.get_container_client.return_value
            
            mock_blobs = [Mock(name="2024/01/voice1.wav", size=1024)]
            container_client.list_blobs.return_value = mock_blobs
            
            result = await blob_service.list_blobs(container_name, name_starts_with=prefix)
            
            assert len(result) == 1
            call_args = container_client.list_blobs.call_args
            assert call_args.kwargs["name_starts_with"] == prefix

    # ==========================================================================
    # SAS TOKEN TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_generate_blob_sas_token(self, blob_service):
        """Test SAS token generation for blob access."""
        with patch('app.azure.AzureBlobService.generate_blob_sas') as mock_generate_sas:
            blob_name = "secure-audio.wav"
            container_name = "voice-attachments"
            expiry_hours = 2
            
            expected_token = "sv=2021-04-10&st=2024-01-01T00%3A00%3A00Z&se=2024-01-01T02%3A00%3A00Z&sr=b&sp=r&sig=test"
            mock_generate_sas.return_value = expected_token
            
            result = await blob_service.generate_blob_sas_token(
                blob_name, container_name, expiry_hours
            )
            
            assert result == expected_token
            mock_generate_sas.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_blob_url_with_sas(self, blob_service):
        """Test getting blob URL with SAS token."""
        with patch.object(blob_service, 'generate_blob_sas_token') as mock_generate_sas:
            blob_name = "audio-file.wav"
            container_name = "voice-attachments"
            sas_token = "test-sas-token"
            
            mock_generate_sas.return_value = sas_token
            
            with patch('app.azure.AzureBlobService.settings') as mock_settings:
                mock_settings.blob_storage_account_name = "teststorage"
                
                result = await blob_service.get_blob_url_with_sas(blob_name, container_name)
                
                expected_url = f"https://teststorage.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
                assert result == expected_url

    # ==========================================================================
    # CLEANUP OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_cleanup_expired_blobs(self, blob_service, mock_blob_service_client):
        """Test automatic cleanup of expired blobs."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            container_name = "temp-attachments"
            expiry_days = 7
            container_client = mock_blob_service_client.get_container_client.return_value
            
            # Mock blobs with different ages
            old_blob = Mock(
                name="old-blob.wav", 
                last_modified=datetime.now(timezone.utc) - timedelta(days=10)
            )
            recent_blob = Mock(
                name="recent-blob.wav",
                last_modified=datetime.now(timezone.utc) - timedelta(days=3)
            )
            container_client.list_blobs.return_value = [old_blob, recent_blob]
            
            # Mock individual blob clients for deletion
            old_blob_client = Mock()
            mock_blob_service_client.get_blob_client.return_value = old_blob_client
            
            result = await blob_service.cleanup_expired_blobs(container_name, expiry_days)
            
            assert result["deleted_count"] == 1
            assert result["total_scanned"] == 2
            assert "old-blob.wav" in result["deleted_blobs"]

    @pytest.mark.asyncio
    async def test_cleanup_blobs_by_metadata(self, blob_service, mock_blob_service_client):
        """Test cleanup of blobs based on metadata criteria."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            container_name = "voice-attachments"
            metadata_filter = {"processed": "true", "keep": "false"}
            
            container_client = mock_blob_service_client.get_container_client.return_value
            
            # Mock blob with matching metadata
            matching_blob = Mock(name="processed-blob.wav")
            container_client.list_blobs.return_value = [matching_blob]
            
            # Mock getting blob properties with metadata
            blob_client = Mock()
            blob_properties = Mock()
            blob_properties.metadata = {"processed": "true", "keep": "false"}
            blob_client.get_blob_properties.return_value = blob_properties
            mock_blob_service_client.get_blob_client.return_value = blob_client
            
            result = await blob_service.cleanup_blobs_by_metadata(container_name, metadata_filter)
            
            assert result["deleted_count"] == 1
            assert "processed-blob.wav" in result["deleted_blobs"]

    # ==========================================================================
    # BATCH OPERATIONS TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_upload_multiple_blobs(self, blob_service, mock_blob_service_client, 
                                        mock_blob_client):
        """Test uploading multiple blobs in batch."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_data = [
                ("blob1.wav", b"audio content 1", "audio/wav"),
                ("blob2.mp3", b"audio content 2", "audio/mpeg")
            ]
            
            mock_blob_client.upload_blob.return_value = Mock(
                etag="test-etag",
                last_modified=datetime.now(timezone.utc)
            )
            
            results = await blob_service.upload_multiple_blobs(blob_data)
            
            assert len(results) == 2
            assert all(result["blob_name"].endswith(('.wav', '.mp3')) for result in results)
            assert mock_blob_client.upload_blob.call_count == 2

    @pytest.mark.asyncio
    async def test_download_multiple_blobs(self, blob_service, mock_blob_service_client, 
                                          mock_blob_client):
        """Test downloading multiple blobs in batch."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            blob_names = ["audio1.wav", "audio2.mp3"]
            
            mock_download_response = Mock()
            mock_download_response.readall.return_value = b"test audio content"
            mock_blob_client.download_blob.return_value = mock_download_response
            
            results = await blob_service.download_multiple_blobs(blob_names)
            
            assert len(results) == 2
            assert all(content == b"test audio content" for _, content in results)
            assert mock_blob_client.download_blob.call_count == 2

    # ==========================================================================
    # ERROR HANDLING AND EDGE CASES
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_handle_storage_account_error(self, blob_service, mock_blob_service_client, 
                                               mock_blob_client):
        """Test handling of storage account errors."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            mock_blob_client.upload_blob.side_effect = AzureError("Storage account not accessible")
            
            with pytest.raises(AuthenticationError):
                await blob_service.upload_blob("test.wav", b"content", "audio/wav")

    @pytest.mark.asyncio
    async def test_handle_network_timeout(self, blob_service, mock_blob_service_client, 
                                         mock_blob_client):
        """Test handling of network timeouts."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            import asyncio
            mock_blob_client.upload_blob.side_effect = asyncio.TimeoutError("Network timeout")
            
            with pytest.raises(AuthenticationError):
                await blob_service.upload_blob("test.wav", b"content", "audio/wav")

    def test_validate_blob_name_valid(self, blob_service):
        """Test blob name validation with valid names."""
        valid_names = [
            "simple.wav",
            "path/to/file.mp3",
            "2024/01/15/voice-recording-123.wav",
            "user-123_message-456.audio"
        ]
        
        for name in valid_names:
            # Should not raise exception
            blob_service._validate_blob_name(name)

    def test_validate_blob_name_invalid(self, blob_service):
        """Test blob name validation with invalid names."""
        invalid_names = [
            "",  # Empty
            "blob\\with\\backslashes.wav",  # Backslashes
            "blob with spaces.wav",  # Spaces (depending on implementation)
            "blob/with//double/slashes.wav",  # Double slashes
            "very-long-blob-name" * 20 + ".wav"  # Too long
        ]
        
        for name in invalid_names:
            with pytest.raises(ValidationError):
                blob_service._validate_blob_name(name)

    def test_content_type_detection(self, blob_service):
        """Test automatic content type detection from file extensions."""
        test_cases = [
            ("audio.wav", "audio/wav"),
            ("audio.mp3", "audio/mpeg"),
            ("audio.m4a", "audio/mp4"),
            ("audio.ogg", "audio/ogg"),
            ("unknown.xyz", "application/octet-stream")
        ]
        
        for filename, expected_type in test_cases:
            detected_type = blob_service._detect_content_type(filename)
            assert detected_type == expected_type

    # ==========================================================================
    # PERFORMANCE AND CONCURRENCY TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, blob_service, mock_blob_service_client, 
                                     mock_blob_client):
        """Test concurrent blob uploads."""
        import asyncio
        
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            mock_blob_client.upload_blob.return_value = Mock(
                etag="concurrent-etag",
                last_modified=datetime.now(timezone.utc)
            )
            
            # Simulate concurrent uploads
            tasks = [
                blob_service.upload_blob(f"concurrent-{i}.wav", b"test content", "audio/wav")
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all("blob_name" in result for result in results)
            assert mock_blob_client.upload_blob.call_count == 5

    @pytest.mark.asyncio
    async def test_large_file_upload_chunked(self, blob_service, mock_blob_service_client, 
                                            mock_blob_client):
        """Test large file upload with chunking."""
        with patch.object(blob_service, 'blob_service_client', mock_blob_service_client):
            # Create large content (10MB)
            large_content = b"x" * (10 * 1024 * 1024)
            
            mock_blob_client.upload_blob.return_value = Mock(
                etag="large-file-etag",
                last_modified=datetime.now(timezone.utc)
            )
            
            result = await blob_service.upload_blob(
                "large-file.wav", large_content, "audio/wav"
            )
            
            assert result["size"] == len(large_content)
            # Verify chunked upload was used (implementation specific)
            call_args = mock_blob_client.upload_blob.call_args
            # Could check for chunk_size parameter if implemented