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


def test_semantic_reconcile_auto_admits_new_current_user_work(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_call(_table, operation: str, payload: dict):
        calls.append((operation, dict(payload)))
        if operation == "RECONCILE_ASSIGNMENT":
            return {
                "disposition": "NEW_WORK_READY_FOR_AUTO_ADMISSION",
                "requires_user_confirmation": False,
            }
        if operation == "ENTER_WORK":
            return {
                "disposition": "NEW_WORK_ADMITTED",
                "work": {"slice": {"execution_state": "ACTIVE"}},
            }
        raise AssertionError(operation)

    monkeypatch.setattr(worker, "_call_allowlisted", fake_call)
    monkeypatch.delenv("MANGOME_RUNTIME_ACTOR", raising=False)
    monkeypatch.setenv("MANGOME_DEPLOYMENT_ID", "managed-local")

    result = worker.mangome_work(
        "RECONCILE_ASSIGNMENT",
        {"request_text": "Repair the Fruit stack"},
    )

    assert result["disposition"] == "NEW_WORK_AUTO_ADMITTED"
    assert result["recommended_next_action"] == "EXECUTE_CURRENT_SLICE"
    assert "ASK_USER_FOR_WORK_REF" in result["forbidden_next_actions"]
    assert calls[1][0] == "ENTER_WORK"
    assert calls[1][1]["actor_id"] == "worker:managed-local"
    assert calls[1][1]["request_text"] == "Repair the Fruit stack"


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
