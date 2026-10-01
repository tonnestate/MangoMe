from __future__ import annotations

from mangome import mcp_server
from mangome.runtime import reset_service_for_tests, set_session_restore_snapshot


def test_existing_workspace_current_user_intent_can_enter_execute_without_controller(monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_REQUIRE_SESSION_RESTORE", "1")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", "/workspace/demo")
    reset_service_for_tests()

    # Simulate an already-known workspace. v0.3.17 blocked ENTER_WORK here unless
    # a separate CONTROL capability was supplied by the host.
    set_session_restore_snapshot({"restore_state": "STATE_FOUND"})

    result = mcp_server.enter_work(
        actor_id="worker-current-user",
        request_text="Implement the explicitly requested bounded task",
        acceptance_criteria=["bounded task is observable"],
        expected_artifacts=["result.txt"],
    )

    assert result.get("ok") is not False
    assert result["authority"] == "USER_INTENT_RELAYED_BY_CLIENT"
    assert result["work"]["turn"]["mode"] == "EXECUTE"
    assert result["work"]["turn"]["actor_id"] == "worker-current-user"
    assert result["work"]["turn"]["authorized_by"] == "USER_INTENT_RELAYED_BY_CLIENT"


def test_user_intent_does_not_mint_verify_authority(monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_REQUIRE_SESSION_RESTORE", "1")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", "/workspace/demo")
    reset_service_for_tests()
    set_session_restore_snapshot({"restore_state": "STATE_FOUND"})

    admitted = mcp_server.enter_work(
        actor_id="worker-current-user",
        request_text="Implement another bounded task",
    )
    work_id = admitted["work_identity"]["entity_id"]

    denied = mcp_server.bind_work_turn(
        work_ref=work_id,
        request_text="Verify the task",
        mode="VERIFY",
        actor_id="worker-current-user",
        controller_actor_id=None,
        controller_token=None,
    )

    assert denied["ok"] is False
    assert denied["error"]["code"] == "CONTROL_PLANE_CAPABILITY_REQUIRED"
