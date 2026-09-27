from __future__ import annotations

import pytest

from mangome.context import ContextCompiler
from mangome.interlingua import UAICompiler
from mangome.storage.memory import InMemoryStore
from mangome.work_control import (
    NormativeBaselineDrift,
    WorkGovernedMangoMeService,
    WorkTurnError,
)


def _entered():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    result = svc.enter_work(
        workspace_id="/workspace/demo",
        workspace_title="Demo",
        actor_id="worker-a",
        request_text="Implement the bounded change",
        intent="Implement change",
        acceptance_criteria=["change is observable"],
    )
    return svc, result


def test_enter_work_admits_identity_without_turning_prompt_into_spec():
    svc, result = _entered()
    work = result["work_identity"]
    plan = result["work"]["plan"]
    baseline = result["normative_baseline"]

    assert result["spec"] is None
    assert result["spec_admitted"] is False
    assert work["persistence_level"] == "CANONICAL"
    assert baseline["semantics"]["source"]["kind"] == "OPERATIONAL_INTENT"
    assert plan["work_id"] == work["entity_id"]
    assert plan["turn_id"] == result["turn"]["entity_id"]
    assert plan["normative_baseline_id"] == baseline["entity_id"]
    assert svc.store.find("specs", {"family_id": work["family_id"]}) == []


def test_progressive_checkpoint_cannot_invent_work_identity():
    svc, result = _entered()
    with pytest.raises(KeyError):
        svc.checkpoint_work(work_ref="DOES-NOT-EXIST", actor_id="worker-a", payload={"step": 1})

    checkpoint = svc.checkpoint_work(
        work_ref=result["work_identity"]["entity_id"],
        actor_id="worker-a",
        plan_id=result["work"]["plan"]["entity_id"],
        turn_id=result["turn"]["entity_id"],
        payload={"step": 1},
    )
    assert checkpoint["persistence_level"] == "PROGRESSIVE"
    assert checkpoint["work_id"] == result["work_identity"]["entity_id"]


def test_playbook_selection_is_non_normative_and_does_not_change_effective_truth():
    svc, result = _entered()
    work_id = result["work_identity"]["entity_id"]
    before = svc.current_normative_baseline(work_id)["semantic_hash"]
    playbook = svc.register_playbook(
        playbook_key="python-repair",
        version="1",
        description="Repair Python code",
        source="skill://python-repair",
        content_hash="a" * 64,
    )
    selection = svc.select_playbook(
        work_ref=work_id,
        playbook_id=playbook["entity_id"],
        actor_id="worker-a",
        turn_id=result["turn"]["entity_id"],
    )
    after = svc.current_normative_baseline(work_id)["semantic_hash"]
    assert selection["persistence_level"] == "PROGRESSIVE"
    assert playbook["authority"] == "PROCEDURAL_NON_NORMATIVE"
    assert before == after


def test_spec_evolution_requires_modify_turn_and_invalidates_stale_plan_baseline():
    svc, result = _entered()
    work = result["work_identity"]
    family_id = work["family_id"]
    plan = result["work"]["plan"]
    slice_id = result["work"]["slice"]["entity_id"]

    with pytest.raises(WorkTurnError):
        svc.create_spec(
            family_id=family_id,
            objective="New normative objective",
            actor_id="writer",
            work_id=work["entity_id"],
        )

    modify = svc.bind_work_turn(
        work_ref=work["entity_id"],
        request_text="Change the normative target",
        mode="MODIFY",
        actor_id="writer",
    )
    spec = svc.create_spec(
        family_id=family_id,
        objective="New normative objective",
        acceptance_criteria=["new criterion"],
        actor_id="writer",
        work_id=work["entity_id"],
        turn_id=modify["turn"]["entity_id"],
    )
    assert spec["objective"] == "New normative objective"
    current = svc.current_normative_baseline(work["entity_id"])
    assert current["entity_id"] != plan["normative_baseline_id"]

    with pytest.raises(NormativeBaselineDrift, match="BASELINE_DRIFT"):
        svc.update_slice_progress(
            slice_id=slice_id,
            actor_id="worker-a",
            plan_id=plan["entity_id"],
            current_step=1,
        )


