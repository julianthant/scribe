"""
Email Processing function implementations
Contains all the actual function implementations for email operations

NOTE: All HTTP requests use 60-second timeouts for better reliability with slow connections
"""

import logging
import requests
from datetime import datetime, timedelta

# Configure longer timeout for all requests
DEFAULT_TIMEOUT = 60  # 60 seconds for better connection reliability


def process_emails_impl(self):
    """Main function to process voice emails"""
    try:
        logging.info("Starting email processing...")
        
        # Step 1: Get voice emails from inbox
        emails = get_emails_with_voice_attachments_impl(self)
        
        if not emails:
            logging.info("No voice emails found to process")
            return
        
        # Step 2: Process all inbox emails (they're all new since processed ones are moved)
        logging.info(f"Processing {len(emails)} voice emails from inbox")
        
        for email in emails:
            process_single_email_impl(self, email)
            
    except Exception as e:
        logging.error(f"Error in process_emails: {str(e)}")
        raise  # Re-raise to see the error in logs


def get_emails_with_voice_attachments_impl(self):
    """Fetch emails from inbox only with voice attachments (optimized)"""
    headers = {
        'Authorization': f'Bearer {self.access_token}',
        'Content-Type': 'application/json'
    }
    
    # Get emails from last 7 days from INBOX ONLY (extended for testing)
    time_filter = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Use /me/mailFolders/inbox/messages to only check inbox
    url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
    params = {
        '$filter': f"receivedDateTime ge {time_filter} and hasAttachments eq true",
        '$expand': 'attachments',
        '$select': 'id,subject,receivedDateTime,from,attachments',
        '$orderby': 'receivedDateTime desc',
        '$top': 50
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
    if response.status_code != 200:
        logging.error(f"Failed to get inbox emails: {response.text}")
        return []
        
    emails = response.json().get('value', [])
    logging.info(f"Found {len(emails)} emails with attachments in last 7 days")
    
    # Filter for voice attachments
    voice_emails = []
    for email in emails:
        voice_attachments = [att for att in email.get('attachments', []) 
                           if is_voice_attachment_impl(self, att)]
        if voice_attachments:
            email['voice_attachments'] = voice_attachments
            voice_emails.append(email)
            logging.info(f"Found voice email: {email['subject']} with {len(voice_attachments)} voice attachments")
    
    logging.info(f"Found {len(voice_emails)} voice emails in inbox")
    return voice_emails


def is_voice_attachment_impl(self, attachment):
    """Check if attachment is a voice file"""
    voice_types = ['.mp3', '.wav', '.m4a', '.ogg', '.aac', '.wma', '.mp4', '.3gp']
    filename = attachment.get('name', '').lower()
    return any(filename.endswith(ext) for ext in voice_types)


def process_single_email_impl(self, email):
    """Process a single email with voice attachments and move to done folder after completion"""
    try:
        logging.info(f"Processing email: {email['subject']}")
        
        # Process all attachments first
        processed_successfully = True
        
        for attachment in email['voice_attachments']:
            try:
                # Step 2: Download to blob storage
                blob_url = download_attachment_to_blob_impl(self, email['id'], attachment)
                
                if blob_url:
                    # Step 3: Process with Azure Foundry Speech Services
                    # Download the attachment temporarily for transcription
                    temp_file_path = download_attachment_temp_impl(self, attachment, email['id'])
                    if temp_file_path and self.audio_processor:
                        # Use Azure Foundry for fast transcription
                        transcript = self.audio_processor.transcribe_local_audio(temp_file_path)
                        # Clean up temp file
                        try:
                            import os
                            os.remove(temp_file_path)
                        except:
                            pass
                    else:
                        transcript = "[Failed to download attachment for transcription or no audio processor available]"
                    
                    # Step 4: Extract structured data (pass blob_url for link)
                    structured_data = extract_structured_data_impl(self, transcript, email, attachment, blob_url)
                    
                    # Step 5: Update Excel file in OneDrive
                    from .excel_processor_functions import update_excel_file_impl
                    update_excel_file_impl(self, structured_data, blob_url)
                    
                    # Step 7: Keep blob for reference (don't cleanup immediately)
                    logging.info(f"Voice message saved at: {blob_url}")
                else:
                    processed_successfully = False
                    logging.warning(f"Failed to download attachment: {attachment.get('name', 'Unknown')}")
                    
            except Exception as attachment_error:
                logging.error(f"Error processing attachment {attachment.get('name', 'Unknown')}: {attachment_error}")
                processed_successfully = False
        
        # Only move email to processed folder if ALL attachments were processed successfully
        if processed_successfully:
            # Step 6: Move email to processed folder after ALL attachments are done
            move_email_to_processed_folder_impl(self, email['id'])
            logging.info(f"✅ Email fully processed and moved to done folder: {email['subject']}")
        else:
            logging.warning(f"❌ Email processing incomplete, keeping in inbox: {email['subject']}")
            
    except Exception as e:
        logging.error(f"Error processing email {email['id']}: {str(e)}")
        # Don't move email if there was a major processing error


def download_attachment_temp_impl(self, attachment, email_id):
    """Download email attachment to temporary file for transcription"""
    try:
        import tempfile
        import base64
        
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        # Get attachment content
        attachment_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/attachments/{attachment['id']}/$value"
        
        response = requests.get(attachment_url, headers=headers, timeout=DEFAULT_TIMEOUT)
        if response.status_code != 200:
            logging.error(f"Failed to download attachment: {response.text}")
            return None
            
        # Create temporary file
        file_extension = '.wav'  # Default to wav
        if '.' in attachment['name']:
            file_extension = '.' + attachment['name'].split('.')[-1].lower()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name
            
        logging.info(f"Downloaded attachment to temp file: {temp_file_path}")
        return temp_file_path
        
    except Exception as e:
        logging.error(f"Error downloading attachment to temp file: {str(e)}")
        return None


def download_attachment_to_blob_impl(self, email_id, attachment):
    """Download email attachment to Azure Blob Storage with public access"""
    try:
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        # Get attachment content
        url = f"https://graph.microsoft.com/v1.0/users/{self.target_user_email}/messages/{email_id}/attachments/{attachment['id']}/$value"
        response = requests.get(url, headers=headers, timeout=60)
        
        if response.status_code != 200:
            logging.error(f"Failed to download attachment: {response.text}")
            return None
        
        # Upload to blob storage with public access
        container_name = "voice-files"
        blob_name = f"{email_id}_{attachment['id']}_{attachment['name']}"
        
        # Create container if it doesn't exist with public access
        try:
            container_client = self.blob_client.get_container_client(container_name)
            container_client.create_container(public_access='blob')  # Make blobs publicly accessible
        except Exception:
            pass  # Container might already exist
        
        blob_client = self.blob_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        )
        
        # Upload with public read access
        blob_client.upload_blob(response.content, overwrite=True)
        
        # Set blob to be publicly readable
        try:
            blob_client.set_blob_access_tier('Hot')  # Ensure it's in hot tier for quick access
        except Exception as e:
            logging.warning(f"Could not set blob access tier: {e}")
        
        return blob_client.url
        
    except Exception as e:
        logging.error(f"Error downloading attachment: {str(e)}")
        return None


