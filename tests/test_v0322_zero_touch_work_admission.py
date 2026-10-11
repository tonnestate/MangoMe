from __future__ import annotations

from mangome.storage.memory import InMemoryStore
from mangome.work_control import WorkGovernedMangoMeService
import mangome.worker_mcp_server as worker


def test_unrelated_workspace_work_does_not_match_current_request():
    service = WorkGovernedMangoMeService(InMemoryStore())
    service.enter_work(
        workspace_id="/root",
        workspace_title="root",
        actor_id="worker:test",
        request_text="Evidence Test",
    )

    unrelated = service.work_candidate_for_request(
        workspace_id="/root",
        request_text="Repair the Fruit stack PlumMe adapter path",
    )
    same = service.work_candidate_for_request(
        workspace_id="/root",
        request_text="Evidence Test.",
    )

    assert unrelated["state"] == "NONE"
    assert same["state"] == "EXACT_NORMALIZED_MATCH"


def test_semantic_reconcile_never_admits_new_work(monkeypatch):
    """HANDOVER-002 A1 supersedes v0.3.22 auto-admission: no match => CONFLICT, ENTER_WORK is not called."""
    calls: list[str] = []

    def fake_call(_table, operation: str, payload: dict):
        calls.append(operation)
        return {"disposition": "CONFLICT", "reason": "NO_MATCH", "search_criteria": {}}

    monkeypatch.setattr(worker, "_call_allowlisted", fake_call)
    result = worker.mangome_work("RECONCILE_ASSIGNMENT", {"request_text": "Repair the Fruit stack"})

    assert result["disposition"] == "CONFLICT" and result["ok"] is False
    assert calls == ["RECONCILE_ASSIGNMENT"]


def test_direct_enter_work_gets_managed_worker_actor(monkeypatch):
    seen: dict = {}

    def fake_call(_table, operation: str, payload: dict):
        seen.update(payload)
        return {"disposition": "NEW_WORK_ADMITTED"}

    monkeypatch.setattr(worker, "_call_allowlisted", fake_call)
    monkeypatch.delenv("MANGOME_RUNTIME_ACTOR", raising=False)
    monkeypatch.setenv("MANGOME_DEPLOYMENT_ID", "managed-local")

    result = worker.mangome_work(
        "ENTER_WORK",
        {"request_text": "Do the task"},
    )

    assert result["ok"] is True
    assert seen["actor_id"] == "worker:managed-local"
