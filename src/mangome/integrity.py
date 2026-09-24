from __future__ import annotations

from fnmatch import fnmatch
from typing import Any

from .authority import CapabilityDenied, require_approver, require_verifier
from .enums import AssuranceState, ClaimType, EvidenceClass, EvidenceTrust, EvidenceVerdict, ExecutionState
from .filesystem import reproduction_fingerprint
from .models import utcnow
from .service import ApprovalRequired, InvalidTransition, MangoMeService


_ADMISSIBLE_CLASSES = {
    EvidenceClass.TEST_RESULT.value,
    EvidenceClass.RUNTIME_OBSERVATION.value,
    EvidenceClass.STATIC_ANALYSIS.value,
    EvidenceClass.ARTIFACT_CHECK.value,
    EvidenceClass.HUMAN_ATTESTATION.value,
    EvidenceClass.EXTERNAL_REVIEW.value,
}
_ADMISSIBLE_TRUST = {EvidenceTrust.VERIFIER_ATTESTED.value, EvidenceTrust.OWNER_ATTESTED.value}

_VERIFICATION_OBSERVATION_VERSION = "AV/1"
_VERIFICATION_OBSERVATION_TYPES = {"REPLAY", "DIFF", "SCOPE", "SPEC_CHECK", "RUNTIME", "ARTIFACT", "OTHER"}
_VERIFICATION_OBSERVATION_STATUS = {"PASS", "FAIL", "UNVERIFIABLE"}


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _scope_match(path: str, pattern: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_pattern = _normalize_path(pattern).rstrip("/")
    if not normalized_pattern:
        return False
    if any(ch in normalized_pattern for ch in "*?["):
        return fnmatch(normalized_path, normalized_pattern)
    return normalized_path == normalized_pattern or normalized_path.startswith(normalized_pattern + "/")


def _looks_like_test_path(path: str) -> bool:
    normalized = "/" + _normalize_path(path).lower()
    name = normalized.rsplit("/", 1)[-1]
    return (
        "/tests/" in normalized
        or "/test/" in normalized
        or name.startswith(("test_", "spec_"))
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


class IntegrityMangoMeService(MangoMeService):
    """MangoMe service with runtime-capability-backed assurance invariants."""

    def request_override(self, *, action_type: str, subject_id: str, requested_by: str, reason: str) -> dict[str, Any]:
        action = action_type.upper()
        if action == "ACCEPT_SLICE":
            self._must_get("slices", subject_id)
        elif action == "WAIVE_GATE":
            known_subjects = {
                f"{sl['entity_id']}:{gate.get('gate_id')}"
                for sl in self.store.find("slices")
                for gate in sl.get("gates", [])
            }
            if subject_id not in known_subjects:
                raise KeyError(f"unknown gate approval subject {subject_id}")
        return super().request_override(action_type=action, subject_id=subject_id, requested_by=requested_by, reason=reason)

    def _must_get_approved(self, approval_id: str, *, action_type: str, subject_id: str) -> dict[str, Any]:
        approval = self._must_get("approvals", approval_id)
        if approval.get("status") != "APPROVED":
            raise ApprovalRequired("approval is not APPROVED")
        if approval.get("action_type") != action_type:
            raise ApprovalRequired(f"approval action mismatch: expected {action_type}, got {approval.get('action_type')}")
        if approval.get("subject_id") != subject_id:
            raise ApprovalRequired("approval subject does not match requested action")
        return approval

    def attest_evidence(
        self,
        *,
        evidence_id: str,
        attested_by: str,
        capability_token: str | None = None,
        authority: str = "VERIFIER",
    ) -> dict[str, Any]:
        evidence = self._must_get("evidence", evidence_id)
        authority = authority.upper()
        try:
            if authority == "OWNER":
                require_approver(attested_by, capability_token)
                trust = EvidenceTrust.OWNER_ATTESTED.value
            elif authority == "VERIFIER":
                require_verifier(attested_by, capability_token)
                trust = EvidenceTrust.VERIFIER_ATTESTED.value
            else:
                raise InvalidTransition("authority must be VERIFIER or OWNER")
        except CapabilityDenied as exc:
            raise ApprovalRequired(str(exc)) from exc
        return self._update(
            "evidence",
            evidence_id,
            {"trust": trust, "attested_by": attested_by, "attested_at": utcnow(), "updated_at": utcnow()},
            expected_revision=int(evidence.get("revision", 0)),
        )

    def _validate_evidence_ids(self, *, slice_id: str, evidence_ids: list[str], require_pass: bool = True) -> list[dict[str, Any]]:
        if not evidence_ids:
            raise InvalidTransition("PASS/verification requires at least one persisted evidence id")
        resolved: list[dict[str, Any]] = []
        for evidence_id in evidence_ids:
            evidence = self._must_get("evidence", evidence_id)
            if evidence.get("subject_id") != slice_id:
                raise InvalidTransition(f"evidence {evidence_id} does not belong to slice {slice_id}")
            if evidence.get("evidence_class") not in _ADMISSIBLE_CLASSES:
                raise InvalidTransition(f"evidence {evidence_id} class is not admissible for verification")
            if evidence.get("trust") not in _ADMISSIBLE_TRUST:
                raise InvalidTransition(f"evidence {evidence_id} has not been attested by a trusted verifier/owner")
            if require_pass and evidence.get("verdict") != EvidenceVerdict.PASS.value:
                raise InvalidTransition(f"evidence {evidence_id} does not carry PASS verdict")
            resolved.append(evidence)
        return resolved

    @staticmethod
    def _verification_observation(evidence: dict[str, Any]) -> dict[str, Any] | None:
        payload = evidence.get("payload") or {}
        observation = payload.get("verification_observation")
        if not isinstance(observation, dict) or observation.get("version") != _VERIFICATION_OBSERVATION_VERSION:
            return None
        return observation

    def _is_independent_observation(self, evidence: dict[str, Any], *, executor_actor_id: str | None) -> bool:
        observation = self._verification_observation(evidence)
        if not observation:
            return False
        observed_by = observation.get("observed_by")
        observation_type = str(observation.get("observation_type") or "").upper()
        status = str(observation.get("status") or "").upper()
        if not observed_by or (executor_actor_id and observed_by == executor_actor_id):
            return False
        if observation_type not in _VERIFICATION_OBSERVATION_TYPES or status not in _VERIFICATION_OBSERVATION_STATUS:
            return False
        if evidence.get("evidence_class") not in _ADMISSIBLE_CLASSES:
            return False
        if evidence.get("actor_id") != observed_by or evidence.get("attested_by") != observed_by:
            return False
        if evidence.get("trust") not in _ADMISSIBLE_TRUST:
            return False
        expected_verdict = {"PASS": EvidenceVerdict.PASS.value, "FAIL": EvidenceVerdict.FAIL.value, "UNVERIFIABLE": EvidenceVerdict.UNKNOWN.value}[status]
        if evidence.get("verdict") != expected_verdict:
            return False
        original_evidence_id = observation.get("original_evidence_id")
        if original_evidence_id:
            original = self.store.get("evidence", original_evidence_id)
            if not original or original.get("subject_id") != evidence.get("subject_id"):
                return False
        reproduction = (evidence.get("payload") or {}).get("reproduction")
        if observation_type == "REPLAY" and not isinstance(reproduction, dict):
            return False
        if isinstance(reproduction, dict):
            if reproduction.get("version") != "RB/1":
                return False
            fingerprint = reproduction.get("fingerprint")
            if not fingerprint or fingerprint != reproduction_fingerprint(reproduction):
                return False
        return True

    def _is_independent_pass_observation(self, evidence: dict[str, Any], *, executor_actor_id: str | None) -> bool:
        observation = self._verification_observation(evidence)
        return bool(
            self._is_independent_observation(evidence, executor_actor_id=executor_actor_id)
            and observation
            and observation.get("status") == "PASS"
            and evidence.get("verdict") == EvidenceVerdict.PASS.value
        )

    def review_change_set(self, *, slice_id: str, changed_paths: list[str]) -> dict[str, Any]:
        """Compare a verifier-observed change set with the persisted plan scope.

        This is deterministic navigation/risk detection only. It does not infer fraud,
        correctness, or verification from a changed path.
        """
        sl = self._must_get("slices", slice_id)
        plan_id = sl.get("last_plan_id")
        plan = self.store.get("plans", plan_id) if plan_id else None
        expected_scope = list((plan or {}).get("expected_scope") or [])
        normalized = list(dict.fromkeys(_normalize_path(path) for path in changed_paths if str(path).strip()))
        out_of_scope = [] if not expected_scope else [
            path for path in normalized if not any(_scope_match(path, pattern) for pattern in expected_scope)
        ]
        test_changes = [path for path in normalized if _looks_like_test_path(path)]
        if not expected_scope:
            status = "UNSPECIFIED"
        elif out_of_scope:
            status = "OUT_OF_SCOPE"
        else:
            status = "WITHIN_SCOPE"
        risk_flags: list[str] = []
        if out_of_scope:
            risk_flags.append("SCOPE_DEVIATION")
        if test_changes:
            risk_flags.append("TEST_CHANGE_REVIEW_REQUIRED")
        return {
            "slice_id": slice_id,
            "plan_id": plan_id,
            "status": status,
            "expected_scope": expected_scope,
            "changed_paths": normalized,
            "out_of_scope_paths": out_of_scope,
            "test_change_paths": test_changes,
            "risk_flags": risk_flags,
            "rule": "A scope or test-change flag is a review signal, not proof of misconduct or incorrectness.",
        }

    def completion_review(self, *, slice_id: str, changed_paths: list[str] | None = None) -> dict[str, Any]:
        """Build a deterministic adversarial-verification brief for DONE_CLAIMED work."""
        sl = self._must_get("slices", slice_id)
        plan_id = sl.get("last_plan_id")
        plan = self.store.get("plans", plan_id) if plan_id else None
        spec_id = (plan or {}).get("spec_id")
        spec = self.store.get("specs", spec_id) if spec_id else None
        claims = sorted(
            self.store.find("claims", {"subject_id": slice_id}),
            key=lambda item: str(item.get("timestamp") or item.get("created_at") or ""),
        )
        evidence = sorted(
            self.store.find("evidence", {"subject_id": slice_id}),
            key=lambda item: str(item.get("created_at") or ""),
        )
        executor = sl.get("last_actor_id")
        independent: list[dict[str, Any]] = []
        worker_evidence_ids: list[str] = []
        for item in evidence:
            observation = self._verification_observation(item)
            if observation and self._is_independent_observation(item, executor_actor_id=executor):
                independent.append({
                    "evidence_id": item.get("entity_id"),
                    "status": observation.get("status"),
                    "observation_type": observation.get("observation_type"),
                    "claim": observation.get("claim"),
                    "observed_by": observation.get("observed_by"),
                    "trust": item.get("trust"),
                })
            elif item.get("actor_id") == executor:
                worker_evidence_ids.append(item.get("entity_id"))
        risk_flags: list[str] = []
        if sl.get("execution_state") != ExecutionState.DONE_CLAIMED.value:
            risk_flags.append("NOT_DONE_CLAIMED")
        if not independent:
            risk_flags.append("NO_INDEPENDENT_OBSERVATION")
        if worker_evidence_ids and not independent:
            risk_flags.append("WORKER_ONLY_EVIDENCE")
        if any(obs.get("status") == "FAIL" for obs in independent):
            risk_flags.append("OBSERVED_FAILURE_PRESENT")
        if any(obs.get("status") == "UNVERIFIABLE" for obs in independent):
            risk_flags.append("UNVERIFIABLE_CLAIM_PRESENT")
        scope_review = self.review_change_set(slice_id=slice_id, changed_paths=changed_paths or []) if changed_paths is not None else None
        if scope_review:
            risk_flags.extend(flag for flag in scope_review["risk_flags"] if flag not in risk_flags)
        return {
            "slice_id": slice_id,
            "execution_state": sl.get("execution_state"),
            "assurance_state": sl.get("assurance_state"),
            "executor_actor_id": executor,
            "plan_id": plan_id,
            "expected_scope": list((plan or {}).get("expected_scope") or []),
            "expected_artifacts": list((plan or {}).get("expected_artifacts") or []),
            "acceptance_expectations": list((plan or {}).get("acceptance_expectations") or []),
            "acceptance_criteria": list((spec or {}).get("acceptance_criteria") or []),
            "required_evidence": list((spec or {}).get("required_evidence") or []),
            "persisted_claims": [
                {"claim_id": c.get("entity_id"), "claim_type": c.get("claim_type"), "actor_id": c.get("actor_id"), "value": c.get("value")}
                for c in claims
            ],
            "worker_evidence_ids": worker_evidence_ids,
            "independent_observations": independent,
            "scope_review": scope_review,
            "risk_flags": risk_flags,
            "review_checks": [
                "REPRODUCE_LOAD_BEARING_CLAIMS",
                "COMPARE_ACTUAL_CHANGESET_TO_PLAN_SCOPE",
                "REVIEW_CHANGED_TESTS_AGAINST_SPEC",
                "VERIFY_TARGET_AND_SURROUNDING_SYSTEM",
                "LABEL_UNVERIFIABLE_AS_UNKNOWN",
            ],
            "rule": "The completion report and worker Evidence are claims to inspect, not independent proof. Free-text claims are returned verbatim; MangoMe does not pretend to extract their semantics deterministically.",
        }

    def submit_verification_observation(
        self,
        *,
        slice_id: str,
        verifier_actor_id: str,
        verifier_token: str | None,
        claim: str,
        observation_type: str,
        status: str,
        evidence_type: str,
        evidence_class: str,
        source: str,
        original_evidence_id: str | None = None,
        artifact_id: str | None = None,
        reproduction: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a verifier-observed AV/1 Evidence item.

        MangoMe does not execute the check. The verifier/host must perform the
        observation and submit what it actually observed. Capability enforcement
        makes this materially different from a worker-authored PASS claim.
        """
        try:
            require_verifier(verifier_actor_id, verifier_token)
        except CapabilityDenied as exc:
            raise ApprovalRequired(str(exc)) from exc
        sl = self._must_get("slices", slice_id)
        if sl.get("execution_state") != ExecutionState.DONE_CLAIMED.value:
            raise InvalidTransition("verification observation requires DONE_CLAIMED execution state")
        executor = sl.get("last_actor_id")
        if executor and executor == verifier_actor_id:
            raise InvalidTransition("the last executing actor may not submit its own independent verification observation")
        normalized_type = observation_type.upper()
        normalized_status = status.upper()
        normalized_class = evidence_class.upper()
        if normalized_type not in _VERIFICATION_OBSERVATION_TYPES:
            raise InvalidTransition(f"unsupported observation_type {observation_type}")
        if normalized_status not in _VERIFICATION_OBSERVATION_STATUS:
            raise InvalidTransition(f"unsupported verification observation status {status}")
        if normalized_class not in _ADMISSIBLE_CLASSES:
            raise InvalidTransition(f"evidence class {evidence_class} is not admissible for verification")
        if original_evidence_id:
            original = self._must_get("evidence", original_evidence_id)
            if original.get("subject_id") != slice_id:
                raise InvalidTransition("replayed/original evidence must belong to the same slice")
        if reproduction is not None:
            if reproduction.get("version") != "RB/1":
                raise InvalidTransition("verification reproduction must use RB/1")
            stored_fingerprint = reproduction.get("fingerprint")
            if not stored_fingerprint or stored_fingerprint != reproduction_fingerprint(reproduction):
                raise InvalidTransition("verification reproduction fingerprint mismatch")
        if normalized_type == "REPLAY" and reproduction is None:
            raise InvalidTransition("REPLAY observations require an RB/1 reproduction binding")
        result = {"PASS": "PASS", "FAIL": "FAIL", "UNVERIFIABLE": "UNKNOWN"}[normalized_status]
        payload: dict[str, Any] = dict(details or {})
        if reproduction is not None:
            payload["reproduction"] = reproduction
        payload["verification_observation"] = {
            "version": _VERIFICATION_OBSERVATION_VERSION,
            "claim": claim,
            "observation_type": normalized_type,
            "status": normalized_status,
            "observed_by": verifier_actor_id,
            "original_evidence_id": original_evidence_id,
            "observed_at": utcnow(),
        }
        evidence = super().submit_evidence(
            subject_id=slice_id,
            evidence_type=evidence_type,
            source=source,
            result=result,
            evidence_class=normalized_class,
            artifact_id=artifact_id,
            actor_id=verifier_actor_id,
            payload=payload,
        )
        return self._update(
            "evidence",
            evidence["entity_id"],
            {
                "trust": EvidenceTrust.VERIFIER_ATTESTED.value,
                "attested_by": verifier_actor_id,
                "attested_at": utcnow(),
                "updated_at": utcnow(),
            },
            expected_revision=int(evidence.get("revision", 0)),
        )

    def set_gate(
        self,
        *,
        slice_id: str,
        gate_id: str,
        status: str,
        evidence_ids: list[str] | None = None,
        actor_id: str | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        normalized = status.upper()
        evidence_ids = evidence_ids or []
        if normalized == "PASS":
            self._validate_evidence_ids(slice_id=slice_id, evidence_ids=evidence_ids)
        elif normalized == "WAIVED":
            if not approval_id:
                raise ApprovalRequired("WAIVED requires an approved WAIVE_GATE decision")
            self._must_get_approved(approval_id, action_type="WAIVE_GATE", subject_id=f"{slice_id}:{gate_id}")
        elif normalized == "FAIL":
            if evidence_ids:
                self._validate_evidence_ids(slice_id=slice_id, evidence_ids=evidence_ids, require_pass=False)
        elif normalized != "OPEN":
            raise InvalidTransition(f"unsupported gate status {status}")

        gates = [dict(g) for g in sl.get("gates", [])]
        found = False
        for gate in gates:
            if gate.get("gate_id") == gate_id:
                gate["status"] = normalized
                gate["evidence_ids"] = evidence_ids
                gate["decided_by"] = actor_id
                gate["decided_at"] = utcnow()
                gate["approval_id"] = approval_id
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

    def verify_slice(
        self,
        *,
        slice_id: str,
        verifier_actor_id: str,
        verifier_token: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        try:
            require_verifier(verifier_actor_id, verifier_token)
        except CapabilityDenied as exc:
            raise ApprovalRequired(str(exc)) from exc
        sl = self._must_get("slices", slice_id)
        if sl["execution_state"] != ExecutionState.DONE_CLAIMED.value:
            raise InvalidTransition("verification requires DONE_CLAIMED execution state")
        executor = sl.get("last_actor_id")
        if executor and executor == verifier_actor_id:
            raise InvalidTransition("the last executing actor may not verify its own DONE claim")
        gates = sl.get("gates", [])
        open_or_failed = [g for g in gates if g.get("status") not in {"PASS", "WAIVED"}]
        if open_or_failed:
            raise InvalidTransition(f"verification denied: {len(open_or_failed)} acceptance gates are not PASS/WAIVED")
        gate_evidence: list[str] = []
        independent_observation_ids: list[str] = []
        for gate in gates:
            if gate.get("status") == "PASS":
                ids = list(gate.get("evidence_ids") or [])
                resolved_gate = self._validate_evidence_ids(slice_id=slice_id, evidence_ids=ids)
                independent_gate = [
                    item for item in resolved_gate
                    if self._is_independent_pass_observation(item, executor_actor_id=executor)
                ]
                if not independent_gate:
                    raise InvalidTransition(
                        f"verification denied: PASS gate {gate.get('gate_id')} lacks independent AV/1 observed PASS evidence"
                    )
                independent_observation_ids.extend(item["entity_id"] for item in independent_gate)
                gate_evidence.extend(ids)
            elif gate.get("status") == "WAIVED":
                approval_id = gate.get("approval_id")
                if not approval_id:
                    raise InvalidTransition("WAIVED gate is missing approval reference")
                self._must_get_approved(approval_id, action_type="WAIVE_GATE", subject_id=f"{slice_id}:{gate['gate_id']}")
        explicit = evidence_ids or []
        resolved_explicit: list[dict[str, Any]] = []
        if explicit:
            resolved_explicit = self._validate_evidence_ids(slice_id=slice_id, evidence_ids=explicit)
            independent_observation_ids.extend(
                item["entity_id"] for item in resolved_explicit
                if self._is_independent_pass_observation(item, executor_actor_id=executor)
            )
        proof_ids = list(dict.fromkeys(gate_evidence + explicit))
        independent_observation_ids = list(dict.fromkeys(independent_observation_ids))
        if not gates and not proof_ids:
            raise InvalidTransition("verification of a gateless slice requires explicit attested evidence")
        if not gates and not independent_observation_ids:
            raise InvalidTransition("verification of a gateless slice requires independent AV/1 observed PASS evidence")
        now = utcnow()
        updated = self._update(
            "slices", slice_id,
            {"assurance_state": AssuranceState.VERIFIED.value, "verified_at": now, "last_activity_at": now, "updated_at": now},
            expected_revision=int(sl.get("revision", 0)),
        )
        self._claim(
            verifier_actor_id,
            slice_id,
            ClaimType.TEST_PASSED,
            {
                "verification": True,
                "evidence_ids": proof_ids,
                "independent_observation_ids": independent_observation_ids,
                "executor_actor_id": executor,
                "verification_profile": "AV/1",
            },
        )
        self._project_family(sl["family_id"])
        return updated

    def approve_override(
        self,
        *,
        approval_id: str,
        decided_by: str,
        approval_token: str | None = None,
        decision_ref: str | None = None,
    ) -> dict[str, Any]:
        try:
            require_approver(decided_by, approval_token)
        except CapabilityDenied as exc:
            raise ApprovalRequired(str(exc)) from exc
        approval = self._must_get("approvals", approval_id)
        if approval["status"] != "REQUIRED":
            raise InvalidTransition("approval already decided")
        return self._update(
            "approvals",
            approval_id,
            {
                "status": "APPROVED",
                "decided_by": decided_by,
                "decided_at": utcnow(),
                "decision_ref": decision_ref,
                "updated_at": utcnow(),
            },
            expected_revision=int(approval.get("revision", 0)),
        )

    def reject_override(
        self,
        *,
        approval_id: str,
        decided_by: str,
        approval_token: str | None = None,
        decision_ref: str | None = None,
    ) -> dict[str, Any]:
        try:
            require_approver(decided_by, approval_token)
        except CapabilityDenied as exc:
            raise ApprovalRequired(str(exc)) from exc
        approval = self._must_get("approvals", approval_id)
        if approval["status"] != "REQUIRED":
            raise InvalidTransition("approval already decided")
        return self._update(
            "approvals",
            approval_id,
            {
                "status": "REJECTED",
                "decided_by": decided_by,
                "decided_at": utcnow(),
                "decision_ref": decision_ref,
                "updated_at": utcnow(),
            },
            expected_revision=int(approval.get("revision", 0)),
        )

    def list_approvals(self, *, status: str | None = None, subject_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.store.find("approvals")
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if subject_id is not None:
            rows = [row for row in rows if row.get("subject_id") == subject_id]
        return sorted(rows, key=lambda row: row.get("created_at"), reverse=True)

    def accept_slice(self, *, slice_id: str, approval_id: str, accepted_by: str | None = None) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        if sl.get("assurance_state") != AssuranceState.VERIFIED.value:
            raise InvalidTransition("ACCEPTED requires VERIFIED assurance state")
        approval = self._must_get_approved(approval_id, action_type="ACCEPT_SLICE", subject_id=slice_id)
        authoritative_actor = approval.get("decided_by")
        if not authoritative_actor:
            raise ApprovalRequired("approved acceptance has no trusted decision actor")
        if accepted_by is not None and accepted_by != authoritative_actor:
            raise ApprovalRequired("accepted_by must match the trusted approval decision actor")
        now = utcnow()
        updated = self._update(
            "slices", slice_id,
            {
                "assurance_state": AssuranceState.ACCEPTED.value,
                "accepted_at": now,
                "last_activity_at": now,
                "updated_at": now,
                "accepted_by": authoritative_actor,
                "acceptance_approval_id": approval_id,
            },
            expected_revision=int(sl.get("revision", 0)),
        )
        self._project_family(sl["family_id"])
        return updated
