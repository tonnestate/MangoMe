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


def edges(svc):
    return [e for e in svc.store.find("edges") if e["relation"] == "SUPERSEDES" and e["from_type"] == "WORK"]


def test_supersede_uses_the_existing_relation_and_adds_no_new_state():
    svc, (canonical, dup) = svc_with("canonical research", "duplicate research")
    work_docs_before = {k: dict(v) for k, v in svc.store._data["work_identities"].items()}
    before = snapshot(svc)
    out = svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="auto-admitted duplicate")
    (edge,) = edges(svc)
    assert (edge["from_id"], edge["to_id"], edge["status"], edge["source_actor_id"], edge["to_type"]) == (dup, canonical, "CONFIRMED", "owner", "WORK")
    assert out["disposition"] == "WORK_SUPERSEDED" and svc.superseding_work_id(dup) == canonical and svc.superseding_work_id(canonical) is None
    # no invented fields: WorkIdentity documents are byte-identical; evidence/slices/plans/claims untouched
    assert {k: dict(v) for k, v in svc.store._data["work_identities"].items()} == work_docs_before
    assert {k: v for k, v in snapshot(svc).items() if k not in {"edges", "work_turn_bindings"}} == {k: v for k, v in before.items() if k not in {"edges", "work_turn_bindings"}}
    events = [e for e in svc.store.find("assurance_events") if e["event_type"] == "WORK_SUPERSEDED"]
    assert len(events) == 1 and events[0]["payload"]["superseded_by"] == canonical


def test_direct_link_requires_a_modify_turn_on_the_superseded_work_for_the_same_actor():
    from mangome.work_control import WorkTurnError
    svc, (canonical, dup) = svc_with("canonical", "duplicate")
    args = dict(from_type="WORK", from_id=dup, relation="SUPERSEDES", to_type="WORK", to_id=canonical, work_id=dup)
    with pytest.raises(WorkTurnError):
        svc.link(**args, source_actor_id="owner", turn_id=None)                      # no turn
    read_turn = svc.bind_work_turn(work_ref=dup, request_text="x", mode="QUERY", actor_id="owner")["turn"]["entity_id"]
    with pytest.raises(WorkTurnError):
        svc.link(**args, source_actor_id="owner", turn_id=read_turn)                  # wrong mode
    modify = svc.bind_work_turn(work_ref=dup, request_text="x", mode="MODIFY", actor_id="owner")["turn"]["entity_id"]
    with pytest.raises(WorkTurnError):
        svc.link(**args, source_actor_id="somebody-else", turn_id=modify)             # turn belongs to another actor
    other_work_turn = svc.bind_work_turn(work_ref=canonical, request_text="x", mode="MODIFY", actor_id="owner")["turn"]["entity_id"]
    with pytest.raises(WorkTurnError):
        svc.link(**args, source_actor_id="owner", turn_id=other_work_turn)            # turn belongs to another work
    assert edges(svc) == []
    svc.link(**args, source_actor_id="owner", turn_id=modify)
    assert len(edges(svc)) == 1


def test_supersede_is_idempotent():
    svc, (canonical, dup) = svc_with("a", "b")
    first = svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="dup")
    second = svc.supersede_work(superseded_ref=dup, canonical_ref=canonical, actor_id="owner", reason="dup")
    assert first["disposition"] == "WORK_SUPERSEDED" and second["disposition"] == "ALREADY_SUPERSEDED"
    assert len(edges(svc)) == 1 and len([e for e in svc.store.find("assurance_events") if e["event_type"] == "WORK_SUPERSEDED"]) == 1


@pytest.mark.parametrize("case", ["self", "empty_reason", "unknown", "canonical_superseded", "other_target", "other_project"])
def test_supersede_rejects_invalid_requests_without_writing(case):
    svc, (a, b, c) = svc_with("a", "b", "c")
    svc.supersede_work(superseded_ref=c, canonical_ref=a, actor_id="owner", reason="dup")
    other_project = svc.enter_work(workspace_id="/other", workspace_title="o", actor_id="a", request_text="x")["work_identity"]["entity_id"]
    args = {"self": dict(superseded_ref=b, canonical_ref=b, reason="r"), "empty_reason": dict(superseded_ref=b, canonical_ref=a, reason="  "),
            "unknown": dict(superseded_ref=b, canonical_ref="nope", reason="r"), "canonical_superseded": dict(superseded_ref=b, canonical_ref=c, reason="r"),
            "other_target": dict(superseded_ref=c, canonical_ref=b, reason="r"), "other_project": dict(superseded_ref=b, canonical_ref=other_project, reason="r")}[case]
    before = len(edges(svc))
    with pytest.raises((MangoMeError, KeyError)):
        svc.supersede_work(actor_id="owner", **args)
    assert len(edges(svc)) == before


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
    assert denied["ok"] is False and runtime_svc.superseding_work_id(ids[1]) is None
    ok = worker.mangome_control("SUPERSEDE_WORK", {**payload, "controller_actor_id": "host-controller", "controller_token": TOKEN})
    assert ok["ok"] is True and runtime_svc.superseding_work_id(ids[1]) == ids[0]
