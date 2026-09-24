from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer

from .context import ContextCompiler
from .importer import (
    BigBangReconciler,
    BigBangScanner,
    load_id_patterns_json,
    serialize_discovery,
    serialize_git_discovery,
)
from .maintenance import MangoMaintainer
from .filesystem import FilesystemScanner
from .interlingua import UAICompiler, decode_uai_result as decode_result_packet, render_uai_result as render_result_packet
from .runtime import get_service, health_snapshot

mcp = MCPServer(
    "MangoMe",
    description="Canonical contract-family, slice, evidence, and project-state graph for multi-agent work.",
    instructions=(
        "Read relevant state before acting. Productive mutation requires a persisted plan. "
        "DONE is a worker claim, not verification. Verification and approval use runtime capabilities. "
        "Collision warnings are advisory and must never block work. UAI/1 is compact transport only: "
        "decode worker results and route them through normal MangoMe mutation/assurance tools."
    ),
    version="0.1.6",
)


@mcp.tool()
def health() -> dict[str, Any]:
    """Return readiness even when backing-store initialization fails."""
    return health_snapshot()


@mcp.tool()
def intake_request(request_text: str, classification: str | None = None, classification_source: str | None = None, source_ref: str | None = None, family_id: str | None = None) -> dict[str, Any]:
    """Persist and categorize a new assignment before execution."""
    return get_service().intake_request(request_text=request_text, classification=classification, classification_source=classification_source, source_ref=source_ref, family_id=family_id)


@mcp.tool()
def create_spec(family_id: str, objective: str, contract_ids: list[str] | None = None, deliverables: list[str] | None = None, constraints: list[str] | None = None, acceptance_criteria: list[str] | None = None, out_of_scope: list[str] | None = None, required_evidence: list[str] | None = None, supersedes_spec_id: str | None = None) -> dict[str, Any]:
    """Append an immutable specification version for a family."""
    return get_service().create_spec(family_id=family_id, objective=objective, contract_ids=contract_ids, deliverables=deliverables, constraints=constraints, acceptance_criteria=acceptance_criteria, out_of_scope=out_of_scope, required_evidence=required_evidence, supersedes_spec_id=supersedes_spec_id)


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
def register_contract(declared_id: str, family_id: str, title: str, kind: str = "BASE", actor_id: str | None = None, storage_system: str | None = None, physical_location: str | None = None, checksum: str | None = None) -> dict[str, Any]:
    """Append a contract contribution; declared-id collisions are preserved and warned."""
    return get_service().register_contract(declared_id=declared_id, family_id=family_id, title=title, kind=kind, actor_id=actor_id, storage_system=storage_system, physical_location=physical_location, checksum=checksum)


@mcp.tool()
def import_contract_bundle(family_key: str, family_title: str, declared_id: str, contract_title: str, actor_id: str, slices: list[dict[str, Any]], kind: str = "BASE", project_ids: list[str] | None = None, scope_ids: list[str] | None = None, storage_system: str | None = None, physical_location: str | None = None) -> dict[str, Any]:
    """Onboard an existing contract plus its existing slices in one explicit operation."""
    svc = get_service()
    family = svc.create_family(family_key, family_title, project_ids, scope_ids)
    contract = svc.register_contract(declared_id=declared_id, family_id=family["entity_id"], title=contract_title, kind=kind, actor_id=actor_id, storage_system=storage_system, physical_location=physical_location)
    imported = []
    for item in slices:
        payload = dict(item)
        payload.setdefault("contract_ids", [contract["entity_id"]])
        payload["family_id"] = family["entity_id"]
        imported.append(svc.import_slice(**payload))
    return {"family": family, "contract": contract, "slices": imported, "status": svc.status(family["entity_id"])}


