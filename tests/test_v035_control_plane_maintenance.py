from __future__ import annotations

import importlib
import sys
import types

import pytest

from mangome.control_plane import (
    control_plane_maintenance_result,
    database_changes_explicitly_disallowed,
    is_mangome_self_maintenance_request,
)

def _load_mcp_server_without_sdk():
    """Load the module with a tiny MCPServer stub when the optional SDK is absent."""
    try:
        return importlib.import_module("mangome.mcp_server")
    except ModuleNotFoundError as exc:
        if exc.name != "mcp":
            raise
    server_mod = types.ModuleType("mcp.server")
    mcp_mod = types.ModuleType("mcp")

    class MCPServer:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self, *args, **kwargs):
            def decorate(fn):
                return fn
            return decorate

        def run(self, *args, **kwargs):
            raise AssertionError("stub MCP server must not run")

    server_mod.MCPServer = MCPServer
    mcp_mod.server = server_mod
    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.server"] = server_mod
    try:
        return importlib.import_module("mangome.mcp_server")
    finally:
        sys.modules.pop("mcp.server", None)
        sys.modules.pop("mcp", None)


def test_explicit_mangome_self_maintenance_is_narrowly_detected():
    assert is_mangome_self_maintenance_request(
        "Aktualisiere MangoMe direkt aus GitHub, aber verändere die Datenbank nicht."
    )
    assert is_mangome_self_maintenance_request("Install the MangoMe hotfix from main.")
    assert is_mangome_self_maintenance_request(
        "Aktualisiere die Daten direkt aus dem GitHub repo", target="MangoMe"
    )
    assert not is_mangome_self_maintenance_request("MangoMe läuft")
    assert not is_mangome_self_maintenance_request("Nutze MangoMe für diesen Auftrag")
    assert not is_mangome_self_maintenance_request("Update the TonnEstate dashboard")


def test_explicit_no_database_change_constraint_is_detected():
    assert database_changes_explicitly_disallowed(
        "Aktualisiere MangoMe, aber die Datenbank nicht ändern"
    )
    assert database_changes_explicitly_disallowed(
        "Update MangoMe; do not touch the database"
    )


def test_cpm1_is_read_only_out_of_band_and_never_self_admits():
    result = control_plane_maintenance_result(
        "Aktualisiere MangoMe aus GitHub, Datenbank nicht verändern",
        workspace_root="/srv/work",
    )
    assert result["reconciliation_protocol"] == "CPM/1"
    assert result["out_of_band_control_plane_maintenance"] is True
    assert result["project_work_admission_required"] is False
    assert result["enter_work_required"] is False
    assert result["work_identity_required"] is False
    assert result["database_write_allowed_by_this_disposition"] is False
    assert result["database_changes_explicitly_disallowed"] is True
    assert "DATABASE_CHANGE_REQUIRED" in result["next_action"]


def test_reconcile_assignment_short_circuits_restore_for_self_maintenance(monkeypatch, tmp_path):
    mcp_server = _load_mcp_server_without_sdk()
    monkeypatch.setattr(
        mcp_server,
        "workspace_attachment_snapshot",
        lambda: {"workspace_root": str(tmp_path)},
    )

    def explode(_root):
        raise AssertionError("canonical restore must not run before CPM/1 self-maintenance")

    monkeypatch.setattr(mcp_server, "restore_workspace_state", explode)
    result = mcp_server._reconcile_assignment_impl(
        "Bitte MangoMe auf 0.3.5 aktualisieren; die Datenbank nicht verändern."
    )
    assert result["reconciliation_protocol"] == "CPM/1"
    assert result["enter_work_required"] is False


def test_reconcile_assignment_accepts_current_conversation_target_for_elliptical_followup(monkeypatch, tmp_path):
    mcp_server = _load_mcp_server_without_sdk()
    monkeypatch.setattr(
        mcp_server,
        "workspace_attachment_snapshot",
        lambda: {"workspace_root": str(tmp_path)},
    )

    def explode(_root):
        raise AssertionError("CPM/1 follow-up must not enter canonical restore")

    monkeypatch.setattr(mcp_server, "restore_workspace_state", explode)
    result = mcp_server._reconcile_assignment_impl(
        "Aktualisiere die Daten direkt aus dem GitHub repo, aber verändere die Datenbank nicht",
        target="MangoMe",
    )
    assert result["reconciliation_protocol"] == "CPM/1"
    assert result["database_changes_explicitly_disallowed"] is True


def test_normal_assignment_still_uses_canonical_reconciliation(monkeypatch, tmp_path):
    mcp_server = _load_mcp_server_without_sdk()
    monkeypatch.setattr(
        mcp_server,
        "workspace_attachment_snapshot",
        lambda: {"workspace_root": str(tmp_path)},
    )
    seen = {"restore": 0}

    def restore(_root):
        seen["restore"] += 1
        return {"restore_state": "STATE_NOT_FOUND"}

    monkeypatch.setattr(mcp_server, "restore_workspace_state", restore)
    result = mcp_server._reconcile_assignment_impl("Fix the dashboard bug")
    assert seen["restore"] == 1
    assert result["reconciliation_protocol"] == "RAE/1"
