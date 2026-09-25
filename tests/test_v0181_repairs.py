from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

import mangome.operability as operability
import mangome.runtime as runtime
from mangome.integrity import IntegrityMangoMeService
from mangome.interlingua import InterlinguaError, decode_uai_result
from mangome.maintenance import MangoMaintainer
from mangome.service import InvalidTransition, MangoMeService
from mangome.storage.memory import InMemoryStore


VERIFIER_TOKEN = "verify-secret"
APPROVAL_TOKEN = "owner-secret"


def _configure_caps(monkeypatch):
    monkeypatch.setenv("MANGOME_VERIFIER_TOKEN", VERIFIER_TOKEN)
    monkeypatch.setenv("MANGOME_VERIFIER_ACTORS", "verifier-b")
    monkeypatch.setenv("MANGOME_APPROVAL_TOKEN", APPROVAL_TOKEN)
    monkeypatch.setenv("MANGOME_APPROVER_ACTORS", "human-owner")


def _gateless_done_slice(monkeypatch):
    _configure_caps(monkeypatch)
    svc = IntegrityMangoMeService(InMemoryStore())
    family = svc.create_family("REPAIR", "Repair family")
    contract = svc.register_contract(
        declared_id="REPAIR-1", family_id=family["entity_id"], title="Repair contract"
    )
    spec = svc.create_spec(
        family_id=family["entity_id"], objective="Repair evaluated defect",
        contract_ids=[contract["entity_id"]],
    )
    result = svc.begin_work(
        family_id=family["entity_id"], actor_id="worker-a",
        request_text="repair the evaluated defect", intent="repair defect",
        proposed_slice={"title": "Repair defect"},
    )
    sl = result["slice"]
    svc.claim_done(
        slice_id=sl["entity_id"], actor_id="worker-a", plan_id=result["plan"]["entity_id"],
        summary="done",
    )
    obs = svc.submit_verification_observation(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
        claim="repair check passes", observation_type="SPEC_CHECK", status="PASS",
        evidence_type="repair-check", evidence_class="TEST_RESULT", source="verifier",
    )
    return svc, family, spec, sl, obs


def test_imported_assurance_is_preserved_as_claim_but_never_authoritative():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("IMPORT", "Import")
    sl = svc.import_slice(
        family_id=family["entity_id"], declared_id="LEGACY-1", title="Legacy",
        execution_state="DONE_CLAIMED", assurance_state="ACCEPTED",
    )
    assert sl["assurance_state"] == "UNVERIFIED"
    assert sl["imported_assurance_state"] == "ACCEPTED"


def test_begin_work_generates_stable_declared_id_when_worker_omits_it():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("ZERO", "Zero touch")
    contract = svc.register_contract(declared_id="ZERO-1", family_id=family["entity_id"], title="Contract")
    svc.create_spec(family_id=family["entity_id"], objective="Do ordinary work", contract_ids=[contract["entity_id"]])
    result = svc.begin_work(
        family_id=family["entity_id"], actor_id="worker-a",
        request_text="Fix the login test", intent="Fix login",
        proposed_slice={"title": "Fix login"},
    )
    assert result["slice"]["declared_id"].startswith("AUTO-")
    assert result["plan"]["proposed_slices"][0]["declared_id"] == result["slice"]["declared_id"]


def test_verification_provenance_is_atomic_with_verified_slice(monkeypatch):
    svc, _, _, sl, obs = _gateless_done_slice(monkeypatch)
    verified = svc.verify_slice(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
        evidence_ids=[obs["entity_id"]],
    )
    assert verified["assurance_state"] == "VERIFIED"
    assert verified["verified_by"] == "verifier-b"
    assert verified["verification_evidence_ids"] == [obs["entity_id"]]
    assert verified["verification_observation_ids"] == [obs["entity_id"]]
    assert verified["verification_profile"] == "AV/1"


