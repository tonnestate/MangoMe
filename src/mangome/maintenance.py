from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .schema import CURRENT_SCHEMA_VERSION, upgrade_document
from .service import MangoMeService


class MangoMaintainer:
    """Deterministic maintenance and diagnostics; no LLM is required."""

    COLLECTIONS = (
        "requests", "projects", "families", "contracts", "specs", "slices", "plans", "claims",
        "evidence", "artifacts", "edges", "approvals", "project_views", "models", "execution_receipts",
        "filesystem_entries", "filesystem_roots",
    )

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    def refresh_all_family_views(self) -> dict[str, int]:
        refreshed = 0
        for family in self.service.store.find("families"):
            self.service.status(family["entity_id"])
            refreshed += 1
        return {"families_refreshed": refreshed}

    def detect_declared_id_collisions(self) -> dict[str, list[str]]:
        by_id: dict[str, list[str]] = {}
        for contract in self.service.store.find("contracts"):
            by_id.setdefault(contract["declared_id"], []).append(contract["entity_id"])
        return {declared: ids for declared, ids in by_id.items() if len(ids) > 1}

    def migrate_schema(self, *, dry_run: bool = True) -> dict[str, Any]:
        scanned = changed = persisted = 0
        details: list[dict[str, Any]] = []
        for collection in self.COLLECTIONS:
            for doc in self.service.store.raw_find(collection):
                scanned += 1
                upgraded, changes = upgrade_document(collection, doc)
                if not changes and int(doc.get("schema_version", CURRENT_SCHEMA_VERSION)) >= CURRENT_SCHEMA_VERSION:
                    continue
                changed += 1
                details.append({"collection": collection, "entity_id": doc["entity_id"], "changes": changes})
                if not dry_run:
                    patch = {k: v for k, v in upgraded.items() if k not in {"entity_id", "revision", "created_at"}}
                    self.service._update(
                        collection,
                        doc["entity_id"],
                        patch,
                        expected_revision=int(doc.get("revision", 0)),
                    )
                    persisted += 1
        return {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "dry_run": dry_run,
            "scanned": scanned,
            "changed": changed,
            "persisted": persisted,
            "details": details,
        }

    def diagnose(self, *, stale_after_hours: float = 24.0) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=stale_after_hours)
        stale_plans = []
        for plan in self.service.store.find("plans"):
            if plan.get("status") not in {"RECORDED", "ACTIVE"}:
                continue
            updated = plan.get("updated_at") or plan.get("created_at")
            bound = [s for s in self.service.store.find("slices", {"family_id": plan["family_id"]}) if s.get("active_plan_id") == plan["entity_id"]]
            if updated and updated < threshold and not bound:
                stale_plans.append({"plan_id": plan["entity_id"], "actor_id": plan["actor_id"], "updated_at": updated})
        open_approvals = [a for a in self.service.store.find("approvals") if a.get("status") == "REQUIRED"]
        suggested_edges = [e for e in self.service.store.find("edges") if e.get("status") == "SUGGESTED"]
        return {
            "declared_id_collisions": self.detect_declared_id_collisions(),
            "stale_plan_candidates": stale_plans,
            "open_approval_count": len(open_approvals),
            "suggested_edge_count": len(suggested_edges),
            "note": "Diagnostics never cancel plans or confirm semantic relations automatically.",
        }
