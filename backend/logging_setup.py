"""Structured logging: console + per-workspace DB rows. Secrets are redacted."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.persistence.db import connect, utcnow

_REDACT_KEY_RE = re.compile(r"(secret|token|password|passwd|api[_-]?key|authorization)", re.I)
_SENSITIVE_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9]{8,}|Bearer\s+\S+)", re.I)

_logger = logging.getLogger("uibinder")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if _REDACT_KEY_RE.search(str(k)) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return _SENSITIVE_VALUE_RE.sub("[REDACTED]", value)
    return value


def log(workspace_id: str, level: str, message: str, **context: Any) -> None:
    """Persist a structured log row and mirror to console. Never raises."""
    level = level.upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        level = "INFO"
    safe_ctx = _redact(context)
    getattr(_logger, level.lower() if level != "WARNING" else "warning")(
        "[%s] %s %s", workspace_id or "-", message, json.dumps(safe_ctx, default=str)
    )
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO logs (workspace_id, ts, level, message, context) VALUES (?,?,?,?,?)",
                (workspace_id, utcnow(), level, message, json.dumps(safe_ctx, default=str)),
            )
    except Exception:  # logging must never break the request path
        _logger.exception("failed to persist log row")
