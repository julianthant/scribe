"""
Workflow Orchestrator for Scribe Voice Email Processor
Coordinates the complete end-to-end voice email processing workflow
"""

import logging
import time
from typing import List, Dict, Any

from core.config import ScribeConfig
from processors.email import EmailProcessor
from processors.transcription import TranscriptionProcessor
from processors.excel import ExcelProcessor
from models.data import WorkflowResult, VoiceEmail

logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    """Orchestrates the complete voice email processing workflow"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        
        # Initialize processors
        self.email_processor = EmailProcessor(config)
        self.transcription_processor = TranscriptionProcessor(config)
        self.excel_processor = ExcelProcessor(config)
        
        logger.info("🚀 Workflow orchestrator initialized")
    
    def execute_complete_workflow(
        self,
        max_emails: int = None,
        days_back: int = None
    ) -> WorkflowResult:
        """Execute the complete voice email processing workflow"""
        start_time = time.time()
        
        try:
            max_emails = max_emails or self.config.max_emails
            days_back = days_back or self.config.days_back
            
            logger.info(f"🚀 Starting complete workflow: {max_emails} emails, {days_back} days back")
            
            # Initialize result
            result = WorkflowResult(success=False)
            
            # Step 1: Get voice emails
            logger.info("📧 Step 1: Retrieving voice emails...")
            voice_emails = self.email_processor.get_voice_emails(days_back, max_emails)
            
            if not voice_emails:
                logger.warning("⚠️ No voice emails found")
                result.processing_time_seconds = time.time() - start_time
                return result
            
            logger.info(f"📧 Found {len(voice_emails)} voice emails to process")
            result.emails_processed = len(voice_emails)
            
            # Step 2: Process each voice email
            for i, voice_email in enumerate(voice_emails, 1):
                logger.info(f"🔄 Processing email {i}/{len(voice_emails)}: {voice_email.subject[:50]}...")
                
                try:
                    email_success = self._process_single_voice_email(voice_email)
                    if email_success:
                        result.transcriptions_completed += 1
                        result.excel_rows_added += 1
                        
                        # Mark email as processed
                        self.email_processor.mark_email_processed(voice_email.message_id)
                        
                    else:
                        result.errors.append(f"Failed to process email: {voice_email.subject[:50]}")
                
                except Exception as e:
                    error_msg = f"Error processing email '{voice_email.subject[:50]}': {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    result.errors.append(error_msg)
            
            # Determine overall success
            result.success = result.transcriptions_completed > 0
            result.processing_time_seconds = time.time() - start_time
            
            # Log final results
            if result.success:
                logger.info(f"✅ Workflow completed successfully:")
                logger.info(f"   📧 Emails processed: {result.emails_processed}")
                logger.info(f"   🎤 Transcriptions completed: {result.transcriptions_completed}")
                logger.info(f"   📊 Excel rows added: {result.excel_rows_added}")
                logger.info(f"   ⏱️ Processing time: {result.processing_time_seconds:.1f}s")
                logger.info(f"   📈 Success rate: {result.success_rate:.1f}%")
            else:
                logger.error("❌ Workflow failed - no transcriptions completed")
                for error in result.errors:
                    logger.error(f"   Error: {error}")
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            
            return WorkflowResult(
                success=False,
                errors=[error_msg],
                processing_time_seconds=processing_time
            )
    
    def _process_single_voice_email(self, voice_email: VoiceEmail) -> bool:
        """Process a single voice email through the complete pipeline"""
        try:
            logger.info(f"📧 Processing: {voice_email.subject}")
            logger.info(f"   📎 Voice attachments: {len(voice_email.voice_attachments)}")
            
            # Process each voice attachment
            for attachment in voice_email.voice_attachments:
                try:
                    logger.info(f"   🎤 Transcribing: {attachment.filename} ({attachment.size} bytes)")
                    
                    # Step 1: Transcribe audio
                    transcription_result = self.transcription_processor.transcribe_audio(
                        attachment.content,
                        attachment.filename
                    )
                    
                    if not transcription_result.success:
                        logger.error(f"❌ Transcription failed: {transcription_result.error_message}")
                        continue
                    
                    logger.info(f"✅ Transcription successful: {len(transcription_result.text)} characters")
                    
                    # Step 2: Write to Excel
                    excel_result = self.excel_processor.write_transcription_result(
                        transcription=transcription_result,
                        email_subject=voice_email.subject,
                        email_sender=voice_email.sender,
                        email_date=voice_email.received_date,
                        attachment_filename=attachment.filename
                    )
                    
                    if not excel_result.success:
                        logger.error(f"❌ Excel write failed: {excel_result.error_message}")
                        continue
                    
                    logger.info(f"✅ Excel write successful: Row {excel_result.row_number}")
                    
                    # If we get here, at least one attachment was processed successfully
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Error processing attachment {attachment.filename}: {e}")
                    continue
            
            # If we get here, no attachments were processed successfully
            return False
            
        except Exception as e:
            logger.error(f"❌ Error processing voice email: {e}")
            return False
    
    def test_all_components(self) -> Dict[str, Any]:
        """Test all workflow components"""
        logger.info("🧪 Testing all workflow components...")
        
        test_results = {
            'timestamp': time.time(),
            'components': {},
            'overall_success': False
        }
        
        # Test OAuth
        try:
            from helpers.oauth import test_oauth_configuration
            oauth_result = test_oauth_configuration()
            test_results['components']['oauth'] = {
                'success': oauth_result.get('valid', False),
                'details': oauth_result
            }
        except Exception as e:
            test_results['components']['oauth'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test transcription processor
        try:
            transcription_test = self.transcription_processor.test_connection()
            test_results['components']['transcription'] = {
                'success': transcription_test,
                'details': 'Azure Speech Services connection test'
            }
        except Exception as e:
            test_results['components']['transcription'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test Excel processor
        try:
            excel_test = self.excel_processor.test_excel_access()
            test_results['components']['excel'] = {
                'success': excel_test,
                'details': f'OneDrive access to {self.config.excel_file_name}'
            }
        except Exception as e:
            test_results['components']['excel'] = {
                'success': False,
                'error': str(e)
            }
        
        # Calculate overall success
        component_results = [comp['success'] for comp in test_results['components'].values()]
        success_count = sum(component_results)
        total_count = len(component_results)
        
        test_results['overall_success'] = success_count >= (total_count * 0.75)  # 75% threshold
        test_results['success_rate'] = (success_count / total_count) * 100 if total_count > 0 else 0
        
        logger.info(f"🧪 Component tests completed: {success_count}/{total_count} passed ({test_results['success_rate']:.1f}%)")
        
        return test_results
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all components"""
        return {
            'timestamp': time.time(),
            'config_valid': self.config.validate(),
            'component_tests': self.test_all_components(),
            'ready_for_processing': self.config.validate() and self.test_all_components()['overall_success']
        }