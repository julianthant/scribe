"""
Production Workflow Processor - Main orchestrator using new core architecture
Coordinates email processing, transcription, and Excel operations
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from ..core import (
    ScribeConfigurationManager, ScribeServiceInitializer, 
    ScribeWorkflowOrchestrator, ScribeErrorHandler, ScribeLogger
)
from ..models import (
    WorkflowRun, WorkflowStage, WorkflowStatus, StageResult,
    EmailMessage, ProcessingResult, WorkflowConfiguration
)
from .email_processor import ScribeEmailProcessor
from .excel_processor import ScribeExcelProcessor
from .transcription_processor import ScribeTranscriptionProcessor


class ScribeWorkflowProcessor:
    """Main workflow processor coordinating all operations"""
    
    def __init__(self, dependencies: Dict[str, Any]):
        """Initialize workflow processor with dependency injection pattern"""
        self.config = dependencies['config_manager']
        self.service_init = dependencies['service_initializer'] 
        self.orchestrator = dependencies['workflow_orchestrator']
        self.error_handler = dependencies['error_handler']
        self.logger = dependencies['logger']
        
        # Initialize sub-processors
        self.email_processor = ScribeEmailProcessor(self.config, self.error_handler, self.logger)
        self.excel_processor = ScribeExcelProcessor(self.config, self.error_handler, self.logger)
        self.transcription_processor = ScribeTranscriptionProcessor(self.config, self.error_handler, self.logger)
        
        # Workflow configuration
        self.workflow_config = WorkflowConfiguration()
        
        # Initialized services
        self.access_token = None
        self.blob_client = None
        self.target_email = None
        self.excel_filename = None
    
    def initialize_services(self) -> bool:
        """Initialize all required Azure services"""
        try:
            # Initialize Azure services
            services = self.service_init.initialize_all_services()
            if not services:
                raise Exception("Failed to initialize Azure services")
            
            # Extract service components
            self.access_token = services.get('graph_token')
            self.blob_client = services.get('blob_client')
            self.target_email = self.config.get_setting('TARGET_USER_EMAIL')
            self.excel_filename = self.config.get_setting('EXCEL_FILE_NAME')
            
            # Initialize sub-processors
            email_init = self.email_processor.initialize(self.access_token, self.target_email)
            excel_init = self.excel_processor.initialize(self.access_token, self.excel_filename)
            transcription_init = self.transcription_processor.initialize()
            
            if not all([email_init, excel_init, transcription_init]):
                raise Exception("Failed to initialize processors")
            
            self.logger.log_info("All services initialized successfully", {
                'has_token': bool(self.access_token),
                'has_blob_client': bool(self.blob_client),
                'target_email': self.target_email,
                'excel_filename': self.excel_filename
            })
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize services")
            return False
    
    def process_voice_emails(self) -> WorkflowRun:
        """Main workflow to process voice emails end-to-end"""
        # Create new workflow run
        workflow_run = WorkflowRun(
            run_id="",  # Will be auto-generated
            start_time=datetime.now(timezone.utc),
            status=WorkflowStatus.RUNNING,
            current_stage=WorkflowStage.INITIALIZATION
        )
        
        try:
            self.logger.log_info("Starting voice email processing workflow", {
                'run_id': workflow_run.run_id
            })
            
            # Stage 1: Initialization
            if not self._execute_initialization_stage(workflow_run):
                return workflow_run
            
            # Stage 2: Email Retrieval
            if not self._execute_email_retrieval_stage(workflow_run):
                return workflow_run
            
            # Stage 3: Email Filtering
            if not self._execute_email_filtering_stage(workflow_run):
                return workflow_run
            
            # Stage 4: Process each email
            if not self._execute_email_processing_stage(workflow_run):
                return workflow_run
            
            # Stage 5: Completion
            self._execute_completion_stage(workflow_run)
            
            return workflow_run
            
        except Exception as e:
            self.error_handler.handle_error(e, "Workflow execution failed")
            workflow_run.mark_failed(str(e))
            return workflow_run
    
    def _execute_initialization_stage(self, workflow_run: WorkflowRun) -> bool:
        """Execute initialization stage"""
        stage_result = StageResult(
            stage=WorkflowStage.INITIALIZATION,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            # Initialize services if not already done
            if not all([self.access_token, self.blob_client]):
                success = self.initialize_services()
                if not success:
                    stage_result.success = False
                    stage_result.error_message = "Service initialization failed"
                    stage_result.end_time = datetime.now(timezone.utc)
                    workflow_run.add_stage_result(stage_result)
                    return False
            
            stage_result.success = True
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            return True
            
        except Exception as e:
            stage_result.success = False
            stage_result.error_message = str(e)
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            return False
    
    def _execute_email_retrieval_stage(self, workflow_run: WorkflowRun) -> bool:
        """Execute email retrieval stage"""
        stage_result = StageResult(
            stage=WorkflowStage.EMAIL_RETRIEVAL,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            # Get voice emails
            emails = self.email_processor.get_voice_emails(
                days_back=7,
                max_emails=self.workflow_config.max_emails_per_run
            )
            
            workflow_run.emails_processed = emails
            stage_result.items_total = len(emails)
            stage_result.items_processed = len(emails)
            stage_result.success = True
            stage_result.end_time = datetime.now(timezone.utc)
            stage_result.metadata = {'emails_found': len(emails)}
            
            workflow_run.add_stage_result(stage_result)
            
            self.logger.log_info(f"Email retrieval completed", {
                'emails_found': len(emails),
                'run_id': workflow_run.run_id
            })
            
            return True
            
        except Exception as e:
            stage_result.success = False
            stage_result.error_message = str(e)
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            return False
    
    def _execute_email_filtering_stage(self, workflow_run: WorkflowRun) -> bool:
        """Execute email filtering stage"""
        stage_result = StageResult(
            stage=WorkflowStage.EMAIL_FILTERING,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            # Filter emails with voice attachments
            voice_emails = [email for email in workflow_run.emails_processed 
                          if email.has_voice_attachments]
            
            # Update workflow with filtered emails
            workflow_run.emails_processed = voice_emails
            
            stage_result.items_total = len(voice_emails)
            stage_result.items_processed = len(voice_emails)
            stage_result.success = True
            stage_result.end_time = datetime.now(timezone.utc)
            stage_result.metadata = {'voice_emails_filtered': len(voice_emails)}
            
            workflow_run.add_stage_result(stage_result)
            
            return True
            
        except Exception as e:
            stage_result.success = False
            stage_result.error_message = str(e)
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            return False
    
    def _execute_email_processing_stage(self, workflow_run: WorkflowRun) -> bool:
        """Execute email processing stage for each email"""
        stage_result = StageResult(
            stage=WorkflowStage.ATTACHMENT_PROCESSING,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
            items_total=len(workflow_run.emails_processed)
        )
        
        try:
            for email in workflow_run.emails_processed:
                try:
                    # Process single email
                    processing_result = self._process_single_email(email)
                    workflow_run.processing_results.append(processing_result)
                    
                    if processing_result.success:
                        stage_result.items_processed += 1
                    
                    self.logger.log_info(f"Email processed", {
                        'email_id': email.message_id,
                        'success': processing_result.success,
                        'run_id': workflow_run.run_id
                    })
                    
                except Exception as e:
                    # Create failed result for this email
                    failed_result = ProcessingResult(
                        email_id=email.message_id,
                        success=False,
                        transcription_results=[],
                        error_message=str(e)
                    )
                    workflow_run.processing_results.append(failed_result)
                    
                    self.error_handler.handle_error(e, f"Failed to process email {email.message_id}")
            
            stage_result.success = stage_result.items_processed > 0
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            
            return True
            
        except Exception as e:
            stage_result.success = False
            stage_result.error_message = str(e)
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            return False
    
    def _process_single_email(self, email: EmailMessage) -> ProcessingResult:
        """Process a single email with voice attachments"""
        processing_result = ProcessingResult(
            email_id=email.message_id,
            success=False,
            transcription_results=[]
        )
        
        try:
            for attachment in email.voice_attachments:
                attachment_result = self._process_voice_attachment(email, attachment)
                if attachment_result:
                    processing_result.transcription_results.append(attachment_result)
                    processing_result.excel_updated = True
                else:
                    processing_result.add_warning(f"Failed processing {attachment.filename}")
            
            # Mark as successful if any attachments processed
            processing_result.success = len(processing_result.transcription_results) > 0
            
            # Move email to processed folder if successful
            if processing_result.success:
                self._move_email_to_processed_folder(email)
                
        except Exception as e:
            self.logger.error(f"Error processing email {email.message_id}: {str(e)}")
            processing_result.add_error(str(e))
            
        return processing_result
    
    def _process_voice_attachment(self, email: EmailMessage, attachment) -> Optional[Dict[str, Any]]:
        """Process a single voice attachment and return transcription result"""
        try:
            # Download attachment to blob storage
            blob_url = self.email_processor.download_voice_attachment(
                email.message_id, attachment, self.blob_client
            )
            
            if not blob_url:
                self.logger.warning(f"Failed to download {attachment.filename}")
                return None
            
            # Transcribe audio
            transcription = self.transcription_processor.transcribe_audio_file(
                blob_url, attachment.filename
            )
            
            if not transcription or transcription.status != "completed":
                self.logger.warning(f"Failed to transcribe {attachment.filename}")
                return None
            
            # Update Excel with transcription
            self._update_excel_with_transcription(email, transcription, blob_url)
            
            return transcription.to_dict()
            
        except Exception as e:
            self.logger.error(f"Error processing attachment {attachment.filename}: {str(e)}")
            return None
    
    def _update_excel_with_transcription(self, email: EmailMessage, transcription, blob_url: str) -> bool:
        """Update Excel file with transcription data"""
        try:
            structured_data = self._extract_structured_data(email, transcription)
            return self.excel_processor.update_excel_with_transcription(
                structured_data, blob_url
            )
        except Exception as e:
            self.logger.error(f"Failed to update Excel: {str(e)}")
            return False
    
    def _move_email_to_processed_folder(self, email: EmailMessage) -> bool:
        """Move processed email to appropriate folder"""
        try:
            return self.email_processor.move_email_to_processed_folder(email.message_id)
        except Exception as e:
            self.logger.error(f"Failed to move email {email.message_id}: {str(e)}")
            return False
    
    def _execute_completion_stage(self, workflow_run: WorkflowRun):
        """Execute completion stage"""
        stage_result = StageResult(
            stage=WorkflowStage.COMPLETION,
            status=WorkflowStatus.RUNNING,
            start_time=datetime.now(timezone.utc)
        )
        
        try:
            # Calculate summary statistics
            successful_transcriptions = len([r for r in workflow_run.processing_results if r.success])
            
            stage_result.success = True
            stage_result.end_time = datetime.now(timezone.utc)
            stage_result.metadata = {
                'total_emails': len(workflow_run.emails_processed),
                'successful_transcriptions': successful_transcriptions,
                'failed_transcriptions': len(workflow_run.processing_results) - successful_transcriptions
            }
            
            workflow_run.add_stage_result(stage_result)
            workflow_run.mark_completed()
            
            self.logger.log_info("Workflow completed successfully", {
                'run_id': workflow_run.run_id,
                'summary': workflow_run.to_summary_dict()
            })
            
        except Exception as e:
            stage_result.success = False
            stage_result.error_message = str(e)
            stage_result.end_time = datetime.now(timezone.utc)
            workflow_run.add_stage_result(stage_result)
            workflow_run.mark_failed(str(e))
    
    def _extract_structured_data(self, email: EmailMessage, transcription) -> Dict[str, Any]:
        """Extract structured data for Excel storage"""
        return {
            'date': email.received_datetime.strftime('%Y-%m-%d'),
            'time': email.received_datetime.strftime('%H:%M:%S'),
            'from': email.sender,
            'subject': email.subject,
            'transcript': transcription.full_text,
            'duration': transcription.audio_metadata.duration_seconds if transcription.audio_metadata else '',
            'confidence': transcription.confidence_score or ''
        }
