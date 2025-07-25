"""
Excel Processing function implementations
Contains all the actual function implementations for Excel operations
"""

import logging
import requests
from datetime import datetime


def update_excel_file_impl(self, structured_data, voice_url):
    """Update Excel file with new voicemail data using efficient row-based approach"""
    try:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # First, find the Excel file
        excel_file_id = find_excel_file_impl(self)
        if not excel_file_id:
            logging.error("Could not find Excel file")
            return False
        
        # Get the workbook and worksheet - use /me endpoint
        workbook_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{excel_file_id}/workbook"
        
        # Ensure the worksheet exists and has proper headers
        setup_excel_worksheet_impl(self, workbook_url, headers)
        
        # Find the next available row (more efficient than column shifting)
        next_row = find_next_row_impl(self, workbook_url, headers)
        
        # Prepare row data (horizontal layout)
        processed_date_display = str(structured_data.get('processed_date', ''))
        received_date_display = str(structured_data.get('received_date', ''))
        
        # Get transcript and clean it (remove Azure info for cleaner display)
        transcript_text = structured_data.get('transcript', 'No transcript available')
        if '[Azure Fast Transcription:' in transcript_text:
            transcript_text = transcript_text.split('[Azure Fast Transcription:')[0].strip()
        
        # Get contact info 
        contact_info = structured_data.get('contact', '')
        
        # Get status
        status_info = structured_data.get('status', 'Processed')
        
        # Get confidence score
        confidence_score = structured_data.get('confidence_score', '')
        
        # Format the row data
        row_data = format_excel_row_impl(
            self, 
            processed_date_display,
            received_date_display, 
            structured_data.get('sender', ''),
            contact_info,
            transcript_text,
            confidence_score,
            voice_url
        )
        
        # Ensure we have exactly 8 values for the 8 columns
        if len(row_data) != 8:
            logging.warning(f"Row data has {len(row_data)} values, expected 8. Padding with empty strings.")
            while len(row_data) < 8:
                row_data.append("")
            row_data = row_data[:8]  # Trim if too many
        
        # Ensure all values are strings (Excel requirement)
        row_data = [str(value) if value is not None else "" for value in row_data]
        
        # Update the row (A{next_row}:H{next_row})
        range_address = f"A{next_row}:H{next_row}"
        
        # Use the worksheet by name with proper URL encoding
        range_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='{range_address}')"
        
        payload = {
            "values": [row_data]
        }
        
        # Debug logging
        logging.info(f"Updating range: {range_address}")
        logging.info(f"Row data length: {len(row_data)}")
        logging.info(f"Range URL: {range_url}")
        
        response = requests.patch(range_url, headers=headers, json=payload)
        
        if response.status_code == 200:
            logging.info(f"Successfully updated Excel file at row {next_row}")
            
            # Apply formatting to the new row
            format_row_impl(self, workbook_url, headers, next_row)
            
            return True
        else:
            logging.error(f"Failed to update Excel file: {response.status_code} {response.text}")
            return False

    except Exception as e:
        logging.error(f"Error updating Excel file: {e}")
        raise


