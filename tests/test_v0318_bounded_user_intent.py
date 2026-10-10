from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from mangome import mcp_server
from mangome.runtime import reset_service_for_tests, set_session_restore_snapshot


def _prepare(monkeypatch, workspace) -> None:
    # The workspace must exist (bind_workspace_read_only fails closed otherwise);
    # a fixed /workspace/demo path only existed on one development machine.
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_REQUIRE_SESSION_RESTORE", "1")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(workspace))
    reset_service_for_tests()
    set_session_restore_snapshot({"restore_state": "STATE_FOUND"})


def test_existing_workspace_current_user_intent_can_enter_execute_without_controller(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)

    result = mcp_server.enter_work(
        actor_id="worker-current-user",
        request_text="Implement the explicitly requested bounded task",
        acceptance_criteria=["bounded task is observable"],
        expected_artifacts=["result.txt"],
    )

    assert result.get("ok") is not False
    assert result["turn"]["mode"] == "EXECUTE"
    assert result["turn"]["actor_id"] == "worker-current-user"
    assert result["turn"]["authorized_by"] == "USER_INTENT_RELAYED_BY_CLIENT"


def test_bounded_user_intent_does_not_mint_privileged_turn(monkeypatch, tmp_path):
    _prepare(monkeypatch, tmp_path)

    admitted = mcp_server.enter_work(
        actor_id="worker-current-user",
        request_text="Implement another bounded task",
    )

    denied = mcp_server.bind_work_turn(
        work_ref=admitted["work_identity"]["entity_id"],
        request_text="Verify the task",
        mode="VERIFY",
        actor_id="worker-current-user",
        controller_actor_id=None,
        controller_token=None,
    )

    assert denied["ok"] is False
    assert denied["error"]["code"] == "CONTROL_PLANE_CAPABILITY_REQUIRED"
