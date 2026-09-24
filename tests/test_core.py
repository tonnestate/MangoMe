from __future__ import annotations

import pytest

from mangome.service import ApprovalRequired, MangoMeService, PlanRequired
from mangome.storage.memory import InMemoryStore


def make_service() -> MangoMeService:
    return MangoMeService(InMemoryStore())


def setup_family(svc: MangoMeService):
    project = svc.create_project("AVCOS", "AVCOS")
    family = svc.create_family("AVCOS-OSEP", "OSEP", [project["entity_id"]], ["AVCOS"])
    contract = svc.register_contract(
        declared_id="AVCOS-OSEP-001",
        family_id=family["entity_id"],
        title="OSEP Contract",
        actor_id="human-owner",
        storage_system="filesystem",
        physical_location="/root/contracts/AVCOS-OSEP-001.md",
    )
    return project, family, contract


def make_request_and_spec(svc, family, contract, actor="tester"):
    req = svc.intake_request(request_text="Implement existing contract work", classification="EXISTING_CONTRACT_WORK", classification_source="test", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Execute the contract", contract_ids=[contract["entity_id"]], acceptance_criteria=["work satisfies gates"])
    return req, spec


def test_done_claim_is_not_verification_and_gates_are_hard():
    svc = make_service()
    _, family, contract = setup_family(svc)
    req, spec = make_request_and_spec(svc, family, contract, "luna")
    plan = svc.submit_plan(
        family_id=family["entity_id"],
        request_id=req["entity_id"],
        spec_id=spec["entity_id"],
        actor_id="luna",
        intent="implement phase 3B",
        contract_ids=[contract["entity_id"]],
        proposed_slices=[{
            "declared_id": "OSEP-3B",
            "title": "Phase 3B",
            "acceptance": ["integration test passes", "runtime state observed"],
        }],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="luna", plan_id=plan["entity_id"])
    svc.claim_done(slice_id=sl["entity_id"], actor_id="luna", plan_id=plan["entity_id"], summary="done")

    status = svc.status(family["entity_id"])
    assert status["execution_state"] == "DONE_CLAIMED"
    assert status["assurance_state"] == "UNVERIFIED"

    with pytest.raises(ApprovalRequired):
        svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="codex")

    assert svc.status(family["entity_id"])["assurance_state"] == "UNVERIFIED"


def test_plan_before_mutate_is_enforced():
    svc = make_service()
    _, family, contract = setup_family(svc)
    req, spec = make_request_and_spec(svc, family, contract, "codex")
    plan = svc.submit_plan(
        family_id=family["entity_id"],
        request_id=req["entity_id"],
        spec_id=spec["entity_id"],
        actor_id="codex",
        intent="work",
        contract_ids=[contract["entity_id"]],
        proposed_slices=[{"declared_id": "S1", "title": "Slice 1"}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    with pytest.raises(PlanRequired):
        svc.start_slice(slice_id=sl["entity_id"], actor_id="claude", plan_id=plan["entity_id"])


def test_collision_is_warning_not_lock():
    svc = make_service()
    _, family, contract = setup_family(svc)
    req1, spec = make_request_and_spec(svc, family, contract, "codex")
    p1 = svc.submit_plan(
        family_id=family["entity_id"],
        request_id=req1["entity_id"],
        spec_id=spec["entity_id"],
        actor_id="codex",
        intent="backend",
        contract_ids=[contract["entity_id"]],
        expected_artifacts=["src/worker.py"],
        expected_scope=["runtime"],
        proposed_slices=[{"declared_id": "S1", "title": "Slice 1"}],
    )
    req2 = svc.intake_request(request_text="parallel runtime work", classification="EXISTING_CONTRACT_WORK", classification_source="test", family_id=family["entity_id"])
    p2 = svc.submit_plan(
        family_id=family["entity_id"],
        request_id=req2["entity_id"],
        spec_id=spec["entity_id"],
        actor_id="claude",
        intent="runtime",
        contract_ids=[contract["entity_id"]],
        expected_artifacts=["src/worker.py", "src/runtime.py"],
        expected_scope=["runtime"],
        proposed_slices=[{"declared_id": "S2", "title": "Slice 2"}],
    )
    warning = svc.collision_warnings(p2["entity_id"])
    assert warning.action == "CONTINUE_ALLOWED"
    assert warning.family_overlap is True
    assert warning.artifact_overlap == ["src/worker.py"]
    assert warning.scope_overlap == ["runtime"]
    assert "codex" in warning.other_actor_ids


def test_last_started_slice_is_derived_from_persistent_timestamps():
    svc = make_service()
    _, family, contract = setup_family(svc)
    req, spec = make_request_and_spec(svc, family, contract, "codex")
    plan = svc.submit_plan(
        family_id=family["entity_id"],
        request_id=req["entity_id"],
        spec_id=spec["entity_id"],
        actor_id="codex",
        intent="two slices",
        contract_ids=[contract["entity_id"]],
        proposed_slices=[
            {"declared_id": "S1", "title": "Slice 1", "sequence": 1},
            {"declared_id": "S2", "title": "Slice 2", "sequence": 2},
        ],
    )
    slices = {s["declared_id"]: s for s in svc.store.find("slices", {"family_id": family["entity_id"]})}
    svc.start_slice(slice_id=slices["S1"]["entity_id"], actor_id="codex", plan_id=plan["entity_id"])
    svc.claim_done(slice_id=slices["S1"]["entity_id"], actor_id="codex", plan_id=plan["entity_id"])
    svc.start_slice(slice_id=slices["S2"]["entity_id"], actor_id="codex", plan_id=plan["entity_id"])
    status = svc.status(family["entity_id"])
    assert status["last_started_slice_id"] == slices["S2"]["entity_id"]
    assert status["last_done_claimed_slice_id"] == slices["S1"]["entity_id"]
    assert slices["S2"]["entity_id"] in status["active_slice_ids"]


def test_declared_contract_id_collision_preserves_both_contributions():
    svc = make_service()
    _, family, _ = setup_family(svc)
    second = svc.register_contract(
        declared_id="AVCOS-OSEP-001",
        family_id=family["entity_id"],
        title="Different contribution with same declared id",
        actor_id="claude",
    )
    matches = svc.store.find("contracts", {"declared_id": "AVCOS-OSEP-001"})
    assert len(matches) == 2
    assert len({m["entity_id"] for m in matches}) == 2
    assert second["entity_id"] in {m["entity_id"] for m in matches}
    status = svc.status(family["entity_id"])
    assert "DECLARED_ID_COLLISION" in status["warnings"]
