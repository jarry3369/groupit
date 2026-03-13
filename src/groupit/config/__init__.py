"""
Configuration management for the commit grouping system.
"""

from .settings import Settings, get_settings, update_settings
from .logging_config import setup_logging, get_logger
from .paths import get_default_config_path

__all__ = ['Settings', 'get_settings', 'update_settings', 'setup_logging', 'get_logger', 'get_default_config_path']
