import azure.functions as func
import logging
import os
import sys
from azure.storage.blob import BlobServiceClient

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
    
# Import all processors
from azure_foundry_processor_class import AzureFoundryAudioProcessor
from excel_processor_class import ExcelProcessor
from email_processor_class import EmailProcessor

# Create the function app
app = func.FunctionApp()

# Configuration
STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
SPEECH_KEY = os.environ.get('AZURE_SPEECH_KEY')
SPEECH_REGION = os.environ.get('AZURE_SPEECH_REGION')
AZURE_FOUNDRY_ENDPOINT = os.environ.get('AZURE_FOUNDRY_ENDPOINT')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
TENANT_ID = os.environ.get('TENANT_ID')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
TARGET_USER_EMAIL = os.environ.get('TARGET_USER_EMAIL')
EXCEL_FILE_NAME = os.environ.get('EXCEL_FILE_NAME', 'Voice_Emails.xlsx')

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="mytimer", run_on_startup=True,
                   use_monitor=False) 
def ProcessEmails(mytimer: func.TimerRequest) -> None:
    """Timer-triggered function to process voice emails every 5 minutes"""
    logging.info('Python timer trigger function started processing voice emails.')
    
    try:
        # Get Microsoft Graph access token
        access_token = get_access_token()
        if not access_token:
            logging.error("Failed to get access token")
            return
            
        # Initialize blob storage client
        blob_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        
        # Create processor instance and process emails
        email_processor = EmailProcessor(access_token, blob_client, TARGET_USER_EMAIL)
        email_processor.process_emails()
        
        logging.info('Voice email processing completed successfully')
        
    except Exception as e:
        logging.error(f"Error in ProcessEmails: {str(e)}")
        raise


@app.route(route="ProcessEmailsHttp", auth_level=func.AuthLevel.FUNCTION)
def ProcessEmailsHttp(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP-triggered function for manual voice email processing"""
    logging.info('Python HTTP trigger function started processing voice emails.')
    
    try:
        # Get Microsoft Graph access token
        access_token = get_access_token()
        if not access_token:
            return func.HttpResponse("Failed to get access token", status_code=500)
            
        # Initialize blob storage client
        blob_client = BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)
        
        # Create processor instance and process emails
        email_processor = EmailProcessor(access_token, blob_client, TARGET_USER_EMAIL)
        email_processor.process_emails()
        
        return func.HttpResponse("Voice email processing completed successfully", status_code=200)
        
    except Exception as e:
        logging.error(f"Error in ProcessEmailsHttp: {str(e)}")
        return func.HttpResponse(f"Error processing emails: {str(e)}", status_code=500)


def get_access_token():
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
