"""
Structured logging with automatic sensitive data redaction.
"""

import json
import logging
from datetime import datetime
from typing import Any


SENSITIVE_KEYS = {
    "password",
    "token",
    "api_key",
    "secret",
    "authorization",
    "cookie",
    "image_base64",
    "credential",
    "private_key",
}


class StructuredFormatter(logging.Formatter):
    """JSON formatter that redacts sensitive data."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields, redacting sensitive ones
        skip_keys = {
            "name",
            "msg",
            "args",
            "created",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "msecs",
            "taskName",
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in skip_keys:
                continue
            if any(s in key.lower() for s in SENSITIVE_KEYS):
                log_data[key] = "[REDACTED]"
            else:
                log_data[key] = _sanitize_value(value)

        return json.dumps(log_data, default=str)


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize values, redacting sensitive data."""
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if any(s in k.lower() for s in SENSITIVE_KEYS) else _sanitize_value(v)
            for k, v in value.items()
        }
    elif isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


class StructuredLogger(logging.Logger):
    """Logger that supports extra kwargs for structured logging."""

    def _log(
        self,
        level: int,
        msg: object,
        args: tuple,
        exc_info=None,
        extra: dict | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        **kwargs,
    ) -> None:
        """Override to accept extra kwargs and add them to the record."""
        if extra is None:
            extra = {}
        extra.update(kwargs)
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)


def get_logger(name: str, level: int = logging.INFO) -> StructuredLogger:
    """Get configured logger with structured JSON output."""
    logging.setLoggerClass(StructuredLogger)
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger  # type: ignore


def sanitize_for_logging(data: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize a dictionary for safe logging.
    Use this before logging any user-provided or external data.
    """
    return _sanitize_value(data)
