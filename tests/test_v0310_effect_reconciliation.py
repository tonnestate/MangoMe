from __future__ import annotations

import pytest

from mangome.effect_control import EffectJournalService
from mangome.service import InvalidTransition
from mangome.storage.memory import InMemoryStore
from mangome.work_control import WorkGovernedMangoMeService


def _entered():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    entered = svc.enter_work(
        workspace_id="/workspace/v0310",
        workspace_title="MangoMe v0.3.10",
        actor_id="worker-a",
        request_text="implement persistent effect reconciliation",
        intent="implement PER/1",
    )
    return svc, entered, entered["work"]["slice"], entered["work"]["plan"], entered["turn"]


def _verify_turn(svc, entered, actor):
    return svc.bind_work_turn(
        work_ref=entered["work_identity"]["entity_id"],
        request_text=f"{actor} assurance",
        mode="VERIFY",
        actor_id=actor,
    )["turn"]


def _done_and_validated(svc, entered, sl, plan):
    done = svc.claim_done(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        plan_id=plan["entity_id"],
    )
    assert done["execution_state"] == "DONE_CLAIMED"
    assert done["validation_state"] == "PENDING"
    assert done["closure_state"] == "OPEN"

    turn = _verify_turn(svc, entered, "validator-a")
    validated = svc.validate_slice(
        slice_id=sl["entity_id"],
        validator_actor_id="validator-a",
        status="VALIDATED",
        turn_id=turn["entity_id"],
    )
    assert validated["validation_state"] == "VALIDATED"
    assert validated["closure_state"] == "OPEN"
    return turn


def _independent_pass(svc, entered, sl, monkeypatch):
    monkeypatch.setenv("MANGOME_VERIFIER_TOKEN", "verify-secret")
    turn = _verify_turn(svc, entered, "verifier-a")
    evidence = svc.submit_verification_observation(
        slice_id=sl["entity_id"],
        verifier_actor_id="verifier-a",
        verifier_token="verify-secret",
        claim="slice satisfies its intended result",
        observation_type="OTHER",
        status="PASS",
        evidence_type="V0310",
        evidence_class="RUNTIME_OBSERVATION",
        source="test",
        turn_id=turn["entity_id"],
    )
    return turn, evidence


def test_done_claim_is_not_slice_completion_and_rework_reopens_execution():
    svc, entered, sl, plan, _ = _entered()
    done = svc.claim_done(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        plan_id=plan["entity_id"],
    )
    assert done["validation_state"] == "PENDING"
    assert done["closure_state"] == "OPEN"

    validation_turn = _verify_turn(svc, entered, "validator-a")
    rejected = svc.validate_slice(
        slice_id=sl["entity_id"],
        validator_actor_id="validator-a",
        status="REWORK_REQUIRED",
        note="one implementation delta remains",
        completed_items=["effect journal model"],
        open_deltas=["closure transition"],
        turn_id=validation_turn["entity_id"],
    )
    assert rejected["validation_state"] == "REWORK_REQUIRED"

    restarted = svc.start_slice(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        plan_id=plan["entity_id"],
    )
    assert restarted["slice"]["execution_state"] == "ACTIVE"
    assert restarted["slice"]["validation_state"] == "NOT_STARTED"
    assert restarted["slice"]["validation_at"] is None
    assert restarted["slice"]["validation_actor_id"] is None
    assert restarted["slice"]["validation_open_deltas"] == []
    assert restarted["slice"]["closure_state"] == "OPEN"


def test_verification_requires_validation(monkeypatch):
    svc, entered, sl, plan, _ = _entered()
    svc.claim_done(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        plan_id=plan["entity_id"],
    )
    verify_turn, evidence = _independent_pass(svc, entered, sl, monkeypatch)
    with pytest.raises(InvalidTransition, match="VALIDATED"):
        svc.verify_slice(
            slice_id=sl["entity_id"],
            verifier_actor_id="verifier-a",
            verifier_token="verify-secret",
            evidence_ids=[evidence["entity_id"]],
            turn_id=verify_turn["entity_id"],
        )


