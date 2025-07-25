"""
Email Processing class definitions
Contains the EmailProcessor class with method signatures that delegate to function implementations
"""


class EmailProcessor:
    """Email processing class with delegated implementations"""
    
    def __init__(self, access_token, blob_client, target_user_email, audio_processor=None):
        self.access_token = access_token
        self.blob_client = blob_client
        self.target_user_email = target_user_email
        self.audio_processor = audio_processor
    
    def process_emails(self):
        """Main function to process voice emails"""
        from .email_processor_functions import process_emails_impl
        return process_emails_impl(self)
    
    def _get_emails_with_voice_attachments(self):
        """Fetch emails from inbox only with voice attachments (optimized)"""
        from .email_processor_functions import get_emails_with_voice_attachments_impl
        return get_emails_with_voice_attachments_impl(self)
    
    def _is_voice_attachment(self, attachment):
        """Check if attachment is a voice file"""
        from .email_processor_functions import is_voice_attachment_impl
        return is_voice_attachment_impl(self, attachment)
    
    def _process_single_email(self, email):
        """Process a single email with voice attachments and move to done folder after completion"""
        from .email_processor_functions import process_single_email_impl
        return process_single_email_impl(self, email)
    
    def _download_attachment_to_blob(self, email_id, attachment):
        """Download email attachment to Azure Blob Storage with public access"""
        from .email_processor_functions import download_attachment_to_blob_impl
        return download_attachment_to_blob_impl(self, email_id, attachment)
    
    def _extract_structured_data(self, transcript, email, attachment, blob_url):
        """Extract structured data from transcript and email for Excel storage"""
        from .email_processor_functions import extract_structured_data_impl
        return extract_structured_data_impl(self, transcript, email, attachment, blob_url)
    
    def _move_email_to_processed_folder(self, email_id):
        """Move processed email to a 'Voice Messages Processed' folder"""
        from .email_processor_functions import move_email_to_processed_folder_impl
        return move_email_to_processed_folder_impl(self, email_id)
    
    def _get_or_create_processed_folder(self):
        """Get or create 'Voice Messages Processed' folder"""
        from .email_processor_functions import get_or_create_processed_folder_impl
        return get_or_create_processed_folder_impl(self)
    
    def _cleanup_blob(self, blob_url):
        """Remove temporary blob file"""
        from .email_processor_functions import cleanup_blob_impl
        return cleanup_blob_impl(self, blob_url)
