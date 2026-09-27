from __future__ import annotations

import pytest

from mangome.fast_judgment import FastJudgmentError, FastJudgmentService
from mangome.models import utcnow
from mangome.maintenance import MangoMaintainer
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def _service_with_work() -> tuple[MangoMeService, str]:
    svc = MangoMeService(InMemoryStore())
    now = utcnow()
    work_id = "01TESTFASTJUDGMENT000000001"
    svc.store.insert(
        "work_identities",
        {
            "entity_id": work_id,
            "schema_version": 5,
            "revision": 0,
            "created_at": now,
            "updated_at": now,
            "work_key": "TEST-FAST-JUDGMENT",
            "family_id": "F-1",
        },
    )
    return svc, work_id


def test_fjd1_validates_bool_score_choice_and_keeps_judgment_non_authoritative():
    result = FastJudgmentService().assess(
        purpose="audit triage",
        source="local-small-model",
        model_ref="tiny-local-v1",
        decisions=[
            {"name": "material", "type": "BOOL", "value": True, "confidence": 0.93, "role": "TRIAGE"},
            {"name": "relevance", "type": "SCORE", "value": 0.87, "confidence": 0.90, "role": "ACTIVATION"},
            {
                "name": "impact_class",
                "type": "CHOICE",
                "value": "CROSS_SCOPE",
                "options": ["LOCAL", "CROSS_SCOPE", "SYSTEM"],
                "confidence": 0.84,
                "role": "CLASSIFICATION",
            },
        ],
    )

    assert result["protocol"] == "FJD/1"
    assert result["batch_disposition"] == "USE_SIGNAL"
    assert result["epistemic_role"] == "WORKER_JUDGMENT"
    assert result["authority"] == {
        "may_create_canonical_truth": False,
        "may_create_evidence": False,
        "may_verify": False,
        "may_accept": False,
        "may_grant_mutation": False,
    }
    assert "CONFIDENCE_IS_NOT_TRUTH" in result["principles"]
    assert "MUTATION_AUTHORITY" in result["forbidden_uses"]


def test_fjd1_low_confidence_escalates_and_mid_confidence_reviews():
    review = FastJudgmentService().assess(
        purpose="routing",
        decisions=[{"name": "route", "type": "BOOL", "value": True, "confidence": 0.70}],
    )
    assert review["batch_disposition"] == "REVIEW"
    assert review["fallback"] == "STRONGER_REASONING_OR_DETERMINISTIC_CHECK"

    escalate = FastJudgmentService().assess(
        purpose="routing",
        decisions=[{"name": "route", "type": "BOOL", "value": True, "confidence": 0.40}],
    )
    assert escalate["batch_disposition"] == "ESCALATE"


def test_fjd1_high_impact_never_auto_uses_signal_even_at_high_confidence():
    result = FastJudgmentService().assess(
        purpose="security triage",
        high_impact=True,
        decisions=[{"name": "material", "type": "BOOL", "value": True, "confidence": 0.99}],
    )
    assert result["batch_disposition"] == "REVIEW_REQUIRED"
    assert result["decisions"][0]["disposition"] == "REVIEW_REQUIRED"


def test_fjd1_is_strict_about_typed_outputs():
    with pytest.raises(FastJudgmentError):
        FastJudgmentService().assess(
            purpose="bad bool",
            decisions=[{"name": "x", "type": "BOOL", "value": "yes", "confidence": 0.9}],
        )
    with pytest.raises(FastJudgmentError):
        FastJudgmentService().assess(
            purpose="bad choice",
            decisions=[{"name": "x", "type": "CHOICE", "value": "C", "options": ["A", "B"], "confidence": 0.9}],
        )


def test_fjd1_persists_only_progressive_worker_judgment_bound_to_existing_work():
    svc, work_id = _service_with_work()
    result = FastJudgmentService(svc).record(
        work_id=work_id,
        actor_id="worker-1",
        purpose="pch relevance hint",
        source="heuristic",
        context_refs=["artifact:A", "artifact:A", "ticket:T"],
        decisions=[
            {"name": "relevance", "type": "SCORE", "value": 0.9, "confidence": 0.91, "role": "ACTIVATION"}
        ],
    )
    judgment = result["judgment"]
    assert judgment["persistence_level"] == "PROGRESSIVE"
    assert judgment["epistemic_role"] == "WORKER_JUDGMENT"
    assert judgment["work_id"] == work_id
    assert judgment["context_refs"] == ["artifact:A", "ticket:T"]
    assert judgment["authority"]["may_verify"] is False
    assert FastJudgmentService(svc).status(judgment["entity_id"])["judgment"]["entity_id"] == judgment["entity_id"]


def test_fjd1_record_requires_existing_work_identity():
    svc = MangoMeService(InMemoryStore())
    with pytest.raises(FastJudgmentError):
        FastJudgmentService(svc).record(
            work_id="missing",
            actor_id="worker-1",
            purpose="routing",
            decisions=[{"name": "route", "type": "BOOL", "value": True, "confidence": 0.9}],
        )


def test_fjd1_collection_participates_in_maintenance_schema_scans():
    assert "fast_judgments" in MangoMaintainer.COLLECTIONS
