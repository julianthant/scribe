#!/usr/bin/env python3
"""
Check the voice file that was uploaded to see what format it's in
"""
import requests
import json
from azure.storage.blob import BlobServiceClient

def check_voice_file():
    """Check the uploaded voice file"""
    # Load config
    with open('local.settings.json', 'r') as f:
        settings = json.load(f)
        config = settings.get('Values', {})
    
    # Connect to storage
    connection_string = config['AZURE_STORAGE_CONNECTION_STRING']
    blob_client = BlobServiceClient.from_connection_string(connection_string)
    
    # List files in voice-files container
    container_client = blob_client.get_container_client("voice-files")
    
    print("📁 Files in voice-files container:")
    blobs = container_client.list_blobs()
    for blob in blobs:
        print(f"  - {blob.name}")
        print(f"    Size: {blob.size} bytes")
        print(f"    Content Type: {blob.content_settings.content_type}")
        
        # Download first few bytes to check format
        blob_client_file = container_client.get_blob_client(blob.name)
        sample = blob_client_file.download_blob(offset=0, length=12).readall()
        
        print(f"    Header bytes: {sample.hex()}")
        
        # Check if it's a valid WAV file
        if sample.startswith(b'RIFF') and b'WAVE' in sample:
            print(f"    ✅ Valid WAV file")
        else:
            print(f"    ❌ Not a standard WAV file")
        
        print()

if __name__ == "__main__":
    check_voice_file()