def test_verified_slice_closes_when_no_required_effect_is_open(monkeypatch):
    svc, entered, sl, plan, _ = _entered()
    _done_and_validated(svc, entered, sl, plan)
    verify_turn, evidence = _independent_pass(svc, entered, sl, monkeypatch)

    verified = svc.verify_slice(
        slice_id=sl["entity_id"],
        verifier_actor_id="verifier-a",
        verifier_token="verify-secret",
        evidence_ids=[evidence["entity_id"]],
        turn_id=verify_turn["entity_id"],
    )
    assert verified["assurance_state"] == "VERIFIED"
    assert verified["closure_state"] == "CLOSED"
    assert verified["closure_decision"]["blocking_effect_ids"] == []


def test_required_effect_keeps_verified_slice_open_until_reconciled(monkeypatch):
    svc, entered, sl, plan, worker_turn = _entered()
    effects = EffectJournalService(svc)
    intent = effects.record_intent(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        turn_id=worker_turn["entity_id"],
        effect_key="deploy-production",
        action="DEPLOY",
        target="production",
        payload_hash="abc123",
        expected_state={"sha": "abc123"},
    )["effect"]
    effects.mark_dispatched(
        effect_id=intent["entity_id"],
        actor_id="worker-a",
        turn_id=worker_turn["entity_id"],
        receipt={"request_id": "req-1"},
    )
    effects.record_observation(
        effect_id=intent["entity_id"],
        actor_id="worker-a",
        turn_id=worker_turn["entity_id"],
        outcome="UNKNOWN",
    )
    with pytest.raises(InvalidTransition, match="RETRY_REQUIRES_KNOWN_NON_EXECUTION"):
        effects.mark_dispatched(
            effect_id=intent["entity_id"],
            actor_id="worker-a",
            turn_id=worker_turn["entity_id"],
        )

    _done_and_validated(svc, entered, sl, plan)
    verify_turn, evidence = _independent_pass(svc, entered, sl, monkeypatch)
    verified = svc.verify_slice(
        slice_id=sl["entity_id"],
        verifier_actor_id="verifier-a",
        verifier_token="verify-secret",
        evidence_ids=[evidence["entity_id"]],
        turn_id=verify_turn["entity_id"],
        close_slice=True,
    )
    assert verified["assurance_state"] == "VERIFIED"
    assert verified["closure_state"] == "OPEN"
    assert verified["closure_decision"]["blocking_effect_ids"] == [intent["entity_id"]]

    with pytest.raises(InvalidTransition, match="CONFIRMED"):
        effects.reconcile(
            effect_id=intent["entity_id"],
            actor_id="verifier-a",
            turn_id=verify_turn["entity_id"],
            satisfied=True,
            verifier_token="verify-secret",
            observed_state={"sha": "abc123"},
            resolution="unknown outcome cannot satisfy effect",
        )

    effects.record_observation(
        effect_id=intent["entity_id"],
        actor_id="verifier-a",
        turn_id=verify_turn["entity_id"],
        outcome="CONFIRMED",
        observed_state={"sha": "abc123"},
    )
    effects.reconcile(
        effect_id=intent["entity_id"],
        actor_id="verifier-a",
        turn_id=verify_turn["entity_id"],
        satisfied=True,
        verifier_token="verify-secret",
        observed_state={"sha": "abc123"},
        resolution="production independently observed at expected sha",
    )
    closed = svc.close_verified_slice(
        slice_id=sl["entity_id"],
        verifier_actor_id="verifier-a",
        verifier_token="verify-secret",
        turn_id=verify_turn["entity_id"],
    )
    assert closed["closure_state"] == "CLOSED"


