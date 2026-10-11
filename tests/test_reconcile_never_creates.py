"""HANDOVER-002 A1: RECONCILE_ASSIGNMENT finds existing work or reports CONFLICT; it never writes."""
from __future__ import annotations

import pytest

import mangome.runtime as runtime
import mangome.worker_mcp_server as worker


@pytest.fixture()
def svc(monkeypatch, tmp_path):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    for k in ("MANGOME_EXPECTED_VERSION", "MANGOME_EXPECTED_SOURCE_ROOT", "MANGOME_REQUIRE_SESSION_RESTORE"):
        monkeypatch.delenv(k, raising=False)
    runtime.reset_service_for_tests()
    yield runtime.get_service()
    runtime.reset_service_for_tests()


def docs(svc) -> dict[str, int]:
    return {c: len(rows) for c, rows in svc.store._data.items()}


def reconcile(text, **extra):
    return worker.mangome_work("RECONCILE_ASSIGNMENT", {"request_text": text, **extra})


def test_no_match_is_conflict_and_writes_nothing(svc):
    before = docs(svc)
    out = reconcile("FruitStack Forschungsauftrag fortsetzen")
    assert out["disposition"] == "CONFLICT" and "NO_MATCH" in out["reason_codes"]
    assert out["result"]["reason"] == "NO_MATCH" and out["result"]["search_criteria"]["admission_key"]
    assert docs(svc) == before


def test_regression_acceptance_call_creates_no_documents(svc):
    reconcile("seed")  # first call, as in the acceptance run
    before = docs(svc)
    reconcile("FruitStack Forschungsauftrag fortsetzen", target="FruitStack")
    assert docs(svc) == before


def test_matched_returns_existing_id_and_is_idempotent(svc):
    entered = worker.mangome_work("ENTER_WORK", {"request_text": "Evidence Test"})
    assert entered["ok"] is True
    before = docs(svc)
    first = reconcile("Evidence Test.")
    second = reconcile("Evidence Test.")
    assert first["disposition"] == "MATCHED" and first["result"]["work_ref"]
    assert first["result"]["work_ref"] == second["result"]["work_ref"]
    assert docs(svc) == before


def test_ambiguous_lists_all_candidates_and_writes_nothing(svc, monkeypatch):
    cands = [{"family_id": f"F{i}", "work_ref": f"W{i}", "work_key": None, "admission_key": "k"} for i in (1, 2)]
    monkeypatch.setattr(svc, "work_candidate_for_request",
                        lambda **kw: {"state": "AMBIGUOUS", "admission_key": "k", "fingerprint": "x", "candidates": cands})
    before = docs(svc)
    out = reconcile("anything")
    assert out["disposition"] == "CONFLICT" and "AMBIGUOUS" in out["reason_codes"]
    assert out["result"]["candidate_ids"] == ["W1", "W2"] and docs(svc) == before


def test_db_unavailable_is_retriable_error_class(svc, monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError

    def boom(**kw):
        raise ServerSelectionTimeoutError("down")

    monkeypatch.setattr(svc, "work_candidate_for_request", boom)
    out = reconcile("anything")
    assert out["ok"] is False
    err = out["result"]["error"]
    assert err["error_class"] == "DB_UNAVAILABLE" and err["retriable"] is True
