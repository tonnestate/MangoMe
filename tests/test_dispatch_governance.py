from mangome.integrity import IntegrityMangoMeService
from mangome.storage.memory import InMemoryStore


def _family(service: IntegrityMangoMeService) -> str:
    result = service.enter_work(
        workspace_id="/tmp/mangome-dispatch-governance",
        workspace_title="Dispatch Governance",
        actor_id="coordinator",
        request_text="Recover one bounded delta",
        acceptance_criteria=["delta recovered"],
        expected_artifacts=[],
    )
    return result["family"]["entity_id"]


def test_runtime_mode_downgrade_removes_deploy_eligibility():
    svc = IntegrityMangoMeService(InMemoryStore())
    family_id = _family(svc)

    svc.register_worker_runtime(
        worker_key="luna",
        runtime_mode="NORMAL",
        capabilities=["READ", "REASON", "MUTATE", "TEST", "DEPLOY"],
        cost_class="CHEAP",
    )
    assert svc.check_execution_eligibility(
        worker_key="luna", required_capabilities=["DEPLOY"], cost_ceiling="CHEAP", family_id=family_id
    )["eligible"] is True

    svc.register_worker_runtime(
        worker_key="luna",
        runtime_mode="RESERVE",
        capabilities=["READ", "REASON", "TEST"],
        cost_class="CHEAP",
    )
    decision = svc.check_execution_eligibility(
        worker_key="luna", required_capabilities=["DEPLOY"], cost_ceiling="CHEAP", family_id=family_id
    )

    assert decision["eligible"] is False
    assert decision["runtime_mode"] == "RESERVE"
    assert decision["missing_capabilities"] == ["DEPLOY"]
    assert "CURRENT_RUNTIME_CAPABILITY_MISSING" in decision["reason_codes"]
    assert decision["handoff_policy"] == "CHECKPOINT_AND_HANDOFF_MISSING_CAPABILITY_ONLY"


def test_expensive_worker_cannot_be_silently_escalated_without_owner_approval(monkeypatch):
    svc = IntegrityMangoMeService(InMemoryStore())
    family_id = _family(svc)
    svc.register_worker_runtime(
        worker_key="high-cost-judge",
        runtime_mode="NORMAL",
        capabilities=["READ", "REASON", "MUTATE", "TEST"],
        cost_class="EXPENSIVE",
    )

    cheap_ceiling = svc.check_execution_eligibility(
        worker_key="high-cost-judge",
        required_capabilities=["REASON"],
        cost_ceiling="CHEAP",
        family_id=family_id,
    )
    assert cheap_ceiling["eligible"] is False
    assert "COST_CEILING_EXCEEDED" in cheap_ceiling["reason_codes"]
    assert "OWNER_APPROVAL_REQUIRED" in cheap_ceiling["reason_codes"]

    no_approval = svc.check_execution_eligibility(
        worker_key="high-cost-judge",
        required_capabilities=["REASON"],
        cost_ceiling="EXPENSIVE",
        family_id=family_id,
    )
    assert no_approval["eligible"] is False
    assert no_approval["reason_codes"] == ["OWNER_APPROVAL_REQUIRED"]

    monkeypatch.setenv("MANGOME_APPROVAL_TOKEN", "owner-secret")
    approval = svc.request_override(
        action_type="AUTHORIZE_DELEGATION",
        subject_id=f"{family_id}:high-cost-judge:critical-judgment",
        requested_by="coordinator",
        reason="One bounded high-cost judgment is required",
    )
    approved = svc.approve_override(
        approval_id=approval["entity_id"], decided_by="owner", approval_token="owner-secret"
    )
    allowed = svc.check_execution_eligibility(
        worker_key="high-cost-judge",
        required_capabilities=["REASON"],
        cost_ceiling="EXPENSIVE",
        family_id=family_id,
        delegation_key="critical-judgment",
        owner_approval_id=approved["entity_id"],
    )
    assert allowed["eligible"] is True


