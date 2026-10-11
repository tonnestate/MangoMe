"""HANDOVER-002: SUPERSEDE_WORK is a governance-bound control operation; it archives a duplicate WorkIdentity by
reference and never deletes or moves evidence."""
from __future__ import annotations

import pytest

import mangome.runtime as runtime
import mangome.worker_mcp_server as worker
from mangome.service import MangoMeError
from mangome.storage.memory import InMemoryStore
from mangome.work_control import WorkGovernedMangoMeService

TOKEN = "controller-test-token-0123456789"


def svc_with(*texts, workspace="/w"):
    svc = WorkGovernedMangoMeService(InMemoryStore())
    works = [svc.enter_work(workspace_id=workspace, workspace_title="w", actor_id="a", request_text=t)["work_identity"]["entity_id"] for t in texts]
    return svc, works


def snapshot(svc):
    return {c: [(d["entity_id"], d.get("revision")) for d in rows.values()] for c, rows in svc.store._data.items() if c not in {"assurance_events", "work_identities", "work_views"}}


def test_supersede_marks_old_work_and_keeps_everything_else():
    svc, (canonical, dup) = svc_with("canonical research", "duplicate research")
    before = snapshot(svc)
    out = svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="auto-admitted duplicate")
    old = svc.store.get("work_identities", dup)
    assert old["status"] == "SUPERSEDED" and old["superseded_by"] == canonical and old["supersede_reason"] == "auto-admitted duplicate"
    assert svc.store.get("work_identities", canonical)["status"] != "SUPERSEDED"
    assert out["disposition"] == "WORK_SUPERSEDED"
    assert snapshot(svc) == before  # evidence, slices, plans, claims untouched; nothing deleted or moved
    events = [e for e in svc.store.find("assurance_events") if e["event_type"] == "WORK_SUPERSEDED"]
    assert len(events) == 1 and events[0]["payload"]["superseded_by"] == canonical


def test_supersede_is_idempotent():
    svc, (canonical, dup) = svc_with("a", "b")
    first = svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="dup")
    second = svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="dup")
    assert second["disposition"] == "ALREADY_SUPERSEDED" and first["work"]["entity_id"] == second["work"]["entity_id"]
    assert len([e for e in svc.store.find("assurance_events") if e["event_type"] == "WORK_SUPERSEDED"]) == 1


@pytest.mark.parametrize("case", ["self", "empty_reason", "unknown", "canonical_superseded", "other_target", "other_project"])
def test_supersede_rejects_invalid_requests_without_writing(case):
    svc, (a, b, c) = svc_with("a", "b", "c")
    svc.supersede_work(superseded_ref=c, canonical_ref=a, actor_id="owner", reason="dup")
    other_project = svc.enter_work(workspace_id="/other", workspace_title="o", actor_id="a", request_text="x")["work_identity"]["entity_id"]
    args = {"self": dict(superseded_ref=b, canonical_ref=b, reason="r"), "empty_reason": dict(superseded_ref=b, canonical_ref=a, reason="  "),
            "unknown": dict(superseded_ref=b, canonical_ref="nope", reason="r"), "canonical_superseded": dict(superseded_ref=b, canonical_ref=c, reason="r"),
            "other_target": dict(superseded_ref=c, canonical_ref=b, reason="r"), "other_project": dict(superseded_ref=b, canonical_ref=other_project, reason="r")}[case]
    before = {k: dict(v) for k, v in svc.store._data["work_identities"].items()}
    with pytest.raises((MangoMeError, KeyError)):
        svc.supersede_work(actor_id="owner", **args)
    assert {k: dict(v) for k, v in svc.store._data["work_identities"].items()} == before


def test_reconcile_follows_a_superseded_identity_to_the_canonical_one():
    svc, (canonical, dup) = svc_with("canonical research", "duplicate research")
    svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="dup")
    match = svc.work_candidate_for_request(workspace_id="/w", request_text="duplicate research")
    assert match["state"] == "EXACT_NORMALIZED_MATCH" and match["candidate"]["work_ref"] == canonical


@pytest.fixture()
def runtime_svc(monkeypatch, tmp_path):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("MANGOME_CONTROLLER_TOKEN", TOKEN)
    monkeypatch.setenv("MANGOME_CONTROLLER_ACTORS", "host-controller")
    for k in ("MANGOME_EXPECTED_VERSION", "MANGOME_EXPECTED_SOURCE_ROOT", "MANGOME_REQUIRE_SESSION_RESTORE"):
        monkeypatch.delenv(k, raising=False)
    runtime.reset_service_for_tests()
    yield runtime.get_service()
    runtime.reset_service_for_tests()


def test_worker_control_operation_requires_the_controller_capability(runtime_svc):
    ids = [worker.mangome_work("ENTER_WORK", {"request_text": t})["result"]["work_identity"]["entity_id"] for t in ("canonical", "duplicate")]
    payload = {"superseded_ref": ids[1], "canonical_ref": ids[0], "reason": "dup"}
    denied = worker.mangome_control("SUPERSEDE_WORK", {**payload, "controller_actor_id": "worker:managed-local"})
    assert denied["ok"] is False and runtime_svc.store.get("work_identities", ids[1])["status"] != "SUPERSEDED"
    ok = worker.mangome_control("SUPERSEDE_WORK", {**payload, "controller_actor_id": "host-controller", "controller_token": TOKEN})
    assert ok["ok"] is True and runtime_svc.store.get("work_identities", ids[1])["superseded_by"] == ids[0]
