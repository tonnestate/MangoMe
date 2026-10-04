from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from .authority import CapabilityDenied, require_verifier
from .contract_control import ContractGovernedMangoMeService
from .effect_control import unresolved_required_effects
from .enums import AssuranceState, ClosureState, EdgeStatus, EntityType, ExecutionState, RelationType, ValidationState
from .ids import new_id
from .models import Gate, Plan, ProposedSlice, Slice, SliceOrigin, utcnow
from .schema import CURRENT_SCHEMA_VERSION
from .service import (
    ApprovalRequired,
    InvalidTransition,
    MangoMeError,
    PlanRequired,
    RevisionConflict,
    _auto_slice_declared_id,
    _dump,
    workspace_project_key,
)

PERSISTENCE_LEVELS = {"VOLATILE", "PROGRESSIVE", "CANONICAL"}
WORK_TURN_MODES = {"QUERY", "CONTINUE", "EXECUTE", "VERIFY", "MODIFY", "CONTROL"}
_EXECUTION_MODES = {"CONTINUE", "EXECUTE"}


class WorkIdentityError(MangoMeError):
    pass


class WorkTurnError(MangoMeError):
    pass


class NormativeBaselineDrift(MangoMeError):
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


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_admission_text(text: str) -> str:
    """Return a conservative zero-touch deduplication fingerprint input.

    This normalization is intentionally mechanical, not semantic. It removes only
    representation noise (Unicode form, case, repeated whitespace and trailing
    sentence punctuation). The resulting hash is a candidate/admission key; it is
    never the durable WorkIdentity itself.
    """
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[\s.!?;:,]+$", "", value).strip()
    return value


