from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

import mangome.runtime as runtime
from mangome import __version__
from mangome.operability import (
    OperabilityError,
    attach_workspace,
    attest_client,
    configure_claude_code,
    configure_codex,
    enforce_expected_identity,
)
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def test_unknown_workspace_auto_attaches_once_without_inventing_contract_truth(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "PROJECT-001.md").write_text(
        "# PROJECT-001 Contract\n\n## Slice 1 - Discovery\n", encoding="utf-8"
    )
    svc = MangoMeService(InMemoryStore())

    first = attach_workspace(svc, str(tmp_path), include_git=False)
    second = attach_workspace(svc, str(tmp_path), include_git=False)

    assert first["first_attach"] is True
    assert first["discovery"]["record_count"] >= 1
    assert first["discovery"]["canonical_mutations"] == 0
    assert second["first_attach"] is False
    assert second["discovery"] is None
    assert svc.store.find("contracts") == []
    assert svc.store.find("filesystem_roots")[0]["root_path"] == str(tmp_path.resolve())


def test_claude_code_setup_defaults_to_local_scope_and_preserves_other_servers(tmp_path: Path):
    existing = {
        "mcpServers": {
            "other": {"command": "other-mcp"},
            "mangome_old": {"command": "/opt/mangome-lab/.venv/bin/mangome-mcp"},
        },
        "keep": True,
    }
    (tmp_path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")

    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").write_text(
        json.dumps({"mcpServers": {"mangome_old": {"command": "/old/mangome-mcp"}}}), encoding="utf-8"
    )
    result = configure_claude_code(
        str(tmp_path), backend="memory", database="mangome_test", home=str(home)
    )

    assert result["scope"] == "local"
    project_config = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert project_config["mcpServers"]["other"]["command"] == "other-mcp"
    assert "mangome" not in project_config["mcpServers"]
    assert "mangome_old" not in project_config["mcpServers"]
    assert project_config["keep"] is True

    local_config = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    assert local_config.get("mcpServers", {}) == {}
    server = local_config["projects"][str(tmp_path.resolve())]["mcpServers"]["mangome"]
    assert server["type"] == "stdio"
    assert server["args"] == ["-m", "mangome.mcp_server"]
    assert server["env"]["MANGOME_AUTO_ATTACH"] == "1"
    assert server["env"]["MANGOME_WORKSPACE_ROOT"] == str(tmp_path.resolve())

    skill = tmp_path / ".claude" / "skills" / "mangome" / "SKILL.md"
    assert skill.is_file()
    rule = tmp_path / ".claude" / "rules" / "mangome.md"
    assert rule.is_file()
    rule_text = rule.read_text(encoding="utf-8")
    assert "Zero-touch applies to the user interface" in rule_text
    assert "AUTHORITATIVE RECOVERY RULE" in rule_text
    assert "NEVER reconstruct current work state" in rule_text
    assert "MangoMe is infrastructure" in rule_text
    assert "STATE_NOT_FOUND" in rule_text

    attested = attest_client(
        "claude-code", str(tmp_path), backend="memory", database="mangome_test",
        home=str(home), check_client=False,
    )
    assert attested["status"] == "STATIC_PASS"
    assert attested["reasons"] == []


def test_claude_code_project_scope_remains_explicit_opt_in(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    result = configure_claude_code(
        str(tmp_path), backend="memory", database="mangome_test", home=str(home), scope="project"
    )
    config = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert result["scope"] == "project"
    assert config["mcpServers"]["mangome"]["args"] == ["-m", "mangome.mcp_server"]
    attested = attest_client(
        "claude-code", str(tmp_path), backend="memory", database="mangome_test",
        home=str(home), check_client=False, claude_scope="project",
    )
    assert attested["status"] == "STATIC_PASS"


def test_codex_setup_is_project_scoped_idempotent_and_preserves_unrelated_toml(tmp_path: Path):
    config = tmp_path / ".codex" / "config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        'model = "example"\n\n[features]\nfoo = true\n\n'
        '[mcp_servers.mangome_old]\ncommand = "/old/mangome-mcp"\n',
        encoding="utf-8",
    )

    home = tmp_path / "home"
    user_config = home / ".codex" / "config.toml"
    user_config.parent.mkdir(parents=True)
    user_config.write_text(
        '[mcp_servers.mangome_eval]\ncommand = "/opt/mangome-lab/.venv/bin/mangome-mcp"\n',
        encoding="utf-8",
    )
    first = configure_codex(
        str(tmp_path), backend="memory", database="mangome_test", home=str(home)
    )
    configure_codex(str(tmp_path), backend="memory", database="mangome_test", home=str(home))

    assert set(first["removed_shadow_entries"]) == {
        "mcp_servers.mangome_eval",
        f"{config}:mcp_servers.mangome_old",
    }
    assert "mangome_eval" not in user_config.read_text(encoding="utf-8")
    raw = config.read_text(encoding="utf-8")
    parsed = tomllib.loads(raw)
    assert parsed["model"] == "example"
    assert parsed["features"]["foo"] is True
    assert raw.count("[mcp_servers.mangome]") == 1
    assert "mangome_old" not in raw
    server = parsed["mcp_servers"]["mangome"]
    assert server["args"] == ["-m", "mangome.mcp_server"]
    assert server["env"]["MANGOME_AUTO_ATTACH"] == "1"
    agents = tmp_path / "AGENTS.md"
    assert agents.is_file()
    assert agents.read_text(encoding="utf-8").count("BEGIN MANGOME ZERO-TOUCH") == 1

    attested = attest_client(
        "codex", str(tmp_path), backend="memory", database="mangome_test",
        home=str(home), check_client=False,
    )
    assert attested["status"] == "STATIC_PASS"
    assert attested["reasons"] == []


def test_managed_instructions_preserve_existing_project_instructions(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / "AGENTS.md").write_text("# Existing\n\nKeep this.\n", encoding="utf-8")
    configure_codex(str(tmp_path), backend="memory", database="mangome_test", home=str(home))
    configure_codex(str(tmp_path), backend="memory", database="mangome_test", home=str(home))
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "# Existing" in text
    assert "Keep this." in text
    assert text.count("BEGIN MANGOME ZERO-TOUCH") == 1


def test_expected_version_mismatch_fails_closed(monkeypatch):
    monkeypatch.setenv("MANGOME_EXPECTED_VERSION", "999.0")
    with pytest.raises(OperabilityError) as exc:
        enforce_expected_identity()
    assert exc.value.code == "WRONG_MANGOME_VERSION"


def test_runtime_auto_attach_uses_managed_workspace_without_user_bigbang_command(tmp_path: Path, monkeypatch):
    (tmp_path / "README.md").write_text("# Workspace\n", encoding="utf-8")
    runtime.reset_service_for_tests()
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("MANGOME_AUTO_ATTACH", "1")
    monkeypatch.setenv("MANGOME_EXPECTED_VERSION", __version__)

    svc = runtime.get_service()
    attachment = runtime.workspace_attachment_snapshot()

    assert svc.store.find("filesystem_roots")
    assert attachment is not None
    assert attachment["workspace_root"] == str(tmp_path.resolve())
    assert attachment["first_attach"] is True
    runtime.reset_service_for_tests()
