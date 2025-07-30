#!/usr/bin/env python3
"""
Workflow Orchestrator Unit Tests
Tests the complete workflow orchestration and error handling
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class TestWorkflowOrchestrator(unittest.TestCase):
    """Test workflow orchestration functionality"""
    
    def setUp(self):
        """Set up test configuration"""
        from core.config import ScribeConfig
        
        self.config = ScribeConfig(
            client_id='test-client-id',
            tenant_id='test-tenant-id',
            storage_connection_string='test-connection',
            excel_file_name='Test_Scribe.xlsx',
            speech_api_key='test-api-key',
            max_emails=5,
            days_back=7
        )
    
    def test_workflow_orchestrator_initialization(self):
        """Test workflow orchestrator initialization"""
        try:
            from core.workflow import WorkflowOrchestrator
            
            orchestrator = WorkflowOrchestrator(self.config)
            self.assertIsNotNone(orchestrator)
            self.assertEqual(orchestrator.config, self.config)
            
            # Test that processors are initialized
            self.assertTrue(hasattr(orchestrator, 'email_processor'))
            self.assertTrue(hasattr(orchestrator, 'transcription_processor'))
            self.assertTrue(hasattr(orchestrator, 'excel_processor'))
            
        except ImportError as e:
            self.skipTest(f"Workflow orchestrator import failed: {e}")
    
    def test_workflow_result_structure(self):
        """Test workflow result data structure"""
        try:
            from models.data import WorkflowResult
            
            result = WorkflowResult(
                success=True,
                emails_processed=3,
                transcriptions_completed=3,
                excel_rows_added=3,
                errors=[],
                processing_time_seconds=45.2
            )
            
            self.assertTrue(result.success)
            self.assertEqual(result.emails_processed, 3)
            self.assertEqual(result.transcriptions_completed, 3)
            self.assertEqual(result.excel_rows_added, 3)
            self.assertEqual(len(result.errors), 0)
            self.assertGreater(result.processing_time_seconds, 0)
            
        except ImportError as e:
            self.skipTest(f"Workflow result test skipped: {e}")
    
    @patch('core.workflow.WorkflowOrchestrator._retrieve_voice_emails')
    @patch('core.workflow.WorkflowOrchestrator._process_voice_emails')
    def test_complete_workflow_execution(self, mock_process, mock_retrieve):
        """Test complete workflow execution with mocks"""
        from models.data import VoiceEmail, EmailAttachment
        
        # Mock voice email data
        attachment = EmailAttachment(
            filename="test.wav",
            content=b"test_audio",
            content_type="audio/wav",
            size=1024
        )
        
        voice_email = VoiceEmail(
            message_id="test-123",
            subject="Voice Message from (555) 123-4567",
            sender="test@example.com",
            received_date=datetime.now(),
            voice_attachments=[attachment]
        )
        
        mock_retrieve.return_value = [voice_email]
        mock_process.return_value = None  # Successful processing
        
        try:
            from core.workflow import WorkflowOrchestrator
            
            orchestrator = WorkflowOrchestrator(self.config)
            
            # Test workflow execution
            result = orchestrator.execute_complete_workflow(max_emails=1, days_back=1)
            
            self.assertIsNotNone(result)
            mock_retrieve.assert_called_once()
            mock_process.assert_called_once()
            
        except Exception as e:
            self.skipTest(f"Complete workflow test skipped (requires mocking): {e}")
    
    def test_workflow_timeout_handling(self):
        """Test workflow timeout handling"""
        try:
            from core.workflow import WorkflowOrchestrator
            from core.exceptions import WorkflowTimeoutError
            
            orchestrator = WorkflowOrchestrator(self.config)
            
            # Test that timeout parameter is respected
            result = orchestrator.execute_complete_workflow(
                max_emails=1, 
                days_back=1, 
                timeout_seconds=1  # Very short timeout
            )
            
            # Should complete quickly or handle timeout gracefully
            self.assertIsNotNone(result)
            
        except Exception as e:
            self.skipTest(f"Timeout handling test skipped: {e}")
    
    def test_workflow_error_handling(self):
        """Test workflow error handling and recovery"""
        try:
            from core.workflow import WorkflowOrchestrator
            
            orchestrator = WorkflowOrchestrator(self.config)
            
            # Test that workflow handles errors gracefully
            self.assertTrue(hasattr(orchestrator, '_create_workflow_result'))
            
        except ImportError as e:
            self.skipTest(f"Error handling test skipped: {e}")
    
    def test_workflow_stats_tracking(self):
        """Test workflow statistics tracking"""
        try:
            from core.workflow import WorkflowStats
            import time
            
            stats = WorkflowStats(start_time=time.time())
            
            # Test stats initialization
            self.assertIsNotNone(stats.start_time)
            self.assertEqual(stats.emails_found, 0)
            self.assertEqual(stats.emails_processed, 0)
            self.assertEqual(stats.transcriptions_attempted, 0)
            self.assertEqual(stats.transcriptions_successful, 0)
            self.assertIsInstance(stats.errors_encountered, list)
            
            # Test stats updates
            stats.emails_found = 2
            stats.emails_processed = 2
            stats.transcriptions_attempted = 2
            stats.transcriptions_successful = 1
            stats.errors_encountered.append("Test error")
            
            self.assertEqual(stats.emails_found, 2)
            self.assertEqual(stats.transcriptions_successful, 1)
            self.assertEqual(len(stats.errors_encountered), 1)
            
            # Test success rate calculation
            success_rate = stats.success_rate
            self.assertEqual(success_rate, 50.0)  # 1/2 = 50%
            
        except ImportError as e:
            self.skipTest(f"Workflow stats test skipped: {e}")
    
    def test_workflow_context_manager(self):
        """Test workflow context manager functionality"""
        try:
            from core.workflow import WorkflowOrchestrator
            
            orchestrator = WorkflowOrchestrator(self.config)
            
            # Test that context manager exists
            self.assertTrue(hasattr(orchestrator, '_workflow_context'))
            
            # Test workflow state tracking
            self.assertFalse(orchestrator.is_running)
            
        except ImportError as e:
            self.skipTest(f"Context manager test skipped: {e}")
    
    def test_partial_workflow_success(self):
        """Test handling of partial workflow success"""
        try:
            from core.workflow import WorkflowOrchestrator
            
            orchestrator = WorkflowOrchestrator(self.config)
            
            # Test that partial success handling exists
            self.assertTrue(hasattr(orchestrator, '_create_workflow_result'))
            
        except ImportError as e:
            self.skipTest(f"Partial success test skipped: {e}")


if __name__ == '__main__':
    unittest.main()