"""
Excel Processor for Scribe Voice Email Processor
Handles writing transcription results to Excel file in OneDrive
"""

import logging
import time
import html
from datetime import datetime, timezone
from typing import Optional, List

from core.config import ScribeConfig
from core.input_validation import input_validator
from helpers.auth_manager import make_graph_request
from models.data import TranscriptionResult, ExcelWriteResult
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ExcelRowData:
    """Data structure for Excel row information"""
    transcription: TranscriptionResult
    email_subject: str
    email_sender: str
    email_date: datetime
    attachment_filename: str
    download_url: Optional[str] = None

class ExcelProcessor:
    """Process Excel file operations for transcription logging"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        # Use the same Scribe.xlsx file but with monthly worksheets
        validated_filename = input_validator.validate_excel_filename(config.excel_file_name)
        self.excel_file_name = validated_filename or "Scribe.xlsx"
        
        # Generate monthly worksheet name
        current_date = datetime.now(timezone.utc)
        self.monthly_worksheet_name = f"{current_date.year}_{current_date.month:02d}"
        self._file_id_cache = None
        self._worksheet_name = None  # Cache for worksheet name
        logger.info(f"📊 Excel processor initialized: {self.excel_file_name}")
    
    def write_transcription_result(self, row_data: ExcelRowData) -> ExcelWriteResult:
        """Write transcription result to Excel file in OneDrive"""
        start_time = time.time()
        
        try:
            logger.info(f"📊 Writing transcription to Excel: {row_data.attachment_filename}")
            
            # Validate prerequisites
            file_id = self._validate_excel_file_access()
            if not file_id:
                return self._create_error_result("Excel file not found or inaccessible", start_time)
            
            # Determine write location
            next_row = self._determine_next_row(file_id)
            if next_row is None:
                return self._create_error_result("Failed to determine next row in Excel file", start_time)
            
            # Ensure headers exist before writing data (safety check)
            if next_row <= 2:  # If we're writing to row 1 or 2, make sure headers are there
                logger.info("📊 Safety check: Ensuring headers exist before writing data")
                self._create_headers_if_needed(file_id)
                if next_row == 1:
                    next_row = 2  # Move to row 2 if headers were just created
            
            # Execute write operation
            write_success = self._execute_excel_write(file_id, next_row, row_data)
            
            # Return result
            return self._create_write_result(write_success, next_row, start_time)
                
        except Exception as e:
            error_msg = f"Excel write error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return self._create_error_result(error_msg, start_time)
    
    def _validate_excel_file_access(self) -> Optional[str]:
        """Validate that we can access the Excel file"""
        try:
            file_id = self._get_excel_file_id()
            if not file_id:
                logger.error(f"❌ Excel file '{self.excel_file_name}' not found in OneDrive")
                return None
            return file_id
        except Exception as e:
            logger.error(f"❌ Error validating Excel file access: {e}")
            return None
    
    def _determine_next_row(self, file_id: str) -> Optional[int]:
        """Determine the next available row for writing"""
        try:
            next_row = self._get_next_row_number(file_id)
            if next_row is None:
                logger.error("❌ Failed to determine next row in Excel file")
                return None
            return next_row
        except Exception as e:
            logger.error(f"❌ Error determining next row: {e}")
            return None
    
    def _execute_excel_write(self, file_id: str, row_number: int, row_data: ExcelRowData) -> bool:
        """Execute the actual Excel write operation"""
        try:
            # Prepare data for Excel
            excel_data = self._prepare_excel_data(row_data)
            
            # Write to Excel
            success = self._write_to_excel_row(file_id, row_number, excel_data)
            
            if success:
                logger.info(f"✅ Excel write successful: Row {row_number}")
                
                # Set row to auto-height for transcription text
                self._set_row_auto_height(file_id, row_number)
                
                # Apply text wrapping and fixed width formatting to transcription column
                self._apply_transcription_formatting(file_id, row_number)
                
            else:
                logger.error(f"❌ Excel write failed: Row {row_number}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error executing Excel write: {e}")
            return False
    
    def _create_error_result(self, error_message: str, start_time: float) -> ExcelWriteResult:
        """Create an error result with timing information"""
        processing_time = time.time() - start_time
        return ExcelWriteResult(
            success=False,
            error_message=error_message,
            processing_time_seconds=processing_time
        )
    
    def _create_write_result(self, success: bool, row_number: int, start_time: float) -> ExcelWriteResult:
        """Create a write result with timing information"""
        processing_time = time.time() - start_time
        
        if success:
            return ExcelWriteResult(
                success=True,
                row_number=row_number,
                processing_time_seconds=processing_time
            )
        else:
            return ExcelWriteResult(
                success=False,
                error_message="Failed to write data to Excel file",
                processing_time_seconds=processing_time
            )
    
    def _get_excel_file_id(self) -> Optional[str]:
        """Get Excel file ID from OneDrive"""
        try:
            # Clear cache to always search for fresh file (debug mode)
            self._file_id_cache = None
            
            # Search for Excel file
            search_url = f"https://graph.microsoft.com/v1.0/me/drive/root/search(q='{self.excel_file_name}')"
            response = make_graph_request(search_url)
            
            if not response or response.status_code != 200:
                logger.error(f"❌ Failed to search for Excel file: {response.status_code if response else 'No response'}")
                return None
            
            search_results = response.json().get('value', [])
            excel_files = [f for f in search_results if f.get('name') == self.excel_file_name]
            
            if not excel_files:
                logger.error(f"❌ Excel file '{self.excel_file_name}' not found in OneDrive")
                return None
            
            file_id = excel_files[0].get('id')
            file_name = excel_files[0].get('name')
            file_path = excel_files[0].get('parentReference', {}).get('path', 'Unknown path')
            if file_id:
                self._file_id_cache = file_id
                logger.info(f"📊 Excel file found: {file_name}")
                logger.info(f"📊 File ID: {file_id}")
                logger.info(f"📊 File path: {file_path}")
                return file_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding Excel file: {e}")
            return None
    
    def _create_monthly_excel_file(self) -> Optional[str]:
        """Create a new monthly Excel file in OneDrive"""
        try:
            logger.info(f"📊 Creating new monthly Excel file: {self.excel_file_name}")
            
            # Create new Excel workbook using upload API
            upload_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{self.excel_file_name}:/content"
            
            # Create a minimal Excel file content (basic .xlsx structure)
            import io
            import zipfile
            
            # Create minimal Excel file in memory
            excel_content = self._create_minimal_excel_content()
            
            response = self._upload_excel_file(upload_url, excel_content)
            
            if response and response.status_code == 201:
                file_info = response.json()
                file_id = file_info.get('id')
                
                if file_id:
                    self._file_id_cache = file_id
                    logger.info(f"✅ Monthly Excel file created successfully: {file_id}")
                    
                    # Initialize the workbook with headers
                    self._initialize_new_workbook(file_id)
                    
                    return file_id
            
            logger.error(f"❌ Failed to create monthly Excel file: {response.status_code if response else 'No response'}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error creating monthly Excel file: {e}")
            return None
    
    def _initialize_new_workbook(self, file_id: str) -> None:
        """Initialize a new workbook with proper headers and formatting"""
        try:
            logger.info("📊 Initializing new workbook with headers")
            
            # Wait a moment for the file to be fully created
            import time
            time.sleep(2)
            
            # Create headers
            self.create_excel_headers()
            
            # Set optimal column widths
            self._set_optimal_column_widths(file_id)
            
            logger.info("✅ New workbook initialized successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Error initializing new workbook: {e}")
            # Don't fail the entire operation if formatting fails
    
    def _create_minimal_excel_content(self) -> bytes:
        """Create minimal Excel file content as CSV that will be converted to Excel"""
        try:
            # Create basic CSV content with headers
            csv_content = "Date,Time,Email Sender,Phone Number,Attachment Filename,Transcription Text,Confidence (%),Audio Duration (sec),Status\n"
            return csv_content.encode('utf-8')
        except Exception as e:
            logger.error(f"Error creating Excel content: {e}")
            return b"Date,Time,Email Sender,Phone Number,Attachment Filename,Transcription Text,Confidence (%),Audio Duration (sec),Status\n".encode('utf-8')
    
    def _upload_excel_file(self, upload_url: str, content: bytes):
        """Upload file content to OneDrive"""
        try:
            from helpers.auth import get_access_token
            
            access_token = get_access_token()
            if not access_token:
                logger.error("❌ No access token for file upload")
                return None
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'text/csv'  # Upload as CSV first
            }
            
            import requests
            response = requests.put(upload_url, headers=headers, data=content)
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ File uploaded successfully: {response.status_code}")
            else:
                logger.error(f"❌ File upload failed: {response.status_code} - {response.text}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return None
    
    def _get_or_create_monthly_worksheet(self, file_id: str) -> Optional[str]:
        """Get existing monthly worksheet or create a new one"""
        try:
            # Check if monthly worksheet already exists
            worksheets_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets"
            logger.info(f"📋 Requesting worksheets from: {worksheets_url}")
            response = make_graph_request(worksheets_url)
            
            if response and response.status_code == 200:
                worksheets = response.json().get('value', [])
                logger.info(f"📋 Found {len(worksheets)} existing worksheets")
                
                # Look for monthly worksheet
                for worksheet in worksheets:
                    worksheet_name = worksheet.get('name')
                    logger.info(f"📋 Checking worksheet: {worksheet_name}")
                    if worksheet_name == self.monthly_worksheet_name:
                        logger.info(f"📋 Found existing monthly worksheet: {self.monthly_worksheet_name}")
                        self._worksheet_name = self.monthly_worksheet_name
                        return self.monthly_worksheet_name
                
                # Monthly worksheet doesn't exist, create it
                logger.info(f"📋 Creating new monthly worksheet: {self.monthly_worksheet_name}")
                return self._create_monthly_worksheet(file_id)
            elif response:
                logger.error(f"❌ Failed to get worksheets: {response.status_code}")
                logger.error(f"Response content: {response.text[:500]}")
                return None
            else:
                logger.error("❌ Failed to get worksheets: No response from Graph API")
                # Try to use default worksheet "Sheet1" as fallback
                logger.info("📋 Attempting fallback to default worksheet 'Sheet1'")
                self._worksheet_name = "Sheet1"
                return "Sheet1"
                
        except Exception as e:
            logger.error(f"❌ Error getting/creating monthly worksheet: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _create_monthly_worksheet(self, file_id: str) -> Optional[str]:
        """Create a new monthly worksheet"""
        try:
            # Validate worksheet name before creation
            if not self.monthly_worksheet_name or not self.monthly_worksheet_name.strip():
                logger.error("❌ Invalid monthly worksheet name")
                return None
            
            # Create new worksheet
            create_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/add"
            
            worksheet_data = {
                "name": self.monthly_worksheet_name.strip()
            }
            
            logger.info(f"📋 Creating worksheet with name: '{self.monthly_worksheet_name}'")
            logger.info(f"📋 Excel file ID: {file_id}")
            logger.info(f"📋 Create URL: {create_url}")
            response = make_graph_request(create_url, method='POST', data=worksheet_data)
            
            if response and response.status_code == 201:
                logger.info(f"✅ Created monthly worksheet: {self.monthly_worksheet_name}")
                self._worksheet_name = self.monthly_worksheet_name
                
                # Initialize the new worksheet with headers
                self._initialize_monthly_worksheet(file_id)
                
                return self.monthly_worksheet_name
            else:
                logger.error(f"❌ Failed to create monthly worksheet: {response.status_code if response else 'No response'}")
                if response and response.text:
                    logger.error(f"   Response: {response.text[:500]}")
                    
                    # Check if it's a name conflict (worksheet already exists)
                    if response.status_code == 400:
                        logger.warning(f"⚠️ Worksheet creation failed with 400 - possibly already exists")
                        # Try to return the existing worksheet name
                        return self.monthly_worksheet_name
                        
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating monthly worksheet: {e}")
            return None
    
    def _initialize_monthly_worksheet(self, file_id: str) -> None:
        """Initialize a new monthly worksheet with headers and formatting"""
        try:
            logger.info(f"📊 Initializing monthly worksheet: {self.monthly_worksheet_name}")
            
            # Wait a moment for the worksheet to be fully created
            import time
            time.sleep(2)  # Increase wait time to ensure worksheet is ready
            
            # Create headers immediately after worksheet creation
            logger.info("📊 Creating headers for new monthly worksheet")
            self._create_headers_if_needed(file_id)
            
            logger.info("✅ Monthly worksheet initialized successfully with headers")
            
        except Exception as e:
            logger.warning(f"⚠️ Error initializing monthly worksheet: {e}")
            # Don't fail the entire operation if formatting fails
    
    def _create_basic_headers(self, file_id: str) -> None:
        """Create basic headers without complex formatting"""
        try:
            # Validate worksheet name exists
            worksheet_name = self._worksheet_name or self.monthly_worksheet_name
            if not worksheet_name:
                logger.warning("⚠️ No worksheet name available for header creation")
                return
            
            # Simple header row data
            headers = {
                "values": [[
                    "Date",
                    "Time", 
                    "Email Sender",
                    "Phone Number",
                    "Attachment Filename",
                    "Transcription Text",
                    "Confidence (%)",
                    "Audio Duration (sec)",
                    "Status"
                ]]
            }
            
            # Validate the worksheet exists before trying to write headers
            worksheet_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}"
            check_response = make_graph_request(worksheet_check_url)
            
            if not check_response or check_response.status_code != 200:
                logger.warning(f"⚠️ Worksheet '{worksheet_name}' not accessible, skipping header creation")
                return
            
            # Write headers to row 1
            update_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='A1:I1')"
            
            response = make_graph_request(update_url, method='PATCH', data=headers)
            
            if response and response.status_code == 200:
                logger.info("✅ Basic headers created successfully")
            else:
                logger.warning(f"⚠️ Failed to create headers: {response.status_code if response else 'No response'}")
                if response and response.text:
                    logger.warning(f"   Error details: {response.text[:200]}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error creating basic headers: {e}")
    
    def _try_list_excel_files(self) -> Optional[str]:
        """List all Excel files in OneDrive for debugging"""
        try:
            logger.info("📊 Listing all Excel files in OneDrive...")
            
            # Search for all Excel files
            search_url = "https://graph.microsoft.com/v1.0/me/drive/root/search(q='.xlsx')"
            response = make_graph_request(search_url)
            
            if response and response.status_code == 200:
                excel_files = response.json().get('value', [])
                logger.info(f"📊 Found {len(excel_files)} Excel files:")
                
                for file in excel_files:
                    name = file.get('name', 'Unknown')
                    file_id = file.get('id', 'No ID')
                    logger.info(f"   📄 {name} (ID: {file_id[:20]}...)")
                    
                    # Check for close matches
                    if self.excel_file_name.lower() in name.lower() or name.lower() in self.excel_file_name.lower():
                        logger.info(f"💡 Possible match found: {name}")
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Excel file listing failed: {e}")
            return None
    
    def _get_next_row_number(self, file_id: str) -> Optional[int]:
        """Get the next available row number in the worksheet"""
        try:
            # Get or create monthly worksheet
            worksheet_name = self._get_or_create_monthly_worksheet(file_id)
            if not worksheet_name:
                logger.error("❌ Failed to get or create monthly worksheet")
                return None
            
            # Get used range to determine next row
            worksheet_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/usedRange"
            response = make_graph_request(worksheet_url)
            
            if response and response.status_code == 200:
                used_range = response.json()
                row_count = used_range.get('rowCount', 0)
                next_row = row_count + 1  # Next available row
                logger.info(f"📊 Next row: {next_row}")
                
                # If file is empty (row_count = 0), create headers first
                if row_count == 0:
                    logger.info("📊 Empty file detected, creating headers first")
                    self._create_headers_if_needed(file_id)
                    return 2  # Start data at row 2 after headers
                
                return next_row
            elif response and response.status_code == 404:
                # Empty file, create headers first
                logger.info("📊 Empty file, creating headers")
                self._create_headers_if_needed(file_id)
                return 2  # Start data at row 2 after headers
            else:
                logger.warning(f"⚠️ Could not access used range, creating headers and starting at row 2")
                self._create_headers_if_needed(file_id)
                return 2
                
        except Exception as e:
            logger.error(f"❌ Error getting next row number: {e}")
            # Default to row 1 for safety
            logger.info("📊 Using fallback row 1")
            return 1
    
    def _create_headers_if_needed(self, file_id: str) -> None:
        """Create headers in the Excel file with 11-column layout"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            # Create 11-column headers in worksheet (silent operation)
            
            # Create header row with 11 columns with updated layout
            headers = {
                "values": [[
                    "Date Received",
                    "Time Received",
                    "Date Processed",
                    "Time Processed", 
                    "Phone Number",
                    "Sender",
                    "Transcription",
                    "Confidence Score",
                    "Voice Length",
                    "Download",
                    "Status"
                ]]
            }
            
            # Write headers to row 1 (11 columns A1:K1)
            update_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='A1:K1')"
            response = make_graph_request(update_url, method='PATCH', data=headers)
            
            if response and response.status_code in [200, 204]:
                logger.info("✅ Excel headers created")
                
                # Set column widths after creating headers
                self._set_optimal_column_widths(file_id)
                
                # Format headers (skip formatting to avoid 400 errors)
                # Headers created, skip complex formatting
            else:
                logger.warning(f"⚠️ Failed to create headers: {response.status_code if response else 'No response'}")
            
        except Exception as e:
            logger.warning(f"⚠️ Error creating headers: {e}")
            # Don't fail - data writing is more important than headers
    
    def _prepare_excel_data(self, row_data: ExcelRowData) -> dict:
        """Prepare and validated data for Excel write operation with 11-column layout"""
        from datetime import datetime
        import pytz
        
        # Format received date/time (from email)
        received_data = self._format_timestamps(row_data.email_date)
        
        # Format processed date/time (current time)
        current_time = datetime.now(pytz.timezone('US/Pacific'))
        processed_data = {
            'pst_date': current_time.strftime('%m/%d/%Y'),
            'pst_time': current_time.strftime('%I:%M %p')
        }
        
        validated_data = self._validate_row_data(row_data)
        numeric_data = self._normalize_numeric_values(row_data.transcription)
        
        # Extract phone number from email subject
        phone_number = self._extract_phone_number(row_data.email_subject)
        
        # Create download hyperlink
        download_link = self._create_download_hyperlink(row_data.attachment_filename)
        
        return {
            "values": [[
                received_data['pst_date'],                 # Column A: Date Received
                received_data['pst_time'],                 # Column B: Time Received  
                processed_data['pst_date'],                # Column C: Date Processed
                processed_data['pst_time'],                # Column D: Time Processed
                phone_number,                              # Column E: Phone Number
                validated_data['sender'],                  # Column F: Sender
                validated_data['text'],                    # Column G: Transcription
                f"{numeric_data['confidence']:.0%}",       # Column H: Confidence Score
                f"{numeric_data['duration']:.1f}s",        # Column I: Voice Length (seconds)
                download_link,                             # Column J: Download Link
                self._get_status_text(row_data.transcription.success)  # Column K: Status
            ]]
        }
    
    def _format_timestamps(self, email_date: datetime) -> dict:
        """Format timestamp data in PST with separate date and time columns"""
        import pytz
        
        # Convert email date to PST
        pst = pytz.timezone('US/Pacific')
        if email_date.tzinfo is None:
            email_date = email_date.replace(tzinfo=timezone.utc)
        
        email_pst = email_date.astimezone(pst)
        formatted_date = email_pst.strftime('%m/%d/%Y')
        formatted_time = email_pst.strftime('%I:%M %p')
        
        return {
            'pst_date': formatted_date,
            'pst_time': formatted_time
        }
    
    def _validate_row_data(self, row_data: ExcelRowData) -> dict:
        """Validate and sanitize text data"""
        # Format transcription text for optimal Excel display
        formatted_text = self._format_transcription_text(row_data.transcription.text or "")
        
        return {
            'sender': input_validator.validate_email_address(row_data.email_sender) or "Unknown",
            'subject': input_validator.validate_email_subject(row_data.email_subject) or "No Subject",
            'filename': input_validator.validate_filename(row_data.attachment_filename) or "unknown_file",
            'text': formatted_text
        }
    
    def _normalize_numeric_values(self, transcription: TranscriptionResult) -> dict:
        """Normalize numeric values to safe ranges with proper formatting"""
        confidence = max(0.0, min(1.0, transcription.confidence or 0.0))
        return {
            'confidence': confidence,  # Keep as decimal for percentage formatting in Excel
            'duration': max(0.0, transcription.duration_seconds or 0.0),
            'word_count': max(0, int(transcription.word_count or 0))
        }
    
    def _get_status_text(self, success: bool) -> str:
        """Get status text for transcription result"""
        return "Success" if success else "Failed"
    
    def _extract_phone_number(self, subject: str) -> str:
        """Extract phone number from email subject line with improved patterns"""
        import re
        
        if not subject:
            return "N/A"
        
        # Enhanced phone number patterns for better extraction
        patterns = [
            # Standard formats
            r'\((\d{3})\)\s*(\d{3})-?(\d{4})',  # (xxx) xxx-xxxx
            r'(\d{3})-(\d{3})-(\d{4})',         # xxx-xxx-xxxx
            r'(\d{3})\.(\d{3})\.(\d{4})',       # xxx.xxx.xxxx
            r'(\d{3})\s+(\d{3})\s+(\d{4})',     # xxx xxx xxxx
            r'\((\d{3})\)(\d{3})(\d{4})',       # (xxx)xxxxxxx
            r'(\d{3})\s*(\d{3})\s*(\d{4})',     # flexible spacing
            
            # 10 consecutive digits
            r'(?<!\d)(\d{10})(?!\d)',           # xxxxxxxxxx (10 digits, not part of larger number)
            
            # With +1 country code
            r'\+1\s*\(?(\d{3})\)?\s*(\d{3})\s*(\d{4})',  # +1 xxx xxx xxxx
            r'1\s*\(?(\d{3})\)?\s*(\d{3})\s*(\d{4})',    # 1 xxx xxx xxxx
            
            # Edge cases
            r'(\d{3})[^\d]*(\d{3})[^\d]*(\d{4})'  # xxx...xxx...xxxx (any separator)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    # Standard 3-part number
                    return f"({groups[0]}) {groups[1]}-{groups[2]}"
                elif len(groups) == 1 and len(groups[0]) == 10:
                    # 10-digit number
                    num = groups[0]
                    return f"({num[:3]}) {num[3:6]}-{num[6:]}"
        
        return "N/A"
    
    def _create_download_hyperlink(self, filename: str) -> str:
        """Create secure download hyperlink for voice message"""
        import os
        import hashlib
        from datetime import datetime
        
        if not filename:
            return "No File"
        
        # Generate secure file ID from filename and timestamp
        file_id = hashlib.md5(f"{filename}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        # Get base URL from environment
        base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
        
        # Create secure download URL
        download_url = f"{base_url}/api/download_voice/{file_id}"
        
        # Return Excel hyperlink formula
        return f'=HYPERLINK("{download_url}", "Download")'
    
    def _write_to_excel_row(self, file_id: str, row_number: int, excel_data: dict) -> bool:
        """Write data to specific Excel row with simplified formatting"""
        try:
            # Define the range for the row (A:K covers our 11 columns)
            range_address = f"A{row_number}:K{row_number}"
            
            # Update the specific range with data  
            worksheet_name = self._worksheet_name or "Sheet1"
            update_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='{range_address}')"
            
            logger.debug(f"📝 Excel write URL: {update_url}")
            response = make_graph_request(update_url, method='PATCH', data=excel_data)
            
            if response and response.status_code == 200:
                logger.info(f"✅ Successfully wrote to Excel row {row_number}")
                
                # Apply right-alignment to voice length and status columns
                self._apply_right_alignment(file_id, row_number)
                
                return True
            else:
                # Check for specific error types
                if response and response.status_code == 404:
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error', {}).get('code', '')
                        if error_code == 'ItemNotFound':
                            logger.error(f"❌ ItemNotFound: Excel file, worksheet '{worksheet_name}', or range '{range_address}' not found")
                            logger.error(f"   URL: {update_url}")
                    except:
                        pass
                elif response and response.status_code == 401:
                    try:
                        error_data = response.json()
                        error_code = error_data.get('error', {}).get('code', '')
                        if error_code == 'FileOpenUserUnauthorized':
                            logger.error("❌ FileOpenUserUnauthorized: Missing Excel permissions")
                    except:
                        pass
                
                logger.error(f"❌ Failed to write to Excel row {row_number}: {response.status_code if response else 'No response'}")
                if response and response.text:
                    logger.error(f"   Error details: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error writing to Excel row: {e}")
            return False
    
    def _apply_right_alignment(self, file_id: str, row_number: int) -> None:
        """Apply right alignment to voice length (column I) and status (column K) columns"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            
            # Right-align Voice Length column (I)
            voice_length_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='I{row_number}')/format"
            voice_length_format = {
                "horizontalAlignment": "Right",
                "verticalAlignment": "Center"
            }
            make_graph_request(voice_length_url, method='PATCH', data=voice_length_format)
            
            # Right-align Status column (K)
            status_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='K{row_number}')/format"
            status_format = {
                "horizontalAlignment": "Right",
                "verticalAlignment": "Center"
            }
            make_graph_request(status_url, method='PATCH', data=status_format)
            
        except Exception as e:
            # Silent failure - formatting is not critical
            pass
    
    def _set_row_auto_height(self, file_id: str, row_number: int) -> None:
        """Set row to auto-height to fit transcription content (11-column layout)"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            
            # Use the correct API to set row height to auto-fit for 11 columns
            autofit_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='A{row_number}:K{row_number}')/format/autofitRows"
            
            response = make_graph_request(autofit_url, method='POST', data={})
            
            if response and response.status_code in [200, 204]:
                # Row height auto-adjusted (silent operation)
                pass
            else:
                # Fallback: Set minimum height manually to accommodate text
                height_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='A{row_number}:K{row_number}')/format/rowHeight"
                height_data = {"value": 80}  # Set minimum height to accommodate wrapped text
                
                fallback_response = make_graph_request(height_url, method='PATCH', data=height_data)
                if fallback_response and fallback_response.status_code in [200, 204]:
                    # Row height set to fallback (silent operation)
                    pass
                
        except Exception as e:
            # Could not set auto-height (silent operation)
            # Don't fail the entire operation if auto-height fails
            pass

    def _apply_transcription_formatting(self, file_id: str, row_number: int) -> None:
        """Apply optimal formatting for transcription text with fixed widths and text wrapping"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            
            # Set fixed column widths and text wrapping for transcription column (G in 11-column layout)
            transcription_format_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='G{row_number}')/format"
            
            transcription_formatting = {
                "wrapText": True,
                "verticalAlignment": "Top",
                "horizontalAlignment": "Left",
                "font": {
                    "size": 11,
                    "name": "Calibri"
                }
            }
            
            response = make_graph_request(transcription_format_url, method='PATCH', data=transcription_formatting)
            
            if response and response.status_code == 200:
                # Applied transcription formatting (silent operation)
                pass
            
            # Set fixed column width for transcription column if not already set
            self._set_fixed_column_widths(file_id)
                
        except Exception as e:
            # Could not apply transcription formatting (silent operation)
            # Don't fail the entire operation if formatting fails
            pass

    def _set_fixed_column_widths(self, file_id: str) -> None:
        """Set reasonable column widths for 11-column layout"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            
            # Define reasonable column widths for 11-column layout
            column_widths = {
                'A': 90,   # Date Received - reasonable for MM/DD/YYYY
                'B': 90,   # Time Received - reasonable for HH:MM AM/PM  
                'C': 90,   # Date Processed - reasonable for MM/DD/YYYY
                'D': 90,   # Time Processed - reasonable for HH:MM AM/PM
                'E': 120,  # Phone Number - reasonable for (xxx) xxx-xxxx
                'F': 150,  # Sender - reasonable for email addresses
                'G': 300,  # Transcription - wider for readability but not excessive
                'H': 100,  # Confidence Score - reasonable for percentages
                'I': 100,  # Voice Length - reasonable for duration
                'J': 80,   # Download - reasonable for "Download" link
                'K': 80    # Status - reasonable for Success/Failed
            }
            
            for column, width in column_widths.items():
                # Use the correct range API to set column width
                column_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='{column}:{column}')/format"
                column_data = {"columnWidth": width}
                
                response = make_graph_request(column_url, method='PATCH', data=column_data)
                
                if response and response.status_code in [200, 204]:
                    # Column width set (silent operation)
                    pass
                else:
                    # Column width setting failed (silent operation)
                    pass
                
        except Exception as e:
            # Could not set column widths (silent operation)
            # Don't fail the entire operation if column width setting fails
            pass
    
    def _set_optimal_column_widths(self, file_id: str) -> None:
        """Set optimal column widths (alias for _set_fixed_column_widths)"""
        self._set_fixed_column_widths(file_id)
    
    def _format_header_row(self, file_id: str) -> None:
        """Apply formatting to the header row (9-column layout)"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            
            # Format header row with bold font and background color for 9 columns
            header_format_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='A1:I1')/format"
            
            header_formatting = {
                "font": {
                    "bold": True,
                    "size": 12,
                    "name": "Calibri",
                    "color": "#FFFFFF"
                },
                "fill": {
                    "color": "#4472C4"  # Professional blue background
                },
                "horizontalAlignment": "Center",
                "verticalAlignment": "Center"
            }
            
            response = make_graph_request(header_format_url, method='PATCH', data=header_formatting)
            
            if response and response.status_code in [200, 204]:
                logger.info("✅ Header formatting applied successfully")
            else:
                logger.warning(f"⚠️ Failed to apply header formatting: {response.status_code if response else 'No response'}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error formatting header row: {e}")
            # Don't fail the entire operation if header formatting fails
            pass

    def _apply_row_formatting(self, file_id: str, row_number: int) -> None:
        """Apply formatting to a specific row"""
        try:
            formatting_configs = self._get_row_formatting_configs(row_number)
            
            for config in formatting_configs:
                self._apply_single_format(file_id, config)
            
            # Formatting applied successfully
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to apply formatting to row {row_number}: {e}")
            # Don't fail the entire operation if formatting fails
    
    def _get_row_formatting_configs(self, row_number: int) -> List[dict]:
        """Get professional formatting configurations for a data row"""
        return [
            # Date & Time column (A)
            {
                'range': f"A{row_number}",
                'formatting': {
                    "horizontalAlignment": "Left",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "name": "Calibri"}
                }
            },
            # Email Sender column (B)
            {
                'range': f"B{row_number}",
                'formatting': {
                    "horizontalAlignment": "Left",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "name": "Calibri"}
                }
            },
            # Email Subject column (C)
            {
                'range': f"C{row_number}",
                'formatting': {
                    "horizontalAlignment": "Left",
                    "verticalAlignment": "Center",
                    "wrapText": True,
                    "font": {"size": 10, "name": "Calibri"}
                }
            },
            # Phone Number column (D)
            {
                'range': f"D{row_number}",
                'formatting': {
                    "horizontalAlignment": "Center",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "name": "Calibri", "bold": True}
                }
            },
            # Attachment Filename column (E)
            {
                'range': f"E{row_number}",
                'formatting': {
                    "horizontalAlignment": "Left",
                    "verticalAlignment": "Center",
                    "font": {"size": 9, "name": "Calibri", "italic": True}
                }
            },
            # Transcription Text column (F) - Most important formatting
            {
                'range': f"F{row_number}",
                'formatting': {
                    "wrapText": True,
                    "verticalAlignment": "Top",
                    "horizontalAlignment": "Left",
                    "font": {"size": 11, "name": "Calibri"},
                    "borders": {
                        "style": "Thin",
                        "color": "#E0E0E0"
                    }
                }
            },
            # Confidence Score column (G)
            {
                'range': f"G{row_number}",
                'formatting': {
                    "numberFormat": ["0.00%"],
                    "horizontalAlignment": "Center",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "name": "Calibri"}
                }
            },
            # Audio Duration column (H)
            {
                'range': f"H{row_number}",
                'formatting': {
                    "numberFormat": ["0.0\"s\""],
                    "horizontalAlignment": "Center",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "name": "Calibri"}
                }
            },
            # Word Count column (I)
            {
                'range': f"I{row_number}",
                'formatting': {
                    "numberFormat": ["0"],
                    "horizontalAlignment": "Center",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "name": "Calibri"}
                }
            },
            # Status column (J)
            {
                'range': f"J{row_number}",
                'formatting': {
                    "horizontalAlignment": "Center",
                    "verticalAlignment": "Center",
                    "font": {"size": 10, "bold": True, "name": "Calibri"}
                }
            }
        ]
    
    def _apply_single_format(self, file_id: str, config: dict) -> None:
        """Apply a single formatting configuration"""
        try:
            format_url = self._build_format_url(file_id, config['range'])
            make_graph_request(format_url, method='PATCH', data=config['formatting'])
        except Exception as e:
            logger.warning(f"⚠️ Error applying format to {config['range']}: {e}")
    
    def _format_transcription_column(self, file_id: str, row_number: int) -> None:
        """Format the transcription text column (F) for better readability"""
        try:
            transcription_range = f"F{row_number}"
            format_url = self._build_format_url(file_id, transcription_range)
            
            formatting = {
                "wrapText": True,
                "verticalAlignment": "Top",
                "font": {
                    "size": 10,
                    "name": "Calibri"
                }
            }
            
            make_graph_request(format_url, method='PATCH', data=formatting)
            
        except Exception as e:
            logger.warning(f"⚠️ Error formatting transcription column: {e}")
    
    def _format_date_columns(self, file_id: str, row_number: int) -> None:
        """Format timestamp columns (A, B) for better date display"""
        try:
            for col in ['A', 'B']:
                date_range = f"{col}{row_number}"
                format_url = self._build_format_url(file_id, date_range)
                
                formatting = {
                    "numberFormat": ["yyyy-mm-dd hh:mm:ss"],
                    "font": {
                        "size": 9,
                        "name": "Calibri"
                    }
                }
                
                make_graph_request(format_url, method='PATCH', data=formatting)
                
        except Exception as e:
            logger.warning(f"⚠️ Error formatting date columns: {e}")
    
    def _format_number_columns(self, file_id: str, row_number: int) -> None:
        """Format confidence and duration columns (G, H) for numbers"""
        try:
            for col in ['G', 'H']:
                number_range = f"{col}{row_number}"
                format_url = self._build_format_url(file_id, number_range)
                
                formatting = {
                    "numberFormat": ["0.00"],
                    "horizontalAlignment": "Right",
                    "font": {
                        "size": 10,
                        "name": "Calibri"
                    }
                }
                
                make_graph_request(format_url, method='PATCH', data=formatting)
                
        except Exception as e:
            logger.warning(f"⚠️ Error formatting number columns: {e}")
    
    def _format_status_column(self, file_id: str, row_number: int) -> None:
        """Format status column (J) with centered, bold text"""
        try:
            status_range = f"J{row_number}"
            format_url = self._build_format_url(file_id, status_range)
            
            formatting = {
                "horizontalAlignment": "Center",
                "font": {
                    "size": 10,
                    "bold": True,
                    "name": "Calibri"
                }
            }
            
            make_graph_request(format_url, method='PATCH', data=formatting)
            
        except Exception as e:
            logger.warning(f"⚠️ Error formatting status column: {e}")
    
    def _build_format_url(self, file_id: str, range_address: str) -> str:
        """Build formatting URL for a specific range"""
        worksheet_name = self._worksheet_name or "Sheet1"
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='{range_address}')/format"
    
    def create_excel_headers(self) -> bool:
        """Create formatted headers in Excel file if they don't exist"""
        try:
            logger.info("📊 Creating Excel headers with formatting...")
            
            file_id = self._get_excel_file_id()
            if not file_id:
                logger.error("❌ Cannot create headers: Excel file not found")
                return False
            
            # Create title row first
            title = {
                "values": [[
                    "SCRIBE VOICE EMAIL TRANSCRIPTION LOG",
                    "", "", "", "", "", "", "", "", ""  # Empty cells for merge
                ]]
            }
            
            # Write title to row 1
            title_success = self._write_to_excel_row(file_id, 1, title)
            if title_success:
                self._format_title_row(file_id)
            
            # Create headers for row 2
            headers = {
                "values": [[
                    "Date",
                    "Time",
                    "Email Sender",
                    "Phone Number",
                    "Attachment Filename",
                    "Transcription Text",
                    "Confidence (%)",
                    "Audio Duration (sec)",
                    "Status"
                ]]
            }
            
            # Write headers to row 2
            success = self._write_to_excel_row(file_id, 2, headers)
            
            if success:
                # Apply header formatting
                self._format_headers(file_id)
                # Set column widths
                self._set_column_widths(file_id)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error creating Excel headers: {e}")
            return False
    
    def _format_title_row(self, file_id: str) -> None:
        """Apply formatting to title row"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            
            # Merge cells A1:J1 for title
            merge_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='A1:J1')/merge"
            make_graph_request(merge_url, method='POST', data={})
            
            # Format title
            title_range = "A1:J1"
            format_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='{title_range}')/format"
            
            title_formatting = {
                "fill": {
                    "color": "#2F5496"  # Dark blue
                },
                "font": {
                    "bold": True,
                    "color": "#FFFFFF",  # White text
                    "size": 14,
                    "name": "Calibri"
                },
                "horizontalAlignment": "Center",
                "verticalAlignment": "Center"
            }
            
            make_graph_request(format_url, method='PATCH', data=title_formatting)
            # Title formatting applied
            
        except Exception as e:
            logger.warning(f"⚠️ Error formatting title: {e}")
    
    def _format_headers(self, file_id: str) -> None:
        """Apply formatting to header row"""
        try:
            worksheet_name = self._worksheet_name or "Sheet1"
            header_range = "A2:J2"
            format_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/{worksheet_name}/range(address='{header_range}')/format"
            
            header_formatting = {
                "fill": {
                    "color": "#2F5496"  # Professional dark blue
                },
                "font": {
                    "bold": True,
                    "color": "#FFFFFF",  # White text
                    "size": 12,
                    "name": "Calibri"
                },
                "borders": {
                    "style": "Continuous",
                    "color": "#1F4788",
                    "weight": "Medium"
                },
                "horizontalAlignment": "Center",
                "verticalAlignment": "Center"
            }
            
            response = make_graph_request(format_url, method='PATCH', data=header_formatting)
            
            if response and response.status_code == 200:
                # Header formatting applied
                pass
            else:
                logger.warning("⚠️ Failed to apply header formatting")
                
        except Exception as e:
            logger.warning(f"⚠️ Error formatting headers: {e}")
    
    def _set_column_widths(self, file_id: str) -> None:
        """Set appropriate column widths for better readability"""
        try:
            column_widths = self._get_optimal_column_widths()
            
            for column, width in column_widths.items():
                self._set_single_column_width(file_id, column, width)
            
            # Column widths set
            
        except Exception as e:
            logger.warning(f"⚠️ Error setting column widths: {e}")
    
    def _get_optimal_column_widths(self) -> dict:
        """Get the optimal column width configuration for professional appearance"""
        return {
            'A': 15,  # Date - adequate for MM/DD/YYYY
            'B': 15,  # Time - adequate for HH:MM AM/PM
            'C': 25,  # Email Sender - wider for full email addresses
            'D': 18,  # Phone Number - perfect for (xxx) xxx-xxxx format
            'E': 20,  # Attachment Filename - adequate for voice files
            'F': 90,  # Transcription Text - wider for readability
            'G': 15,  # Confidence Score - adequate for percentage
            'H': 18,  # Audio Duration - wider for seconds display
            'I': 12   # Status - adequate for Success/Failed
        }
    
    def _set_single_column_width(self, file_id: str, column: str, width: int) -> None:
        """Set width for a single column"""
        try:
            column_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/Sheet1/columns/{column}"
            
            column_data = {
                "columnWidth": width
            }
            
            make_graph_request(column_url, method='PATCH', data=column_data)
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to set width for column {column}: {e}")
    
    def test_excel_access(self) -> bool:
        """Test access to Excel file in OneDrive"""
        try:
            logger.info("🧪 Testing Excel file access...")
            
            file_id = self._get_excel_file_id()
            if not file_id:
                return False
            
            # Try to read the file properties
            file_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}"
            response = make_graph_request(file_url)
            
            if response and response.status_code == 200:
                file_info = response.json()
                logger.info(f"✅ Excel file access test passed: {file_info.get('name')}")
                return True
            else:
                logger.error(f"❌ Excel file access test failed: {response.status_code if response else 'No response'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Excel access test error: {e}")
            return False
    
    def _format_transcription_text(self, text: str) -> str:
        """Format transcription text as a clean single paragraph for Excel"""
        try:
            if not text:
                return ""
            
            # Decode HTML entities (like &#x27; to ')
            text = html.unescape(text)
            
            # Remove all line breaks and extra whitespace, create single paragraph
            text = ' '.join(text.split())
            text = text.strip()
            
            # Remove multiple spaces
            import re
            text = re.sub(r'\s+', ' ', text)
            
            # Capitalize first letter of sentences properly
            sentences = []
            current_sentence = ""
            
            # Split by sentence ending punctuation
            sentence_parts = re.split(r'([.!?])', text)
            for i in range(0, len(sentence_parts) - 1, 2):
                sentence_text = sentence_parts[i].strip()
                punctuation = sentence_parts[i + 1] if i + 1 < len(sentence_parts) else ""
                
                if sentence_text:
                    # Capitalize first letter
                    sentence_text = sentence_text[0].upper() + sentence_text[1:] if len(sentence_text) > 1 else sentence_text.upper()
                    sentences.append(sentence_text + punctuation)
            
            # Handle any remaining text
            if len(sentence_parts) % 2 == 1 and sentence_parts[-1].strip():
                remaining_text = sentence_parts[-1].strip()
                remaining_text = remaining_text[0].upper() + remaining_text[1:] if len(remaining_text) > 1 else remaining_text.upper()
                sentences.append(remaining_text)
            
            # Join sentences with proper spacing
            text = ' '.join(sentences)
            
            # Add final punctuation if missing
            if text and not text.endswith(('.', '!', '?')):
                text += '.'
            
            # Clean up any double spaces
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
            
        except Exception as e:
            logger.warning(f"⚠️ Error formatting transcription text: {e}")
            return text  # Return original text if formatting fails
    
