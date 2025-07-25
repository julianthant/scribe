"""
Excel Processing class definitions
Contains the ExcelProcessor class with method signatures that delegate to function implementations
"""


class ExcelProcessor:
    """Excel processing class with delegated implementations"""
    
    def __init__(self, access_token, excel_file_name):
        self.access_token = access_token
        self.excel_file_name = excel_file_name
    
    def update_excel_file(self, structured_data, voice_url):
        """Update Excel file with new voicemail data"""
        from excel_processor_functions import update_excel_file_impl
        return update_excel_file_impl(self, structured_data, voice_url)
    
    def _find_excel_file(self):
        """Find the Excel file in OneDrive"""
        from excel_processor_functions import find_excel_file_impl
        return find_excel_file_impl(self)
    
    def _setup_excel_worksheet(self, workbook_url, headers):
        """Ensure the worksheet exists with column-based layout"""
        from excel_processor_functions import setup_excel_worksheet_impl
        return setup_excel_worksheet_impl(self, workbook_url, headers)
    
    def _find_next_column(self, workbook_url, headers):
        """Find the next available column"""
        from excel_processor_functions import find_next_column_impl
        return find_next_column_impl(self, workbook_url, headers)
    
    def _shift_columns_right(self, workbook_url, headers, rightmost_column):
        """Shift all existing voicemail columns one position to the right"""
        from excel_processor_functions import shift_columns_right_impl
        return shift_columns_right_impl(self, workbook_url, headers, rightmost_column)
    
    def _copy_column_formatting(self, workbook_url, headers, source_col, target_col):
        """Copy formatting from source column to target column"""
        from excel_processor_functions import copy_column_formatting_impl
        return copy_column_formatting_impl(self, workbook_url, headers, source_col, target_col)
    
    def _format_excel_column(self, workbook_url, headers, column_letter, voice_url):
        """Apply enhanced formatting to the column with hyperlinks and styling"""
        from excel_processor_functions import format_excel_column_impl
        return format_excel_column_impl(self, workbook_url, headers, column_letter, voice_url)
    
    def _set_enhanced_row_heights(self, workbook_url, headers):
        """Set enhanced row heights for better content display"""
        from excel_processor_functions import set_enhanced_row_heights_impl
        return set_enhanced_row_heights_impl(self, workbook_url, headers)
    
    def _create_enhanced_hyperlink(self, workbook_url, headers, column_letter, voice_url):
        """Create an enhanced hyperlink for the audio file"""
        from excel_processor_functions import create_enhanced_hyperlink_impl
        return create_enhanced_hyperlink_impl(self, workbook_url, headers, column_letter, voice_url)
