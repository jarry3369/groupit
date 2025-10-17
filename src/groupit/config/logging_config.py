"""
Logging configuration and setup utilities.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from .settings import LoggingSettings, get_settings


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        """Format log record with colors"""
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        record.name = f"\033[34m{record.name}{self.RESET}"  # Blue for logger name
        return super().format(record)


def setup_logging(settings: Optional[LoggingSettings] = None) -> None:
    """Setup logging configuration"""
    if settings is None:
        app_settings = get_settings()
        settings = app_settings.logging
    
    # Remove existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set root logger level
    root_logger.setLevel(getattr(logging, settings.level.upper()))
    
    # Console handler
    if settings.enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = ColoredFormatter(settings.format)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(getattr(logging, settings.level.upper()))
        root_logger.addHandler(console_handler)
    
    # File handler
    if settings.enable_file and settings.file_path:
        file_path = Path(settings.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=settings.max_file_size,
            backupCount=settings.backup_count,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(settings.format)
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, settings.level.upper()))
        root_logger.addHandler(file_handler)
    
    # Set third-party loggers to WARNING to reduce noise
    noisy_loggers = [
        'urllib3',
        'requests',
        'httpx',
        'httpcore',
        'openai',
        'google.genai',
        'git',
        'unidiff'
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)


class LoggingContext:
    """Context manager for temporary logging level changes"""
    
    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.new_level = level
        self.old_level = None
    
    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.setLevel(self.new_level)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.old_level)


def debug_context(logger: logging.Logger):
    """Context manager for temporary DEBUG level logging"""
    return LoggingContext(logger, logging.DEBUG)


def quiet_context(logger: logging.Logger):
    """Context manager for temporary WARNING level logging"""
    return LoggingContext(logger, logging.WARNING)