def test_accepted_slice_cannot_be_reverified_or_downgraded(monkeypatch):
    svc, _, _, sl, obs = _gateless_done_slice(monkeypatch)
    svc.verify_slice(
        slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
        evidence_ids=[obs["entity_id"]],
    )
    approval = svc.request_override(
        action_type="ACCEPT_SLICE", subject_id=sl["entity_id"], requested_by="verifier-b", reason="accept"
    )
    approval = svc.approve_override(
        approval_id=approval["entity_id"], decided_by="human-owner", approval_token=APPROVAL_TOKEN
    )
    accepted = svc.accept_slice(slice_id=sl["entity_id"], approval_id=approval["entity_id"])
    assert accepted["assurance_state"] == "ACCEPTED"
    with pytest.raises(InvalidTransition, match="current assurance is ACCEPTED"):
        svc.verify_slice(
            slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=VERIFIER_TOKEN,
            evidence_ids=[obs["entity_id"]],
        )
    assert svc.store.get("slices", sl["entity_id"])["assurance_state"] == "ACCEPTED"


def test_uai_result_requires_expected_context_hash():
    payload = {"v": "UAI/1R", "h": "0" * 64, "st": "SUCCESS", "a": []}
    with pytest.raises(InterlinguaError, match="expected_context_hash is required"):
        decode_uai_result(payload)


def test_maintenance_accepts_naive_mongodb_style_datetimes():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("MAINT", "Maintenance")
    contract = svc.register_contract(declared_id="MAINT-1", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(request_text="work", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="work", contract_ids=[contract["entity_id"]])
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"],
        actor_id="worker", intent="work", proposed_slices=[{"title": "Work"}],
    )
    svc.store.update(
        "plans", plan["entity_id"],
        {"updated_at": datetime.now() - timedelta(days=2)},
    )
    result = MangoMaintainer(svc).diagnose(stale_after_hours=24)
    assert any(item["plan_id"] == plan["entity_id"] for item in result["stale_plan_candidates"])


def test_refresh_preserves_first_attach_from_get_service(tmp_path: Path, monkeypatch):
    (tmp_path / "README.md").write_text("# Workspace\n", encoding="utf-8")
    runtime.reset_service_for_tests()
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("MANGOME_AUTO_ATTACH", "1")
    monkeypatch.setenv("MANGOME_EXPECTED_VERSION", "0.1.8.1")
    result = runtime.refresh_workspace_attachment(str(tmp_path))
    assert result["first_attach"] is True
    runtime.reset_service_for_tests()


