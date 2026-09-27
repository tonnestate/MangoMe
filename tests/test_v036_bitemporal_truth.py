from __future__ import annotations

from datetime import datetime, timezone

from mangome.hygiene import CognitiveHygieneService
from mangome.storage.memory import InMemoryStore
from mangome.truth import BitemporalTruthService
from mangome.work_control import WorkGovernedMangoMeService


def _entered():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    result = svc.enter_work(
        workspace_id="/workspace/truth-demo",
        workspace_title="Truth Demo",
        actor_id="worker-a",
        request_text="Maintain a temporally auditable fact set",
        intent="Maintain facts",
        acceptance_criteria=["facts remain historically reconstructable"],
    )
    work = result["work_identity"]
    verify = svc.bind_work_turn(
        work_ref=work["entity_id"], request_text="Verify observations", mode="VERIFY", actor_id="verifier-a"
    )
    modify = svc.bind_work_turn(
        work_ref=work["entity_id"], request_text="Revise truth", mode="MODIFY", actor_id="editor-a"
    )
    return svc, result, verify["turn"], modify["turn"]


def test_bitemporal_query_separates_valid_time_from_known_time():
    svc, entered, verify, _ = _entered()
    family_id = entered["family"]["entity_id"]
    evidence = svc.submit_evidence(
        subject_id=family_id, evidence_type="OBSERVATION", source="test", result="PASS", actor_id="verifier-a"
    )
    truth = BitemporalTruthService(svc)
    recorded = truth.record_assertion(
        work_ref=entered["work_identity"]["entity_id"],
        subject_id=family_id,
        predicate="dependency.version",
        value="2.0",
        actor_id="verifier-a",
        turn_id=verify["entity_id"],
        valid_from="2026-09-20T00:00:00+00:00",
        valid_to="2026-09-30T00:00:00+00:00",
        known_from="2026-09-22T00:00:00+00:00",
        evidence_ids=[evidence["entity_id"]],
    )
    assert recorded["evaluation"]["support_state"] == "SUPPORTED"

    before_known = truth.truth_at(
        work_ref=entered["work_identity"]["entity_id"],
        valid_at="2026-09-21T00:00:00+00:00",
        known_at="2026-09-21T00:00:00+00:00",
    )
    assert before_known["assertions"] == []

    later_known = truth.truth_at(
        work_ref=entered["work_identity"]["entity_id"],
        valid_at="2026-09-21T00:00:00+00:00",
        known_at="2026-09-23T00:00:00+00:00",
    )
    assert [x["assertion"]["value"] for x in later_known["assertions"]] == ["2.0"]


def test_invalidation_preserves_history_and_reheats_dependents():
    svc, entered, verify, modify = _entered()
    family_id = entered["family"]["entity_id"]
    evidence = svc.submit_evidence(
        subject_id=family_id, evidence_type="OBSERVATION", source="test", result="PASS", actor_id="verifier-a"
    )
    truth = BitemporalTruthService(svc)
    base = truth.record_assertion(
        work_ref=entered["work_identity"]["entity_id"], subject_id=family_id,
        predicate="service.available", value=True, actor_id="verifier-a", turn_id=verify["entity_id"],
        known_from="2026-09-20T10:00:00+00:00", evidence_ids=[evidence["entity_id"]],
    )["assertion"]
    derived = truth.record_assertion(
        work_ref=entered["work_identity"]["entity_id"], subject_id=family_id,
        predicate="dashboard.usable", value=True, actor_id="verifier-a", turn_id=verify["entity_id"],
        known_from="2026-09-20T10:01:00+00:00", support_ids=[base["entity_id"]],
    )["assertion"]
    assert truth.evaluate(derived["entity_id"], known_at="2026-09-20T10:02:00+00:00")["support_state"] == "SUPPORTED"

    invalidated = truth.invalidate(
        assertion_id=base["entity_id"], actor_id="editor-a", turn_id=modify["entity_id"],
        reason="live observation failed", known_at="2026-09-21T10:00:00+00:00",
    )
    assert derived["entity_id"] in invalidated["revalidation_frontier"]
    current_derived = svc.store.get("truth_assertions", derived["entity_id"])
    assert current_derived["support_state"] == "REVALIDATION_REQUIRED"
    assert current_derived["validity_status"] == "REVALIDATION_REQUIRED"

    historical = truth.truth_at(
        work_ref=entered["work_identity"]["entity_id"],
        valid_at="2026-09-20T12:00:00+00:00",
        known_at="2026-09-20T12:00:00+00:00",
        include_unsupported=True,
    )
    ids = {x["assertion"]["entity_id"] for x in historical["assertions"]}
    assert base["entity_id"] in ids
    assert derived["entity_id"] in ids

    pch = CognitiveHygieneService(svc).evaluate(family_id, query_text="dashboard service revalidation")
    row = next(x for x in pch["thermal_map"] if x["entity_id"] == derived["entity_id"])
    assert row["validity_status"] == "REVALIDATION_REQUIRED"
    assert row["signals"]["revalidation_attention_boost"] > 0


def test_ungrounded_worker_assertion_never_becomes_supported_truth():
    svc, entered, verify, _ = _entered()
    family_id = entered["family"]["entity_id"]
    truth = BitemporalTruthService(svc)
    result = truth.record_assertion(
        work_ref=entered["work_identity"]["entity_id"], subject_id=family_id,
        predicate="worker.guess", value="probably", actor_id="verifier-a", turn_id=verify["entity_id"],
    )
    assert result["evaluation"]["support_state"] == "UNSUPPORTED"
