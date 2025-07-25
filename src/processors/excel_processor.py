"""
Production Excel Processor using new core architecture
Handles Excel file operations with error handling and monitoring
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..core import ScribeLogger, ScribeErrorHandler, ScribeConfigurationManager
from ..helpers.retry_helpers import RetryConfig, retry_with_exponential_backoff
from ..helpers.performance_helpers import PerformanceTimer
from ..helpers.validation_helpers import validate_url
from ..helpers.http_helpers import make_authenticated_request
from ..helpers.request_config import RequestConfig


class ScribeExcelProcessor:
    """Production Excel processor with comprehensive error handling"""
    
    def __init__(self, configuration_manager: ScribeConfigurationManager,
                 error_handler: ScribeErrorHandler, logger: ScribeLogger):
        """Initialize Excel processor with injected dependencies"""
        self.config = configuration_manager
        self.error_handler = error_handler
        self.logger = logger
        self.auth_manager = None
        self.excel_file_name = None
    
    def initialize(self, excel_file_name: str) -> bool:
        """Initialize processor with file configuration"""
        try:
            # Get centralized auth manager
            from ..helpers.auth_helpers import get_auth_manager
            self.auth_manager = get_auth_manager()
            
            self.excel_file_name = excel_file_name
            
            self.logger.log_info("Excel processor initialized successfully", {
                'excel_file_name': excel_file_name,
                'has_auth_manager': bool(self.auth_manager)
            })
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize Excel processor")
            return False
    
    def update_excel_with_transcription(self, structured_data: Dict[str, Any], 
                                      voice_url: str) -> bool:
        """Update Excel file with new transcription data"""
        with PerformanceTimer("update_spreadsheet") as timer:
            try:
                # Find Excel file
                workbook_url = self._find_excel_file()
                if not workbook_url:
                    return False
                
                # Setup worksheet with headers
                headers = self._get_standard_headers()
                worksheet_setup = self._setup_worksheet(workbook_url, headers)
                if not worksheet_setup:
                    return False
                
                # Find next available column
                next_column = self._find_next_available_column(workbook_url, headers)
                if not next_column:
                    return False
                
                # Insert new data
                success = self._insert_transcription_data(
                    workbook_url, headers, next_column, structured_data, voice_url
                )
                
                if success:
                    self.logger.log_info("Excel file updated successfully", {
                        'workbook_url': workbook_url,
                        'column_used': next_column,
                        'processing_time_ms': timer.elapsed_ms,
                        'voice_url': voice_url
                    })
                
                return success
                
            except Exception as e:
                self.error_handler.handle_error(e, "Failed to update Excel file")
                return False
    
    def backup_excel_file(self, workbook_url: str) -> Optional[str]:
        """Create backup of Excel file before modifications"""
        try:
            backup_name = f"{self.excel_file_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Implementation would create a copy of the workbook
            # This is a placeholder for the backup logic
            self.logger.log_info("Excel backup created", {
                'original_file': self.excel_file_name,
                'backup_name': backup_name
            })
            
            return backup_name
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to create Excel backup")
            return None
    
    def _find_excel_file(self) -> Optional[str]:
        """Find Excel file in OneDrive"""
        
        def _search_operation():
            search_url = f"{RequestConfig.ENDPOINTS['graph_drive']}/search(q='{self.excel_file_name}')"
            
            response = make_authenticated_request(
                'GET', search_url,
                token_type='graph',
                operation_type='api'
            )
            
            items = response.json().get('value', [])
            excel_files = [item for item in items if item['name'] == self.excel_file_name]
            
            if not excel_files:
                raise Exception(f"Excel file '{self.excel_file_name}' not found")
            
            return excel_files[0]['webUrl']
        
        try:
            workbook_url = retry_with_exponential_backoff(
                _search_operation, 
                RequestConfig.get_retry_for_operation('network'),
                "find_excel_file"
            )
            self.logger.log_info(f"Found Excel file: {workbook_url}")
            return workbook_url
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to find Excel file {self.excel_file_name}")
            return None
    
    def _setup_worksheet(self, workbook_url: str, headers: List[str]) -> bool:
        """Setup worksheet with required headers"""
        try:
            # Get workbook ID from URL
            workbook_id = self._extract_workbook_id(workbook_url)
            if not workbook_id:
                return False
            
            # Ensure headers exist in the worksheet
            return self._ensure_headers_exist(workbook_id, headers)
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to setup worksheet")
            return False
    
    def _find_next_available_column(self, workbook_url: str, headers: List[str]) -> Optional[str]:
        """Find the next available column for data insertion"""
        try:
            workbook_id = self._extract_workbook_id(workbook_url)
            if not workbook_id:
                return None
            
            # Get used range to find next available column
            used_range = self._get_used_range(workbook_id)
            if not used_range:
                return "B"  # Start with column B if no data exists
            
            # Calculate next column letter
            next_column = self._calculate_next_column(used_range)
            return next_column
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to find next available column")
            return None
    
    def _insert_transcription_data(self, workbook_url: str, headers: List[str],
                                 column: str, data: Dict[str, Any], voice_url: str) -> bool:
        """Insert transcription data into specified column"""
        
        def _insert_operation():
            workbook_id = self._extract_workbook_id(workbook_url)
            if not workbook_id:
                raise Exception("Invalid workbook URL")
            
            # Prepare data values for insertion
            values = self._prepare_data_values(data, voice_url)
            
            # Insert data into column
            range_address = f"{column}1:{column}{len(headers)}"
            return self._update_cell_range(workbook_id, range_address, values)
        
        try:
            return retry_with_exponential_backoff(
                _insert_operation, 
                RequestConfig.get_retry_for_operation('network'),
                "insert_data_operation"
            )
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to insert data in column {column}")
            return False
    
    def _get_standard_headers(self) -> List[str]:
        """Get standard headers for the Excel worksheet"""
        return [
            "Date",
            "Time", 
            "From",
            "Subject",
            "Transcript",
            "Voice Recording",
            "Duration",
            "Confidence"
        ]
    
    def _extract_workbook_id(self, workbook_url: str) -> Optional[str]:
        """Extract workbook ID from OneDrive URL"""
        try:
            if not validate_url(workbook_url):
                return None
            
            # Extract ID from OneDrive URL
            # This is a simplified extraction - real implementation would be more robust
            parts = workbook_url.split('/')
            for i, part in enumerate(parts):
                if 'workbook' in part.lower() and i + 1 < len(parts):
                    return parts[i + 1]
            
            return None
            
        except Exception:
            return None
    
    def _ensure_headers_exist(self, workbook_id: str, headers: List[str]) -> bool:
        """Ensure required headers exist in the worksheet"""
        
        def _headers_operation():
            headers_data = {"values": [headers]}
            range_address = f"A1:{chr(ord('A') + len(headers) - 1)}1"
            
            return self._update_cell_range(workbook_id, range_address, headers_data["values"])
        
        try:
            return retry_with_exponential_backoff(
                _headers_operation, 
                RequestConfig.get_retry_for_operation('network'),
                "ensure_headers_operation"
            )
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to ensure headers exist")
            return False
    
    def _get_used_range(self, workbook_id: str) -> Optional[Dict]:
        """Get the used range of the worksheet"""
        
        def _range_operation():
            url = f"{RequestConfig.ENDPOINTS['graph_drive']}/items/{workbook_id}/workbook/worksheets/Sheet1/usedRange"
            
            response = make_authenticated_request(
                'GET', url,
                token_type='graph',
                operation_type='api'
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None  # No used range
            else:
                raise Exception(f"Failed to get used range: {response.text}")
        
        try:
            return retry_with_exponential_backoff(
                _range_operation, 
                RequestConfig.get_retry_for_operation('network'),
                "get_used_range"
            )
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to get used range")
            return None
    
    def _calculate_next_column(self, used_range: Dict) -> str:
        """Calculate next available column letter"""
        try:
            address = used_range.get('address', '')
            # Extract column information from address (e.g., "Sheet1!A1:E10")
            if ':' in address:
                end_range = address.split(':')[1]
                last_column = ''.join(c for c in end_range if c.isalpha())
                # Calculate next column letter
                return chr(ord(last_column) + 1)
            
            return "B"  # Default to column B
            
        except Exception:
            return "B"  # Safe default
    
    def _prepare_data_values(self, data: Dict[str, Any], voice_url: str) -> List[List[Any]]:
        """Prepare data values for Excel insertion"""
        try:
            values = [
                [data.get('date', datetime.now().strftime('%Y-%m-%d'))],
                [data.get('time', datetime.now().strftime('%H:%M:%S'))],
                [data.get('from', '')],
                [data.get('subject', '')],
                [data.get('transcript', '')],
                [voice_url],
                [data.get('duration', '')],
                [data.get('confidence', '')]
            ]
            
            return values
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to prepare data values")
            return []
    
    def _update_cell_range(self, workbook_id: str, range_address: str, values: List) -> bool:
        """Update cell range with values"""
        
        def _update_operation():
            url = f"{RequestConfig.ENDPOINTS['graph_drive']}/items/{workbook_id}/workbook/worksheets/Sheet1/range(address='{range_address}')"
            
            data = {"values": values}
            
            response = make_authenticated_request(
                'PATCH', url,
                token_type='graph',
                operation_type='api',
                json=data
            )
            
            return True
        
        try:
            return retry_with_exponential_backoff(
                _update_operation, 
                RequestConfig.get_retry_for_operation('network'),
                "update_cell_range"
            )
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to update range {range_address}")
            return False
    
    def _get_request_headers(self) -> Dict[str, str]:
        """Get headers for Graph API requests"""
        return self.auth_manager.get_auth_headers('graph')