def extract_structured_data_impl(self, transcript, email, attachment, blob_url):
    """Extract structured data from transcript and email for Excel storage"""
    try:
        # Basic email info with consistent date formatting (no leading zeros)
        processed_date = datetime.now().strftime('%-m/%-d/%Y %H:%M')  # e.g., 7/24/2025 17:03
        received_date = datetime.fromisoformat(email['receivedDateTime'][:19]).strftime('%-m/%-d/%Y %H:%M')  # Same format
        
        structured_data = {
            'processed_date': processed_date,
            'received_date': received_date,
            'sender': email['from']['emailAddress']['address'],
            'subject': email['subject'],
            'transcript': transcript[:5000],  # Limit length for Excel
            'attachment_name': attachment['name'],
            'blob_url': blob_url,
            'status': 'Processed'
        }
        
        # Extract contact info from subject and transcript
        contact_info = extract_simple_contact_info(email['subject'], transcript)
        structured_data['contact'] = contact_info if contact_info else ''
        
        # Add confidence score if available (from speech recognition)
        if hasattr(self, 'audio_processor') and hasattr(self.audio_processor, '_last_confidence_score'):
            structured_data['confidence_score'] = f"{self.audio_processor._last_confidence_score:.1f}%"
        else:
            structured_data['confidence_score'] = 'N/A'
        
        return structured_data
        
    except Exception as e:
        logging.error(f"Error extracting structured data: {str(e)}")
        # Return minimal data structure
        return {
            'processed_date': datetime.now().strftime('%-m/%-d/%Y %H:%M'),
            'received_date': email.get('receivedDateTime', 'Unknown')[:19].replace('T', ' '),
            'sender': email.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
            'subject': email.get('subject', 'Unknown'),
            'transcript': transcript[:5000] if transcript else 'Transcription failed',
            'contact': 'N/A',
            'confidence_score': 'N/A',
            'status': 'Error',
            'attachment_name': attachment.get('name', 'Unknown'),
            'blob_url': blob_url
        }


