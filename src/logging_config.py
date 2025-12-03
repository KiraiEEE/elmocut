"""
Logging configuration for elmoCut
Provides both file and console logging with rotation
"""

import logging
import logging.handlers
from pathlib import Path
from constants import DOCUMENTS_PATH

def setup_logging(log_level=logging.INFO):
    """
    Setup logging for the application
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create logs directory
    log_dir = Path(DOCUMENTS_PATH) / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'elmocut.log'
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # File handler with rotation (max 5MB, keep 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler (only show INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Silence overly verbose libraries
    logging.getLogger('scapy').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    # Suppress Python warnings from Scapy
    import warnings
    warnings.filterwarnings('ignore', category=SyntaxWarning, module='scapy')
    warnings.filterwarnings('ignore', message='.*iface.*has no effect.*')
    
    logging.info('='*60)
    logging.info('elmoCut logging initialized')
    logging.info(f'Log file: {log_file}')
    logging.info('='*60)

def get_logger(name):
    """
    Get a logger instance for a module
    
    Args:
        name: Module name (usually __name__)
    
    Returns:
        logging.Logger instance
    """
    return logging.getLogger(name)
