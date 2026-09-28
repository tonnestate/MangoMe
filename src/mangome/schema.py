from __future__ import annotations

from copy import deepcopy
from typing import Any

CURRENT_SCHEMA_VERSION = 6


class UnsupportedSchemaVersion(RuntimeError):
    """Raised when a reader is older than the persisted MangoMe document schema."""


def upgrade_document(collection: str, document: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Upgrade a document in memory without destroying unknown fields."""
    doc = deepcopy(document)
    changes: list[str] = []
    version = int(doc.get("schema_version", 1))
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"unsupported future schema for {collection}: document={version}, reader={CURRENT_SCHEMA_VERSION}"
        )

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
        version = 2

    if version < 3:
        if collection == "execution_receipts":
            doc.setdefault("context_tokens_interlingua", None)
            doc.setdefault("output_tokens_interlingua", None)
            doc.setdefault("interlingua_version", None)
        doc["schema_version"] = 3
        changes.append("schema 2 -> 3")
        version = 3

    if version < 4:
        if collection == "slices":
            doc.setdefault("imported_assurance_state", None)
            doc.setdefault("verification_evidence_ids", [])
            doc.setdefault("verification_observation_ids", [])
            doc.setdefault("verification_profile", None)
            doc.setdefault("verified_by", None)
        doc["schema_version"] = 4
        changes.append("schema 3 -> 4")
        version = 4

    if version < 5:
        if collection == "plans":
            doc.setdefault("work_id", None)
            doc.setdefault("turn_id", None)
            doc.setdefault("normative_baseline_id", None)
        elif collection in {"evidence", "claims"}:
            doc.setdefault("work_id", None)
            doc.setdefault("normative_baseline_id", None)
        doc["schema_version"] = 5
        changes.append("schema 4 -> 5")
        version = 5

    if version < 6:
        if collection == "slices":
            execution = str(doc.get("execution_state") or "PLANNED")
            assurance = str(doc.get("assurance_state") or "UNVERIFIED")
            already_assured = assurance in {"VERIFIED", "ACCEPTED"}
            if already_assured:
                validation_state = "VALIDATED"
                closure_state = "CLOSED"
            elif execution == "DONE_CLAIMED":
                validation_state = "PENDING"
                closure_state = "OPEN"
            else:
                validation_state = "NOT_STARTED"
                closure_state = "OPEN"
            doc.setdefault("validation_state", validation_state)
            doc.setdefault("closure_state", closure_state)
            doc.setdefault("validation_at", None)
            doc.setdefault("validation_actor_id", None)
            doc.setdefault("validation_note", None)
            doc.setdefault("validation_completed_items", [])
            doc.setdefault("validation_open_deltas", [])
            doc.setdefault("validation_evidence_ids", [])
            doc.setdefault("closed_at", (doc.get("accepted_at") or doc.get("verified_at")) if already_assured else None)
            doc.setdefault("closed_by", (doc.get("accepted_by") or doc.get("verified_by")) if already_assured else None)
        doc["schema_version"] = 6
        changes.append("schema 5 -> 6")

    return doc, changes
