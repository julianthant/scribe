"""
Voice Message Storage Manager for Scribe Voice Email Processor
Handles secure storage and authenticated download of voice message files
"""

import logging
import os
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid

# Azure SDK imports
try:
    from azure.storage.blob import BlobServiceClient, BlobClient
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)

class VoiceStorageManager:
    """Manages voice message file storage in Azure Blob Storage"""
    
    def __init__(self):
        self.storage_connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING', '')
        self.container_name = os.getenv('AZURE_STORAGE_CONTAINER_NAME', 'voice-attachments')
        self.base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
        
        # Initialize Azure SDK client
        self.blob_service_client = None
        
        if AZURE_SDK_AVAILABLE and self.storage_connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.storage_connection_string
                )
                logger.info("✅ Voice Storage Manager initialized")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Voice Storage client: {e}")
                self.blob_service_client = None
        else:
            logger.warning("⚠️ Azure SDK not available or no connection string for voice storage")
    
    def store_voice_message(self, 
                          voice_content: bytes, 
                          original_filename: str,
                          email_subject: str,
                          email_sender: str,
                          email_date: datetime) -> Optional[str]:
        """
        Store voice message file and return download URL
        
        Args:
            voice_content: Raw voice message bytes
            original_filename: Original attachment filename
            email_subject: Email subject for metadata
            email_sender: Email sender for metadata
            email_date: Email received date
            
        Returns:
            Download URL for the stored file or None if failed
        """
        try:
            if not self.blob_service_client:
                logger.warning("⚠️ No blob service client available for voice storage")
                return None
            
            # Generate unique filename with timestamp and hash
            file_id = self._generate_file_id(voice_content, original_filename, email_date)
            blob_name = f"{email_date.strftime('%Y/%m')}/{file_id}.wav"
            
            # Prepare metadata
            metadata = {
                'original_filename': original_filename,
                'email_subject': email_subject[:200],  # Limit length
                'email_sender': email_sender,
                'upload_date': datetime.now(timezone.utc).isoformat(),
                'file_size': str(len(voice_content))
            }
            
            # Upload to blob storage
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data=voice_content,
                overwrite=True,
                content_type='audio/wav',
                metadata=metadata
            )
            
            # Generate download URL
            download_url = f"{self.base_url}/api/download_voice/{file_id}"
            
            logger.info(f"✅ Voice message stored: {original_filename} -> {file_id}")
            return download_url
            
        except Exception as e:
            logger.error(f"❌ Failed to store voice message {original_filename}: {e}")
            return None
    
    def get_voice_message(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve voice message file and metadata
        
        Args:
            file_id: Unique file identifier
            
        Returns:
            Dictionary with file content and metadata or None if not found
        """
        try:
            if not self.blob_service_client:
                return None
            
            # Search for the file across monthly folders
            blob_name = self._find_blob_by_file_id(file_id)
            if not blob_name:
                logger.warning(f"⚠️ Voice message not found: {file_id}")
                return None
            
            # Download the file
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            blob_data = blob_client.download_blob()
            content = blob_data.readall()
            
            # Get metadata
            properties = blob_client.get_blob_properties()
            metadata = properties.metadata
            
            return {
                'content': content,
                'content_type': 'audio/wav',
                'filename': metadata.get('original_filename', f'{file_id}.wav'),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve voice message {file_id}: {e}")
            return None
    
    def _generate_file_id(self, content: bytes, filename: str, email_date: datetime) -> str:
        """Generate unique file ID based on content and metadata"""
        # Create hash from content + filename + date for uniqueness
        hash_input = content[:1024] + filename.encode('utf-8') + email_date.isoformat().encode('utf-8')
        file_hash = hashlib.sha256(hash_input).hexdigest()[:16]
        
        # Add timestamp for additional uniqueness
        timestamp = email_date.strftime('%Y%m%d_%H%M%S')
        
        return f"{timestamp}_{file_hash}"
    
    def _find_blob_by_file_id(self, file_id: str) -> Optional[str]:
        """Find blob name by searching for file_id in container"""
        try:
            # List all blobs and find the one matching the file_id
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            logger.info(f"🔍 Searching for file_id: {file_id}")
            
            for blob in container_client.list_blobs():
                logger.debug(f"   Checking blob: {blob.name}")
                # Check if file_id is in the blob name (should match pattern: YYYY/MM/file_id.wav)
                if file_id in blob.name and blob.name.endswith('.wav'):
                    logger.info(f"✅ Found matching blob: {blob.name}")
                    return blob.name
            
            logger.warning(f"⚠️ No blob found for file_id: {file_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error searching for blob {file_id}: {e}")
            return None
    
    def list_voice_files(self) -> List[Dict[str, Any]]:
        """List all voice files in storage for debugging"""
        try:
            if not self.blob_service_client:
                logger.error("❌ No blob service client available")
                return []
            
            container_client = self.blob_service_client.get_container_client(self.container_name)
            files = []
            
            for blob in container_client.list_blobs():
                if blob.name.endswith('.wav'):
                    # Extract file_id from blob name (remove path and extension)
                    file_id = blob.name.split('/')[-1].replace('.wav', '')
                    
                    files.append({
                        'file_id': file_id,
                        'blob_name': blob.name,
                        'size': blob.size,
                        'created': blob.creation_time.isoformat() if blob.creation_time else None
                    })
            
            logger.info(f"📁 Listed {len(files)} voice files")
            return files
            
        except Exception as e:
            logger.error(f"❌ Error listing voice files: {e}")
            return []
    
    def download_voice_message(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Download voice message by file_id"""
        try:
            if not self.blob_service_client:
                logger.error("❌ No blob service client available for download")
                return None
            
            # Find the blob by file_id
            blob_name = self._find_blob_by_file_id(file_id)
            if not blob_name:
                logger.warning(f"⚠️ Voice file not found: {file_id}")
                return None
            
            # Download the blob
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            
            blob_data = blob_client.download_blob()
            content = blob_data.readall()
            
            # Get blob properties for metadata
            properties = blob_client.get_blob_properties()
            
            # Extract metadata
            metadata = properties.metadata or {}
            original_filename = metadata.get('original_filename', 'voice_message.wav')
            
            logger.info(f"📁 Successfully downloaded voice file: {file_id} ({len(content)} bytes)")
            
            return {
                'content': content,
                'filename': original_filename,
                'content_type': 'audio/wav',
                'size': len(content)
            }
            
        except Exception as e:
            logger.error(f"❌ Error downloading voice message {file_id}: {e}")
            return None
    
    def test_voice_storage_connection(self) -> bool:
        """Test voice storage connectivity"""
        try:
            if not self.blob_service_client:
                logger.error("❌ No blob service client available")
                return False
            
            # Try to get container properties
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            try:
                container_client.get_container_properties()
                logger.info(f"✅ Voice storage connection test passed - {self.container_name} container accessible")
                return True
            except Exception as e:
                if "ContainerNotFound" in str(e):
                    # Try to create the container
                    logger.info(f"📁 Creating voice messages container: {self.container_name}")
                    container_client.create_container()
                    logger.info(f"✅ Voice messages container created: {self.container_name}")
                    return True
                else:
                    raise e
            
        except Exception as e:
            logger.error(f"❌ Voice storage connection test failed: {type(e).__name__}: {str(e)}")
            return False
    
    def get_voice_message_download_url(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get download URL and metadata for a voice message"""
        try:
            if not self.blob_service_client:
                logger.error("❌ No blob service client available")
                return None
            
            blob_name = self._find_blob_by_file_id(file_id)
            if not blob_name:
                logger.error(f"❌ Voice message not found: {file_id}")
                return None
            
            # Get blob client
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            # Get blob properties
            blob_properties = blob_client.get_blob_properties()
            
            # Generate download URL (valid for 1 hour)
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            from datetime import datetime, timedelta
            
            sas_token = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=blob_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            
            download_url = f"{blob_client.url}?{sas_token}"
            
            return {
                'download_url': download_url,
                'filename': blob_properties.metadata.get('original_filename', 'voice_message.wav'),
                'file_size': blob_properties.size,
                'content_type': blob_properties.content_settings.content_type or 'audio/wav',
                'created_date': blob_properties.creation_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting download URL for {file_id}: {e}")
            return None
    
    def list_voice_messages(self, limit: int = 50, offset: int = 0, date_filter: str = None) -> Dict[str, Any]:
        """List voice messages with pagination"""
        try:
            if not self.blob_service_client:
                logger.error("❌ No blob service client available")
                return {'files': [], 'total_count': 0, 'has_more': False}
            
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Get all blobs
            all_blobs = list(container_client.list_blobs(include=['metadata']))
            
            # Apply date filtering if specified
            if date_filter == 'last_7_days':
                from datetime import datetime, timedelta
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
                all_blobs = [blob for blob in all_blobs if blob.creation_time >= cutoff_date]
            
            # Sort by creation time (newest first)
            all_blobs.sort(key=lambda x: x.creation_time, reverse=True)
            
            total_count = len(all_blobs)
            
            # Apply pagination
            paginated_blobs = all_blobs[offset:offset + limit]
            
            files = []
            for blob in paginated_blobs:
                file_info = {
                    'file_id': blob.metadata.get('file_id', blob.name),
                    'filename': blob.metadata.get('original_filename', blob.name),
                    'size': blob.size,
                    'created_date': blob.creation_time.isoformat(),
                    'email_sender': blob.metadata.get('email_sender', 'Unknown'),
                    'email_subject': blob.metadata.get('email_subject', 'Unknown')[:100]
                }
                files.append(file_info)
            
            has_more = (offset + limit) < total_count
            
            return {
                'files': files,
                'total_count': total_count,
                'has_more': has_more
            }
            
        except Exception as e:
            logger.error(f"❌ Error listing voice messages: {e}")
            return {'files': [], 'total_count': 0, 'has_more': False}

# Global instance
voice_storage_manager = VoiceStorageManager()