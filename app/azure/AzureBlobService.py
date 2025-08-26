"""
AzureBlobService.py - Azure Blob Storage Service

Provides Azure Blob Storage operations for voice attachments.
This service handles:
- Voice attachment upload to blob storage
- Secure blob download with SAS tokens
- Blob metadata management
- Container operations
- Automatic cleanup of expired blobs

The AzureBlobService class provides comprehensive blob storage
capabilities for the Scribe voice attachment system.
"""

from typing import Optional, Dict, Any, List
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib

from azure.storage.blob import BlobServiceClient, BlobClient, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError, AzureError
from azure.identity import DefaultAzureCredential

from app.core.config import settings
from app.core.Exceptions import ValidationError, AuthenticationError

logger = logging.getLogger(__name__)


class AzureBlobService:
    """Azure Blob Storage service for voice attachments."""

    def __init__(self):
        """Initialize Azure Blob Storage service."""
        self._blob_service_client: Optional[BlobServiceClient] = None
        self._credential: Optional[DefaultAzureCredential] = None
    
    @property
    def blob_service_client(self) -> BlobServiceClient:
        """Get or create blob service client."""
        if self._blob_service_client is None:
            account_name = getattr(settings, 'blob_storage_account_name', '')
            use_access_token = getattr(settings, 'blob_storage_use_access_token', True)
            
            if not account_name:
                raise ValidationError(
                    "Blob storage account name not configured. Set blob_storage_account_name in settings.toml",
                    error_code="BLOB_CONFIG_MISSING"
                )
            
            account_url = f"https://{account_name}.blob.core.windows.net"
            
            if use_access_token:
                # Use Azure AD authentication
                if self._credential is None:
                    self._credential = DefaultAzureCredential()
                self._blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=self._credential
                )
                logger.info("Blob service client initialized with Azure AD authentication")
            else:
                # For development - would use connection string or account key
                # This should be configured via environment variables in production
                raise ValidationError(
                    "Account key authentication not implemented. Use Azure AD authentication.",
                    error_code="BLOB_AUTH_NOT_SUPPORTED"
                )
        
        return self._blob_service_client
    
    async def ensure_container_exists(self) -> None:
        """Ensure the voice attachments container exists."""
        try:
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # Try to get container properties (this will fail if container doesn't exist)
            try:
                await container_client.get_container_properties()
                logger.debug(f"Container '{container_name}' already exists")
            except ResourceNotFoundError:
                # Container doesn't exist, create it
                public_access = getattr(settings, 'blob_storage_public_access', False)
                public_access_type = None if not public_access else "container"
                
                await container_client.create_container(public_access=public_access_type)
                logger.info(f"Created blob storage container: {container_name}")
                
        except Exception as e:
            logger.error(f"Failed to ensure container exists: {str(e)}")
            raise AuthenticationError(f"Failed to access blob storage: {str(e)}")
    
    def generate_blob_name(
        self,
        message_id: str,
        attachment_id: str,
        original_filename: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """Generate a unique blob name for a voice attachment.
        
        Args:
            message_id: Graph API message ID
            attachment_id: Graph API attachment ID
            original_filename: Original file name
            user_id: User ID for additional uniqueness
            
        Returns:
            Unique blob name
        """
        # Create a hash of message_id + attachment_id for uniqueness
        unique_data = f"{message_id}_{attachment_id}"
        if user_id:
            unique_data += f"_{user_id}"
            
        hash_value = hashlib.sha256(unique_data.encode()).hexdigest()[:16]
        
        # Extract extension from original filename
        extension = ""
        if original_filename:
            extension = Path(original_filename).suffix.lower()
        
        # Generate timestamp for additional uniqueness
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        return f"voice_{timestamp}_{hash_value}{extension}"
    
    async def upload_voice_attachment(
        self,
        content: bytes,
        blob_name: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None,
        overwrite: bool = False
    ) -> str:
        """Upload voice attachment to blob storage.
        
        Args:
            content: File content as bytes
            blob_name: Unique blob name
            content_type: MIME content type
            metadata: Optional metadata dictionary
            overwrite: Whether to overwrite existing blob
            
        Returns:
            Blob URL
            
        Raises:
            ValidationError: If validation fails
            AuthenticationError: If upload fails
        """
        try:
            # Validate file size
            max_size_mb = getattr(settings, 'blob_storage_max_size_mb', 50)
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if len(content) > max_size_bytes:
                raise ValidationError(
                    f"File size {len(content)} bytes exceeds maximum {max_size_bytes} bytes",
                    error_code="FILE_TOO_LARGE"
                )
            
            # Validate file extension
            extension = Path(blob_name).suffix.lower()
            allowed_extensions = getattr(settings, 'blob_storage_allowed_extensions', [])
            if allowed_extensions and extension not in allowed_extensions:
                raise ValidationError(
                    f"File extension {extension} not allowed. Allowed: {allowed_extensions}",
                    error_code="INVALID_FILE_TYPE"
                )
            
            # Ensure container exists
            await self.ensure_container_exists()
            
            # Get blob client
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Prepare blob metadata
            blob_metadata = {
                "content_type": content_type,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "file_size": str(len(content))
            }
            if metadata:
                blob_metadata.update(metadata)
            
            # Upload blob
            await blob_client.upload_blob(
                data=content,
                content_type=content_type,
                metadata=blob_metadata,
                overwrite=overwrite
            )
            
            blob_url = blob_client.url
            logger.info(f"Uploaded voice attachment to blob: {blob_name} ({len(content)} bytes)")
            return blob_url
            
        except (ValidationError, AuthenticationError):
            raise
        except ResourceExistsError:
            raise ValidationError(
                f"Blob {blob_name} already exists. Use overwrite=True to replace.",
                error_code="BLOB_EXISTS"
            )
        except AzureError as e:
            logger.error(f"Azure error uploading blob {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to upload voice attachment: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error uploading blob {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to upload voice attachment: {str(e)}")
    
    async def download_voice_attachment(
        self,
        blob_name: str
    ) -> bytes:
        """Download voice attachment from blob storage.
        
        Args:
            blob_name: Blob name to download
            
        Returns:
            File content as bytes
            
        Raises:
            ValidationError: If blob not found
            AuthenticationError: If download fails
        """
        try:
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Download blob content
            download_stream = await blob_client.download_blob()
            content = await download_stream.readall()
            
            logger.info(f"Downloaded voice attachment: {blob_name} ({len(content)} bytes)")
            return content
            
        except ResourceNotFoundError:
            raise ValidationError(
                f"Voice attachment {blob_name} not found",
                error_code="BLOB_NOT_FOUND"
            )
        except AzureError as e:
            logger.error(f"Azure error downloading blob {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to download voice attachment: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error downloading blob {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to download voice attachment: {str(e)}")
    
    async def get_blob_metadata(
        self,
        blob_name: str
    ) -> Dict[str, Any]:
        """Get blob metadata and properties.
        
        Args:
            blob_name: Blob name
            
        Returns:
            Dictionary with blob metadata and properties
            
        Raises:
            ValidationError: If blob not found
            AuthenticationError: If retrieval fails
        """
        try:
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Get blob properties
            properties = await blob_client.get_blob_properties()
            
            metadata = {
                "blob_name": blob_name,
                "size": properties.size,
                "content_type": properties.content_settings.content_type,
                "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
                "created_on": properties.creation_time.isoformat() if properties.creation_time else None,
                "metadata": properties.metadata or {},
                "etag": properties.etag,
                "blob_url": blob_client.url
            }
            
            return metadata
            
        except ResourceNotFoundError:
            raise ValidationError(
                f"Voice attachment {blob_name} not found",
                error_code="BLOB_NOT_FOUND"
            )
        except AzureError as e:
            logger.error(f"Azure error getting blob metadata {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to get blob metadata: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting blob metadata {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to get blob metadata: {str(e)}")
    
    def generate_sas_url(
        self,
        blob_name: str,
        expiry_hours: Optional[int] = None,
        permissions: str = "r"
    ) -> str:
        """Generate a SAS URL for secure blob access.
        
        Args:
            blob_name: Blob name
            expiry_hours: Hours until SAS expires (default from settings)
            permissions: SAS permissions (default: read-only)
            
        Returns:
            SAS URL for the blob
            
        Raises:
            AuthenticationError: If SAS generation fails
        """
        try:
            if expiry_hours is None:
                expiry_hours = getattr(settings, 'blob_storage_sas_expiry_hours', 24)
            
            account_name = getattr(settings, 'blob_storage_account_name', '')
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=None,  # We'll use user delegation key with Azure AD
                permission=BlobSasPermissions(read=True, write=False),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
            
            logger.info(f"Generated SAS URL for {blob_name} (expires in {expiry_hours}h)")
            return blob_url
            
        except Exception as e:
            logger.error(f"Failed to generate SAS URL for {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to generate secure access URL: {str(e)}")
    
    async def delete_voice_attachment(
        self,
        blob_name: str
    ) -> bool:
        """Delete voice attachment from blob storage.
        
        Args:
            blob_name: Blob name to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValidationError: If blob not found
            AuthenticationError: If deletion fails
        """
        try:
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            await blob_client.delete_blob()
            logger.info(f"Deleted voice attachment: {blob_name}")
            return True
            
        except ResourceNotFoundError:
            raise ValidationError(
                f"Voice attachment {blob_name} not found",
                error_code="BLOB_NOT_FOUND"
            )
        except AzureError as e:
            logger.error(f"Azure error deleting blob {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to delete voice attachment: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting blob {blob_name}: {str(e)}")
            raise AuthenticationError(f"Failed to delete voice attachment: {str(e)}")
    
    async def list_voice_attachments(
        self,
        name_starts_with: Optional[str] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """List voice attachments in blob storage.
        
        Args:
            name_starts_with: Optional prefix filter
            include_metadata: Whether to include blob metadata
            
        Returns:
            List of blob information dictionaries
            
        Raises:
            AuthenticationError: If listing fails
        """
        try:
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            container_client = self.blob_service_client.get_container_client(container_name)
            
            blobs = []
            async for blob in container_client.list_blobs(
                name_starts_with=name_starts_with,
                include=['metadata'] if include_metadata else None
            ):
                blob_info = {
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_settings.content_type if blob.content_settings else None,
                    "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "created_on": blob.creation_time.isoformat() if blob.creation_time else None,
                }
                
                if include_metadata and blob.metadata:
                    blob_info["metadata"] = blob.metadata
                
                blobs.append(blob_info)
            
            logger.info(f"Listed {len(blobs)} voice attachments from blob storage")
            return blobs
            
        except AzureError as e:
            logger.error(f"Azure error listing blobs: {str(e)}")
            raise AuthenticationError(f"Failed to list voice attachments: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error listing blobs: {str(e)}")
            raise AuthenticationError(f"Failed to list voice attachments: {str(e)}")
    
    async def cleanup_expired_attachments(
        self,
        max_age_days: Optional[int] = None
    ) -> int:
        """Clean up expired voice attachments.
        
        Args:
            max_age_days: Maximum age in days (default from settings)
            
        Returns:
            Number of blobs deleted
            
        Raises:
            AuthenticationError: If cleanup fails
        """
        try:
            if max_age_days is None:
                max_age_days = getattr(settings, 'blob_storage_default_expiry_days', 90)
            
            cutoff_date = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=max_age_days)
            
            container_name = getattr(settings, 'blob_storage_container_name', 'voice-attachments')
            container_client = self.blob_service_client.get_container_client(container_name)
            
            deleted_count = 0
            async for blob in container_client.list_blobs():
                if blob.last_modified and blob.last_modified < cutoff_date:
                    try:
                        await container_client.delete_blob(blob.name)
                        deleted_count += 1
                        logger.debug(f"Deleted expired blob: {blob.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete expired blob {blob.name}: {str(e)}")
            
            logger.info(f"Cleanup completed: {deleted_count} expired voice attachments deleted")
            return deleted_count
            
        except AzureError as e:
            logger.error(f"Azure error during cleanup: {str(e)}")
            raise AuthenticationError(f"Failed to cleanup expired attachments: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during cleanup: {str(e)}")
            raise AuthenticationError(f"Failed to cleanup expired attachments: {str(e)}")


# Global instance
azure_blob_service = AzureBlobService()