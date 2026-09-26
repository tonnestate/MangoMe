from __future__ import annotations

import json
import os

import pytest

from mangome.context import ContextBudgetExceeded, ContextCompiler
from mangome.enums import ExecutionState
from mangome.schema import UnsupportedSchemaVersion, upgrade_document
from mangome.service import InvalidTransition, MangoMeService
from mangome.storage.memory import InMemoryStore


def _family_with_spec(svc: MangoMeService):
    project = svc.create_project("P-V022", "v0.2.2")
    family = svc.create_family("F-V022", "v0.2.2 family", project_ids=[project["entity_id"]])
    spec = svc.create_spec(
        family_id=family["entity_id"],
        objective="Keep implementation aligned with observed reality",
        acceptance_criteria=["Observed implementation satisfies the requirement"],
        required_evidence=["runtime/static observation"],
    )
    return family, spec


def test_prepare_assignment_reuses_existing_slices_without_creating_new():
    svc = MangoMeService(InMemoryStore())
    family, spec = _family_with_spec(svc)
    first = svc.begin_work(
        family_id=family["entity_id"], actor_id="worker-a", request_text="Implement baseline",
        intent="Implement baseline", proposed_slice={"declared_id": "S1", "title": "Existing", "objective": "Existing"},
        spec_id=spec["entity_id"],
    )
    before = svc.store.find("slices", {"family_id": family["entity_id"]})
    # Make the existing Slice non-active so assignment preparation can bind a new Plan without duplicating it.
    svc.claim_done(slice_id=first["slice"]["entity_id"], actor_id="worker-a", plan_id=first["plan"]["entity_id"])
    result = svc.prepare_assignment(
        family_id=family["entity_id"], actor_id="auditor", request_text="Audit the current implementation",
    )
    after = svc.store.find("slices", {"family_id": family["entity_id"]})
    assert result["slice_action"] == "REUSED_EXISTING"
    assert result["slice_count_before"] == result["slice_count_after"] == 1
    assert len(before) == len(after) == 1
    assert result["presentation_policy"]["slices"] == "INTERNAL_ONLY"


def test_prepare_assignment_materializes_one_internal_slice_when_none_exist():
    svc = MangoMeService(InMemoryStore())
    family, _ = _family_with_spec(svc)
    result = svc.prepare_assignment(
        family_id=family["entity_id"], actor_id="auditor", request_text="Audit the current implementation",
    )
    slices = svc.store.find("slices", {"family_id": family["entity_id"]})
    assert result["slice_action"] == "MATERIALIZED_INTERNAL"
    assert result["slice_count_before"] == 0
    assert result["slice_count_after"] == 1
    assert len(slices) == 1
    assert slices[0]["execution_state"] == ExecutionState.ACTIVE.value


def test_audit_cannot_claim_done_from_planning_or_prose_without_evidence():
    svc = MangoMeService(InMemoryStore())
    family, _ = _family_with_spec(svc)
    result = svc.prepare_assignment(
        family_id=family["entity_id"], actor_id="auditor", request_text="Audit the current implementation",
    )
    target = result["targets"][0]
    with pytest.raises(InvalidTransition, match="AUDIT_RESULT_EVIDENCE_REQUIRED"):
        svc.claim_done(
            slice_id=target["entity_id"], actor_id="auditor", plan_id=result["plan"]["entity_id"],
            summary="I wrote an audit plan instead of auditing",
        )
    svc.submit_evidence(
        subject_id=target["entity_id"], evidence_type="STATIC_CHECK", evidence_class="STATIC_ANALYSIS",
        source="auditor", result="PASS", actor_id="auditor", payload={"observed": "actual code inspected"},
    )
    done = svc.claim_done(
        slice_id=target["entity_id"], actor_id="auditor", plan_id=result["plan"]["entity_id"],
        summary="Audit executed and evidence persisted",
    )
    assert done["execution_state"] == "DONE_CLAIMED"


def test_context_budget_bounds_execution_projection_but_not_canonical_truth():
    svc = MangoMeService(InMemoryStore())
    family, _ = _family_with_spec(svc)
    prepared = svc.prepare_assignment(
        family_id=family["entity_id"], actor_id="auditor", request_text="Audit current implementation",
    )
    sid = prepared["targets"][0]["entity_id"]
    for i in range(20):
        svc.submit_evidence(
            subject_id=sid, evidence_type=f"OBS-{i}", evidence_class="STATIC_ANALYSIS", source="audit",
            result="PASS", actor_id="auditor", payload={"bulk": "x" * 1500, "i": i},
        )
    full = ContextCompiler(svc).compile(family["entity_id"], sid)
    bounded = ContextCompiler(svc).compile(family["entity_id"], sid, max_bytes=7000)
    assert "context_budget" not in full
    assert bounded["context_budget"]["max_bytes"] == 7000
    assert bounded["context_budget"]["truncated"] is True
    assert bounded["context_budget"]["omitted_evidence"] > 0
    assert len(json.dumps(bounded, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8")) <= 7000
    assert bounded["current_spec"] == full["current_spec"]
    assert bounded["current_slice"] == full["current_slice"]


def test_future_schema_fails_closed():
    with pytest.raises(UnsupportedSchemaVersion):
        upgrade_document("slices", {"entity_id": "future", "schema_version": 999})


def test_context_budget_fails_closed_if_mandatory_projection_is_too_large():
    svc = MangoMeService(InMemoryStore())
    family, _ = _family_with_spec(svc)
    prepared = svc.prepare_assignment(
        family_id=family["entity_id"], actor_id="auditor", request_text="Audit current implementation",
    )
    sid = prepared["targets"][0]["entity_id"]
    with pytest.raises(ContextBudgetExceeded):
        ContextCompiler(svc).compile(family["entity_id"], sid, max_bytes=100)


def test_release_layout_has_no_root_shadow_modules():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    forbidden = {
        "__init__.py", "context.py", "mcp_server.py", "mongo.py", "operability.py",
        "runtime.py", "schema.py", "service.py", "SKILL.md", "SKILL (1).md",
    }
    present = sorted(name for name in forbidden if (root / name).exists())
    assert present == [], f"repository-root shadow files are forbidden: {present}"


def test_release_version_surfaces_are_consistent():
    from pathlib import Path
    import re
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    expected = project["project"]["version"]
    init_text = (root / "src/mangome/__init__.py").read_text(encoding="utf-8")
    server_text = (root / "src/mangome/mcp_server.py").read_text(encoding="utf-8")
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    server_match = re.search(r'\bversion\s*=\s*"([^"]+)"', server_text)
    assert init_match and init_match.group(1) == expected
    assert server_match and server_match.group(1) == expected
    assert expected == "0.2.2"


def test_mangome_runtime_does_not_manage_host_network_configuration():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (root / "src/mangome").rglob("*.py")
    ).lower()
    forbidden = (
        "/etc/resolv.conf", "systemd-resolved", "resolvectl", "netplan",
        "iptables", "nftables", "ufw ",
    )
    hits = [token for token in forbidden if token in source]
    assert hits == [], f"host network/resolver management is outside MangoMe runtime scope: {hits}"
