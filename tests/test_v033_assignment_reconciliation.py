from __future__ import annotations

from pathlib import Path

from mangome.reconciliation import assignment_reconciliation_result


def test_rae1_state_found_reconciles_existing_work():
    restored = {"restore_state": "STATE_FOUND", "families": [{"family_id": "F-1"}]}
    result = assignment_reconciliation_result(restored, workspace_root="/workspace/demo")

    assert result["reconciliation_protocol"] == "RAE/1"
    assert result["rule"] == "THINK_FREELY_RECONCILE_BEFORE_EFFECT"
    assert result["disposition"] == "RECONCILE_WITH_EXISTING_WORK"
    assert result["tentative_worker_decomposition_allowed"] is True
    assert result["canonicalization_allowed_by_this_call"] is False
    assert result["productive_effect_allowed_by_this_call"] is False
    assert result["canonical_state"] is restored


def test_rae1_state_partial_requires_bounded_recovery():
    result = assignment_reconciliation_result(
        {"restore_state": "STATE_PARTIAL", "reason_codes": ["MISSING"]},
        workspace_root="/workspace/demo",
    )
    assert result["disposition"] == "BOUNDED_RECOVERY_REQUIRED"
    assert result["productive_effect_allowed_by_this_call"] is False


def test_rae1_state_not_found_never_manufactures_restore():
    restored = {"restore_state": "STATE_NOT_FOUND", "reason_codes": ["RESTORE_STATE_NOT_FOUND"]}
    result = assignment_reconciliation_result(restored, workspace_root="/workspace/demo")
    assert result["disposition"] == "NEW_OR_UNADMITTED_WORK"
    assert result["request_is_canonical_truth"] is False
    assert result["canonical_state"] == restored


def test_skill_teaches_reconcile_before_effect_not_restore_first():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")

    assert "THINK FREELY" in skill
    assert "RECONCILE BEFORE EFFECT" in skill
    assert "reconcile_assignment" in skill
    assert "Do **not** perform a ritual restore merely because a chat/session started" in skill
    assert "**Restore first.**" not in skill
    assert "before repository exploration, planning or execution" not in skill


def test_managed_gate_source_uses_lazy_restore_after_fast_binding():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mangome" / "mcp_server.py").read_text(encoding="utf-8")
    assert 'os.environ.get("MANGOME_AUTO_ATTACH"' in source
    assert "get_service()" in source
    assert "restore_workspace_state" in source
    assert "SESSION_RECONCILIATION_REQUIRED" in source
    assert "session_restore merely because a session started" in source
