"""
Refactored Workflow Orchestrator for Scribe Voice Email Processor
Production-ready workflow with proper error handling, security, and logging
"""

import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import contextmanager

from core.config import ScribeConfig
from core.exceptions import (
    ScribeBaseException, WorkflowError, WorkflowTimeoutError, 
    PartialWorkflowError, ValidationError
)
from core.security import security_validator
from processors.email import EmailProcessor
from processors.transcription import TranscriptionProcessor
from processors.excel import ExcelProcessor
from models.data import WorkflowResult, VoiceEmail
from core.voice_storage_manager import voice_storage_manager

logger = logging.getLogger(__name__)

@dataclass
class WorkflowStats:
    """Statistics for workflow execution"""
    start_time: float
    end_time: Optional[float] = None
    emails_found: int = 0
    emails_processed: int = 0
    transcriptions_attempted: int = 0
    transcriptions_successful: int = 0
    excel_writes_attempted: int = 0
    excel_writes_successful: int = 0
    errors_encountered: List[str] = None
    
    def __post_init__(self):
        if self.errors_encountered is None:
            self.errors_encountered = []
    
    @property
    def duration_seconds(self) -> float:
        """Get workflow duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate"""
        if self.emails_processed == 0:
            return 0.0
        return (self.transcriptions_successful / self.emails_processed) * 100

