from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer

from .context import ContextCompiler
from .importer import BigBangScanner, serialize_discovery
from .maintenance import MangoMaintainer
from .runtime import get_service

mcp = MCPServer(
    "MangoMe",
    description="Canonical contract-family, slice, evidence, and project-state graph for multi-agent work.",
    instructions=(
        "Read access is unrestricted. Before productive mutation, submit a plan. "
        "DONE is a worker claim, not verification. Collision warnings are advisory and must never block work."
    ),
    version="0.1.0",
)


@mcp.tool()
def intake_request(
    request_text: str,
    classification: str | None = None,
    classification_source: str | None = None,
    source_ref: str | None = None,
    family_id: str | None = None,
) -> dict[str, Any]:
    """Persist and categorize a new assignment before execution. IntakeGov should pass its classification when available."""
    return get_service().intake_request(
        request_text=request_text, classification=classification, classification_source=classification_source,
        source_ref=source_ref, family_id=family_id,
    )


@mcp.tool()
def create_spec(
    family_id: str,
    objective: str,
    contract_ids: list[str] | None = None,
    deliverables: list[str] | None = None,
    constraints: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    required_evidence: list[str] | None = None,
    supersedes_spec_id: str | None = None,
) -> dict[str, Any]:
    """Append an immutable specification version for a family."""
    return get_service().create_spec(
        family_id=family_id, objective=objective, contract_ids=contract_ids, deliverables=deliverables,
        constraints=constraints, acceptance_criteria=acceptance_criteria, out_of_scope=out_of_scope,
        required_evidence=required_evidence, supersedes_spec_id=supersedes_spec_id,
    )


@mcp.tool()
def resolve(query: str) -> dict[str, Any]:
    """Resolve a family, declared contract id, or slice id without semantic guessing."""
    return get_service().resolve(query)


@mcp.tool()
def create_project(project_key: str, title: str, description: str | None = None) -> dict[str, Any]:
    """Create or return a project container."""
    return get_service().create_project(project_key, title, description)


@mcp.tool()
def create_family(family_key: str, title: str, project_ids: list[str] | None = None, scope_ids: list[str] | None = None) -> dict[str, Any]:
    """Create or return a durable contract/work family."""
    return get_service().create_family(family_key, title, project_ids, scope_ids)


@mcp.tool()
def register_contract(
    declared_id: str,
    family_id: str,
    title: str,
    kind: str = "BASE",
    actor_id: str | None = None,
    storage_system: str | None = None,
    physical_location: str | None = None,
    checksum: str | None = None,
) -> dict[str, Any]:
    """Append a contract contribution. Declared-id collisions are preserved and warned, never overwritten."""
    return get_service().register_contract(
        declared_id=declared_id,
        family_id=family_id,
        title=title,
        kind=kind,
        actor_id=actor_id,
        storage_system=storage_system,
        physical_location=physical_location,
        checksum=checksum,
    )


@mcp.tool()
def import_contract_bundle(
    family_key: str,
    family_title: str,
    declared_id: str,
    contract_title: str,
    actor_id: str,
    slices: list[dict[str, Any]],
    kind: str = "BASE",
    project_ids: list[str] | None = None,
    scope_ids: list[str] | None = None,
    storage_system: str | None = None,
    physical_location: str | None = None,
) -> dict[str, Any]:
    """Onboard an existing contract plus its existing slices in one explicit operation."""
    svc = get_service()
    family = svc.create_family(family_key, family_title, project_ids, scope_ids)
    contract = svc.register_contract(
        declared_id=declared_id,
        family_id=family["entity_id"],
        title=contract_title,
        kind=kind,
        actor_id=actor_id,
        storage_system=storage_system,
        physical_location=physical_location,
    )
    imported = []
    for s in slices:
        payload = dict(s)
        payload.setdefault("contract_ids", [contract["entity_id"]])
        payload["family_id"] = family["entity_id"]
        imported.append(svc.import_slice(**payload))
    return {"family": family, "contract": contract, "slices": imported, "status": svc.status(family["entity_id"])}


@mcp.tool()
def submit_plan(
    family_id: str,
    request_id: str,
    spec_id: str,
    actor_id: str,
    intent: str,
    proposed_slices: list[dict[str, Any]],
    contract_ids: list[str] | None = None,
    expected_artifacts: list[str] | None = None,
    expected_scope: list[str] | None = None,
    estimate: dict[str, Any] | None = None,
    acceptance_expectations: list[str] | None = None,
) -> dict[str, Any]:
    """Record the mandatory pre-execution plan and return advisory collision warnings."""
    return get_service().submit_plan(
        family_id=family_id,
        request_id=request_id,
        spec_id=spec_id,
        actor_id=actor_id,
        intent=intent,
        proposed_slices=proposed_slices,
        contract_ids=contract_ids,
        expected_artifacts=expected_artifacts,
        expected_scope=expected_scope,
        estimate=estimate,
        acceptance_expectations=acceptance_expectations,
    )


@mcp.tool()
def start_slice(slice_id: str, actor_id: str, plan_id: str) -> dict[str, Any]:
    """Start a slice. A matching recorded plan is mandatory; collisions only warn."""
    return get_service().start_slice(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)


