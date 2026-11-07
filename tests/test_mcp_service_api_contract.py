from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from mangome import mcp_server, worker_mcp_server


class _Service:
    def enter_work(
        self, *, workspace_id, workspace_title, actor_id, request_text, intent=None,
        work_ref=None,
        slice_title=None, slice_objective=None, acceptance_criteria=None,
        required_evidence=None, expected_artifacts=None, expected_scope=None, estimate=None,
    ):
        result = {"operation": "enter_work"}
        if work_ref is not None:
            result["work_ref"] = work_ref
        return result

    def prepare_assignment(
        self, *, family_id, actor_id, request_text, intent=None, classification=None,
        classification_source="MANGOME_ASSIGNMENT_PREP", read_only=False,
        expected_artifacts=None, expected_scope=None, estimate=None,
    ):
        return {"operation": "prepare_assignment"}

    def begin_work(
        self, *, family_id, actor_id, request_text, intent, proposed_slice,
        classification="EXISTING_CONTRACT_WORK", classification_source="IntakeGov",
        spec_id=None, contract_ids=None, expected_artifacts=None, expected_scope=None,
        estimate=None, acceptance_expectations=None,
    ):
        return {"operation": "begin_work"}


@pytest.fixture
def ready_mcp(monkeypatch, tmp_path):
    service = _Service()
    monkeypatch.setattr(mcp_server, "get_service", lambda: service)
    monkeypatch.setattr(mcp_server, "_restore_gate", lambda *args, **kwargs: None)
    monkeypatch.setattr(mcp_server, "_work_identity_gate_family", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        mcp_server, "workspace_attachment_snapshot",
        lambda: {"workspace_root": str(tmp_path)},
    )
    monkeypatch.setattr(mcp_server, "set_session_restore_snapshot", lambda *_: None)
    return service


@pytest.mark.parametrize(
    ("operation", "payload", "field"),
    [
        ("PREPARE_ASSIGNMENT", {"family_id": "F-1", "actor_id": "worker", "request_text": "task", "work_id": "W-1"}, "work_id"),
        ("PREPARE_ASSIGNMENT", {"family_id": "F-1", "actor_id": "worker", "request_text": "task", "turn_id": "T-1"}, "turn_id"),
        ("BEGIN_WORK", {"family_id": "F-1", "actor_id": "worker", "request_text": "task", "intent": "task", "work_id": "W-1"}, "work_id"),
        ("BEGIN_WORK", {"family_id": "F-1", "actor_id": "worker", "request_text": "task", "intent": "task", "turn_id": "T-1"}, "turn_id"),
    ],
)
def test_worker_rejects_unsupported_service_fields_before_call(ready_mcp, operation, payload, field):
    result = worker_mcp_server._call_allowlisted(worker_mcp_server._WORK, operation, payload)

    assert result["error"]["code"] == "INVALID_CAPABILITY_ARGUMENTS"
    assert f"'{field}'" in result["error"]["message"]


@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        ("ENTER_WORK", {"actor_id": "worker", "request_text": "task"}),
        ("PREPARE_ASSIGNMENT", {"family_id": "F-1", "actor_id": "worker", "request_text": "task"}),
        ("BEGIN_WORK", {"family_id": "F-1", "actor_id": "worker", "request_text": "task", "intent": "task"}),
    ],
)
def test_worker_calls_service_with_current_service_contract(ready_mcp, operation, payload):
    result = worker_mcp_server._call_allowlisted(worker_mcp_server._WORK, operation, payload)

    assert result == {"operation": operation.lower()}


def test_worker_continues_existing_work_identity(ready_mcp):
    result = worker_mcp_server._call_allowlisted(
        worker_mcp_server._WORK,
        "ENTER_WORK",
        {"actor_id": "worker", "request_text": "continue task", "work_ref": "W-1"},
    )

    assert result == {"operation": "enter_work", "work_ref": "W-1"}
