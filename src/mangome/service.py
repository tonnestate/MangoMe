from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from .enums import (
    AssuranceState,
    ClaimType,
    ContractKind,
    DependencyLevel,
    EdgeStatus,
    EntityType,
    EvidenceClass,
    EvidenceVerdict,
    ExecutionState,
    RelationType,
    SliceOrigin,
)
from .models import (
    Approval,
    Artifact,
    Claim,
    CollisionWarning,
    ContractContribution,
    Edge,
    Evidence,
    ExecutionReceipt,
    Family,
    FamilyCurrent,
    FamilyStatusView,
    Gate,
    IntakeRequest,
    ModelProfile,
    Plan,
    Project,
    ProposedSlice,
    Slice,
    SliceDependency,
    Specification,
    StorageBinding,
    utcnow,
)
from .storage.base import RevisionConflictError, Store


class MangoMeError(RuntimeError):
    pass


class PlanRequired(MangoMeError):
    pass


class ApprovalRequired(MangoMeError):
    pass


class InvalidTransition(MangoMeError):
    pass


class RevisionConflict(MangoMeError):
    pass


def _dump(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="python")


def _dt_key(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0


_ENTITY_COLLECTIONS = {
    EntityType.PROJECT.value: "projects",
    EntityType.FAMILY.value: "families",
    EntityType.CONTRACT.value: "contracts",
    EntityType.SPEC.value: "specs",
    EntityType.SLICE.value: "slices",
    EntityType.PLAN.value: "plans",
    EntityType.ARTIFACT.value: "artifacts",
    EntityType.EVIDENCE.value: "evidence",
    EntityType.APPROVAL.value: "approvals",
    EntityType.MODEL.value: "models",
}

_CONTRACT_EVOLUTION_RELATIONS = {
    RelationType.ADDS_TO.value,
    RelationType.AMENDS.value,
    RelationType.EXTENDS.value,
    RelationType.REPAIRS.value,
    RelationType.RECOVERS.value,
    RelationType.SUPERSEDES.value,
    RelationType.CONFLICTS_WITH.value,
    RelationType.VALIDATES.value,
}


class MangoMeService:
    """Provider-neutral work-state domain service.

    Read access is unrestricted. Productive execution is bound to a persisted
    plan. Worker claims are state inputs, never proof of assurance.
    """

    def __init__(self, store: Store) -> None:
        self.store = store
        self.store.ensure_indexes()

    def _update(
        self,
        collection: str,
        entity_id: str,
        patch: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        try:
            return self.store.update(collection, entity_id, patch, expected_revision=expected_revision)
        except RevisionConflictError as exc:
            raise RevisionConflict(str(exc)) from exc

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
        if family_id:
            self._must_get("families", family_id)
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
        contract_ids = contract_ids or []
        self._validate_contracts_in_family(family_id, contract_ids)
        existing_specs = self.store.find("specs", {"family_id": family_id})
        version = max((int(x.get("version", 0)) for x in existing_specs), default=0) + 1
        if supersedes_spec_id:
            prior = self._must_get("specs", supersedes_spec_id)
            if prior["family_id"] != family_id:
                raise ValueError("superseded spec must belong to the same family")
            self._update(
                "specs", supersedes_spec_id,
                {"effective": False, "updated_at": utcnow()},
                expected_revision=int(prior.get("revision", 0)),
            )
        spec = Specification(
            family_id=family_id,
            contract_ids=contract_ids,
            version=version,
            objective=objective,
            deliverables=deliverables or [],
            constraints=constraints or [],
            acceptance_criteria=acceptance_criteria or [],
            out_of_scope=out_of_scope or [],
            required_evidence=required_evidence or [],
            supersedes_spec_id=supersedes_spec_id,
        )
        saved = self.store.insert("specs", _dump(spec))
        spec_ids = list(dict.fromkeys(family.get("spec_ids", []) + [spec.entity_id]))
        self._update(
            "families", family_id,
            {"spec_ids": spec_ids, "current_spec_id": spec.entity_id, "updated_at": utcnow()},
            expected_revision=int(family.get("revision", 0)),
        )
        return saved

    # ---------- identity / registry ----------
    def create_project(self, project_key: str, title: str, description: str | None = None) -> dict[str, Any]:
        existing = self.store.find("projects", {"project_key": project_key})
        if existing:
            return existing[0]
        return self.store.insert("projects", _dump(Project(project_key=project_key, title=title, description=description)))

    def create_family(
        self,
        family_key: str,
        title: str,
        project_ids: list[str] | None = None,
        scope_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        existing = self.store.find("families", {"family_key": family_key})
        project_ids = project_ids or []
        scope_ids = scope_ids or []
        for project_id in project_ids:
            self._must_get("projects", project_id)
        if existing:
            family = existing[0]
            merged_projects = list(dict.fromkeys(family.get("project_ids", []) + project_ids))
            merged_scopes = list(dict.fromkeys(family.get("scope_ids", []) + scope_ids))
            if merged_projects != family.get("project_ids", []) or merged_scopes != family.get("scope_ids", []):
                family = self._update(
                    "families", family["entity_id"],
                    {"project_ids": merged_projects, "scope_ids": merged_scopes, "updated_at": utcnow()},
                    expected_revision=int(family.get("revision", 0)),
                )
            for project_id in project_ids:
                project = self._must_get("projects", project_id)
                if family["entity_id"] not in project.get("family_ids", []):
                    self._update(
                        "projects", project_id,
                        {"family_ids": list(dict.fromkeys(project.get("family_ids", []) + [family["entity_id"]])), "updated_at": utcnow()},
                        expected_revision=int(project.get("revision", 0)),
                    )
            return family
        family = Family(family_key=family_key, title=title, project_ids=project_ids, scope_ids=scope_ids)
        saved = self.store.insert("families", _dump(family))
        for project_id in project_ids:
            project = self._must_get("projects", project_id)
            family_ids = list(dict.fromkeys(project.get("family_ids", []) + [family.entity_id]))
            self._update(
                "projects", project_id,
                {"family_ids": family_ids, "last_activity_at": utcnow(), "updated_at": utcnow()},
                expected_revision=int(project.get("revision", 0)),
            )
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
        for _ in range(3):
            family = self._must_get("families", family_id)
            contract_ids = list(dict.fromkeys(family.get("contract_ids", []) + [contract.entity_id]))
            warnings = list(family.get("current", {}).get("warning_flags", []))
            collisions = self.store.find("contracts", {"declared_id": declared_id})
            if len(collisions) > 1 and "DECLARED_ID_COLLISION" not in warnings:
                warnings.append("DECLARED_ID_COLLISION")
            try:
                self._update(
                    "families", family_id,
                    {
                        "contract_ids": contract_ids,
                        "current.warning_flags": warnings,
                        "last_activity_at": utcnow(),
                        "last_actor_id": actor_id,
                        "updated_at": utcnow(),
                    },
                    expected_revision=int(family.get("revision", 0)),
                )
                break
            except RevisionConflict:
                continue
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
        for entity_id in belongs_to or []:
            if not self._entity_exists_anywhere(entity_id):
                raise KeyError(f"unknown belongs_to entity {entity_id}")
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
        from_type = EntityType(from_type.upper()).value
        to_type = EntityType(to_type.upper()).value
        relation = RelationType(relation.upper()).value
        status = EdgeStatus(status.upper()).value
        from_doc = self._must_get(_ENTITY_COLLECTIONS[from_type], from_id)
        to_doc = self._must_get(_ENTITY_COLLECTIONS[to_type], to_id)
        if relation in _CONTRACT_EVOLUTION_RELATIONS:
            if from_id == to_id:
                raise ValueError("contract evolution edge cannot point to itself")
            if from_type != EntityType.CONTRACT.value or to_type != EntityType.CONTRACT.value:
                raise ValueError(f"{relation} requires CONTRACT -> CONTRACT endpoints")
            if from_doc.get("family_id") != to_doc.get("family_id"):
                raise ValueError("contract evolution edges must stay inside one family")
        duplicate = [
            e for e in self.store.find("edges", {"from_id": from_id})
            if e.get("relation") == relation and e.get("to_id") == to_id and e.get("status") == status
        ]
        if duplicate:
            return duplicate[0]
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
        saved = self.store.insert("edges", _dump(edge))
        if from_type == EntityType.CONTRACT.value:
            self._project_family(from_doc["family_id"])
        return saved

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
        if request.get("family_id") and request["family_id"] != family_id:
            raise PlanRequired("request must belong to the same family")
        if spec["family_id"] != family_id:
            raise PlanRequired("spec must belong to the same family")
        if request.get("classification") in {"INFORMATION", "UNRESOLVED"}:
            raise PlanRequired("request classification is not executable")
        contract_ids = contract_ids or []
        self._validate_contracts_in_family(family_id, contract_ids)
        plan = Plan(
            family_id=family_id,
            request_id=request_id,
            spec_id=spec_id,
            actor_id=actor_id,
            intent=intent,
            contract_ids=contract_ids,
            proposed_slices=[ProposedSlice(**s) for s in proposed_slices],
            expected_artifacts=expected_artifacts or [],
            expected_scope=expected_scope or [],
            estimate=estimate or {},
            acceptance_expectations=acceptance_expectations or [],
        )
        saved = self.store.insert("plans", _dump(plan))
        if materialize_missing_slices:
            self._materialize_plan_slices(plan)
        saved["collision_warning"] = self.collision_warnings(plan.entity_id).model_dump(mode="python")
        self._project_family(family_id)
        return saved

    def _materialize_plan_slices(self, plan: Plan) -> None:
        family = self._must_get("families", plan.family_id)
        existing = self.store.find("slices", {"family_id": plan.family_id})
        by_declared = {s["declared_id"]: s for s in existing}
        for ps in plan.proposed_slices:
            if ps.declared_id in by_declared:
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
            family["slice_ids"] = list(dict.fromkeys(family.get("slice_ids", []) + [slice_obj.entity_id]))
        all_slices = self.store.find("slices", {"family_id": plan.family_id})
        lookup = {s["declared_id"]: s["entity_id"] for s in all_slices}
        for ps in plan.proposed_slices:
            entity_id = lookup.get(ps.declared_id)
            if not entity_id:
                continue
            sl = self._must_get("slices", entity_id)
            requirements: list[dict[str, str]] = []
            seen: set[str] = set()
            for dep in ps.dependencies:
                if dep.declared_id in lookup:
                    requirements.append({"slice_id": lookup[dep.declared_id], "required_level": dep.required_level.value})
                    seen.add(dep.declared_id)
            for dep_id in ps.depends_on_declared_ids:
                if dep_id in lookup and dep_id not in seen:
                    requirements.append({"slice_id": lookup[dep_id], "required_level": DependencyLevel.DONE_CLAIMED.value})
            if requirements:
                self._update(
                    "slices", entity_id,
                    {
                        "depends_on": [d["slice_id"] for d in requirements],
                        "dependency_requirements": requirements,
                        "updated_at": utcnow(),
                    },
                    expected_revision=int(sl.get("revision", 0)),
                )
        current_family = self._must_get("families", plan.family_id)
        self._update(
            "families", plan.family_id,
            {"slice_ids": family.get("slice_ids", []), "updated_at": utcnow()},
            expected_revision=int(current_family.get("revision", 0)),
        )

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
        dependency_requirements: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._must_get("families", family_id)
        contract_ids = contract_ids or []
        self._validate_contracts_in_family(family_id, contract_ids)
        existing = self.store.find("slices", {"family_id": family_id, "declared_id": declared_id})
        if existing:
            return existing[0]
        deps = [SliceDependency(**d) for d in (dependency_requirements or [])]
        slice_obj = Slice(
            declared_id=declared_id,
            family_id=family_id,
            title=title,
            objective=objective,
            sequence=sequence,
            contract_ids=contract_ids,
            origin=SliceOrigin.IMPORTED,
            execution_state=ExecutionState(execution_state),
            assurance_state=AssuranceState(assurance_state),
            started_at=started_at,
            last_activity_at=last_activity_at,
            last_actor_id=actor_id,
            gates=[Gate(**g) for g in (gates or [])],
            depends_on=[d.slice_id for d in deps],
            dependency_requirements=deps,
        )
        saved = self.store.insert("slices", _dump(slice_obj))
        family = self._must_get("families", family_id)
        ids = list(dict.fromkeys(family.get("slice_ids", []) + [slice_obj.entity_id]))
        self._update(
            "families", family_id,
            {"slice_ids": ids, "updated_at": utcnow()},
            expected_revision=int(family.get("revision", 0)),
        )
        self._project_family(family_id)
        return saved

    def _require_plan_for_slice(self, *, slice_id: str, actor_id: str, plan_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        sl = self._must_get("slices", slice_id)
        try:
            plan = self._must_get("plans", plan_id)
        except KeyError as exc:
            raise PlanRequired(f"unknown plan {plan_id}") from exc
        if plan["actor_id"] != actor_id or plan["family_id"] != sl["family_id"]:
            raise PlanRequired("plan must belong to the same actor and family")
        if plan.get("status") not in {"RECORDED", "ACTIVE"}:
            raise PlanRequired("plan is not active")
        proposed_ids = {p["declared_id"] for p in plan.get("proposed_slices", [])}
        if proposed_ids and sl["declared_id"] not in proposed_ids:
            raise PlanRequired("slice is not included in the submitted plan")
        active_plan = sl.get("active_plan_id")
        if active_plan and active_plan != plan_id:
            raise PlanRequired(f"slice is currently bound to another plan: {active_plan}")
        return sl, plan

    def start_slice(self, *, slice_id: str, actor_id: str, plan_id: str) -> dict[str, Any]:
        sl, plan = self._require_plan_for_slice(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)
        if sl["execution_state"] in {ExecutionState.DONE_CLAIMED.value, ExecutionState.CANCELLED.value}:
            raise InvalidTransition("terminal slice cannot be started")
        now = utcnow()
        updated = self._update(
            "slices", slice_id,
            {
                "execution_state": ExecutionState.ACTIVE.value,
                "started_at": sl.get("started_at") or now,
                "last_activity_at": now,
                "last_actor_id": actor_id,
                "active_plan_id": plan_id,
                "last_plan_id": plan_id,
                "updated_at": now,
            },
            expected_revision=int(sl.get("revision", 0)),
        )
        self._update(
            "plans", plan_id,
            {"status": "ACTIVE", "updated_at": now},
            expected_revision=int(plan.get("revision", 0)),
        )
        self._claim(actor_id, slice_id, ClaimType.SLICE_STARTED, {"plan_id": plan_id})
        self._project_family(sl["family_id"])
        return {"slice": updated, "collision_warning": self.collision_warnings(plan_id).model_dump(mode="python")}

    def update_slice_progress(
        self,
        *,
        slice_id: str,
        actor_id: str,
        plan_id: str,
        current_step: int | None = None,
        total_steps: int | None = None,
        blocker: str | None = None,
        execution_state: str | None = None,
    ) -> dict[str, Any]:
        sl, _ = self._require_plan_for_slice(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)
        if sl.get("active_plan_id") != plan_id:
            raise PlanRequired("slice must be started under this plan before progress can mutate")
        now = utcnow()
        patch: dict[str, Any] = {"last_activity_at": now, "last_actor_id": actor_id, "last_plan_id": plan_id, "updated_at": now}
        if current_step is not None:
            patch["current_step"] = current_step
        if total_steps is not None:
            patch["total_steps"] = total_steps
        if blocker is not None:
            patch["blocker"] = blocker
        if execution_state is not None:
            new_state = ExecutionState(execution_state)
            if new_state in {ExecutionState.DONE_CLAIMED, ExecutionState.CANCELLED, ExecutionState.PLANNED}:
                raise InvalidTransition("use the dedicated transition for terminal/reset states")
            patch["execution_state"] = new_state.value
        updated = self._update(
            "slices", slice_id, patch,
            expected_revision=int(sl.get("revision", 0)),
        )
        self._project_family(sl["family_id"])
        return updated

    def claim_done(self, *, slice_id: str, actor_id: str, plan_id: str, summary: str | None = None) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        if sl.get("execution_state") == ExecutionState.DONE_CLAIMED.value:
            if sl.get("last_actor_id") == actor_id and sl.get("last_plan_id") == plan_id:
                return sl
            raise InvalidTransition("slice already has a DONE claim from another execution context")
        sl, _ = self._require_plan_for_slice(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)
        if sl.get("active_plan_id") != plan_id:
            raise PlanRequired("slice must be active under this plan before DONE can be claimed")
        now = utcnow()
        updated = self._update(
            "slices", slice_id,
            {
                "execution_state": ExecutionState.DONE_CLAIMED.value,
                "done_claimed_at": now,
                "last_activity_at": now,
                "last_actor_id": actor_id,
                "active_plan_id": None,
                "last_plan_id": plan_id,
                "updated_at": now,
            },
            expected_revision=int(sl.get("revision", 0)),
        )
        self._claim(actor_id, slice_id, ClaimType.DONE, {"summary": summary, "plan_id": plan_id})
        self._project_family(sl["family_id"])
        return updated

    # Base methods retain structural validation. Runtime uses IntegrityMangoMeService for trust enforcement.
    def set_gate(self, *, slice_id: str, gate_id: str, status: str, evidence_ids: list[str] | None = None, **_: Any) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        gates = [dict(g) for g in sl.get("gates", [])]
        found = False
        for gate in gates:
            if gate["gate_id"] == gate_id:
                gate["status"] = status.upper()
                gate["evidence_ids"] = evidence_ids or gate.get("evidence_ids", [])
                found = True
                break
        if not found:
            raise KeyError(f"unknown gate {gate_id}")
        updated = self._update(
            "slices", slice_id,
            {"gates": gates, "updated_at": utcnow()},
            expected_revision=int(sl.get("revision", 0)),
        )
        self._project_family(sl["family_id"])
        return updated

    def verify_slice(self, **_: Any) -> dict[str, Any]:
        raise ApprovalRequired("verification requires IntegrityMangoMeService and a runtime verifier capability")

    @staticmethod
    def _derive_verdict(result: str | None) -> EvidenceVerdict:
        normalized = str(result or "").upper()
        if normalized in {"PASS", "PASSED", "OK", "SUCCESS", "TRUE"}:
            return EvidenceVerdict.PASS
        if normalized in {"FAIL", "FAILED", "ERROR", "REJECTED", "FALSE"}:
            return EvidenceVerdict.FAIL
        if normalized:
            return EvidenceVerdict.INFO
        return EvidenceVerdict.UNKNOWN

    def submit_evidence(
        self,
        *,
        subject_id: str,
        evidence_type: str,
        source: str,
        result: str | None = None,
        evidence_class: str = "CLAIM",
        artifact_id: str | None = None,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._entity_exists_anywhere(subject_id):
            raise KeyError(f"unknown evidence subject {subject_id}")
        if artifact_id is not None:
            self._must_get("artifacts", artifact_id)
        evidence = Evidence(
            subject_id=subject_id,
            evidence_type=evidence_type,
            evidence_class=EvidenceClass(evidence_class.upper()),
            source=source,
            result=result,
            verdict=self._derive_verdict(result),
            artifact_id=artifact_id,
            actor_id=actor_id,
            payload=payload or {},
        )
        return self.store.insert("evidence", _dump(evidence))

    def close_plan(self, plan_id: str, actor_id: str) -> dict[str, Any]:
        plan = self._must_get("plans", plan_id)
        if plan["actor_id"] != actor_id:
            raise InvalidTransition("only the plan actor may close its own plan")
        bound = [s for s in self.store.find("slices", {"family_id": plan["family_id"]}) if s.get("active_plan_id") == plan_id]
        if bound:
            raise InvalidTransition("cannot close a plan while slices are actively bound to it")
        return self._update(
            "plans", plan_id,
            {"status": "CLOSED", "updated_at": utcnow()},
            expected_revision=int(plan.get("revision", 0)),
        )

    # ---------- approvals ----------
    def request_override(self, *, action_type: str, subject_id: str, requested_by: str, reason: str) -> dict[str, Any]:
        if not self._entity_exists_anywhere(subject_id) and ":" not in subject_id:
            raise KeyError(f"unknown approval subject {subject_id}")
        approval = Approval(action_type=action_type, subject_id=subject_id, requested_by=requested_by, reason=reason)
        return self.store.insert("approvals", _dump(approval))

    def approve_override(self, **_: Any) -> dict[str, Any]:
        raise ApprovalRequired("approval decisions require the integrity runtime capability")

    def reject_override(self, **_: Any) -> dict[str, Any]:
        raise ApprovalRequired("approval decisions require the integrity runtime capability")

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
        needle = q.lower()
        all_families = [f for f in self.store.find("families") if needle in (f.get("family_key", "") + " " + f.get("title", "")).lower()]
        all_contracts = [c for c in self.store.find("contracts") if needle in (c.get("declared_id", "") + " " + c.get("title", "")).lower()]
        all_slices = [s for s in self.store.find("slices") if needle in (s.get("declared_id", "") + " " + s.get("title", "")).lower()]
        return {"query": q, "families": all_families, "contracts": all_contracts, "slices": all_slices}

    def get_context(self, family_id: str) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        contracts = self.store.find("contracts", {"family_id": family_id})
        specs = self.store.find("specs", {"family_id": family_id})
        slices = sorted(
            self.store.find("slices", {"family_id": family_id}),
            key=lambda s: (s.get("sequence") is None, s.get("sequence") or 0, s["created_at"]),
        )
        plans = self.store.find("plans", {"family_id": family_id})
        active_plans = [p for p in plans if p.get("status") in {"RECORDED", "ACTIVE"}]
        context_ids = {family_id, *(s["entity_id"] for s in slices), *(c["entity_id"] for c in contracts), *(x["entity_id"] for x in specs)}
        evidence = [e for e in self.store.find("evidence") if e.get("subject_id") in context_ids]
        edges = [e for e in self.store.find("edges") if e.get("from_id") in context_ids or e.get("to_id") in context_ids]
        return {
            "family": family,
            "contracts": contracts,
            "specs": specs,
            "slices": slices,
            "active_plans": active_plans,
            "evidence": evidence,
            "edges": edges,
            "status": self.status(family_id),
            "effective": self.effective_family_view(family_id),
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
        if not self._entity_exists_anywhere(entity_id):
            raise KeyError(f"unknown graph entity {entity_id}")
        outgoing = [e for e in self.store.find("edges") if e.get("from_id") == entity_id]
        incoming = [e for e in self.store.find("edges") if e.get("to_id") == entity_id]
        return {"entity_id": entity_id, "outgoing": outgoing, "incoming": incoming}

    def effective_family_view(self, family_id: str) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        contracts = sorted(self.store.find("contracts", {"family_id": family_id}), key=lambda c: c["created_at"])
        ids = {c["entity_id"] for c in contracts}
        edges = [
            e for e in self.store.find("edges")
            if e.get("from_id") in ids and e.get("to_id") in ids and e.get("relation") in _CONTRACT_EVOLUTION_RELATIONS
        ]
        confirmed = [e for e in edges if e.get("status") == EdgeStatus.CONFIRMED.value]
        superseded = {e["to_id"] for e in confirmed if e.get("relation") == RelationType.SUPERSEDES.value}
        effective = [c for c in contracts if c["entity_id"] not in superseded]
        conflicts = [
            e for e in confirmed
            if e.get("relation") == RelationType.CONFLICTS_WITH.value
            and e.get("from_id") not in superseded
            and e.get("to_id") not in superseded
        ]
        suggestions = [e for e in edges if e.get("status") == EdgeStatus.SUGGESTED.value]
        current_spec = self.store.get("specs", family.get("current_spec_id")) if family.get("current_spec_id") else None
        return {
            "family_id": family_id,
            "family_key": family["family_key"],
            "current_spec": current_spec,
            "contributions": contracts,
            "effective_contract_ids": [c["entity_id"] for c in effective],
            "superseded_contract_ids": sorted(superseded),
            "confirmed_relations": confirmed,
            "suggested_relations": suggestions,
            "conflicts": conflicts,
            "is_conflicted": bool(conflicts),
        }

    def project_overview(self, project_ref: str) -> dict[str, Any]:
        project = self.store.get("projects", project_ref)
        if project is None:
            matches = self.store.find("projects", {"project_key": project_ref})
            if not matches:
                raise KeyError(f"unknown project {project_ref}")
            project = matches[0]
        family_ids = list(dict.fromkeys(
            project.get("family_ids", [])
            + [f["entity_id"] for f in self.store.find("families") if project["entity_id"] in f.get("project_ids", [])]
        ))
        families = [self._must_get("families", fid) for fid in family_ids]
        statuses = [self.status(fid) for fid in family_ids]
        all_slices = [s for fid in family_ids for s in self.store.find("slices", {"family_id": fid})]
        all_contracts = [c for fid in family_ids for c in self.store.find("contracts", {"family_id": fid})]
        subject_ids = set(family_ids) | {s["entity_id"] for s in all_slices} | {c["entity_id"] for c in all_contracts}
        approvals = [
            a for a in self.store.find("approvals")
            if a.get("status") == "REQUIRED"
            and (
                a.get("subject_id") in subject_ids
                or any(str(a.get("subject_id", "")).startswith(f"{sid}:") for sid in {s["entity_id"] for s in all_slices})
            )
        ]
        counts = Counter(s["execution_state"] for s in all_slices)
        assurance_counts = Counter(s["assurance_state"] for s in all_slices)
        timestamps = [s.get("last_activity_at") or s.get("updated_at") for s in all_slices] + [f.get("last_activity_at") for f in families]
        last_activity = max((t for t in timestamps if t), key=_dt_key, default=project.get("last_activity_at"))
        return {
            "project": project,
            "families": statuses,
            "family_count": len(families),
            "contract_count": len(all_contracts),
            "slice_counts": {**dict(counts), **{f"ASSURANCE_{k}": v for k, v in assurance_counts.items()}},
            "active_actor_ids": sorted({actor for status in statuses for actor in status.get("active_actor_ids", [])}),
            "open_approvals": approvals,
            "warnings": sorted({warning for status in statuses for warning in status.get("warnings", [])}),
            "last_activity_at": last_activity,
        }

    def health(self) -> dict[str, Any]:
        from . import __version__
        from .schema import CURRENT_SCHEMA_VERSION

        return {
            "ok": True,
            "version": __version__,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "store": self.store.health(),
        }

    # ---------- projections ----------
    def _dependency_satisfied(self, requirement: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
        dep = by_id.get(requirement.get("slice_id"))
        if not dep:
            return False
        level = str(requirement.get("required_level") or DependencyLevel.DONE_CLAIMED.value)
        if level == DependencyLevel.ACCEPTED.value:
            return dep.get("assurance_state") == AssuranceState.ACCEPTED.value
        if level == DependencyLevel.VERIFIED.value:
            return dep.get("assurance_state") in {AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value}
        return dep.get("execution_state") == ExecutionState.DONE_CLAIMED.value or dep.get("assurance_state") in {
            AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value
        }

    def _project_family(self, family_id: str) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        slices = self.store.find("slices", {"family_id": family_id})
        warnings = list(family.get("current", {}).get("warning_flags", []))
        effective = self.effective_family_view(family_id)
        if effective["is_conflicted"] and "CONTRACT_CONFLICT" not in warnings:
            warnings.append("CONTRACT_CONFLICT")
        if not slices:
            current = FamilyCurrent(warning_flags=warnings, last_timestamp=family.get("last_activity_at") or utcnow())
        else:
            active = [s for s in slices if s["execution_state"] in {ExecutionState.STARTED.value, ExecutionState.ACTIVE.value}]
            blocked = [s for s in slices if s["execution_state"] == ExecutionState.BLOCKED.value]
            done_claimed = [s for s in slices if s["execution_state"] == ExecutionState.DONE_CLAIMED.value]
            verified = [s for s in slices if s["assurance_state"] in {AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value}]
            accepted = [s for s in slices if s["assurance_state"] == AssuranceState.ACCEPTED.value]
            rejected = [s for s in slices if s["assurance_state"] == AssuranceState.REJECTED.value]
            started = [s for s in slices if s.get("started_at")]
            last_started = max(started, key=lambda s: _dt_key(s.get("started_at")))["entity_id"] if started else None
            last_done = max(done_claimed, key=lambda s: _dt_key(s.get("done_claimed_at")))["entity_id"] if done_claimed else None
            last_verified = max(verified, key=lambda s: _dt_key(s.get("verified_at") or s.get("accepted_at")))["entity_id"] if verified else None
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
            by_id = {s["entity_id"]: s for s in slices}
            planned = []
            for s in slices:
                if s["execution_state"] != ExecutionState.PLANNED.value:
                    continue
                requirements = s.get("dependency_requirements") or [
                    {"slice_id": dep, "required_level": DependencyLevel.DONE_CLAIMED.value}
                    for dep in s.get("depends_on", [])
                ]
                if all(self._dependency_satisfied(req, by_id) for req in requirements):
                    planned.append(s)
            planned.sort(key=lambda s: (s.get("sequence") is None, s.get("sequence") or 0, s["created_at"]))
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
                warning_flags=warnings,
                last_timestamp=last_ts,
            )

        now = utcnow()
        for _ in range(3):
            family = self._must_get("families", family_id)
            try:
                family = self._update(
                    "families", family_id,
                    {"current": current.model_dump(mode="python"), "last_activity_at": current.last_timestamp, "updated_at": now},
                    expected_revision=int(family.get("revision", 0)),
                )
                break
            except RevisionConflict:
                continue
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
        payload["schema_version"] = 2
        payload["updated_at"] = now
        if previous:
            payload.pop("revision", None)
            self._update(
                "project_views", previous[0]["entity_id"], payload,
                expected_revision=int(previous[0].get("revision", 0)),
            )
        else:
            payload["revision"] = 0
            payload["created_at"] = now
            self.store.insert("project_views", payload)
        return payload

    def _claim(self, actor_id: str, subject_id: str, claim_type: ClaimType, value: Any) -> dict[str, Any]:
        return self.store.insert("claims", _dump(Claim(actor_id=actor_id, subject_id=subject_id, claim_type=claim_type, value=value)))

    def _validate_contracts_in_family(self, family_id: str, contract_ids: list[str]) -> None:
        for contract_id in contract_ids:
            contract = self._must_get("contracts", contract_id)
            if contract.get("family_id") != family_id:
                raise ValueError(f"contract {contract_id} does not belong to family {family_id}")

    def _entity_exists_anywhere(self, entity_id: str) -> bool:
        return any(self.store.get(collection, entity_id) is not None for collection in _ENTITY_COLLECTIONS.values())

    def _must_get(self, collection: str, entity_id: str) -> dict[str, Any]:
        doc = self.store.get(collection, entity_id)
        if doc is None:
            raise KeyError(f"unknown {collection}:{entity_id}")
        return doc