def test_assurance_history_is_work_bound_and_survives_spec_change():
    svc, result = _entered()
    work = result["work_identity"]
    slice_id = result["work"]["slice"]["entity_id"]
    plan_id = result["work"]["plan"]["entity_id"]
    original_baseline = result["normative_baseline"]["entity_id"]

    svc.claim_done(slice_id=slice_id, actor_id="worker-a", plan_id=plan_id, summary="implemented")
    events = svc.store.find("assurance_events", {"work_id": work["entity_id"]})
    assert len(events) == 1
    assert events[0]["event_type"] == "DONE_CLAIMED"
    assert events[0]["normative_baseline_id"] == original_baseline

    modify = svc.bind_work_turn(
        work_ref=work["entity_id"], request_text="Admit a specification", mode="MODIFY", actor_id="writer"
    )
    svc.create_spec(
        family_id=work["family_id"], objective="Specified target", actor_id="writer",
        work_id=work["entity_id"], turn_id=modify["turn"]["entity_id"],
    )
    assert svc.current_normative_baseline(work["entity_id"])["entity_id"] != original_baseline
    events_after = svc.store.find("assurance_events", {"work_id": work["entity_id"]})
    assert [e["entity_id"] for e in events_after] == [events[0]["entity_id"]]


def test_context_and_uai_expose_persistence_boundaries():
    svc, result = _entered()
    work_id = result["work_identity"]["entity_id"]
    family_id = result["family"]["entity_id"]
    slice_id = result["work"]["slice"]["entity_id"]
    playbook = svc.register_playbook(
        playbook_key="bounded-work", version="1", description="Bounded execution",
        source="skill://bounded-work", content_hash="b" * 64,
    )
    svc.select_playbook(
        work_ref=work_id, playbook_id=playbook["entity_id"], actor_id="worker-a",
        turn_id=result["turn"]["entity_id"],
    )
    svc.checkpoint_work(
        work_ref=work_id, actor_id="worker-a", plan_id=result["work"]["plan"]["entity_id"],
        turn_id=result["turn"]["entity_id"], payload={"cursor": 4},
    )

    compiled = ContextCompiler(svc).compile(family_id, slice_id)
    assert compiled["persistence"]["canonical"]["persistence_level"] == "CANONICAL"
    assert compiled["persistence"]["progressive"]["persistence_level"] == "PROGRESSIVE"
    assert compiled["persistence"]["volatile"]["persistence_level"] == "VOLATILE"
    assert compiled["persistence"]["canonical"]["work_identity"]["entity_id"] == work_id

    uai = UAICompiler(svc)
    projection = uai.semantic_projection(family_id, slice_id)
    assert projection["persistence"]["canonical"]["work_id"] == work_id
    decoded = uai.decode_context(uai.compile(family_id, slice_id)["wire"])
    assert decoded["persistence"] == projection["persistence"]


def test_hot_read_paths_do_not_recompute_or_write_materialized_work_state():
    svc, result = _entered()
    family_id = result["family"]["entity_id"]
    work_id = result["work_identity"]["entity_id"]
    family_before = svc.store.get("families", family_id)
    view_before = svc.store.get("project_views", family_id)
    baselines_before = svc.store.find("normative_baselines", {"work_id": work_id})

    first = svc.status(family_id)
    second = svc.status(family_id)
    effective = svc.effective_family_view(family_id)

    family_after = svc.store.get("families", family_id)
    view_after = svc.store.get("project_views", family_id)
    baselines_after = svc.store.find("normative_baselines", {"work_id": work_id})
    assert first["entity_id"] == second["entity_id"] == family_id
    assert family_after["revision"] == family_before["revision"]
    assert view_after["revision"] == view_before["revision"]
    assert len(baselines_after) == len(baselines_before)
    assert effective["effective_normative_baseline"]["status"] == "CURRENT"
    assert effective["playbooks_affect_effective_truth"] is False


