from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mangome.operability import attach_workspace
from mangome.service import MangoMeService, workspace_project_key
from mangome.storage.memory import InMemoryStore


def test_restore_not_found_does_not_create_replacement_state(tmp_path: Path):
    svc = MangoMeService(InMemoryStore())
    key = workspace_project_key(str(tmp_path))
    result = svc.session_restore(key)
    assert result["restore_state"] == "STATE_NOT_FOUND"
    assert result["productive_execution_allowed"] is False
    assert result["reason_codes"] == ["RESTORE_STATE_NOT_FOUND"]
    assert svc.store.find("projects") == []
    assert svc.store.find("families") == []
    assert svc.store.find("specs") == []


def test_blocked_existing_work_is_found_but_not_execution_permission(tmp_path: Path):
    svc = MangoMeService(InMemoryStore())
    work = svc.enter_work(
        workspace_id=str(tmp_path), workspace_title="Demo", actor_id="worker-a",
        request_text="Continue durable work", acceptance_criteria=["runtime effect observed"],
    )
    slice_id = work["work"]["slice"]["entity_id"]
    plan_id = work["work"]["plan"]["entity_id"]
    svc.update_slice_progress(
        slice_id=slice_id, actor_id="worker-a", plan_id=plan_id,
        blocker="upstream dependency", execution_state="BLOCKED",
    )
    restored = svc.session_restore(workspace_project_key(str(tmp_path)))
    assert restored["restore_state"] == "STATE_FOUND"
    assert restored["productive_execution_allowed"] is False
    assert restored["next_executable_items"] == []
    assert "UNFINISHED_INTENT_DOES_NOT_GRANT_EXECUTION" in restored["execution_rule"]


def test_portable_multi_root_discovery_and_repository_locations(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    contracts = tmp_path / "contracts"
    repos = tmp_path / "ai-chaos"
    workspace.mkdir(); contracts.mkdir(); repos.mkdir()
    (contracts / "LOG-006.md").write_text("# Contract LOG-006\nAcceptance criteria\n", encoding="utf-8")
    repo = repos / "repair-copy"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "README.md").write_text("repair workspace\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)

    monkeypatch.setenv("MANGOME_DISCOVERY_SCOPES_JSON", json.dumps([
        {"role": "CONTRACT_SOURCE", "location": str(contracts)},
        {"role": "REPOSITORY_SEARCH", "location": str(repos)},
    ]))
    svc = MangoMeService(InMemoryStore())
    attached = attach_workspace(svc, str(workspace), include_git=True)
    roles = {row["role"] for row in attached["discovery_scopes"]}
    assert {"WORKSPACE", "CONTRACT_SOURCE", "REPOSITORY_SEARCH"}.issubset(roles)
    assert any(row["path"] == str(repo.resolve()) for row in attached["repository_locations"])
    # Discovery stores references/metadata, not arbitrary file bodies.
    artifacts = svc.store.find("artifacts")
    assert any(a.get("physical_location") == str((contracts / "LOG-006.md").resolve()) for a in artifacts)
    assert all("content" not in a for a in artifacts)


def test_agent_private_context_is_not_inventory_truth(tmp_path: Path):
    workspace = tmp_path / "workspace"; workspace.mkdir()
    private = workspace / ".claude" / "projects"; private.mkdir(parents=True)
    (private / "MEMORY.md").write_text("agent-only context", encoding="utf-8")
    (workspace / "README.md").write_text("normal project file", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    attach_workspace(svc, str(workspace), include_git=False)
    paths = [str(row.get("path") or "") for row in svc.store.find("filesystem_entries")]
    assert any(path.endswith("README.md") for path in paths)
    assert not any("/.claude/" in path for path in paths)
