"""
Azure AI Foundry Audio Processor Functions
Function implementations for Azure Foundry audio processing
"""

import logging
import os
import json
import time
import threading
import wave
import requests
from azure.cognitiveservices.speech import SpeechConfig, AudioConfig, SpeechRecognizer, OutputFormat
from azure.cognitiveservices.speech import PropertyId, ResultReason, CancellationReason


def transcribe_local_audio_impl(processor, local_file_path):
    """Implementation for transcribing local audio files"""
    try:
        # Get audio duration for metrics
        audio_duration = processor._get_audio_duration(local_file_path)
        
        # Use Fast Transcription API
        start_time = time.time()
        result = processor._perform_fast_transcription(local_file_path, audio_duration)
        processing_time = time.time() - start_time
        
        # Process and return result 
        return processor._process_fast_transcription_result(result, processing_time, audio_duration)
        
    except Exception as e:
        logging.error(f"Fast transcription failed, attempting fallback: {str(e)}")
        # Fallback to Speech SDK if Fast Transcription fails
        return processor._fallback_to_speech_sdk(local_file_path, audio_duration)


def transcribe_audio_impl(processor, blob_url_or_path):
    """Implementation for transcribing audio from blob URL or local path"""
    try:
        import tempfile
        import os
        from azure.storage.blob import BlobServiceClient
        from urllib.parse import urlparse, unquote
        
        # If it's a local path, use transcribe_local_audio
        if not blob_url_or_path.startswith('http'):
            return transcribe_local_audio_impl(processor, blob_url_or_path)
        
        # Parse URL properly to avoid double encoding issues
        parsed_url = urlparse(blob_url_or_path)
        path_parts = parsed_url.path.strip('/').split('/')
        container_name = path_parts[0]  # voice-files
        blob_name = '/'.join(path_parts[1:])  # everything after container
        
        # URL decode the blob name to handle special characters
        blob_name = unquote(blob_name)
        
        logging.info(f"Attempting to download blob: container='{container_name}', blob='{blob_name}'")
        
        # Use the processor's blob_client if available
        if processor.blob_client:
            blob_client = processor.blob_client.get_blob_client(container=container_name, blob=blob_name)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_path = temp_file.name
            
            # Download blob to temporary file using authenticated access
            with open(temp_path, 'wb') as temp_file:
                download_stream = blob_client.download_blob()
                temp_file.write(download_stream.readall())
            
            try:
                # Transcribe the temporary file
                result = transcribe_local_audio_impl(processor, temp_path)
                return result
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            # Fallback to HTTP request (will fail if blob is private)
            import requests
            
            response = requests.get(blob_url_or_path, timeout=60)
            response.raise_for_status()
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
            
            try:
                # Transcribe the temporary file
                result = transcribe_local_audio_impl(processor, temp_path)
                return result
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                
    except Exception as e:
        logging.error(f"Error transcribing audio from blob URL: {str(e)}")
        raise


def transcribe_local_audio_impl(processor, local_file_path):
    """Transcribe audio from local file using Azure AI Foundry Speech Services"""
    try:
        logging.info(f"Starting Azure Foundry transcription for: {local_file_path}")
        
        # Check if file exists
        if not os.path.exists(local_file_path):
            logging.error(f"Audio file not found: {local_file_path}")
            return "[Audio file not found]"
        
        # Get audio duration for optimal processing strategy
        audio_duration = get_audio_duration_impl(processor, local_file_path)
        logging.info(f"Audio duration: {audio_duration:.2f} seconds")
        
        # Use Azure Foundry Fast Transcription API directly on original file
        transcription = perform_fast_transcription_impl(processor, local_file_path, audio_duration)
        
        return transcription
        
    except Exception as e:
        logging.error(f"Error in Azure Foundry transcription: {str(e)}")
        return f"[Azure Foundry Error: {str(e)}]"


def get_audio_duration_impl(processor, file_path):
    """Get audio file duration in seconds"""
    try:
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            framerate = wav_file.getframerate()
            duration = frames / framerate
            return duration
    except Exception as e:
        logging.warning(f"Could not get audio duration: {e}")
        # Fallback: estimate based on file size
        try:
            file_size = os.path.getsize(file_path)
            estimated_duration = max(1.0, file_size / 32000)  # Rough estimate
            return estimated_duration
        except:
            return 30.0  # Default assumption


