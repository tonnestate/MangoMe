from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from mangome.authority import CapabilityDenied, require_verifier
from mangome.models import Family, Project, Slice
from mangome.service import MangoMeService, _dump, workspace_project_key
from mangome.storage.memory import InMemoryStore
from mangome.trust_boundary import resolve_mongodb_connection
from mangome.work_control import WorkGovernedMangoMeService


def test_inmemory_store_enforces_domain_unique_keys():
    store = InMemoryStore()
    p1 = _dump(Project(project_key="P", title="one"))
    p2 = _dump(Project(project_key="P", title="two"))
    store.insert("projects", p1)
    with pytest.raises(ValueError, match="duplicate unique key projects"):
        store.insert("projects", p2)

    f1 = _dump(Family(family_key="F1", title="one", admission_key="A"))
    f2 = _dump(Family(family_key="F2", title="two", admission_key="A"))
    store.insert("families", f1)
    with pytest.raises(ValueError, match="duplicate unique key families"):
        store.insert("families", f2)

    s1 = _dump(Slice(declared_id="S", family_id=f1["entity_id"], title="one"))
    s2 = _dump(Slice(declared_id="S", family_id=f1["entity_id"], title="two"))
    store.insert("slices", s1)
    with pytest.raises(ValueError, match="duplicate unique key slices"):
        store.insert("slices", s2)


def test_atomic_get_or_create_returns_one_identity():
    store = InMemoryStore()
    d1 = _dump(Project(project_key="P", title="one"))
    d2 = _dump(Project(project_key="P", title="two"))
    first, created_first = store.get_or_create("projects", {"project_key": "P"}, d1)
    second, created_second = store.get_or_create("projects", {"project_key": "P"}, d2)
    assert created_first is True
    assert created_second is False
    assert first["entity_id"] == second["entity_id"]
    assert len(store.find("projects")) == 1