def test_effect_key_is_idempotent_but_cannot_change_logical_effect():
    svc, _, sl, _, worker_turn = _entered()
    effects = EffectJournalService(svc)
    first = effects.record_intent(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        turn_id=worker_turn["entity_id"],
        effect_key="send-1",
        action="SEND",
        target="endpoint-a",
        payload_hash="p1",
    )
    second = effects.record_intent(
        slice_id=sl["entity_id"],
        actor_id="worker-a",
        turn_id=worker_turn["entity_id"],
        effect_key="send-1",
        action="SEND",
        target="endpoint-a",
        payload_hash="p1",
    )
    assert first["effect"]["entity_id"] == second["effect"]["entity_id"]
    assert second["idempotent"] is True

    with pytest.raises(InvalidTransition, match="EFFECT_KEY_CONFLICT"):
        effects.record_intent(
            slice_id=sl["entity_id"],
            actor_id="worker-a",
            turn_id=worker_turn["entity_id"],
            effect_key="send-1",
            action="SEND",
            target="endpoint-b",
            payload_hash="p2",
        )


def test_recovery_surfaces_rework_in_active_methods():
    svc, entered, sl, plan, _ = _entered()
    svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    validation_turn = _verify_turn(svc, entered, "validator-a")
    svc.validate_slice(
        slice_id=sl["entity_id"],
        validator_actor_id="validator-a",
        status="REWORK_REQUIRED",
        open_deltas=["repair remaining delta"],
        turn_id=validation_turn["entity_id"],
    )

    project_ref = entered["project"]["entity_id"]
    recovery = svc.recovery_context(project_ref)
    family = next(row for row in recovery["families"] if row["family_id"] == entered["family"]["entity_id"] )
    item = next(row for row in family["recovery_slices"] if row["entity_id"] == sl["entity_id"] )
    assert item["validation_state"] == "REWORK_REQUIRED"
    assert item["closure_state"] == "OPEN"

    restored = svc.session_restore(project_ref)
    assert any(row["entity_id"] == sl["entity_id"] for row in restored["next_executable_items"])
    assert any(row["entity_id"] == sl["entity_id"] for row in restored["pending_closure_items"])


def test_positive_reconciliation_requires_verifier_authority(monkeypatch):
    from mangome.service import ApprovalRequired

    svc, entered, sl, _, worker_turn = _entered()
    effects = EffectJournalService(svc)
    effect = effects.record_intent(
        slice_id=sl["entity_id"], actor_id="worker-a", turn_id=worker_turn["entity_id"],
        effect_key="notify-provider", action="SEND", target="provider", payload_hash="p1",
    )["effect"]
    effects.mark_dispatched(effect_id=effect["entity_id"], actor_id="worker-a", turn_id=worker_turn["entity_id"])
    verify_turn = _verify_turn(svc, entered, "verifier-a")
    effects.record_observation(
        effect_id=effect["entity_id"], actor_id="verifier-a", turn_id=verify_turn["entity_id"],
        outcome="CONFIRMED", observed_state={"delivered": True},
    )
    monkeypatch.setenv("MANGOME_VERIFIER_TOKEN", "verify-secret")
    with pytest.raises(ApprovalRequired):
        effects.reconcile(
            effect_id=effect["entity_id"], actor_id="verifier-a", turn_id=verify_turn["entity_id"],
            satisfied=True, observed_state={"delivered": True},
        )
    reconciled = effects.reconcile(
        effect_id=effect["entity_id"], actor_id="verifier-a", turn_id=verify_turn["entity_id"],
        satisfied=True, verifier_token="verify-secret", observed_state={"delivered": True},
    )
    assert reconciled["state"] == "RECONCILED"
    assert reconciled["satisfied"] is True