def move_email_to_processed_folder_impl(self, email_id):
    """Move processed email to a 'Voice Messages Processed' folder"""
    try:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # First, ensure the processed folder exists
        processed_folder_id = get_or_create_processed_folder_impl(self)
        if not processed_folder_id:
            logging.warning("Could not create processed folder - email will remain in inbox")
            return False
        
        # Move the email to the processed folder
        move_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/move"
        payload = {
            "destinationId": processed_folder_id
        }
        
        response = requests.post(move_url, headers=headers, json=payload, timeout=60)
        
        if response.status_code in [200, 201]:
            logging.info(f"Successfully moved email to processed folder")
            return True
        else:
            logging.warning(f"Failed to move email: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logging.error(f"Error moving email to processed folder: {e}")
        return False


def get_or_create_processed_folder_impl(self):
    """Get or create 'Voice Messages Processed' folder"""
    try:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        folder_name = "Voice Messages Processed"
        
        # First, check if folder already exists
        folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
        response = requests.get(folders_url, headers=headers, timeout=60)
        
        if response.status_code == 200:
            folders = response.json().get('value', [])
            for folder in folders:
                if folder['displayName'] == folder_name:
                    logging.info(f"Found existing processed folder: {folder['id']}")
                    return folder['id']
        
        # Folder doesn't exist, create it
        logging.info(f"Creating new folder: {folder_name}")
        create_payload = {
            "displayName": folder_name
        }
        
        response = requests.post(folders_url, headers=headers, json=create_payload, timeout=60)
        
        if response.status_code in [200, 201]:
            folder_data = response.json()
            folder_id = folder_data['id']
            logging.info(f"Successfully created processed folder: {folder_id}")
            return folder_id
        else:
            logging.error(f"Failed to create processed folder: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"Error getting/creating processed folder: {e}")
        return None


def cleanup_blob_impl(self, blob_url):
    """Remove temporary blob file"""
    try:
        blob_name = blob_url.split('/')[-1]
        blob_client = self.blob_client.get_blob_client(
            container="voice-files", 
            blob=blob_name
        )
        blob_client.delete_blob()
        logging.info("Cleaned up temporary blob file")
    except Exception as e:
        logging.error(f"Error cleaning up blob: {str(e)}")


def extract_simple_contact_info(subject, transcript=None):
    """Extract contact information from email subject and transcript using simple rules"""
    import re
    
    contact_info = []
    
    # Combined text to search
    search_text = (subject or "") + " " + (transcript or "")
    
    # Look for phone numbers (various formats)
    phone_patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890, 123.456.7890, 1234567890
        r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',    # (123) 456-7890
        r'\b\d{3}\s+\d{3}\s+\d{4}\b',      # 123 456 7890
        r'\b\d{10}\b'                      # 1234567890
    ]
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, search_text)
        for match in matches:
            # Clean up the phone number
            clean_phone = re.sub(r'[^\d]', '', match)
            if len(clean_phone) == 10:  # Valid US phone number
                formatted_phone = f"({clean_phone[:3]}) {clean_phone[3:6]}-{clean_phone[6:]}"
                if formatted_phone not in contact_info:
                    contact_info.append(formatted_phone)
    
    # Look for names in subject
    if subject:
        # Look for common patterns: "From John Smith", "Call from Mary", etc.
        name_patterns = [
            r'from\s+([A-Za-z\s]+)',
            r'call\s+from\s+([A-Za-z\s]+)',
            r'message\s+from\s+([A-Za-z\s]+)',
            r'voicemail\s+from\s+([A-Za-z\s]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, subject.lower())
            if match:
                contact_name = match.group(1).strip().title()
                if len(contact_name) > 2 and contact_name not in contact_info:
                    contact_info.append(contact_name)
    
    # Look for names in transcript (simple pattern)
    if transcript:
        # Look for "My name is..." or "This is..."
        name_patterns = [
            r'my name is\s+([A-Za-z\s]+)',
            r'this is\s+([A-Za-z\s]+)',
            r'i\'m\s+([A-Za-z\s]+)',
            r'hello,?\s*([A-Za-z\s]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, transcript.lower())
            if match:
                potential_name = match.group(1).strip().title()
                # Filter out common false positives
                if (len(potential_name) > 2 and 
                    potential_name not in contact_info and
                    potential_name.lower() not in ['calling', 'trying', 'looking', 'wondering', 'asking']):
                    contact_info.append(potential_name)
                    break  # Only take the first name found
    
    return " | ".join(contact_info[:2]) if contact_info else None  # Max 2 items
