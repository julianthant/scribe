"""
Core module for Scribe Voice Email Processor
Contains configuration, workflow orchestration, and component management
"""

# Export main functions for easier imports
from .components import get_workflow_orchestrator, initialize_workflow, get_config
from .config import ScribeConfig
from .workflow import WorkflowOrchestrator
from .input_validation import input_validator

__all__ = [
    'get_workflow_orchestrator',
    'initialize_workflow', 
    'get_config',
    'ScribeConfig',
    'WorkflowOrchestrator',
    'input_validator'
]