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


def reset_service_for_tests() -> None:
    """Reset the process-global service singleton. Intended for tests only."""
    global _service
    _service = None
