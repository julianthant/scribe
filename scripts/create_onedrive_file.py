#!/usr/bin/env python3
"""
Create and upload the Scribe.xlsx file to OneDrive
"""
import json
import requests
import pandas as pd
import io

def load_oauth_tokens():
    """Load OAuth tokens"""
    try:
        with open('.oauth_tokens.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ No OAuth tokens found")
        return None

def create_excel_file():
    """Create a basic Excel file structure for the Scribe app"""
    # Create a simple DataFrame with the expected structure
    data = {
        'Date': [],
        'From': [],
        'Subject': [],
        'Transcription': [],
        'Voice_File_URL': [],
        'Processed_Date': []
    }
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Voice_Emails', index=False)
    
    excel_buffer.seek(0)
    return excel_buffer.getvalue()

def upload_to_onedrive(file_content, filename):
    """Upload file to OneDrive"""
    oauth_tokens = load_oauth_tokens()
    if not oauth_tokens:
        return False
    
    headers = {
        'Authorization': f'Bearer {oauth_tokens["access_token"]}',
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    
    # Upload to OneDrive root
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{filename}:/content"
    
    print(f"📤 Uploading {filename} to OneDrive...")
    response = requests.put(url, headers=headers, data=file_content)
    
    if response.status_code in [200, 201]:
        print(f"✅ {filename} uploaded successfully to OneDrive")
        file_info = response.json()
        print(f"   File ID: {file_info.get('id')}")
        print(f"   Web URL: {file_info.get('webUrl')}")
        return True
    else:
        print(f"❌ Upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def main():
    print("📁 Creating and uploading Scribe.xlsx to OneDrive...")
    
    # Create Excel file
    excel_content = create_excel_file()
    print("✅ Excel file created in memory")
    
    # Upload to OneDrive
    success = upload_to_onedrive(excel_content, "Scribe.xlsx")
    
    if success:
        print("\n🎉 Scribe.xlsx is now available in OneDrive!")
        print("Run the comprehensive test again to verify.")
    else:
        print("\n💥 Failed to upload file to OneDrive.")

if __name__ == "__main__":
    main()