class WorkGovernedMangoMeService(ContractGovernedMangoMeService):
    """v0.3 control plane: durable work identity around evolving specs and transient playbooks.

    Playbooks are procedural hints, Specifications are normative inputs, and neither is
    allowed to reconstruct or replace the durable identity/assurance history of admitted
    work. New v0.3 work therefore receives a canonical WorkIdentity before productive
    execution. Legacy families remain readable/executable through the v0.2 compatibility
    path until explicitly admitted/backfilled.
    """

    # ---------- identity ----------
    def _resolve_work(self, work_ref: str) -> dict[str, Any]:
        direct = self.store.get("work_identities", work_ref)
        if direct is not None:
            return direct
        matches = self.store.find("work_identities", {"work_key": work_ref})
        if not matches:
            raise KeyError(f"unknown work identity {work_ref}")
        if len(matches) != 1:
            raise WorkIdentityError(f"ambiguous work identity {work_ref!r}; use entity_id")
        return matches[0]

    def _work_for_family(self, family_id: str) -> dict[str, Any] | None:
        rows = self.store.find("work_identities", {"family_id": family_id})
        if len(rows) > 1:
            raise WorkIdentityError(f"family {family_id} is bound to multiple WorkIdentity rows")
        return rows[0] if rows else None

    def _work_for_slice(self, slice_id: str) -> dict[str, Any] | None:
        sl = self._must_get("slices", slice_id)
        return self._work_for_family(sl["family_id"])

    def work_candidate_for_request(self, *, workspace_id: str, request_text: str) -> dict[str, Any]:
        """Resolve only an exact normalized admission candidate for the current request.

        Workspace restore state alone is not request identity. Existing unrelated work
        in the same workspace must never force a new user request to bind to it or ask
        the user for a WorkIdentity reference.
        """
        workspace_id = str(workspace_id).strip()
        request_text = str(request_text).strip()
        if not workspace_id or not request_text:
            return {"state": "NONE", "candidates": []}

        project_key = workspace_project_key(workspace_id)
        normalized = _normalize_admission_text(request_text)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16].upper()
        admission_key = f"{project_key}:INTENT:{digest}"
        families = self.store.find("families", {"admission_key": admission_key})

        candidates: list[dict[str, Any]] = []
        for family in families:
            work = self._work_for_family(family["entity_id"])
            if work is not None:
                candidates.append({
                    "family_id": family["entity_id"],
                    "work_ref": work["entity_id"],
                    "work_key": work.get("work_key"),
                    "admission_key": admission_key,
                })

        if not candidates:
            return {
                "state": "NONE",
                "admission_key": admission_key,
                "fingerprint": digest,
                "candidates": [],
            }
        if len(candidates) > 1:
            return {
                "state": "AMBIGUOUS",
                "admission_key": admission_key,
                "fingerprint": digest,
                "candidates": candidates,
            }
        return {
            "state": "EXACT_NORMALIZED_MATCH",
            "admission_key": admission_key,
            "fingerprint": digest,
            "candidate": candidates[0],
            "candidates": candidates,
        }

    def admit_work(
        self,
        *,
        family_id: str,
        project_id: str,
        request_id: str | None,
        title: str,
        work_key: str | None = None,
        admitted_by: str | None = None,
        admission_source: str = "USER_INTENT",
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        family = self._must_get("families", family_id)
        project = self._must_get("projects", project_id)
        request = self._must_get("requests", request_id) if request_id else None
        if project_id not in family.get("project_ids", []):
            raise WorkIdentityError("work project must own the admitted family")
        if request and request.get("family_id") and request.get("family_id") != family_id:
            raise WorkIdentityError("admission request must belong to the admitted family")
        key_material = family_id + ":" + (request_id or str(source_ref or admission_source))
        key = str(work_key or f"WORK-{hashlib.sha256(key_material.encode()).hexdigest()[:16].upper()}")
        doc = {
            **_base_doc(),
            "work_key": key,
            "title": str(title).strip() or family.get("title") or key,
            "project_id": project_id,
            "family_id": family_id,
            "admission_request_id": request_id,
            "admission_request_hash": (
                hashlib.sha256(str((request or {}).get("request_text") or "").encode("utf-8")).hexdigest()
                if request is not None else None
            ),
            "admission_source": str(admission_source).upper(),
            "source_ref": source_ref,
            "admitted_by": admitted_by,
            "status": "ADMITTED",
            "persistence_level": "CANONICAL",
        }
        saved, created = self.store.get_or_create("work_identities", {"family_id": family_id}, doc)
        if created:
            self._refresh_normative_baseline(saved["entity_id"])
            self._refresh_work_view(saved["entity_id"])
        return saved

    def backfill_work_identity(
        self,
        *,
        family_id: str,
        project_id: str,
        title: str | None = None,
        admitted_by: str | None = None,
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        """Explicitly bind existing canonical family state to WorkIdentity without inventing user intent."""
        family = self._must_get("families", family_id)
        return self.admit_work(
            family_id=family_id,
            project_id=project_id,
            request_id=None,
            title=title or family.get("title") or family.get("family_key") or "Historical work",
            admitted_by=admitted_by,
            admission_source="HISTORICAL_BACKFILL",
            source_ref=source_ref,
        )

    # ---------- turn / authority binding ----------
    def bind_work_turn(
        self,
        *,
        work_ref: str,
        request_text: str,
        mode: str,
        actor_id: str,
        authorized_by: str | None = None,
    ) -> dict[str, Any]:
        work = self._resolve_work(work_ref)
        normalized = str(mode).strip().upper()
        if normalized not in WORK_TURN_MODES:
            raise WorkTurnError(f"unsupported work turn mode {mode!r}; expected one of {sorted(WORK_TURN_MODES)}")
        doc = {
            **_base_doc(),
            "work_id": work["entity_id"],
            "family_id": work["family_id"],
            "request_text_hash": hashlib.sha256(str(request_text).encode("utf-8")).hexdigest(),
            "mode": normalized,
            "actor_id": actor_id,
            "authorized_by": authorized_by,
            "status": "BOUND",
            "persistence_level": "CANONICAL",
        }
        saved = self.store.insert("work_turn_bindings", doc)
        self._refresh_work_view(work["entity_id"])
        return {
            "turn": saved,
            "work": work,
            "allowed": {
                "read": True,
                "execute": normalized in _EXECUTION_MODES,
                "verify": normalized == "VERIFY",
                "modify_normative_truth": normalized == "MODIFY",
                "control": normalized == "CONTROL",
            },
            "rule": "Recovered state, a Playbook, a filesystem path, or an active Plan never authorizes the current turn.",
        }

    def _require_work_turn(
        self,
        *,
        work_id: str,
        turn_id: str | None,
        actor_id: str,
        allowed_modes: set[str],
    ) -> dict[str, Any]:
        if not turn_id:
            raise WorkTurnError("WORK_TURN_REQUIRED")
        turn = self._must_get("work_turn_bindings", turn_id)
        if turn.get("work_id") != work_id:
            raise WorkTurnError("work turn belongs to another WorkIdentity")
        if turn.get("actor_id") != actor_id:
            raise WorkTurnError("work turn belongs to another actor")
        if turn.get("status") not in {"BOUND", "ACTIVE"}:
            raise WorkTurnError(f"work turn is not active: {turn.get('status')}")
        if turn.get("mode") not in allowed_modes:
            raise WorkTurnError(f"work turn mode {turn.get('mode')} does not authorize this operation")
        return turn

    # ---------- deterministic normative baseline ----------
    def _normative_semantics(self, work: dict[str, Any]) -> dict[str, Any]:
        family = self._must_get("families", work["family_id"])
        effective = super().effective_family_view(work["family_id"])
        spec = effective.get("current_spec")
        contract_bindings: list[dict[str, Any]] = []
        for contract_id in effective.get("effective_contract_ids") or []:
            head_rows = self.store.find("contract_heads", {"contract_id": contract_id})
            head = head_rows[0] if head_rows else None
            contract_bindings.append({
                "contract_id": contract_id,
                "generation": int((head or {}).get("current_generation", 0)),
                "content_hash": (head or {}).get("current_content_hash"),
            })
        contract_bindings.sort(key=lambda row: row["contract_id"])
        if spec:
            source = {
                "kind": "SPECIFICATION",
                "spec_id": spec["entity_id"],
                "spec_version": spec.get("version"),
                "spec_revision": spec.get("revision", 0),
                "objective": spec.get("objective"),
                "deliverables": list(spec.get("deliverables") or []),
                "constraints": list(spec.get("constraints") or []),
                "acceptance_criteria": list(spec.get("acceptance_criteria") or []),
                "out_of_scope": list(spec.get("out_of_scope") or []),
                "required_evidence": list(spec.get("required_evidence") or []),
            }
        else:
            request_id = work.get("admission_request_id")
            if request_id:
                request = self._must_get("requests", request_id)
                source = {
                    "kind": "OPERATIONAL_INTENT",
                    "request_id": request["entity_id"],
                    "request_hash": work.get("admission_request_hash"),
                    "classification": request.get("classification"),
                }
            else:
                source = {
                    "kind": "HISTORICAL_CANONICAL_STATE",
                    "family_id": family["entity_id"],
                    "family_key": family.get("family_key"),
                    "admission_source": work.get("admission_source"),
                    "source_ref": work.get("source_ref"),
                }
        return {
            "work_id": work["entity_id"],
            "family_id": family["entity_id"],
            "source": source,
            "effective_contracts": contract_bindings,
        }

    def _refresh_normative_baseline(self, work_ref: str) -> dict[str, Any]:
        work = self._resolve_work(work_ref)
        semantics = self._normative_semantics(work)
        semantic_hash = _canonical_hash(semantics)
        existing = self.store.find("normative_baselines", {"work_id": work["entity_id"], "semantic_hash": semantic_hash})
        if existing:
            return existing[0]
        previous = sorted(
            self.store.find("normative_baselines", {"work_id": work["entity_id"]}),
            key=lambda row: str(row.get("created_at")),
        )
        doc = {
            **_base_doc(),
            "work_id": work["entity_id"],
            "family_id": work["family_id"],
            "semantic_hash": semantic_hash,
            "semantics": semantics,
            "previous_baseline_id": previous[-1]["entity_id"] if previous else None,
            "persistence_level": "CANONICAL",
            "status": "CURRENT",
        }
        return self.store.insert("normative_baselines", doc)

    def current_normative_baseline(self, work_ref: str, *, materialize: bool = False) -> dict[str, Any]:
        work = self._resolve_work(work_ref)
        semantics = self._normative_semantics(work)
        semantic_hash = _canonical_hash(semantics)
        rows = self.store.find("normative_baselines", {"work_id": work["entity_id"], "semantic_hash": semantic_hash})
        if rows:
            return rows[0]
        if materialize:
            return self._refresh_normative_baseline(work["entity_id"])
        raise NormativeBaselineDrift("CURRENT_NORMATIVE_BASELINE_NOT_MATERIALIZED")

    def _assert_plan_baseline_current(self, plan: dict[str, Any]) -> None:
        work_id = plan.get("work_id")
        if not work_id:
            return
        bound_id = plan.get("normative_baseline_id")
        if not bound_id:
            raise NormativeBaselineDrift("WORK_PLAN_MISSING_NORMATIVE_BASELINE")
        bound = self._must_get("normative_baselines", bound_id)
        current = self.current_normative_baseline(work_id, materialize=False)
        if bound.get("semantic_hash") != current.get("semantic_hash"):
            raise NormativeBaselineDrift(
                f"BASELINE_DRIFT: plan={bound.get('semantic_hash')} current={current.get('semantic_hash')}"
            )

    # ---------- playbooks: procedural, never normative ----------
    def register_playbook(
        self,
        *,
        playbook_key: str,
        version: str,
        description: str,
        source: str,
        content_hash: str | None = None,
        applicability: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self.store.find("playbooks", {"playbook_key": playbook_key, "version": version})
        if existing:
            return existing[0]
        doc = {
            **_base_doc(),
            "playbook_key": playbook_key,
            "version": version,
            "description": description,
            "source": source,
            "content_hash": content_hash,
            "applicability": list(applicability or []),
            "required_capabilities": list(required_capabilities or []),
            "metadata": dict(metadata or {}),
            "authority": "PROCEDURAL_NON_NORMATIVE",
            "persistence_level": "CANONICAL",
        }
        return self.store.insert("playbooks", doc)

    def select_playbook(
        self,
        *,
        work_ref: str,
        playbook_id: str,
        actor_id: str,
        turn_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        work = self._resolve_work(work_ref)
        playbook = self._must_get("playbooks", playbook_id)
        if turn_id:
            self._require_work_turn(
                work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id,
                allowed_modes={"QUERY", "CONTINUE", "EXECUTE", "VERIFY", "MODIFY", "CONTROL"},
            )
        doc = {
            **_base_doc(),
            "work_id": work["entity_id"],
            "playbook_id": playbook_id,
            "actor_id": actor_id,
            "turn_id": turn_id,
            "reason": reason,
            "persistence_level": "PROGRESSIVE",
            "authority": "NON_NORMATIVE",
        }
        saved = self.store.insert("playbook_selections", doc)
        self._refresh_work_view(work["entity_id"])
        return saved

    # ---------- progressive checkpoints ----------
    def checkpoint_work(
        self,
        *,
        work_ref: str,
        actor_id: str,
        payload: dict[str, Any],
        kind: str = "EXECUTION_CHECKPOINT",
        plan_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        work = self._resolve_work(work_ref)  # critical: checkpoints can never create identity
        if plan_id:
            plan = self._must_get("plans", plan_id)
            if plan.get("work_id") != work["entity_id"] or plan.get("actor_id") != actor_id:
                raise WorkIdentityError("checkpoint plan is not bound to this work/actor")
            self._assert_plan_baseline_current(plan)
        if turn_id:
            self._require_work_turn(
                work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id,
                allowed_modes={"CONTINUE", "EXECUTE", "VERIFY", "MODIFY", "CONTROL"},
            )
        doc = {
            **_base_doc(),
            "work_id": work["entity_id"],
            "actor_id": actor_id,
            "turn_id": turn_id,
            "plan_id": plan_id,
            "kind": kind,
            "payload": dict(payload),
            "persistence_level": "PROGRESSIVE",
        }
        saved = self.store.insert("work_checkpoints", doc)
        self._refresh_work_view(work["entity_id"])
        return saved

    # ---------- plan/execution enforcement ----------
    def submit_plan(
        self,
        *,
        family_id: str,
        request_id: str,
        actor_id: str,
        intent: str,
        proposed_slices: list[dict[str, Any]],
        spec_id: str | None = None,
        work_id: str | None = None,
        turn_id: str | None = None,
        normative_baseline_id: str | None = None,
        contract_ids: list[str] | None = None,
        expected_artifacts: list[str] | None = None,
        expected_scope: list[str] | None = None,
        estimate: dict[str, Any] | None = None,
        acceptance_expectations: list[str] | None = None,
        materialize_missing_slices: bool = True,
    ) -> dict[str, Any]:
        work = self._work_for_family(family_id)
        if work is None:
            if not spec_id:
                raise PlanRequired("legacy families require spec_id")
            return super().submit_plan(
                family_id=family_id, request_id=request_id, spec_id=spec_id, actor_id=actor_id,
                intent=intent, proposed_slices=proposed_slices, contract_ids=contract_ids,
                expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
                acceptance_expectations=acceptance_expectations, materialize_missing_slices=materialize_missing_slices,
            )
        if work_id and work_id != work["entity_id"]:
            raise WorkIdentityError("plan work_id does not match family WorkIdentity")
        work_id = work["entity_id"]
        turn = self._require_work_turn(work_id=work_id, turn_id=turn_id, actor_id=actor_id, allowed_modes=_EXECUTION_MODES)
        request = self._must_get("requests", request_id)
        if request.get("family_id") and request["family_id"] != family_id:
            raise PlanRequired("request must belong to the same family")
        if request.get("classification") in {"INFORMATION", "UNRESOLVED"}:
            raise PlanRequired("request classification is not executable")
        if spec_id:
            spec = self._must_get("specs", spec_id)
            if spec.get("family_id") != family_id or not spec.get("effective", True):
                raise PlanRequired("spec must be an effective specification in the same family")
        baseline = self.current_normative_baseline(work_id, materialize=True)
        baseline_source_kind = str(((baseline.get("semantics") or {}).get("source") or {}).get("kind") or "")
        if baseline_source_kind == "HISTORICAL_CANONICAL_STATE":
            raise PlanRequired(
                "NORMATIVE_BASELINE_REQUIRED: historical WorkIdentity without admitted Specification cannot execute productively"
            )
        if normative_baseline_id and normative_baseline_id != baseline["entity_id"]:
            raise NormativeBaselineDrift("new plans must bind the current normative baseline")
        normative_baseline_id = baseline["entity_id"]
        contract_ids = list(contract_ids or baseline.get("semantics", {}).get("effective_contracts") or [])
        if contract_ids and isinstance(contract_ids[0], dict):
            contract_ids = [row["contract_id"] for row in contract_ids]
        self._validate_contracts_in_family(family_id, contract_ids)

        normalized_slices: list[dict[str, Any]] = []
        for index, raw in enumerate(proposed_slices):
            item = dict(raw)
            title = str(item.get("title") or intent or f"Work item {index + 1}").strip() or f"Work item {index + 1}"
            item["title"] = title
            if not str(item.get("declared_id") or "").strip():
                item["declared_id"] = _auto_slice_declared_id(
                    family_id=family_id, request_text=str(request.get("request_text") or ""),
                    intent=intent, title=title, index=index,
                )
            normalized_slices.append(item)
        if not normalized_slices:
            raise PlanRequired("a productive plan requires at least one proposed slice")
        plan = Plan(
            family_id=family_id,
            request_id=request_id,
            spec_id=spec_id,
            actor_id=actor_id,
            work_id=work_id,
            turn_id=turn_id,
            normative_baseline_id=normative_baseline_id,
            intent=intent,
            contract_ids=contract_ids,
            proposed_slices=[ProposedSlice(**item) for item in normalized_slices],
            expected_artifacts=expected_artifacts or [],
            expected_scope=expected_scope or [],
            estimate=estimate or {},
            acceptance_expectations=acceptance_expectations or [],
        )
        saved = self.store.insert("plans", _dump(plan))
        if materialize_missing_slices:
            self._materialize_plan_slices(plan)
        saved["collision_warning"] = self.collision_warnings(plan.entity_id).model_dump(mode="python")
        if turn.get("status") == "BOUND":
            self._update("work_turn_bindings", turn["entity_id"], {"status": "ACTIVE", "updated_at": utcnow()}, expected_revision=int(turn.get("revision", 0)))
        self._project_family(family_id)
        self._refresh_work_view(work_id)
        return saved

    def _require_plan_for_slice(self, *, slice_id: str, actor_id: str, plan_id: str):
        sl, plan = super()._require_plan_for_slice(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)
        work = self._work_for_family(sl["family_id"])
        if work:
            if plan.get("work_id") != work["entity_id"]:
                raise PlanRequired("WORK_PLAN_BINDING_REQUIRED")
            self._require_work_turn(
                work_id=work["entity_id"], turn_id=plan.get("turn_id"), actor_id=actor_id, allowed_modes=_EXECUTION_MODES
            )
            self._assert_plan_baseline_current(plan)
        return sl, plan

    def prepare_assignment(
        self,
        *,
        family_id: str,
        actor_id: str,
        request_text: str,
        intent: str | None = None,
        classification: str | None = None,
        classification_source: str = "MANGOME_ASSIGNMENT_PREP",
        read_only: bool = False,
        expected_artifacts: list[str] | None = None,
        expected_scope: list[str] | None = None,
        estimate: dict[str, Any] | None = None,
        work_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        work = self._work_for_family(family_id)
        if work is None:
            return super().prepare_assignment(
                family_id=family_id, actor_id=actor_id, request_text=request_text, intent=intent,
                classification=classification, classification_source=classification_source, read_only=read_only,
                expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
            )
        if work_id and work_id != work["entity_id"]:
            raise WorkIdentityError("prepare_assignment work_id mismatch")
        self._require_work_turn(
            work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes=_EXECUTION_MODES
        )
        family = self._must_get("families", family_id)
        spec_id = family.get("current_spec_id")
        request = self.intake_request(
            request_text=request_text,
            classification=str(classification or self._fallback_classification(request_text)).upper(),
            classification_source=classification_source,
            family_id=family_id,
        )
        existing = sorted(
            self.store.find("slices", {"family_id": family_id}),
            key=lambda row: (row.get("sequence") is None, row.get("sequence") or 0, row.get("created_at")),
        )
        policy = {
            "slices": "INTERNAL_ONLY",
            "user_result": "OUTCOME_FINDINGS_EVIDENCE_ONLY",
            "planning_is_completion": False,
            "reuse_existing_slices": True,
            "materialize_only_when_none_exist": True,
            "observe_before_repair": True,
            "repair_allowed_after_evidence": not read_only,
            "normative_truth_mutation": "FORBIDDEN_UNLESS_MODIFY_TURN",
            "work_identity": work["entity_id"],
        }
        if existing:
            nonterminal = [
                row for row in existing
                if row.get("execution_state") not in {ExecutionState.DONE_CLAIMED.value, ExecutionState.CANCELLED.value}
                or (
                    row.get("execution_state") == ExecutionState.DONE_CLAIMED.value
                    and row.get("validation_state") == ValidationState.REWORK_REQUIRED.value
                )
            ]
            active_plan_ids = sorted({str(row.get("active_plan_id")) for row in nonterminal if row.get("active_plan_id")})
            plan = self.store.get("plans", active_plan_ids[0]) if len(active_plan_ids) == 1 else None
            if nonterminal and not active_plan_ids:
                proposed = [
                    {
                        "declared_id": row["declared_id"],
                        "title": row.get("title") or row["declared_id"],
                        "objective": row.get("objective"),
                        "sequence": row.get("sequence"),
                        "acceptance": [g.get("description") for g in row.get("gates", []) if g.get("description")],
                    }
                    for row in nonterminal
                ]
                plan = self.submit_plan(
                    family_id=family_id, request_id=request["entity_id"], spec_id=spec_id,
                    actor_id=actor_id, intent=str(intent or request_text), proposed_slices=proposed,
                    expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
                    acceptance_expectations=list((self.store.get("specs", spec_id) or {}).get("acceptance_criteria") or []),
                    work_id=work["entity_id"], turn_id=turn_id, materialize_missing_slices=False,
                )
            return {
                "request": request,
                "plan": plan,
                "active_plan_ids": active_plan_ids,
                "slice_action": "REUSED_EXISTING",
                "slice_count_before": len(existing),
                "slice_count_after": len(existing),
                "targets": [
                    {
                        "entity_id": row.get("entity_id"),
                        "declared_id": row.get("declared_id"),
                        "execution_state": row.get("execution_state"),
                        "assurance_state": row.get("assurance_state"),
                    }
                    for row in existing
                ],
                "presentation_policy": policy,
            }

        title = "Internal assignment execution"
        declared_id = _auto_slice_declared_id(
            family_id=family_id, request_text=request_text, intent=str(intent or request_text), title=title
        )
        plan = self.submit_plan(
            family_id=family_id, request_id=request["entity_id"], spec_id=spec_id, actor_id=actor_id,
            intent=str(intent or request_text),
            proposed_slices=[{
                "declared_id": declared_id, "title": title, "objective": request_text,
                "acceptance": list((self.store.get("specs", spec_id) or {}).get("acceptance_criteria") or []),
            }],
            expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
            work_id=work["entity_id"], turn_id=turn_id,
        )
        matches = self.store.find("slices", {"family_id": family_id, "declared_id": declared_id})
        if len(matches) != 1:
            raise RuntimeError("prepare_assignment failed to materialize exactly one internal slice")
        started = self.start_slice(slice_id=matches[0]["entity_id"], actor_id=actor_id, plan_id=plan["entity_id"])
        return {
            "request": request, "plan": plan, "slice_action": "MATERIALIZED_INTERNAL",
            "slice_count_before": 0, "slice_count_after": 1,
            "targets": [{
                "entity_id": started["slice"]["entity_id"],
                "declared_id": started["slice"]["declared_id"],
                "execution_state": started["slice"]["execution_state"],
                "assurance_state": started["slice"]["assurance_state"],
            }],
            "presentation_policy": policy,
        }

    def begin_work(
        self,
        *,
        family_id: str,
        actor_id: str,
        request_text: str,
        intent: str,
        proposed_slice: dict[str, Any],
        classification: str = "EXISTING_WORK",
        classification_source: str = "MANGOME_ZERO_TOUCH",
        spec_id: str | None = None,
        contract_ids: list[str] | None = None,
        expected_artifacts: list[str] | None = None,
        expected_scope: list[str] | None = None,
        estimate: dict[str, Any] | None = None,
        acceptance_expectations: list[str] | None = None,
        work_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        work = self._work_for_family(family_id)
        if not work:
            if spec_id is None:
                raise PlanRequired("legacy begin_work requires spec_id")
            return super().begin_work(
                family_id=family_id, actor_id=actor_id, request_text=request_text, intent=intent,
                proposed_slice=proposed_slice, classification=classification,
                classification_source=classification_source, spec_id=spec_id, contract_ids=contract_ids,
                expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
                acceptance_expectations=acceptance_expectations,
            )
        if work_id and work_id != work["entity_id"]:
            raise WorkIdentityError("begin_work work_id mismatch")
        payload = dict(proposed_slice)
        title = str(payload.get("title") or intent or "Work item").strip() or "Work item"
        payload["title"] = title
        if not str(payload.get("declared_id") or "").strip():
            payload["declared_id"] = _auto_slice_declared_id(
                family_id=family_id, request_text=request_text, intent=intent, title=title
            )
        existing = self.store.find("slices", {"family_id": family_id, "declared_id": payload["declared_id"]})
        if existing and existing[0].get("active_plan_id"):
            raise PlanRequired(f"slice is already active under plan {existing[0].get('active_plan_id')}")
        request = self.intake_request(
            request_text=request_text, classification=classification,
            classification_source=classification_source, family_id=family_id,
        )
        plan = self.submit_plan(
            family_id=family_id, request_id=request["entity_id"], spec_id=spec_id,
            actor_id=actor_id, intent=intent, proposed_slices=[payload], contract_ids=contract_ids,
            expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
            acceptance_expectations=acceptance_expectations, work_id=work["entity_id"], turn_id=turn_id,
        )
        matches = self.store.find("slices", {"family_id": family_id, "declared_id": payload["declared_id"]})
        if not matches:
            raise RuntimeError("begin_work failed to materialize/reuse requested slice")
        started = self.start_slice(slice_id=matches[0]["entity_id"], actor_id=actor_id, plan_id=plan["entity_id"])
        return {"request": request, "plan": plan, "slice": started["slice"], "collision_warning": started["collision_warning"]}

    def enter_work(
        self,
        *,
        workspace_id: str,
        workspace_title: str,
        actor_id: str,
        request_text: str,
        work_ref: str | None = None,
        intent: str | None = None,
        slice_title: str | None = None,
        slice_objective: str | None = None,
        acceptance_criteria: list[str] | None = None,
        required_evidence: list[str] | None = None,
        expected_artifacts: list[str] | None = None,
        expected_scope: list[str] | None = None,
        estimate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace_id = str(workspace_id).strip()
        request_text = str(request_text).strip()
        actor_id = str(actor_id).strip()
        if not workspace_id or not request_text or not actor_id:
            raise ValueError("workspace_id, request_text and actor_id are required")

        intent_text = str(intent or request_text).strip() or request_text
        project_key = workspace_project_key(workspace_id)
        normalized_intent = _normalize_admission_text(request_text)
        task_digest = hashlib.sha256(normalized_intent.encode("utf-8")).hexdigest()[:16].upper()
        admission_key = f"{project_key}:INTENT:{task_digest}"

        if work_ref:
            work = self._resolve_work(work_ref)
            project = self._must_get("projects", work["project_id"])
            if str(project.get("project_key") or "") != project_key:
                raise WorkIdentityError("work_ref belongs to another workspace")
            family = self._must_get("families", work["family_id"])
            request = self.intake_request(
                request_text=request_text,
                classification="OPERATIONAL_TASK",
                classification_source="MANGOME_WORK_CONTINUATION",
                family_id=family["entity_id"],
            )
        else:
            project = self.create_project(
                project_key,
                str(workspace_title or "Workspace"),
                description="MangoMe managed workspace",
                workspace_root=workspace_id,
            )
            family = self.create_family(
                f"{project_key}-WORK-{new_id()}",
                str(slice_title or intent_text),
                project_ids=[project["entity_id"]],
                scope_ids=[f"workspace:{workspace_id}", f"user-intent:{task_digest}"],
                admission_key=admission_key,
            )

            # A prompt fingerprint is only a dedup candidate. Once durable work
            # already exists, a new caller must bind explicitly to that WorkIdentity
            # rather than silently minting another execution context.
            existing_work = self._work_for_family(family["entity_id"])
            if existing_work is not None:
                open_slices = [
                    row for row in self.store.find("slices", {"family_id": family["entity_id"]})
                    if row.get("execution_state") not in {ExecutionState.DONE_CLAIMED.value, ExecutionState.CANCELLED.value}
                ]
                return {
                    "project": project,
                    "family": family,
                    "work_identity": existing_work,
                    "disposition": "EXISTING_WORK_CANDIDATE",
                    "requires_explicit_work_ref": True,
                    "candidate_work_ref": existing_work["entity_id"],
                    "open_slices": open_slices,
                    "admission": {
                        "fingerprint": task_digest,
                        "normalized_match": True,
                        "identity_role": "DEDUP_HINT_ONLY",
                    },
                    "rule": "Prompt similarity never silently creates or rebinds durable WorkIdentity; continue explicitly with work_ref.",
                }

            request = self.intake_request(
                request_text=request_text,
                classification="OPERATIONAL_TASK",
                classification_source="MANGOME_WORK_ADMISSION",
                family_id=family["entity_id"],
                admission_key=admission_key,
            )
            work = self.admit_work(
                family_id=family["entity_id"],
                project_id=project["entity_id"],
                request_id=request["entity_id"],
                title=str(slice_title or intent_text),
                admitted_by=actor_id,
            )

        bound = self.bind_work_turn(
            work_ref=work["entity_id"],
            request_text=request_text,
            mode="EXECUTE",
            actor_id=actor_id,
            authorized_by="USER_INTENT_RELAYED_BY_CLIENT",
        )
        criteria = list(acceptance_criteria or [])
        proposed: dict[str, Any] = {
            "title": str(slice_title or intent_text) or "Work item",
            "objective": slice_objective or request_text,
            "acceptance": criteria,
        }
        if not work_ref:
            # The admission fingerprint is stable across punctuation/case noise and
            # prevents a concurrent zero-touch admission from materializing two
            # execution slices. It is not exposed as the WorkIdentity.
            proposed["declared_id"] = f"INTENT-{task_digest}"

        plan = self.submit_plan(
            family_id=family["entity_id"],
            request_id=request["entity_id"],
            actor_id=actor_id,
            intent=intent_text,
            spec_id=None,
            work_id=work["entity_id"],
            turn_id=bound["turn"]["entity_id"],
            proposed_slices=[proposed],
            expected_artifacts=expected_artifacts,
            expected_scope=expected_scope,
            estimate=estimate,
            acceptance_expectations=criteria,
        )
        targets = self.store.find("slices", {"family_id": family["entity_id"]})
        declared = {row.get("declared_id") for row in plan.get("proposed_slices", [])}
        target = next((row for row in targets if row.get("declared_id") in declared), None)
        if target is None:
            raise RuntimeError("enter_work failed to resolve materialized execution target")

        try:
            started = self.start_slice(
                slice_id=target["entity_id"],
                actor_id=actor_id,
                plan_id=plan["entity_id"],
            )
            disposition = "NEW_WORK_ADMITTED" if not work_ref else "EXISTING_WORK_BOUND"
        except (PlanRequired, RevisionConflict):
            # A concurrent admission may have activated the same unique Slice after
            # this Plan was recorded. Preserve one active execution target and
            # cancel this redundant plan rather than creating parallel work.
            current = self._must_get("slices", target["entity_id"])
            active_plan_id = current.get("active_plan_id")
            if not active_plan_id or active_plan_id == plan["entity_id"]:
                raise
            current_plan = self._must_get("plans", plan["entity_id"])
            try:
                self._update(
                    "plans",
                    plan["entity_id"],
                    {"status": "CANCELLED", "updated_at": utcnow()},
                    expected_revision=int(current_plan.get("revision", 0)),
                )
            except RevisionConflict:
                pass
            started = {
                "slice": current,
                "collision_warning": self.collision_warnings(active_plan_id).model_dump(mode="python"),
            }
            disposition = "CONCURRENT_WORK_REUSED"

        baseline = self._must_get("normative_baselines", plan["normative_baseline_id"])
        return {
            "project": project,
            "family": self._must_get("families", family["entity_id"]),
            "work_identity": work,
            "turn": bound["turn"],
            "normative_baseline": baseline,
            "spec": None,
            "spec_admitted": False,
            "work": {"request": request, "plan": plan, "slice": started["slice"]},
            "disposition": disposition,
            "admission": {
                "fingerprint": task_digest,
                "normalized_match": not bool(work_ref),
                "identity_role": "DEDUP_HINT_ONLY",
            },
            "persistence": {
                "identity": "CANONICAL",
                "working_state": "PROGRESSIVE",
                "playbook": "VOLATILE/PROGRESSIVE",
            },
            "rule": "Prompt fingerprints deduplicate admission candidates; WorkIdentity is durable and explicit after admission.",
        }

    # ---------- normative mutation closure ----------
    def create_spec(self, *, work_id: str | None = None, turn_id: str | None = None, actor_id: str | None = None, **kwargs: Any):
        family_id = kwargs.get("family_id")
        work = self._work_for_family(family_id) if family_id else None
        if work:
            if work_id and work_id != work["entity_id"]:
                raise WorkIdentityError("spec work_id mismatch")
            if not actor_id:
                raise WorkTurnError("actor_id is required for normative mutation")
            self._require_work_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"MODIFY"})
        saved = super().create_spec(**kwargs)
        if work:
            self._refresh_normative_baseline(work["entity_id"])
            self._refresh_work_view(work["entity_id"])
        return saved

    def register_contract(self, *, work_id: str | None = None, turn_id: str | None = None, **kwargs: Any):
        family_id = kwargs.get("family_id")
        actor_id = kwargs.get("actor_id")
        work = self._work_for_family(family_id) if family_id else None
        if work:
            if work_id and work_id != work["entity_id"]:
                raise WorkIdentityError("contract work_id mismatch")
            if not actor_id:
                raise WorkTurnError("actor_id is required for normative mutation")
            self._require_work_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"MODIFY"})
        saved = super().register_contract(**kwargs)
        if work:
            self._refresh_normative_baseline(work["entity_id"])
            self._refresh_work_view(work["entity_id"])
        return saved

    def link(self, *, work_id: str | None = None, turn_id: str | None = None, **kwargs: Any):
        relation = str(kwargs.get("relation") or "").upper()
        from_type = str(kwargs.get("from_type") or "").upper()
        source_actor_id = kwargs.get("source_actor_id")
        work = None
        if relation in {
            RelationType.ADDS_TO.value, RelationType.AMENDS.value, RelationType.EXTENDS.value,
            RelationType.REPAIRS.value, RelationType.RECOVERS.value, RelationType.SUPERSEDES.value,
            RelationType.CONFLICTS_WITH.value, RelationType.VALIDATES.value,
        } and from_type == EntityType.CONTRACT.value:
            contract = self._must_get("contracts", kwargs["from_id"])
            work = self._work_for_family(contract["family_id"])
            if work:
                if work_id and work_id != work["entity_id"]:
                    raise WorkIdentityError("relation work_id mismatch")
                if not source_actor_id:
                    raise WorkTurnError("source_actor_id is required for normative mutation")
                self._require_work_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=source_actor_id, allowed_modes={"MODIFY"})
        saved = super().link(**kwargs)
        if work and kwargs.get("status", "CONFIRMED").upper() == EdgeStatus.CONFIRMED.value:
            self._refresh_normative_baseline(work["entity_id"])
            self._refresh_work_view(work["entity_id"])
        return saved

    # ---------- assurance history bound to WorkIdentity ----------
    def _baseline_for_slice(self, slice_id: str) -> str | None:
        sl = self._must_get("slices", slice_id)
        plan_id = sl.get("last_plan_id") or sl.get("active_plan_id")
        plan = self.store.get("plans", plan_id) if plan_id else None
        return (plan or {}).get("normative_baseline_id")

    def _append_assurance_event(self, *, work_id: str, subject_id: str, event_type: str, actor_id: str | None, baseline_id: str | None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        doc = {
            **_base_doc(),
            "work_id": work_id,
            "subject_id": subject_id,
            "event_type": event_type,
            "actor_id": actor_id,
            "normative_baseline_id": baseline_id,
            "payload": dict(payload or {}),
            "persistence_level": "CANONICAL",
        }
        saved = self.store.insert("assurance_events", doc)
        self._refresh_work_view(work_id)
        return saved

    def claim_done(self, *, slice_id: str, actor_id: str, plan_id: str, summary: str | None = None):
        result = super().claim_done(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id, summary=summary)
        work = self._work_for_slice(slice_id)
        if work:
            self._append_assurance_event(
                work_id=work["entity_id"], subject_id=slice_id, event_type="DONE_CLAIMED",
                actor_id=actor_id, baseline_id=self._baseline_for_slice(slice_id), payload={"summary": summary},
            )
        return result

    def validate_slice(
        self,
        *,
        slice_id: str,
        validator_actor_id: str,
        status: str,
        note: str | None = None,
        completed_items: list[str] | None = None,
        open_deltas: list[str] | None = None,
        evidence_ids: list[str] | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        work = self._work_for_slice(slice_id)
        if work is None:
            raise InvalidTransition("validation requires admitted WorkIdentity")
        self._require_work_turn(
            work_id=work["entity_id"],
            turn_id=turn_id,
            actor_id=validator_actor_id,
            allowed_modes={"VERIFY", "CONTROL"},
        )
        sl = self._must_get("slices", slice_id)
        if sl.get("execution_state") != ExecutionState.DONE_CLAIMED.value:
            raise InvalidTransition("validation requires DONE_CLAIMED execution state")
        if sl.get("assurance_state") in {AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value}:
            raise InvalidTransition("validation cannot rewrite VERIFIED/ACCEPTED assurance")
        normalized = ValidationState(str(status).upper())
        if normalized not in {ValidationState.VALIDATED, ValidationState.REWORK_REQUIRED, ValidationState.INCONCLUSIVE}:
            raise InvalidTransition(f"unsupported validation status {status}")
        completed = [str(item).strip() for item in (completed_items or []) if str(item).strip()]
        remaining = [str(item).strip() for item in (open_deltas or []) if str(item).strip()]
        if normalized == ValidationState.VALIDATED and remaining:
            raise InvalidTransition("VALIDATED cannot carry unresolved validation_open_deltas")
        if normalized == ValidationState.REWORK_REQUIRED and not remaining:
            raise InvalidTransition("REWORK_REQUIRED requires at least one explicit open delta")
        valid_evidence: list[str] = []
        for evidence_id in evidence_ids or []:
            evidence = self._must_get("evidence", evidence_id)
            if evidence.get("subject_id") != slice_id:
                raise InvalidTransition(f"validation evidence {evidence_id} does not belong to Slice {slice_id}")
            valid_evidence.append(evidence_id)
        now = utcnow()
        updated = self._update(
            "slices",
            slice_id,
            {
                "validation_state": normalized.value,
                "validation_at": now,
                "validation_actor_id": validator_actor_id,
                "validation_note": note,
                "validation_completed_items": list(dict.fromkeys(completed)),
                "validation_open_deltas": list(dict.fromkeys(remaining)),
                "validation_evidence_ids": list(dict.fromkeys(valid_evidence)),
                "closure_state": ClosureState.OPEN.value,
                "closed_at": None,
                "closed_by": None,
                "last_activity_at": now,
                "updated_at": now,
            },
            expected_revision=int(sl.get("revision", 0)),
        )
        self._append_assurance_event(
            work_id=work["entity_id"],
            subject_id=slice_id,
            event_type=f"VALIDATION_{normalized.value}",
            actor_id=validator_actor_id,
            baseline_id=self._baseline_for_slice(slice_id),
            payload={
                "note": note,
                "completed_items": completed,
                "open_deltas": remaining,
                "evidence_ids": valid_evidence,
            },
        )
        self._project_family(sl["family_id"])
        return updated

    def submit_evidence(self, **kwargs: Any):
        saved = super().submit_evidence(**kwargs)
        subject_id = kwargs["subject_id"]
        work = None
        if self.store.get("slices", subject_id):
            work = self._work_for_slice(subject_id)
        elif self.store.get("families", subject_id):
            work = self._work_for_family(subject_id)
        if work:
            baseline_id = self._baseline_for_slice(subject_id) if self.store.get("slices", subject_id) else None
            saved = self._update(
                "evidence", saved["entity_id"],
                {"work_id": work["entity_id"], "normative_baseline_id": baseline_id, "persistence_level": "CANONICAL", "updated_at": utcnow()},
                expected_revision=int(saved.get("revision", 0)),
            )
            self._refresh_work_view(work["entity_id"])
        return saved

    def set_gate(self, *, turn_id: str | None = None, **kwargs: Any):
        slice_id = kwargs["slice_id"]
        actor_id = kwargs.get("actor_id")
        work = self._work_for_slice(slice_id)
        if work:
            if not actor_id:
                raise WorkTurnError("actor_id is required for work-bound gate mutation")
            self._require_work_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"VERIFY", "CONTROL"})
        return super().set_gate(**kwargs)

    def submit_verification_observation(self, *, turn_id: str | None = None, **kwargs: Any):
        slice_id = kwargs["slice_id"]
        actor_id = kwargs["verifier_actor_id"]
        work = self._work_for_slice(slice_id)
        if work:
            self._require_work_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"VERIFY"})
        saved = super().submit_verification_observation(**kwargs)
        if work:
            saved = self._update(
                "evidence", saved["entity_id"],
                {"work_id": work["entity_id"], "normative_baseline_id": self._baseline_for_slice(slice_id), "persistence_level": "CANONICAL", "updated_at": utcnow()},
                expected_revision=int(saved.get("revision", 0)),
            )
            self._refresh_work_view(work["entity_id"])
        return saved

    def verify_slice(self, *, turn_id: str | None = None, close_slice: bool = True, **kwargs: Any):
        slice_id = kwargs["slice_id"]
        actor_id = kwargs["verifier_actor_id"]
        work = self._work_for_slice(slice_id)
        if work is None:
            return super().verify_slice(**kwargs)
        self._require_work_turn(
            work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"VERIFY"}
        )
        before = self._must_get("slices", slice_id)
        if before.get("validation_state") != ValidationState.VALIDATED.value:
            raise InvalidTransition("verification requires VALIDATED Slice state")
        plan_id = before.get("last_plan_id")
        if plan_id:
            self._assert_plan_baseline_current(self._must_get("plans", plan_id))
        result = super().verify_slice(**kwargs)
        self._append_assurance_event(
            work_id=work["entity_id"], subject_id=slice_id, event_type="VERIFIED",
            actor_id=actor_id, baseline_id=self._baseline_for_slice(slice_id),
            payload={"verification_profile": result.get("verification_profile")},
        )
        blockers = unresolved_required_effects(self, slice_id)
        closed = bool(close_slice) and not blockers
        if closed:
            now = utcnow()
            current = self._must_get("slices", slice_id)
            result = self._update(
                "slices",
                slice_id,
                {
                    "closure_state": ClosureState.CLOSED.value,
                    "closed_at": now,
                    "closed_by": actor_id,
                    "last_activity_at": now,
                    "updated_at": now,
                },
                expected_revision=int(current.get("revision", 0)),
            )
            self._append_assurance_event(
                work_id=work["entity_id"], subject_id=slice_id, event_type="CLOSED",
                actor_id=actor_id, baseline_id=self._baseline_for_slice(slice_id),
                payload={"reason": "VERIFIED_WITHOUT_OPEN_REQUIRED_EFFECTS"},
            )
        else:
            current = self._must_get("slices", slice_id)
            if current.get("closure_state") != ClosureState.OPEN.value:
                result = self._update(
                    "slices",
                    slice_id,
                    {"closure_state": ClosureState.OPEN.value, "closed_at": None, "closed_by": None, "updated_at": utcnow()},
                    expected_revision=int(current.get("revision", 0)),
                )
            else:
                result = current
        result = dict(result)
        result["closure_decision"] = {
            "requested": bool(close_slice),
            "closed": closed,
            "blocking_effect_ids": [row["entity_id"] for row in blockers],
        }
        self._project_family(self._must_get("slices", slice_id)["family_id"])
        self._refresh_work_view(work["entity_id"])
        return result

    def close_verified_slice(
        self,
        *,
        slice_id: str,
        verifier_actor_id: str,
        verifier_token: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            require_verifier(verifier_actor_id, verifier_token)
        except CapabilityDenied as exc:
            raise ApprovalRequired(str(exc)) from exc
        sl = self._must_get("slices", slice_id)
        work = self._work_for_slice(slice_id)
        if work is None:
            raise InvalidTransition("closure requires admitted WorkIdentity")
        self._require_work_turn(
            work_id=work["entity_id"],
            turn_id=turn_id,
            actor_id=verifier_actor_id,
            allowed_modes={"VERIFY"},
        )
        if sl.get("validation_state") != ValidationState.VALIDATED.value:
            raise InvalidTransition("closure requires VALIDATED Slice state")
        if sl.get("assurance_state") not in {AssuranceState.VERIFIED.value, AssuranceState.ACCEPTED.value}:
            raise InvalidTransition("closure requires VERIFIED assurance")
        if sl.get("closure_state") == ClosureState.CLOSED.value:
            return sl
        blockers = unresolved_required_effects(self, slice_id)
        if blockers:
            raise InvalidTransition(
                "slice closure blocked by unresolved required effects: "
                + ",".join(row["entity_id"] for row in blockers)
            )
        now = utcnow()
        updated = self._update(
            "slices",
            slice_id,
            {
                "closure_state": ClosureState.CLOSED.value,
                "closed_at": now,
                "closed_by": verifier_actor_id,
                "last_activity_at": now,
                "updated_at": now,
            },
            expected_revision=int(sl.get("revision", 0)),
        )
        self._append_assurance_event(
            work_id=work["entity_id"], subject_id=slice_id, event_type="CLOSED",
            actor_id=verifier_actor_id, baseline_id=self._baseline_for_slice(slice_id),
            payload={"reason": "RECONCILED_AFTER_VERIFICATION"},
        )
        self._project_family(sl["family_id"])
        return updated

    def accept_slice(self, *, turn_id: str | None = None, **kwargs: Any):
        slice_id = kwargs["slice_id"]
        work = self._work_for_slice(slice_id)
        if work is not None and self._must_get("slices", slice_id).get("closure_state") != ClosureState.CLOSED.value:
            raise InvalidTransition("ACCEPTED requires CLOSED Slice state")
        if work:
            approval = self._must_get("approvals", kwargs["approval_id"])
            actor_id = approval.get("decided_by")
            if not actor_id:
                raise WorkTurnError("approved acceptance has no actor for CONTROL binding")
            self._require_work_turn(work_id=work["entity_id"], turn_id=turn_id, actor_id=actor_id, allowed_modes={"CONTROL"})
        result = super().accept_slice(**kwargs)
        if work:
            self._append_assurance_event(
                work_id=work["entity_id"], subject_id=slice_id, event_type="ACCEPTED",
                actor_id=result.get("accepted_by"), baseline_id=self._baseline_for_slice(slice_id),
                payload={"approval_id": kwargs["approval_id"]},
            )
        return result

    # ---------- materialized work view / context ----------
    def _build_work_view(self, work: dict[str, Any]) -> dict[str, Any]:
        baselines = sorted(self.store.find("normative_baselines", {"work_id": work["entity_id"]}), key=lambda x: str(x.get("created_at")))
        plans = [p for p in self.store.find("plans", {"work_id": work["entity_id"]}) if p.get("status") in {"RECORDED", "ACTIVE"}]
        checkpoints = sorted(self.store.find("work_checkpoints", {"work_id": work["entity_id"]}), key=lambda x: str(x.get("created_at")))
        turns = sorted(self.store.find("work_turn_bindings", {"work_id": work["entity_id"]}), key=lambda x: str(x.get("created_at")))
        selections = sorted(self.store.find("playbook_selections", {"work_id": work["entity_id"]}), key=lambda x: str(x.get("created_at")))
        assurance = sorted(self.store.find("assurance_events", {"work_id": work["entity_id"]}), key=lambda x: str(x.get("created_at")))
        effects = sorted(self.store.find("effects", {"work_id": work["entity_id"]}), key=lambda x: str(x.get("created_at")))
        open_effects = [
            effect for effect in effects
            if not (effect.get("state") == "RECONCILED" and effect.get("satisfied") is True)
        ]
        return {
            "work_id": work["entity_id"],
            "family_id": work["family_id"],
            "project_id": work["project_id"],
            "current_normative_baseline_id": baselines[-1]["entity_id"] if baselines else None,
            "active_plan_ids": [p["entity_id"] for p in plans],
            "latest_checkpoint_id": checkpoints[-1]["entity_id"] if checkpoints else None,
            "latest_turn_id": turns[-1]["entity_id"] if turns else None,
            "latest_playbook_selection_id": selections[-1]["entity_id"] if selections else None,
            "assurance_cursor": assurance[-1]["entity_id"] if assurance else None,
            "assurance_event_count": len(assurance),
            "open_effect_ids": [effect["entity_id"] for effect in open_effects],
            "open_effect_count": len(open_effects),
            "updated_at": utcnow(),
        }

    def _refresh_work_view(self, work_ref: str) -> dict[str, Any]:
        work = self._resolve_work(work_ref)
        view = self._build_work_view(work)
        rows = self.store.find("work_views", {"work_id": work["entity_id"]})
        if rows:
            return self._update("work_views", rows[0]["entity_id"], view, expected_revision=int(rows[0].get("revision", 0)))
        return self.store.insert("work_views", {**_base_doc(), **view, "persistence_level": "CANONICAL"})

    def work_context(self, work_ref: str) -> dict[str, Any]:
        work = self._resolve_work(work_ref)
        views = self.store.find("work_views", {"work_id": work["entity_id"]})
        view = views[0] if views else self._build_work_view(work)
        baseline = self.store.get("normative_baselines", view.get("current_normative_baseline_id")) if view.get("current_normative_baseline_id") else None
        checkpoint = self.store.get("work_checkpoints", view.get("latest_checkpoint_id")) if view.get("latest_checkpoint_id") else None
        selection = self.store.get("playbook_selections", view.get("latest_playbook_selection_id")) if view.get("latest_playbook_selection_id") else None
        playbook = self.store.get("playbooks", selection.get("playbook_id")) if selection else None
        assurance = self.store.find("assurance_events", {"work_id": work["entity_id"]})
        return {
            "work_identity": work,
            "work_view": view,
            "canonical": {
                "persistence_level": "CANONICAL",
                "work_identity": work,
                "normative_baseline": baseline,
                "assurance_history": assurance,
            },
            "progressive": {
                "persistence_level": "PROGRESSIVE",
                "latest_checkpoint": checkpoint,
                "playbook_selection": selection,
            },
            "volatile": {
                "persistence_level": "VOLATILE",
                "playbook": playbook,
                "authority": "PROCEDURAL_NON_NORMATIVE",
            },
            "rule": "Playbooks may change; Specs may evolve; WorkIdentity and assurance history survive both.",
        }

    def status(self, family_id: str) -> dict[str, Any]:
        """Read the materialized family projection for admitted v0.3 work.

        Write paths already refresh project_views. The hot read path therefore does
        not recompute-and-write family state. Legacy families keep the v0.2 behavior.
        """
        if self._work_for_family(family_id):
            view = self.store.get("project_views", family_id)
            if view is not None:
                return view
        return super().status(family_id)

    def effective_family_view(self, family_id: str) -> dict[str, Any]:
        base = super().effective_family_view(family_id)
        work = self._work_for_family(family_id)
        if not work:
            base["work_identity"] = None
            return base
        semantics = self._normative_semantics(work)
        semantic_hash = _canonical_hash(semantics)
        rows = self.store.find("normative_baselines", {"work_id": work["entity_id"], "semantic_hash": semantic_hash})
        baseline = rows[0] if rows else {
            "entity_id": None, "work_id": work["entity_id"], "family_id": family_id,
            "semantic_hash": semantic_hash, "semantics": semantics, "persistence_level": "CANONICAL",
            "status": "UNMATERIALIZED",
        }
        base["work_identity"] = work
        base["effective_normative_baseline"] = baseline
        base["effective_truth_hash"] = semantic_hash
        base["playbooks_affect_effective_truth"] = False
        return base

    def project_overview(self, project_ref: str) -> dict[str, Any]:
        overview = super().project_overview(project_ref)
        project = overview.get("project") or {}
        family_ids = [row.get("family_id") for row in overview.get("families") or [] if row.get("family_id")]
        work_rows = [row for row in self.store.find("work_identities") if row.get("family_id") in set(family_ids)]
        bound_families = {row.get("family_id") for row in work_rows}
        overview["work_identities"] = work_rows
        overview["work_identity_count"] = len(work_rows)
        overview["legacy_family_ids"] = [fid for fid in family_ids if fid not in bound_families]
        overview["work_identity_required_for_productive_mutation"] = True
        overview["zero_touch_new_work_admission"] = "AUTOMATIC_FROM_CURRENT_USER_INTENT"
        overview["user_supplied_work_ref_required_for_new_work"] = False
        overview["user_confirmation_required_for_new_work"] = False
        overview["project_work_identity_coverage"] = (
            len(bound_families) / len(family_ids) if family_ids else 1.0
        )
        return overview

    def session_restore(self, project_ref: str) -> dict[str, Any]:
        restored = super().session_restore(project_ref)
        if restored.get("restore_state") in {"STATE_NOT_FOUND", None}:
            return restored
        remaining: list[str] = []
        for reason in list(restored.get("reason_codes") or []):
            if not str(reason).endswith(":CURRENT_SPEC_MISSING"):
                remaining.append(reason)
                continue
            family_id = str(reason).split(":", 1)[0]
            work = self._work_for_family(family_id)
            if work is None:
                remaining.append(reason)
                continue
            try:
                baseline = self.current_normative_baseline(work["entity_id"], materialize=False)
            except (KeyError, NormativeBaselineDrift):
                remaining.append(reason)
                continue
            kind = str((((baseline.get("semantics") or {}).get("source") or {}).get("kind")) or "")
            # New user-intent work is intentionally executable without manufacturing a Spec.
            # Historical backfill without a Spec remains partial until a normative target is admitted.
            if kind not in {"OPERATIONAL_INTENT", "SPECIFICATION"}:
                remaining.append(reason)
        if restored.get("families") and not remaining:
            restored["restore_state"] = "STATE_FOUND"
        restored["reason_codes"] = sorted(set(remaining))
        restored["productive_execution_allowed"] = False
        restored["current_turn_execution_authorized"] = False
        restored["turn_binding_required"] = True
        restored["execution_rule"] = (
            "RECOVERED_WORK_IS_CONTEXT_NOT_CURRENT_INTENT; bind the current user turn to WorkIdentity before execution. "
            "A missing Specification is acceptable only when the current canonical baseline is admitted OPERATIONAL_INTENT; "
            "historical backfill without normative target remains partial."
        )
        pending_closure: list[dict[str, Any]] = []
        next_items = list(restored.get("next_executable_items") or [])
        known_next = {item.get("entity_id") for item in next_items}
        for family in restored.get("families") or []:
            family_id = family.get("family_id")
            for item in family.get("recovery_slices") or []:
                if item.get("validation_state") == ValidationState.REWORK_REQUIRED.value and item.get("entity_id") not in known_next:
                    next_items.append({"family_id": family_id, **item})
                    known_next.add(item.get("entity_id"))
                if item.get("execution_state") == ExecutionState.DONE_CLAIMED.value and item.get("closure_state") != ClosureState.CLOSED.value:
                    pending_closure.append({"family_id": family_id, **item})
        restored["next_executable_items"] = next_items
        restored["pending_closure_items"] = pending_closure
        # Recovery exposes executable candidates but never grants current-turn execution.
        # The caller must bind/reconcile the current user turn before productive effects.
        restored["productive_execution_allowed"] = False
        restored["current_turn_execution_authorized"] = False
        return restored

    def recovery_context(self, project_ref: str) -> dict[str, Any]:
        context = super().recovery_context(project_ref)
        work_items = []
        for family in context.get("families") or []:
            work = self._work_for_family(family.get("family_id"))
            if work:
                wc = self.work_context(work["entity_id"])
                family["work_identity"] = work
                family["persistence"] = {
                    "canonical": wc["canonical"],
                    "progressive": wc["progressive"],
                    "volatile_included": False,
                }
                work_items.append(work["entity_id"])
        for family in context.get("families") or []:
            family_id = family.get("family_id")
            effects = sorted(self.store.find("effects", {"family_id": family_id}), key=lambda row: str(row.get("created_at") or ""))
            family["open_effects"] = [effect for effect in effects if not (effect.get("state") == "RECONCILED" and effect.get("satisfied") is True)]
            recovery = list(family.get("recovery_slices") or [])
            known = {item.get("entity_id") for item in recovery}
            relevant = [sl for sl in self.store.find("slices", {"family_id": family_id}) if sl.get("validation_state") in {ValidationState.PENDING.value, ValidationState.REWORK_REQUIRED.value, ValidationState.INCONCLUSIVE.value} or (sl.get("execution_state") == ExecutionState.DONE_CLAIMED.value and sl.get("closure_state") != ClosureState.CLOSED.value)]
            for full in relevant:
                if full.get("entity_id") not in known:
                    recovery.append({"entity_id": full.get("entity_id"), "declared_id": full.get("declared_id"), "title": full.get("title"), "objective": full.get("objective"), "execution_state": full.get("execution_state"), "assurance_state": full.get("assurance_state"), "active_plan_id": full.get("active_plan_id"), "depends_on": full.get("depends_on") or [], "dependency_requirements": full.get("dependency_requirements") or [], "gates": full.get("gates") or []})
            for item in recovery:
                full = self.store.get("slices", item.get("entity_id"))
                if full:
                    item["validation_state"] = full.get("validation_state")
                    item["closure_state"] = full.get("closure_state")
            family["recovery_slices"] = recovery
        context["work_identity_ids"] = work_items
        context["recovery_priority"] = [
            "CURRENT_USER_TURN",
            "CANONICAL_WORK_IDENTITY",
            "CURRENT_NORMATIVE_BASELINE",
            "ASSURANCE_HISTORY",
            "PROGRESSIVE_CHECKPOINT",
            "DERIVED_PLAN_AND_SLICE_STATE",
        ]
        context["rule"] = "Recovery follows WorkIdentity. Progressive state, Playbooks, filesystem and agent prose may validate or guide work but can never synthesize canonical identity or assurance."
        return context
