from __future__ import annotations

import pytest

from mangome.integrity import IntegrityMangoMeService
from mangome.service import ApprovalRequired, InvalidTransition, PlanRequired
from mangome.storage.memory import InMemoryStore


VERIFIER_TOKEN = "verify-secret"
APPROVAL_TOKEN = "owner-secret"


def configure_caps(monkeypatch):
    monkeypatch.setenv("MANGOME_VERIFIER_TOKEN", VERIFIER_TOKEN)
    monkeypatch.setenv("MANGOME_VERIFIER_ACTORS", "verifier-b")
    monkeypatch.setenv("MANGOME_APPROVAL_TOKEN", APPROVAL_TOKEN)
    monkeypatch.setenv("MANGOME_APPROVER_ACTORS", "human-owner")


def make_ready_slice():
    svc = IntegrityMangoMeService(InMemoryStore())
    family = svc.create_family("F", "Family")
    contract = svc.register_contract(declared_id="C-1", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(request_text="implement", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Implement", contract_ids=[contract["entity_id"]])
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"],
        actor_id="worker-a", intent="execute", contract_ids=[contract["entity_id"]],
        proposed_slices=[{"declared_id": "S1", "title": "Slice 1", "acceptance": ["runtime check passes"]}],
        expected_scope=["src/"], acceptance_expectations=["runtime check passes"],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    return svc, family, sl, plan


def trusted_pass_evidence(svc, sl):
    return svc.submit_verification_observation(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
        claim="runtime check passes", observation_type="SPEC_CHECK", status="PASS",
        evidence_type="verification-check", evidence_class="TEST_RESULT", source="verifier",
    )


def test_pass_requires_attested_slice_evidence(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="pytest", evidence_class="TEST_RESULT",
        source="pytest", result="PASS", actor_id="verifier-b",
    )
    with pytest.raises(InvalidTransition):
        svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]])
    attested = svc.attest_evidence(evidence_id=ev["entity_id"], attested_by="verifier-b", capability_token=VERIFIER_TOKEN)
    updated = svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[attested["entity_id"]]
    )
    assert updated["gates"][0]["status"] == "PASS"
    assert updated["gates"][0]["decided_by"] == "verifier-b"


def test_verifier_capability_and_self_verification_are_enforced(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = trusted_pass_evidence(svc, sl)
    svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]])
    with pytest.raises(ApprovalRequired):
        svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token="wrong")
    with pytest.raises(ApprovalRequired):
        svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="worker-a", verifier_token=VERIFIER_TOKEN)
    verified = svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN)
    assert verified["assurance_state"] == "VERIFIED"


def test_waive_gate_requires_trusted_approved_override(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    with pytest.raises(ApprovalRequired):
        svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="WAIVED", actor_id="worker-a")
    approval = svc.request_override(
        action_type="WAIVE_GATE", subject_id=f"{sl['entity_id']}:{gate_id}",
        requested_by="worker-a", reason="obsolete gate",
    )
    with pytest.raises(ApprovalRequired):
        svc.approve_override(approval_id=approval["entity_id"], decided_by="human-owner", approval_token="wrong")
    approval = svc.approve_override(
        approval_id=approval["entity_id"], decided_by="human-owner",
        approval_token=APPROVAL_TOKEN, decision_ref="chat:decision-1",
    )
    updated = svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="WAIVED", actor_id="worker-a",
        approval_id=approval["entity_id"],
    )
    assert updated["gates"][0]["approval_id"] == approval["entity_id"]


