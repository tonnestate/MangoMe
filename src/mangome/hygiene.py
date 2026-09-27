from __future__ import annotations

import json
import math
import os
import re
from collections import deque
from typing import Any

from .enums import EdgeStatus, RelationType
from .service import MangoMeService

PCH_POLICY_VERSION = "PCH/1"
DEFAULT_ACTIVE_MAX_OBJECTS = 64
HOT_THRESHOLD = 0.72
WARM_THRESHOLD = 0.38

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it", "of",
    "on", "or", "that", "the", "this", "to", "with", "work", "task", "current", "new", "der", "die", "das",
    "den", "dem", "des", "ein", "eine", "einer", "eines", "und", "oder", "ist", "im", "in", "zu", "mit",
    "von", "für", "auf", "wir", "jetzt", "diese", "dieser", "dieses",
}

_VALIDITY_SCORES = {
    "CURRENT": 1.0,
    "REVALIDATED": 1.0,
    "UNKNOWN": 0.65,
    "STALE": 0.25,
    "SOURCE_CHANGED": 0.20,
    "ENVIRONMENT_CHANGED": 0.20,
    "REVALIDATION_REQUIRED": 0.35,
}


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


def _tokens(value: Any) -> set[str]:
    text = str(value or "").lower()
    raw = re.findall(r"[\w-]{2,}", text, flags=re.UNICODE)
    return {token for token in raw if token not in _STOPWORDS and not token.isdigit()}


def _node_text(doc: dict[str, Any]) -> str:
    fields = (
        "title", "objective", "intent", "request_text", "declared_id", "family_key", "work_key",
        "description", "evidence_type", "source", "result", "blocker", "classification",
    )
    parts: list[str] = []
    for key in fields:
        value = doc.get(key)
        if value not in (None, "", [], {}):
            parts.append(str(value))
    for key in ("deliverables", "constraints", "acceptance_criteria", "required_evidence", "expected_scope", "expected_artifacts"):
        value = doc.get(key)
        if isinstance(value, list):
            parts.extend(str(x) for x in value if x not in (None, ""))
    return " ".join(parts)


def _explicit_validity(doc: dict[str, Any]) -> str | None:
    direct = doc.get("validity_status") or doc.get("freshness")
    if direct:
        return str(getattr(direct, "value", direct)).upper()
    for container_key in ("metadata", "payload"):
        container = doc.get(container_key)
        if isinstance(container, dict):
            value = container.get("validity_status") or container.get("freshness")
            if value:
                return str(getattr(value, "value", value)).upper()
    return None


def _band(score: float, *, pinned: bool = False) -> str:
    if pinned or score >= HOT_THRESHOLD:
        return "HOT"
    if score >= WARM_THRESHOLD:
        return "WARM"
    return "COLD"


def _generation(band: str) -> int:
    return {"HOT": 0, "WARM": 1, "COLD": 2}[band]


