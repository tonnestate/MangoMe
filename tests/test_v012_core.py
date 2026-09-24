from __future__ import annotations

import os

import pytest

from mangome.importer import BigBangReconciler, BigBangScanner
from mangome.maintenance import MangoMaintainer
from mangome.service import InvalidTransition, MangoMeService, RevisionConflict
from mangome.storage.memory import InMemoryStore


def test_revision_compare_and_swap_detects_stale_write():
    store = InMemoryStore()
    svc = MangoMeService(store)
    family = svc.create_family("REV", "Revision")
    original = svc.store.get("families", family["entity_id"])
    svc._update("families", family["entity_id"], {"title": "Changed"}, expected_revision=original["revision"])
    with pytest.raises(RevisionConflict):
        svc._update("families", family["entity_id"], {"title": "Stale"}, expected_revision=original["revision"])


def test_effective_family_view_respects_supersedes_and_conflicts():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("EF", "Effective")
    base = svc.register_contract(declared_id="EF-001", family_id=family["entity_id"], title="Base")
    add = svc.register_contract(declared_id="EF-002", family_id=family["entity_id"], title="Addition", kind="ADDITION")
    replacement = svc.register_contract(declared_id="EF-003", family_id=family["entity_id"], title="Replacement", kind="AMENDMENT")
    svc.link(from_type="CONTRACT", from_id=replacement["entity_id"], relation="SUPERSEDES", to_type="CONTRACT", to_id=base["entity_id"])
    svc.link(from_type="CONTRACT", from_id=add["entity_id"], relation="CONFLICTS_WITH", to_type="CONTRACT", to_id=replacement["entity_id"])
    view = svc.effective_family_view(family["entity_id"])
    assert base["entity_id"] not in view["effective_contract_ids"]
    assert replacement["entity_id"] in view["effective_contract_ids"]
    assert view["is_conflicted"] is True
    assert "CONTRACT_CONFLICT" in svc.status(family["entity_id"])["warnings"]


def test_graph_relations_validate_endpoint_types_and_family():
    svc = MangoMeService(InMemoryStore())
    f1 = svc.create_family("F1", "F1")
    f2 = svc.create_family("F2", "F2")
    c1 = svc.register_contract(declared_id="C-1", family_id=f1["entity_id"], title="C1")
    c2 = svc.register_contract(declared_id="C-2", family_id=f2["entity_id"], title="C2")
    with pytest.raises(ValueError):
        svc.link(from_type="CONTRACT", from_id=c1["entity_id"], relation="AMENDS", to_type="CONTRACT", to_id=c2["entity_id"])
    with pytest.raises(ValueError):
        svc.link(from_type="FAMILY", from_id=f1["entity_id"], relation="AMENDS", to_type="FAMILY", to_id=f2["entity_id"])


def test_project_overview_aggregates_families():
    svc = MangoMeService(InMemoryStore())
    project = svc.create_project("P", "Project")
    f1 = svc.create_family("P-A", "A", [project["entity_id"]])
    f2 = svc.create_family("P-B", "B", [project["entity_id"]])
    svc.register_contract(declared_id="A-1", family_id=f1["entity_id"], title="A")
    svc.register_contract(declared_id="B-1", family_id=f2["entity_id"], title="B")
    overview = svc.project_overview("P")
    assert overview["family_count"] == 2
    assert overview["contract_count"] == 2


def test_dependency_can_require_verification():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("DEP", "Dependencies")
    contract = svc.register_contract(declared_id="DEP-1", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(request_text="work", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Work", contract_ids=[contract["entity_id"]])
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"], actor_id="a", intent="two",
        proposed_slices=[
            {"declared_id": "S1", "title": "One"},
            {"declared_id": "S2", "title": "Two", "dependencies": [{"declared_id": "S1", "required_level": "VERIFIED"}]},
        ],
    )
    slices = {s["declared_id"]: s for s in svc.store.find("slices", {"family_id": family["entity_id"]})}
    svc.start_slice(slice_id=slices["S1"]["entity_id"], actor_id="a", plan_id=plan["entity_id"])
    svc.claim_done(slice_id=slices["S1"]["entity_id"], actor_id="a", plan_id=plan["entity_id"])
    assert slices["S2"]["entity_id"] not in svc.status(family["entity_id"])["next_known_slice_ids"]
    fresh = svc.store.get("slices", slices["S1"]["entity_id"])
    svc._update("slices", fresh["entity_id"], {"assurance_state": "VERIFIED", "verified_at": fresh["updated_at"]}, expected_revision=fresh["revision"])
    assert slices["S2"]["entity_id"] in svc.status(family["entity_id"])["next_known_slice_ids"]


def test_schema_migration_upgrades_v1_documents():
    store = InMemoryStore()
    svc = MangoMeService(store)
    family = svc.create_family("MIG", "Migration")
    # simulate an old persisted document directly
    store._data["families"][family["entity_id"]].pop("revision", None)
    store._data["families"][family["entity_id"]]["schema_version"] = 1
    report = MangoMaintainer(svc).migrate_schema(dry_run=True)
    assert report["changed"] >= 1
    report = MangoMaintainer(svc).migrate_schema(dry_run=False)
    assert report["persisted"] >= 1
    migrated = svc.store.get("families", family["entity_id"])
    assert migrated["schema_version"] == 3
    assert "revision" in migrated


def test_bigbang_generic_id_and_reconciliation(tmp_path):
    p = tmp_path / "AURORA-ENGINE-004.md"
    p.write_text("# AURORA-ENGINE-004 Contract\n\n## Slice 2 - Runtime\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("AURORA-ENGINE", "Aurora Engine")
    contract = svc.register_contract(declared_id="AURORA-ENGINE-004", family_id=family["entity_id"], title="Contract")
    records = BigBangScanner(svc).scan([str(tmp_path)])
    assert "AURORA-ENGINE-004" in records[0].declared_ids
    reconciled = BigBangReconciler(svc).reconcile(records)
    assert reconciled["matched"][0]["match"]["contract_id"] == contract["entity_id"]
    assert reconciled["canonical_mutations"] == 0


def test_health_reports_schema_and_backend():
    svc = MangoMeService(InMemoryStore())
    health = svc.health()
    assert health["ok"] is True
    assert health["schema_version"] == 3
    assert health["store"]["backend"] == "memory"


def test_existing_family_can_gain_project_and_scope_contexts():
    svc = MangoMeService(InMemoryStore())
    p1 = svc.create_project("P1", "One")
    p2 = svc.create_project("P2", "Two")
    family = svc.create_family("SHARED", "Shared", [p1["entity_id"]], ["AVCOS"])
    same = svc.create_family("SHARED", "Shared", [p2["entity_id"]], ["TONNESTATE"])
    assert same["entity_id"] == family["entity_id"]
    assert set(same["project_ids"]) == {p1["entity_id"], p2["entity_id"]}
    assert set(same["scope_ids"]) == {"AVCOS", "TONNESTATE"}
    assert family["entity_id"] in svc.store.get("projects", p2["entity_id"])["family_ids"]
