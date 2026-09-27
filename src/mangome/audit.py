from __future__ import annotations

from typing import Any

from .enums import EdgeStatus
from .ids import new_id
from .models import utcnow
from .schema import CURRENT_SCHEMA_VERSION
from .service import MangoMeError, MangoMeService

SRA_POLICY_VERSION = "SRA/1"
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_OBJECTS = 64
DEFAULT_FRONTIER_LIMIT = 16

AUDIT_KINDS = {
    "CLASSIFICATION", "ARCHITECTURE", "ARTIFACT", "CODE_REVIEW", "INCIDENT",
    "RECONCILIATION", "IMPACT", "SECURITY", "GENERAL",
}
AUDIT_MODES = {"READ_ONLY", "REPAIR_WITHIN_SCOPE"}
FINDING_CLASSES = {"NO_ISSUE", "INFO", "ISSUE", "CONFLICT", "ASSUMPTION", "UNKNOWN"}
IMPACT_LEVELS = {"NONE", "LOCAL", "EXPAND", "OUTSIDE_SCOPE"}

# These are traversal permissions, not truth semantics. Only CONFIRMED persisted edges
# and deterministic structural references are traversed. The caller can narrow this set.
DEFAULT_EXPANSION_RELATIONS = {
    "ADDS_TO", "AMENDS", "EXTENDS", "REPAIRS", "RECOVERS", "SUPERSEDES",
    "CONFLICTS_WITH", "VALIDATES", "IMPLEMENTS", "PART_OF", "EXPOSED_BY", "RELATES_TO",
    "DEPENDS_ON", "BOUND_TO_PLAN", "PLAN_USES_SPEC", "PLAN_FOR_REQUEST", "PLAN_USES_CONTRACT",
    "SPEC_USES_CONTRACT", "SLICE_USES_CONTRACT", "EVIDENCES", "ARTIFACT_BELONGS_TO",
    "FAMILY_HAS_CONTRACT", "FAMILY_HAS_SPEC", "FAMILY_HAS_SLICE", "FAMILY_HAS_PLAN",
    "FAMILY_HAS_WORK", "WORK_HAS_BASELINE", "WORK_HAS_ASSURANCE_EVENT",
}

_ENTITY_COLLECTIONS = (
    "families", "contracts", "specs", "slices", "plans", "requests", "evidence", "artifacts",
    "work_identities", "normative_baselines", "assurance_events", "work_checkpoints",
)


class ScopedAuditError(MangoMeError):
    pass


def _base_doc() -> dict[str, Any]:
    now = utcnow()
    return {
        "entity_id": new_id(),
        "schema_version": CURRENT_SCHEMA_VERSION,
        "revision": 0,
        "created_at": now,
        "updated_at": now,
    }


def _unique(values: list[str] | None) -> list[str]:
    return list(dict.fromkeys(str(v).strip() for v in (values or []) if str(v).strip()))