def perform_fast_transcription_impl(processor, audio_file_path, audio_duration):
    """Perform Fast Transcription using Azure AI Foundry Fast Transcription API"""
    try:
        logging.info(f"Starting Azure Foundry Fast Transcription API for {audio_duration:.2f}s audio")
        
        # API key authentication headers
        headers = {
            'Ocp-Apim-Subscription-Key': processor.speech_key
        }
        
        # Prepare form data for Fast Transcription API
        files = {
            'audio': (os.path.basename(audio_file_path), open(audio_file_path, 'rb'), 'audio/wav')
        }
        
        # Fast Transcription API form definition
        definition = {
            "locales": ["en-US"],
            "profanityFilterMode": "Masked",
            "channels": [0]  # Process first channel
        }
        
        form_data = {
            'definition': json.dumps(definition)
        }
        
        logging.info("Sending request to Fast Transcription API...")
        start_time = time.time()
        
        # Make Fast Transcription API request with multipart/form-data
        response = requests.post(
            processor.fast_transcription_endpoint,
            headers=headers,
            files=files,
            data=form_data,
            timeout=120  # 2 minute timeout for long audio
        )
        
        processing_time = time.time() - start_time
        logging.info(f"Fast Transcription API response received in {processing_time:.2f} seconds")
        
        # Close the file
        files['audio'][1].close()
        
        if response.status_code == 200:
            result = response.json()
            return process_fast_transcription_result_impl(processor, result, processing_time, audio_duration)
        else:
            error_msg = f"Fast Transcription API error: {response.status_code} - {response.text}"
            logging.error(error_msg)
            
            # Fallback to regular Speech SDK if Fast Transcription fails
            logging.info("Falling back to regular Speech SDK...")
            return fallback_to_speech_sdk_impl(processor, audio_file_path, audio_duration)
            
    except requests.exceptions.Timeout:
        logging.error("Fast Transcription API timeout")
        return "[Fast Transcription API timeout - try with shorter audio]"
    except Exception as e:
        logging.error(f"Fast Transcription API error: {e}")
        # Fallback to regular Speech SDK
        logging.info("Falling back to regular Speech SDK due to error...")
        return fallback_to_speech_sdk_impl(processor, audio_file_path, audio_duration)


def process_fast_transcription_result_impl(processor, result, processing_time, audio_duration):
    """Process Fast Transcription API response"""
    try:
        # Extract transcription from Fast Transcription result
        if 'combinedPhrases' in result and result['combinedPhrases']:
            combined_phrases = result['combinedPhrases']
            
            # Get the transcript directly from combinedPhrases
            if len(combined_phrases) > 0 and 'text' in combined_phrases[0]:
                transcript = combined_phrases[0]['text'].strip()
                
                if transcript:
                    # Calculate speed ratio (faster than real-time indicator)
                    speed_ratio = audio_duration / processing_time if processing_time > 0 else 1.0
                    
                    # Get character count and duration info
                    char_count = len(transcript)
                    duration_seconds = result.get('durationMilliseconds', 0) / 1000 if 'durationMilliseconds' in result else audio_duration
                    
                    logging.info(f"Fast Transcription successful: {char_count} characters, "
                               f"duration: {duration_seconds:.1f}s, speed: {speed_ratio:.1f}x faster than real-time")
                    
                    return f"{transcript} [Azure Fast Transcription: {speed_ratio:.1f}x speed, {duration_seconds:.1f}s]"
        
        # Fallback: check individual phrases if combinedPhrases doesn't have direct text
        if 'phrases' in result:
            phrases = result['phrases']
            transcript_parts = []
            confidence_scores = []
            
            for phrase in phrases:
                if 'text' in phrase and phrase['text'].strip():
                    transcript_parts.append(phrase['text'])
                    
                    # Extract confidence if available
                    if 'confidence' in phrase:
                        confidence_scores.append(phrase['confidence'])
            
            if transcript_parts:
                full_transcript = ' '.join(transcript_parts)
                avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.8
                speed_ratio = audio_duration / processing_time if processing_time > 0 else 1.0
                
                # Store confidence score in processor for later access
                processor._last_confidence_score = avg_confidence * 100  # Convert to percentage
                
                logging.info(f"Fast Transcription successful: {len(transcript_parts)} phrases, "
                           f"confidence: {avg_confidence:.2f}, speed: {speed_ratio:.1f}x faster than real-time")
                
                return f"{full_transcript} [Azure Fast Transcription: {avg_confidence:.1%}, {speed_ratio:.1f}x speed]"
        
        # No transcription found
        logging.warning("Fast Transcription API returned no recognizable speech")
        return "[Fast Transcription: No speech recognized]"
        
    except Exception as e:
        logging.error(f"Error processing Fast Transcription result: {e}")
        return f"[Fast Transcription result processing error: {e}]"


