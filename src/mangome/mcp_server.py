from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from .context import ContextCompiler
from .authority import CapabilityDenied, require_router
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
from .runtime import (
    get_service, health_snapshot, refresh_workspace_attachment, workspace_attachment_snapshot,
    set_session_restore_snapshot, session_restore_snapshot,
)
from .service import MangoMeError, workspace_project_key

mcp = MCPServer(
    "MangoMe",
    description="Canonical operational memory and verification substrate for multi-agent work.",
    instructions=(
        "Zero-touch applies to the user interface, not to governance. Never ask the user to operate Big Bang, "
        "contracts, slices, plans, or other MangoMe internals. Before project-changing work, call session_restore (or session_bootstrap) first. "
        "Discovery is candidate-only and is only an onboarding mechanism for work that is not yet admitted. Once a "
        "workspace/project is admitted, current work identity and recovery state MUST come from MangoMe canonical state, "
        "never from broad filesystem/repository scans, Git/worktree archaeology, contract/evidence directories, or prior "
        "agent prose. Use recovery_context/project_overview/status/read_context first and inspect physical artifacts only "
        "for a bounded unresolved delta. A missing restore state is RESTORE_STATE_NOT_FOUND and MUST NOT be replaced by newly created Project/Family/Specification state. For genuinely new work without admitted MangoMe identity, call enter_work with "
        "the user's request; it creates client-relayed user-intent operational state and the mandatory Plan/Slice binding "
        "without promoting discovered history. Productive mutation requires a persisted plan and canonical next_executable_items. Unfinished intent or an ACTIVE goal does not itself grant execution. MangoMe is infrastructure: agents may use it, but must not modify MangoMe source unless the explicit assignment is to change MangoMe itself. Delegation is also governed: "
        "mechanical recovery should use bounded low-cost workers; current runtime capabilities must be checked before dispatch "
        "and again before capability-sensitive actions. A capability downgrade means checkpoint and hand off only the missing "
        "capability; never rediscover state or automatically escalate to a costly model swarm. MangoMe authorizes/checkpoints "
        "delegation but does not own the external model dispatcher, so the host/orchestrator MUST enforce negative authorization "
        "decisions at its actual dispatch boundary. Human-visible coordinator/recovery/control-plane narration MUST inherit the "
        "current user/session working language unless the user explicitly changes it; persona, memory, runtime defaults, or Skill "
        "text must not silently switch natural language. Stable machine identifiers/reason codes remain language-neutral. DONE is "
        "only a worker claim; verification and acceptance remain separate privileged transitions."
    ),
    version="0.1.9rc4",
)