@mcp.tool()
def update_slice_progress(
    slice_id: str,
    actor_id: str,
    current_step: int | None = None,
    total_steps: int | None = None,
    blocker: str | None = None,
    execution_state: str | None = None,
) -> dict[str, Any]:
    """Persist current slice state. Does not verify or complete work."""
    return get_service().update_slice_progress(
        slice_id=slice_id,
        actor_id=actor_id,
        current_step=current_step,
        total_steps=total_steps,
        blocker=blocker,
        execution_state=execution_state,
    )


@mcp.tool()
def claim_done(slice_id: str, actor_id: str, summary: str | None = None) -> dict[str, Any]:
    """Record DONE_CLAIMED. The slice remains open/unverified until its gates are verified."""
    return get_service().claim_done(slice_id=slice_id, actor_id=actor_id, summary=summary)


@mcp.tool()
def submit_evidence(
    subject_id: str,
    evidence_type: str,
    source: str,
    result: str | None = None,
    artifact_id: str | None = None,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach durable evidence to a family, contract, slice, or artifact."""
    return get_service().submit_evidence(
        subject_id=subject_id,
        evidence_type=evidence_type,
        source=source,
        result=result,
        artifact_id=artifact_id,
        actor_id=actor_id,
        payload=payload,
    )


@mcp.tool()
def set_gate(slice_id: str, gate_id: str, status: str, evidence_ids: list[str] | None = None) -> dict[str, Any]:
    """Update an acceptance gate with evidence references. Verification still requires all gates PASS/WAIVED."""
    return get_service().set_gate(slice_id=slice_id, gate_id=gate_id, status=status, evidence_ids=evidence_ids)


@mcp.tool()
def verify_slice(slice_id: str, verifier_actor_id: str, evidence_ids: list[str] | None = None) -> dict[str, Any]:
    """Verify a DONE_CLAIMED slice only when every acceptance gate is PASS or WAIVED."""
    return get_service().verify_slice(slice_id=slice_id, verifier_actor_id=verifier_actor_id, evidence_ids=evidence_ids)


@mcp.tool()
def status(family_id: str) -> dict[str, Any]:
    """Return deterministic materialized project-management state for one family."""
    return get_service().status(family_id)


@mcp.tool()
def read_context(family_id: str) -> dict[str, Any]:
    """Read all current family context. Reading is unrestricted for every agent."""
    return get_service().get_context(family_id)


@mcp.tool()
def compile_execution_context(family_id: str, slice_id: str | None = None) -> dict[str, Any]:
    """Produce a compact deterministic execution package for IntakeGov/CogC or a worker."""
    return ContextCompiler(get_service()).compile(family_id, slice_id)


@mcp.tool()
def graph(entity_id: str) -> dict[str, Any]:
    """Return confirmed/suggested incoming and outgoing graph edges for an entity."""
    return get_service().graph(entity_id)


@mcp.tool()
def register_model(model_key: str, provider: str | None = None, access_path: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register a model/access-path identity for empirical execution comparisons."""
    return get_service().register_model(model_key=model_key, provider=provider, access_path=access_path, metadata=metadata)


@mcp.tool()
def record_execution_receipt(
    family_id: str, slice_id: str, actor_id: str, model_id: str | None = None, work_class: str = "UNCLASSIFIED",
    input_tokens: int | None = None, output_tokens: int | None = None, execution_cost: float = 0.0,
    verification_cost: float = 0.0, repair_cost: float = 0.0, human_cost: float = 0.0, currency: str = "EUR",
    outcome: str = "UNKNOWN", context_tokens_raw: int | None = None, context_tokens_compiled: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record model/agent cost and outcome for a slice; durable cost includes verification, repair and human cost."""
    return get_service().record_execution_receipt(
        family_id=family_id, slice_id=slice_id, actor_id=actor_id, model_id=model_id, work_class=work_class,
        input_tokens=input_tokens, output_tokens=output_tokens, execution_cost=execution_cost,
        verification_cost=verification_cost, repair_cost=repair_cost, human_cost=human_cost, currency=currency,
        outcome=outcome, context_tokens_raw=context_tokens_raw, context_tokens_compiled=context_tokens_compiled, metadata=metadata,
    )


@mcp.tool()
def model_stats(model_id: str | None = None, work_class: str | None = None) -> dict[str, Any]:
    """Return empirical cost/verified-outcome statistics from MangoMe execution receipts."""
    return get_service().model_stats(model_id=model_id, work_class=work_class)


@mcp.tool()
def bigbang_scan(roots: list[str]) -> dict[str, Any]:
    """Non-destructively inventory configured filesystem roots; never auto-canonicalizes ambiguous contracts."""
    records = BigBangScanner(get_service()).scan(roots)
    return {
        "roots": roots,
        "count": len(records),
        "records": serialize_discovery(records),
        "note": "Discovery only. CONTRACT_CANDIDATE does not become a canonical contract until explicitly onboarded.",
    }


@mcp.tool()
def refresh_views() -> dict[str, int]:
    """Run deterministic maintenance and refresh all family status projections without LLM use."""
    return MangoMaintainer(get_service()).refresh_all_family_views()


def main() -> None:
    transport = os.environ.get("MANGOME_MCP_TRANSPORT", "stdio")
    kwargs: dict[str, Any] = {}
    if transport in {"streamable-http", "sse"}:
        kwargs["host"] = os.environ.get("MANGOME_MCP_HOST", "127.0.0.1")
        kwargs["port"] = int(os.environ.get("MANGOME_MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
