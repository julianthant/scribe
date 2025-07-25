"""
Main Azure Function app for voice email processing
Orchestrates email processing, transcription, AI analysis, and Excel updates using the modular src/ structure
"""

import azure.functions as func
import logging
import os
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient

# Import our modular components from src folder
from src.azure_foundry_processor_class import AzureFoundryAudioProcessor
from src.excel_processor_class import ExcelProcessor
from src.email_processor_class import EmailProcessor

app = func.FunctionApp()

# Configuration
STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
SPEECH_KEY = os.environ.get('AZURE_SPEECH_KEY')
SPEECH_REGION = os.environ.get('AZURE_SPEECH_REGION')
TENANT_ID = os.environ.get('TENANT_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
TARGET_USER_EMAIL = os.environ.get('TARGET_USER_EMAIL')
EXCEL_FILE_NAME = os.environ.get('EXCEL_FILE_NAME', 'Voice_Emails.xlsx')


class VoiceEmailProcessor:
    """Main orchestrator class for voice email processing using modular src/ components"""
    
    def __init__(self):
        # Initialize blob storage client
        if not STORAGE_CONNECTION_STRING:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING not configured")
        self.blob_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        
        # Initialize processors using Azure Foundry Fast Transcription
        self.audio_processor = AzureFoundryAudioProcessor(
            speech_key=SPEECH_KEY, 
            speech_region=SPEECH_REGION, 
            blob_client=self.blob_client,
            foundry_endpoint=os.environ.get('AZURE_FOUNDRY_ENDPOINT')
        )
        
        # These will be initialized when we get the access token
        self.email_processor = None
        self.excel_processor = None
        self.access_token = None
    
    def process_emails(self):
        """Main function to process voice emails"""
        try:
            # Get access token
            self.access_token = self._get_access_token()
            if not self.access_token:
                logging.error("Failed to get access token")
                return
            
            # Initialize token-dependent processors
            self.email_processor = EmailProcessor(
                self.access_token, 
                self.blob_client, 
                TARGET_USER_EMAIL,
                self.audio_processor  # Pass the Azure Foundry processor
            )
            self.excel_processor = ExcelProcessor(self.access_token, EXCEL_FILE_NAME)
            
            # Process emails using the email processor
            self.email_processor.process_emails()
                
        except Exception as e:
            logging.error(f"Error in process_emails: {str(e)}")
    
    def _get_access_token(self):
        """Get Microsoft Graph access token using client credentials flow"""
        import requests
        
        try:
            url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'scope': 'https://graph.microsoft.com/.default'
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data['access_token']
            else:
                logging.error(f"Failed to get access token: {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Error getting access token: {str(e)}")
            return None


# Global processor instance
processor = VoiceEmailProcessor()


@app.timer_trigger(schedule="0 */5 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def process_voice_emails(myTimer: func.TimerRequest) -> None:
    """Azure Function timer trigger to process voice emails every 5 minutes"""
    
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('🎯 Voice email processing started...')
    
    try:
        processor.process_emails()
        logging.info('✅ Voice email processing completed successfully')
    except Exception as e:
        logging.error(f'❌ Voice email processing failed: {str(e)}')

    logging.info('📧 Voice email processing function completed.')


@app.function_name(name="HttpTrigger")
@app.route(route="process") 
def http_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger for manual voice email processing"""
    logging.info('Manual voice email processing triggered via HTTP')

    try:
        processor.process_emails()
        return func.HttpResponse("Voice email processing completed successfully", status_code=200)
    except Exception as e:
        logging.error(f'Manual processing failed: {str(e)}')
        return func.HttpResponse(f"Processing failed: {str(e)}", status_code=500)
