"""Sanitized structured diagnostics; never log provider exception messages."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_SECRET = re.compile(
    r"(?i)\b(token|password|secret|api[_-]?key|authorization)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|\S+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_URL_PASSWORD = re.compile(r"(://[^\s:/]+:)[^\s@]+(@)")
LOGGER = logging.getLogger("ci_diagnosis")
LOGGER.addHandler(logging.NullHandler())


def safe_detail(text: str) -> str:
    text = _SECRET.sub(lambda m: m.group(1) + "=[REDACTED]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    return _URL_PASSWORD.sub(r"\1[REDACTED]\2", text)[:512]


def emit(event: str, **fields: object) -> None:
    """Call sites supply only IDs/hashes, dispositions and numeric resource facts."""
    if not LOGGER.isEnabledFor(logging.INFO):
        return
    clean = {key: safe_detail(value) if isinstance(value, str) else value for key, value in fields.items()}
    LOGGER.info(event, extra={"diagnostic_event": {"event": event, **clean}})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = getattr(record, "diagnostic_event", {"event": record.getMessage()})
        return json.dumps(payload, sort_keys=True, allow_nan=False)