class ScopedAuditService:
    """Bounded recursive audit over MangoMe's existing persistent graph.

    SRA/1 starts from a local scope, persists observations, and expands only when a
    finding identifies material impact. Expansion follows confirmed graph/structural
    relations until no pending frontier remains or an explicit depth/object budget is
    reached. It never equates audit closure with VERIFIED system truth.
    """

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    # ---------- identity / scope helpers ----------
    def _locate(self, entity_id: str) -> tuple[str, dict[str, Any]] | None:
        for collection in _ENTITY_COLLECTIONS:
            row = self.service.store.get(collection, entity_id)
            if row is not None:
                return collection, row
        return None

    def _family_for(self, entity_id: str, seen: set[str] | None = None) -> str | None:
        seen = set(seen or set())
        if entity_id in seen:
            return None
        seen.add(entity_id)
        located = self._locate(entity_id)
        if located is None:
            return None
        collection, row = located
        if collection == "families":
            return entity_id
        direct = row.get("family_id")
        if direct:
            return str(direct)
        if collection == "work_identities":
            return str(row.get("family_id") or "") or None
        if collection in {"normative_baselines", "assurance_events", "work_checkpoints"}:
            work_id = row.get("work_id")
            if work_id:
                work = self.service.store.get("work_identities", str(work_id))
                return str((work or {}).get("family_id") or "") or None
        if collection == "evidence":
            subject_id = row.get("subject_id")
            return self._family_for(str(subject_id), seen) if subject_id else None
        if collection == "artifacts":
            for owner_id in row.get("belongs_to") or []:
                resolved = self._family_for(str(owner_id), seen)
                if resolved:
                    return resolved
        return None

    def _require_same_family(self, family_id: str, entity_id: str) -> None:
        located = self._locate(entity_id)
        if located is None:
            raise ScopedAuditError(f"unknown audit scope entity {entity_id}")
        owner_family = self._family_for(entity_id)
        if owner_family != family_id:
            raise ScopedAuditError(
                f"audit scope entity {entity_id} is outside family {family_id}; report it as an outside-scope impact instead"
            )

    def _work_and_turn(self, family_id: str, actor_id: str, turn_id: str | None) -> dict[str, Any] | None:
        resolver = getattr(self.service, "_work_for_family", None)
        work = resolver(family_id) if callable(resolver) else None
        if work is not None:
            require_turn = getattr(self.service, "_require_work_turn", None)
            if callable(require_turn):
                require_turn(
                    work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id,
                    allowed_modes={"VERIFY", "EXECUTE", "CONTINUE"},
                )
        return work

    # ---------- graph traversal ----------
    def _neighbors(self, entity_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []

        def add(neighbor_id: str | None, relation: str) -> None:
            if not neighbor_id or str(neighbor_id) == entity_id:
                return
            rows.append({"entity_id": str(neighbor_id), "relation": str(relation).upper()})

        # Persisted graph edges are authoritative only when CONFIRMED.
        edge_rows = (
            self.service.store.find("edges", {"from_id": entity_id})
            + self.service.store.find("edges", {"to_id": entity_id})
        )
        for edge in edge_rows:
            if str(edge.get("status")) != EdgeStatus.CONFIRMED.value:
                continue
            if edge.get("from_id") == entity_id:
                add(edge.get("to_id"), str(edge.get("relation") or "RELATES_TO"))
            else:
                add(edge.get("from_id"), str(edge.get("relation") or "RELATES_TO"))

        located = self._locate(entity_id)
        if located is None:
            return []
        collection, row = located

        if collection == "families":
            for cid in row.get("contract_ids") or []:
                add(cid, "FAMILY_HAS_CONTRACT")
            for sid in row.get("spec_ids") or []:
                add(sid, "FAMILY_HAS_SPEC")
            for sid in row.get("slice_ids") or []:
                add(sid, "FAMILY_HAS_SLICE")
            for plan in self.service.store.find("plans", {"family_id": entity_id}):
                add(plan.get("entity_id"), "FAMILY_HAS_PLAN")
            work_rows = self.service.store.find("work_identities", {"family_id": entity_id})
            for work in work_rows:
                add(work.get("entity_id"), "FAMILY_HAS_WORK")

        elif collection == "contracts":
            add(row.get("family_id"), "FAMILY_HAS_CONTRACT")
            for spec in self.service.store.find("specs", {"contract_ids__contains": entity_id}):
                add(spec.get("entity_id"), "SPEC_USES_CONTRACT")
            for sl in self.service.store.find("slices", {"contract_ids__contains": entity_id}):
                add(sl.get("entity_id"), "SLICE_USES_CONTRACT")
            for plan in self.service.store.find("plans", {"contract_ids__contains": entity_id}):
                add(plan.get("entity_id"), "PLAN_USES_CONTRACT")

        elif collection == "specs":
            add(row.get("family_id"), "FAMILY_HAS_SPEC")
            for cid in row.get("contract_ids") or []:
                add(cid, "SPEC_USES_CONTRACT")
            for plan in self.service.store.find("plans", {"spec_id": entity_id}):
                add(plan.get("entity_id"), "PLAN_USES_SPEC")

        elif collection == "slices":
            add(row.get("family_id"), "FAMILY_HAS_SLICE")
            for cid in row.get("contract_ids") or []:
                add(cid, "SLICE_USES_CONTRACT")
            for dep in row.get("depends_on") or []:
                add(dep, "DEPENDS_ON")
            add(row.get("parent_slice_id"), "PART_OF")
            add(row.get("active_plan_id") or row.get("last_plan_id"), "BOUND_TO_PLAN")
            for ev in self.service.store.find("evidence", {"subject_id": entity_id}):
                add(ev.get("entity_id"), "EVIDENCES")
            for artifact in self.service.store.find("artifacts", {"belongs_to__contains": entity_id}):
                add(artifact.get("entity_id"), "ARTIFACT_BELONGS_TO")

        elif collection == "plans":
            add(row.get("family_id"), "FAMILY_HAS_PLAN")
            add(row.get("request_id"), "PLAN_FOR_REQUEST")
            add(row.get("spec_id"), "PLAN_USES_SPEC")
            for cid in row.get("contract_ids") or []:
                add(cid, "PLAN_USES_CONTRACT")

        elif collection == "requests":
            add(row.get("family_id"), "PLAN_FOR_REQUEST")
            for plan in self.service.store.find("plans", {"request_id": entity_id}):
                add(plan.get("entity_id"), "PLAN_FOR_REQUEST")

        elif collection == "evidence":
            add(row.get("subject_id"), "EVIDENCES")
            add(row.get("artifact_id"), "ARTIFACT_BELONGS_TO")

        elif collection == "artifacts":
            for owner_id in row.get("belongs_to") or []:
                add(owner_id, "ARTIFACT_BELONGS_TO")
            for ev in self.service.store.find("evidence", {"artifact_id": entity_id}):
                add(ev.get("entity_id"), "EVIDENCES")

        elif collection == "work_identities":
            add(row.get("family_id"), "FAMILY_HAS_WORK")
            for baseline in self.service.store.find("normative_baselines", {"work_id": entity_id}):
                add(baseline.get("entity_id"), "WORK_HAS_BASELINE")
            for event in self.service.store.find("assurance_events", {"work_id": entity_id}):
                add(event.get("entity_id"), "WORK_HAS_ASSURANCE_EVENT")

        elif collection == "normative_baselines":
            add(row.get("work_id"), "WORK_HAS_BASELINE")

        elif collection == "assurance_events":
            add(row.get("work_id"), "WORK_HAS_ASSURANCE_EVENT")
            add(row.get("subject_id"), "RELATES_TO")

        # Deterministic de-duplication while preserving relation evidence.
        seen: set[tuple[str, str]] = set()
        result: list[dict[str, str]] = []
        for item in rows:
            key = (item["entity_id"], item["relation"])
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    # ---------- lifecycle ----------
    def start(
        self,
        *,
        family_id: str,
        actor_id: str,
        objective: str,
        audit_kind: str = "GENERAL",
        mode: str = "READ_ONLY",
        target_ids: list[str] | None = None,
        target_refs: list[str] | None = None,
        slice_id: str | None = None,
        plan_id: str | None = None,
        mutation_scope_ids: list[str] | None = None,
        mutation_scope_refs: list[str] | None = None,
        assumptions: list[str] | None = None,
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_objects: int = DEFAULT_MAX_OBJECTS,
        expansion_relations: list[str] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        family = self.service._must_get("families", family_id)
        work = self._work_and_turn(family_id, actor_id, turn_id)
        kind = str(audit_kind).strip().upper()
        if kind not in AUDIT_KINDS:
            raise ScopedAuditError(f"unsupported audit_kind {audit_kind!r}; expected one of {sorted(AUDIT_KINDS)}")
        normalized_mode = str(mode).strip().upper()
        if normalized_mode not in AUDIT_MODES:
            raise ScopedAuditError(f"unsupported audit mode {mode!r}; expected one of {sorted(AUDIT_MODES)}")
        if max_depth < 0:
            raise ScopedAuditError("max_depth must be >= 0")
        if max_objects < 1:
            raise ScopedAuditError("max_objects must be >= 1")

        seeds = _unique(target_ids)
        refs = _unique(target_refs)
        if slice_id:
            self._require_same_family(family_id, slice_id)
            seeds = _unique([slice_id, *seeds])
        if plan_id:
            self._require_same_family(family_id, plan_id)
            plan = self.service._must_get("plans", plan_id)
            if plan.get("actor_id") != actor_id:
                raise ScopedAuditError("audit plan belongs to another actor")

        if not seeds and not refs:
            active_ids = list((family.get("current") or {}).get("active_slice_ids") or [])
            if active_ids:
                seeds = [active_ids[0]]
            elif family.get("current_spec_id"):
                seeds = [str(family["current_spec_id"])]
            else:
                seeds = [family_id]

        if len(seeds) + len(refs) > max_objects:
            raise ScopedAuditError("initial audit scope exceeds max_objects")
        for entity_id in seeds:
            self._require_same_family(family_id, entity_id)

        mutation_ids = _unique(mutation_scope_ids)
        mutation_refs = _unique(mutation_scope_refs)
        if normalized_mode == "READ_ONLY" and (mutation_ids or mutation_refs):
            raise ScopedAuditError("READ_ONLY audit cannot declare a mutation scope")
        if normalized_mode == "REPAIR_WITHIN_SCOPE":
            for entity_id in mutation_ids:
                self._require_same_family(family_id, entity_id)
            outside_initial = [x for x in mutation_ids if x not in seeds]
            outside_refs = [x for x in mutation_refs if x not in refs]
            if outside_initial or outside_refs:
                raise ScopedAuditError("mutation scope must be a subset of the initial explicit audit scope")

        allowed_relations = _unique(expansion_relations) or sorted(DEFAULT_EXPANSION_RELATIONS)
        unknown_relations = [r for r in allowed_relations if r not in DEFAULT_EXPANSION_RELATIONS]
        if unknown_relations:
            raise ScopedAuditError(f"unsupported expansion relations: {unknown_relations}")

        doc = {
            **_base_doc(),
            "policy_version": SRA_POLICY_VERSION,
            "family_id": family_id,
            "work_id": (work or {}).get("entity_id"),
            "turn_id": turn_id,
            "plan_id": plan_id,
            "slice_id": slice_id,
            "actor_id": actor_id,
            "objective": str(objective).strip(),
            "audit_kind": kind,
            "mode": normalized_mode,
            "status": "ACTIVE",
            "closure_state": "OPEN",
            "initial_scope_ids": list(seeds),
            "current_scope_ids": list(seeds),
            "pending_ids": list(seeds),
            "inspected_ids": [],
            "initial_scope_refs": list(refs),
            "current_scope_refs": list(refs),
            "pending_refs": list(refs),
            "inspected_refs": [],
            "depth_by_id": {entity_id: 0 for entity_id in seeds},
            "depth_by_ref": {ref: 0 for ref in refs},
            "mutation_scope_ids": list(mutation_ids),
            "mutation_scope_refs": list(mutation_refs),
            "assumptions": _unique(assumptions),
            "max_depth": int(max_depth),
            "max_objects": int(max_objects),
            "expansion_relations": allowed_relations,
            "expansion_history": [],
            "boundary_events": [],
            "persistence_level": "CANONICAL",
        }
        saved = self.service.store.insert("audit_runs", doc)
        return self.context(saved["entity_id"])

    def _closure_state(self, run: dict[str, Any]) -> str:
        if run.get("pending_ids") or run.get("pending_refs"):
            return "OPEN"
        limit_reasons = {"DEPTH_LIMIT", "OBJECT_BUDGET"}
        if any(str(event.get("reason")) in limit_reasons for event in run.get("boundary_events") or []):
            return "BOUNDED_FIXPOINT"
        return "FIXPOINT_REACHED"

    def _next_frontier(self, run: dict[str, Any], limit: int = DEFAULT_FRONTIER_LIMIT) -> dict[str, Any]:
        ids = list(run.get("pending_ids") or [])[: max(1, int(limit))]
        refs = list(run.get("pending_refs") or [])[: max(1, int(limit))]
        return {
            "ids": [self._describe_entity(entity_id) for entity_id in ids],
            "refs": refs,
        }

    def _describe_entity(self, entity_id: str) -> dict[str, Any]:
        located = self._locate(entity_id)
        if located is None:
            return {"entity_id": entity_id, "collection": "UNKNOWN", "missing": True}
        collection, row = located
        return {
            "entity_id": entity_id,
            "collection": collection,
            "title": row.get("title") or row.get("logical_name") or row.get("declared_id") or row.get("work_key"),
            "state": row.get("execution_state") or row.get("status") or row.get("assurance_state"),
            "revision": row.get("revision", 0),
        }

    def status(self, audit_id: str, *, frontier_limit: int = DEFAULT_FRONTIER_LIMIT) -> dict[str, Any]:
        run = self.service._must_get("audit_runs", audit_id)
        closure = self._closure_state(run)
        findings = self.service.store.find("audit_findings", {"audit_id": audit_id})
        return {
            "audit_id": audit_id,
            "policy_version": run.get("policy_version"),
            "status": run.get("status"),
            "closure_state": closure,
            "closure_ready": closure != "OPEN",
            "family_id": run.get("family_id"),
            "work_id": run.get("work_id"),
            "actor_id": run.get("actor_id"),
            "audit_kind": run.get("audit_kind"),
            "mode": run.get("mode"),
            "objective": run.get("objective"),
            "counts": {
                "scope_ids": len(run.get("current_scope_ids") or []),
                "scope_refs": len(run.get("current_scope_refs") or []),
                "pending_ids": len(run.get("pending_ids") or []),
                "pending_refs": len(run.get("pending_refs") or []),
                "inspected_ids": len(run.get("inspected_ids") or []),
                "inspected_refs": len(run.get("inspected_refs") or []),
                "findings": len(findings),
                "boundary_events": len(run.get("boundary_events") or []),
            },
            "next_frontier": self._next_frontier(run, frontier_limit),
            "boundary_events": list(run.get("boundary_events") or []),
            "rule": "Audit closure proves bounded scope closure, never global system correctness or VERIFIED assurance.",
        }

    def mutation_allowed(self, audit_id: str, *, entity_id: str | None = None, ref: str | None = None) -> dict[str, Any]:
        run = self.service._must_get("audit_runs", audit_id)
        if run.get("mode") != "REPAIR_WITHIN_SCOPE":
            return {"allowed": False, "reason": "AUDIT_READ_ONLY"}
        if entity_id is not None:
            return {
                "allowed": entity_id in set(run.get("mutation_scope_ids") or []),
                "reason": "EXPLICIT_MUTATION_SCOPE" if entity_id in set(run.get("mutation_scope_ids") or []) else "OUTSIDE_MUTATION_SCOPE",
            }
        if ref is not None:
            return {
                "allowed": ref in set(run.get("mutation_scope_refs") or []),
                "reason": "EXPLICIT_MUTATION_SCOPE" if ref in set(run.get("mutation_scope_refs") or []) else "OUTSIDE_MUTATION_SCOPE",
            }
        raise ScopedAuditError("entity_id or ref is required")

    def record_finding(
        self,
        *,
        audit_id: str,
        actor_id: str,
        summary: str,
        finding_class: str,
        impact: str = "NONE",
        subject_id: str | None = None,
        subject_ref: str | None = None,
        evidence_ids: list[str] | None = None,
        affected_ids: list[str] | None = None,
        affected_refs: list[str] | None = None,
        assumptions: list[str] | None = None,
        unknowns: list[str] | None = None,
    ) -> dict[str, Any]:
        run = self.service._must_get("audit_runs", audit_id)
        if run.get("status") != "ACTIVE":
            raise ScopedAuditError(f"audit {audit_id} is not ACTIVE")
        if run.get("actor_id") != actor_id:
            raise ScopedAuditError("audit finding actor does not own this audit run")
        self._work_and_turn(run["family_id"], actor_id, run.get("turn_id"))
        if bool(subject_id) == bool(subject_ref):
            raise ScopedAuditError("provide exactly one of subject_id or subject_ref")
        if subject_id and subject_id not in set(run.get("current_scope_ids") or []):
            raise ScopedAuditError("finding subject_id is outside current audit scope")
        if subject_ref and subject_ref not in set(run.get("current_scope_refs") or []):
            raise ScopedAuditError("finding subject_ref is outside current audit scope")

        fclass = str(finding_class).strip().upper()
        if fclass not in FINDING_CLASSES:
            raise ScopedAuditError(f"unsupported finding_class {finding_class!r}; expected one of {sorted(FINDING_CLASSES)}")
        impact_level = str(impact).strip().upper()
        if impact_level not in IMPACT_LEVELS:
            raise ScopedAuditError(f"unsupported impact {impact!r}; expected one of {sorted(IMPACT_LEVELS)}")

        ev_ids = _unique(evidence_ids)
        for evidence_id in ev_ids:
            if self.service.store.get("evidence", evidence_id) is None:
                raise ScopedAuditError(f"unknown evidence {evidence_id}")

        explicit_affected_ids = _unique(affected_ids)
        explicit_affected_refs = _unique(affected_refs)
        finding = self.service.store.insert("audit_findings", {
            **_base_doc(),
            "audit_id": audit_id,
            "family_id": run["family_id"],
            "work_id": run.get("work_id"),
            "actor_id": actor_id,
            "subject_id": subject_id,
            "subject_ref": subject_ref,
            "finding_class": fclass,
            "impact": impact_level,
            "summary": str(summary).strip(),
            "evidence_ids": ev_ids,
            "affected_ids": explicit_affected_ids,
            "affected_refs": explicit_affected_refs,
            "assumptions": _unique(assumptions),
            "unknowns": _unique(unknowns),
            "persistence_level": "CANONICAL",
        })

        current_ids = list(run.get("current_scope_ids") or [])
        pending_ids = [x for x in run.get("pending_ids") or [] if x != subject_id]
        inspected_ids = _unique([*(run.get("inspected_ids") or []), *([subject_id] if subject_id else [])])
        current_refs = list(run.get("current_scope_refs") or [])
        pending_refs = [x for x in run.get("pending_refs") or [] if x != subject_ref]
        inspected_refs = _unique([*(run.get("inspected_refs") or []), *([subject_ref] if subject_ref else [])])
        depth_by_id = dict(run.get("depth_by_id") or {})
        depth_by_ref = dict(run.get("depth_by_ref") or {})
        boundary_events = list(run.get("boundary_events") or [])
        expansion_history = list(run.get("expansion_history") or [])
        expanded_ids: list[str] = []
        expanded_refs: list[str] = []

        total_scope = lambda: len(current_ids) + len(current_refs)

        def boundary(reason: str, candidate: str, relation: str | None, depth: int | None) -> None:
            boundary_events.append({
                "reason": reason,
                "candidate": candidate,
                "relation": relation,
                "depth": depth,
                "finding_id": finding["entity_id"],
            })

        def try_add_id(candidate: str, relation: str, depth: int) -> None:
            if candidate in current_ids:
                return
            if depth > int(run.get("max_depth", DEFAULT_MAX_DEPTH)):
                boundary("DEPTH_LIMIT", candidate, relation, depth)
                return
            located = self._locate(candidate)
            if located is None:
                boundary("UNKNOWN_ENTITY", candidate, relation, depth)
                return
            owner_family = self._family_for(candidate)
            if owner_family != run["family_id"]:
                boundary("OUTSIDE_FAMILY", candidate, relation, depth)
                return
            if total_scope() >= int(run.get("max_objects", DEFAULT_MAX_OBJECTS)):
                boundary("OBJECT_BUDGET", candidate, relation, depth)
                return
            current_ids.append(candidate)
            pending_ids.append(candidate)
            depth_by_id[candidate] = depth
            expanded_ids.append(candidate)

        def try_add_ref(candidate: str, depth: int) -> None:
            if candidate in current_refs:
                return
            if depth > int(run.get("max_depth", DEFAULT_MAX_DEPTH)):
                boundary("DEPTH_LIMIT", candidate, "EXPLICIT_REF", depth)
                return
            if total_scope() >= int(run.get("max_objects", DEFAULT_MAX_OBJECTS)):
                boundary("OBJECT_BUDGET", candidate, "EXPLICIT_REF", depth)
                return
            current_refs.append(candidate)
            pending_refs.append(candidate)
            depth_by_ref[candidate] = depth
            expanded_refs.append(candidate)

        subject_depth = 0
        if subject_id:
            subject_depth = int(depth_by_id.get(subject_id, 0))
        elif subject_ref:
            subject_depth = int(depth_by_ref.get(subject_ref, 0))
        next_depth = subject_depth + 1

        if impact_level == "EXPAND":
            for candidate in explicit_affected_ids:
                try_add_id(candidate, "EXPLICIT_IMPACT", next_depth)
            for candidate in explicit_affected_refs:
                try_add_ref(candidate, next_depth)
            if subject_id:
                allowed = set(run.get("expansion_relations") or [])
                for item in self._neighbors(subject_id):
                    if item["relation"] in allowed:
                        try_add_id(item["entity_id"], item["relation"], next_depth)
        elif impact_level == "OUTSIDE_SCOPE":
            for candidate in explicit_affected_ids:
                boundary("REPORTED_OUTSIDE_SCOPE", candidate, "EXPLICIT_IMPACT", next_depth)
            for candidate in explicit_affected_refs:
                boundary("REPORTED_OUTSIDE_SCOPE", candidate, "EXPLICIT_REF", next_depth)

        if expanded_ids or expanded_refs:
            expansion_history.append({
                "finding_id": finding["entity_id"],
                "from_id": subject_id,
                "from_ref": subject_ref,
                "depth": next_depth,
                "added_ids": expanded_ids,
                "added_refs": expanded_refs,
            })

        patch = {
            "current_scope_ids": current_ids,
            "pending_ids": _unique(pending_ids),
            "inspected_ids": inspected_ids,
            "current_scope_refs": current_refs,
            "pending_refs": _unique(pending_refs),
            "inspected_refs": inspected_refs,
            "depth_by_id": depth_by_id,
            "depth_by_ref": depth_by_ref,
            "boundary_events": boundary_events,
            "expansion_history": expansion_history,
            "updated_at": utcnow(),
        }
        updated = self.service._update(
            "audit_runs", audit_id, patch, expected_revision=int(run.get("revision", 0))
        )
        return {
            "finding": finding,
            "expanded_ids": expanded_ids,
            "expanded_refs": expanded_refs,
            "audit": self.status(updated["entity_id"]),
        }

    def context(self, audit_id: str) -> dict[str, Any]:
        run = self.service._must_get("audit_runs", audit_id)
        findings = sorted(
            self.service.store.find("audit_findings", {"audit_id": audit_id}),
            key=lambda x: str(x.get("created_at") or ""),
        )
        scope = [self._describe_entity(entity_id) for entity_id in run.get("current_scope_ids") or []]
        mutation_ids = set(run.get("mutation_scope_ids") or [])
        for item in scope:
            item["mutation_allowed_by_audit"] = item["entity_id"] in mutation_ids and run.get("mode") == "REPAIR_WITHIN_SCOPE"
        status = self.status(audit_id)

        hygiene: dict[str, Any] | None = None
        try:
            from .hygiene import CognitiveHygieneService
            hygiene_result = CognitiveHygieneService(self.service).evaluate(
                run["family_id"], run.get("slice_id"), query_text=run.get("objective"),
                max_active_objects=min(int(run.get("max_objects", DEFAULT_MAX_OBJECTS)), DEFAULT_MAX_OBJECTS),
                extra_root_ids=list(run.get("pending_ids") or run.get("current_scope_ids") or []),
            )
            hygiene = {
                "policy": hygiene_result.get("policy"),
                "working_set_ids": hygiene_result.get("working_set_ids"),
                "counts": hygiene_result.get("counts"),
            }
        except Exception:
            hygiene = None

        return {
            "audit": status,
            "scope": scope,
            "scope_refs": list(run.get("current_scope_refs") or []),
            "findings": findings,
            "boundaries": {
                "knowledge": "Only current audit scope, persisted findings, explicit assumptions and discovered frontier are known for this audit.",
                "inspection": {
                    "auto_expands": True,
                    "max_depth": run.get("max_depth"),
                    "max_objects": run.get("max_objects"),
                    "relations": list(run.get("expansion_relations") or []),
                },
                "mutation": {
                    "mode": run.get("mode"),
                    "ids": list(run.get("mutation_scope_ids") or []),
                    "refs": list(run.get("mutation_scope_refs") or []),
                    "rule": "Audit scope expansion never expands mutation authority. Actual mutation still requires the normal MangoMe Plan/WorkTurn and host permissions.",
                },
                "assurance": "Findings and closure are scoped audit evidence. They do not promote underlying work to VERIFIED or claim global system correctness.",
            },
            "cognitive_hygiene": hygiene,
            "instruction": (
                "Inspect the next frontier only. State assumptions and unknowns explicitly. Expand only on material impact. "
                "Outside mutation scope: report, do not repair. Stop when the frontier reaches a fixpoint or the configured boundary."
            ),
        }

    def close(self, audit_id: str, *, actor_id: str, summary: str | None = None) -> dict[str, Any]:
        run = self.service._must_get("audit_runs", audit_id)
        if run.get("status") != "ACTIVE":
            raise ScopedAuditError(f"audit {audit_id} is not ACTIVE")
        if run.get("actor_id") != actor_id:
            raise ScopedAuditError("only the owning audit actor may close the audit")
        self._work_and_turn(run["family_id"], actor_id, run.get("turn_id"))
        closure = self._closure_state(run)
        if closure == "OPEN":
            raise ScopedAuditError("AUDIT_FRONTIER_NOT_CLOSED: pending scope remains")
        updated = self.service._update(
            "audit_runs", audit_id,
            {
                "status": "CLOSED",
                "closure_state": closure,
                "closed_at": utcnow(),
                "closed_by": actor_id,
                "summary": summary,
                "updated_at": utcnow(),
            },
            expected_revision=int(run.get("revision", 0)),
        )
        return {
            "audit_id": audit_id,
            "status": updated.get("status"),
            "closure_state": closure,
            "summary": summary,
            "boundary_events": list(updated.get("boundary_events") or []),
            "assurance_rule": "CLOSED audit means bounded impact closure only; it does not imply VERIFIED underlying work or whole-system correctness.",
        }
