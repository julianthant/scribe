#!/usr/bin/env python3
"""
Audio File Analyzer and Converter
"""
import requests
import tempfile
import os
from azure.storage.blob import BlobServiceClient
import json

def analyze_audio_file():
    """Download and analyze the audio file to understand the format"""
    # Load config
    with open('local.settings.json', 'r') as f:
        settings = json.load(f)
        config = settings.get('Values', {})
    
    # Connect to storage
    connection_string = config['AZURE_STORAGE_CONNECTION_STRING']
    blob_client = BlobServiceClient.from_connection_string(connection_string)
    
    # Get the voice file
    container_client = blob_client.get_container_client("voice-files")
    blobs = list(container_client.list_blobs())
    
    if not blobs:
        print("No files found in voice-files container")
        return
    
    blob_name = blobs[0].name
    print(f"Analyzing file: {blob_name}")
    
    # Download the file
    blob_client_file = container_client.get_blob_client(blob_name)
    blob_data = blob_client_file.download_blob().readall()
    
    print(f"File size: {len(blob_data)} bytes")
    print(f"First 32 bytes: {blob_data[:32].hex()}")
    
    # Try to identify the format
    if blob_data.startswith(b'RIFF'):
        print("✅ File starts with RIFF header")
        if b'WAVE' in blob_data[:12]:
            print("✅ Contains WAVE signature")
        else:
            print("❌ No WAVE signature found")
            
        # Look for fmt chunk
        if b'fmt ' in blob_data[:100]:
            print("✅ Contains fmt chunk")
        else:
            print("❌ No fmt chunk found")
            
        # Look for data chunk
        if b'data' in blob_data[:200]:
            print("✅ Contains data chunk")
        else:
            print("❌ No data chunk found")
    else:
        print("❌ Not a RIFF file")
        
        # Check for other formats
        if blob_data.startswith(b'ID3') or blob_data[1:4] == b'ID3':
            print("🔍 Appears to be MP3 format")
        elif blob_data.startswith(b'OggS'):
            print("🔍 Appears to be OGG format")
        elif blob_data.startswith(b'fLaC'):
            print("🔍 Appears to be FLAC format")
        else:
            print("🔍 Unknown format")
    
    # Save to temp file and try analysis with ffprobe
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        temp_file.write(blob_data)
        temp_path = temp_file.name
    
    try:
        import subprocess
        result = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', temp_path], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("📊 FFprobe analysis:")
            print(result.stdout)
        else:
            print("❌ FFprobe failed:")
            print(result.stderr)
    except Exception as e:
        print(f"❌ FFprobe error: {e}")
    finally:
        os.unlink(temp_path)

if __name__ == "__main__":
    analyze_audio_file()