def find_next_row_impl(self, workbook_url, headers):
    """Find the next available row in the horizontal layout"""
    try:
        # Get used range starting from row 2 (after headers) - use worksheet name
        used_range_url = f"{workbook_url}/worksheets/Voice_Emails/usedRange"
        response = requests.get(used_range_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Get row count and add 1 for next row
            row_count = data.get('rowCount', 1)
            next_row = row_count + 1
            # Ensure we're at least on row 2 (after headers)
            return max(next_row, 2)
        else:
            # If no used range found, start at row 2
            return 2
            
    except Exception as e:
        logging.warning(f"Error finding next row: {e}")
        return 2  # Default to row 2 if error


def format_excel_row_impl(self, processed_date, email_received, sender, 
                         contact_info, transcript, confidence_score, audio_url):
    """Format data for a single row in the horizontal layout"""
    # Format dates to user's preferred format: "7/24/25 5:03 PM"
    def format_date(date_str):
        try:
            if isinstance(date_str, str):
                # Parse the ISO format timestamp
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = date_str
            
            # Convert to user's preferred format
            return dt.strftime("%m/%d/%y %I:%M %p")
        except:
            return date_str

    formatted_processed_date = format_date(processed_date)
    formatted_email_received = format_date(email_received)
    
    # Format confidence score as percentage
    confidence_display = "N/A"
    if confidence_score and confidence_score != "N/A":
        try:
            if isinstance(confidence_score, (int, float)):
                confidence_display = f"{confidence_score:.1f}%"
            elif isinstance(confidence_score, str) and confidence_score.replace('.', '').isdigit():
                confidence_display = f"{float(confidence_score):.1f}%"
        except:
            confidence_display = str(confidence_score)
    
    # Create clickable link for audio if URL is valid
    audio_link = "N/A"
    if audio_url and audio_url != "N/A" and audio_url.startswith('http'):
        audio_link = f'=HYPERLINK("{audio_url}", "Listen")'
    
    # Return row data as list
    return [
        formatted_processed_date,
        formatted_email_received,
        sender or "Unknown",
        contact_info or "N/A", 
        transcript or "N/A",
        confidence_display,
        "Processed",
        audio_link
    ]


def format_row_impl(self, workbook_url, headers, row_number):
    """Apply formatting to a specific row"""
    try:
        # Format the data row with alternating colors for better readability
        row_color = "#F8F9FA" if row_number % 2 == 0 else "#FFFFFF"
        
        format_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='A{row_number}:H{row_number}')/format"
        format_payload = {
            "fill": {"color": row_color},
            "borders": {
                "bottom": {"style": "Thin", "color": "#E0E0E0"}
            },
            "alignment": {
                "vertical": "Top",
                "wrapText": True
            }
        }
        requests.patch(format_url, headers=headers, json=format_payload)
        
        # Set row height for better readability
        row_height_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='{row_number}:{row_number}')/format/rows"
        height_payload = {"rowHeight": 60}
        requests.patch(row_height_url, headers=headers, json=height_payload)
        
    except Exception as e:
        logging.warning(f"Error formatting row {row_number}: {e}")


def setup_excel_worksheet_impl(self, workbook_url, headers):
    """Ensure the worksheet exists with horizontal header layout (more efficient)"""
    try:
        # Get all worksheets first to understand what we're working with
        worksheets_url = f"{workbook_url}/worksheets"
        response = requests.get(worksheets_url, headers=headers)
        
        worksheets = []
        if response.status_code == 200:
            worksheets = response.json().get('value', [])
            logging.info(f"Found {len(worksheets)} worksheets")
            for i, sheet in enumerate(worksheets):
                logging.info(f"Worksheet {i}: {sheet.get('name', 'Unknown')}")
        
        # Check if we have any worksheets - if not, the first one will be created
        if len(worksheets) == 0:
            # Create a worksheet
            create_worksheet_url = f"{workbook_url}/worksheets"
            payload = {"name": "Voice_Emails"}
            create_response = requests.post(create_worksheet_url, headers=headers, json=payload)
            if create_response.status_code == 201:
                logging.info("Created Voice_Emails worksheet")
            else:
                logging.warning(f"Failed to create worksheet: {create_response.status_code}")
        else:
            # Rename the first worksheet if it exists
            first_sheet = worksheets[0]
            sheet_id = first_sheet.get('id')
            current_name = first_sheet.get('name', 'Sheet1')
            
            if current_name != 'Voice_Emails':
                # Rename the first sheet
                rename_url = f"{workbook_url}/worksheets/{sheet_id}"
                rename_payload = {"name": "Voice_Emails"}
                rename_response = requests.patch(rename_url, headers=headers, json=rename_payload)
                if rename_response.status_code == 200:
                    logging.info(f"Renamed worksheet from '{current_name}' to 'Voice_Emails'")
                else:
                    logging.warning(f"Failed to rename worksheet: {rename_response.status_code}")
        
        # Set up header row (A1:H1) - use worksheet name without quotes
        header_range_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='A1:H1')"
        header_data = [
            [
                "Processed Date",
                "Email Received", 
                "Sender",
                "Contact",
                "Transcript",
                "Confidence Score",
                "Status",
                "Audio Link"
            ]
        ]
        
        header_payload = {
            "values": header_data
        }
        
        header_response = requests.patch(header_range_url, headers=headers, json=header_payload)
        if header_response.status_code == 200:
            logging.info("Successfully set header row")
        else:
            logging.warning(f"Failed to set headers: {header_response.status_code} {header_response.text}")
        
        # Format header row with better styling
        format_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='A1:H1')/format"
        format_payload = {
            "font": {"bold": True, "color": "#FFFFFF", "size": 12},
            "fill": {"color": "#2F5597"},
            "borders": {
                "bottom": {"style": "Thick", "color": "#FFFFFF"}
            },
            "alignment": {
                "horizontal": "Center",
                "vertical": "Center"
            }
        }
        requests.patch(format_url, headers=headers, json=format_payload)
        
        # Set column widths for optimal display
        column_widths = {
            'A': 25,  # Processed Date
            'B': 25,  # Email Received
            'C': 30,  # Sender
            'D': 20,  # Contact
            'E': 60,  # Transcript (widest)
            'F': 15,  # Confidence Score
            'G': 15,  # Status
            'H': 25   # Audio Link
        }
        
        for col, width in column_widths.items():
            col_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='{col}:{col}')/format/columns"
            width_payload = {"columnWidth": width}
            requests.patch(col_url, headers=headers, json=width_payload)
        
        # Set header row height
        row_height_url = f"{workbook_url}/worksheets/Voice_Emails/range(address='1:1')/format/rows"
        height_payload = {"rowHeight": 45}
        requests.patch(row_height_url, headers=headers, json=height_payload)
        
    except Exception as e:
        logging.warning(f"Error setting up worksheet: {e}")


