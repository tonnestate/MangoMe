from __future__ import annotations

import json
import os
from typing import Any

from .service import MangoMeService


class ContextBudgetExceeded(RuntimeError):
    """The mandatory execution projection alone exceeds the configured transport envelope."""


def _json_bytes(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))


def _compact_contract(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in ("entity_id", "declared_id", "family_id", "title", "kind", "schema_version", "revision")
        if key in item
    }


def _compact_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.get(key)
        for key in (
            "entity_id", "subject_id", "evidence_type", "evidence_class", "source", "result",
            "verdict", "trust", "artifact_id", "actor_id", "attested_by", "attested_at", "created_at",
        )
        if key in item
    }


class ContextCompiler:
    """Deterministic execution-context projection for IntakeGov/CogC downstream use."""

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    def compile(self, family_id: str, slice_id: str | None = None, max_bytes: int | None = None) -> dict:
        ctx = self.service.get_context(family_id)
        slices = ctx["slices"]
        selected = None
        if slice_id:
            selected = next((s for s in slices if s["entity_id"] == slice_id), None)
            if selected is None:
                raise KeyError(f"slice {slice_id} is not part of family {family_id}")
        else:
            active = [s for s in slices if s["entity_id"] in ctx["status"].get("active_slice_ids", [])]
            if active:
                selected = max(active, key=lambda s: s.get("last_activity_at") or s.get("started_at") or s["created_at"])
            elif ctx["status"].get("next_known_slice_ids"):
                next_id = ctx["status"]["next_known_slice_ids"][0]
                selected = next((s for s in slices if s["entity_id"] == next_id), None)

        contract_ids = set(selected.get("contract_ids", [])) if selected else set()
        relevant_contracts = [c for c in ctx["contracts"] if not contract_ids or c["entity_id"] in contract_ids]
        evidence_subjects = {family_id}
        if selected:
            evidence_subjects.add(selected["entity_id"])
        evidence = [e for e in ctx["evidence"] if e.get("subject_id") in evidence_subjects]
        payload = {
            "family": {
                "entity_id": ctx["family"]["entity_id"],
                "family_key": ctx["family"]["family_key"],
                "title": ctx["family"]["title"],
                "scope_ids": ctx["family"].get("scope_ids", []),
            },
            "current_state": ctx["status"],
            "truth_level": ctx["status"].get("truth_level", "CANONICAL_UNVERIFIED"),
            "truth_boundary": {
                "discovery": "CANDIDATE_ONLY",
                "execution_state": ctx["status"].get("execution_state"),
                "assurance_state": ctx["status"].get("assurance_state"),
                "done_claimed_is_verified": False,
                "verification": "CAPABILITY_REQUIRED",
                "acceptance": "OWNER_CAPABILITY_REQUIRED",
            },
            "effective_family": ctx["effective"],
            "current_spec": next((x for x in ctx.get("specs", []) if x.get("entity_id") == ctx["family"].get("current_spec_id")), None),
            "current_slice": selected,
            "active_plan_id": selected.get("active_plan_id") if selected else None,
            "relevant_contracts": relevant_contracts,
            "evidence": evidence,
            "instruction": (
                "Treat worker completion statements as claims. Mutations must stay bound to the active plan. "
                "Do not infer VERIFIED from DONE_CLAIMED and do not treat un-attested evidence as verification proof."
            ),
            "presentation_policy": {
                "slices": "INTERNAL_ONLY",
                "plans": "INTERNAL_ONLY",
                "user_result": "OUTCOME_FINDINGS_EVIDENCE_ONLY",
            },
        }

        configured = max_bytes
        if configured is None:
            raw = os.environ.get("MANGOME_CONTEXT_MAX_BYTES", "").strip()
            configured = int(raw) if raw else None
        if configured is None or configured <= 0:
            return payload

        original_bytes = _json_bytes(payload)
        budget = int(configured)
        if original_bytes <= budget:
            payload["context_budget"] = {
                "max_bytes": budget, "original_bytes": original_bytes, "compiled_bytes": original_bytes,
                "truncated": False, "omitted_evidence": 0,
            }
            final_bytes = _json_bytes(payload)
            if final_bytes <= budget:
                payload["context_budget"]["compiled_bytes"] = final_bytes
                return payload
            # Budget metadata itself is optional transport telemetry. Never make an
            # otherwise compliant execution projection exceed the hard envelope.
            payload.pop("context_budget", None)
            return payload

        # Never truncate normative state, current Slice identity, gates or acceptance semantics.
        # First remove bulky optional Evidence payloads and Contract storage detail.
        payload["evidence"] = [_compact_evidence(item) for item in payload["evidence"]]
        payload["relevant_contracts"] = [_compact_contract(item) for item in payload["relevant_contracts"]]
        omitted = 0
        while payload["evidence"] and _json_bytes(payload) > max(0, budget - 512):
            payload["evidence"].pop(0)
            omitted += 1
        compiled_bytes = _json_bytes(payload)
        if compiled_bytes > budget:
            raise ContextBudgetExceeded(
                f"mandatory MangoMe execution context requires {compiled_bytes} bytes, budget is {budget}; "
                "increase MANGOME_CONTEXT_MAX_BYTES or narrow the requested execution scope"
            )
        payload["context_budget"] = {
            "max_bytes": budget, "original_bytes": original_bytes, "compiled_bytes": compiled_bytes,
            "truncated": True, "omitted_evidence": omitted,
            "rule": "Canonical truth is never truncated; only this disposable execution projection is bounded.",
        }
        final_bytes = _json_bytes(payload)
        payload["context_budget"]["compiled_bytes"] = final_bytes
        final_bytes = _json_bytes(payload)
        if final_bytes > budget:
            raise ContextBudgetExceeded(
                f"bounded MangoMe execution context requires {final_bytes} bytes after budget metadata, budget is {budget}"
            )
        payload["context_budget"]["compiled_bytes"] = final_bytes
        return payload
