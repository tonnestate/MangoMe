from __future__ import annotations

from typing import Any

from .base import Store

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
        self.db[collection].insert_one(doc)
        return doc

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        return self.db[collection].find_one({"entity_id": entity_id}, {"_id": 0})

    def find(self, collection: str, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        mongo_query: dict[str, Any] = {}
        for key, value in (query or {}).items():
            if key.endswith("__in"):
                mongo_query[key[:-4]] = {"$in": value}
            elif key.endswith("__contains"):
                mongo_query[key[:-10]] = value
            else:
                mongo_query[key] = value
        return list(self.db[collection].find(mongo_query, {"_id": 0}))

    def update(self, collection: str, entity_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        result = self.db[collection].find_one_and_update(
            {"entity_id": entity_id},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        if result is None:
            raise KeyError(f"missing {collection}:{entity_id}")
        return result

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