def fallback_to_speech_sdk_impl(processor, audio_file_path, audio_duration):
    """Fallback to regular Speech SDK if Fast Transcription fails"""
    try:
        logging.info("Using Speech SDK fallback...")
        
        # Configure Speech SDK
        speech_config = SpeechConfig(subscription=processor.speech_key, region=processor.speech_region)
        speech_config.speech_recognition_language = "en-US"
        speech_config.output_format = OutputFormat.Detailed
        speech_config.request_word_level_timestamps()
        speech_config.enable_dictation()
        
        # Enhanced settings for better recognition
        speech_config.set_property(PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "30000")
        speech_config.set_property(PropertyId.Speech_SegmentationSilenceTimeoutMs, "8000")
        
        audio_config = AudioConfig(filename=audio_file_path)
        speech_recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        
        if audio_duration > 30:
            # Use continuous recognition for longer audio
            return perform_continuous_fallback_impl(processor, speech_recognizer, audio_duration)
        else:
            # Use single recognition for shorter audio
            result = speech_recognizer.recognize_once()
            if result.reason == ResultReason.RecognizedSpeech:
                confidence = extract_confidence_impl(processor, result)
                processor._last_confidence_score = confidence * 100  # Store for later access
                return f"{result.text.strip()} [SDK Fallback: {confidence:.1%}]"
            else:
                return "[SDK Fallback: No speech recognized]"
                
    except Exception as e:
        logging.error(f"Speech SDK fallback error: {e}")
        return f"[Speech SDK fallback error: {e}]"


def perform_continuous_fallback_impl(processor, speech_recognizer, audio_duration):
    """Continuous recognition fallback for longer audio"""
    try:
        recognized_texts = []
        recognition_complete = threading.Event()
        
        def recognized_handler(evt):
            if evt.result.reason == ResultReason.RecognizedSpeech:
                text = evt.result.text.strip()
                if text:
                    recognized_texts.append(text)
                    logging.info(f"SDK Fallback segment: '{text[:50]}...'")
        
        def session_stopped_handler(evt):
            recognition_complete.set()
        
        speech_recognizer.recognized.connect(recognized_handler)
        speech_recognizer.session_stopped.connect(session_stopped_handler)
        
        speech_recognizer.start_continuous_recognition()
        
        # Wait with timeout
        timeout = min(120, max(30, audio_duration * 1.5))
        recognition_complete.wait(timeout=timeout)
        
        speech_recognizer.stop_continuous_recognition()
        
        if recognized_texts:
            combined_text = ' '.join(recognized_texts)
            return f"{combined_text} [SDK Continuous Fallback: {len(recognized_texts)} segments]"
        else:
            return "[SDK Continuous Fallback: No speech recognized]"
            
    except Exception as e:
        logging.error(f"Continuous fallback error: {e}")
        return f"[Continuous fallback error: {e}]"


def extract_confidence_impl(processor, result):
    """Extract confidence score from recognition result"""
    try:
        # Try to get detailed confidence
        if hasattr(result, 'properties'):
            json_result = result.properties.get("SPEECH-SpeechServiceResponse_JsonResult", "")
            if json_result:
                try:
                    parsed_result = json.loads(json_result)
                    if 'NBest' in parsed_result and len(parsed_result['NBest']) > 0:
                        best_result = parsed_result['NBest'][0]
                        if 'Confidence' in best_result:
                            return float(best_result['Confidence'])
                except json.JSONDecodeError:
                    pass
        
        # Fallback confidence estimation
        text = result.text.strip() if hasattr(result, 'text') else ""
        if not text:
            return 0.0
        
        words = text.split()
        word_count = len(words)
        
        # Quality-based confidence estimation
        if word_count >= 10:
            base_confidence = 0.85
        elif word_count >= 5:
            base_confidence = 0.75
        elif word_count >= 3:
            base_confidence = 0.65
        else:
            base_confidence = 0.55
        
        # Boost for proper capitalization and punctuation
        if text[0].isupper():
            base_confidence += 0.05
        if any(punct in text for punct in '.!?'):
            base_confidence += 0.05
        
        return max(0.1, min(base_confidence, 0.95))
        
    except Exception as e:
        logging.warning(f"Confidence extraction error: {e}")
        return 0.7  # Default confidence