def test_effect_identity_conflicts_when_provider_idempotency_key_changes():
    svc, _, sl, _, worker_turn = _entered()
    effects = EffectJournalService(svc)
    first = effects.record_intent(
        slice_id=sl["entity_id"], actor_id="worker-a", turn_id=worker_turn["entity_id"],
        effect_key="send-stable", action="SEND", target="endpoint", payload_hash="p1", idempotency_key="provider-1",
    )
    assert first["effect"]["entity_id"].startswith("EFFECT-")
    with pytest.raises(InvalidTransition, match="EFFECT_KEY_CONFLICT"):
        effects.record_intent(
            slice_id=sl["entity_id"], actor_id="worker-a", turn_id=worker_turn["entity_id"],
            effect_key="send-stable", action="SEND", target="endpoint", payload_hash="p1", idempotency_key="provider-2",
        )


def test_legacy_non_workidentity_acceptance_remains_compatible(monkeypatch):
    monkeypatch.setenv("MANGOME_VERIFIER_TOKEN", "verify-secret")
    monkeypatch.setenv("MANGOME_VERIFIER_ACTORS", "verifier-b")
    monkeypatch.setenv("MANGOME_APPROVAL_TOKEN", "owner-secret")
    monkeypatch.setenv("MANGOME_APPROVER_ACTORS", "human-owner")

    svc = WorkGovernedMangoMeService(InMemoryStore())
    family = svc.create_family("F-LEGACY-310", "Legacy family")
    contract = svc.register_contract(
        declared_id="C-LEGACY-310", family_id=family["entity_id"], title="Legacy contract"
    )
    req = svc.intake_request(
        request_text="legacy work", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"]
    )
    spec = svc.create_spec(
        family_id=family["entity_id"], objective="Legacy objective", contract_ids=[contract["entity_id"]]
    )
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"],
        actor_id="worker-a", intent="legacy execute", contract_ids=[contract["entity_id"]],
        proposed_slices=[{"declared_id": "S-LEGACY-310", "title": "Legacy slice", "acceptance": ["passes"]}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
    evidence = svc.submit_verification_observation(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token="verify-secret",
        claim="passes", observation_type="OTHER", status="PASS", evidence_type="legacy",
        evidence_class="RUNTIME_OBSERVATION", source="test",
    )
    gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
    svc.set_gate(
        slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b",
        evidence_ids=[evidence["entity_id"]],
    )
    verified = svc.verify_slice(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token="verify-secret"
    )
    assert verified["assurance_state"] == "VERIFIED"
    assert verified["closure_state"] == "OPEN"

    approval = svc.request_override(
        action_type="ACCEPT_SLICE", subject_id=sl["entity_id"], requested_by="verifier-b", reason="legacy acceptance"
    )
    approval = svc.approve_override(
        approval_id=approval["entity_id"], decided_by="human-owner", approval_token="owner-secret"
    )
    accepted = svc.accept_slice(slice_id=sl["entity_id"], approval_id=approval["entity_id"])
    assert accepted["assurance_state"] == "ACCEPTED"


def test_family_status_exposes_validation_closure_and_effect_blockers(monkeypatch):
    svc, entered, sl, plan, worker_turn = _entered()
    effects = EffectJournalService(svc)
    effect = effects.record_intent(
        slice_id=sl["entity_id"], actor_id="worker-a", turn_id=worker_turn["entity_id"],
        effect_key="publish-status", action="DEPLOY", target="production", payload_hash="status-sha",
    )["effect"]

    _done_and_validated(svc, entered, sl, plan)
    verify_turn, evidence = _independent_pass(svc, entered, sl, monkeypatch)
    verified = svc.verify_slice(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-a", verifier_token="verify-secret",
        evidence_ids=[evidence["entity_id"]], turn_id=verify_turn["entity_id"],
    )
    assert verified["assurance_state"] == "VERIFIED"
    assert verified["closure_state"] == "OPEN"

    status = svc.status(entered["family"]["entity_id"])
    assert status["validation_counts"]["VALIDATED"] == 1
    assert status["closure_counts"]["OPEN"] == 1
    assert status["pending_closure_slice_ids"] == [sl["entity_id"]]
    assert status["open_required_effect_ids"] == [effect["entity_id"]]
    assert status["open_required_effect_count"] == 1
