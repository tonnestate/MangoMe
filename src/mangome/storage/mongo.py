from __future__ import annotations

from typing import Any

from ..schema import upgrade_document
from .base import RevisionConflictError, Store

try:
    from pymongo import ASCENDING, MongoClient, ReturnDocument
except ImportError:  # pragma: no cover - unit tests use InMemoryStore
    ASCENDING = 1
    MongoClient = None  # type: ignore[assignment]
    ReturnDocument = None  # type: ignore[assignment]


class MongoStore(Store):
    def __init__(self, uri: str, database: str = "mangome") -> None:
        if MongoClient is None:
            raise RuntimeError("PyMongo is not installed. Install mangome-mcp with its default dependencies.")
        self.client = MongoClient(uri)
        self.db = self.client[database]

    def insert(self, collection: str, doc: dict[str, Any]) -> dict[str, Any]:
        doc = dict(doc)
        doc.setdefault("revision", 0)
        self.db[collection].insert_one(doc)
        return dict(doc)

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        doc = self.db[collection].find_one({"entity_id": entity_id}, {"_id": 0})
        if doc is None:
            return None
        return upgrade_document(collection, doc)[0]

    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        mongo_query: dict[str, Any] = {}
        for key, value in (query or {}).items():
            if key.endswith("__in"):
                mongo_query[key[:-4]] = {"$in": value}
            elif key.endswith("__contains"):
                mongo_query[key[:-10]] = value
            else:
                mongo_query[key] = value
        return [upgrade_document(collection, d)[0] for d in self.db[collection].find(mongo_query, {"_id": 0})]


    def raw_find(self, collection: str) -> list[dict[str, Any]]:
        return list(self.db[collection].find({}, {"_id": 0}))

    def update(
        self,
        collection: str,
        entity_id: str,
        patch: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"entity_id": entity_id}
        if expected_revision is not None:
            if expected_revision == 0:
                query["$or"] = [{"revision": 0}, {"revision": {"$exists": False}}]
            else:
                query["revision"] = expected_revision
        clean_patch = {k: v for k, v in patch.items() if k != "revision"}
        result = self.db[collection].find_one_and_update(
            query,
            {"$set": clean_patch, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        if result is None:
            exists = self.db[collection].find_one({"entity_id": entity_id}, {"_id": 0, "revision": 1})
            if exists is None:
                raise KeyError(f"missing {collection}:{entity_id}")
            raise RevisionConflictError(
                f"revision conflict for {collection}:{entity_id}: expected {expected_revision}, current {exists.get('revision', 0)}"
            )
        return upgrade_document(collection, result)[0]

    def ensure_indexes(self) -> None:
        for name in (
            "requests", "projects", "families", "contracts", "specs", "slices", "plans", "claims",
            "evidence", "artifacts", "edges", "approvals", "project_views", "models", "execution_receipts"
        ):
            self.db[name].create_index([("entity_id", ASCENDING)], unique=True)
        self.db["projects"].create_index([("project_key", ASCENDING)])
        self.db["requests"].create_index([("classification", ASCENDING)])
        self.db["families"].create_index([("family_key", ASCENDING)])
        self.db["contracts"].create_index([("declared_id", ASCENDING)])
        self.db["contracts"].create_index([("family_id", ASCENDING)])
        self.db["specs"].create_index([("family_id", ASCENDING), ("version", ASCENDING)])
        self.db["slices"].create_index([("family_id", ASCENDING), ("sequence", ASCENDING)])
        self.db["plans"].create_index([("family_id", ASCENDING), ("status", ASCENDING)])
        self.db["artifacts"].create_index([("physical_location", ASCENDING)])
        self.db["models"].create_index([("model_key", ASCENDING)], unique=True)
        self.db["execution_receipts"].create_index([("model_id", ASCENDING), ("work_class", ASCENDING)])
        self.db["edges"].create_index([("from_id", ASCENDING), ("relation", ASCENDING), ("to_id", ASCENDING)])

    def health(self) -> dict[str, Any]:
        result = self.db.command("ping")
        return {"ok": result.get("ok") == 1.0, "backend": "mongodb", "database": self.db.name}
