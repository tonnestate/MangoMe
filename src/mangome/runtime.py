from __future__ import annotations

import os

from .integrity import IntegrityMangoMeService
from .service import MangoMeService
from .storage.memory import InMemoryStore
from .storage.mongo import MongoStore

_service: MangoMeService | None = None


def get_service() -> MangoMeService:
    global _service
    if _service is not None:
        return _service
    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()
    if backend == "memory":
        store = InMemoryStore()
    else:
        uri = os.environ.get("MANGOME_MONGODB_URI", "mongodb://127.0.0.1:27017")
        database = os.environ.get("MANGOME_DATABASE", "mangome")
        store = MongoStore(uri, database)
    _service = IntegrityMangoMeService(store)
    return _service


def health_snapshot() -> dict[str, object]:
    """Return a health report even when backing-store bootstrap fails.

    Health is an observability boundary, so it must not require a successfully
    constructed MangoMeService. Diagnostics intentionally expose only the
    exception class and a sanitized category, never connection strings or
    exception messages that may contain credentials.
    """
    from . import __version__
    from .schema import CURRENT_SCHEMA_VERSION

    backend = os.environ.get("MANGOME_BACKEND", "mongo").lower()
    database = os.environ.get("MANGOME_DATABASE", "mangome") if backend != "memory" else None
    backend_name = "memory" if backend == "memory" else "mongodb"

    try:
        service = get_service()
        store_health = service.store.health()
    except Exception as exc:  # health must survive failed store/bootstrap initialization
        error_type = type(exc).__name__
        code = getattr(exc, "code", None)
        if code == 13 or error_type in {"AuthenticationFailure", "OperationFailure"}:
            diagnostic = "MongoDB authorization failed during MangoMe initialization"
        elif error_type in {"ServerSelectionTimeoutError", "ConnectionFailure", "AutoReconnect"}:
            diagnostic = "MongoDB is unreachable"
        else:
            diagnostic = "MangoMe backing-store initialization failed"
        store: dict[str, object] = {
            "ok": False,
            "backend": backend_name,
            "error_type": error_type,
            "diagnostic": diagnostic,
        }
        if database is not None:
            store["database"] = database
        return {
            "ok": False,
            "version": __version__,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "store": store,
        }

    return {
        "ok": bool(store_health.get("ok")),
        "version": __version__,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "store": store_health,
    }


def reset_service_for_tests() -> None:
    """Reset the process-global service singleton. Intended for tests only."""
    global _service
    _service = None
