from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..schema import upgrade_document
from .base import RevisionConflictError, Store


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
        doc = deepcopy(doc)
        doc.setdefault("revision", 0)
        bucket[entity_id] = doc
        return deepcopy(bucket[entity_id])

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        doc = self._data.get(collection, {}).get(entity_id)
        if not doc:
            return None
        upgraded, _ = upgrade_document(collection, doc)
        return upgraded

    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        query = query or {}
        docs = self._data.get(collection, {}).values()
        result: list[dict[str, Any]] = []
        for raw in docs:
            doc, _ = upgrade_document(collection, raw)
            if _matches(doc, query):
                result.append(doc)
        return result


    def raw_find(self, collection: str) -> list[dict[str, Any]]:
        return [deepcopy(d) for d in self._data.get(collection, {}).values()]

    def update(
        self,
        collection: str,
        entity_id: str,
        patch: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        bucket = self._data.setdefault(collection, {})
        if entity_id not in bucket:
            raise KeyError(f"missing {collection}:{entity_id}")
        current_revision = int(bucket[entity_id].get("revision", 0))
        if expected_revision is not None and current_revision != expected_revision:
            raise RevisionConflictError(
                f"revision conflict for {collection}:{entity_id}: expected {expected_revision}, current {current_revision}"
            )
        for key, value in patch.items():
            if key == "revision":
                continue
            if "." not in key:
                bucket[entity_id][key] = deepcopy(value)
                continue
            parts = key.split(".")
            target = bucket[entity_id]
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = deepcopy(value)
        bucket[entity_id]["revision"] = current_revision + 1
        upgraded, _ = upgrade_document(collection, bucket[entity_id])
        bucket[entity_id] = deepcopy(upgraded)
        return deepcopy(upgraded)

    def ensure_indexes(self) -> None:
        return None

    def health(self) -> dict[str, Any]:
        return {"ok": True, "backend": "memory", "collections": len(self._data)}
