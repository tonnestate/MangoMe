from __future__ import annotations

from copy import deepcopy
from threading import RLock
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
    # Mirrors MongoStore's domain-level unique indexes. Tests must be capable of
    # detecting the same identity races that production MongoDB rejects.
    _UNIQUE_KEYS: dict[str, tuple[tuple[str, ...], ...]] = {
        "projects": (("project_key",),),
        "requests": (("admission_key",),),
        "families": (("family_key",), ("admission_key",)),
        "slices": (("family_id", "declared_id"),),
        "models": (("model_key",),),
        "effects": (("slice_id", "effect_key"),),
        "filesystem_entries": (("path",),),
        "filesystem_roots": (("root_path",),),
        "contract_heads": (("contract_id",),),
        "work_identities": (("work_key",), ("family_id",)),
        "normative_baselines": (("work_id", "semantic_hash"),),
        "playbooks": (("playbook_key", "version"),),
        "work_views": (("work_id",),),
    }

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict[str, Any]]] = {}
        self._lock = RLock()

    def _assert_unique(self, collection: str, doc: dict[str, Any], *, ignore_entity_id: str | None = None) -> None:
        for fields in self._UNIQUE_KEYS.get(collection, ()):
            values = tuple(doc.get(field) for field in fields)
            # Mirrors sparse Mongo indexes used for optional identity fields.
            if any(value is None for value in values):
                continue
            for existing_id, existing in self._data.get(collection, {}).items():
                if ignore_entity_id is not None and existing_id == ignore_entity_id:
                    continue
                if tuple(existing.get(field) for field in fields) == values:
                    label = ",".join(fields)
                    raise ValueError(f"duplicate unique key {collection}({label})={values!r}")

    def insert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            bucket = self._data.setdefault(collection, {})
            entity_id = str(doc["entity_id"])
            if entity_id in bucket:
                raise ValueError(f"duplicate entity_id {entity_id}")
            doc = deepcopy(doc)
            doc.setdefault("revision", 0)
            self._assert_unique(collection, doc)
            bucket[entity_id] = doc
            return deepcopy(bucket[entity_id])

    def get_or_create(
        self,
        collection: str,
        query: dict[str, Any],
        doc: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        with self._lock:
            for existing in self._data.get(collection, {}).values():
                upgraded, _ = upgrade_document(collection, existing)
                if _matches(upgraded, query):
                    return deepcopy(upgraded), False
            return self.insert(collection, doc), True

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
        with self._lock:
            bucket = self._data.setdefault(collection, {})
            if entity_id not in bucket:
                raise KeyError(f"missing {collection}:{entity_id}")
            current_revision = int(bucket[entity_id].get("revision", 0))
            if expected_revision is not None and current_revision != expected_revision:
                raise RevisionConflictError(
                    f"revision conflict for {collection}:{entity_id}: expected {expected_revision}, current {current_revision}"
                )
            candidate = deepcopy(bucket[entity_id])
            for key, value in patch.items():
                if key == "revision":
                    continue
                if "." not in key:
                    candidate[key] = deepcopy(value)
                    continue
                parts = key.split(".")
                target = candidate
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = deepcopy(value)
            self._assert_unique(collection, candidate, ignore_entity_id=entity_id)
            candidate["revision"] = current_revision + 1
            upgraded, _ = upgrade_document(collection, candidate)
            bucket[entity_id] = deepcopy(upgraded)
            return deepcopy(upgraded)

    def ensure_indexes(self) -> None:
        return None

    def health(self) -> dict[str, Any]:
        return {"ok": True, "backend": "memory", "collections": len(self._data)}
