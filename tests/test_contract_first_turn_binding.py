from __future__ import annotations

import pytest

from mangome.contract_control import (
    ContractGenerationConflict,
    ContractGovernedMangoMeService,
)
from mangome.service import workspace_project_key
from mangome.storage.memory import InMemoryStore


def _contract_service():
    svc = ContractGovernedMangoMeService(InMemoryStore())
    project = svc.create_project("P-CF", "Contract-first")
    family = svc.create_family("F-CF", "Contract-first family", project_ids=[project["entity_id"]])
    contract = svc.register_contract(
        declared_id="C-CF",
        family_id=family["entity_id"],
        title="Canonical contract",
        actor_id="author-a",
        storage_system="filesystem",
        physical_location="/work/contracts/C-CF.md",
        checksum="working-copy-hash",
    )
    svc.create_spec(
        family_id=family["entity_id"],
        objective="Implement the canonical contract",
        contract_ids=[contract["entity_id"]],
        acceptance_criteria=["contract requirement is satisfied"],
    )
    return svc, project, family, contract


def test_query_turn_is_read_only_and_does_not_acquire_generation_grant():
    svc, _, _, contract = _contract_service()

    bound = svc.bind_turn(
        request_text="Is this contract stored in MangoMe?",
        mode="QUERY",
        actor_id="reader-a",
        contract_ref=contract["entity_id"],
    )

    assert bound["turn"]["mode"] == "QUERY"
    assert bound["allowed"]["read_contract_truth"] is True
    assert bound["allowed"]["continue_or_execute_slices"] is False
    assert bound["allowed"]["promote_contract_generation"] is False
    assert bound["generation_grant"] is None
    assert svc.store.find("contract_generation_grants") == []


def test_modify_turn_has_single_writer_generation_grant():
    svc, _, _, contract = _contract_service()

    first = svc.bind_turn(
        request_text="Extend the contract with requirement B",
        mode="MODIFY",
        actor_id="writer-a",
        contract_ref=contract["entity_id"],
    )
    assert first["generation_grant"]["status"] == "ACTIVE"

    with pytest.raises(ContractGenerationConflict, match="WRITE_ALREADY_GRANTED"):
        svc.bind_turn(
            request_text="Change the same contract concurrently",
            mode="MODIFY",
            actor_id="writer-b",
            contract_ref=contract["entity_id"],
        )
    denied = [row for row in svc.store.find("turn_bindings") if row.get("actor_id") == "writer-b"]
    assert denied and denied[0]["status"] == "DENIED"


def test_contract_generations_are_immutable_and_promotion_is_turn_bound():
    svc, _, _, contract = _contract_service()

    first = svc.bind_turn(
        request_text="Create the canonical contract body",
        mode="MODIFY",
        actor_id="writer-a",
        contract_ref=contract["entity_id"],
    )
    first_result = svc.promote_contract_generation(
        contract_ref=contract["entity_id"],
        turn_id=first["turn"]["entity_id"],
        grant_id=first["generation_grant"]["entity_id"],
        actor_id="writer-a",
        content="# Contract\nRequirement A\n",
        change_type="INITIAL",
        source_binding={"storage_system": "filesystem", "physical_location": "/work/contracts/C-CF.md"},
    )
    assert first_result["promoted"] is True
    assert first_result["generation"]["generation"] == 1
    generation_one_id = first_result["generation"]["entity_id"]

    # A changed physical working copy alone does not change canonical truth.
    unchanged_state = svc.contract_state(contract["entity_id"], include_content=True)
    assert unchanged_state["current_generation"] == 1
    assert unchanged_state["current"]["content"] == "# Contract\nRequirement A\n"

    second = svc.bind_turn(
        request_text="Extend the contract with requirement B",
        mode="MODIFY",
        actor_id="writer-b",
        contract_ref=contract["entity_id"],
    )
    second_result = svc.promote_contract_generation(
        contract_ref=contract["entity_id"],
        turn_id=second["turn"]["entity_id"],
        grant_id=second["generation_grant"]["entity_id"],
        actor_id="writer-b",
        content="# Contract\nRequirement A\nRequirement B\n",
        change_type="EXTENSION",
        source_binding={"storage_system": "filesystem", "physical_location": "/work/contracts/C-CF.md"},
    )
    assert second_result["generation"]["generation"] == 2

    final_state = svc.contract_state(contract["entity_id"], include_content=True)
    assert final_state["canonical_content_present"] is True
    assert any(binding.get("physical_location") == "/work/contracts/C-CF.md" for binding in final_state["storage_bindings"])
    assert final_state["current_generation"] == 2
    assert final_state["current"]["content"].endswith("Requirement B\n")
    generation_one = svc.store.get("contract_generations", generation_one_id)
    assert generation_one["content"] == "# Contract\nRequirement A\n"
    assert generation_one["status"] == "CANONICAL"


