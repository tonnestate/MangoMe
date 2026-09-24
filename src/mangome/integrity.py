from __future__ import annotations

from typing import Any

from .authority import CapabilityDenied, require_approver, require_verifier
from .enums import AssuranceState, ClaimType, EvidenceClass, EvidenceTrust, EvidenceVerdict, ExecutionState
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
        for gate in gates:
            if gate.get("status") == "PASS":
                ids = list(gate.get("evidence_ids") or [])
                self._validate_evidence_ids(slice_id=slice_id, evidence_ids=ids)
                gate_evidence.extend(ids)
            elif gate.get("status") == "WAIVED":
                approval_id = gate.get("approval_id")
                if not approval_id:
                    raise InvalidTransition("WAIVED gate is missing approval reference")
                self._must_get_approved(approval_id, action_type="WAIVE_GATE", subject_id=f"{slice_id}:{gate['gate_id']}")
        explicit = evidence_ids or []
        if explicit:
            self._validate_evidence_ids(slice_id=slice_id, evidence_ids=explicit)
        proof_ids = list(dict.fromkeys(gate_evidence + explicit))
        if not gates and not proof_ids:
            raise InvalidTransition("verification of a gateless slice requires explicit attested evidence")
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
            {"verification": True, "evidence_ids": proof_ids, "executor_actor_id": executor},
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