def test_high_cost_fanout_is_serialized_per_family(monkeypatch):
    svc = IntegrityMangoMeService(InMemoryStore())
    family_id = _family(svc)
    monkeypatch.setenv("MANGOME_APPROVAL_TOKEN", "owner-secret")

    approvals = {}
    for worker in ("expensive-a", "expensive-b"):
        svc.register_worker_runtime(
            worker_key=worker,
            runtime_mode="NORMAL",
            capabilities=["REASON", "MUTATE", "TEST"],
            cost_class="EXPENSIVE",
        )
        approval = svc.request_override(
            action_type="AUTHORIZE_DELEGATION",
            subject_id=f"{family_id}:{worker}:delta-{worker[-1]}",
            requested_by="coordinator",
            reason="bounded high-cost work",
        )
        approvals[worker] = svc.approve_override(
            approval_id=approval["entity_id"], decided_by="owner", approval_token="owner-secret"
        )["entity_id"]

    first = svc.authorize_delegation(
        family_id=family_id,
        coordinator_actor_id="coordinator",
        worker_key="expensive-a",
        task_key="delta-a",
        purpose="Implement one bounded delta",
        required_capabilities=["MUTATE"],
        cost_ceiling="EXPENSIVE",
        owner_approval_id=approvals["expensive-a"],
    )
    assert first["authorized"] is True

    second = svc.authorize_delegation(
        family_id=family_id,
        coordinator_actor_id="coordinator",
        worker_key="expensive-b",
        task_key="delta-b",
        purpose="Implement another bounded delta",
        required_capabilities=["MUTATE"],
        cost_ceiling="EXPENSIVE",
        owner_approval_id=approvals["expensive-b"],
    )
    assert second["authorized"] is False
    assert second["eligibility"]["reason_codes"] == ["EXPENSIVE_FANOUT_LIMIT_REACHED"]

    svc.complete_delegation(
        delegation_id=first["delegation"]["entity_id"],
        coordinator_actor_id="coordinator",
        status="COMPLETED",
        artifact="checkpoint-a",
        missing_delta=None,
        next_dependency="delta-b",
    )
    retry = svc.authorize_delegation(
        family_id=family_id,
        coordinator_actor_id="coordinator",
        worker_key="expensive-b",
        task_key="delta-b",
        purpose="Implement another bounded delta",
        required_capabilities=["MUTATE"],
        cost_ceiling="EXPENSIVE",
        owner_approval_id=approvals["expensive-b"],
    )
    assert retry["authorized"] is True


def test_missing_capability_never_selects_a_substitute_worker():
    svc = IntegrityMangoMeService(InMemoryStore())
    family_id = _family(svc)
    svc.register_worker_runtime(
        worker_key="reserve-worker",
        runtime_mode="RESERVE",
        capabilities=["READ", "REASON"],
        cost_class="CHEAP",
    )
    svc.register_worker_runtime(
        worker_key="expensive-substitute",
        runtime_mode="NORMAL",
        capabilities=["READ", "REASON", "DEPLOY"],
        cost_class="EXPENSIVE",
    )

    decision = svc.authorize_delegation(
        family_id=family_id,
        coordinator_actor_id="coordinator",
        worker_key="reserve-worker",
        task_key="deploy-delta",
        purpose="Deploy completed bounded delta",
        required_capabilities=["DEPLOY"],
        cost_ceiling="CHEAP",
    )

    assert decision["authorized"] is False
    assert decision["eligibility"]["handoff_policy"] == "CHECKPOINT_AND_HANDOFF_MISSING_CAPABILITY_ONLY"
    # MangoMe is a policy/coordination substrate, not a dispatcher: failure to
    # authorize one worker must not silently select or spawn another model.
    assert svc.store.find("delegations") == []


def test_high_cost_owner_approval_is_bound_to_one_delegation_task(monkeypatch):
    svc = IntegrityMangoMeService(InMemoryStore())
    family_id = _family(svc)
    monkeypatch.setenv("MANGOME_APPROVAL_TOKEN", "owner-secret")
    svc.register_worker_runtime(
        worker_key="monster-worker",
        runtime_mode="NORMAL",
        capabilities=["REASON", "MUTATE"],
        cost_class="PREMIUM",
    )
    approval = svc.request_override(
        action_type="AUTHORIZE_DELEGATION",
        subject_id=f"{family_id}:monster-worker:bounded-delta-1",
        requested_by="coordinator",
        reason="One explicitly approved premium delegation",
    )
    approval_id = svc.approve_override(
        approval_id=approval["entity_id"], decided_by="owner", approval_token="owner-secret"
    )["entity_id"]

    first = svc.authorize_delegation(
        family_id=family_id, coordinator_actor_id="coordinator", worker_key="monster-worker",
        task_key="bounded-delta-1", purpose="Critical bounded change",
        required_capabilities=["MUTATE"], cost_ceiling="PREMIUM", owner_approval_id=approval_id,
    )
    assert first["authorized"] is True
    svc.complete_delegation(
        delegation_id=first["delegation"]["entity_id"], coordinator_actor_id="coordinator", status="COMPLETED"
    )

    second = svc.authorize_delegation(
        family_id=family_id, coordinator_actor_id="coordinator", worker_key="monster-worker",
        task_key="bounded-delta-2", purpose="Another critical bounded change",
        required_capabilities=["MUTATE"], cost_ceiling="PREMIUM", owner_approval_id=approval_id,
    )
    assert second["authorized"] is False
    assert "OWNER_APPROVAL_REQUIRED" in second["eligibility"]["reason_codes"]