def test_claude_attestation_does_not_treat_pending_approval_as_ready(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    operability.configure_claude_code(
        str(tmp_path), backend="memory", database="mangome_test", home=str(home), scope="project"
    )

    class Result:
        stdout = "mangome: python -m mangome.mcp_server - Pending approval"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(operability.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(operability.subprocess, "run", lambda *a, **k: Result())
    attested = operability.attest_client(
        "claude-code", str(tmp_path), backend="memory", database="mangome_test",
        home=str(home), check_client=True, claude_scope="project",
    )
    assert attested["status"] == "CLIENT_READINESS_FAILED"
    assert "CONFIGURATION_NOT_EFFECTIVE" in attested["reasons"]
    assert "PROJECT_MCP_APPROVAL_REQUIRED" in attested["reasons"]


def test_installation_identity_preserves_venv_symlink_path(tmp_path: Path, monkeypatch):
    real = tmp_path / "python-real"
    real.write_text("", encoding="utf-8")
    link = tmp_path / "venv-python"
    link.symlink_to(real)
    monkeypatch.setattr(operability.sys, "executable", str(link))
    identity = operability.installation_identity()
    assert identity["python"] == str(link.absolute())
    assert identity["python"] != str(real.resolve())


def test_enter_work_turns_current_user_intent_into_governed_work_without_discovery_admission():
    svc = MangoMeService(InMemoryStore())
    result = svc.enter_work(
        workspace_id="/tmp/example-workspace",
        workspace_title="Example",
        actor_id="worker-a",
        request_text="Fix the login timeout",
        intent="Fix login timeout",
        acceptance_criteria=["login timeout test passes"],
        expected_scope=["src/auth"],
    )

    assert result["authority"] == "USER_INTENT_RELAYED_BY_CLIENT"
    assert result["discovery_promoted"] is False
    assert result["truth_level"] == "CANONICAL_UNVERIFIED"
    assert result["spec"]["objective"] == "Fix the login timeout"
    assert result["work"]["plan"]["actor_id"] == "worker-a"
    assert result["work"]["slice"]["active_plan_id"] == result["work"]["plan"]["entity_id"]
    assert result["work"]["slice"]["execution_state"] in {"STARTED", "ACTIVE"}
    assert svc.store.find("contracts") == []


def test_family_status_exposes_truth_level_without_new_assurance_state():
    svc = MangoMeService(InMemoryStore())
    result = svc.enter_work(
        workspace_id="/tmp/truth-level",
        workspace_title="Truth",
        actor_id="worker-a",
        request_text="Do bounded work",
        intent="Do bounded work",
    )
    family_id = result["family"]["entity_id"]
    status = svc.status(family_id)
    assert status["truth_level"] == "CANONICAL_UNVERIFIED"

    sl = result["work"]["slice"]
    plan = result["work"]["plan"]
    svc.claim_done(
        slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"], summary="done"
    )
    assert svc.status(family_id)["truth_level"] == "CLAIMED"


def test_claude_attestation_requires_connected_not_name_visibility(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    operability.configure_claude_code(
        str(tmp_path), backend="memory", database="mangome_test", home=str(home), scope="local"
    )

    class Result:
        stdout = "mangome: configured"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(operability.shutil, "which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr(operability.subprocess, "run", lambda *a, **k: Result())
    attested = operability.attest_client(
        "claude-code", str(tmp_path), backend="memory", database="mangome_test",
        home=str(home), check_client=True, claude_scope="local",
    )
    assert attested["status"] == "CLIENT_READINESS_FAILED"
    assert attested["client_check"]["connection_state"] == "VISIBLE_UNCONFIRMED"
    assert "CONFIGURATION_NOT_EFFECTIVE" in attested["reasons"]


def test_schema_v4_adds_verification_fields_without_inventing_provenance():
    from mangome.schema import upgrade_document

    upgraded, changes = upgrade_document(
        "slices",
        {
            "entity_id": "SLICE-OLD",
            "schema_version": 3,
            "assurance_state": "VERIFIED",
        },
    )
    assert upgraded["schema_version"] == 4
    assert upgraded["verification_evidence_ids"] == []
    assert upgraded["verification_observation_ids"] == []
    assert upgraded["verified_by"] is None
    assert "schema 3 -> 4" in changes


def test_explicit_workspace_refresh_rechecks_known_workspace(tmp_path: Path, monkeypatch):
    (tmp_path / "README.md").write_text("# Workspace\n", encoding="utf-8")
    runtime.reset_service_for_tests()
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("MANGOME_AUTO_ATTACH", "1")
    monkeypatch.setenv("MANGOME_EXPECTED_VERSION", "0.1.8.1")
    first = runtime.refresh_workspace_attachment(str(tmp_path))
    assert first["first_attach"] is True
    second = runtime.refresh_workspace_attachment(str(tmp_path), force=True)
    assert second["first_attach"] is False
    runtime.reset_service_for_tests()


def test_enter_work_keeps_unrelated_user_tasks_in_separate_families():
    svc = MangoMeService(InMemoryStore())
    first = svc.enter_work(
        workspace_id="/tmp/project", workspace_title="Project", actor_id="worker-a",
        request_text="Fix login timeout", intent="Fix login timeout",
    )
    second = svc.enter_work(
        workspace_id="/tmp/project", workspace_title="Project", actor_id="worker-b",
        request_text="Add export button", intent="Add export button",
    )
    assert first["project"]["entity_id"] == second["project"]["entity_id"]
    assert first["family"]["entity_id"] != second["family"]["entity_id"]
    assert len(svc.project_overview(first["project"]["entity_id"])["families"]) == 2
