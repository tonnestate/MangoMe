from __future__ import annotations

import pytest

from mangome.audit import ScopedAuditError, ScopedAuditService
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def _fixture():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("AUDIT", "Scoped Recursive Audit")
    contract = svc.register_contract(
        declared_id="AUDIT-C1", family_id=family["entity_id"], title="Audit contract"
    )
    spec = svc.create_spec(
        family_id=family["entity_id"], objective="Keep the audit target correct",
        contract_ids=[contract["entity_id"]], acceptance_criteria=["target remains correct"],
    )
    request = svc.intake_request(
        request_text="Review the target", classification="VERIFICATION", family_id=family["entity_id"]
    )
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=request["entity_id"], spec_id=spec["entity_id"],
        actor_id="auditor", intent="review target", contract_ids=[contract["entity_id"]],
        proposed_slices=[{"declared_id": "AUDIT-S1", "title": "Review target"}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    artifact = svc.attach_artifact(
        logical_name="target.py", artifact_type="CODE", storage_system="FILESYSTEM",
        physical_location="/repo/target.py", belongs_to=[sl["entity_id"]], checksum="abc",
    )
    svc.link(
        from_type="SLICE", from_id=sl["entity_id"], relation="IMPLEMENTS",
        to_type="ARTIFACT", to_id=artifact["entity_id"], status="CONFIRMED",
    )
    return svc, family, plan, sl, artifact


def test_recursive_audit_expands_only_after_material_impact_and_reaches_fixpoint():
    svc, family, plan, sl, artifact = _fixture()
    audits = ScopedAuditService(svc)
    started = audits.start(
        family_id=family["entity_id"], actor_id="auditor", objective="Review target impact",
        audit_kind="CODE_REVIEW", target_ids=[sl["entity_id"]], plan_id=plan["entity_id"],
        expansion_relations=["IMPLEMENTS"], max_depth=2, max_objects=8,
    )
    audit_id = started["audit"]["audit_id"]
    assert started["audit"]["counts"]["pending_ids"] == 1

    first = audits.record_finding(
        audit_id=audit_id, actor_id="auditor", subject_id=sl["entity_id"],
        finding_class="ISSUE", impact="EXPAND", summary="Implementation impact requires artifact inspection",
    )
    assert artifact["entity_id"] in first["expanded_ids"]
    assert first["audit"]["closure_state"] == "OPEN"
    audit_ctx = audits.context(audit_id)
    assert artifact["entity_id"] in audit_ctx["cognitive_hygiene"]["working_set_ids"]

    second = audits.record_finding(
        audit_id=audit_id, actor_id="auditor", subject_id=artifact["entity_id"],
        finding_class="NO_ISSUE", impact="NONE", summary="Artifact is consistent within inspected scope",
    )
    assert second["audit"]["closure_state"] == "FIXPOINT_REACHED"
    closed = audits.close(audit_id, actor_id="auditor", summary="Bounded impact closure reached")
    assert closed["status"] == "CLOSED"
    assert closed["closure_state"] == "FIXPOINT_REACHED"
    assert "does not imply VERIFIED" in closed["assurance_rule"]


def test_inspection_expansion_never_expands_mutation_authority():
    svc, family, plan, sl, artifact = _fixture()
    audits = ScopedAuditService(svc)
    started = audits.start(
        family_id=family["entity_id"], actor_id="auditor", objective="Review and repair local slice only",
        audit_kind="CODE_REVIEW", mode="REPAIR_WITHIN_SCOPE", target_ids=[sl["entity_id"]],
        mutation_scope_ids=[sl["entity_id"]], plan_id=plan["entity_id"], expansion_relations=["IMPLEMENTS"],
    )
    audit_id = started["audit"]["audit_id"]
    audits.record_finding(
        audit_id=audit_id, actor_id="auditor", subject_id=sl["entity_id"],
        finding_class="ISSUE", impact="EXPAND", summary="Inspect dependent artifact",
    )
    assert audits.mutation_allowed(audit_id, entity_id=sl["entity_id"])["allowed"] is True
    check = audits.mutation_allowed(audit_id, entity_id=artifact["entity_id"])
    assert check == {"allowed": False, "reason": "OUTSIDE_MUTATION_SCOPE"}


def test_depth_limit_creates_bounded_fixpoint_not_false_global_closure():
    svc, family, plan, sl, artifact = _fixture()
    audits = ScopedAuditService(svc)
    started = audits.start(
        family_id=family["entity_id"], actor_id="auditor", objective="Bounded review",
        target_ids=[sl["entity_id"]], plan_id=plan["entity_id"], expansion_relations=["IMPLEMENTS"],
        max_depth=0, max_objects=8,
    )
    audit_id = started["audit"]["audit_id"]
    result = audits.record_finding(
        audit_id=audit_id, actor_id="auditor", subject_id=sl["entity_id"],
        finding_class="ISSUE", impact="EXPAND", summary="Potential downstream effect",
    )
    assert result["audit"]["closure_state"] == "BOUNDED_FIXPOINT"
    assert artifact["entity_id"] not in result["expanded_ids"]
    assert any(e["reason"] == "DEPTH_LIMIT" for e in result["audit"]["boundary_events"])
    closed = audits.close(audit_id, actor_id="auditor")
    assert closed["closure_state"] == "BOUNDED_FIXPOINT"


def test_outside_family_impact_is_reported_not_absorbed_into_scope():
    svc, family, plan, sl, _ = _fixture()
    other = svc.create_family("OTHER", "Other system")
    other_artifact = svc.attach_artifact(
        logical_name="external.py", artifact_type="CODE", storage_system="FILESYSTEM",
        physical_location="/other/external.py", belongs_to=[other["entity_id"]],
    )
    audits = ScopedAuditService(svc)
    started = audits.start(
        family_id=family["entity_id"], actor_id="auditor", objective="Local review",
        target_ids=[sl["entity_id"]], plan_id=plan["entity_id"],
    )
    audit_id = started["audit"]["audit_id"]
    result = audits.record_finding(
        audit_id=audit_id, actor_id="auditor", subject_id=sl["entity_id"],
        finding_class="INFO", impact="OUTSIDE_SCOPE", summary="External dependency may be affected",
        affected_ids=[other_artifact["entity_id"]], affected_refs=["service://external-api"],
    )
    assert other_artifact["entity_id"] not in svc.store.get("audit_runs", audit_id)["current_scope_ids"]
    assert any(e["reason"] == "REPORTED_OUTSIDE_SCOPE" for e in result["audit"]["boundary_events"])


def test_read_only_audit_rejects_mutation_scope_and_close_rejects_open_frontier():
    svc, family, plan, sl, _ = _fixture()
    audits = ScopedAuditService(svc)
    with pytest.raises(ScopedAuditError):
        audits.start(
            family_id=family["entity_id"], actor_id="auditor", objective="Read only",
            target_ids=[sl["entity_id"]], plan_id=plan["entity_id"], mode="READ_ONLY",
            mutation_scope_ids=[sl["entity_id"]],
        )
    started = audits.start(
        family_id=family["entity_id"], actor_id="auditor", objective="Read only",
        target_ids=[sl["entity_id"]], plan_id=plan["entity_id"], mode="READ_ONLY",
    )
    audit_id = started["audit"]["audit_id"]
    assert audits.mutation_allowed(audit_id, entity_id=sl["entity_id"])["allowed"] is False
    with pytest.raises(ScopedAuditError, match="AUDIT_FRONTIER_NOT_CLOSED"):
        audits.close(audit_id, actor_id="auditor")
