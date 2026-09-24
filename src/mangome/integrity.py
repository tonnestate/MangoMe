from __future__ import annotations

from typing import Any

from .enums import AssuranceState, ClaimType, ExecutionState
from .models import utcnow
from .service import ApprovalRequired, InvalidTransition, MangoMeService


_FAIL_RESULTS = {"FAIL", "FAILED", "ERROR", "REJECTED", "FALSE"}


class IntegrityMangoMeService(MangoMeService):
    """MangoMe service with v0.1.1 integrity invariants.

    This layer intentionally does not implement authentication. Actor IDs are
    still declarative identities supplied by the MCP host. What it *does*
    enforce is the work-state protocol: evidence-backed PASS, approval-backed
    WAIVE/ACCEPT, and separation between the last executing actor and the
    verifier.
    """

    def _must_get_approved(self, approval_id: str, *, action_type: str, subject_id: str) -> dict[str, Any]:
        approval = self._must_get("approvals", approval_id)
        if approval.get("status") != "APPROVED":
            raise ApprovalRequired("approval is not APPROVED")
        if approval.get("action_type") != action_type:
            raise ApprovalRequired(
                f"approval action mismatch: expected {action_type}, got {approval.get('action_type')}"
            )
        if approval.get("subject_id") != subject_id:
            raise ApprovalRequired("approval subject does not match requested action")
        return approval

    def _validate_evidence_ids(self, *, slice_id: str, evidence_ids: list[str]) -> list[dict[str, Any]]:
        if not evidence_ids:
            raise InvalidTransition("PASS requires at least one persisted evidence id")
        resolved: list[dict[str, Any]] = []
        for evidence_id in evidence_ids:
            evidence = self._must_get("evidence", evidence_id)
            if evidence.get("subject_id") != slice_id:
                raise InvalidTransition(f"evidence {evidence_id} does not belong to slice {slice_id}")
            result = str(evidence.get("result") or "").upper()
            if result in _FAIL_RESULTS:
                raise InvalidTransition(f"evidence {evidence_id} reports a failing result")
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
        normalized = status.upper()
        evidence_ids = evidence_ids or []

        if normalized == "PASS":
            self._validate_evidence_ids(slice_id=slice_id, evidence_ids=evidence_ids)
        elif normalized == "WAIVED":
            if not approval_id:
                raise ApprovalRequired("WAIVED requires an approved WAIVE_GATE request")
            self._must_get_approved(
                approval_id,
                action_type="WAIVE_GATE",
                subject_id=f"{slice_id}:{gate_id}",
            )
        elif normalized not in {"OPEN", "FAIL"}:
            raise InvalidTransition(f"unsupported gate status {status}")

        updated = super().set_gate(
            slice_id=slice_id,
            gate_id=gate_id,
            status=normalized,
            evidence_ids=evidence_ids,
        )
        # Keep audit metadata next to the gate without changing the v0.1 Gate model.
        gates = [dict(g) for g in updated.get("gates", [])]
        for gate in gates:
            if gate.get("gate_id") == gate_id:
                gate["decided_by"] = actor_id
                gate["decided_at"] = utcnow()
                if approval_id:
                    gate["approval_id"] = approval_id
                break
        updated = self.store.update("slices", slice_id, {"gates": gates, "updated_at": utcnow()})
        self._project_family(updated["family_id"])
        return updated

    def verify_slice(
        self,
        *,
        slice_id: str,
        verifier_actor_id: str,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        if sl["execution_state"] != ExecutionState.DONE_CLAIMED.value:
            raise InvalidTransition("verification requires DONE_CLAIMED execution state")

        executor = sl.get("last_actor_id")
        if executor and executor == verifier_actor_id:
            raise InvalidTransition("the last executing actor may not verify its own DONE claim")

        gates = sl.get("gates", [])
        open_or_failed = [g for g in gates if g.get("status") not in {"PASS", "WAIVED"}]
        if open_or_failed:
            raise InvalidTransition(
                f"verification denied: {len(open_or_failed)} acceptance gates are not PASS/WAIVED"
            )

        gate_evidence: list[str] = []
        for gate in gates:
            if gate.get("status") == "PASS":
                ids = list(gate.get("evidence_ids") or [])
                self._validate_evidence_ids(slice_id=slice_id, evidence_ids=ids)
                gate_evidence.extend(ids)
            elif gate.get("status") == "WAIVED" and not gate.get("approval_id"):
                raise InvalidTransition("WAIVED gate is missing its approval reference")

        explicit = evidence_ids or []
        if explicit:
            self._validate_evidence_ids(slice_id=slice_id, evidence_ids=explicit)

        proof_ids = list(dict.fromkeys(gate_evidence + explicit))
        if not gates and not proof_ids:
            raise InvalidTransition("verification of a gateless slice requires explicit persisted evidence")

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
        decision_ref: str | None = None,
    ) -> dict[str, Any]:
        approval = self._must_get("approvals", approval_id)
        if approval["status"] != "REQUIRED":
            raise InvalidTransition("approval already decided")
        patch: dict[str, Any] = {
            "status": "APPROVED",
            "decided_by": decided_by,
            "decided_at": utcnow(),
            "updated_at": utcnow(),
        }
        if decision_ref:
            patch["decision_ref"] = decision_ref
        return self.store.update("approvals", approval_id, patch)

    def reject_override(
        self,
        *,
        approval_id: str,
        decided_by: str,
        decision_ref: str | None = None,
    ) -> dict[str, Any]:
        approval = self._must_get("approvals", approval_id)
        if approval["status"] != "REQUIRED":
            raise InvalidTransition("approval already decided")
        patch: dict[str, Any] = {
            "status": "REJECTED",
            "decided_by": decided_by,
            "decided_at": utcnow(),
            "updated_at": utcnow(),
        }
        if decision_ref:
            patch["decision_ref"] = decision_ref
        return self.store.update("approvals", approval_id, patch)

    def list_approvals(
        self,
        *,
        status: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.store.find("approvals")
        if status is not None:
            rows = [row for row in rows if row.get("status") == status]
        if subject_id is not None:
            rows = [row for row in rows if row.get("subject_id") == subject_id]
        return sorted(rows, key=lambda row: row.get("created_at"), reverse=True)

    def accept_slice(
        self,
        *,
        slice_id: str,
        approval_id: str,
        accepted_by: str,
    ) -> dict[str, Any]:
        sl = self._must_get("slices", slice_id)
        if sl.get("assurance_state") != AssuranceState.VERIFIED.value:
            raise InvalidTransition("ACCEPTED requires VERIFIED assurance state")
        self._must_get_approved(
            approval_id,
            action_type="ACCEPT_SLICE",
            subject_id=slice_id,
        )
        now = utcnow()
        updated = self.store.update(
            "slices",
            slice_id,
            {
                "assurance_state": AssuranceState.ACCEPTED.value,
                "accepted_at": now,
                "last_activity_at": now,
                "updated_at": now,
                "accepted_by": accepted_by,
                "acceptance_approval_id": approval_id,
            },
        )
        self._project_family(sl["family_id"])
        return updated
