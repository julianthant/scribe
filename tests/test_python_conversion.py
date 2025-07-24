#!/usr/bin/env python3

"""
Test Python-based mu-law conversion directly.
"""

import requests
import tempfile
import subprocess
import os
import json
import wave
import audioop
import struct
from azure.storage.blob import BlobServiceClient

def test_python_mulaw_conversion():
    """Test converting mu-law to PCM using Python's built-in modules."""
    
    # Load settings
    with open('local.settings.json') as f:
        settings = json.load(f)['Values']
    
    # Connect to storage and get the voice file
    connection_string = settings['AZURE_STORAGE_CONNECTION_STRING']
    blob_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_client.get_container_client('voice-files')
    
    blobs = list(container_client.list_blobs())
    if not blobs:
        print("❌ No voice files found")
        return
    
    latest_blob = max(blobs, key=lambda x: x.last_modified)
    blob_name = latest_blob.name
    blob_url = f"https://scribepersonal20798.blob.core.windows.net/voice-files/{blob_name}"
    
    print(f"🔍 Testing with blob: {blob_name}")
    
    # Download the audio file
    response = requests.get(blob_url)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
        temp_file.write(response.content)
        input_path = temp_file.name
    
    print(f"📥 Downloaded {len(response.content)} bytes")
    
    # Try Python-based conversion
    output_path = 'test_python_converted.wav'
    
    try:
        print("🔄 Attempting Python mu-law conversion...")
        
        # Read as raw data and find the audio data
        with open(input_path, 'rb') as f:
            data = f.read()
        
        print(f"📊 File header: {data[:16].hex()}")
        
        # Look for the data chunk in the WAV file
        if b'RIFF' in data and b'WAVE' in data:
            data_pos = data.find(b'data')
            if data_pos != -1:
                # Skip 'data' header (4 bytes) and get size (4 bytes)
                size_bytes = data[data_pos + 4:data_pos + 8]
                audio_size = struct.unpack('<I', size_bytes)[0]
                
                # Get the actual audio data
                audio_data_start = data_pos + 8
                audio_data = data[audio_data_start:audio_data_start + audio_size]
                
                print(f"🎵 Found audio data: {len(audio_data)} bytes, expected: {audio_size}")
                
                # Convert mu-law to linear PCM
                try:
                    linear_frames = audioop.ulaw2lin(audio_data, 2)
                    print(f"✅ Converted to linear PCM: {len(linear_frames)} bytes")
                    
                    # Create proper WAV file
                    with wave.open(output_path, 'wb') as out_wav:
                        out_wav.setnchannels(1)  # Mono
                        out_wav.setsampwidth(2)  # 16-bit
                        out_wav.setframerate(8000)  # Original rate
                        out_wav.writeframes(linear_frames)
                    
                    print(f"💾 Created WAV file: {output_path}")
                    
                    # Verify with ffprobe
                    probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', output_path]
                    result = subprocess.run(probe_cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        probe_data = json.loads(result.stdout)
                        duration = float(probe_data.get('format', {}).get('duration', 0))
                        print(f"🎧 Converted file duration: {duration:.2f} seconds")
                        
                        if duration > 1.0:
                            print("✅ Success! Conversion preserved the full duration")
                            
                            # Now test if we can upsample to 16kHz for Azure Speech
                            upsampled_path = 'test_python_16khz.wav'
                            
                            # Read the 8kHz data and upsample to 16kHz
                            resampled = audioop.ratecv(linear_frames, 2, 1, 8000, 16000, None)[0]
                            
                            with wave.open(upsampled_path, 'wb') as up_wav:
                                up_wav.setnchannels(1)
                                up_wav.setsampwidth(2)
                                up_wav.setframerate(16000)
                                up_wav.writeframes(resampled)
                            
                            print(f"🚀 Created 16kHz version: {upsampled_path}")
                            
                            # Verify upsampled version
                            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', upsampled_path]
                            result = subprocess.run(probe_cmd, capture_output=True, text=True)
                            
                            if result.returncode == 0:
                                probe_data = json.loads(result.stdout)
                                duration = float(probe_data.get('format', {}).get('duration', 0))
                                print(f"🎯 16kHz file duration: {duration:.2f} seconds")
                                print("🎉 Python-based conversion successful!")
                            
                        else:
                            print(f"❌ Converted file too short: {duration:.3f}s")
                    else:
                        print(f"❌ Could not verify converted file: {result.stderr}")
                        
                except Exception as conv_e:
                    print(f"❌ mu-law conversion failed: {conv_e}")
            else:
                print("❌ Could not find 'data' chunk in WAV file")
        else:
            print("❌ Not a valid WAV file")
            
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
    finally:
        # Cleanup
        if os.path.exists(input_path):
            os.unlink(input_path)

if __name__ == "__main__":
    test_python_mulaw_conversion()
