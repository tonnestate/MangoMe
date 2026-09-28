from __future__ import annotations

from pathlib import Path

import mangome.runtime as runtime
from mangome.operability import configure_codex
from mangome.work_control import WorkGovernedMangoMeService
from mangome.storage.memory import InMemoryStore


def _admit(service: WorkGovernedMangoMeService, workspace: Path, actor: str = "worker") -> None:
    service.enter_work(
        workspace_id=str(workspace.resolve()),
        workspace_title=workspace.name,
        actor_id=actor,
        request_text=f"Maintain {workspace.name}",
    )


def test_codex_skill_is_user_scoped_and_does_not_require_saved_project(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    result = configure_codex(str(workspace), backend="memory", database="mangome_test", home=str(home))

    skill = home / ".codex" / "skills" / "mangome" / "SKILL.md"
    assert skill.is_file()
    assert result["skill_path"] == str(skill)
    assert result["skill_scope"] == "user"


def test_restore_rebinds_from_child_cwd_to_canonical_workspace(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "project"
    child = workspace / "src"
    child.mkdir(parents=True)
    service = WorkGovernedMangoMeService(InMemoryStore())
    _admit(service, workspace)

    runtime.reset_service_for_tests()
    monkeypatch.setattr(runtime, "get_service", lambda: service)
    runtime.ensure_workspace_binding(str(child))
    restored = runtime.restore_workspace_state(str(child))

    assert restored["restore_state"] == "STATE_FOUND"
    assert restored["workspace_resolution"]["state"] == "CANONICAL_REBOUND"
    assert restored["workspace_resolution"]["resolved_workspace_root"] == str(workspace.resolve())
    assert restored["database_binding"]["state"] == "BOUND"
    runtime.reset_service_for_tests()


def test_restore_rebinds_broad_cwd_only_when_single_canonical_descendant(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "project"
    workspace.mkdir()
    service = WorkGovernedMangoMeService(InMemoryStore())
    _admit(service, workspace)

    runtime.reset_service_for_tests()
    monkeypatch.setattr(runtime, "get_service", lambda: service)
    runtime.ensure_workspace_binding(str(tmp_path))
    restored = runtime.restore_workspace_state(str(tmp_path))

    assert restored["restore_state"] == "STATE_FOUND"
    assert restored["workspace_resolution"]["state"] == "CANONICAL_REBOUND"
    assert restored["workspace_resolution"]["resolved_workspace_root"] == str(workspace.resolve())
    runtime.reset_service_for_tests()


def test_restore_refuses_to_guess_between_multiple_projects(tmp_path: Path, monkeypatch):
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir(); two.mkdir()
    service = WorkGovernedMangoMeService(InMemoryStore())
    _admit(service, one, "worker-1")
    _admit(service, two, "worker-2")

    runtime.reset_service_for_tests()
    monkeypatch.setattr(runtime, "get_service", lambda: service)
    runtime.ensure_workspace_binding(str(tmp_path))
    restored = runtime.restore_workspace_state(str(tmp_path))

    assert restored["restore_state"] == "STATE_PARTIAL"
    assert restored["reason_codes"] == ["WORKSPACE_BINDING_AMBIGUOUS"]
    assert restored["workspace_resolution"]["state"] == "AMBIGUOUS"
    assert restored["workspace_resolution"]["candidate_count"] == 2
    runtime.reset_service_for_tests()
