import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional

COLORS = {
    'DEBUG': '\033[36m',
    'INFO': '\033[32m',
    'WARNING': '\033[33m',
    'ERROR': '\033[31m',
    'CRITICAL': '\033[35m',
    'RESET': '\033[0m'
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelname, COLORS['RESET'])
        reset = COLORS['RESET']
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)

class LogBuffer:
    def __init__(self, max_lines: int = 100):
        self.max_lines = max_lines
        self.lines = []
    
    def add(self, line: str):
        self.lines.append(line)
        if len(self.lines) > self.max_lines:
            self.lines.pop(0)
    
    def get_recent(self, n: int = 20) -> list:
        return self.lines[-n:] if self.lines else []

_log_buffer = LogBuffer()

class BufferHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            _log_buffer.add(msg)
        except Exception:
            pass

def get_log_buffer() -> LogBuffer:
    return _log_buffer

def setup_logger(name: str, config: dict) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.get('log_level', 'INFO')))
    
    if logger.handlers:
        return logger
    
    log_file = config.get('log_file', 'bot.log')
    max_mb = config.get('log_max_mb', 10)
    backup_count = config.get('log_backup_count', 3)
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_mb * 1024 * 1024, backupCount=backup_count
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    buffer_handler = BufferHandler()
    buffer_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(buffer_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)