def _domain_call(fn, /, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Return actionable domain failures instead of opaque MCP execution errors.

    Successful calls keep their historical response shape. Expected MangoMe/user-input
    failures are returned as structured data so an agent can repair its own tool call
    without asking the user to understand MangoMe internals.
    """
    try:
        return fn(*args, **kwargs)
    except (MangoMeError, ValueError, KeyError) as exc:
        return {
            "ok": False,
            "error": {
                "code": type(exc).__name__,
                "message": str(exc),
                "recoverable": True,
            },
        }


def _restore_gate(operation: str, *, allow_new_work: bool = False) -> dict[str, Any] | None:
    """Managed clients fail closed until a three-state restore decision exists.

    This gate is opt-in for unmanaged/API callers but enabled by `mangome setup`.
    It never creates state. `enter_work` is the sole explicit new-work exception when
    restore returned STATE_NOT_FOUND.
    """
    if str(os.environ.get("MANGOME_REQUIRE_SESSION_RESTORE", "")).strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    restored = session_restore_snapshot()
    if restored is None:
        return {
            "ok": False,
            "error": {
                "code": "SESSION_RESTORE_REQUIRED",
                "message": f"{operation} is blocked until session_restore/session_bootstrap runs.",
                "recoverable": True,
            },
        }
    state = str(restored.get("restore_state") or "")
    if state == "STATE_NOT_FOUND" and allow_new_work:
        return None
    if state != "STATE_FOUND":
        return {
            "ok": False,
            "error": {
                "code": "RESTORE_NOT_EXECUTABLE",
                "message": f"{operation} is blocked because restore_state={state or 'UNKNOWN'}; use explicit backfill/import or NEW-WORK admission rather than synthesizing recovery state.",
                "recoverable": True,
            },
            "restore": restored,
        }
    return None


def _known_admitted_workspace_roots() -> list[Path]:
    """Return known filesystem roots that already have canonical zero-touch Project state."""
    svc = get_service()
    roots: list[Path] = []
    for row in svc.store.find("filesystem_roots"):
        raw = str(row.get("root_path") or "").strip()
        if not raw:
            continue
        try:
            root = Path(raw).expanduser().resolve()
            svc.project_overview(workspace_project_key(str(root)))
        except (OSError, KeyError):
            continue
        roots.append(root)
    current = workspace_attachment_snapshot()
    raw_current = str((current or {}).get("workspace_root") or "").strip()
    if raw_current:
        try:
            root = Path(raw_current).expanduser().resolve()
            svc.project_overview(workspace_project_key(str(root)))
            if root not in roots:
                roots.append(root)
        except (OSError, KeyError):
            pass
    return roots


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _discovery_block(roots: list[str] | None, operation: str) -> dict[str, Any] | None:
    """Fail closed when broad discovery would reconstruct already-admitted work."""
    admitted = _known_admitted_workspace_roots()
    if not admitted:
        return None
    targets: list[Path] = []
    for raw in roots or []:
        try:
            targets.append(Path(raw).expanduser().resolve())
        except OSError:
            continue
    if targets and not any(_overlaps(target, root) for target in targets for root in admitted):
        return None
    return {
        "ok": False,
        "error": {
            "code": "ADMITTED_WORK_DISCOVERY_FORBIDDEN",
            "message": (
                f"{operation} cannot be used to reconstruct state for admitted MangoMe work. "
                "Read recovery_context/project_overview/status/read_context first; inspect only the bounded unresolved delta."
            ),
            "recoverable": True,
        },
        "authoritative_roots": [str(root) for root in admitted],
        "rule": "Recovery follows identity. Discovery must never create or reconstruct admitted work identity/state.",
    }


@mcp.tool()
def health() -> dict[str, Any]:
    """Return readiness even when backing-store initialization fails."""
    return health_snapshot()


@mcp.tool()
def workspace_status(workspace_root: str | None = None, refresh: bool = False) -> dict[str, Any]:
    """Return attachment state plus any durable workspace project already known to MangoMe."""
    current = workspace_attachment_snapshot()
    if refresh or current is None or (workspace_root and current.get("workspace_root") != workspace_root):
        current = refresh_workspace_attachment(workspace_root, force=refresh)
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    project_key = workspace_project_key(root)
    try:
        overview = get_service().project_overview(project_key)
    except KeyError:
        overview = None
    admitted = overview is not None
    return {
        "attachment": current,
        "workspace_project_key": project_key,
        "project_overview": overview,
        "state_source": "MANGOME_CANONICAL_STATE" if admitted else "UNADMITTED_DISCOVERY",
        "discovery_allowed_for_state_reconstruction": not admitted,
        "session_restore": session_restore_snapshot(),
        "infrastructure_policy": {
            "mangome_source_mutation": "FORBIDDEN_UNLESS_EXPLICIT_ASSIGNMENT_TARGETS_MANGOME",
            "host_enforcement": "REQUIRED_FOR_HARD_FILESYSTEM_ENFORCEMENT",
        },
        "communication_policy": {
            "human_visible_language": "INHERIT_CURRENT_USER_SESSION_LANGUAGE",
            "silent_language_switch": "FORBIDDEN",
            "machine_identifiers": "STABLE_LANGUAGE_NEUTRAL_TOKENS",
        },
        "truth_boundary": {
            "discovery": "FORBIDDEN_FOR_ADMITTED_STATE_RECONSTRUCTION" if admitted else "CANDIDATE_ONLY",
            "work_admission": "USER_INTENT_RELAYED_BY_CLIENT",
            "verification": "CAPABILITY_REQUIRED",
            "acceptance": "OWNER_CAPABILITY_REQUIRED",
        },
        "rule": (
            "Admitted work must recover from MangoMe canonical state; filesystem/repository discovery may not reconstruct "
            "its identity or current status. Unknown workspaces may use candidate-only discovery before admission."
            if admitted else
            "Discovery is automatic but candidate-only. Ordinary user intent may enter governed operational work through "
            "enter_work; VERIFIED and ACCEPTED remain separate protected states."
        ),
    }


@mcp.tool()
def intake_request(request_text: str, classification: str | None = None, classification_source: str | None = None, source_ref: str | None = None, family_id: str | None = None) -> dict[str, Any]:
    """Persist and categorize a new assignment before execution."""
    blocked = _restore_gate("intake_request")
    if blocked:
        return blocked
    return get_service().intake_request(request_text=request_text, classification=classification, classification_source=classification_source, source_ref=source_ref, family_id=family_id)


@mcp.tool()
def create_spec(family_id: str, objective: str, contract_ids: list[str] | None = None, deliverables: list[str] | None = None, constraints: list[str] | None = None, acceptance_criteria: list[str] | None = None, out_of_scope: list[str] | None = None, required_evidence: list[str] | None = None, supersedes_spec_id: str | None = None) -> dict[str, Any]:
    """Append an immutable specification version for a family."""
    blocked = _restore_gate("create_spec")
    if blocked:
        return blocked
    return get_service().create_spec(family_id=family_id, objective=objective, contract_ids=contract_ids, deliverables=deliverables, constraints=constraints, acceptance_criteria=acceptance_criteria, out_of_scope=out_of_scope, required_evidence=required_evidence, supersedes_spec_id=supersedes_spec_id)


@mcp.tool()
def resolve(query: str) -> dict[str, Any]:
    """Resolve a family, declared contract id, or slice id without semantic guessing."""
    return get_service().resolve(query)


@mcp.tool()
def create_project(project_key: str, title: str, description: str | None = None) -> dict[str, Any]:
    """Create or return a project container."""
    blocked = _restore_gate("create_project")
    if blocked:
        return blocked
    return get_service().create_project(project_key, title, description)


@mcp.tool()
def create_family(family_key: str, title: str, project_ids: list[str] | None = None, scope_ids: list[str] | None = None) -> dict[str, Any]:
    """Create or return a durable contract/work family."""
    blocked = _restore_gate("create_family")
    if blocked:
        return blocked
    return get_service().create_family(family_key, title, project_ids, scope_ids)


@mcp.tool()
def register_contract(declared_id: str, family_id: str, title: str, kind: str = "BASE", actor_id: str | None = None, storage_system: str | None = None, physical_location: str | None = None, checksum: str | None = None) -> dict[str, Any]:
    """Append a contract contribution; declared-id collisions are preserved and warned."""
    blocked = _restore_gate("register_contract")
    if blocked:
        return blocked
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
    blocked = _restore_gate("attach_artifact")
    if blocked:
        return blocked
    return get_service().attach_artifact(logical_name=logical_name, artifact_type=artifact_type, storage_system=storage_system, physical_location=physical_location, belongs_to=belongs_to, checksum=checksum, metadata=metadata)


@mcp.tool()
def link_entities(from_type: str, from_id: str, relation: str, to_type: str, to_id: str, status: str = "CONFIRMED", source_actor_id: str | None = None, confidence: float | None = None) -> dict[str, Any]:
    """Create a validated typed relation such as ADDS_TO, AMENDS, EXTENDS, REPAIRS or SUPERSEDES."""
    blocked = _restore_gate("link_entities")
    if blocked:
        return blocked
    return get_service().link(from_type=from_type, from_id=from_id, relation=relation, to_type=to_type, to_id=to_id, status=status, source_actor_id=source_actor_id, confidence=confidence)


@mcp.tool()
def submit_plan(family_id: str, request_id: str, spec_id: str, actor_id: str, intent: str, proposed_slices: list[dict[str, Any]], contract_ids: list[str] | None = None, expected_artifacts: list[str] | None = None, expected_scope: list[str] | None = None, estimate: dict[str, Any] | None = None, acceptance_expectations: list[str] | None = None) -> dict[str, Any]:
    """Record the mandatory pre-execution plan.

    Each proposed slice needs a title. `declared_id` is optional in v0.1.8.1;
    MangoMe creates a stable AUTO-* id when an ordinary worker omits it.
    Expected domain/input failures are returned as structured `error` data.
    """
    blocked = _restore_gate("submit_plan")
    if blocked:
        return blocked
    return _domain_call(
        get_service().submit_plan,
        family_id=family_id, request_id=request_id, spec_id=spec_id, actor_id=actor_id,
        intent=intent, proposed_slices=proposed_slices, contract_ids=contract_ids,
        expected_artifacts=expected_artifacts, expected_scope=expected_scope, estimate=estimate,
        acceptance_expectations=acceptance_expectations,
    )


@mcp.tool()
def enter_work(
    actor_id: str,
    request_text: str,
    intent: str | None = None,
    slice_title: str | None = None,
    slice_objective: str | None = None,
    acceptance_criteria: list[str] | None = None,
    required_evidence: list[str] | None = None,
    expected_artifacts: list[str] | None = None,
    expected_scope: list[str] | None = None,
    estimate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enter governed work from ordinary user intent with no MangoMe identifiers required.

    The managed workspace becomes a deterministic operational Project/Family. The current
    user request becomes the authoritative Specification for this work. Discovery candidates
    are never promoted automatically. The normal Request -> Plan -> Slice binding is preserved.
    """
    blocked = _restore_gate("enter_work", allow_new_work=True)
    if blocked:
        return blocked
    attachment = workspace_attachment_snapshot() or refresh_workspace_attachment()
    root = str(attachment.get("workspace_root") or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    result = _domain_call(
        get_service().enter_work,
        workspace_id=root,
        workspace_title=Path(root).name or "Workspace",
        actor_id=actor_id,
        request_text=request_text,
        intent=intent,
        slice_title=slice_title,
        slice_objective=slice_objective,
        acceptance_criteria=acceptance_criteria,
        required_evidence=required_evidence,
        expected_artifacts=expected_artifacts,
        expected_scope=expected_scope,
        estimate=estimate,
    )
    if result.get("ok") is not False:
        set_session_restore_snapshot({"restore_state": "STATE_FOUND", "mode": "NEW_WORK_ADMITTED"})
    return result


@mcp.tool()
def begin_work(
    family_id: str, actor_id: str, request_text: str, intent: str,
    proposed_slice: dict[str, Any] | None = None,
    slice_title: str | None = None, slice_declared_id: str | None = None, slice_objective: str | None = None,
    classification: str = "EXISTING_CONTRACT_WORK", classification_source: str = "MANGOME_ZERO_TOUCH",
    spec_id: str | None = None, contract_ids: list[str] | None = None,
    expected_artifacts: list[str] | None = None, expected_scope: list[str] | None = None,
    estimate: dict[str, Any] | None = None, acceptance_expectations: list[str] | None = None,
) -> dict[str, Any]:
    """Compose intake -> plan -> start for ordinary work without MangoMe jargon.

    Existing callers may pass `proposed_slice`. Zero-touch callers can instead pass
    `slice_title` and optionally `slice_objective`; `slice_declared_id` is optional and
    MangoMe generates a stable AUTO-* id when omitted. Domain failures are returned
    as structured error data so the worker can self-correct.
    """
    payload = dict(proposed_slice or {})
    if slice_title and not payload.get("title"):
        payload["title"] = slice_title
    if slice_declared_id and not payload.get("declared_id"):
        payload["declared_id"] = slice_declared_id
    if slice_objective and not payload.get("objective"):
        payload["objective"] = slice_objective
    if not payload.get("title"):
        payload["title"] = intent
    blocked = _restore_gate("begin_work")
    if blocked:
        return blocked
    return _domain_call(
        get_service().begin_work,
        family_id=family_id, actor_id=actor_id, request_text=request_text, intent=intent,
        proposed_slice=payload, classification=classification, classification_source=classification_source,
        spec_id=spec_id, contract_ids=contract_ids, expected_artifacts=expected_artifacts,
        expected_scope=expected_scope, estimate=estimate, acceptance_expectations=acceptance_expectations,
    )


@mcp.tool()
def start_slice(slice_id: str, actor_id: str, plan_id: str) -> dict[str, Any]:
    """Start a slice and bind it to the actor's persisted active plan."""
    blocked = _restore_gate("start_slice")
    if blocked:
        return blocked
    return _domain_call(get_service().start_slice, slice_id=slice_id, actor_id=actor_id, plan_id=plan_id)


@mcp.tool()
def update_slice_progress(slice_id: str, actor_id: str, plan_id: str, current_step: int | None = None, total_steps: int | None = None, blocker: str | None = None, execution_state: str | None = None) -> dict[str, Any]:
    """Persist slice progress; the same active plan that started the slice is mandatory."""
    blocked = _restore_gate("update_slice_progress")
    if blocked:
        return blocked
    return _domain_call(
        get_service().update_slice_progress, slice_id=slice_id, actor_id=actor_id, plan_id=plan_id,
        current_step=current_step, total_steps=total_steps, blocker=blocker, execution_state=execution_state,
    )


@mcp.tool()
def claim_done(slice_id: str, actor_id: str, plan_id: str, summary: str | None = None) -> dict[str, Any]:
    """Record DONE_CLAIMED under the slice's active plan; this never implies verification."""
    blocked = _restore_gate("claim_done")
    if blocked:
        return blocked
    return _domain_call(
        get_service().claim_done, slice_id=slice_id, actor_id=actor_id, plan_id=plan_id, summary=summary
    )


@mcp.tool()
def close_plan(plan_id: str, actor_id: str) -> dict[str, Any]:
    """Close an unbound plan so it stops generating collision traffic."""
    blocked = _restore_gate("close_plan")
    if blocked:
        return blocked
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
def completion_review(slice_id: str, changed_paths: list[str] | None = None) -> dict[str, Any]:
    """Build an AV/1 adversarial verification brief from persisted DONE claims, plan/spec obligations, Evidence and an optional observed change set."""
    return get_service().completion_review(slice_id=slice_id, changed_paths=changed_paths)


@mcp.tool()
def submit_verification_observation(
    slice_id: str,
    verifier_actor_id: str,
    verifier_token: str | None,
    claim: str,
    observation_type: str,
    status: str,
    evidence_type: str,
    evidence_class: str,
    source: str,
    original_evidence_id: str | None = None,
    artifact_id: str | None = None,
    reproduction: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist an independent AV/1 verifier observation. REPLAY requires an intact RB/1 binding; MangoMe does not execute the check itself."""
    return get_service().submit_verification_observation(
        slice_id=slice_id,
        verifier_actor_id=verifier_actor_id,
        verifier_token=verifier_token,
        claim=claim,
        observation_type=observation_type,
        status=status,
        evidence_type=evidence_type,
        evidence_class=evidence_class,
        source=source,
        original_evidence_id=original_evidence_id,
        artifact_id=artifact_id,
        reproduction=reproduction,
        details=details,
    )


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
    """Verify DONE_CLAIMED only when PASS gates (or gateless proof) include independent AV/1 observed PASS Evidence."""
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
def session_restore(workspace_root: str | None = None) -> dict[str, Any]:
    """Restore canonical session/work state without creating Project/Family/Spec state."""
    current = workspace_attachment_snapshot() or refresh_workspace_attachment(workspace_root)
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    project_key = workspace_project_key(str(Path(root).expanduser().resolve()))
    result = get_service().session_restore(project_key)
    set_session_restore_snapshot(result)
    return result


@mcp.tool()
def session_bootstrap(workspace_root: str | None = None) -> dict[str, Any]:
    """Host-start alias for session_restore; same read-only semantics."""
    return session_restore(workspace_root)


@mcp.tool()
def recovery_context(workspace_root: str | None = None) -> dict[str, Any]:
    """Return compact authoritative recovery state; never derive admitted work state from path discovery."""
    current = workspace_attachment_snapshot()
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    project_key = workspace_project_key(str(Path(root).expanduser().resolve()))
    try:
        return get_service().recovery_context(project_key)
    except KeyError:
        return {
            "source": "UNADMITTED",
            "workspace_project_key": project_key,
            "discovery_allowed_for_state_reconstruction": True,
            "rule": "No admitted workspace Project exists yet; candidate-only discovery may be used for onboarding, never as canonical truth.",
        }


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
def decode_uai_result(result_json: str, expected_context_hash: str) -> dict[str, Any]:
    """Validate and expand a compact UAI/1R worker result. This never mutates canonical state."""
    return decode_result_packet(result_json, expected_context_hash=expected_context_hash)


@mcp.tool()
def render_uai_result(result_json: str, expected_context_hash: str, language: str = "en") -> str:
    """Render a structured UAI/1R worker result into deterministic human-readable English or German."""
    return render_result_packet(result_json, language=language, expected_context_hash=expected_context_hash)


@mcp.tool()
def graph(entity_id: str) -> dict[str, Any]:
    """Return validated confirmed/suggested incoming and outgoing graph edges for an entity."""
    return get_service().graph(entity_id)


@mcp.tool()
def publish_worker_runtime(
    worker_key: str,
    router_actor_id: str,
    router_token: str | None = None,
    model_id: str | None = None,
    runtime_mode: str = "NORMAL",
    capabilities: list[str] | None = None,
    cost_class: str = "STANDARD",
    owner_gated: bool = False,
    max_parallel_tasks: int = 1,
    active: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a host-observed worker runtime snapshot through the router capability.

    This is not a worker self-report. Model identity, runtime mode, capabilities and
    cost are separate facts; hosts should refresh the snapshot when provider/tool
    availability changes (for example a degraded/reserve mode).
    """
    try:
        require_router(router_actor_id, router_token)
    except CapabilityDenied as exc:
        return {
            "ok": False,
            "error": {"code": "ROUTER_CAPABILITY_REQUIRED", "message": str(exc), "recoverable": True},
        }
    return _domain_call(
        get_service().register_worker_runtime,
        worker_key=worker_key, model_id=model_id, runtime_mode=runtime_mode,
        capabilities=capabilities, cost_class=cost_class, owner_gated=owner_gated,
        max_parallel_tasks=max_parallel_tasks, active=active, metadata=metadata,
    )


@mcp.tool()
def execution_eligibility(
    worker_key: str,
    required_capabilities: list[str] | None = None,
    cost_ceiling: str = "STANDARD",
    family_id: str | None = None,
    delegation_key: str | None = None,
    owner_approval_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate the worker's CURRENT runtime capabilities/cost before dispatch or a protected action.

    MangoMe returns an authorization decision but does not itself dispatch the model.
    The external orchestrator must enforce a negative decision at its real dispatch
    boundary and should re-check before capability-sensitive actions such as DEPLOY.
    """
    return _domain_call(
        get_service().check_execution_eligibility,
        worker_key=worker_key, required_capabilities=required_capabilities,
        cost_ceiling=cost_ceiling, family_id=family_id, delegation_key=delegation_key,
        owner_approval_id=owner_approval_id,
    )


@mcp.tool()
def authorize_delegation(
    family_id: str,
    coordinator_actor_id: str,
    worker_key: str,
    task_key: str,
    purpose: str,
    required_capabilities: list[str] | None = None,
    cost_ceiling: str = "STANDARD",
    input_scope: list[str] | None = None,
    owner_approval_id: str | None = None,
) -> dict[str, Any]:
    """Persist one bounded delegation authorization from current runtime/cost/concurrency state.

    This is a policy/coordination record, not the model dispatch itself. The host must
    refuse dispatch when `authorized` is false. High-cost workers require explicit
    owner approval and only one high-cost delegation may be active per family.
    """
    return _domain_call(
        get_service().authorize_delegation,
        family_id=family_id, coordinator_actor_id=coordinator_actor_id,
        worker_key=worker_key, task_key=task_key, purpose=purpose,
        required_capabilities=required_capabilities, cost_ceiling=cost_ceiling,
        input_scope=input_scope, owner_approval_id=owner_approval_id,
    )


@mcp.tool()
def complete_delegation(
    delegation_id: str,
    coordinator_actor_id: str,
    status: str = "COMPLETED",
    artifact: str | None = None,
    missing_delta: str | None = None,
    next_dependency: str | None = None,
) -> dict[str, Any]:
    """Checkpoint/close a bounded delegation so recovery can continue without rediscovery."""
    return _domain_call(
        get_service().complete_delegation,
        delegation_id=delegation_id, coordinator_actor_id=coordinator_actor_id,
        status=status, artifact=artifact, missing_delta=missing_delta,
        next_dependency=next_dependency,
    )


@mcp.tool()
def delegation_status(family_id: str) -> dict[str, Any]:
    """Return persisted delegation/checkpoint state for one family."""
    return _domain_call(get_service().delegation_status, family_id=family_id)


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
def discovery_scopes(workspace_root: str | None = None) -> dict[str, Any]:
    """Return portable typed discovery scopes; this does not scan or admit content."""
    current = workspace_attachment_snapshot() or refresh_workspace_attachment(workspace_root)
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    return {"workspace_root": root, "scopes": get_service().discovery_scopes(workspace_root=root)}


@mcp.tool()
def repository_locations(workspace_root: str | None = None) -> dict[str, Any]:
    """Return observed physical Git checkout/worktree locations without inferring project truth."""
    current = workspace_attachment_snapshot() or refresh_workspace_attachment(workspace_root)
    root = str((current or {}).get("workspace_root") or workspace_root or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd())
    return {"workspace_root": root, "repositories": get_service().repository_locations(workspace_root=root)}


@mcp.tool()
def bigbang_scan(roots: list[str], id_patterns: list[str] | None = None, include_git: bool = True) -> dict[str, Any]:
    """Candidate-only onboarding discovery. Forbidden as a recovery/state reconstruction path for admitted work."""
    blocked = _discovery_block(roots, "bigbang_scan")
    if blocked is not None:
        return blocked
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
    """Reconcile candidate discovery only before work admission; never rebuild admitted state from discovered records."""
    record_paths = [str(item.get("path") or "") for item in records if isinstance(item, dict) and item.get("path")]
    blocked = _discovery_block(record_paths or None, "reconcile_bigbang")
    if blocked is not None:
        return blocked
    return BigBangReconciler(get_service()).reconcile(records)  # type: ignore[return-value]


@mcp.tool()
def filesystem_scan(roots: list[str], max_files: int = 50000, max_depth: int = 16, max_hash_bytes: int = 67108864) -> dict[str, Any]:
    """Broad inventory for onboarding/maintenance; forbidden as state reconstruction for admitted work."""
    blocked = _discovery_block(roots, "filesystem_scan")
    if blocked is not None:
        return blocked
    return FilesystemScanner(get_service()).scan(
        roots, max_files=max_files, max_depth=max_depth, max_hash_bytes=max_hash_bytes
    )


@mcp.tool()
def filesystem_references(declared_id: str, present_only: bool = True, limit: int = 200) -> dict[str, Any]:
    """Targeted validation of an already-canonical identity; never use lexical references to invent recovery state."""
    if _known_admitted_workspace_roots():
        resolved = get_service().resolve(declared_id)
        if not any(resolved.get(key) for key in ("families", "contracts", "slices")):
            return {
                "ok": False,
                "error": {
                    "code": "UNKNOWN_CANONICAL_IDENTITY",
                    "message": "filesystem_references requires an identity already known to MangoMe when work is admitted.",
                    "recoverable": True,
                },
                "rule": "Lexical/path references may validate canonical identity; they may not create or reconstruct it.",
            }
    result = FilesystemScanner(get_service()).references(declared_id, present_only=present_only, limit=limit)
    result["mode"] = "TARGETED_CANONICAL_REFERENCE_VALIDATION"
    return result


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
