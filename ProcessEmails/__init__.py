import azure.functions as func
import logging
import sys
import os

# Add the parent directory to the path so we can import from function_app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from function_app import EmailVoiceProcessor

def main(mytimer: func.TimerRequest) -> None:
    """
    Timer trigger function that processes voice email attachments
    Runs every 15 minutes as configured in function.json
    """
    utc_timestamp = mytimer.utc_timestamp.replace(tzinfo=None) if mytimer.utc_timestamp else None
    
    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info(f'Python timer trigger function executed at UTC {utc_timestamp}')
    
    try:
        # Create processor instance and run
        processor = EmailVoiceProcessor()
        processor.process_emails()
        logging.info('Email processing completed successfully')
        
    except Exception as e:
        logging.error(f'Error in timer function: {str(e)}')
        raise e
