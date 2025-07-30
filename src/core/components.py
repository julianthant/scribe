"""
Component initialization and management for Azure Functions
Thread-safe singleton pattern for configuration and workflow orchestrator
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Thread-safe singleton implementation
_lock = threading.RLock()
_config = None
_workflow_orchestrator = None


def get_config():
    """Get or create configuration (thread-safe)"""
    global _config
    
    # Double-checked locking pattern
    if _config is None:
        with _lock:
            if _config is None:
                try:
                    from core.config import ScribeConfig
                    _config = ScribeConfig.from_environment()
                    if not _config.validate():
                        logger.error("❌ Configuration validation failed")
                        _config = None
                        return None
                    logger.debug("✅ Configuration initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Configuration initialization failed: {e}")
                    _config = None
                    return None
    return _config


def get_workflow_orchestrator():
    """Get or create workflow orchestrator (thread-safe)"""
    global _workflow_orchestrator
    
    # Double-checked locking pattern
    if _workflow_orchestrator is None:
        with _lock:
            if _workflow_orchestrator is None:
                try:
                    config = get_config()
                    if not config:
                        logger.error("❌ Cannot create workflow orchestrator: Configuration failed")
                        return None
                    
                    from core.workflow import WorkflowOrchestrator
                    _workflow_orchestrator = WorkflowOrchestrator(config)
                    logger.debug("✅ Workflow orchestrator initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Workflow orchestrator initialization failed: {e}")
                    _workflow_orchestrator = None
                    return None
    return _workflow_orchestrator


def initialize_workflow():
    """Initialize workflow orchestrator with proper error handling"""
    workflow = get_workflow_orchestrator()
    if not workflow:
        raise RuntimeError("Failed to initialize workflow orchestrator - check configuration and dependencies")
    return workflow


def reset_components():
    """Reset global components (thread-safe, useful for testing)"""
    global _config, _workflow_orchestrator
    with _lock:
        _config = None
        _workflow_orchestrator = None
        logger.debug("🔄 Components reset successfully")


def get_component_status() -> dict:
    """Get status of all components for health checks"""
    return {
        'config_initialized': _config is not None,
        'workflow_initialized': _workflow_orchestrator is not None,
        'thread_safe': True
    }