def create_foundry_audio_processor(speech_key, speech_region, blob_client=None, foundry_endpoint=None):
    """Factory function to create Azure Foundry Audio Processor"""
    try:
        from .azure_foundry_processor_class import AzureFoundryAudioProcessor
    except ImportError:
        # Fallback for when running tests or standalone
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from azure_foundry_processor_class import AzureFoundryAudioProcessor
    
    return AzureFoundryAudioProcessor(
        speech_key=speech_key,
        speech_region=speech_region, 
        blob_client=blob_client,
        foundry_endpoint=foundry_endpoint
    )


def test_foundry_transcription(voice_file_path, speech_key, speech_region, foundry_endpoint=None):
    """Test function for transcribing audio files with Azure Foundry"""
    try:
        logging.basicConfig(level=logging.INFO)
        
        # Create processor
        processor = create_foundry_audio_processor(
            speech_key=speech_key,
            speech_region=speech_region,
            blob_client=None,  # Not needed for local file
            foundry_endpoint=foundry_endpoint
        )
        
        logging.info(f"Testing Azure Foundry transcription with: {voice_file_path}")
        
        # Test transcription
        transcription = processor.transcribe_local_audio(voice_file_path)
        
        print(f"\n🎤 Azure AI Foundry Fast Transcription Result:")
        print(f"File: {voice_file_path}")
        print(f"Result: {transcription}")
        
        return transcription
        
    except Exception as e:
        logging.error(f"Test failed: {e}")
        return f"Test failed: {e}"


def process_audio_file(file_path, speech_key, speech_region, foundry_endpoint=None):
    """Simple function to process a single audio file"""
    processor = create_foundry_audio_processor(speech_key, speech_region, foundry_endpoint=foundry_endpoint)
    return processor.transcribe_local_audio(file_path)


def batch_process_audio_files(file_paths, speech_key, speech_region, foundry_endpoint=None):
    """Process multiple audio files and return results"""
    processor = create_foundry_audio_processor(speech_key, speech_region, foundry_endpoint=foundry_endpoint)
    results = {}
    
    for file_path in file_paths:
        try:
            result = processor.transcribe_local_audio(file_path)
            results[file_path] = result
            logging.info(f"Processed {file_path}: {len(result)} characters")
        except Exception as e:
            results[file_path] = f"Error: {e}"
            logging.error(f"Failed to process {file_path}: {e}")
    
    return results


def validate_audio_file(file_path):
    """Validate if audio file exists and is accessible"""
    import os
    
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    if not os.path.isfile(file_path):
        return False, "Path is not a file"
    
    if os.path.getsize(file_path) == 0:
        return False, "File is empty"
    
    # Check file extension
    valid_extensions = ['.wav', '.mp3', '.m4a', '.ogg', '.flac']
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in valid_extensions:
        return False, f"Unsupported file extension: {file_ext}"
    
    return True, "File is valid"


def get_audio_file_info(file_path):
    """Get basic information about an audio file"""
    import os
    import wave
    
    info = {
        'path': file_path,
        'size_bytes': 0,
        'duration_seconds': 0,
        'format': 'unknown'
    }
    
    try:
        info['size_bytes'] = os.path.getsize(file_path)
        info['format'] = os.path.splitext(file_path)[1].lower()
        
        # Try to get duration for WAV files
        if info['format'] == '.wav':
            try:
                with wave.open(file_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    framerate = wav_file.getframerate()
                    info['duration_seconds'] = frames / framerate
                    info['sample_rate'] = framerate
                    info['channels'] = wav_file.getnchannels()
            except Exception as e:
                logging.warning(f"Could not read WAV file details: {e}")
        
    except Exception as e:
        logging.error(f"Error getting file info: {e}")
    
    return info


def format_transcription_result(transcription, include_metadata=True):
    """Format transcription result for display"""
    if not transcription:
        return "No transcription available"
    
    # Extract metadata if present
    if '[' in transcription and ']' in transcription:
        text_part = transcription.split('[')[0].strip()
        metadata_part = transcription.split('[')[1].split(']')[0] if '[' in transcription else ""
        
        if include_metadata and metadata_part:
            return f"Text: {text_part}\nMetadata: {metadata_part}"
        else:
            return text_part
    
    return transcription


def estimate_processing_time(file_path):
    """Estimate processing time based on file size and format"""
    import os
    
    try:
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        # Fast Transcription is typically 5-10x faster than real-time
        # Estimate based on file size (rough approximation)
        estimated_audio_duration = file_size_mb * 8  # Very rough estimate
        estimated_processing_time = estimated_audio_duration / 6  # 6x faster than real-time average
        
        return max(1, estimated_processing_time)  # Minimum 1 second
        
    except Exception:
        return 5  # Default estimate
