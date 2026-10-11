"""Central fail-soft envelope for MCP tool handlers (never raise across the protocol boundary)."""
from __future__ import annotations

import functools
import sys
import traceback
from typing import Any, Callable


def classify_error(exc: BaseException) -> tuple[str, bool]:
    """Map an exception to (error_class, retriable). No class ever stops the server."""
    name = type(exc).__name__
    code = str(getattr(exc, "code", "") or "")
    if name in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect", "NetworkTimeout", "NotPrimaryError"}:
        return "DB_UNAVAILABLE", True
    if name == "DuplicateKeyError" or "CONFLICT" in code.upper():
        return "CONFLICT", False
    if code.startswith("WRONG_") or "DENIED" in code.upper() or "GOVERNANCE" in code.upper():
        return "GOVERNANCE_DENIED", False
    if isinstance(exc, (KeyError, ValueError, TypeError, AttributeError)) or "INVALID" in code.upper():
        return "INPUT_INVALID", False
    return "INTERNAL", False


def failsoft(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Central error envelope: a tool call never raises, so it never closes the transport."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - deliberate catch-all at the protocol boundary
            error_class, retriable = classify_error(exc)
            print(f"mangome tool {fn.__name__} failed [{error_class}]: {exc!r}", file=sys.stderr)
            if error_class == "INTERNAL":
                traceback.print_exc(file=sys.stderr)
            return {
                "ok": False,
                "disposition": "ACTION_BLOCKED",
                "reason_codes": [error_class],
                "error": {
                    "code": str(getattr(exc, "code", "") or error_class),
                    "error_class": error_class,
                    "message": str(exc)[:500],
                    "retriable": retriable,
                    "affects": fn.__name__,
                },
            }

    return wrapper