class WorkflowOrchestrator:
    """Production-ready workflow orchestrator with comprehensive error handling"""
    
    def __init__(self, config: ScribeConfig):
        self.config = config
        self._validate_configuration()
        
        # Initialize processors with dependency injection
        self.email_processor = EmailProcessor(config)
        self.transcription_processor = TranscriptionProcessor(config)
        self.excel_processor = ExcelProcessor(config)
        
        # Workflow state
        self._is_running = False
        self._stats = None
        
        logger.info("🔧 Workflow orchestrator initialized")
    
    def _validate_configuration(self):
        """Validate configuration before workflow execution"""
        validation_result = security_validator.validate_configuration(self.config.__dict__)
        
        if not validation_result.is_valid:
            raise ValidationError(
                "Configuration validation failed",
                details={'errors': validation_result.errors}
            )
        
        if validation_result.warnings:
            logger.warning(f"Configuration warnings: {validation_result.warnings}")
    
    @contextmanager
    def _workflow_context(self):
        """Context manager for workflow execution"""
        if self._is_running:
            raise WorkflowError("Workflow is already running")
        
        self._is_running = True
        self._stats = WorkflowStats(start_time=time.time())
        
        try:
            logger.info("🚀 Starting workflow execution")
            yield self._stats
        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            self._stats.errors_encountered.append(str(e))
            raise
        finally:
            self._stats.end_time = time.time()
            self._is_running = False
            logger.info(f"⏹️ Workflow execution completed in {self._stats.duration_seconds:.2f}s")
    
    def execute_complete_workflow(
        self,
        max_emails: int = None,
        days_back: int = None,
        timeout_seconds: int = 600
    ) -> WorkflowResult:
        """
        Execute the complete voice email processing workflow
        
        Args:
            max_emails: Maximum emails to process (None = use config default)
            days_back: Days back to search (None = use config default)
            timeout_seconds: Maximum execution time before timeout
            
        Returns:
            WorkflowResult with detailed execution results
            
        Raises:
            WorkflowTimeoutError: If execution exceeds timeout
            WorkflowError: For general workflow failures
        """
        max_emails = max_emails or self.config.max_emails
        days_back = days_back or self.config.days_back
        
        logger.info(f"🚀 Processing up to {max_emails} emails from last {days_back} days")
        
        with self._workflow_context() as stats:
            try:
                # Step 1: Retrieve voice emails
                voice_emails = self._retrieve_voice_emails(days_back, max_emails, stats)
                
                if not voice_emails:
                    logger.warning("⚠️ No voice emails found")
                    return self._create_workflow_result(stats, success=False)
                
                # Step 2: Process each voice email
                self._process_voice_emails(voice_emails, stats, timeout_seconds)
                
                # Step 3: Determine overall success
                overall_success = (
                    stats.transcriptions_successful > 0 and
                    stats.transcriptions_successful == stats.transcriptions_attempted and
                    len(stats.errors_encountered) == 0
                )
                
                if not overall_success and stats.transcriptions_successful > 0:
                    # Partial success
                    logger.warning(f"⚠️ Partial workflow success: {stats.transcriptions_successful}/{stats.transcriptions_attempted}")
                
                return self._create_workflow_result(stats, success=overall_success)
                
            except Exception as e:
                logger.error(f"❌ Workflow execution failed: {e}")
                stats.errors_encountered.append(f"Workflow execution failed: {str(e)}")
                return self._create_workflow_result(stats, success=False)
    
    def _retrieve_voice_emails(self, days_back: int, max_emails: int, stats: WorkflowStats) -> List[VoiceEmail]:
        """Retrieve voice emails with error handling"""
        try:
            logger.info("📧 Retrieving voice emails...")
            voice_emails = self.email_processor.get_voice_emails(days_back, max_emails)
            
            stats.emails_found = len(voice_emails)
            logger.info(f"📧 Found {len(voice_emails)} voice emails")
            
            return voice_emails
            
        except Exception as e:
            error_msg = f"Failed to retrieve voice emails: {str(e)}"
            logger.error(f"❌ {error_msg}")
            stats.errors_encountered.append(error_msg)
            raise WorkflowError(error_msg, details={'step': 'email_retrieval'})
    
    def _process_voice_emails(self, voice_emails: List[VoiceEmail], stats: WorkflowStats, timeout_seconds: int):
        """Process voice emails with comprehensive error handling"""
        start_time = time.time()
        
        for i, voice_email in enumerate(voice_emails, 1):
            # Check timeout
            if time.time() - start_time > timeout_seconds:
                raise WorkflowTimeoutError(
                    f"Workflow timed out after {timeout_seconds} seconds",
                    details={'processed': i-1, 'total': len(voice_emails)}
                )
            
            logger.info(f"📧 Processing email {i}/{len(voice_emails)}: {voice_email.subject}")
            
            try:
                self._process_single_email(voice_email, stats)
                stats.emails_processed += 1
                
            except Exception as e:
                error_msg = f"Failed to process email: {voice_email.subject}"
                logger.error(f"❌ {error_msg}: {e}")
                stats.errors_encountered.append(f"{error_msg}: {str(e)}")
                continue  # Continue with next email
    
    def _process_single_email(self, voice_email: VoiceEmail, stats: WorkflowStats):
        """Process a single voice email"""
        for attachment in voice_email.voice_attachments:
            try:
                # Validate attachment
                validation_result = security_validator.validate_audio_content(
                    attachment.content, attachment.content_type
                )
                
                if not validation_result.is_valid:
                    raise ValidationError(
                        f"Audio validation failed: {validation_result.errors}",
                        details={'filename': attachment.filename}
                    )
                
                if validation_result.warnings:
                    logger.warning(f"Audio validation warnings for {attachment.filename}: {validation_result.warnings}")
                
                # Step 1: Transcribe audio
                stats.transcriptions_attempted += 1
                transcription = self._transcribe_audio_safely(attachment, stats)
                
                if not transcription or not transcription.success:
                    continue  # Skip to next attachment
                
                stats.transcriptions_successful += 1
                
                # Step 2: Store voice message (optional)
                self._store_voice_message_safely(voice_email, attachment)
                
                # Step 3: Write to Excel
                stats.excel_writes_attempted += 1
                excel_result = self._write_to_excel_safely(voice_email, attachment, transcription, stats)
                
                if excel_result and excel_result.success:
                    stats.excel_writes_successful += 1
                
                # Step 4: Mark email as processed
                self._mark_email_processed_safely(voice_email)
                
            except Exception as e:
                error_msg = f"Failed to process attachment: {attachment.filename}"
                logger.error(f"❌ {error_msg}: {e}")
                stats.errors_encountered.append(f"{error_msg}: {str(e)}")
                continue  # Continue with next attachment
    
    def _transcribe_audio_safely(self, attachment, stats):
        """Safely transcribe audio with error handling"""
        try:
            logger.info(f"🎤 Transcribing: {attachment.filename}")
            transcription = self.transcription_processor.transcribe_audio(
                attachment.content, attachment.filename
            )
            
            if transcription.success:
                logger.info(f"✅ Transcription successful: {len(transcription.text)} chars, {transcription.confidence:.2f} confidence")
                return transcription
            else:
                logger.error(f"❌ Transcription failed: {transcription.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Transcription exception: {e}")
            return None
    
    def _store_voice_message_safely(self, voice_email, attachment):
        """Safely store voice message with error handling"""
        try:
            storage_url = voice_storage_manager.store_voice_message(
                attachment.content,
                attachment.filename,
                voice_email.subject,
                voice_email.sender,
                voice_email.received_date
            )
            
            if storage_url:
                logger.info(f"💾 Voice message stored: {storage_url}")
            else:
                logger.warning("⚠️ Voice message storage failed")
                
        except Exception as e:
            logger.warning(f"⚠️ Voice message storage exception: {e}")
    
    def _write_to_excel_safely(self, voice_email, attachment, transcription, stats):
        """Safely write to Excel with error handling"""
        try:
            logger.info(f"📊 Writing to Excel: {attachment.filename}")
            from processors.excel import ExcelRowData
            row_data = ExcelRowData(
                transcription=transcription,
                email_subject=voice_email.subject,
                email_sender=voice_email.sender,
                email_date=voice_email.received_date,
                attachment_filename=attachment.filename,
                download_url=None
            )
            excel_result = self.excel_processor.write_transcription_result(row_data)
            
            if excel_result.success:
                logger.info(f"✅ Excel write successful: Row {excel_result.row_number}")
                return excel_result
            else:
                logger.error(f"❌ Excel write failed: {excel_result.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Excel write exception: {e}")
            return None
    
    def _mark_email_processed_safely(self, voice_email):
        """Safely mark email as processed"""
        try:
            success = self.email_processor.mark_email_processed(voice_email.message_id)
            if success:
                logger.info(f"✅ Email marked as processed: {voice_email.message_id}")
            else:
                logger.warning(f"⚠️ Failed to mark email as processed: {voice_email.message_id}")
                
        except Exception as e:
            logger.warning(f"⚠️ Email processing exception: {e}")
    
    def _send_token_expiry_notification(self):
        """Send email notification when OAuth token expires with sign-in link"""
        try:
            import os
            from helpers.auth_manager import make_graph_request
            
            # Get configuration
            base_url = os.getenv('AZURE_FUNCTION_BASE_URL', 'https://your-function-app.azurewebsites.net')
            signin_url = f"{base_url}/api/signin"
            
            # Create email content
            email_subject = "🔐 Voice Email Processing - Token Expired"
            email_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #d73027;">🔐 Authentication Required</h2>
                    
                    <p>Your voice email processing system needs re-authentication.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0;">
                        <strong>What happened?</strong><br>
                        Your OAuth refresh token has expired, and the system can no longer access your emails to process voice messages.
                    </div>
                    
                    <div style="background-color: #e8f5e8; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0;">
                        <strong>What to do?</strong><br>
                        Click the button below to sign in again. The system will automatically resume processing once you complete authentication.
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{signin_url}" 
                           style="background-color: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                            🔑 Sign In to Resume Processing
                        </a>
                    </div>
                    
                    <p style="font-size: 12px; color: #666; margin-top: 30px;">
                        This is an automated message from your Voice Email Processing System.<br>
                        System Status: <strong>Waiting for Authentication</strong>
                    </p>
                </div>
            </body>
            </html>
            """
            
            # Send email using Microsoft Graph
            email_data = {
                "message": {
                    "subject": email_subject,
                    "body": {
                        "contentType": "HTML",
                        "content": email_body
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": os.getenv('TARGET_USER_EMAIL', 'user@example.com'),
                                "name": os.getenv('TARGET_USER_NAME', 'User')
                            }
                        }
                    ]
                }
            }
            
            # Try to send email (this might fail if token is expired, but worth trying)
            response = make_graph_request("https://graph.microsoft.com/v1.0/me/sendMail", method='POST', data=email_data)
            
            if response and response.status_code == 202:
                logger.info("✅ Token expiry notification sent successfully")
            else:
                logger.warning("⚠️ Could not send token expiry notification via Graph API")
                
        except Exception as e:
            logger.error(f"❌ Failed to send token expiry notification: {e}")
    
    def _create_workflow_result(self, stats: WorkflowStats, success: bool) -> WorkflowResult:
        """Create workflow result from stats"""
        return WorkflowResult(
            success=success,
            emails_processed=stats.emails_processed,
            transcriptions_completed=stats.transcriptions_successful,
            excel_rows_added=stats.excel_writes_successful,
            errors=stats.errors_encountered.copy(),
            processing_time_seconds=stats.duration_seconds
        )
    
    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running"""
        return self._is_running
    
    @property
    def current_stats(self) -> Optional[WorkflowStats]:
        """Get current workflow statistics"""
        return self._stats