def test_historical_backfill_does_not_invent_user_intent_and_requires_normative_target():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    project = svc.create_project("LEGACY-P", "Legacy")
    family = svc.create_family("LEGACY-F", "Legacy Family", project_ids=[project["entity_id"]])
    work = svc.backfill_work_identity(
        family_id=family["entity_id"], project_id=project["entity_id"], admitted_by="controller",
        source_ref="migration:v0.3",
    )
    baseline = svc.current_normative_baseline(work["entity_id"])
    assert baseline["semantics"]["source"]["kind"] == "HISTORICAL_CANONICAL_STATE"
    assert work["admission_request_id"] is None

    turn = svc.bind_work_turn(
        work_ref=work["entity_id"], request_text="Continue legacy work", mode="EXECUTE", actor_id="worker-a"
    )
    request = svc.intake_request(
        request_text="Continue legacy work", classification="OPERATIONAL_TASK",
        classification_source="test", family_id=family["entity_id"],
    )
    with pytest.raises(Exception, match="NORMATIVE_BASELINE_REQUIRED"):
        svc.submit_plan(
            family_id=family["entity_id"], request_id=request["entity_id"], actor_id="worker-a",
            intent="continue", proposed_slices=[{"title": "legacy"}], work_id=work["entity_id"],
            turn_id=turn["turn"]["entity_id"],
        )


def test_backfilled_family_with_existing_spec_can_resume_under_work_identity():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    project = svc.create_project("LEGACY-SPEC-P", "Legacy")
    family = svc.create_family("LEGACY-SPEC-F", "Legacy Family", project_ids=[project["entity_id"]])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Existing normative target")
    work = svc.backfill_work_identity(
        family_id=family["entity_id"], project_id=project["entity_id"], admitted_by="controller"
    )
    baseline = svc.current_normative_baseline(work["entity_id"])
    assert baseline["semantics"]["source"]["kind"] == "SPECIFICATION"
    assert baseline["semantics"]["source"]["spec_id"] == spec["entity_id"]

    request = svc.intake_request(
        request_text="Resume", classification="OPERATIONAL_TASK", classification_source="test",
        family_id=family["entity_id"],
    )
    with pytest.raises(WorkTurnError, match="WORK_TURN_REQUIRED"):
        svc.submit_plan(
            family_id=family["entity_id"], request_id=request["entity_id"], actor_id="worker-a",
            intent="resume", proposed_slices=[{"title": "resume"}], work_id=work["entity_id"],
        )

    turn = svc.bind_work_turn(
        work_ref=work["entity_id"], request_text="Resume", mode="EXECUTE", actor_id="worker-a"
    )
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=request["entity_id"], actor_id="worker-a",
        intent="resume", proposed_slices=[{"title": "resume"}], work_id=work["entity_id"],
        turn_id=turn["turn"]["entity_id"], spec_id=spec["entity_id"],
    )
    assert plan["work_id"] == work["entity_id"]
    assert plan["normative_baseline_id"] == baseline["entity_id"]


def test_restore_accepts_operational_intent_baseline_without_manufacturing_spec():
    svc, result = _entered()
    project_key = result["project"]["project_key"]
    restored = svc.session_restore(project_key)
    assert restored["restore_state"] == "STATE_FOUND"
    assert restored["productive_execution_allowed"] is False
    assert restored["turn_binding_required"] is True
    assert not [r for r in restored["reason_codes"] if r.endswith(":CURRENT_SPEC_MISSING")]


def test_restore_keeps_historical_backfill_without_spec_partial():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    project = svc.create_project("HIST-P", "Historical")
    family = svc.create_family("HIST-F", "Historical", project_ids=[project["entity_id"]])
    svc.backfill_work_identity(family_id=family["entity_id"], project_id=project["entity_id"])
    # Ensure a deterministic family view exists, as write paths do in real operation.
    svc._project_family(family["entity_id"])
    restored = svc.session_restore(project["project_key"])
    assert restored["restore_state"] == "STATE_PARTIAL"
    assert any(r.endswith(":CURRENT_SPEC_MISSING") for r in restored["reason_codes"])
