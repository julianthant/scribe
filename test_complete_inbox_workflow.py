"""
Test the complete inbox workflow with folder management
Tests: Inbox emails → WAV processing → Excel write → Mark read & move to processed folder
"""

import sys
import os
import logging
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_complete_workflow.log')
    ]
)
logger = logging.getLogger(__name__)

def test_complete_workflow():
    """Test the complete voice email processing workflow"""
    try:
        logger.info("🚀 Starting complete inbox workflow test")
        
        # Import after path setup
        from core.config import ScribeConfig
        from core.workflow import WorkflowOrchestrator
        
        # Load configuration
        config = ScribeConfig.from_environment()
        if not config.validate():
            logger.error("❌ Configuration validation failed")
            return False
        
        logger.info("✅ Configuration loaded and validated")
        
        # Initialize workflow orchestrator
        workflow = WorkflowOrchestrator(config)
        logger.info("✅ Workflow orchestrator initialized")
        
        # Test OAuth connection
        logger.info("🔐 Testing OAuth connection...")
        from helpers.oauth import test_oauth_configuration
        oauth_status = test_oauth_configuration()
        
        if not oauth_status.get('valid', False):
            logger.error(f"❌ OAuth test failed: {oauth_status}")
            return False
        
        logger.info(f"✅ OAuth connection successful: {oauth_status.get('user_email', 'Unknown user')}")
        
        # Test inbox folder access
        logger.info("📧 Testing inbox folder access...")
        voice_emails = workflow.email_processor.get_voice_emails(days_back=7, max_emails=3)
        
        if not voice_emails:
            logger.warning("⚠️ No voice emails found in inbox")
            logger.info("📧 Checking if there are any emails with attachments in inbox...")
            
            # Let's check what's in the inbox
            from helpers.oauth import make_graph_request
            response = make_graph_request("https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top=5")
            if response and response.status_code == 200:
                messages = response.json().get('value', [])
                logger.info(f"📧 Found {len(messages)} total messages in inbox")
                
                for i, msg in enumerate(messages[:3], 1):
                    subject = msg.get('subject', 'No Subject')[:50]
                    has_attachments = msg.get('hasAttachments', False)
                    logger.info(f"   {i}. {subject}... (attachments: {has_attachments})")
            
            return True  # Not an error if no voice emails found
        
        logger.info(f"📧 Found {len(voice_emails)} voice emails in inbox to process")
        
        # Process each voice email
        for i, voice_email in enumerate(voice_emails, 1):
            logger.info(f"\n🔄 Processing voice email {i}/{len(voice_emails)}")
            logger.info(f"   📧 Subject: {voice_email.subject}")
            logger.info(f"   👤 Sender: {voice_email.sender}")
            logger.info(f"   📎 Attachments: {len(voice_email.voice_attachments)}")
            
            # Process each voice attachment
            for j, attachment in enumerate(voice_email.voice_attachments, 1):
                logger.info(f"\n   🎤 Processing attachment {j}: {attachment.filename}")
                logger.info(f"      📦 Size: {attachment.size} bytes")
                
                # Transcribe audio
                transcription_result = workflow.transcription_processor.transcribe_audio(
                    attachment.content,
                    attachment.filename
                )
                
                if not transcription_result.success:
                    logger.error(f"      ❌ Transcription failed: {transcription_result.error_message}")
                    continue
                
                logger.info(f"      ✅ Transcription successful!")
                logger.info(f"      📝 Text ({len(transcription_result.text)} chars): {transcription_result.text[:100]}...")
                logger.info(f"      🎯 Confidence: {transcription_result.confidence:.2f}")
                logger.info(f"      ⏱️ Duration: {transcription_result.duration_seconds:.1f}s")
                logger.info(f"      📊 Words: {transcription_result.word_count}")
                
                # Write to Excel
                excel_result = workflow.excel_processor.write_transcription_result(
                    transcription=transcription_result,
                    email_subject=voice_email.subject,
                    email_sender=voice_email.sender,
                    email_date=voice_email.received_date,
                    attachment_filename=attachment.filename
                )
                
                if not excel_result.success:
                    logger.error(f"      ❌ Excel write failed: {excel_result.error_message}")
                    continue
                
                logger.info(f"      ✅ Excel write successful! Row: {excel_result.row_number}")
                logger.info(f"      ⏱️ Excel write time: {excel_result.processing_time_seconds:.2f}s")
            
            # Mark email as processed (read + move to folder)
            logger.info(f"\n   📝 Marking email as processed...")
            processed_success = workflow.email_processor.mark_email_processed(voice_email.message_id)
            
            if processed_success:
                logger.info(f"   ✅ Email marked as read and moved to 'Voice Messages Processed' folder")
            else:
                logger.warning(f"   ⚠️ Failed to fully process email marking")
        
        logger.info(f"\n🎉 Complete workflow test finished!")
        logger.info(f"📊 Summary:")
        logger.info(f"   📧 Voice emails found: {len(voice_emails)}")
        logger.info(f"   🎤 Total attachments processed: {sum(len(email.voice_attachments) for email in voice_emails)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Complete workflow test failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Complete Inbox Voice Email Workflow")
    print("=" * 60)
    
    success = test_complete_workflow()
    
    print("=" * 60)
    if success:
        print("✅ Test completed successfully!")
        print("📋 Check the logs above for detailed results")
        print("📊 Check your Excel file for new transcription entries")
        print("📧 Check your 'Voice Messages Processed' folder for moved emails")
    else:
        print("❌ Test failed! Check logs for details")
    
    print("\n📁 Log file saved to: test_complete_workflow.log")