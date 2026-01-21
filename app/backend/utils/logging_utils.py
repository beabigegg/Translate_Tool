"""Logging helpers for backend services."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FILE_NAME = "translator.log"

logger = logging.getLogger("TranslateTool")


def setup_logging(log_dir: Path, level: int = DEFAULT_LOG_LEVEL, enable_console: bool = True) -> logging.Logger:
    """Configure logging for backend processes."""
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    existing = {type(handler) for handler in logger.handlers}

    if RotatingFileHandler not in existing:
        file_handler = RotatingFileHandler(
            log_dir / LOG_FILE_NAME,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if enable_console and logging.StreamHandler not in existing:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


class QueueHandler(logging.Handler):
    """Logging handler that forwards formatted records to a queue."""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except (ValueError, TypeError):
            self.handleError(record)


class JobLogger:
    """Job-aware logger that writes to both Python logger and a queue."""

    def __init__(self, job_id: str, queue):
        self.job_id = job_id
        self.queue = queue

    def log(self, message: str) -> None:
        logger.info("[%s] %s", self.job_id, message)
        self.queue.put(message)

    def info(self, message: str) -> None:
        self.log(message)

    def warning(self, message: str) -> None:
        logger.warning("[%s] %s", self.job_id, message)
        self.queue.put(message)

    def error(self, message: str) -> None:
        logger.error("[%s] %s", self.job_id, message)
        self.queue.put(message)