@mcp.tool()
def attach_artifact(logical_name: str, artifact_type: str, storage_system: str, physical_location: str, belongs_to: list[str] | None = None, checksum: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register a physical artifact/reference without changing its external storage."""
    return get_service().attach_artifact(logical_name=logical_name, artifact_type=artifact_type, storage_system=storage_system, physical_location=physical_location, belongs_to=belongs_to, checksum=checksum, metadata=metadata)


@mcp.tool()
def link_entities(from_type: str, from_id: str, relation: str, to_type: str, to_id: str, status: str = "CONFIRMED", source_actor_id: str | None = None, confidence: float | None = None) -> dict[str, Any]:
    """Create a validated typed relation such as ADDS_TO, AMENDS, EXTENDS, REPAIRS or SUPERSEDES."""
    return get_service().link(from_type=from_type, from_id=from_id, relation=relation, to_type=to_type, to_id=to_id, status=status, source_actor_id=source_actor_id, confidence=confidence)


@mcp.tool()
def submit_plan(family_id: str, request_id: str, spec_id: str, actor_id: str, intent: str, proposed_slices: list[dict[str, Any]], contract_ids: list[str] | None = None, expected_artifacts: list[str] | None = None, expected_scope: list[str] | None = None, estimate: dict[str, Any] | None = None, acceptance_expectations: list[str] | None = None) -> dict[str, Any]:
    """Record the mandatory pre-execution plan and return advisory collision warnings."""
    return get_service().submit_plan(family_id=family_id, request_id=request_id, spec_id=spec_id, actor_id=actor_id, intent=intent, proposed_slices=proposed_slices, contract_ids=contract_ids, expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate, acceptance_expectations=acceptance_expectations)


@mcp.tool()
def begin_work(
    family_id: str, actor_id: str, request_text: str, intent: str, proposed_slice: dict[str, Any],
    classification: str = "EXISTING_CONTRACT_WORK", classification_source: str = "IntakeGov",
    spec_id: str | None = None, contract_ids: list[str] | None = None,
    expected_artifacts: list[str] | None = None, expected_scope: list[str] | None = None,
    estimate: dict[str, Any] | None = None, acceptance_expectations: list[str] | None = None,
) -> dict[str, Any]:
    """Convenience composition of intake -> plan -> start using an existing effective spec; no governance invariant is bypassed."""
    return get_service().begin_work(
        family_id=family_id, actor_id=actor_id, request_text=request_text, intent=intent,
        proposed_slice=proposed_slice, classification=classification, classification_source=classification_source,
        spec_id=spec_id, contract_ids=contract_ids, expected_artifacts=expected_artifacts,
        expected_scope=expected_scope, estimate=estimate, acceptance_expectations=acceptance_expectations,
    )


@mcp.tool()
def start_slice(slice_id: str, actor_id: str, plan_id: str) -> dict[str, Any]:
    """Start a slice and bind it to the actor's persisted active plan."""
    return get_service().start_slice(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)


@mcp.tool()
def update_slice_progress(slice_id: str, actor_id: str, plan_id: str, current_step: int | None = None, total_steps: int | None = None, blocker: str | None = None, execution_state: str | None = None) -> dict[str, Any]:
    """Persist slice progress; the same active plan that started the slice is mandatory."""
    return get_service().update_slice_progress(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id, current_step=current_step, total_steps=total_steps, blocker=blocker, execution_state=execution_state)


@mcp.tool()
def claim_done(slice_id: str, actor_id: str, plan_id: str, summary: str | None = None) -> dict[str, Any]:
    """Record DONE_CLAIMED under the slice's active plan; this never implies verification."""
    return get_service().claim_done(slice_id=slice_id, actor_id=actor_id, plan_id=plan_id, summary=summary)


@mcp.tool()
def close_plan(plan_id: str, actor_id: str) -> dict[str, Any]:
    """Close an unbound plan so it stops generating collision traffic."""
    return get_service().close_plan(plan_id, actor_id)


@mcp.tool()
def submit_evidence(subject_id: str, evidence_type: str, source: str, result: str | None = None, evidence_class: str = "CLAIM", artifact_id: str | None = None, actor_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist evidence. New evidence is UNATTESTED until a trusted verifier/owner attests it."""
    return get_service().submit_evidence(subject_id=subject_id, evidence_type=evidence_type, source=source, result=result, evidence_class=evidence_class, artifact_id=artifact_id, actor_id=actor_id, payload=payload)


@mcp.tool()
def attest_evidence(evidence_id: str, attested_by: str, capability_token: str | None = None, authority: str = "VERIFIER") -> dict[str, Any]:
    """Attest evidence using a runtime verifier/owner capability. The capability is never persisted."""
    return get_service().attest_evidence(evidence_id=evidence_id, attested_by=attested_by, capability_token=capability_token, authority=authority)


@mcp.tool()
def set_gate(slice_id: str, gate_id: str, status: str, actor_id: str | None = None, evidence_ids: list[str] | None = None, approval_id: str | None = None) -> dict[str, Any]:
    """Set a gate. PASS requires attested PASS evidence; WAIVED requires approved owner decision."""
    return get_service().set_gate(slice_id=slice_id, gate_id=gate_id, status=status, actor_id=actor_id, evidence_ids=evidence_ids, approval_id=approval_id)


@mcp.tool()
def set_gate_controlled(slice_id: str, gate_id: str, status: str, actor_id: str, evidence_ids: list[str] | None = None, approval_id: str | None = None) -> dict[str, Any]:
    """Compatibility alias for v0.1.1 controlled gate updates."""
    return get_service().set_gate(slice_id=slice_id, gate_id=gate_id, status=status, actor_id=actor_id, evidence_ids=evidence_ids, approval_id=approval_id)


@mcp.tool()
def verify_slice(slice_id: str, verifier_actor_id: str, verifier_token: str | None = None, evidence_ids: list[str] | None = None) -> dict[str, Any]:
    """Verify DONE_CLAIMED using an independent runtime verifier capability and attested evidence."""
    return get_service().verify_slice(slice_id=slice_id, verifier_actor_id=verifier_actor_id, verifier_token=verifier_token, evidence_ids=evidence_ids)


@mcp.tool()
def request_override(action_type: str, subject_id: str, requested_by: str, reason: str) -> dict[str, Any]:
    """Create an explicit approval request; requesting approval does not grant it."""
    return get_service().request_override(action_type=action_type, subject_id=subject_id, requested_by=requested_by, reason=reason)


@mcp.tool()
def approve_override(approval_id: str, decided_by: str, approval_token: str | None = None, decision_ref: str | None = None) -> dict[str, Any]:
    """Approve using the owner runtime capability; actor strings alone are insufficient."""
    return get_service().approve_override(approval_id=approval_id, decided_by=decided_by, approval_token=approval_token, decision_ref=decision_ref)


@mcp.tool()
def reject_override(approval_id: str, decided_by: str, approval_token: str | None = None, decision_ref: str | None = None) -> dict[str, Any]:
    """Reject using the owner runtime capability."""
    return get_service().reject_override(approval_id=approval_id, decided_by=decided_by, approval_token=approval_token, decision_ref=decision_ref)


@mcp.tool()
def list_approvals(status: str | None = None, subject_id: str | None = None) -> list[dict[str, Any]]:
    """List approval requests, optionally filtered by status and subject."""
    return get_service().list_approvals(status=status, subject_id=subject_id)


@mcp.tool()
def accept_slice(slice_id: str, approval_id: str, accepted_by: str | None = None) -> dict[str, Any]:
    """Move VERIFIED to ACCEPTED using a trusted approved ACCEPT_SLICE decision."""
    return get_service().accept_slice(slice_id=slice_id, approval_id=approval_id, accepted_by=accepted_by)


@mcp.tool()
def status(family_id: str) -> dict[str, Any]:
    """Return deterministic materialized state for one family."""
    return get_service().status(family_id)


@mcp.tool()
def project_overview(project_ref: str) -> dict[str, Any]:
    """Explain a complete project's current state across all known families."""
    return get_service().project_overview(project_ref)


@mcp.tool()
def effective_family_view(family_id: str) -> dict[str, Any]:
    """Return the effective append-only contract-family view, supersession, relations, and conflicts."""
    return get_service().effective_family_view(family_id)


@mcp.tool()
def read_context(family_id: str) -> dict[str, Any]:
    """Read all relevant family context. Reading is unrestricted."""
    return get_service().get_context(family_id)


@mcp.tool()
def compile_execution_context(family_id: str, slice_id: str | None = None) -> dict[str, Any]:
    """Produce a compact deterministic execution package for IntakeGov/CogC or a worker."""
    return ContextCompiler(get_service()).compile(family_id, slice_id)


@mcp.tool()
def compile_uai_context(family_id: str, slice_id: str | None = None) -> dict[str, Any]:
    """Compile canonical MangoMe truth into a versioned compact UAI/1 execution packet with semantic hash and savings metrics."""
    return UAICompiler(get_service()).compile(family_id, slice_id)


@mcp.tool()
def expand_uai_context(wire: str) -> dict[str, Any]:
    """Round-trip a UAI/1 context packet back into its canonical semantic execution projection and verify its hash."""
    return UAICompiler.decode_context(wire)


@mcp.tool()
def decode_uai_result(result_json: str, expected_context_hash: str | None = None) -> dict[str, Any]:
    """Validate and expand a compact UAI/1R worker result. This never mutates canonical state."""
    return decode_result_packet(result_json, expected_context_hash=expected_context_hash)


@mcp.tool()
def render_uai_result(result_json: str, language: str = "en", expected_context_hash: str | None = None) -> str:
    """Render a structured UAI/1R worker result into deterministic human-readable English or German."""
    return render_result_packet(result_json, language=language, expected_context_hash=expected_context_hash)


@mcp.tool()
def graph(entity_id: str) -> dict[str, Any]:
    """Return validated confirmed/suggested incoming and outgoing graph edges for an entity."""
    return get_service().graph(entity_id)


@mcp.tool()
def register_model(model_key: str, provider: str | None = None, access_path: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Register a model/access-path identity for empirical execution comparisons."""
    return get_service().register_model(model_key=model_key, provider=provider, access_path=access_path, metadata=metadata)


@mcp.tool()
def record_execution_receipt(family_id: str, slice_id: str, actor_id: str, model_id: str | None = None, work_class: str = "UNCLASSIFIED", input_tokens: int | None = None, output_tokens: int | None = None, execution_cost: float = 0.0, verification_cost: float = 0.0, repair_cost: float = 0.0, human_cost: float = 0.0, currency: str = "EUR", outcome: str = "UNKNOWN", context_tokens_raw: int | None = None, context_tokens_compiled: int | None = None, context_tokens_interlingua: int | None = None, output_tokens_interlingua: int | None = None, interlingua_version: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record model/agent cost and durable outcome economics, including optional UAI/1 transport telemetry."""
    return get_service().record_execution_receipt(family_id=family_id, slice_id=slice_id, actor_id=actor_id, model_id=model_id, work_class=work_class, input_tokens=input_tokens, output_tokens=output_tokens, execution_cost=execution_cost, verification_cost=verification_cost, repair_cost=repair_cost, human_cost=human_cost, currency=currency, outcome=outcome, context_tokens_raw=context_tokens_raw, context_tokens_compiled=context_tokens_compiled, context_tokens_interlingua=context_tokens_interlingua, output_tokens_interlingua=output_tokens_interlingua, interlingua_version=interlingua_version, metadata=metadata)


@mcp.tool()
def model_stats(model_id: str | None = None, work_class: str | None = None) -> dict[str, Any]:
    """Return empirical cost/verified-outcome statistics."""
    return get_service().model_stats(model_id=model_id, work_class=work_class)


@mcp.tool()
def bigbang_scan(roots: list[str], id_patterns: list[str] | None = None, include_git: bool = True) -> dict[str, Any]:
    """Non-destructively inventory filesystem and optional Git state; never auto-canonicalizes semantic truth."""
    patterns = id_patterns or load_id_patterns_json(os.environ.get("MANGOME_ID_PATTERNS_JSON"))
    scanner = BigBangScanner(get_service(), id_patterns=patterns)
    records = scanner.scan(roots)
    git_records = scanner.scan_git(roots) if include_git else []
    return {
        "roots": roots,
        "count": len(records),
        "records": serialize_discovery(records),
        "git": serialize_git_discovery(git_records),
        "note": "Discovery only. Candidates do not become canonical contracts until explicitly admitted.",
    }


@mcp.tool()
def reconcile_bigbang(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Match Big-Bang discovery against canonical state without performing semantic mutations."""
    return BigBangReconciler(get_service()).reconcile(records)  # type: ignore[return-value]


@mcp.tool()
def filesystem_scan(roots: list[str], max_files: int = 50000, max_depth: int = 16, max_hash_bytes: int = 67108864) -> dict[str, Any]:
    """Build/update a bounded deterministic filesystem inventory. This discovers facts; it never verifies contracts or trusts audit prose."""
    return FilesystemScanner(get_service()).scan(
        roots, max_files=max_files, max_depth=max_depth, max_hash_bytes=max_hash_bytes
    )


@mcp.tool()
def filesystem_references(declared_id: str, present_only: bool = True, limit: int = 200) -> dict[str, Any]:
    """Find indexed source/test/contract/report files that lexically reference a declared contract/work id."""
    return FilesystemScanner(get_service()).references(declared_id, present_only=present_only, limit=limit)


@mcp.tool()
def build_reproduction_binding(
    command: str,
    cwd: str,
    exit_code: int,
    input_paths: list[str],
    output_artifact_id: str | None = None,
    environment_names: list[str] | None = None,
    stdout_sha256: str | None = None,
    stderr_sha256: str | None = None,
    git_commit: str | None = None,
    max_hash_bytes: int = 67108864,
) -> dict[str, Any]:
    """Build an RB/1 reproduction binding from current files/Git metadata without executing the command or reading environment values."""
    return FilesystemScanner(get_service()).build_reproduction_binding(
        command=command,
        cwd=cwd,
        exit_code=exit_code,
        input_paths=input_paths,
        output_artifact_id=output_artifact_id,
        environment_names=environment_names,
        stdout_sha256=stdout_sha256,
        stderr_sha256=stderr_sha256,
        git_commit=git_commit,
        max_hash_bytes=max_hash_bytes,
    )


@mcp.tool()
def evidence_freshness(evidence_id: str, live_check: bool = True) -> dict[str, Any]:
    """Check whether attested PASS evidence remains current under legacy hash bindings or RB/1 reproduction bindings. Never reruns commands or changes assurance state."""
    return FilesystemScanner(get_service()).evidence_freshness(evidence_id, live_check=live_check)


@mcp.tool()
def refresh_views() -> dict[str, int]:
    """Refresh all deterministic family views without LLM use."""
    return MangoMaintainer(get_service()).refresh_all_family_views()


@mcp.tool()
def maintenance_diagnose(stale_after_hours: float = 24.0) -> dict[str, Any]:
    """Report stale plan candidates, collisions, approvals and unresolved graph work without auto-fixing it."""
    return MangoMaintainer(get_service()).diagnose(stale_after_hours=stale_after_hours)


@mcp.tool()
def migrate_schema(dry_run: bool = True) -> dict[str, Any]:
    """Dry-run or explicitly persist registered lazy schema migrations."""
    return MangoMaintainer(get_service()).migrate_schema(dry_run=dry_run)


def main() -> None:
    transport = os.environ.get("MANGOME_MCP_TRANSPORT", "stdio")
    kwargs: dict[str, Any] = {}
    if transport in {"streamable-http", "sse"}:
        kwargs["host"] = os.environ.get("MANGOME_MCP_HOST", "127.0.0.1")
        kwargs["port"] = int(os.environ.get("MANGOME_MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
