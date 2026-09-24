from __future__ import annotations

from mangome.models import Project
from mangome.storage.mongo import MongoStore


class _MutatingCollection:
    def __init__(self) -> None:
        self.inserted = None

    def insert_one(self, doc):
        # Emulate PyMongo: add a BSON-only _id to the exact mapping received.
        doc["_id"] = object()
        self.inserted = doc
        return object()


class _FakeDB:
    def __init__(self) -> None:
        self.collection = _MutatingCollection()

    def __getitem__(self, name):
        return self.collection


def test_mongo_insert_does_not_leak_driver_injected_id_to_domain_result():
    store = MongoStore.__new__(MongoStore)
    store.db = _FakeDB()
    doc = Project(project_key="WIRE", title="Wire safety").model_dump(mode="python")

    returned = store.insert("projects", doc)

    assert "_id" in store.db.collection.inserted
    assert "_id" not in returned
    assert "_id" not in doc
    assert returned["project_key"] == "WIRE"