def test_acceptance_uses_trusted_approval_actor(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = trusted_pass_evidence(svc, sl)
    svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]])
    svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN)
    approval = svc.request_override(action_type="ACCEPT_SLICE", subject_id=sl["entity_id"], requested_by="verifier-b", reason="owner acceptance")
    approval = svc.approve_override(approval_id=approval["entity_id"], decided_by="human-owner", approval_token=APPROVAL_TOKEN)
    with pytest.raises(ApprovalRequired):
        svc.accept_slice(slice_id=sl["entity_id"], approval_id=approval["entity_id"], accepted_by="worker-a")
    accepted = svc.accept_slice(slice_id=sl["entity_id"], approval_id=approval["entity_id"])
    assert accepted["assurance_state"] == "ACCEPTED"
    assert accepted["accepted_by"] == "human-owner"


def test_closed_plan_drops_out_of_collision_set(monkeypatch):
    configure_caps(monkeypatch)
    svc, family, _, plan = make_ready_slice()
    closed = svc.close_plan(plan["entity_id"], "worker-a")
    assert closed["status"] == "CLOSED"
    assert all(p["entity_id"] != plan["entity_id"] for p in svc.get_context(family["entity_id"])["active_plans"])


def test_mutation_after_start_requires_bound_plan(monkeypatch):
    configure_caps(monkeypatch)
    svc = IntegrityMangoMeService(InMemoryStore())
    family = svc.create_family("F2", "Family 2")
    contract = svc.register_contract(declared_id="C-2", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(request_text="implement", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Implement", contract_ids=[contract["entity_id"]])
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"], actor_id="worker-a", intent="work",
        proposed_slices=[{"declared_id": "S2", "title": "Slice 2"}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    with pytest.raises(PlanRequired):
        svc.update_slice_progress(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"], current_step=1)
    svc.start_slice(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    svc.update_slice_progress(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"], current_step=1)
    with pytest.raises(PlanRequired):
        svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a", plan_id="not-a-plan")


def test_dedicated_runtime_role_can_verify_without_token(monkeypatch):
    monkeypatch.delenv("MANGOME_VERIFIER_TOKEN", raising=False)
    monkeypatch.setenv("MANGOME_RUNTIME_ROLE", "VERIFIER")
    monkeypatch.setenv("MANGOME_RUNTIME_ACTOR", "verifier-b")
    svc, _, sl, _ = make_ready_slice()
    ev = svc.submit_verification_observation(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=None,
        claim="runtime check passes", observation_type="SPEC_CHECK", status="PASS",
        evidence_type="verification-check", evidence_class="TEST_RESULT", source="runtime-verifier",
    )
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    svc.set_gate(slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]])
    verified = svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=None)
    assert verified["assurance_state"] == "VERIFIED"


def test_worker_runtime_cannot_spoof_owner_without_capability(monkeypatch):
    monkeypatch.delenv("MANGOME_APPROVAL_TOKEN", raising=False)
    monkeypatch.setenv("MANGOME_RUNTIME_ROLE", "WORKER")
    monkeypatch.delenv("MANGOME_RUNTIME_ACTOR", raising=False)
    svc, _, sl, _ = make_ready_slice()
    approval = svc.request_override(
        action_type="ACCEPT_SLICE", subject_id=sl["entity_id"], requested_by="worker-a", reason="try"
    )
    with pytest.raises(ApprovalRequired):
        svc.approve_override(approval_id=approval["entity_id"], decided_by="human-owner", approval_token=None)


def test_attested_pass_without_independent_observation_cannot_verify(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="pytest", evidence_class="TEST_RESULT",
        source="worker-report", result="PASS", actor_id="worker-a",
    )
    ev = svc.attest_evidence(
        evidence_id=ev["entity_id"], attested_by="verifier-b",
        capability_token=VERIFIER_TOKEN, authority="VERIFIER",
    )
    svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="PASS",
        actor_id="verifier-b", evidence_ids=[ev["entity_id"]],
    )
    with pytest.raises(InvalidTransition, match="independent AV/1 observed PASS"):
        svc.verify_slice(
            slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN
        )


def test_executor_cannot_submit_independent_verification_observation(monkeypatch):
    configure_caps(monkeypatch)
    monkeypatch.setenv("MANGOME_VERIFIER_ACTORS", "worker-a,verifier-b")
    svc, _, sl, _ = make_ready_slice()
    with pytest.raises(InvalidTransition, match="last executing actor"):
        svc.submit_verification_observation(
            slice_id=sl["entity_id"], verifier_actor_id="worker-a", verifier_token=VERIFIER_TOKEN,
            claim="I am done", observation_type="SPEC_CHECK", status="PASS",
            evidence_type="self-check", evidence_class="TEST_RESULT", source="worker",
        )


def test_completion_review_surfaces_scope_and_test_change_risks(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    review = svc.completion_review(
        slice_id=sl["entity_id"],
        changed_paths=["src/runtime.py", "tests/test_runtime.py", "docs/drive-by.md"],
    )
    assert review["execution_state"] == "DONE_CLAIMED"
    assert review["expected_scope"] == ["src/"]
    assert "NO_INDEPENDENT_OBSERVATION" in review["risk_flags"]
    assert "SCOPE_DEVIATION" in review["risk_flags"]
    assert "TEST_CHANGE_REVIEW_REQUIRED" in review["risk_flags"]
    assert review["scope_review"]["test_change_paths"] == ["tests/test_runtime.py"]
    assert set(review["scope_review"]["out_of_scope_paths"]) == {"tests/test_runtime.py", "docs/drive-by.md"}


def test_replay_observation_requires_intact_rb1_binding(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    with pytest.raises(InvalidTransition, match="REPLAY observations require"):
        svc.submit_verification_observation(
            slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
            claim="pytest passes", observation_type="REPLAY", status="PASS",
            evidence_type="pytest", evidence_class="TEST_RESULT", source="pytest",
        )
    with pytest.raises(InvalidTransition, match="fingerprint mismatch"):
        svc.submit_verification_observation(
            slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
            claim="pytest passes", observation_type="REPLAY", status="PASS",
            evidence_type="pytest", evidence_class="TEST_RESULT", source="pytest",
            reproduction={
                "version": "RB/1", "command": "pytest -q", "cwd": ".", "exit_code": 0,
                "git_commit": None, "input_bindings": [], "output_artifact_id": None,
                "stdout_sha256": None, "stderr_sha256": None, "environment_names": [],
                "fingerprint": "not-valid",
            },
        )


def test_forged_generic_replay_payload_without_rb1_cannot_satisfy_av1(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    ev = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="pytest", evidence_class="TEST_RESULT",
        source="generic-path", result="PASS", actor_id="verifier-b",
        payload={"verification_observation": {
            "version": "AV/1", "claim": "pytest passes", "observation_type": "REPLAY",
            "status": "PASS", "observed_by": "verifier-b", "original_evidence_id": None,
        }},
    )
    ev = svc.attest_evidence(
        evidence_id=ev["entity_id"], attested_by="verifier-b",
        capability_token=VERIFIER_TOKEN, authority="VERIFIER",
    )
    svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="PASS",
        actor_id="verifier-b", evidence_ids=[ev["entity_id"]],
    )
    with pytest.raises(InvalidTransition, match="independent AV/1 observed PASS"):
        svc.verify_slice(
            slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN
        )


def test_approved_waiver_remains_explicit_gate_exception(monkeypatch):
    configure_caps(monkeypatch)
    svc, _, sl, _ = make_ready_slice()
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    approval = svc.request_override(
        action_type="WAIVE_GATE", subject_id=f"{sl['entity_id']}:{gate_id}",
        requested_by="worker-a", reason="owner explicitly waives this gate",
    )
    approval = svc.approve_override(
        approval_id=approval["entity_id"], decided_by="human-owner", approval_token=APPROVAL_TOKEN,
    )
    svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="WAIVED",
        actor_id="human-owner", approval_id=approval["entity_id"],
    )
    verified = svc.verify_slice(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN
    )
    assert verified["assurance_state"] == "VERIFIED"
