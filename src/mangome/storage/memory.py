from __future__ import annotations

from copy import deepcopy
from typing import Any

from .base import Store


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    for key, expected in query.items():
        if key.endswith("__in"):
            field = key[:-4]
            if doc.get(field) not in expected:
                return False
        elif key.endswith("__contains"):
            field = key[:-10]
            value = doc.get(field, [])
            if expected not in value:
                return False
        elif doc.get(key) != expected:
            return False
    return True


class InMemoryStore(Store):
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    def insert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        bucket = self._data.setdefault(collection, {})
        entity_id = str(doc["entity_id"])
        if entity_id in bucket:
            raise ValueError(f"duplicate entity_id {entity_id}")
        bucket[entity_id] = deepcopy(doc)
        return deepcopy(bucket[entity_id])

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        doc = self._data.get(collection, {}).get(entity_id)
        return deepcopy(doc) if doc else None

    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = query or {}
        docs = self._data.get(collection, {}).values()
        return [deepcopy(d) for d in docs if _matches(d, query)]

    def update(self, collection: str, entity_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        bucket = self._data.setdefault(collection, {})
        if entity_id not in bucket:
            raise KeyError(f"missing {collection}:{entity_id}")
        for key, value in patch.items():
            if "." not in key:
                bucket[entity_id][key] = deepcopy(value)
                continue
            parts = key.split(".")
            target = bucket[entity_id]
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = deepcopy(value)
        return deepcopy(bucket[entity_id])

    def ensure_indexes(self) -> None:
        return None