def test_concurrent_enter_work_keeps_one_project_family_work_and_active_slice():
    barrier = Barrier(2)

    class RacingService(WorkGovernedMangoMeService):
        def create_family(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            family = super().create_family(*args, **kwargs)
            barrier.wait(timeout=5)
            return family

    svc = RacingService(InMemoryStore())

    def enter(actor: str):
        return svc.enter_work(
            workspace_id="/tmp/mangome-v0320-race",
            workspace_title="race",
            actor_id=actor,
            request_text="Fix the login bug.",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(enter, ["worker-a", "worker-b"]))

    assert len(svc.store.find("projects")) == 1
    assert len(svc.store.find("families")) == 1
    assert len(svc.store.find("work_identities")) == 1
    assert len(svc.store.find("slices")) == 1
    active = [row for row in svc.store.find("slices") if row.get("execution_state") in {"STARTED", "ACTIVE"}]
    assert len(active) == 1
    assert {row["disposition"] for row in results} <= {
        "NEW_WORK_ADMITTED", "EXISTING_WORK_CANDIDATE", "CONCURRENT_WORK_REUSED"
    }


def test_prompt_normalization_is_candidate_hint_not_silent_identity_binding():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    first = svc.enter_work(
        workspace_id="/tmp/mangome-v0320-normalization",
        workspace_title="normalization",
        actor_id="worker-a",
        request_text="Fix the login bug",
    )
    second = svc.enter_work(
        workspace_id="/tmp/mangome-v0320-normalization",
        workspace_title="normalization",
        actor_id="worker-b",
        request_text="  FIX   THE LOGIN BUG.  ",
    )
    assert second["disposition"] == "EXISTING_WORK_CANDIDATE"
    assert second["requires_explicit_work_ref"] is True
    assert second["candidate_work_ref"] == first["work_identity"]["entity_id"]
    assert len(svc.store.find("families")) == 1
    assert len(svc.store.find("work_identities")) == 1


def test_explicit_work_ref_binds_existing_durable_identity():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    first = svc.enter_work(
        workspace_id="/tmp/mangome-v0320-bind",
        workspace_title="bind",
        actor_id="worker-a",
        request_text="Fix the login bug",
    )
    bound = svc.enter_work(
        workspace_id="/tmp/mangome-v0320-bind",
        workspace_title="bind",
        actor_id="worker-b",
        request_text="Continue fixing the login bug",
        work_ref=first["work_identity"]["entity_id"],
    )
    assert bound["work_identity"]["entity_id"] == first["work_identity"]["entity_id"]
    assert bound["family"]["entity_id"] == first["family"]["entity_id"]
    assert bound["project"]["entity_id"] == first["project"]["entity_id"]
    assert len(svc.store.find("work_identities")) == 1


def test_status_is_side_effect_free_when_projection_is_not_materialized():
    store = InMemoryStore()
    svc = MangoMeService(store)
    family = svc.create_family("F-READ", "Read only status")
    before = store.get("families", family["entity_id"])
    assert store.find("project_views", {"family_id": family["entity_id"]}) == []

    one = svc.status(family["entity_id"])
    two = svc.status(family["entity_id"])

    after = store.get("families", family["entity_id"])
    assert before["revision"] == after["revision"]
    assert store.find("project_views", {"family_id": family["entity_id"]}) == []
    assert one["family_id"] == two["family_id"] == family["entity_id"]


def test_workspace_root_is_direct_project_binding():
    svc = MangoMeService(InMemoryStore())
    root = "/tmp/mangome-v0320-root"
    project = svc.create_project(workspace_project_key(root), "root", workspace_root=root)
    assert project["workspace_root"] == root
    assert svc.store.find("projects", {"workspace_root": root})[0]["entity_id"] == project["entity_id"]


def test_full_runtime_role_no_longer_aggregates_privileged_roles(monkeypatch):
    for name in ("MANGOME_VERIFIER_TOKEN", "MANGOME_VERIFIER_ACTORS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MANGOME_RUNTIME_ROLE", "FULL")
    monkeypatch.setenv("MANGOME_RUNTIME_ACTOR", "verifier")
    with pytest.raises(CapabilityDenied):
        require_verifier("verifier")

    monkeypatch.setenv("MANGOME_RUNTIME_ROLE", "VERIFIER")
    require_verifier("verifier")


def test_local_host_trust_boundary_is_explicitly_cooperative(monkeypatch):
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
    monkeypatch.setenv("MANGOME_MONGODB_URI", "mongodb://127.0.0.1:27017")
    monkeypatch.delenv("MANGOME_MONGODB_URI_FILE", raising=False)
    cfg = resolve_mongodb_connection()
    assert cfg.status["verification_boundary"] == "COOPERATIVE_HOST"
    assert cfg.status["tamper_resistant_verification"] is False
    assert cfg.status["authorization_model"] == "COOPERATIVE_HOST_LOCAL"


def test_work_status_does_not_advance_materialized_revisions():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    admitted = svc.enter_work(
        workspace_id="/tmp/mangome-v0320-status", workspace_title="status",
        actor_id="worker", request_text="Fix status race",
    )
    family_id = admitted["family"]["entity_id"]
    before_family = svc.store.get("families", family_id)
    before_view = svc.store.get("project_views", family_id)
    assert before_view is not None
    one = svc.status(family_id)
    two = svc.status(family_id)
    after_family = svc.store.get("families", family_id)
    after_view = svc.store.get("project_views", family_id)
    assert one["family_id"] == two["family_id"] == family_id
    assert after_family["revision"] == before_family["revision"]
    assert after_view["revision"] == before_view["revision"]


def test_discovery_gate_does_not_call_project_overview_or_status():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "src/mangome/mcp_server.py").read_text(encoding="utf-8")
    start = source.index("def _known_admitted_workspace_roots")
    end = source.index("def _overlaps", start)
    body = source[start:end]
    assert "svc.project_overview(" not in body
    assert "svc.status(" not in body
    assert 'store.find("projects")' in body
    assert 'store.find("families")' in body
