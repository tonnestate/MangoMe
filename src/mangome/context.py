from __future__ import annotations

import json
import os
from typing import Any

from .agent_context import AgentContextCompiler
from .hygiene import CognitiveHygieneService
from .service import MangoMeService
from .truth import BitemporalTruthService


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


def _compact_agent_handle(item: dict[str, Any]) -> dict[str, Any]:
    """Keep an omitted source resolvable without smuggling its text into worker context."""
    return {
        key: item.get(key)
        for key in ("handle", "kind", "criticality", "content_hash", "contract_id", "generation_id", "section_path")
        if item.get(key) not in (None, "")
    }


class ContextCompiler:
    """Deterministic execution-context projection for capacity-aware worker use."""

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

        hygiene = CognitiveHygieneService(self.service).evaluate(
            family_id, selected.get("entity_id") if selected else None
        )
        resident_ids = set(hygiene.get("working_set_ids") or [])

        contract_ids = set(selected.get("contract_ids", [])) if selected else set()
        relevant_contracts = [
            c for c in ctx["contracts"]
            if (not contract_ids or c["entity_id"] in contract_ids) and c["entity_id"] in resident_ids
        ]
        evidence_subjects = {family_id}
        if selected:
            evidence_subjects.add(selected["entity_id"])
        evidence = [
            e for e in ctx["evidence"]
            if e.get("subject_id") in evidence_subjects and e["entity_id"] in resident_ids
        ]
        current_spec = next(
            (x for x in ctx.get("specs", []) if x.get("entity_id") == ctx["family"].get("current_spec_id")),
            None,
        )
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
            "current_spec": current_spec,
            "current_slice": selected,
            "active_plan_id": selected.get("active_plan_id") if selected else None,
            "relevant_contracts": relevant_contracts,
            "evidence": evidence,
            "cognitive_hygiene": {
                "policy": hygiene.get("policy"),
                "task_query": hygiene.get("task_query"),
                "roots": hygiene.get("roots"),
                "working_set_ids": hygiene.get("working_set_ids"),
                "counts": hygiene.get("counts"),
                "relations_considered": hygiene.get("relations_considered"),
                "rule": hygiene.get("rule"),
            },
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

        # v0.3.15 native worker-context compilation.  Contract bodies remain canonical
        # in MongoDB; the agent receives only the exact critical/relevant clause units
        # needed for this task plus metadata-only handles for omitted material.
        payload["agent_context"] = AgentContextCompiler(self.service).compile(
            family_id=family_id,
            family=ctx["family"],
            current_spec=current_spec,
            current_slice=selected,
            relevant_contracts=relevant_contracts,
            task_query=hygiene.get("task_query"),
        )
        payload["instruction"] += (
            " Use agent_context as the default worker projection. When its canonical MongoDB clauses already contain "
            "the required contract truth, do not reread the complete local contract file. Omitted source handles are "
            "metadata references only; expand narrowly when the bounded task actually requires more detail. "
            "If agent_context.routing_signal is not READY, do not execute from the reduced projection; split/route or repair the canonical source first."
        )

        # v0.3 persistence boundary: durable identity/assurance is mandatory context,
        # progressive checkpoints are recoverable but non-normative, and Playbooks are
        # procedural/replaceable. Playbooks never participate in effective truth.
        work = None
        resolver = getattr(self.service, "_work_for_family", None)
        if callable(resolver):
            work = resolver(family_id)
        if work is not None and hasattr(self.service, "work_context"):
            wc = self.service.work_context(work["entity_id"])
            view = wc.get("work_view") or {}
            baseline = (wc.get("canonical") or {}).get("normative_baseline") or {}
            assurance = (wc.get("canonical") or {}).get("assurance_history") or []
            latest_assurance = assurance[-1] if assurance else None
            latest_turn = self.service.store.get("work_turn_bindings", view.get("latest_turn_id")) if view.get("latest_turn_id") else None
            payload["persistence"] = {
                "canonical": {
                    "persistence_level": "CANONICAL",
                    "work_identity": {
                        "entity_id": work.get("entity_id"),
                        "work_key": work.get("work_key"),
                        "status": work.get("status"),
                    },
                    "normative_baseline": {
                        "entity_id": baseline.get("entity_id"),
                        "semantic_hash": baseline.get("semantic_hash"),
                        "source": (baseline.get("semantics") or {}).get("source"),
                    },
                    "turn_binding": {
                        "entity_id": (latest_turn or {}).get("entity_id"),
                        "mode": (latest_turn or {}).get("mode"),
                        "actor_id": (latest_turn or {}).get("actor_id"),
                        "status": (latest_turn or {}).get("status"),
                    } if latest_turn else None,
                    "active_plan_ids": list(view.get("active_plan_ids") or []),
                    "assurance": {
                        "event_count": view.get("assurance_event_count", 0),
                        "cursor": view.get("assurance_cursor"),
                        "latest": None if latest_assurance is None else {
                            "event_type": latest_assurance.get("event_type"),
                            "subject_id": latest_assurance.get("subject_id"),
                            "baseline_id": latest_assurance.get("normative_baseline_id"),
                            "actor_id": latest_assurance.get("actor_id"),
                            "created_at": latest_assurance.get("created_at"),
                        },
                    },
                },
                "progressive": {
                    "persistence_level": "PROGRESSIVE",
                    "latest_checkpoint": (wc.get("progressive") or {}).get("latest_checkpoint"),
                },
                "volatile": {
                    "persistence_level": "VOLATILE",
                    "playbook": (wc.get("volatile") or {}).get("playbook"),
                    "authority": "PROCEDURAL_NON_NORMATIVE",
                },
                "promotion_rule": (
                    "Progressive state can only reference an existing canonical WorkIdentity; "
                    "Discovery/recovery/playbooks never promote themselves to canonical truth."
                ),
            }
            truth = BitemporalTruthService(self.service)
            try:
                truth_state = truth.truth_at(work_ref=work["entity_id"], include_unsupported=True)
                current_truth = []
                for item in truth_state.get("assertions") or []:
                    assertion = item.get("assertion") or {}
                    if assertion.get("entity_id") not in resident_ids:
                        continue
                    current_truth.append({
                        "entity_id": assertion.get("entity_id"),
                        "assertion_key": assertion.get("assertion_key"),
                        "subject_id": assertion.get("subject_id"),
                        "predicate": assertion.get("predicate"),
                        "value": assertion.get("value"),
                        "valid_from": assertion.get("valid_from"),
                        "valid_to": assertion.get("valid_to"),
                        "known_from": assertion.get("known_from"),
                        "known_to": assertion.get("known_to"),
                        "support_state": item.get("support_state"),
                    })
                payload["bitemporal_truth"] = {
                    "protocol": "BTTM/1",
                    "current_resident_assertions": current_truth,
                    "rule": "Truth maintenance decides supportability; Cognitive Hygiene independently decides residency.",
                }
            except Exception:
                payload["bitemporal_truth"] = {
                    "protocol": "BTTM/1",
                    "current_resident_assertions": [],
                    "rule": "Truth layer unavailable in this projection; never synthesize truth from worker judgment.",
                }
            payload["instruction"] += (
                " WorkIdentity, normative baseline bindings and assurance history are canonical. "
                "Progressive checkpoints and Playbooks must never overwrite or reconstruct them. "
                "BTTM supportability and PCH activation are separate dimensions."
            )

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
                "truncated": False, "omitted_evidence": 0, "omitted_agent_facts": 0,
            }
            final_bytes = _json_bytes(payload)
            if final_bytes <= budget:
                payload["context_budget"]["compiled_bytes"] = final_bytes
                return payload
            # Budget metadata itself is optional transport telemetry. Never make an
            # otherwise compliant execution projection exceed the hard envelope.
            payload.pop("context_budget", None)
            return payload

        # Never truncate normative state, current Slice identity, gates, acceptance semantics,
        # or MAC/1 C0/C1 units. PCH/1 telemetry and optional agent facts are disposable.
        hygiene_projection = payload.get("cognitive_hygiene") or {}
        if hygiene_projection:
            policy = hygiene_projection.get("policy") or {}
            payload["cognitive_hygiene"] = {
                "policy": {
                    "version": policy.get("version"),
                    "configured_active_budget": policy.get("configured_active_budget"),
                    "effective_active_budget": policy.get("effective_active_budget"),
                    "pinned_budget_override": policy.get("pinned_budget_override"),
                },
                "counts": hygiene_projection.get("counts"),
                "rule": "COLD means non-resident, never deleted; temperature is not truth or assurance.",
            }

        # Remove bulky optional Evidence/Contract storage detail first.
        payload["evidence"] = [_compact_evidence(item) for item in payload["evidence"]]
        payload["relevant_contracts"] = [_compact_contract(item) for item in payload["relevant_contracts"]]
        omitted = 0
        omitted_agent_facts = 0

        # MAC/1 already performs model-targeted selection. If the outer transport envelope is
        # tighter still, fold only optional worker facts behind metadata handles. Critical
        # C0/C1 text remains resident and therefore fail-closed if it cannot fit.
        agent = payload.get("agent_context") or {}
        if _json_bytes(payload) > max(0, budget - 512) and agent:
            handles = list(agent.get("expandable_handles") or [])
            facts = list(agent.get("facts") or [])
            while facts and _json_bytes(payload) > max(0, budget - 512):
                item = facts.pop()
                metadata = item.get("metadata") or {}
                handles.append(_compact_agent_handle({
                    "handle": item.get("id"),
                    "kind": item.get("kind"),
                    "criticality": item.get("criticality"),
                    "content_hash": metadata.get("content_hash"),
                    **metadata,
                }))
                omitted_agent_facts += 1
                agent["facts"] = facts
                agent["expandable_handles"] = handles
            agent["transport"] = {
                "optional_facts_folded": omitted_agent_facts,
                "critical_units_dropped": 0,
                "rule": "OUTER_TRANSPORT_MAY_FOLD_OPTIONAL_FACTS_BUT_NEVER_MAC_C0_C1",
            }

        if _json_bytes(payload) > max(0, budget - 512) and agent.get("expandable_handles"):
            agent["expandable_handles"] = [_compact_agent_handle(item) for item in agent["expandable_handles"]]

        # Context reduction order continues with volatile -> progressive detail -> old evidence.
        # Canonical WorkIdentity/baseline/assurance summary is never removed.
        if _json_bytes(payload) > max(0, budget - 512) and payload.get("persistence"):
            volatile = payload["persistence"].get("volatile") or {}
            if volatile.get("playbook") is not None:
                playbook = volatile.get("playbook") or {}
                volatile["playbook"] = {
                    "entity_id": playbook.get("entity_id"),
                    "playbook_key": playbook.get("playbook_key"),
                    "version": playbook.get("version"),
                    "content_hash": playbook.get("content_hash"),
                }
        if _json_bytes(payload) > max(0, budget - 512) and payload.get("persistence"):
            checkpoint = (payload["persistence"].get("progressive") or {}).get("latest_checkpoint")
            if isinstance(checkpoint, dict) and checkpoint.get("payload") is not None:
                checkpoint = dict(checkpoint)
                checkpoint["payload"] = {"omitted": True}
                payload["persistence"]["progressive"]["latest_checkpoint"] = checkpoint
        while payload["evidence"] and _json_bytes(payload) > max(0, budget - 512):
            payload["evidence"].pop(0)
            omitted += 1
        # Expandable handles are useful but non-normative.  Drop them before ever dropping
        # critical text when the hard byte envelope is exceptionally small.
        while agent.get("expandable_handles") and _json_bytes(payload) > max(0, budget - 512):
            agent["expandable_handles"].pop()
            agent.setdefault("transport", {})["handles_omitted_for_byte_envelope"] = (
                int(agent.get("transport", {}).get("handles_omitted_for_byte_envelope") or 0) + 1
            )

        compiled_bytes = _json_bytes(payload)
        if compiled_bytes > budget:
            raise ContextBudgetExceeded(
                f"mandatory MangoMe execution context requires {compiled_bytes} bytes, budget is {budget}; "
                "critical MAC/1 truth was not truncated; route to a larger context or narrow/split the execution scope"
            )
        payload["context_budget"] = {
            "max_bytes": budget, "original_bytes": original_bytes, "compiled_bytes": compiled_bytes,
            "truncated": True, "omitted_evidence": omitted, "omitted_agent_facts": omitted_agent_facts,
            "rule": "Canonical truth and MAC/1 C0/C1 are never truncated; only disposable execution projection detail is bounded.",
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
