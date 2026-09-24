from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from .enums import AssuranceState, ClaimType, ContractKind, ExecutionState, SliceOrigin
from .models import (
    Approval,
    Artifact,
    Claim,
    CollisionWarning,
    ContractContribution,
    Edge,
    Evidence,
    Family,
    FamilyCurrent,
    FamilyStatusView,
    Gate,
    Plan,
    Project,
    IntakeRequest,
    Specification,
    ModelProfile,
    ExecutionReceipt,
    ProposedSlice,
    Slice,
    StorageBinding,
    utcnow,
)
from .storage.base import Store


class MangoMeError(RuntimeError):
    pass


class PlanRequired(MangoMeError):
    pass


class ApprovalRequired(MangoMeError):
    pass


class InvalidTransition(MangoMeError):
    pass


def _dump(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="python")


def _dt_key(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0


class MangoMeService:
    """Domain service.

    Workers may claim. MangoMe derives state. Mutating execution requires a
    recorded plan, while reading is unrestricted.
    """

    def __init__(self, store: Store) -> None:
        self.store = store
        self.store.ensure_indexes()

    # ---------- intake / specification ----------
    def intake_request(
        self,
        *,
        request_text: str,
        classification: str | None = None,
        classification_source: str | None = None,
        source_ref: str | None = None,
        family_id: str | None = None,
    ) -> dict[str, Any]:
        if classification is None:
            classification = self._fallback_classification(request_text)
            classification_source = classification_source or "MANGOME_RULES"
        else:
            classification_source = classification_source or "EXTERNAL"
        req = IntakeRequest(
            request_text=request_text,
            classification=classification,
            classification_source=classification_source,
            source_ref=source_ref,
            family_id=family_id,
        )
        return self.store.insert("requests", _dump(req))

    @staticmethod
    def _fallback_classification(text: str) -> str:
        t = text.lower()
        # Cheap fallback only. IntakeGov should normally provide classification.
        if any(x in t for x in ("verify", "verif", "prüf", "audit")):
            return "VERIFICATION"
        if any(x in t for x in ("repair", "fix", "repar", "fehler beheben")):
            return "REPAIR"
        if any(x in t for x in ("extend", "erweiter", "addendum", "amend")):
            return "EXTENSION"
        if any(x in t for x in ("vertrag", "contract", "baue mir", "build me", "implement")):
            return "NEW_CONTRACT"
        if any(x in t for x in ("research", "recherch", "untersuch")):
            return "RESEARCH"
        return "OPERATIONAL_TASK"

    def create_spec(
        self,
        *,
        family_id: str,
        objective: str,
        contract_ids: list[str] | None = None,
        deliverables: list[str] | None = None,
        constraints: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        out_of_scope: list[str] | None = None,
        required_evidence: list[str] | None = None,
        supersedes_spec_id: str | None = None,
    ) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        existing_specs = self.store.find("specs", {"family_id": family_id})
        version = max((int(x.get("version", 0)) for x in existing_specs), default=0) + 1
        if supersedes_spec_id:
            self._must_get("specs", supersedes_spec_id)
            self.store.update("specs", supersedes_spec_id, {"effective": False, "updated_at": utcnow()})
        spec = Specification(
            family_id=family_id, contract_ids=contract_ids or [], version=version, objective=objective,
            deliverables=deliverables or [], constraints=constraints or [], acceptance_criteria=acceptance_criteria or [],
            out_of_scope=out_of_scope or [], required_evidence=required_evidence or [],
            supersedes_spec_id=supersedes_spec_id,
        )
        saved = self.store.insert("specs", _dump(spec))
        spec_ids = list(dict.fromkeys(family.get("spec_ids", []) + [spec.entity_id]))
        self.store.update("families", family_id, {"spec_ids": spec_ids, "current_spec_id": spec.entity_id, "updated_at": utcnow()})
        return saved

    # ---------- identity / registry ----------
    def create_project(self, project_key: str, title: str, description: str | None = None) -> dict[str, Any]:
        existing = self.store.find("projects", {"project_key": project_key})
        if existing:
            return existing[0]
        project = Project(project_key=project_key, title=title, description=description)
        return self.store.insert("projects", _dump(project))

    def create_family(
        self,
        family_key: str,
        title: str,
        project_ids: list[str] | None = None,
        scope_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        existing = self.store.find("families", {"family_key": family_key})
        if existing:
            return existing[0]
        family = Family(
            family_key=family_key,
            title=title,
            project_ids=project_ids or [],
            scope_ids=scope_ids or [],
        )
        saved = self.store.insert("families", _dump(family))
        for project_id in family.project_ids:
            project = self._must_get("projects", project_id)
            family_ids = list(dict.fromkeys(project.get("family_ids", []) + [family.entity_id]))
            self.store.update("projects", project_id, {"family_ids": family_ids, "last_activity_at": utcnow(), "updated_at": utcnow()})
        return saved

    def register_contract(
        self,
        *,
        declared_id: str,
        family_id: str,
        title: str,
        kind: str = "BASE",
        actor_id: str | None = None,
        storage_system: str | None = None,
        physical_location: str | None = None,
        checksum: str | None = None,
    ) -> dict[str, Any]:
        self._must_get("families", family_id)
        bindings: list[StorageBinding] = []
        if storage_system and physical_location:
            bindings.append(StorageBinding(storage_system=storage_system, physical_location=physical_location, checksum=checksum))
        contract = ContractContribution(
            declared_id=declared_id,
            family_id=family_id,
            title=title,
            kind=ContractKind(kind),
            source_actor_id=actor_id,
            storage_bindings=bindings,
        )
        saved = self.store.insert("contracts", _dump(contract))
        family = self._must_get("families", family_id)
        contract_ids = list(dict.fromkeys(family.get("contract_ids", []) + [contract.entity_id]))
        warnings = list(family.get("current", {}).get("warning_flags", []))
        collisions = self.store.find("contracts", {"declared_id": declared_id})
        if len(collisions) > 1 and "DECLARED_ID_COLLISION" not in warnings:
            warnings.append("DECLARED_ID_COLLISION")
        self.store.update(
            "families",
            family_id,
            {
                "contract_ids": contract_ids,
                "current.warning_flags": warnings,
                "last_activity_at": utcnow(),
                "last_actor_id": actor_id,
                "updated_at": utcnow(),
            },
        )
        self._project_family(family_id)
        return saved

    def attach_artifact(
        self,
        *,
        logical_name: str,
        artifact_type: str,
        storage_system: str,
        physical_location: str,
        belongs_to: list[str] | None = None,
        checksum: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.store.find("artifacts", {"physical_location": physical_location})
        if existing and (checksum is None or existing[0].get("checksum") == checksum):
            return existing[0]
        artifact = Artifact(
            logical_name=logical_name,
            artifact_type=artifact_type,
            storage_system=storage_system,
            physical_location=physical_location,
            checksum=checksum,
            belongs_to=belongs_to or [],
            metadata=metadata or {},
        )
        return self.store.insert("artifacts", _dump(artifact))

    def link(
        self,
        *,
        from_type: str,
        from_id: str,
        relation: str,
        to_type: str,
        to_id: str,
        status: str = "CONFIRMED",
        source_actor_id: str | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        edge = Edge(
            from_type=from_type,
            from_id=from_id,
            relation=relation,
            to_type=to_type,
            to_id=to_id,
            status=status,
            source_actor_id=source_actor_id,
            confidence=confidence,
        )
        return self.store.insert("edges", _dump(edge))

    # ---------- planning / slices ----------
    def submit_plan(
        self,
        *,
        family_id: str,
        request_id: str,
        spec_id: str,
        actor_id: str,
        intent: str,
        proposed_slices: list[dict[str, Any]],
        contract_ids: list[str] | None = None,
        expected_artifacts: list[str] | None = None,
        expected_scope: list[str] | None = None,
        estimate: dict[str, Any] | None = None,
        acceptance_expectations: list[str] | None = None,
        materialize_missing_slices: bool = True,
    ) -> dict[str, Any]:
        self._must_get("families", family_id)
        request = self._must_get("requests", request_id)
        spec = self._must_get("specs", spec_id)
        if spec["family_id"] != family_id:
            raise PlanRequired("spec must belong to the same family")
        if request.get("classification") in {"INFORMATION", "UNRESOLVED"}:
            raise PlanRequired("request classification is not executable")
        plan = Plan(
            family_id=family_id,
            request_id=request_id,
            spec_id=spec_id,
            actor_id=actor_id,
            intent=intent,
            contract_ids=contract_ids or [],
            proposed_slices=[ProposedSlice(**s) for s in proposed_slices],
            expected_artifacts=expected_artifacts or [],
            expected_scope=expected_scope or [],
            estimate=estimate or {},
            acceptance_expectations=acceptance_expectations or [],
        )
        saved = self.store.insert("plans", _dump(plan))
        if materialize_missing_slices:
            self._materialize_plan_slices(plan)
        warnings = self.collision_warnings(plan.entity_id)
        saved["collision_warning"] = warnings.model_dump(mode="python")
        self._project_family(family_id)
        return saved

    def _materialize_plan_slices(self, plan: Plan) -> None:
        family = self._must_get("families", plan.family_id)
        existing = self.store.find("slices", {"family_id": plan.family_id})
        by_declared = {s["declared_id"]: s for s in existing}
        created_map: dict[str, str] = {}
        for ps in plan.proposed_slices:
            if ps.declared_id in by_declared:
                created_map[ps.declared_id] = by_declared[ps.declared_id]["entity_id"]
                continue
            gates = [Gate(gate_id=f"{ps.declared_id}:G{i+1}", description=text) for i, text in enumerate(ps.acceptance)]
            slice_obj = Slice(
                declared_id=ps.declared_id,
                family_id=plan.family_id,
                title=ps.title,
                objective=ps.objective,
                contract_ids=plan.contract_ids,
                sequence=ps.sequence,
                origin=SliceOrigin.PLANNED,
                gates=gates,
            )
            self.store.insert("slices", _dump(slice_obj))
            created_map[ps.declared_id] = slice_obj.entity_id
            family["slice_ids"] = list(dict.fromkeys(family.get("slice_ids", []) + [slice_obj.entity_id]))
        # Resolve explicit dependencies by declared id after all slices exist.
        all_slices = self.store.find("slices", {"family_id": plan.family_id})
        lookup = {s["declared_id"]: s["entity_id"] for s in all_slices}
        for ps in plan.proposed_slices:
            entity_id = lookup.get(ps.declared_id)
            if entity_id:
                deps = [lookup[d] for d in ps.depends_on_declared_ids if d in lookup]
                self.store.update("slices", entity_id, {"depends_on": deps, "updated_at": utcnow()})
        self.store.update("families", plan.family_id, {"slice_ids": family.get("slice_ids", []), "updated_at": utcnow()})

    def import_slice(
        self,
        *,
        family_id: str,
        declared_id: str,
        title: str,
        objective: str | None = None,
        sequence: float | None = None,
        contract_ids: list[str] | None = None,
        execution_state: str = "PLANNED",
        assurance_state: str = "UNVERIFIED",
        started_at: datetime | None = None,
        last_activity_at: datetime | None = None,
        actor_id: str | None = None,
        gates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._must_get("families", family_id)
        existing = self.store.find("slices", {"family_id": family_id, "declared_id": declared_id})
        if existing:
            return existing[0]
        slice_obj = Slice(
            declared_id=declared_id,
            family_id=family_id,
            title=title,
            objective=objective,
            sequence=sequence,
            contract_ids=contract_ids or [],
            origin=SliceOrigin.IMPORTED,
            execution_state=ExecutionState(execution_state),
            assurance_state=AssuranceState(assurance_state),
            started_at=started_at,
            last_activity_at=last_activity_at,
            last_actor_id=actor_id,
            gates=[Gate(**g) for g in (gates or [])],
        )
        saved = self.store.insert("slices", _dump(slice_obj))
        family = self._must_get("families", family_id)
        ids = list(dict.fromkeys(family.get("slice_ids", []) + [slice_obj.entity_id]))
        self.store.update("families", family_id, {"slice_ids": ids, "updated_at": utcnow()})
        self._project_family(family_id)
        return saved

    def start_slice(self, *, slice_id: str, actor_id: str, plan_id: str) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        plan = self._must_get("plans", plan_id)
        if plan["actor_id"] != actor_id or plan["family_id"] != sl["family_id"]:
            raise PlanRequired("plan must belong to the same actor and family")
        if plan.get("status") not in {"RECORDED", "ACTIVE"}:
            raise PlanRequired("plan is not active")
        proposed_ids = {p["declared_id"] for p in plan.get("proposed_slices", [])}
        if proposed_ids and sl["declared_id"] not in proposed_ids:
            raise PlanRequired("slice is not included in the submitted plan")
        now = utcnow()
        updated = self.store.update(
            "slices",
            slice_id,
            {
                "execution_state": ExecutionState.ACTIVE.value,
                "started_at": sl.get("started_at") or now,
                "last_activity_at": now,
                "last_actor_id": actor_id,
                "updated_at": now,
            },
        )
        self.store.update("plans", plan_id, {"status": "ACTIVE", "updated_at": now})
        self._claim(actor_id, slice_id, ClaimType.SLICE_STARTED, True)
        self._project_family(sl["family_id"])
        return {"slice": updated, "collision_warning": self.collision_warnings(plan_id).model_dump(mode="python")}

    def update_slice_progress(
        self,
        *,
        slice_id: str,
        actor_id: str,
        current_step: int | None = None,
        total_steps: int | None = None,
        blocker: str | None = None,
        execution_state: str | None = None,
    ) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        now = utcnow()
        patch: dict[str, Any] = {"last_activity_at": now, "last_actor_id": actor_id, "updated_at": now}
        if current_step is not None:
            patch["current_step"] = current_step
        if total_steps is not None:
            patch["total_steps"] = total_steps
        if blocker is not None:
            patch["blocker"] = blocker
        if execution_state is not None:
            new_state = ExecutionState(execution_state)
            if new_state in {ExecutionState.DONE_CLAIMED, ExecutionState.CANCELLED}:
                raise InvalidTransition("use claim_done or an approved override for terminal execution claims")
            patch["execution_state"] = new_state.value
        updated = self.store.update("slices", slice_id, patch)
        self._project_family(sl["family_id"])
        return updated

    def claim_done(self, *, slice_id: str, actor_id: str, summary: str | None = None) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        now = utcnow()
        updated = self.store.update(
            "slices",
            slice_id,
            {
                "execution_state": ExecutionState.DONE_CLAIMED.value,
                "done_claimed_at": now,
                "last_activity_at": now,
                "last_actor_id": actor_id,
                "updated_at": now,
            },
        )
        self._claim(actor_id, slice_id, ClaimType.DONE, summary or True)
        self._project_family(sl["family_id"])
        return updated

    def set_gate(self, *, slice_id: str, gate_id: str, status: str, evidence_ids: list[str] | None = None) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        gates = [dict(g) for g in sl.get("gates", [])]
        found = False
        for gate in gates:
            if gate["gate_id"] == gate_id:
                gate["status"] = status
                gate["evidence_ids"] = evidence_ids or gate.get("evidence_ids", [])
                found = True
                break
        if not found:
            raise KeyError(f"unknown gate {gate_id}")
        updated = self.store.update("slices", slice_id, {"gates": gates, "updated_at": utcnow()})
        self._project_family(sl["family_id"])
        return updated

    def verify_slice(self, *, slice_id: str, verifier_actor_id: str, evidence_ids: list[str] | None = None) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        if sl["execution_state"] != ExecutionState.DONE_CLAIMED.value:
            raise InvalidTransition("verification requires DONE_CLAIMED execution state")
        gates = sl.get("gates", [])
        open_or_failed = [g for g in gates if g.get("status") not in {"PASS", "WAIVED"}]
        if open_or_failed:
            raise InvalidTransition(f"verification denied: {len(open_or_failed)} acceptance gates are not PASS/WAIVED")
        now = utcnow()
        updated = self.store.update(
            "slices",
            slice_id,
            {
                "assurance_state": AssuranceState.VERIFIED.value,
                "verified_at": now,
                "last_activity_at": now,
                "updated_at": now,
            },
        )
        self._claim(verifier_actor_id, slice_id, ClaimType.TEST_PASSED, {"verification": True, "evidence_ids": evidence_ids or []})
        self._project_family(sl["family_id"])
        return updated

    def submit_evidence(
        self,
        *,
        subject_id: str,
        evidence_type: str,
        source: str,
        result: str | None = None,
        artifact_id: str | None = None,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evidence = Evidence(
            subject_id=subject_id,
            evidence_type=evidence_type,
            source=source,
            result=result,
            artifact_id=artifact_id,
            actor_id=actor_id,
            payload=payload or {},
        )
        return self.store.insert("evidence", _dump(evidence))

    def close_plan(self, plan_id: str, actor_id: str) -> dict[str, Any]:
        plan = self._must_get("plans", plan_id)
        if plan["actor_id"] != actor_id:
            raise InvalidTransition("only the plan actor may close its own plan")
        return self.store.update("plans", plan_id, {"status": "CLOSED", "updated_at": utcnow()})

    # ---------- approvals ----------
    def request_override(self, *, action_type: str, subject_id: str, requested_by: str, reason: str) -> dict[str, Any]:
        approval = Approval(action_type=action_type, subject_id=subject_id, requested_by=requested_by, reason=reason)
        return self.store.insert("approvals", _dump(approval))

    def approve_override(self, *, approval_id: str, decided_by: str) -> dict[str, Any]:
        approval = self._must_get("approvals", approval_id)
        if approval["status"] != "REQUIRED":
            raise InvalidTransition("approval already decided")
        return self.store.update(
            "approvals",
            approval_id,
            {"status": "APPROVED", "decided_by": decided_by, "decided_at": utcnow(), "updated_at": utcnow()},
        )

    # ---------- model / economics ledger ----------
    def register_model(self, *, model_key: str, provider: str | None = None, access_path: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        existing = self.store.find("models", {"model_key": model_key})
        if existing:
            return existing[0]
        model = ModelProfile(model_key=model_key, provider=provider, access_path=access_path, metadata=metadata or {})
        return self.store.insert("models", _dump(model))

    def record_execution_receipt(
        self, *, family_id: str, slice_id: str, actor_id: str, model_id: str | None = None,
        work_class: str = "UNCLASSIFIED", started_at: datetime | None = None, ended_at: datetime | None = None,
        input_tokens: int | None = None, output_tokens: int | None = None, execution_cost: float = 0.0,
        verification_cost: float = 0.0, repair_cost: float = 0.0, human_cost: float = 0.0, currency: str = "EUR",
        outcome: str = "UNKNOWN", context_tokens_raw: int | None = None, context_tokens_compiled: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._must_get("families", family_id)
        sl = self._must_get("slices", slice_id)
        if sl["family_id"] != family_id:
            raise ValueError("slice does not belong to family")
        if model_id is not None:
            self._must_get("models", model_id)
        receipt = ExecutionReceipt(
            family_id=family_id, slice_id=slice_id, actor_id=actor_id, model_id=model_id, work_class=work_class,
            started_at=started_at, ended_at=ended_at, input_tokens=input_tokens, output_tokens=output_tokens,
            execution_cost=execution_cost, verification_cost=verification_cost, repair_cost=repair_cost, human_cost=human_cost,
            currency=currency, outcome=outcome, context_tokens_raw=context_tokens_raw,
            context_tokens_compiled=context_tokens_compiled, metadata=metadata or {},
        )
        payload = _dump(receipt)
        payload["durable_cost"] = receipt.durable_cost
        if context_tokens_raw and context_tokens_compiled is not None:
            payload["context_tokens_saved"] = max(0, context_tokens_raw - context_tokens_compiled)
        return self.store.insert("execution_receipts", payload)

    def model_stats(self, *, model_id: str | None = None, work_class: str | None = None) -> dict[str, Any]:
        receipts = self.store.find("execution_receipts")
        if model_id is not None:
            receipts = [r for r in receipts if r.get("model_id") == model_id]
        if work_class is not None:
            receipts = [r for r in receipts if r.get("work_class") == work_class]
        attempts = len(receipts)
        verified = [r for r in receipts if r.get("outcome") in {"VERIFIED", "ACCEPTED"}]
        total_cost = round(sum(float(r.get("durable_cost", 0.0)) for r in receipts), 12)
        return {
            "model_id": model_id, "work_class": work_class, "attempts": attempts, "verified_outcomes": len(verified),
            "verified_rate": (len(verified) / attempts) if attempts else None,
            "total_durable_cost": total_cost,
            "cost_per_verified_outcome": (total_cost / len(verified)) if verified else None,
            "context_tokens_raw": sum(int(r.get("context_tokens_raw") or 0) for r in receipts),
            "context_tokens_compiled": sum(int(r.get("context_tokens_compiled") or 0) for r in receipts),
        }

    # ---------- queries ----------
    def resolve(self, query: str) -> dict[str, Any]:
        q = query.strip()
        exact_families = self.store.find("families", {"family_key": q})
        exact_contracts = self.store.find("contracts", {"declared_id": q})
        exact_slices = self.store.find("slices", {"declared_id": q})
        if exact_families or exact_contracts or exact_slices:
            return {"query": q, "families": exact_families, "contracts": exact_contracts, "slices": exact_slices}
        # deterministic contains fallback; intentionally not semantic/LLM.
        all_families = [f for f in self.store.find("families") if q.lower() in (f.get("family_key", "") + " " + f.get("title", "")).lower()]
        all_contracts = [c for c in self.store.find("contracts") if q.lower() in (c.get("declared_id", "") + " " + c.get("title", "")).lower()]
        all_slices = [s for s in self.store.find("slices") if q.lower() in (s.get("declared_id", "") + " " + s.get("title", "")).lower()]
        return {"query": q, "families": all_families, "contracts": all_contracts, "slices": all_slices}

    def get_context(self, family_id: str) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        contracts = self.store.find("contracts", {"family_id": family_id})
        specs = self.store.find("specs", {"family_id": family_id})
        slices = sorted(self.store.find("slices", {"family_id": family_id}), key=lambda s: (s.get("sequence") is None, s.get("sequence") or 0, s["created_at"]))
        plans = self.store.find("plans", {"family_id": family_id})
        active_plans = [p for p in plans if p.get("status") in {"RECORDED", "ACTIVE"}]
        evidence = [e for e in self.store.find("evidence") if e.get("subject_id") in {family_id, *(s["entity_id"] for s in slices), *(c["entity_id"] for c in contracts)}]
        edges = [e for e in self.store.find("edges") if e.get("from_id") == family_id or e.get("to_id") == family_id]
        return {
            "family": family,
            "contracts": contracts,
            "specs": specs,
            "slices": slices,
            "active_plans": active_plans,
            "evidence": evidence,
            "edges": edges,
            "status": self.status(family_id),
        }

    def status(self, family_id: str) -> dict[str, Any]:
        return self._project_family(family_id)

    def collision_warnings(self, plan_id: str) -> CollisionWarning:
        plan = self._must_get("plans", plan_id)
        peers = [
            p for p in self.store.find("plans", {"family_id": plan["family_id"]})
            if p["entity_id"] != plan_id and p.get("status") in {"RECORDED", "ACTIVE"}
        ]
        expected_artifacts = set(plan.get("expected_artifacts", []))
        expected_scope = set(plan.get("expected_scope", []))
        artifact_overlap: set[str] = set()
        scope_overlap: set[str] = set()
        actors: set[str] = set()
        peer_ids: list[str] = []
        for peer in peers:
            ao = expected_artifacts.intersection(peer.get("expected_artifacts", []))
            so = expected_scope.intersection(peer.get("expected_scope", []))
            if ao or so or peer["family_id"] == plan["family_id"]:
                artifact_overlap.update(ao)
                scope_overlap.update(so)
                actors.add(peer["actor_id"])
                peer_ids.append(peer["entity_id"])
        return CollisionWarning(
            family_overlap=bool(peers),
            artifact_overlap=sorted(artifact_overlap),
            scope_overlap=sorted(scope_overlap),
            other_actor_ids=sorted(actors),
            other_plan_ids=peer_ids,
        )

    def graph(self, entity_id: str) -> dict[str, Any]:
        outgoing = [e for e in self.store.find("edges") if e.get("from_id") == entity_id]
        incoming = [e for e in self.store.find("edges") if e.get("to_id") == entity_id]
        return {"entity_id": entity_id, "outgoing": outgoing, "incoming": incoming}

    # ---------- projections ----------
    def _project_family(self, family_id: str) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        slices = self.store.find("slices", {"family_id": family_id})
        if not slices:
            current = FamilyCurrent(
                warning_flags=family.get("current", {}).get("warning_flags", []),
                last_timestamp=family.get("last_activity_at") or utcnow(),
            )
        else:
            active = [s for s in slices if s["execution_state"] in {ExecutionState.STARTED.value, ExecutionState.ACTIVE.value}]
            blocked = [s for s in slices if s["execution_state"] == ExecutionState.BLOCKED.value]
            done_claimed = [s for s in slices if s["execution_state"] == ExecutionState.DONE_CLAIMED.value]
            verified = [s for s in slices if s["assurance_state"] in {AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value}]
            accepted = [s for s in slices if s["assurance_state"] == AssuranceState.ACCEPTED.value]
            rejected = [s for s in slices if s["assurance_state"] == AssuranceState.REJECTED.value]

            started = [s for s in slices if s.get("started_at")]
            last_started = max(started, key=lambda s: _dt_key(s.get("started_at")))["entity_id"] if started else None
            last_done = max(done_claimed, key=lambda s: _dt_key(s.get("done_claimed_at"))) ["entity_id"] if done_claimed else None
            last_verified = max(verified, key=lambda s: _dt_key(s.get("verified_at") or s.get("accepted_at"))) ["entity_id"] if verified else None

            if active:
                execution = ExecutionState.ACTIVE
            elif blocked:
                execution = ExecutionState.BLOCKED
            elif slices and all(s["execution_state"] in {ExecutionState.DONE_CLAIMED.value, ExecutionState.CANCELLED.value} for s in slices):
                execution = ExecutionState.DONE_CLAIMED
            else:
                execution = ExecutionState.PLANNED

            non_cancelled = [s for s in slices if s["execution_state"] != ExecutionState.CANCELLED.value]
            if rejected:
                assurance = AssuranceState.REJECTED
            elif non_cancelled and len(accepted) == len(non_cancelled):
                assurance = AssuranceState.ACCEPTED
            elif non_cancelled and len(verified) == len(non_cancelled):
                assurance = AssuranceState.VERIFIED
            elif verified:
                assurance = AssuranceState.PARTIAL
            else:
                assurance = AssuranceState.UNVERIFIED

            # Next-known is planning guidance only; it never blocks other work.
            satisfied = {
                s["entity_id"] for s in slices
                if s["execution_state"] == ExecutionState.DONE_CLAIMED.value
                or s["assurance_state"] in {AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value}
            }
            planned = sorted(
                [s for s in slices if s["execution_state"] == ExecutionState.PLANNED.value and set(s.get("depends_on", [])).issubset(satisfied)],
                key=lambda s: (s.get("sequence") is None, s.get("sequence") or 0, s["created_at"]),
            )
            last_ts = max((s.get("last_activity_at") or s.get("updated_at") for s in slices), default=utcnow())
            current = FamilyCurrent(
                execution_state=execution,
                assurance_state=assurance,
                last_started_slice_id=last_started,
                active_slice_ids=[s["entity_id"] for s in active],
                last_done_claimed_slice_id=last_done,
                last_verified_slice_id=last_verified,
                next_known_slice_ids=[s["entity_id"] for s in planned],
                active_actor_ids=sorted({s["last_actor_id"] for s in active if s.get("last_actor_id")}),
                warning_flags=family.get("current", {}).get("warning_flags", []),
                last_timestamp=last_ts,
            )

        now = utcnow()
        family = self.store.update(
            "families",
            family_id,
            {"current": current.model_dump(mode="python"), "last_activity_at": current.last_timestamp, "updated_at": now},
        )
        counts = Counter(s["execution_state"] for s in slices)
        assurance_counts = Counter(s["assurance_state"] for s in slices)
        view = FamilyStatusView(
            family_id=family_id,
            family_key=family["family_key"],
            title=family["title"],
            execution_state=current.execution_state,
            assurance_state=current.assurance_state,
            slice_counts={**dict(counts), **{f"ASSURANCE_{k}": v for k, v in assurance_counts.items()}},
            active_slice_ids=current.active_slice_ids,
            last_started_slice_id=current.last_started_slice_id,
            last_done_claimed_slice_id=current.last_done_claimed_slice_id,
            last_verified_slice_id=current.last_verified_slice_id,
            next_known_slice_ids=current.next_known_slice_ids,
            active_actor_ids=current.active_actor_ids,
            warnings=current.warning_flags,
            last_timestamp=current.last_timestamp,
        )
        previous = self.store.find("project_views", {"family_id": family_id})
        payload = view.model_dump(mode="python")
        payload["entity_id"] = previous[0]["entity_id"] if previous else family_id
        payload["schema_version"] = 1
        payload["updated_at"] = now
        if previous:
            self.store.update("project_views", previous[0]["entity_id"], payload)
        else:
            self.store.insert("project_views", payload)
        return payload

    def _claim(self, actor_id: str, subject_id: str, claim_type: ClaimType, value: Any) -> dict[str, Any]:
        claim = Claim(actor_id=actor_id, subject_id=subject_id, claim_type=claim_type, value=value)
        return self.store.insert("claims", _dump(claim))

    def _must_get(self, collection: str, entity_id: str) -> dict[str, Any]:
        doc = self.store.get(collection, entity_id)
        if doc is None:
            raise KeyError(f"unknown {collection}:{entity_id}")
        return doc
