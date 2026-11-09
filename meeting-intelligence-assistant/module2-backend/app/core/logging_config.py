
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> None:
    """Configure application-wide console and rotating file logging."""

    # Create logs directory at the backend project root.
    log_directory = Path(__file__).resolve().parents[2] / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)

    log_file = log_directory / "backend.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console logging.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Rotating file logging (5 MB per file, 5 backups).
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if setup is called more than once.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce unnecessary HTTP client logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    root_logger.info("Logging system initialised")
