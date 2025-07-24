import azure.functions as func
import logging
import os
import requests
import json
from azure.storage.blob import BlobServiceClient
from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import tempfile
from datetime import datetime, timedelta
import io
import base64
from pydub import AudioSegment
import subprocess
import wave
import audioop
import struct

def main(mytimer: func.TimerRequest) -> None:
    logging.info('Python timer trigger function executed.')
    
    processor = EmailVoiceProcessorWithKeyVault()
    processor.process_emails()

class EmailVoiceProcessorWithKeyVault:
    def __init__(self):
        # Azure credentials and configuration
        self.storage_connection_string = os.environ['AZURE_STORAGE_CONNECTION_STRING']
        self.speech_key = os.environ['SPEECH_SERVICE_KEY']
        self.speech_region = os.environ['SPEECH_SERVICE_REGION']
        self.excel_file_name = os.environ['EXCEL_FILE_NAME']
        self.target_user_email = os.environ.get('TARGET_USER_EMAIL', 'julianthant@outlook.com')
        self.keyvault_url = os.environ.get('KEY_VAULT_URL')
        
        # Initialize clients
        self.blob_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
        
        # Initialize KeyVault client with managed identity
        if self.keyvault_url:
            credential = DefaultAzureCredential()
            self.keyvault_client = SecretClient(vault_url=self.keyvault_url, credential=credential)
            logging.info("KeyVault client initialized")
        else:
            self.keyvault_client = None
            logging.warning("No KeyVault URL provided - using fallback token storage")
        
        # Get access token (with KeyVault support)
        self.access_token = self._get_access_token()
        
    def _get_access_token(self):
        """Get Microsoft Graph API access token with KeyVault backup"""
        try:
            # For local testing, prefer local tokens which we know work
            if os.path.exists('.oauth_tokens.json'):
                return self._get_token_from_file()
                
            # Try to get tokens from KeyVault first (for production)
            if self.keyvault_client:
                return self._get_token_from_keyvault()
            else:
                # Fallback to local file or environment variables
                return self._get_token_from_file()
        except Exception as e:
            logging.error(f"Failed to get access token: {str(e)}")
            return None
    
    def _get_token_from_keyvault(self):
        """Get OAuth tokens from Azure Key Vault"""
        try:
            # Try to get existing access token
            access_token_secret = self.keyvault_client.get_secret("personal-account-access-token")
            access_token = access_token_secret.value
            
            # Check if token is still valid (simplified check)
            if self._is_token_valid(access_token):
                logging.info("Using existing access token from KeyVault")
                return access_token
            
            # Token expired, try to refresh
            logging.info("Access token expired, attempting refresh")
            return self._refresh_token_from_keyvault()
            
        except Exception as e:
            logging.warning(f"Could not get token from KeyVault: {str(e)}")
            # Fall back to refresh token or initial setup
            return self._refresh_token_from_keyvault()
    
    def _refresh_token_from_keyvault(self):
        """Refresh OAuth token using refresh token from KeyVault"""
        try:
            # Get refresh token from KeyVault
            refresh_token_secret = self.keyvault_client.get_secret("personal-account-refresh-token")
            refresh_token = refresh_token_secret.value
            
            client_id_secret = self.keyvault_client.get_secret("personal-account-client-id")
            client_id = client_id_secret.value
            
            client_secret_secret = self.keyvault_client.get_secret("personal-account-client-secret")
            client_secret = client_secret_secret.value
            
            # Refresh the token
            url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
                'scope': 'https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Files.ReadWrite.All https://graph.microsoft.com/User.Read offline_access'
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                new_access_token = token_data.get('access_token')
                new_refresh_token = token_data.get('refresh_token', refresh_token)
                
                # Store new tokens back in KeyVault
                self.keyvault_client.set_secret("personal-account-access-token", new_access_token)
                if new_refresh_token != refresh_token:
                    self.keyvault_client.set_secret("personal-account-refresh-token", new_refresh_token)
                
                logging.info("Successfully refreshed access token")
                return new_access_token
            else:
                logging.error(f"Failed to refresh token: {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error refreshing token from KeyVault: {str(e)}")
            return None
    
    def _get_token_from_file(self):
        """Fallback: Get tokens from local file"""
        try:
            oauth_file = os.path.join(os.path.dirname(__file__), '.oauth_tokens.json')
            if os.path.exists(oauth_file):
                with open(oauth_file, 'r') as f:
                    token_data = json.load(f)
                
                access_token = token_data.get('access_token')
                if self._is_token_valid(access_token):
                    logging.info("Using access token from local file")
                    return access_token
                else:
                    # Try to refresh
                    return self._refresh_token_from_file(token_data)
            else:
                logging.error("No OAuth token file found")
                return None
        except Exception as e:
            logging.error(f"Error reading token from file: {str(e)}")
            return None
    
    def _refresh_token_from_file(self, token_data):
        """Refresh token using data from file"""
        try:
            refresh_token = token_data.get('refresh_token')
            client_id = token_data.get('client_id')
            client_secret = token_data.get('client_secret')
            
            url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
                'scope': 'https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Files.ReadWrite.All https://graph.microsoft.com/User.Read offline_access'
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                new_token_data = response.json()
                new_access_token = new_token_data.get('access_token')
                
                # Update the file with new tokens
                token_data.update(new_token_data)
                oauth_file = os.path.join(os.path.dirname(__file__), '.oauth_tokens.json')
                with open(oauth_file, 'w') as f:
                    json.dump(token_data, f)
                
                logging.info("Successfully refreshed access token from file")
                return new_access_token
            else:
                logging.error(f"Failed to refresh token: {response.text}")
                return None
        except Exception as e:
            logging.error(f"Error refreshing token from file: {str(e)}")
            return None
    
    def _is_token_valid(self, token):
        """Check if access token is still valid"""
        if not token:
            return False
        
        try:
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
            return response.status_code == 200
        except Exception:
            return False
    
    def store_tokens_in_keyvault(self, access_token, refresh_token, client_id, client_secret):
        """Store OAuth tokens in KeyVault (for initial setup)"""
        if not self.keyvault_client:
            logging.error("KeyVault client not available")
            return False
        
        try:
            self.keyvault_client.set_secret("personal-account-access-token", access_token)
            self.keyvault_client.set_secret("personal-account-refresh-token", refresh_token)
            self.keyvault_client.set_secret("personal-account-client-id", client_id)
            self.keyvault_client.set_secret("personal-account-client-secret", client_secret)
            
            logging.info("Successfully stored OAuth tokens in KeyVault")
            return True
        except Exception as e:
            logging.error(f"Failed to store tokens in KeyVault: {str(e)}")
            return False
    
    def process_emails(self):
        """Main processing workflow with folder-based organization"""
        try:
            if not self.access_token:
                logging.error("No access token available")
                return
                
            # Step 1: Get new emails with voice attachments from INBOX only
            emails = self._get_emails_with_voice_attachments()
            
            if not emails:
                logging.info("No voice emails found in inbox - skipping processing")
                return
            
            # Step 2: Process all inbox emails (they're all new since processed ones are moved)
            logging.info(f"Processing {len(emails)} voice emails from inbox")
            
            for email in emails:
                self._process_single_email(email)
                
        except Exception as e:
            logging.error(f"Error in process_emails: {str(e)}")
    
    def _get_emails_with_voice_attachments(self):
        """Fetch emails from inbox only with voice attachments (optimized)"""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Get emails from last 2 hours from INBOX ONLY
        time_filter = (datetime.utcnow() - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Use /me/mailFolders/inbox/messages to only check inbox
        url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
        params = {
            '$filter': f"receivedDateTime ge {time_filter} and hasAttachments eq true",
            '$expand': 'attachments',
            '$select': 'id,subject,receivedDateTime,from,attachments',
            '$orderby': 'receivedDateTime desc',
            '$top': 10
        }
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            logging.error(f"Failed to get inbox emails: {response.text}")
            return []
            
        emails = response.json().get('value', [])
        
        # Filter for voice attachments
        voice_emails = []
        for email in emails:
            voice_attachments = [att for att in email.get('attachments', []) 
                               if self._is_voice_attachment(att)]
            if voice_attachments:
                email['voice_attachments'] = voice_attachments
                voice_emails.append(email)
        
        logging.info(f"Found {len(voice_emails)} voice emails in inbox")
        return voice_emails
    
    def _is_voice_attachment(self, attachment):
        """Check if attachment is a voice file"""
        voice_types = ['.mp3', '.wav', '.m4a', '.ogg', '.aac', '.wma', '.mp4', '.3gp']
        filename = attachment.get('name', '').lower()
        return any(filename.endswith(ext) for ext in voice_types)
    
    def _process_single_email(self, email):
        """Process a single email with voice attachments"""
        try:
            logging.info(f"Processing email: {email['subject']}")
            
            for attachment in email['voice_attachments']:
                # Step 2: Download to blob storage
                blob_url = self._download_attachment_to_blob(email['id'], attachment)
                
                if blob_url:
                    # Step 3: Process with Azure Speech Services
                    transcript = self._transcribe_audio(blob_url)
                    
                    # Step 4: Extract structured data
                    structured_data = self._extract_structured_data(transcript, email, attachment)
                    
                    # Step 5: Update Excel file in OneDrive
                    self._update_excel_file(structured_data)
                    
                    # Step 6: Move email to processed folder
                    self._move_email_to_processed_folder(email['id'])
                    
                    # Cleanup blob
                    self._cleanup_blob(blob_url)
                
        except Exception as e:
            logging.error(f"Error processing email {email['id']}: {str(e)}")
    
    def _download_attachment_to_blob(self, email_id, attachment):
        """Download email attachment to Azure Blob Storage"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            # Get attachment content
            url = f"https://graph.microsoft.com/v1.0/users/{self.target_user_email}/messages/{email_id}/attachments/{attachment['id']}/$value"
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                logging.error(f"Failed to download attachment: {response.text}")
                return None
            
            # Upload to blob storage
            container_name = "voice-files"
            blob_name = f"{email_id}_{attachment['id']}_{attachment['name']}"
            
            # Create container if it doesn't exist
            try:
                container_client = self.blob_client.get_container_client(container_name)
                container_client.create_container()
            except Exception:
                pass  # Container might already exist
            
            blob_client = self.blob_client.get_blob_client(
                container=container_name, 
                blob=blob_name
            )
            
            blob_client.upload_blob(response.content, overwrite=True)
            return blob_client.url
            
        except Exception as e:
            logging.error(f"Error downloading attachment: {str(e)}")
            return None
    
    def _convert_mulaw_to_pcm(self, input_path, output_path):
        """Convert mu-law WAV to PCM WAV using Python's built-in modules."""
        try:
            # First, try to read as a proper WAV file
            try:
                with wave.open(input_path, 'rb') as wav_file:
                    frames = wav_file.readframes(-1)
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    
                    logging.info(f"WAV file info: {sample_rate}Hz, {channels}ch, {sample_width}B sample width, {len(frames)} bytes")
                    
                    # Convert mu-law to linear PCM
                    linear_frames = audioop.ulaw2lin(frames, 2)  # Convert to 16-bit linear
                    
                    # Create output WAV file with proper PCM format
                    with wave.open(output_path, 'wb') as out_wav:
                        out_wav.setnchannels(1)  # Mono
                        out_wav.setsampwidth(2)  # 16-bit
                        out_wav.setframerate(16000)  # 16kHz for Azure Speech
                        
                        # Resample if necessary
                        if sample_rate != 16000:
                            linear_frames = audioop.ratecv(linear_frames, 2, 1, sample_rate, 16000, None)[0]
                        
                        out_wav.writeframes(linear_frames)
                    
                    return True
                    
            except wave.Error as e:
                logging.warning(f"Could not read as standard WAV: {e}")
                
                # If standard WAV reading fails, try raw mu-law extraction
                with open(input_path, 'rb') as f:
                    data = f.read()
                
                # Look for the data chunk in the WAV file
                if b'RIFF' in data and b'WAVE' in data:
                    # Find the data chunk
                    data_pos = data.find(b'data')
                    if data_pos != -1:
                        # Skip 'data' header (4 bytes) and size (4 bytes)
                        audio_data_start = data_pos + 8
                        audio_data = data[audio_data_start:]
                        
                        logging.info(f"Extracted {len(audio_data)} bytes of raw audio data")
                        
                        # Convert mu-law to linear PCM
                        linear_frames = audioop.ulaw2lin(audio_data, 2)
                        
                        # Create proper WAV file
                        with wave.open(output_path, 'wb') as out_wav:
                            out_wav.setnchannels(1)  # Mono
                            out_wav.setsampwidth(2)  # 16-bit
                            out_wav.setframerate(16000)  # 16kHz
                            
                            # If we know original was 8kHz, resample to 16kHz
                            resampled = audioop.ratecv(linear_frames, 2, 1, 8000, 16000, None)[0]
                            out_wav.writeframes(resampled)
                        
                        return True
                
                return False
                
        except Exception as e:
            logging.error(f"Python mu-law conversion failed: {e}")
            return False

    def _transcribe_audio(self, blob_url):
        """Transcribe audio using Azure Speech Services with proper mu-law handling"""
        try:
            # Extract blob name from URL and decode it properly
            from urllib.parse import unquote
            blob_name = unquote(blob_url.split('/')[-1])
            
            logging.info(f"Downloading blob: {blob_name}")
            
            blob_client_obj = self.blob_client.get_blob_client(container="voice-files", blob=blob_name)
            audio_data = blob_client_obj.download_blob().readall()
            
            logging.info(f"Downloaded audio file: {len(audio_data)} bytes")
            
            # Save original audio to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.original') as temp_original:
                temp_original.write(audio_data)
                original_path = temp_original.name
            
            converted_path = None
            
            # Try Python-based mu-law conversion
            try:
                logging.info("Attempting Python-based mu-law to PCM conversion...")
                converted_path = original_path + '_python.wav'
                
                # Parse WAV file and extract mu-law audio data
                if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
                    data_pos = audio_data.find(b'data')
                    if data_pos != -1:
                        # Get audio data size and content
                        size_bytes = audio_data[data_pos + 4:data_pos + 8]
                        audio_size = struct.unpack('<I', size_bytes)[0]
                        audio_data_start = data_pos + 8
                        raw_audio = audio_data[audio_data_start:audio_data_start + audio_size]
                        
                        logging.info(f"Found {len(raw_audio)} bytes of mu-law audio data")
                        
                        # Convert mu-law to linear PCM
                        linear_frames = audioop.ulaw2lin(raw_audio, 2)
                        
                        # Resample from 8kHz to 16kHz for Azure Speech
                        resampled_frames = audioop.ratecv(linear_frames, 2, 1, 8000, 16000, None)[0]
                        
                        # Create proper PCM WAV file
                        with wave.open(converted_path, 'wb') as out_wav:
                            out_wav.setnchannels(1)  # Mono
                            out_wav.setsampwidth(2)  # 16-bit
                            out_wav.setframerate(16000)  # 16kHz for Azure Speech
                            out_wav.writeframes(resampled_frames)
                        
                        # Verify conversion
                        if os.path.exists(converted_path) and os.path.getsize(converted_path) > 1000:
                            probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', converted_path]
                            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                            if probe_result.returncode == 0:
                                probe_data = json.loads(probe_result.stdout)
                                duration = float(probe_data.get('format', {}).get('duration', 0))
                                if duration > 1.0:
                                    logging.info(f"Python conversion successful! Duration: {duration:.2f}s")
                                else:
                                    logging.warning(f"Converted audio too short: {duration:.3f}s")
                                    converted_path = None
                            else:
                                converted_path = None
                        else:
                            converted_path = None
                    else:
                        logging.error("Could not find 'data' chunk in WAV file")
                        converted_path = None
                else:
                    logging.error("Not a valid RIFF WAV file")
                    converted_path = None
                    
            except Exception as e:
                logging.error(f"Python conversion failed: {e}")
                converted_path = None
            
            # If Python conversion failed, try FFmpeg as fallback
            if not converted_path:
                logging.info("Trying FFmpeg conversion as fallback...")
                try:
                    converted_path = original_path + '_ffmpeg.wav'
                    ffmpeg_cmd = [
                        'ffmpeg', '-y', '-i', original_path,
                        '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', '-f', 'wav',
                        converted_path
                    ]
                    
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                    if result.returncode != 0 or not os.path.exists(converted_path) or os.path.getsize(converted_path) < 1000:
                        logging.error(f"FFmpeg conversion failed: {result.stderr}")
                        converted_path = None
                except Exception as e:
                    logging.error(f"FFmpeg conversion error: {e}")
                    converted_path = None
            
            # If all conversions failed, return error
            if not converted_path:
                logging.warning("All audio conversion strategies failed")
                return "[Audio format not supported - conversion failed. File saved for manual review.]"
            
            # Configure speech service for transcription
            speech_config = SpeechConfig(
                subscription=self.speech_key, 
                region=self.speech_region
            )
            speech_config.speech_recognition_language = "en-US"
            
            # Try transcription with the converted file using continuous recognition
            try:
                logging.info("Starting continuous speech recognition...")
                audio_input = AudioConfig(filename=converted_path)
                speech_recognizer = SpeechRecognizer(
                    speech_config=speech_config, 
                    audio_config=audio_input
                )
                
                # Use continuous recognition for longer audio files
                all_text = []
                recognition_done = False
                
                def recognized_cb(evt):
                    if evt.result.text:
                        logging.info(f"Recognized: {evt.result.text}")
                        all_text.append(evt.result.text)
                
                def session_stopped_cb(evt):
                    nonlocal recognition_done
                    logging.info("Session stopped")
                    recognition_done = True
                
                def canceled_cb(evt):
                    nonlocal recognition_done
                    logging.info(f"Recognition canceled: {evt.reason}")
                    recognition_done = True
                
                # Connect callbacks
                speech_recognizer.recognized.connect(recognized_cb)
                speech_recognizer.session_stopped.connect(session_stopped_cb)
                speech_recognizer.canceled.connect(canceled_cb)
                
                # Start continuous recognition
                speech_recognizer.start_continuous_recognition()
                
                # Wait for recognition to complete (with timeout)
                import time
                timeout = 60  # 60 seconds timeout
                start_time = time.time()
                
                while not recognition_done and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                speech_recognizer.stop_continuous_recognition()
                
                # Combine all recognized text
                if all_text:
                    transcription = " ".join(all_text)
                    logging.info(f"Continuous transcription successful: {len(transcription)} characters")
                else:
                    # Fallback to single recognition if continuous failed
                    logging.info("Continuous recognition got no results, trying single recognition...")
                    result = speech_recognizer.recognize_once()
                    
                    if result.reason.name == 'RecognizedSpeech':
                        transcription = result.text
                        logging.info(f"Single recognition successful: {len(transcription)} characters")
                    else:
                        transcription = "[No speech detected in audio file]"
                        logging.warning(f"Single recognition also failed: {result.reason}")
                    
            except Exception as e:
                logging.error(f"Speech recognition error: {e}")
                transcription = f"[Recognition error: {str(e)}]"
            
            # Cleanup temp files
            try:
                if os.path.exists(original_path):
                    os.unlink(original_path)
                if converted_path and os.path.exists(converted_path):
                    os.unlink(converted_path)
            except Exception as cleanup_e:
                logging.warning(f"Cleanup error: {cleanup_e}")
            
            return transcription
                
        except Exception as e:
            logging.error(f"Error in transcription: {str(e)}")
            return f"[Error: {str(e)}]"
            
            # Configure speech service with more robust settings
            speech_config = SpeechConfig(
                subscription=self.speech_key, 
                region=self.speech_region
            )
            
            # Try multiple language configurations
            languages_to_try = ["en-US", "en-GB", "en-AU", "en-CA"]
            
            for language in languages_to_try:
                try:
                    logging.info(f"Trying speech recognition with language: {language}")
                    speech_config.speech_recognition_language = language
                    
                    # Enable profanity filter and other options
                    speech_config.enable_audio_logging = True
                    speech_config.request_word_level_timestamps = True
                    
                    audio_input = AudioConfig(filename=converted_path)
                    speech_recognizer = SpeechRecognizer(
                        speech_config=speech_config, 
                        audio_config=audio_input
                    )
                    
                    result = speech_recognizer.recognize_once()
                    
                    if result.reason.name == 'RecognizedSpeech' and result.text.strip():
                        logging.info(f"Transcription successful with {language}: {len(result.text)} characters")
                        break
                    elif result.reason.name == 'NoMatch':
                        logging.info(f"No speech recognized with {language}")
                        continue
                    else:
                        logging.warning(f"Recognition failed with {language}: {result.reason}")
                        continue
                        
                except Exception as lang_e:
                    logging.error(f"Error with language {language}: {lang_e}")
                    continue
            
            # If direct file approach failed, try stream-based approach with best language
            if not (hasattr(result, 'reason') and result.reason.name == 'RecognizedSpeech' and result.text.strip()):
                try:
                    logging.info("Trying stream-based recognition as fallback...")
                    with open(converted_path, 'rb') as audio_file:
                        audio_data = audio_file.read()
                    
                    import azure.cognitiveservices.speech as speechsdk
                    stream = speechsdk.audio.PushAudioInputStream()
                    audio_config = speechsdk.audio.AudioConfig(stream=stream)
                    
                    # Reset to English for stream approach
                    speech_config.speech_recognition_language = "en-US"
                    speech_recognizer = speechsdk.SpeechRecognizer(
                        speech_config=speech_config, 
                        audio_config=audio_config
                    )
                    
                    stream.write(audio_data)
                    stream.close()
                    
                    result = speech_recognizer.recognize_once()
                    
                except Exception as stream_e:
                    logging.error(f"Stream-based recognition also failed: {stream_e}")
                    # If we still have no result, create a placeholder
                    if not hasattr(result, 'reason'):
                        result = type('obj', (object,), {
                            'reason': type('obj', (object,), {'name': 'Error'}),
                            'text': f"[Audio format not supported: {'; '.join(conversion_attempts[:2])}]"
                        })            # Cleanup temp files
            if os.path.exists(original_path):
                os.unlink(original_path)
            if converted_path and os.path.exists(converted_path) and converted_path != original_path:
                os.unlink(converted_path)
            
            if result.reason.name == 'RecognizedSpeech':
                logging.info(f"Transcription successful: {len(result.text)} characters")
                return result.text
            else:
                logging.error(f"Speech recognition failed: {result.reason}")
                return f"[Transcription failed: {result.reason}]"
                
        except Exception as e:
            logging.error(f"Error in transcription: {str(e)}")
            return f"[Error: {str(e)}]"
    
    def _extract_structured_data(self, transcript, email, attachment):
        """Extract structured data from transcript"""
        
        # Get audio duration info if available
        duration_info = f"{attachment.get('size', 0)} bytes"
        
        # Check if we have a meaningful transcript
        if transcript and not transcript.startswith('['):
            status = 'Processed'
            transcript_display = transcript
        elif 'NoMatch' in str(transcript):
            status = 'Audio too short or no speech detected'
            transcript_display = '[Very short audio clip - likely notification sound]'
        elif 'Error' in str(transcript):
            status = 'Processing failed'
            transcript_display = transcript
        else:
            status = 'No transcript available'
            transcript_display = '[No transcript available]'
        
        data = {
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'sender': email['from']['emailAddress']['address'],
            'subject': email['subject'] or '[No subject]',
            'transcript': transcript_display,
            'duration': duration_info,
            'status': status
        }
        
        return data
    
    def _update_excel_file(self, data):
        """Update Excel file in OneDrive"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # First, find the Excel file
            excel_file_id = self._find_excel_file()
            if not excel_file_id:
                logging.error("Could not find Excel file")
                return
            
            # Get the workbook and worksheet - use /me endpoint
            workbook_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{excel_file_id}/workbook"
            
            # Find the next empty row by getting used range
            used_range_url = f"{workbook_url}/worksheets('Voice_Emails')/usedRange"
            range_response = requests.get(used_range_url, headers=headers)
            
            next_row = 2  # Default to row 2 (after header)
            if range_response.status_code == 200:
                used_range = range_response.json()
                row_count = used_range.get('rowCount', 1)
                next_row = row_count + 1
            
            # Add row to the worksheet using proper range API
            range_address = f"A{next_row}:F{next_row}"
            range_url = f"{workbook_url}/worksheets('Voice_Emails')/range(address='{range_address}')"
            
            # Prepare row data
            row_data = [
                data['timestamp'],
                data['sender'],
                data['subject'],
                data['transcript'][:500] if data['transcript'] else '[No transcription]',  # Truncate if too long
                data.get('duration', 'Unknown'),
                data['status']
            ]
            
            # Insert the row
            payload = {
                "values": [row_data]
            }
            
            response = requests.patch(range_url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logging.info(f"Successfully added row to Excel file at row {next_row}")
            else:
                logging.error(f"Failed to update Excel: {response.status_code} - {response.text}")
                
        except Exception as e:
            logging.error(f"Error updating Excel file: {str(e)}")
    
    def _find_excel_file(self):
        """Find the Excel file in OneDrive"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            # Use direct access first (more reliable than search)
            direct_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{self.excel_file_name}"
            response = requests.get(direct_url, headers=headers)
            
            if response.status_code == 200:
                file_info = response.json()
                logging.info(f"Found Excel file: {file_info['id']}")
                return file_info['id']
            
            # Fallback to search
            search_url = f"https://graph.microsoft.com/v1.0/me/drive/search(q='{self.excel_file_name}')"
            response = requests.get(search_url, headers=headers)
            
            if response.status_code == 200:
                files = response.json().get('value', [])
                for file in files:
                    if file['name'] == self.excel_file_name:
                        logging.info(f"Found Excel file via search: {file['id']}")
                        return file['id']
            
            logging.error(f"Excel file '{self.excel_file_name}' not found")
            return None
            
        except Exception as e:
            logging.error(f"Error finding Excel file: {str(e)}")
            return None
    
    def _move_email_to_processed_folder(self, email_id):
        """Move processed email to a 'Voice Messages Processed' folder"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # First, ensure the processed folder exists
            processed_folder_id = self._get_or_create_processed_folder()
            if not processed_folder_id:
                logging.warning("Could not create processed folder - email will remain in inbox")
                return False
            
            # Move the email to the processed folder
            move_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/move"
            payload = {
                "destinationId": processed_folder_id
            }
            
            response = requests.post(move_url, headers=headers, json=payload)
            
            if response.status_code in [200, 201]:
                logging.info(f"Successfully moved email to processed folder")
                return True
            else:
                logging.warning(f"Failed to move email: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Error moving email to processed folder: {e}")
            return False
    
    def _get_or_create_processed_folder(self):
        """Get or create 'Voice Messages Processed' folder"""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            folder_name = "Voice Messages Processed"
            
            # First, check if folder already exists
            folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
            response = requests.get(folders_url, headers=headers)
            
            if response.status_code == 200:
                folders = response.json().get('value', [])
                for folder in folders:
                    if folder['displayName'] == folder_name:
                        logging.info(f"Found existing processed folder: {folder['id']}")
                        return folder['id']
            
            # Folder doesn't exist, create it
            logging.info(f"Creating new folder: {folder_name}")
            create_payload = {
                "displayName": folder_name
            }
            
            response = requests.post(folders_url, headers=headers, json=create_payload)
            
            if response.status_code in [200, 201]:
                folder_data = response.json()
                folder_id = folder_data['id']
                logging.info(f"Successfully created processed folder: {folder_id}")
                return folder_id
            else:
                logging.error(f"Failed to create processed folder: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error getting/creating processed folder: {e}")
            return None
    
    def _cleanup_blob(self, blob_url):
        """Remove temporary blob file"""
        try:
            blob_name = blob_url.split('/')[-1]
            blob_client = self.blob_client.get_blob_client(
                container="voice-files", 
                blob=blob_name
            )
            blob_client.delete_blob()
            logging.info("Cleaned up temporary blob file")
        except Exception as e:
            logging.error(f"Error cleaning up blob: {str(e)}")
