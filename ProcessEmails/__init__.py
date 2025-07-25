import azure.functions as func
import datetime
import logging
import os
import sys

# Add parent directory for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
src_dir = os.path.join(parent_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def main(mytimer: func.TimerRequest) -> None:
    """Azure Function entry point for voice email processing"""
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)
    
    try:
        # Import and run the main processing workflow
        from tests.run_e2e_test import RealWorldWorkflowTest
        
        # Initialize and run the workflow
        workflow = RealWorldWorkflowTest()
        workflow.run_complete_workflow_test()
        
        logging.info('Voice email processing completed successfully')
        
    except Exception as e:
        logging.error(f"Error in voice email processing: {str(e)}")
        raise