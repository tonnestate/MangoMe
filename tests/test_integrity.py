from __future__ import annotations

import pytest

from mangome.integrity import IntegrityMangoMeService
from mangome.service import ApprovalRequired, InvalidTransition
from mangome.storage.memory import InMemoryStore


def make_ready_slice():
    svc = IntegrityMangoMeService(InMemoryStore())
    family = svc.create_family("F", "Family")
    contract = svc.register_contract(declared_id="C-1", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(
        request_text="implement",
        classification="EXISTING_CONTRACT_WORK",
        family_id=family["entity_id"],
    )
    spec = svc.create_spec(
        family_id=family["entity_id"],
        objective="Implement",
        contract_ids=[contract["entity_id"]],
    )
    plan = svc.submit_plan(
        family_id=family["entity_id"],
        request_id=req["entity_id"],
        spec_id=spec["entity_id"],
        actor_id="worker-a",
        intent="execute",
        contract_ids=[contract["entity_id"]],
        proposed_slices=[
            {
                "declared_id": "S1",
                "title": "Slice 1",
                "acceptance": ["runtime check passes"],
            }
        ],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a")
    return svc, family, sl, plan


def test_pass_requires_persisted_slice_evidence():
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]

    with pytest.raises(InvalidTransition):
        svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b")

    ev = svc.submit_evidence(
        subject_id=sl["entity_id"],
        evidence_type="TEST",
        source="pytest",
        result="PASS",
        actor_id="verifier-b",
    )
    updated = svc.set_gate(
        slice_id=sl["entity_id"],
        gate_id=gate_id,
        status="PASS",
        actor_id="verifier-b",
        evidence_ids=[ev["entity_id"]],
    )
    assert updated["gates"][0]["status"] == "PASS"
    assert updated["gates"][0]["evidence_ids"] == [ev["entity_id"]]


def test_self_verification_is_denied_but_independent_verification_passes():
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="TEST", source="runtime", result="PASS", actor_id="verifier-b"
    )
    svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]]
    )

    with pytest.raises(InvalidTransition):
        svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="worker-a")

    verified = svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b")
    assert verified["assurance_state"] == "VERIFIED"


def test_waive_gate_requires_approved_override():
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]

    with pytest.raises(ApprovalRequired):
        svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="WAIVED", actor_id="worker-a")

    approval = svc.request_override(
        action_type="WAIVE_GATE",
        subject_id=f"{sl['entity_id']}:{gate_id}",
        requested_by="worker-a",
        reason="gate obsolete after approved design change",
    )
    approval = svc.approve_override(
        approval_id=approval["entity_id"],
        decided_by="human-owner",
        decision_ref="chat:decision-1",
    )
    assert approval["status"] == "APPROVED"

    updated = svc.set_gate(
        slice_id=sl["entity_id"],
        gate_id=gate_id,
        status="WAIVED",
        actor_id="worker-a",
        approval_id=approval["entity_id"],
    )
    assert updated["gates"][0]["status"] == "WAIVED"
    assert updated["gates"][0]["approval_id"] == approval["entity_id"]


def test_acceptance_requires_verified_slice_and_approved_acceptance():
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="TEST", source="runtime", result="PASS", actor_id="verifier-b"
    )
    svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]]
    )
    svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b")

    approval = svc.request_override(
        action_type="ACCEPT_SLICE",
        subject_id=sl["entity_id"],
        requested_by="verifier-b",
        reason="request owner acceptance",
    )
    with pytest.raises(ApprovalRequired):
        svc.accept_slice(slice_id=sl["entity_id"], approval_id=approval["entity_id"], accepted_by="human-owner")

    svc.approve_override(approval_id=approval["entity_id"], decided_by="human-owner")
    accepted = svc.accept_slice(
        slice_id=sl["entity_id"], approval_id=approval["entity_id"], accepted_by="human-owner"
    )
    assert accepted["assurance_state"] == "ACCEPTED"


def test_closed_plan_drops_out_of_collision_set():
    svc, family, _, plan = make_ready_slice()
    closed = svc.close_plan(plan["entity_id"], "worker-a")
    assert closed["status"] == "CLOSED"
    assert all(p["entity_id"] != plan["entity_id"] for p in svc.get_context(family["entity_id"])["active_plans"])
