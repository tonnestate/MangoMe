from __future__ import annotations

from pathlib import Path

import mangome.runtime as runtime
from mangome.reconciliation import assignment_reconciliation_result


def test_read_only_binding_is_volatile_and_does_not_scan(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_AUTO_ATTACH", "1")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    runtime.reset_service_for_tests()

    monkeypatch.setattr(runtime, "attach_workspace", lambda *a, **k: (_ for _ in ()).throw(AssertionError("full attach called")))

    service = runtime.get_service()
    attachment = runtime.workspace_attachment_snapshot()

    assert attachment is not None
    assert attachment["workspace_root"] == str(tmp_path.resolve())
    assert attachment["binding_mode"] == "READ_ONLY_FAST_PATH"
    assert attachment["discovery_deferred"] is True
    assert runtime.session_restore_snapshot() is None
    assert service.store.find("filesystem_roots") == []


def test_restore_unknown_workspace_uses_binding_without_discovery(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.delenv("MANGOME_AUTO_ATTACH", raising=False)
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    runtime.reset_service_for_tests()

    monkeypatch.setattr(runtime, "attach_workspace", lambda *a, **k: (_ for _ in ()).throw(AssertionError("full attach called")))
    result = runtime.restore_workspace_state(str(tmp_path))

    assert result["restore_state"] == "STATE_NOT_FOUND"
    assert runtime.workspace_attachment_snapshot()["binding_mode"] == "READ_ONLY_FAST_PATH"
    assert runtime.get_service().store.find("filesystem_roots") == []


def test_reconcile_result_can_follow_fast_restore_without_discovery(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.delenv("MANGOME_AUTO_ATTACH", raising=False)
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    runtime.reset_service_for_tests()

    monkeypatch.setattr(runtime, "attach_workspace", lambda *a, **k: (_ for _ in ()).throw(AssertionError("full attach called")))
    restored = runtime.restore_workspace_state(str(tmp_path))
    result = assignment_reconciliation_result(restored, workspace_root=str(tmp_path.resolve()))

    assert result["reconciliation_protocol"] == "RAE/1"
    assert result["restore_state"] == "STATE_NOT_FOUND"
    assert result["productive_effect_allowed_by_this_call"] is False
    assert runtime.workspace_attachment_snapshot()["binding_mode"] == "READ_ONLY_FAST_PATH"
