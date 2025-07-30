"""
Scribe Voice Email Processor - Clean Implementation
Main source package with all core functionality
"""

# Import main modules for easier access
from . import api
from . import core
from . import helpers
from . import models
from . import processors
from . import scripts

__version__ = "2.0.0"

__all__ = [
    'api',
    'core', 
    'helpers',
    'models',
    'processors',
    'scripts'
]