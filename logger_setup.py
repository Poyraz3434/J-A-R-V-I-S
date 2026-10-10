import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOG_FILE

LOGGER_NAME = "jarvis"

_SENSITIVE_PATTERNS = (
    r"(?i)(api[_-]?key|token|secret|password|smtp[_-]?pass|authorization)\s*[:=]\s*([^\s,;]+)",
    r"(?i)(GROQ_API_KEY|OWM_API_KEY|SMTP_PASS|JARVIS_[A-Z_]+)\b",
)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in _SENSITIVE_PATTERNS:
            message = re.sub(pattern, lambda m: f"{m.group(1)}=[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_path = Path(LOG_FILE)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fh = RotatingFileHandler(
        file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    fh.addFilter(RedactingFilter())
    logger.addHandler(fh)

    return logger


logger = get_logger()
