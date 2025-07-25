"""
Performance monitoring helper functions
"""

import time
import psutil
import logging
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Performance metrics data"""
    execution_time: float
    memory_usage_mb: Optional[float] = None
    cpu_percent: Optional[float] = None


class PerformanceTimer:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger(__name__)
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(f"⏱️ Starting timer for {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        execution_time = self.end_time - self.start_time
        self.logger.info(f"⏱️ {self.operation_name} completed in {execution_time:.2f}s")
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """Get elapsed time if timing is complete"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def elapsed_ms(self) -> Optional[float]:
        """Get elapsed time in milliseconds if timing is complete"""
        elapsed = self.elapsed_time
        return elapsed * 1000 if elapsed is not None else None


def time_operation(operation: Callable, operation_name: Optional[str] = None) -> tuple[Any, float]:
    """
    Time an operation and return result with execution time
    
    Args:
        operation: Function to time
        operation_name: Name for logging
        
    Returns:
        Tuple of (result, execution_time_seconds)
    """
    operation_name = operation_name or operation.__name__
    
    start_time = time.time()
    result = operation()
    execution_time = time.time() - start_time
    
    logging.getLogger(__name__).debug(f"⏱️ {operation_name} took {execution_time:.2f}s")
    
    return result, execution_time


@contextmanager
def track_memory_usage(operation_name: str):
    """
    Context manager to track memory usage during operation
    
    Args:
        operation_name: Name of operation for logging
    """
    logger = logging.getLogger(__name__)
    process = psutil.Process()
    
    # Get initial memory usage
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    logger.debug(f"🧠 Starting memory tracking for {operation_name} - Initial: {initial_memory:.1f}MB")
    
    try:
        yield
    finally:
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_diff = final_memory - initial_memory
        
        logger.info(f"🧠 {operation_name} memory usage - Final: {final_memory:.1f}MB (Δ{memory_diff:+.1f}MB)")


def log_performance_metrics(operation_name: str, metrics: PerformanceMetrics) -> None:
    """
    Log performance metrics in structured format
    
    Args:
        operation_name: Name of operation
        metrics: Performance metrics to log
    """
    logger = logging.getLogger(__name__)
    
    log_data = {
        'operation': operation_name,
        'execution_time_seconds': metrics.execution_time,
        'memory_usage_mb': metrics.memory_usage_mb,
        'cpu_percent': metrics.cpu_percent
    }
    
    logger.info(f"📊 Performance metrics for {operation_name}", extra={'metrics': log_data})
