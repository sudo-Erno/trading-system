import os
import logging

def get_core_logger(name: str) -> logging.Logger:
    """
    Creates and returns a configured logger instance.
    Can be imported and used safely across multiple files.
    """
    # Grab the log directory from the environment or default to './logs'
    log_dir = os.getenv('LOG_DIR', './logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'trading_system.log')

    # Initialize the specific logger for the module
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent adding duplicate handlers if the logger is requested multiple times
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # File output handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)

        # Console output handler
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger