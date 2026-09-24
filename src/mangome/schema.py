from __future__ import annotations

from copy import deepcopy
from typing import Any

CURRENT_SCHEMA_VERSION = 2


def upgrade_document(collection: str, document: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Upgrade a document in memory without destroying unknown fields."""
    doc = deepcopy(document)
    changes: list[str] = []
    version = int(doc.get("schema_version", 1))

    if "revision" not in doc:
        doc["revision"] = 0
        changes.append("add revision")

    if version < 2:
        if collection == "slices":
            doc.setdefault("active_plan_id", None)
            doc.setdefault("last_plan_id", None)
            doc.setdefault("dependency_requirements", [
                {"slice_id": dep, "required_level": "DONE_CLAIMED"}
                for dep in doc.get("depends_on", [])
            ])
            for gate in doc.get("gates", []):
                gate.setdefault("decided_by", None)
                gate.setdefault("decided_at", None)
                gate.setdefault("approval_id", None)
        elif collection == "evidence":
            result = str(doc.get("result") or "").upper()
            verdict = "PASS" if result in {"PASS", "PASSED", "OK", "SUCCESS", "TRUE"} else (
                "FAIL" if result in {"FAIL", "FAILED", "ERROR", "REJECTED", "FALSE"} else "UNKNOWN"
            )
            doc.setdefault("evidence_class", "CLAIM")
            doc.setdefault("verdict", verdict)
            doc.setdefault("trust", "UNATTESTED")
            doc.setdefault("attested_by", None)
            doc.setdefault("attested_at", None)
        elif collection == "approvals":
            doc.setdefault("decision_ref", None)
        doc["schema_version"] = 2
        changes.append("schema 1 -> 2")

    return doc, changes
