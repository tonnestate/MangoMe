#!/usr/bin/env python3
"""Migrate requests.admission_key to a partial unique index on string values.

Default is a dry run. --apply requires --backup-dir pointing at a mongodump taken
for this run (must exist and be non-empty). Steps: duplicate check on string keys,
create partial index (idempotent), drop legacy sparse index. Explicit nulls are left untouched unless --unset-nulls.
Usage: migrate_admission_key_index.py --uri URI --db NAME [--apply --backup-dir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys

from pymongo import ASCENDING, MongoClient

NEW = "requests_admission_key_string_unique_v1"
OLD = "admission_key_1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uri", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--unset-nulls", action="store_true",
                    help="also $unset explicit null admission_key values (not needed: the partial index ignores them)")
    a = ap.parse_args()
    if a.apply and not (a.backup_dir and os.path.isdir(a.backup_dir) and os.listdir(a.backup_dir)):
        print("REFUSED: --apply needs an existing, non-empty --backup-dir (fresh mongodump)", file=sys.stderr)
        return 2
    col = MongoClient(a.uri, serverSelectionTimeoutMS=3000)[a.db]["requests"]
    dups = list(col.aggregate([
        {"$match": {"admission_key": {"$type": "string"}}},
        {"$group": {"_id": "$admission_key", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}},
    ]))
    nulls = col.count_documents({"admission_key": None, "$expr": {"$eq": [{"$type": "$admission_key"}, "null"]}})
    names = {i["name"] for i in col.list_indexes()}
    print(f"duplicate string keys={len(dups)} explicit_nulls={nulls} indexes={sorted(names)}")
    if dups:
        print("ABORT: duplicate string admission_keys; resolve manually", file=sys.stderr)
        return 3
    if not a.apply:
        print("dry run: nothing changed")
        return 0
    if nulls and a.unset_nulls:
        col.update_many({"$expr": {"$eq": [{"$type": "$admission_key"}, "null"]}}, {"$unset": {"admission_key": ""}})
    col.create_index([("admission_key", ASCENDING)], unique=True, name=NEW,
                     partialFilterExpression={"admission_key": {"$type": "string"}})
    if OLD in names:
        col.drop_index(OLD)
    print("applied:", sorted(i["name"] for i in col.list_indexes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
