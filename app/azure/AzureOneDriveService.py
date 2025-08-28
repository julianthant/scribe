"""
AzureOneDriveService.py - Microsoft Graph API OneDrive/Excel Service

Provides OneDrive and Excel operations through Microsoft Graph API.
This service handles:
- OneDrive file operations (create, read, update)
- Excel workbook management
- Worksheet operations (create, update, format)
- Cell and range operations
- Batch operations for efficiency
- Error handling and retry logic

The AzureOneDriveService class serves as the interface for all OneDrive/Excel operations.
"""

from typing import Optional, Dict, Any, List, Union
import logging
import json
from datetime import datetime

import httpx

from app.core.config import settings
from app.core.Exceptions import AuthenticationError, AuthorizationError, ValidationError
from app.models.ExcelSync import TranscriptionRowData, ExcelColumnFormat

logger = logging.getLogger(__name__)


class AzureOneDriveService:
    """Microsoft Graph API service for OneDrive and Excel operations."""

    def __init__(self):
        """Initialize OneDrive service."""
        self.graph_base_url = "https://graph.microsoft.com/v1.0"
        self.timeout = getattr(settings, 'excel_sync_timeout_seconds', 120)
        self.max_retries = getattr(settings, 'excel_max_retry_attempts', 3)

    async def get_or_create_excel_file(
        self,
        access_token: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        Get existing Excel file or create new one in OneDrive root.

        Args:
            access_token: Valid access token
            file_name: Excel file name (without .xlsx extension)

        Returns:
            File information from Graph API

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # First, try to get existing file
            file_name_with_ext = f"{file_name}.xlsx"
            get_url = f"{self.graph_base_url}/me/drive/root:/{file_name_with_ext}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    get_url,
                    headers=headers,
                    timeout=self.timeout
                )

            # If file exists, return it
            if response.status_code == 200:
                file_data = response.json()
                logger.info(f"Found existing Excel file: {file_name_with_ext}")
                return file_data

            # If file doesn't exist (404), create it
            elif response.status_code == 404:
                return await self._create_excel_file(access_token, file_name)

            # Handle other errors
            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access OneDrive")
            else:
                logger.error(f"Graph API error getting file: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to access Excel file")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting/creating Excel file: {str(e)}")
            raise AuthenticationError("Failed to access Excel file")

    async def _create_excel_file(
        self,
        access_token: str,
        file_name: str
    ) -> Dict[str, Any]:
        """
        Create a new Excel file in OneDrive root.

        Args:
            access_token: Valid access token
            file_name: Excel file name (without .xlsx extension)

        Returns:
            Created file information
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            file_name_with_ext = f"{file_name}.xlsx"
            
            # Create empty Excel workbook using the workbooks endpoint
            create_url = f"{self.graph_base_url}/me/drive/root:/{file_name_with_ext}:/workbook"

            # Create request body for new workbook
            create_body = {}

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    create_url,
                    headers=headers,
                    json=create_body,
                    timeout=self.timeout
                )

            if response.status_code == 201:
                # Get the file metadata after creation
                get_url = f"{self.graph_base_url}/me/drive/root:/{file_name_with_ext}"
                get_response = await client.get(
                    get_url,
                    headers=headers,
                    timeout=self.timeout
                )
                
                if get_response.status_code == 200:
                    file_data = get_response.json()
                    logger.info(f"Created new Excel file: {file_name_with_ext}")
                    return file_data
                else:
                    logger.error(f"Failed to get created file metadata: {get_response.status_code}")
                    raise AuthenticationError("Failed to retrieve created file")

            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to create Excel file")
            else:
                logger.error(f"Graph API error creating file: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to create Excel file")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating Excel file: {str(e)}")
            raise AuthenticationError("Failed to create Excel file")

    async def get_worksheets(
        self,
        access_token: str,
        file_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all worksheets in an Excel file.

        Args:
            access_token: Valid access token
            file_id: OneDrive file ID

        Returns:
            List of worksheet information

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=self.timeout
                )

            if response.status_code == 200:
                worksheets_data = response.json()
                worksheets = worksheets_data.get("value", [])
                logger.info(f"Retrieved {len(worksheets)} worksheets")
                return worksheets

            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access worksheets")
            elif response.status_code == 404:
                raise AuthenticationError("Excel file not found")
            else:
                logger.error(f"Graph API error getting worksheets: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to retrieve worksheets")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting worksheets: {str(e)}")
            raise AuthenticationError("Failed to retrieve worksheets")

    async def get_or_create_worksheet(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str
    ) -> Dict[str, Any]:
        """
        Get existing worksheet or create new one.

        Args:
            access_token: Valid access token
            file_id: OneDrive file ID
            worksheet_name: Worksheet name

        Returns:
            Worksheet information

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            # First, try to get existing worksheet
            worksheets = await self.get_worksheets(access_token, file_id)
            
            for worksheet in worksheets:
                if worksheet["name"] == worksheet_name:
                    logger.info(f"Found existing worksheet: {worksheet_name}")
                    return worksheet

            # If worksheet doesn't exist, create it
            return await self._create_worksheet(access_token, file_id, worksheet_name)

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting/creating worksheet: {str(e)}")
            raise AuthenticationError("Failed to access worksheet")

    async def _create_worksheet(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str
    ) -> Dict[str, Any]:
        """
        Create a new worksheet in Excel file.

        Args:
            access_token: Valid access token
            file_id: OneDrive file ID
            worksheet_name: Worksheet name

        Returns:
            Created worksheet information
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets"

            request_body = {
                "name": worksheet_name
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=self.timeout
                )

            if response.status_code == 201:
                worksheet_data = response.json()
                logger.info(f"Created new worksheet: {worksheet_name}")
                return worksheet_data

            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to create worksheet")
            else:
                logger.error(f"Graph API error creating worksheet: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to create worksheet")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating worksheet: {str(e)}")
            raise AuthenticationError("Failed to create worksheet")

    async def write_transcription_data(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str,
        transcriptions: List[TranscriptionRowData],
        start_row: int = 2  # Start after header row
    ) -> Dict[str, Any]:
        """
        Write transcription data to Excel worksheet.

        Args:
            access_token: Valid access token
            file_id: OneDrive file ID
            worksheet_name: Worksheet name
            transcriptions: List of transcription data
            start_row: Starting row number (1-indexed)

        Returns:
            Result of write operation

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            if not transcriptions:
                logger.warning("No transcription data provided")
                return {"rows_written": 0}

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Prepare data for Excel
            values = []
            for transcription in transcriptions:
                row = [
                    transcription.transcription_id,
                    transcription.date_time.strftime("%Y-%m-%d %H:%M:%S"),
                    transcription.sender_name or "",
                    transcription.sender_email,
                    transcription.subject,
                    transcription.audio_duration or "",
                    transcription.transcript_text,
                    transcription.confidence_score or "",
                    transcription.language or "",
                    transcription.model_used,
                    transcription.processing_time_ms or ""
                ]
                values.append(row)

            # Calculate range
            end_row = start_row + len(values) - 1
            range_address = f"A{start_row}:K{end_row}"

            # Write data to worksheet
            url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')/range(address='{range_address}')"

            request_body = {
                "values": values
            }

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=self.timeout
                )

            if response.status_code == 200:
                logger.info(f"Wrote {len(values)} rows to worksheet {worksheet_name}")
                return {
                    "rows_written": len(values),
                    "range_address": range_address,
                    "start_row": start_row,
                    "end_row": end_row
                }

            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to write to Excel")
            elif response.status_code == 404:
                raise AuthenticationError("Excel file or worksheet not found")
            else:
                logger.error(f"Graph API error writing data: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to write data to Excel")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error writing transcription data: {str(e)}")
            raise AuthenticationError("Failed to write transcription data")

    async def format_worksheet(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str,
        apply_header_formatting: bool = True,
        apply_column_formatting: bool = True,
        freeze_header_row: bool = True
    ) -> Dict[str, Any]:
        """
        Apply formatting to Excel worksheet.

        Args:
            access_token: Valid access token
            file_id: OneDrive file ID
            worksheet_name: Worksheet name
            apply_header_formatting: Whether to format header row
            apply_column_formatting: Whether to format columns
            freeze_header_row: Whether to freeze header row

        Returns:
            Result of formatting operations

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            formatting_results = {}

            # Format header row
            if apply_header_formatting:
                await self._format_header_row(access_token, file_id, worksheet_name, headers)
                formatting_results["header_formatted"] = True

            # Format columns
            if apply_column_formatting:
                await self._format_columns(access_token, file_id, worksheet_name, headers)
                formatting_results["columns_formatted"] = True

            # Freeze header row
            if freeze_header_row:
                await self._freeze_header_row(access_token, file_id, worksheet_name, headers)
                formatting_results["header_frozen"] = True

            logger.info(f"Applied formatting to worksheet {worksheet_name}")
            return formatting_results

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error formatting worksheet: {str(e)}")
            raise AuthenticationError("Failed to format worksheet")

    async def _format_header_row(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str,
        headers: Dict[str, str]
    ) -> None:
        """Format the header row with bold text and background color."""
        try:
            # Set header values
            header_values = [[
                "ID", "Date & Time", "Sender Name", "Sender Email", "Subject",
                "Audio Duration", "Transcript Text", "Confidence Score",
                "Language", "Model Used", "Processing Time (ms)"
            ]]

            # Write header values
            header_url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')/range(address='A1:K1')"
            header_body = {"values": header_values}

            async with httpx.AsyncClient() as client:
                await client.patch(header_url, headers=headers, json=header_body, timeout=self.timeout)

            # Format header row (bold, background color)
            format_url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')/range(address='A1:K1')/format"
            format_body = {
                "font": {
                    "bold": True,
                    "color": "#FFFFFF"
                },
                "fill": {
                    "color": "#4472C4"
                }
            }

            async with httpx.AsyncClient() as client:
                await client.patch(format_url, headers=headers, json=format_body, timeout=self.timeout)

        except Exception as e:
            logger.error(f"Error formatting header row: {str(e)}")
            raise

    async def _format_columns(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str,
        headers: Dict[str, str]
    ) -> None:
        """Format column widths and text wrapping."""
        try:
            column_widths = getattr(settings, 'excel_column_widths', {})
            
            # Column mappings (A=0, B=1, etc.)
            column_configs = [
                ("A", column_widths.get("ID", 25), False),  # ID
                ("B", column_widths.get("Date_Time", 20), False),  # Date & Time
                ("C", column_widths.get("Sender_Name", 25), False),  # Sender Name
                ("D", column_widths.get("Sender_Email", 30), False),  # Sender Email
                ("E", column_widths.get("Subject", 40), True),  # Subject
                ("F", column_widths.get("Audio_Duration", 15), False),  # Audio Duration
                ("G", column_widths.get("Transcript_Text", 80), True),  # Transcript Text
                ("H", column_widths.get("Confidence_Score", 18), False),  # Confidence Score
                ("I", column_widths.get("Language", 12), False),  # Language
                ("J", column_widths.get("Model_Used", 20), False),  # Model Used
                ("K", column_widths.get("Processing_Time", 18), False),  # Processing Time
            ]

            # Format each column
            for column_letter, width, wrap_text in column_configs:
                column_url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')/range(address='{column_letter}:{column_letter}')/format"
                
                column_format = {
                    "columnWidth": width,
                    "wrapText": wrap_text
                }

                async with httpx.AsyncClient() as client:
                    await client.patch(column_url, headers=headers, json=column_format, timeout=self.timeout)

        except Exception as e:
            logger.error(f"Error formatting columns: {str(e)}")
            raise

    async def _freeze_header_row(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str,
        headers: Dict[str, str]
    ) -> None:
        """Freeze the header row."""
        try:
            url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')"
            
            # Freeze panes at A2 (after header row)
            freeze_body = {
                "freezePanes": {
                    "freezeAt": "A2"
                }
            }

            async with httpx.AsyncClient() as client:
                await client.patch(url, headers=headers, json=freeze_body, timeout=self.timeout)

        except Exception as e:
            logger.error(f"Error freezing header row: {str(e)}")
            # Don't raise - this is not critical
            pass

    async def get_worksheet_data(
        self,
        access_token: str,
        file_id: str,
        worksheet_name: str,
        range_address: Optional[str] = None
    ) -> List[List[Any]]:
        """
        Get data from Excel worksheet.

        Args:
            access_token: Valid access token
            file_id: OneDrive file ID
            worksheet_name: Worksheet name
            range_address: Optional range address (e.g., 'A1:K100')

        Returns:
            List of rows (each row is a list of cell values)

        Raises:
            AuthenticationError: If API call fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            if range_address:
                url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')/range(address='{range_address}')"
            else:
                url = f"{self.graph_base_url}/me/drive/items/{file_id}/workbook/worksheets('{worksheet_name}')/usedRange"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=self.timeout
                )

            if response.status_code == 200:
                range_data = response.json()
                values = range_data.get("values", [])
                logger.info(f"Retrieved {len(values)} rows from worksheet {worksheet_name}")
                return values

            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to read Excel data")
            elif response.status_code == 404:
                logger.info(f"Worksheet {worksheet_name} is empty or doesn't exist")
                return []
            else:
                logger.error(f"Graph API error reading data: {response.status_code} - {response.text}")
                raise AuthenticationError("Failed to read worksheet data")

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting worksheet data: {str(e)}")
            raise AuthenticationError("Failed to retrieve worksheet data")

    async def check_onedrive_access(self, access_token: str) -> Dict[str, Any]:
        """
        Check OneDrive access and permissions.

        Args:
            access_token: Valid access token

        Returns:
            Health check result

        Raises:
            AuthenticationError: If access check fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Test access to OneDrive root
            url = f"{self.graph_base_url}/me/drive"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=30.0
                )

            if response.status_code == 200:
                drive_data = response.json()
                return {
                    "accessible": True,
                    "drive_id": drive_data.get("id"),
                    "drive_type": drive_data.get("driveType"),
                    "owner": drive_data.get("owner", {}).get("user", {}).get("displayName"),
                    "quota": drive_data.get("quota", {}),
                    "checked_at": datetime.utcnow().isoformat()
                }

            elif response.status_code == 401:
                raise AuthenticationError("Access token is invalid or expired")
            elif response.status_code == 403:
                raise AuthorizationError("Insufficient permissions to access OneDrive")
            else:
                logger.error(f"OneDrive access check failed: {response.status_code} - {response.text}")
                return {
                    "accessible": False,
                    "error": f"HTTP {response.status_code}",
                    "checked_at": datetime.utcnow().isoformat()
                }

        except (AuthenticationError, AuthorizationError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error checking OneDrive access: {str(e)}")
            return {
                "accessible": False,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }


# Global instance
azure_onedrive_service = AzureOneDriveService()