def find_excel_file_impl(self):
    """Find the Voice Emails Excel file in the user's OneDrive"""
    try:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Search for the Excel file in OneDrive - using /me endpoint
        search_url = "https://graph.microsoft.com/v1.0/me/drive/root/search(q='Scribe.xlsx')"
        response = requests.get(search_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('value', [])
            
            for item in items:
                if item.get('name') == 'Scribe.xlsx':
                    logging.info(f"Found Excel file: {item['id']}")
                    return item['id']
        
        # If not found, create it
        logging.info("Excel file not found, creating new one...")
        return create_excel_file_impl(self)
        
    except Exception as e:
        logging.error(f"Error finding Excel file: {e}")
        return None


def create_excel_file_impl(self):
    """Create a new Excel file for Voice Emails"""
    try:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        # Create Excel file by uploading to specific path
        upload_url = "https://graph.microsoft.com/v1.0/me/drive/root:/Scribe.xlsx:/content"
        
        # Create minimal Excel workbook content
        # This is a basic XLSX file structure
        import io
        import zipfile
        
        # Create a minimal XLSX file in memory
        excel_buffer = io.BytesIO()
        
        with zipfile.ZipFile(excel_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add minimal required files for Excel
            zf.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>''')
            
            zf.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
            
            zf.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')
            
            zf.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
<sheet name="Sheet1" sheetId="1" r:id="rId1"/>
</sheets>
</workbook>''')
            
            zf.writestr('xl/worksheets/sheet1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData/>
</worksheet>''')
        
        excel_content = excel_buffer.getvalue()
        
        response = requests.put(upload_url, headers=headers, data=excel_content)
        
        if response.status_code in [200, 201]:
            data = response.json()
            file_id = data['id']
            logging.info(f"Created new Excel file: {file_id}")
            return file_id
        else:
            logging.error(f"Failed to create Excel file: {response.status_code} {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"Error creating Excel file: {e}")
        return None


def create_excel_via_workbook_api(self, headers):
    """Alternative method to create Excel file using workbook API"""
    try:
        # This function is no longer needed but keeping for compatibility
        return None
            
    except Exception as e:
        logging.error(f"Error creating Excel via workbook API: {e}")
        return None