class CognitiveHygieneService:
    """Deterministic task-relative working-set selection over canonical MangoMe state.

    PCH/1 never mutates canonical truth and never treats temperature as assurance. It computes
    a disposable activation map over existing MangoMe objects, analogous to reachability/working-
    set management: canonical history remains recoverable while only a bounded set is resident in
    the execution projection.
    """

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    def _selected_slice(self, ctx: dict[str, Any], slice_id: str | None) -> dict[str, Any] | None:
        slices = list(ctx.get("slices") or [])
        if slice_id:
            selected = next((s for s in slices if s.get("entity_id") == slice_id), None)
            if selected is None:
                raise KeyError(f"slice {slice_id} is not part of family {ctx['family']['entity_id']}")
            return selected
        active_ids = set(ctx.get("status", {}).get("active_slice_ids") or [])
        active = [s for s in slices if s.get("entity_id") in active_ids]
        if active:
            return max(active, key=lambda s: s.get("last_activity_at") or s.get("started_at") or s.get("created_at"))
        next_ids = list(ctx.get("status", {}).get("next_known_slice_ids") or [])
        if next_ids:
            return next((s for s in slices if s.get("entity_id") == next_ids[0]), None)
        return None

    def _latest_turn_query(self, family_id: str) -> str | None:
        resolver = getattr(self.service, "_work_for_family", None)
        if not callable(resolver) or not hasattr(self.service, "work_context"):
            return None
        work = resolver(family_id)
        if work is None:
            return None
        try:
            wc = self.service.work_context(work["entity_id"])
        except Exception:
            return None
        view = wc.get("work_view") or {}
        turn_id = view.get("latest_turn_id")
        if not turn_id:
            return None
        turn = self.service.store.get("work_turn_bindings", turn_id)
        if not turn:
            return None
        return str(turn.get("request_text") or "").strip() or None

    def _nodes(self, ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {}

        def add(kind: str, doc: dict[str, Any] | None) -> None:
            if not doc or not doc.get("entity_id"):
                return
            nodes[str(doc["entity_id"])] = {"kind": kind, "doc": doc}

        add("FAMILY", ctx.get("family"))
        for item in ctx.get("contracts") or []:
            add("CONTRACT", item)
        for item in ctx.get("specs") or []:
            add("SPEC", item)
        for item in ctx.get("slices") or []:
            add("SLICE", item)
        for item in ctx.get("active_plans") or []:
            add("PLAN", item)
        for item in ctx.get("evidence") or []:
            add("EVIDENCE", item)

        # Active Plans reference Requests; include them as navigation context when present.
        request_ids = {str(p.get("request_id")) for p in ctx.get("active_plans") or [] if p.get("request_id")}
        for request_id in request_ids:
            add("REQUEST", self.service.store.get("requests", request_id))

        # Artifacts are first-class audit/navigation objects. Include only artifacts that are
        # already bound to this family context or referenced by its Evidence; PCH never
        # performs a host-wide artifact scan.
        context_ids = set(nodes)
        artifact_ids = {
            str(e.get("artifact_id")) for e in ctx.get("evidence") or [] if e.get("artifact_id")
        }
        for artifact_id in artifact_ids:
            add("ARTIFACT", self.service.store.get("artifacts", artifact_id))
        for owner_id in list(context_ids):
            for artifact in self.service.store.find("artifacts", {"belongs_to__contains": owner_id}):
                add("ARTIFACT", artifact)
        return nodes

    def _adjacency(self, ctx: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
        adjacency: dict[str, set[str]] = {entity_id: set() for entity_id in nodes}
        relations: list[dict[str, Any]] = []

        def connect(a: str | None, b: str | None, relation: str, *, synthetic: bool = False) -> None:
            if not a or not b or a not in adjacency or b not in adjacency or a == b:
                return
            adjacency[a].add(b)
            adjacency[b].add(a)
            relations.append({"from_id": a, "to_id": b, "relation": relation, "synthetic": synthetic})

        for edge in ctx.get("edges") or []:
            if str(edge.get("status")) != EdgeStatus.CONFIRMED.value:
                continue
            connect(str(edge.get("from_id") or ""), str(edge.get("to_id") or ""), str(edge.get("relation") or "RELATES_TO"))

        for item in ctx.get("specs") or []:
            for contract_id in item.get("contract_ids") or []:
                connect(item.get("entity_id"), contract_id, "SPEC_USES_CONTRACT", synthetic=True)
        for item in ctx.get("slices") or []:
            for contract_id in item.get("contract_ids") or []:
                connect(item.get("entity_id"), contract_id, "SLICE_USES_CONTRACT", synthetic=True)
            for dependency_id in item.get("depends_on") or []:
                connect(item.get("entity_id"), dependency_id, "DEPENDS_ON", synthetic=True)
            connect(item.get("entity_id"), item.get("parent_slice_id"), "PART_OF", synthetic=True)
            connect(item.get("entity_id"), item.get("active_plan_id"), "BOUND_TO_PLAN", synthetic=True)
        for item in ctx.get("active_plans") or []:
            connect(item.get("entity_id"), item.get("spec_id"), "PLAN_USES_SPEC", synthetic=True)
            connect(item.get("entity_id"), item.get("request_id"), "PLAN_FOR_REQUEST", synthetic=True)
            for contract_id in item.get("contract_ids") or []:
                connect(item.get("entity_id"), contract_id, "PLAN_USES_CONTRACT", synthetic=True)
        for item in ctx.get("evidence") or []:
            connect(item.get("entity_id"), item.get("subject_id"), "EVIDENCES", synthetic=True)
            connect(item.get("entity_id"), item.get("artifact_id"), "EVIDENCES_ARTIFACT", synthetic=True)
        for entry in nodes.values():
            if entry.get("kind") != "ARTIFACT":
                continue
            artifact = entry.get("doc") or {}
            for owner_id in artifact.get("belongs_to") or []:
                connect(artifact.get("entity_id"), owner_id, "ARTIFACT_BELONGS_TO", synthetic=True)
        return adjacency, relations

    @staticmethod
    def _distances(adjacency: dict[str, set[str]], roots: set[str]) -> dict[str, int]:
        distances: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque()
        for root in sorted(roots):
            if root in adjacency:
                distances[root] = 0
                queue.append((root, 0))
        while queue:
            node, distance = queue.popleft()
            for neighbor in sorted(adjacency.get(node, set())):
                if neighbor in distances:
                    continue
                distances[neighbor] = distance + 1
                queue.append((neighbor, distance + 1))
        return distances

    def evaluate(
        self,
        family_id: str,
        slice_id: str | None = None,
        *,
        query_text: str | None = None,
        max_active_objects: int | None = None,
        extra_root_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        ctx = self.service.get_context(family_id)
        selected = self._selected_slice(ctx, slice_id)
        nodes = self._nodes(ctx)
        adjacency, relations = self._adjacency(ctx, nodes)
        effective = ctx.get("effective") or {}

        roots: dict[str, list[str]] = {}

        def pin(entity_id: str | None, reason: str) -> None:
            if entity_id and entity_id in nodes:
                roots.setdefault(entity_id, []).append(reason)

        pin(family_id, "FAMILY_IDENTITY")
        pin(ctx.get("family", {}).get("current_spec_id"), "CURRENT_SPEC")
        for entity_id in ctx.get("status", {}).get("active_slice_ids") or []:
            pin(entity_id, "ACTIVE_SLICE")
        for entity_id in effective.get("effective_contract_ids") or []:
            pin(entity_id, "EFFECTIVE_CONTRACT")
        if selected:
            pin(selected.get("entity_id"), "CURRENT_SLICE")
            pin(selected.get("active_plan_id"), "CURRENT_PLAN")
            for entity_id in selected.get("contract_ids") or []:
                pin(entity_id, "CURRENT_SLICE_CONTRACT")
            for entity_id in selected.get("depends_on") or []:
                pin(entity_id, "CURRENT_SLICE_DEPENDENCY")
            for entity_id in selected.get("verification_evidence_ids") or []:
                pin(entity_id, "CURRENT_VERIFICATION_EVIDENCE")
            for entity_id in selected.get("verification_observation_ids") or []:
                pin(entity_id, "CURRENT_VERIFICATION_OBSERVATION")
        for entity_id in extra_root_ids or []:
            pin(str(entity_id), "AUDIT_SCOPE_ROOT")

        root_ids = set(roots)
        distances = self._distances(adjacency, root_ids)
        conflict_ids: set[str] = set()
        superseded_ids = set(effective.get("superseded_contract_ids") or [])
        superseded_context_ids = set(superseded_ids)
        for evidence in ctx.get("evidence") or []:
            if evidence.get("subject_id") in superseded_ids and evidence.get("entity_id"):
                superseded_context_ids.add(str(evidence["entity_id"]))
        for edge in ctx.get("edges") or []:
            if str(edge.get("status")) != EdgeStatus.CONFIRMED.value:
                continue
            if str(edge.get("relation")) == RelationType.CONFLICTS_WITH.value:
                conflict_ids.add(str(edge.get("from_id")))
                conflict_ids.add(str(edge.get("to_id")))

        query = (query_text or self._latest_turn_query(family_id) or "").strip()
        if not query:
            parts = [ctx.get("family", {}).get("title") or ""]
            current_spec_id = ctx.get("family", {}).get("current_spec_id")
            current_spec = next((s for s in ctx.get("specs") or [] if s.get("entity_id") == current_spec_id), None)
            if current_spec:
                parts.append(current_spec.get("objective") or "")
            if selected:
                parts.extend([selected.get("title") or "", selected.get("objective") or ""])
            query = " ".join(x for x in parts if x).strip()
        query_tokens = _tokens(query)

        decisions: list[dict[str, Any]] = []
        for entity_id, entry in nodes.items():
            kind = entry["kind"]
            doc = entry["doc"]
            pinned = entity_id in root_ids
            distance = distances.get(entity_id)
            proximity = 0.0 if distance is None else 1.0 / (1.0 + float(distance))

            node_tokens = _tokens(_node_text(doc))
            lexical = (len(query_tokens & node_tokens) / len(query_tokens)) if query_tokens else 0.0

            operational = 0.55
            if kind == "FAMILY":
                operational = 1.0
            elif kind == "SPEC":
                operational = 1.0 if entity_id == ctx.get("family", {}).get("current_spec_id") else 0.35
            elif kind == "CONTRACT":
                operational = 0.92 if entity_id in set(effective.get("effective_contract_ids") or []) else 0.20
            elif kind == "SLICE":
                state = str(doc.get("execution_state") or "")
                operational = {
                    "ACTIVE": 1.0, "STARTED": 0.90, "BLOCKED": 0.95, "PLANNED": 0.62,
                    "DONE_CLAIMED": 0.72, "PAUSED": 0.55, "CANCELLED": 0.18,
                }.get(state, 0.55)
            elif kind == "PLAN":
                operational = 0.90 if doc.get("status") in {"RECORDED", "ACTIVE"} else 0.25
            elif kind == "REQUEST":
                operational = 0.70
            elif kind == "EVIDENCE":
                operational = 0.68
            elif kind == "ARTIFACT":
                operational = 0.74 if doc.get("exists", True) and doc.get("readable", True) else 0.40

            validity = _explicit_validity(doc)
            freshness = _VALIDITY_SCORES.get(validity or "UNKNOWN", 0.65)
            if entity_id in superseded_context_ids:
                freshness = min(freshness, 0.20)

            support = 0.65
            if kind == "EVIDENCE":
                trust = str(doc.get("trust") or "UNATTESTED")
                verdict = str(doc.get("verdict") or "UNKNOWN")
                trust_score = {"OWNER_ATTESTED": 1.0, "VERIFIER_ATTESTED": 0.92, "UNATTESTED": 0.45}.get(trust, 0.45)
                verdict_score = {"PASS": 1.0, "FAIL": 1.0, "INFO": 0.70, "UNKNOWN": 0.35}.get(verdict, 0.35)
                support = (trust_score + verdict_score) / 2.0

            conflict_boost = 0.12 if entity_id in conflict_ids else 0.0
            revalidation_boost = 0.16 if validity in {"STALE", "SOURCE_CHANGED", "ENVIRONMENT_CHANGED", "REVALIDATION_REQUIRED"} else 0.0
            # Supersession removes default operational authority, but an explicitly targeted historical query
            # may still reactivate the object for inspection/revalidation without restoring its authority.
            superseded_penalty = (0.08 if lexical >= 0.50 else 0.28) if entity_id in superseded_context_ids else 0.0
            size_bytes = _json_size(doc)
            cost_penalty = min(0.10, math.log2(max(2, size_bytes)) / 200.0)

            score = (
                0.34 * proximity
                + 0.22 * lexical
                + 0.18 * operational
                + 0.13 * freshness
                + 0.13 * support
                + conflict_boost
                + revalidation_boost
                - superseded_penalty
                - cost_penalty
            )
            score = max(0.0, min(1.0, score))
            if pinned:
                score = 1.0
            band = _band(score, pinned=pinned)
            decisions.append({
                "entity_id": entity_id,
                "kind": kind,
                "temperature": round(score, 6),
                "band": band,
                "generation": _generation(band),
                "graph_distance": distance,
                "pinned": pinned,
                "pin_reasons": roots.get(entity_id, []),
                "signals": {
                    "proximity": round(proximity, 6),
                    "lexical_relevance": round(lexical, 6),
                    "operational_authority": round(operational, 6),
                    "freshness": round(freshness, 6),
                    "epistemic_support": round(support, 6),
                    "conflict_attention_boost": round(conflict_boost, 6),
                    "revalidation_attention_boost": round(revalidation_boost, 6),
                    "superseded_penalty": round(superseded_penalty, 6),
                    "representation_cost_penalty": round(cost_penalty, 6),
                },
                "validity_status": validity or "UNKNOWN",
                "historical_preserved": True,
            })

        decisions.sort(key=lambda row: (not row["pinned"], -row["temperature"], row["kind"], row["entity_id"]))

        raw_budget = max_active_objects
        if raw_budget is None:
            env = os.environ.get("MANGOME_ACTIVE_MAX_OBJECTS", "").strip()
            raw_budget = int(env) if env else DEFAULT_ACTIVE_MAX_OBJECTS
        configured_budget = max(1, int(raw_budget))
        effective_budget = max(configured_budget, len(root_ids))

        resident_ids: list[str] = []
        for row in decisions:
            if row["pinned"]:
                resident_ids.append(row["entity_id"])
        for row in decisions:
            if row["entity_id"] in resident_ids:
                continue
            if row["band"] == "COLD":
                continue
            if len(resident_ids) >= effective_budget:
                break
            resident_ids.append(row["entity_id"])
        resident_set = set(resident_ids)

        for row in decisions:
            row["resident"] = row["entity_id"] in resident_set
            if row["resident"]:
                row["residency_reason"] = "PINNED" if row["pinned"] else "THERMAL_WORKING_SET"
            elif row["band"] == "COLD":
                row["residency_reason"] = "COLD_NOT_COLLECTED_FROM_HISTORY"
            else:
                row["residency_reason"] = "ACTIVE_BUDGET_EVICTION"

        counts = {band: sum(1 for row in decisions if row["band"] == band) for band in ("HOT", "WARM", "COLD")}
        return {
            "policy": {
                "version": PCH_POLICY_VERSION,
                "temperature_range": [0.0, 1.0],
                "thresholds": {"hot": HOT_THRESHOLD, "warm": WARM_THRESHOLD},
                "configured_active_budget": configured_budget,
                "effective_active_budget": effective_budget,
                "pinned_budget_override": len(root_ids) > configured_budget,
                "principles": [
                    "TEMPERATURE_IS_NOT_TRUTH",
                    "TEMPERATURE_IS_NOT_ASSURANCE",
                    "HISTORICAL_STATE_IS_NOT_DELETED",
                    "PINNED_CANONICAL_ROOTS_ARE_NEVER_EVICTED",
                    "COLD_MEANS_NON_RESIDENT_NOT_FORGOTTEN",
                ],
            },
            "family_id": family_id,
            "slice_id": selected.get("entity_id") if selected else None,
            "task_query": query,
            "roots": [{"entity_id": entity_id, "reasons": reasons} for entity_id, reasons in sorted(roots.items())],
            "working_set_ids": resident_ids,
            "counts": {
                "candidates": len(decisions),
                "resident": len(resident_ids),
                "evicted": len(decisions) - len(resident_ids),
                **{band.lower(): count for band, count in counts.items()},
            },
            "thermal_map": decisions,
            "relations_considered": len(relations),
            "rule": (
                "PCH/1 computes a disposable task-relative working set over canonical MangoMe history. "
                "It may suppress objects from worker context, but it never deletes, verifies, rejects, or rewrites canonical truth."
            ),
        }
