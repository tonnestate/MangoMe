from __future__ import annotations

from pathlib import Path

import mangome.runtime as runtime
from mangome.storage.memory import InMemoryStore
from mangome.work_control import WorkGovernedMangoMeService


def test_skill_routes_observation_away_from_assignment_and_dispatch_gates():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")
    assert len(skill) < 20_000
    assert "Observation-only requests are **not work assignments by themselves**" in skill
    assert "use exactly one bounded candidate discovery call" in skill
    assert "Do not call `execution_eligibility` merely because MangoMe is active" in skill
    assert "`RUNTIME_PROFILE_REQUIRED` means the host/router" in skill
    assert "Do not scan the same path twice" in skill


def test_mcp_source_has_terminal_pure_discovery_surfaces():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mangome" / "mcp_server.py").read_text(encoding="utf-8")
    bigbang = source[source.index("def bigbang_scan("):source.index("def reconcile_bigbang_scan(")]
    assert "BigBangScanner(None" in bigbang
    assert "include_git: bool = False" in bigbang
    assert '"canonical_mutations": 0' in bigbang
    assert 'max_files: int = 10_000' in bigbang
    assert 'max_depth: int = 16' in bigbang
    assert '"scan_limit_reached"' in bigbang
    assert "_discovery_block" not in bigbang
    assert "reconcile_bigbang_scan" in source
    assert "filesystem_inventory" in source
    assert "CANDIDATE_PAYLOAD_TOO_LARGE" in source


def test_codex_managed_surfaces_are_user_scoped_and_portable():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mangome" / "operability.py").read_text(encoding="utf-8")
    assert 'home_path / ".codex" / "config.toml"' in source
    assert 'home_path / ".codex" / "skills" / "mangome" / "SKILL.md"' in source
    assert 'home_path / ".codex" / "AGENTS.md"' in source
    assert "~/.codex/skills/mangome/SKILL.md" in source
    assert "Do not substitute IntakeGov" in source
    assert "invoke `$mangome`" in source
    assert '"config_scope": "user"' in source
    assert 'portable_workspace=True' in source


def test_explicit_restore_workspace_overrides_stale_process_binding(tmp_path: Path, monkeypatch):
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir(); two.mkdir()
    service = WorkGovernedMangoMeService(InMemoryStore())
    service.enter_work(workspace_id=str(two.resolve()), workspace_title="two", actor_id="worker", request_text="Maintain two")

    runtime.reset_service_for_tests()
    monkeypatch.setattr(runtime, "get_service", lambda: service)
    runtime.ensure_workspace_binding(str(one))
    restored = runtime.restore_workspace_state(str(two))
    assert restored["restore_state"] == "STATE_FOUND"
    assert restored["workspace_resolution"]["requested_workspace_root"] == str(two.resolve())
    runtime.reset_service_for_tests()
