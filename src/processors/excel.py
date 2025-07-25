"""
Excel Processor for Scribe Voice Email Processor
Handles writing transcription results to Excel file in OneDrive
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from core.config import ScribeConfig
from core.input_validation import input_validator
from helpers.oauth import make_graph_request
from models.data import TranscriptionResult, ExcelWriteResult

logger = logging.getLogger(__name__)

class ExcelProcessor:
    """Process Excel file operations for transcription logging"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        # Validate Excel filename
        validated_filename = input_validator.validate_excel_filename(config.excel_file_name)
        self.excel_file_name = validated_filename or "scribe_transcriptions.xlsx"
        if validated_filename != config.excel_file_name:
            logger.warning(f"⚠️ Excel filename sanitized: {config.excel_file_name} -> {self.excel_file_name}")
        self._file_id_cache = None
        logger.info(f"📊 Excel processor initialized: {self.excel_file_name}")
    
    def write_transcription_result(
        self,
        transcription: TranscriptionResult,
        email_subject: str,
        email_sender: str,
        email_date: datetime,
        attachment_filename: str
    ) -> ExcelWriteResult:
        """Write transcription result to Excel file in OneDrive"""
        start_time = time.time()
        
        try:
            logger.info(f"📊 Writing transcription to Excel: {attachment_filename}")
            
            # Validate prerequisites
            file_id = self._validate_excel_file_access()
            if not file_id:
                return self._create_error_result("Excel file not found or inaccessible", start_time)
            
            # Determine write location
            next_row = self._determine_next_row(file_id)
            if next_row is None:
                return self._create_error_result("Failed to determine next row in Excel file", start_time)
            
            # Execute write operation
            write_success = self._execute_excel_write(
                file_id, next_row, transcription, email_subject, email_sender, email_date, attachment_filename
            )
            
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
    
    def _execute_excel_write(
        self,
        file_id: str,
        row_number: int,
        transcription: TranscriptionResult,
        email_subject: str,
        email_sender: str,
        email_date: datetime,
        attachment_filename: str
    ) -> bool:
        """Execute the actual Excel write operation"""
        try:
            # Prepare data for Excel
            excel_data = self._prepare_excel_data(
                transcription, email_subject, email_sender, email_date, attachment_filename
            )
            
            # Write to Excel
            success = self._write_to_excel_row(file_id, row_number, excel_data)
            
            if success:
                logger.info(f"✅ Excel write successful: Row {row_number}")
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
            # Use cached file ID if available
            if self._file_id_cache:
                return self._file_id_cache
            
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
            if file_id:
                self._file_id_cache = file_id
                logger.info(f"✅ Found Excel file: {self.excel_file_name} (ID: {file_id[:20]}...)")
                return file_id
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting Excel file ID: {e}")
            return None
    
    def _get_next_row_number(self, file_id: str) -> Optional[int]:
        """Get the next available row number in the worksheet"""
        try:
            # Get worksheet data to determine last used row
            worksheet_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/Sheet1/usedRange"
            response = make_graph_request(worksheet_url)
            
            if response and response.status_code == 200:
                used_range = response.json()
                row_count = used_range.get('rowCount', 0)
                next_row = row_count + 1  # Next available row
                logger.info(f"📊 Excel file has {row_count} used rows, next row: {next_row}")
                return next_row
            else:
                # If no used range (empty file), start at row 1
                logger.info("📊 Excel file appears empty, starting at row 1")
                return 1
                
        except Exception as e:
            logger.error(f"❌ Error getting next row number: {e}")
            # Default to a safe row number
            return None
    
    def _prepare_excel_data(
        self,
        transcription: TranscriptionResult,
        email_subject: str,
        email_sender: str,
        email_date: datetime,
        attachment_filename: str
    ) -> dict:
        """Prepare and validate data for Excel write operation"""
        
        # Format data for Excel
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        email_date_str = email_date.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Validate and sanitize all data
        validated_sender = input_validator.validate_email_address(email_sender) or "Unknown"
        validated_subject = input_validator.validate_email_subject(email_subject) or "No Subject"
        validated_filename = input_validator.validate_filename(attachment_filename) or "unknown_file"
        validated_text = input_validator.validate_transcription_text(transcription.text) or ""
        
        # Ensure confidence is within valid range
        confidence = max(0.0, min(1.0, transcription.confidence or 0.0))
        
        # Ensure duration is positive
        duration = max(0.0, transcription.duration_seconds or 0.0)
        
        # Ensure word count is positive integer
        word_count = max(0, int(transcription.word_count or 0))
        
        return {
            "values": [[
                timestamp,                           # Column A: Processing Timestamp
                email_date_str,                      # Column B: Email Date
                validated_sender,                    # Column C: Email Sender (validated)
                validated_subject,                   # Column D: Email Subject (sanitized)
                validated_filename,                  # Column E: Attachment Filename (validated)
                validated_text,                      # Column F: Transcription Text (sanitized)
                confidence,                          # Column G: Confidence Score (validated)
                duration,                            # Column H: Audio Duration (validated)
                word_count,                          # Column I: Word Count (validated)
                "Success" if transcription.success else "Failed"  # Column J: Status
            ]]
        }
    
    def _write_to_excel_row(self, file_id: str, row_number: int, excel_data: dict) -> bool:
        """Write data to specific Excel row with formatting"""
        try:
            # Define the range for the row (A:J covers our columns)
            range_address = f"A{row_number}:J{row_number}"
            
            # Update the specific range with data
            update_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/Sheet1/range(address='{range_address}')"
            
            response = make_graph_request(update_url, method='PATCH', data=excel_data)
            
            if response and response.status_code == 200:
                logger.info(f"✅ Successfully wrote to Excel row {row_number}")
                
                # Apply formatting to the row
                self._apply_row_formatting(file_id, row_number)
                
                return True
            else:
                logger.error(f"❌ Failed to write to Excel: {response.status_code if response else 'No response'}")
                if response:
                    logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error writing to Excel row: {e}")
            return False
    
    def _apply_row_formatting(self, file_id: str, row_number: int) -> None:
        """Apply formatting to a specific row"""
        try:
            # Apply different formatting to different column types
            self._format_transcription_column(file_id, row_number)
            self._format_date_columns(file_id, row_number)
            self._format_number_columns(file_id, row_number)
            self._format_status_column(file_id, row_number)
            
            logger.info(f"✨ Applied formatting to row {row_number}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to apply formatting to row {row_number}: {e}")
            # Don't fail the entire operation if formatting fails
    
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
        return f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/Sheet1/range(address='{range_address}')/format"
    
    def create_excel_headers(self) -> bool:
        """Create formatted headers in Excel file if they don't exist"""
        try:
            logger.info("📊 Creating Excel headers with formatting...")
            
            file_id = self._get_excel_file_id()
            if not file_id:
                logger.error("❌ Cannot create headers: Excel file not found")
                return False
            
            headers = {
                "values": [[
                    "Processing Timestamp",
                    "Email Date", 
                    "Email Sender",
                    "Email Subject",
                    "Attachment Filename",
                    "Transcription Text",
                    "Confidence Score",
                    "Audio Duration (sec)",
                    "Word Count",
                    "Status"
                ]]
            }
            
            # Write headers to row 1
            success = self._write_to_excel_row(file_id, 1, headers)
            
            if success:
                # Apply header formatting
                self._format_headers(file_id)
                # Set column widths
                self._set_column_widths(file_id)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error creating Excel headers: {e}")
            return False
    
    def _format_headers(self, file_id: str) -> None:
        """Apply formatting to header row"""
        try:
            header_range = "A1:J1"
            format_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/workbook/worksheets/Sheet1/range(address='{header_range}')/format"
            
            header_formatting = {
                "fill": {
                    "color": "#4F81BD"  # Professional blue
                },
                "font": {
                    "bold": True,
                    "color": "#FFFFFF",  # White text
                    "size": 11,
                    "name": "Calibri"
                },
                "borders": {
                    "style": "Continuous",
                    "color": "#000000",
                    "weight": "Thin"
                },
                "horizontalAlignment": "Center",
                "verticalAlignment": "Center"
            }
            
            response = make_graph_request(format_url, method='PATCH', data=header_formatting)
            
            if response and response.status_code == 200:
                logger.info("✨ Header formatting applied successfully")
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
            
            logger.info("📏 Column widths set successfully")
            
        except Exception as e:
            logger.warning(f"⚠️ Error setting column widths: {e}")
    
    def _get_optimal_column_widths(self) -> dict:
        """Get the optimal column width configuration"""
        return {
            'A': 20,  # Processing Timestamp
            'B': 20,  # Email Date
            'C': 25,  # Email Sender
            'D': 30,  # Email Subject
            'E': 20,  # Attachment Filename
            'F': 50,  # Transcription Text (wider for readability)
            'G': 15,  # Confidence Score
            'H': 15,  # Audio Duration
            'I': 12,  # Word Count
            'J': 12   # Status
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
                logger.info(f"✅ Excel file access test passed: {file_info.get('name')} ({file_info.get('size', 0)} bytes)")
                return True
            else:
                logger.error(f"❌ Excel file access test failed: {response.status_code if response else 'No response'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Excel access test error: {e}")
            return False
    
    def _format_transcription_text(self, text: str) -> str:
        """Format transcription text for better display in Excel"""
        try:
            if not text:
                return ""
            
            # Remove excessive whitespace
            text = ' '.join(text.split())
            
            # Add line breaks every 80 characters at word boundaries for better readability
            words = text.split(' ')
            formatted_lines = []
            current_line = ""
            
            for word in words:
                # Check if adding this word would exceed line length
                if len(current_line + " " + word) > 80 and current_line:
                    formatted_lines.append(current_line.strip())
                    current_line = word
                else:
                    current_line = current_line + " " + word if current_line else word
            
            # Add the last line
            if current_line:
                formatted_lines.append(current_line.strip())
            
            # Join with line breaks (Excel will display these properly with text wrapping)
            formatted_text = "\n".join(formatted_lines)
            
            # Add a summary line at the end if text is long
            if len(formatted_text) > 200:
                word_count = len(words)
                summary = f"\n\n[{word_count} words total]"
                formatted_text += summary
            
            return formatted_text
            
        except Exception as e:
            logger.warning(f"⚠️ Error formatting transcription text: {e}")
            return text  # Return original text if formatting fails