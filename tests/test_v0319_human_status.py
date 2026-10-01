from __future__ import annotations

from pathlib import Path

import mangome.human_status as human_status
from mangome.contract_control import ContractGovernedMangoMeService
from mangome.service import workspace_project_key
from mangome.storage.memory import InMemoryStore
from mangome.structural import StructuralIntelligence


def _bind_human_status(monkeypatch, svc, root: Path) -> None:
    monkeypatch.setattr(human_status, "get_service", lambda: svc)
    monkeypatch.setattr(
        human_status,
        "health_snapshot",
        lambda: {"ok": True, "database_ready": True, "version": "0.3.19"},
    )
    monkeypatch.setattr(
        human_status,
        "workspace_attachment_snapshot",
        lambda: {"workspace_root": str(root.resolve())},
    )


def test_human_status_does_not_trigger_structural_scan(tmp_path: Path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text("def demo():\n    return 1\n", encoding="utf-8")
    StructuralIntelligence.reset_cache_for_tests()
    svc = ContractGovernedMangoMeService(InMemoryStore())
    _bind_human_status(monkeypatch, svc, tmp_path)

    result = human_status.human_status_snapshot(str(tmp_path))

    assert result["scan_performed"] is False
    assert result["canonical_mutations"] == 0
    assert "DISCOVERY   UNINDEXED · 0 indexed files · no scan triggered" in result["rendered"]
    assert StructuralIntelligence(tmp_path).structural_status()["status"] == "UNINDEXED"


def test_human_status_reuses_existing_ast_cache_at_folder_level(tmp_path: Path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "demo.py").write_text("def demo():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
    StructuralIntelligence.reset_cache_for_tests()
    StructuralIntelligence(tmp_path).structural_search("demo")
    svc = ContractGovernedMangoMeService(InMemoryStore())
    _bind_human_status(monkeypatch, svc, tmp_path)

    result = human_status.human_status_snapshot(str(tmp_path))

    assert result["scan_performed"] is False
    assert "DISCOVERY   EXACT · 2 indexed files · no scan triggered" in result["rendered"]
    assert "src/  1 files" in result["rendered"]
    assert "tests/  1 files" in result["rendered"]


def test_human_status_reports_contract_current_then_drifted_without_exposing_hash(tmp_path: Path, monkeypatch):
    contract_dir = tmp_path / "contracts"
    contract_dir.mkdir()
    contract_path = contract_dir / "C-STATUS.md"
    canonical = "# Contract\nRequirement A\n"
    contract_path.write_text(canonical, encoding="utf-8")

    svc = ContractGovernedMangoMeService(InMemoryStore())
    project = svc.create_project(workspace_project_key(str(tmp_path.resolve())), "Demo")
    family = svc.create_family("F-STATUS", "Status family", project_ids=[project["entity_id"]])
    contract = svc.register_contract(
        declared_id="C-STATUS",
        family_id=family["entity_id"],
        title="Status contract",
        actor_id="author",
        storage_system="filesystem",
        physical_location=str(contract_path),
    )
    bound = svc.bind_turn(
        request_text="Create canonical content",
        mode="MODIFY",
        actor_id="author",
        contract_ref=contract["entity_id"],
    )
    svc.promote_contract_generation(
        contract_ref=contract["entity_id"],
        turn_id=bound["turn"]["entity_id"],
        grant_id=bound["generation_grant"]["entity_id"],
        actor_id="author",
        content=canonical,
        change_type="INITIAL",
        source_binding={"storage_system": "filesystem", "physical_location": str(contract_path)},
    )
    StructuralIntelligence.reset_cache_for_tests()
    StructuralIntelligence(tmp_path).structural_search("Contract")
    _bind_human_status(monkeypatch, svc, tmp_path)

    current = human_status.human_status_snapshot(str(tmp_path))
    assert "CONTRACTS   1 known · 1 local · 1 canonical · 1 current" in current["rendered"]
    assert "contracts/" in current["rendered"]
    assert "1 contracts" in current["rendered"]
    assert "content_hash" not in current["rendered"]
    assert contract["entity_id"] not in current["rendered"]

    contract_path.write_text("# Contract\nRequirement A changed\n", encoding="utf-8")
    drifted = human_status.human_status_snapshot(str(tmp_path))
    assert "1 drifted" in drifted["rendered"]
    assert "content_hash" not in drifted["rendered"]
