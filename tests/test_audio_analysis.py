#!/usr/bin/env python3
"""
Test script to analyze the converted audio file
"""

import requests
import tempfile
import subprocess
import os
import json
from azure.storage.blob import BlobServiceClient

def analyze_converted_audio():
    """Analyze the audio after our conversion process"""
    
    # Load settings
    with open('local.settings.json') as f:
        settings = json.load(f)['Values']
    
    # Parse connection string
    conn_str = settings['AZURE_STORAGE_CONNECTION_STRING']
    account_name = None
    for part in conn_str.split(';'):
        if part.startswith('AccountName='):
            account_name = part.split('=', 1)[1]
            break
    
    if not account_name:
        print("Could not find account name")
        return
    
    # Get blob service client
    blob_client = BlobServiceClient.from_connection_string(conn_str)
    container_client = blob_client.get_container_client('voice-files')
    
    # List blobs
    blobs = list(container_client.list_blobs())
    if not blobs:
        print("No blobs found")
        return
    
    blob_name = blobs[0].name
    blob_url = f"https://{account_name}.blob.core.windows.net/voice-files/{blob_name}"
    print(f"Analyzing blob: {blob_name}")
    
    # Download the original audio
    response = requests.get(blob_url)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.original') as temp_original:
        temp_original.write(response.content)
        original_path = temp_original.name
    
    print(f"Original file size: {len(response.content)} bytes")
    
    # Try the same conversion our function uses
    converted_path = original_path + '.wav'
    
    # Strategy that worked: FFmpeg forced mu-law
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-f', 'mulaw', '-ar', '8000', '-ac', '1', 
        '-i', original_path, '-acodec', 'pcm_s16le', '-ar', '16000', 
        '-ac', '1', '-f', 'wav', converted_path
    ]
    
    print("Running conversion...")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Conversion successful!")
        print(f"Converted file size: {os.path.getsize(converted_path)} bytes")
        
        # Analyze the converted file
        print("\n📊 Analyzing converted audio:")
        
        # Get detailed info with ffprobe
        ffprobe_cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', '-show_streams', converted_path
        ]
        
        probe_result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
        if probe_result.returncode == 0:
            probe_data = json.loads(probe_result.stdout)
            
            if 'streams' in probe_data and probe_data['streams']:
                stream = probe_data['streams'][0]
                print(f"  - Codec: {stream.get('codec_name', 'unknown')}")
                print(f"  - Sample Rate: {stream.get('sample_rate', 'unknown')} Hz")
                print(f"  - Channels: {stream.get('channels', 'unknown')}")
                print(f"  - Duration: {stream.get('duration', 'unknown')} seconds")
                print(f"  - Bit Rate: {stream.get('bit_rate', 'unknown')} bps")
                
                # Calculate expected size
                duration = float(stream.get('duration', 0))
                sample_rate = int(stream.get('sample_rate', 16000))
                channels = int(stream.get('channels', 1))
                expected_samples = duration * sample_rate * channels
                expected_bytes = expected_samples * 2  # 16-bit samples
                print(f"  - Expected audio data: ~{expected_bytes:.0f} bytes")
        
        # Play a sample (if available)
        print("\n🔊 Audio sample analysis:")
        volume_cmd = ['ffmpeg', '-i', converted_path, '-af', 'volumedetect', '-f', 'null', '-']
        vol_result = subprocess.run(volume_cmd, capture_output=True, text=True)
        
        # Look for volume info in stderr
        for line in vol_result.stderr.split('\n'):
            if 'mean_volume' in line or 'max_volume' in line:
                print(f"  {line.strip()}")
        
        # Try to extract a very short sample to listen to
        print("\n💾 Creating test sample...")
        sample_path = converted_path + '_sample.wav'
        sample_cmd = ['ffmpeg', '-y', '-i', converted_path, '-t', '3', '-af', 'volume=2.0', sample_path]
        sample_result = subprocess.run(sample_cmd, capture_output=True, text=True)
        
        if sample_result.returncode == 0:
            print(f"✅ Created 3-second test sample: {sample_path}")
            print(f"   Sample size: {os.path.getsize(sample_path)} bytes")
            print("   You can play this file to test audio quality")
        
        # Cleanup
        os.unlink(converted_path)
        if os.path.exists(sample_path):
            # Keep the sample for manual testing
            print(f"   Sample kept at: {sample_path}")
    else:
        print(f"❌ Conversion failed: {result.stderr}")
    
    # Cleanup
    os.unlink(original_path)

if __name__ == "__main__":
    analyze_converted_audio()
