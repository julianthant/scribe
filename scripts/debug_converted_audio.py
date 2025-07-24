#!/usr/bin/env python3

"""
Debug script to save the converted audio file for manual inspection.
This helps us understand what Azure Speech Service is actually receiving.
"""

import requests
import tempfile
import subprocess
import os
import json
from azure.storage.blob import BlobServiceClient

def debug_audio_conversion():
    """Download and convert the voice message, then save for manual inspection."""
    
    # Load settings
    with open('local.settings.json') as f:
        settings = json.load(f)['Values']
    
    # Connect to storage
    connection_string = settings['AZURE_STORAGE_CONNECTION_STRING']
    blob_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_client.get_container_client('voice-files')
    
    # Find the latest blob
    blobs = list(container_client.list_blobs())
    if not blobs:
        print("❌ No voice files found in storage")
        return
    
    # Get the latest blob
    latest_blob = max(blobs, key=lambda x: x.last_modified)
    blob_name = latest_blob.name
    blob_url = f"https://scribepersonal20798.blob.core.windows.net/voice-files/{blob_name}"
    
    print(f"🔍 Analyzing blob: {blob_name}")
    print(f"📊 Size: {latest_blob.size} bytes")
    print(f"📅 Modified: {latest_blob.last_modified}")
    
    # Download the original audio
    response = requests.get(blob_url)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.original') as temp_original:
        temp_original.write(response.content)
        original_path = temp_original.name
    
    print(f"💾 Downloaded original to: {original_path}")
    
    # Convert using the same strategy that worked
    converted_path = original_path + '.wav'
    
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'mulaw', '-ar', '8000', '-ac', '1', '-i', original_path,
        '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-f', 'wav',
        converted_path
    ]
    
    print("🔄 Converting audio using FFmpeg forced mu-law strategy...")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Conversion successful!")
        
        # Save to current directory for inspection
        output_file = "debug_converted_voice.wav"
        os.rename(converted_path, output_file)
        
        print(f"🎵 Converted audio saved as: {output_file}")
        print(f"📊 File size: {os.path.getsize(output_file)} bytes")
        
        # Analyze the converted file
        print("\n🔍 Analyzing converted audio:")
        os.system(f"ffprobe -v quiet -print_format json -show_format -show_streams {output_file}")
        
        print(f"\n✅ You can now listen to '{output_file}' to hear what Azure Speech Service is processing")
        print("🎧 If you can understand speech in this file, then the issue might be with Azure Speech Service configuration")
        print("🤔 If the audio is unclear/silent/corrupted, then we need to improve the conversion process")
        
    else:
        print(f"❌ Conversion failed: {result.stderr}")
    
    # Cleanup
    if os.path.exists(original_path):
        os.unlink(original_path)

if __name__ == "__main__":
    debug_audio_conversion()