def test_grant_is_bound_to_actor_turn_contract_and_base_generation():
    svc, _, _, contract = _contract_service()
    bound = svc.bind_turn(
        request_text="Create canonical generation",
        mode="MODIFY",
        actor_id="writer-a",
        contract_ref=contract["entity_id"],
    )

    with pytest.raises(ContractGenerationConflict, match="turn/actor"):
        svc.promote_contract_generation(
            contract_ref=contract["entity_id"],
            turn_id=bound["turn"]["entity_id"],
            grant_id=bound["generation_grant"]["entity_id"],
            actor_id="writer-b",
            content="forged",
        )


def test_recovery_is_contract_first_and_does_not_authorize_active_slice():
    svc = ContractGovernedMangoMeService(InMemoryStore())
    work = svc.enter_work(
        workspace_id="/workspace/demo",
        workspace_title="Demo",
        actor_id="worker-a",
        request_text="Implement R1",
        acceptance_criteria=["R1 is implemented"],
    )
    family = work["family"]
    contract = svc.register_contract(
        declared_id="C-RECOVER",
        family_id=family["entity_id"],
        title="Recovery contract",
        actor_id="worker-a",
        storage_system="filesystem",
        physical_location="/workspace/demo/contract.md",
    )
    current_spec = svc._must_get("specs", family["current_spec_id"])
    svc._update(
        "specs",
        current_spec["entity_id"],
        {"contract_ids": [contract["entity_id"]]},
        expected_revision=int(current_spec.get("revision", 0)),
    )

    restored = svc.session_restore(workspace_project_key("/workspace/demo"))

    assert restored["restore_state"] == "STATE_FOUND"
    assert restored["productive_execution_allowed"] is False
    assert restored["current_turn_execution_authorized"] is False
    assert restored["turn_binding_required"] is True
    assert restored["recovered_executable_items"]
    assert restored["turn_policy"]["active_slice_grants_current_turn_execution"] is False
    assert restored["recovery_priority"][0] == "CURRENT_USER_TURN"
    assert restored["families"][0]["contract_truth"][0]["contract"]["entity_id"] == contract["entity_id"]
    assert "DERIVED_SUPPORTING_STATE" in restored["families"][0]["execution_state_role"]


def test_stale_generation_grant_fails_closed_if_head_advances():
    svc, _, _, contract = _contract_service()
    bound = svc.bind_turn(
        request_text="Modify canonical contract",
        mode="MODIFY",
        actor_id="writer-a",
        contract_ref=contract["entity_id"],
    )
    head = svc.store.find("contract_heads", {"contract_id": contract["entity_id"]})[0]
    svc._update(
        "contract_heads",
        head["entity_id"],
        {"current_generation": 7, "current_content_hash": "advanced-elsewhere"},
        expected_revision=int(head.get("revision", 0)),
    )

    with pytest.raises(ContractGenerationConflict, match="canonical generation advanced"):
        svc.promote_contract_generation(
            contract_ref=contract["entity_id"],
            turn_id=bound["turn"]["entity_id"],
            grant_id=bound["generation_grant"]["entity_id"],
            actor_id="writer-a",
            content="stale write",
        )
