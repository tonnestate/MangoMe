from __future__ import annotations

import inspect
import json
import os
from typing import Any, Callable, Literal

from mcp.server import MCPServer

from . import __version__
from .context import ContextBudgetExceeded, ContextCompiler
from .runtime import get_service
from .operability import enforce_expected_identity
from .runtime_generation import reconcile_managed_runtime_generation
from .structural import StructuralIntelligence, unavailable_structural_context
from . import mcp_server as advanced

mcp = MCPServer(
    "MangoMe",
    description="Small semantic worker facade over MangoMe's advanced governance capabilities.",
    instructions=(
        "Use only the seven semantic MangoMe operations exposed here. "
        "OBSERVE and QUERY are read-only. WORK, EFFECT, VERIFY and CONTROL route deterministically "
        "to allow-listed MangoMe capabilities. Follow disposition/recommended_next_action and never "
        "treat structural observations as truth, evidence, assurance or mutation authority."
    ),
    version=__version__,
)


_WORK = {
    "RECONCILE_ASSIGNMENT": "reconcile_assignment",
    "INTAKE_REQUEST": "intake_request",
    "ENTER_WORK": "enter_work",
    "CREATE_PROJECT": "create_project",
    "CREATE_FAMILY": "create_family",
    "CREATE_SPEC": "create_spec",
    "REGISTER_CONTRACT": "register_contract",
    "IMPORT_CONTRACT_BUNDLE": "import_contract_bundle",
    "ATTACH_ARTIFACT": "attach_artifact",
    "LINK_ENTITIES": "link_entities",
    "PREPARE_ASSIGNMENT": "prepare_assignment",
    "BEGIN_WORK": "begin_work",
    "SUBMIT_PLAN": "submit_plan",
    "START_SLICE": "start_slice",
    "UPDATE_PROGRESS": "update_slice_progress",
    "CLAIM_DONE": "claim_done",
    "CLOSE_PLAN": "close_plan",
    "CHECKPOINT_WORK": "checkpoint_work",
    "RECORD_TRUTH_ASSERTION": "record_truth_assertion",
    "INVALIDATE_TRUTH_ASSERTION": "invalidate_truth_assertion",
    "RECORD_FAST_JUDGMENT": "record_fast_judgment",
    "FILESYSTEM_SCAN": "filesystem_scan",
    "REGISTER_PLAYBOOK": "register_playbook",
    "SELECT_PLAYBOOK": "select_playbook",
    "BIND_CONTRACT_TURN": "bind_contract_turn",
    "PROMOTE_CONTRACT_GENERATION": "promote_contract_generation",
    "RELEASE_CONTRACT_GENERATION_GRANT": "release_contract_generation_grant",
}
_EFFECT = {
    "RECORD_INTENT": "record_effect_intent",
    "MARK_DISPATCHED": "mark_effect_dispatched",
    "RECORD_OBSERVATION": "record_effect_observation",
    "RECONCILE": "reconcile_effect",
    "STATUS": "effect_status",
    "CLOSURE_STATUS": "slice_closure_status",
}
_VERIFY = {
    "VALIDATE_SLICE": "validate_slice",
    "SUBMIT_EVIDENCE": "submit_evidence",
    "ATTEST_EVIDENCE": "attest_evidence",
    "COMPLETION_REVIEW": "completion_review",
    "SUBMIT_OBSERVATION": "submit_verification_observation",
    "SET_GATE": "set_gate",
    "SET_GATE_CONTROLLED": "set_gate_controlled",
    "VERIFY_SLICE": "verify_slice",
    "CLOSE_VERIFIED_SLICE": "close_verified_slice",
    "ACCEPT_SLICE": "accept_slice",
    "BUILD_REPRODUCTION_BINDING": "build_reproduction_binding",
    "EVIDENCE_FRESHNESS": "evidence_freshness",
    "START_SCOPED_AUDIT": "start_scoped_audit",
    "AUDIT_CONTEXT": "audit_context",
    "AUDIT_STATUS": "audit_status",
    "AUDIT_MUTATION_ALLOWED": "audit_mutation_allowed",
    "RECORD_AUDIT_FINDING": "record_audit_finding",
    "CLOSE_SCOPED_AUDIT": "close_scoped_audit",
}
_CONTROL = {
    "REQUEST_OVERRIDE": "request_override",
    "APPROVE_OVERRIDE": "approve_override",
    "REJECT_OVERRIDE": "reject_override",
    "LIST_APPROVALS": "list_approvals",
    "PUBLISH_WORKER_RUNTIME": "publish_worker_runtime",
    "EXECUTION_ELIGIBILITY": "execution_eligibility",
    "AUTHORIZE_DELEGATION": "authorize_delegation",
    "COMPLETE_DELEGATION": "complete_delegation",
    "DELEGATION_STATUS": "delegation_status",
    "REGISTER_MODEL": "register_model",
    "RECORD_EXECUTION_RECEIPT": "record_execution_receipt",
    "BACKFILL_WORK_IDENTITY": "backfill_work_identity",
    "BIND_WORK_TURN": "bind_work_turn",
    "REFRESH_VIEWS": "refresh_views",
    "MIGRATE_SCHEMA": "migrate_schema",
    "MAINTENANCE_DIAGNOSE": "maintenance_diagnose",
}
_QUERY = {
    "RESOLVE": "resolve",
    "PROJECT_OVERVIEW": "project_overview",
    "FAMILY_STATUS": "status",
    "EFFECTIVE_FAMILY": "effective_family_view",
    "GRAPH": "graph",
    "TRUTH_AT": "truth_at",
    "TRUTH_ASSERTION_STATUS": "truth_assertion_status",
    "BITEMPORAL_STATUS": "bitemporal_truth_status",
    "TRUST_BOUNDARY_STATUS": "trust_boundary_status",
    "WORK_CONTEXT": "work_context",
    "CONTRACT_STATE": "contract_state",
    "ASSESS_FAST_JUDGMENT": "assess_fast_judgment",
    "FAST_JUDGMENT_STATUS": "fast_judgment_status",
    "DECODE_UAI_RESULT": "decode_uai_result",
    "RENDER_UAI_RESULT": "render_uai_result",
    "MODEL_STATS": "model_stats",
}
_OBSERVE_ADVANCED = {
    "WORKSPACE_STATUS": "workspace_status",
    "RECOVERY_CONTEXT": "recovery_context",
    "READ_CONTEXT": "read_context",
    "COGNITIVE_HYGIENE": "cognitive_hygiene",
    "COMPILE_EXECUTION_CONTEXT": "compile_execution_context",
    "COMPILE_UAI_CONTEXT": "compile_uai_context",
    "EXPAND_UAI_CONTEXT": "expand_uai_context",
    "DISCOVERY_SCOPES": "discovery_scopes",
    "REPOSITORY_LOCATIONS": "repository_locations",
    "BIGBANG_SCAN": "bigbang_scan",
    "RECONCILE_BIGBANG_SCAN": "reconcile_bigbang_scan",
    "RECONCILE_BIGBANG": "reconcile_bigbang",
    "FILESYSTEM_INVENTORY": "filesystem_inventory",
    "FILESYSTEM_REFERENCES": "filesystem_references",
}


StatusScope = Literal["HEALTH", "WORKSPACE", "RESTORE", "RECOVERY", "BOOTSTRAP"]
ObserveOperation = Literal[
    "STRUCTURAL_STATUS", "STRUCTURAL_SEARCH", "SYMBOL_LOOKUP", "SYMBOL_RELATIONS",
    "STRUCTURAL_CONTEXT", "IMPACT_FRONTIER", "WORKSPACE_STATUS", "RECOVERY_CONTEXT",
    "READ_CONTEXT", "COGNITIVE_HYGIENE", "COMPILE_CONTEXT", "COMPILE_EXECUTION_CONTEXT",
    "COMPILE_UAI_CONTEXT", "EXPAND_UAI_CONTEXT", "DISCOVERY_SCOPES", "REPOSITORY_LOCATIONS",
    "BIGBANG_SCAN", "RECONCILE_BIGBANG_SCAN", "RECONCILE_BIGBANG", "FILESYSTEM_INVENTORY",
    "FILESYSTEM_REFERENCES",
]
QueryOperation = Literal[
    "RESOLVE", "PROJECT_OVERVIEW", "FAMILY_STATUS", "EFFECTIVE_FAMILY", "GRAPH", "TRUTH_AT",
    "TRUTH_ASSERTION_STATUS", "BITEMPORAL_STATUS", "TRUST_BOUNDARY_STATUS", "WORK_CONTEXT",
    "CONTRACT_STATE", "ASSESS_FAST_JUDGMENT", "FAST_JUDGMENT_STATUS", "DECODE_UAI_RESULT",
    "RENDER_UAI_RESULT", "MODEL_STATS",
]
WorkOperation = Literal[
    "RECONCILE_ASSIGNMENT", "INTAKE_REQUEST", "ENTER_WORK", "CREATE_PROJECT", "CREATE_FAMILY",
    "CREATE_SPEC", "REGISTER_CONTRACT", "IMPORT_CONTRACT_BUNDLE", "ATTACH_ARTIFACT", "LINK_ENTITIES",
    "PREPARE_ASSIGNMENT", "BEGIN_WORK", "SUBMIT_PLAN", "START_SLICE", "UPDATE_PROGRESS",
    "CLAIM_DONE", "CLOSE_PLAN", "CHECKPOINT_WORK", "RECORD_TRUTH_ASSERTION",
    "INVALIDATE_TRUTH_ASSERTION", "RECORD_FAST_JUDGMENT", "FILESYSTEM_SCAN", "REGISTER_PLAYBOOK",
    "SELECT_PLAYBOOK", "BIND_CONTRACT_TURN", "PROMOTE_CONTRACT_GENERATION",
    "RELEASE_CONTRACT_GENERATION_GRANT",
]
EffectOperation = Literal[
    "RECORD_INTENT", "MARK_DISPATCHED", "RECORD_OBSERVATION", "RECONCILE", "STATUS", "CLOSURE_STATUS",
]
VerifyOperation = Literal[
    "VALIDATE_SLICE", "SUBMIT_EVIDENCE", "ATTEST_EVIDENCE", "COMPLETION_REVIEW", "SUBMIT_OBSERVATION",
    "SET_GATE", "SET_GATE_CONTROLLED", "VERIFY_SLICE", "CLOSE_VERIFIED_SLICE", "ACCEPT_SLICE",
    "BUILD_REPRODUCTION_BINDING", "EVIDENCE_FRESHNESS", "START_SCOPED_AUDIT", "AUDIT_CONTEXT",
    "AUDIT_STATUS", "AUDIT_MUTATION_ALLOWED", "RECORD_AUDIT_FINDING", "CLOSE_SCOPED_AUDIT"
]
ControlOperation = Literal[
    "REQUEST_OVERRIDE", "APPROVE_OVERRIDE", "REJECT_OVERRIDE", "LIST_APPROVALS",
    "PUBLISH_WORKER_RUNTIME", "EXECUTION_ELIGIBILITY", "AUTHORIZE_DELEGATION", "COMPLETE_DELEGATION",
    "DELEGATION_STATUS", "REGISTER_MODEL", "RECORD_EXECUTION_RECEIPT", "BACKFILL_WORK_IDENTITY",
    "BIND_WORK_TURN", "REFRESH_VIEWS", "MIGRATE_SCHEMA", "MAINTENANCE_DIAGNOSE"
]


def _normalize_operation(operation: str) -> str:
    return str(operation or "").strip().upper().replace("-", "_").replace(" ", "_")


def _managed_worker_actor_id() -> str:
    explicit = os.environ.get("MANGOME_RUNTIME_ACTOR", "").strip()
    if explicit:
        return explicit
    deployment = os.environ.get("MANGOME_DEPLOYMENT_ID", "managed-local").strip() or "managed-local"
    return f"worker:{deployment}"


def _reason_codes(result: Any) -> list[str]:
    if not isinstance(result, dict):
        return []
    codes: list[str] = []
    err = result.get("error")
    if isinstance(err, dict) and err.get("code"):
        codes.append(str(err["code"]))
    for key in ("reason_code", "reason_codes"):
        value = result.get(key)
        if isinstance(value, str):
            codes.append(value)
        elif isinstance(value, list):
            codes.extend(str(x) for x in value if x)
    return list(dict.fromkeys(codes))


def _guidance(
    semantic: str,
    operation: str,
    result: Any,
    *,
    success_disposition: str,
    recommended: str,
    allowed: list[str],
    forbidden: list[str] | None = None,
) -> dict[str, Any]:
    failed = isinstance(result, dict) and (result.get("ok") is False or isinstance(result.get("error"), dict))
    reasons = _reason_codes(result)
    if failed:
        return {
            "ok": False,
            "semantic_operation": semantic,
            "operation": operation,
            "disposition": "ACTION_BLOCKED",
            "recommended_next_action": "REPAIR_INPUT_OR_ESCALATE",
            "allowed_next_actions": ["OBSERVE", "QUERY", "RETURN_TO_USER", "ESCALATE"],
            "forbidden_next_actions": ["SYNTHESIZE_TRUTH", "BYPASS_GATE", "RETRY_EFFECT_BLINDLY"],
            "reason_codes": reasons or ["CAPABILITY_CALL_FAILED"],
            "result": result,
        }
    return {
        "ok": True,
        "semantic_operation": semantic,
        "operation": operation,
        "disposition": success_disposition,
        "recommended_next_action": recommended,
        "allowed_next_actions": allowed,
        "forbidden_next_actions": forbidden or ["SYNTHESIZE_TRUTH", "BYPASS_GATE"],
        "reason_codes": reasons,
        "result": result,
    }


def _call_allowlisted(table: dict[str, str], operation: str, payload: dict[str, Any]) -> Any:
    op = _normalize_operation(operation)
    target = table.get(op)
    if target is None:
        return {
            "ok": False,
            "error": {
                "code": "UNSUPPORTED_SEMANTIC_OPERATION",
                "message": f"Unsupported operation {op or '<empty>'}. Allowed: {', '.join(sorted(table))}",
                "recoverable": True,
            },
        }
    fn = getattr(advanced, target, None)
    if not callable(fn):
        return {
            "ok": False,
            "error": {"code": "CAPABILITY_UNAVAILABLE", "message": target, "recoverable": True},
        }
    try:
        signature = inspect.signature(fn)
        signature.bind(**payload)
    except TypeError as exc:
        return {
            "ok": False,
            "error": {"code": "INVALID_CAPABILITY_ARGUMENTS", "message": str(exc), "recoverable": True},
        }
    try:
        return fn(**payload)
    except Exception as exc:
        return {
            "ok": False,
            "error": {
                "code": str(getattr(exc, "code", type(exc).__name__)),
                "message": str(exc),
                "recoverable": True,
            },
        }


def _select_slice(ctx: dict[str, Any], slice_id: str | None) -> dict[str, Any] | None:
    slices = list(ctx.get("slices") or [])
    if slice_id:
        return next((x for x in slices if x.get("entity_id") == slice_id), None)
    active = set((ctx.get("status") or {}).get("active_slice_ids") or [])
    selected = next((x for x in slices if x.get("entity_id") in active), None)
    if selected is not None:
        return selected
    next_ids = (ctx.get("status") or {}).get("next_known_slice_ids") or []
    if next_ids:
        return next((x for x in slices if x.get("entity_id") == next_ids[0]), None)
    return None


def _minimal_context(family_id: str, slice_id: str | None, budget: int | None, reason: str) -> dict[str, Any]:
    ctx = get_service().get_context(family_id)
    selected = _select_slice(ctx, slice_id)
    family = ctx.get("family") or {}
    status = ctx.get("status") or {}
    payload: dict[str, Any] = {
        "context_status": "MINIMAL_VIABLE_CONTEXT",
        "family": {k: family.get(k) for k in ("entity_id", "family_key", "title")},
        "current_state": status,
        "current_slice": selected,
        "truth_level": status.get("truth_level", "CANONICAL_UNVERIFIED"),
        "degradation": {
            "reason_code": reason,
            "steps": ["DROP_OPTIONAL_STRUCTURAL", "HOT_ONLY", "CRITICAL_PATH_ONLY", "MINIMAL_VIABLE_CONTEXT"],
            "blocking": False,
        },
        "instruction": "Minimal cognitive projection only. Canonical truth/effect mutation gates remain unchanged.",
    }
    if budget and budget > 0:
        encoded = lambda x: len(json.dumps(x, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))
        if encoded(payload) > budget:
            payload["current_slice"] = None if selected is None else {
                "entity_id": selected.get("entity_id"),
                "title": selected.get("title"),
                "execution_state": selected.get("execution_state"),
                "assurance_state": selected.get("assurance_state"),
            }
        if encoded(payload) > budget:
            payload["current_state"] = {
                k: status.get(k) for k in (
                    "execution_state", "assurance_state", "truth_level", "active_slice_ids", "next_known_slice_ids"
                ) if k in status
            }
        if encoded(payload) > budget:
            return {
                "context_status": "CONTEXT_UNAVAILABLE",
                "reason_code": "MINIMAL_CONTEXT_EXCEEDS_BUDGET",
                "max_bytes": budget,
                "blocking": False,
                "mutation_policy": "TRUTH_AND_EFFECT_GATES_REMAIN_FAIL_CLOSED",
            }
    return payload


def _compile_context(payload: dict[str, Any]) -> dict[str, Any]:
    family_id = str(payload.get("family_id") or "")
    if not family_id:
        return {"ok": False, "error": {"code": "FAMILY_ID_REQUIRED", "message": "family_id is required", "recoverable": True}}
    slice_id = payload.get("slice_id")
    max_bytes = payload.get("max_bytes")
    budget = int(max_bytes) if max_bytes is not None else None
    try:
        compiled = ContextCompiler(get_service()).compile(family_id, slice_id, max_bytes=budget)
    except ContextBudgetExceeded:
        compiled = _minimal_context(family_id, slice_id, budget, "CONTEXT_BUDGET_EXCEEDED")
    except Exception as exc:
        return {"ok": False, "error": {"code": type(exc).__name__, "message": str(exc), "recoverable": True}}

    root = payload.get("workspace_root") or os.environ.get("MANGOME_WORKSPACE_ROOT")
    query = str(payload.get("query_text") or "").strip()
    if not query and isinstance(compiled, dict):
        current = compiled.get("current_slice") or {}
        query = str(current.get("objective") or current.get("title") or family_id)
    if root and compiled.get("context_status") != "CONTEXT_UNAVAILABLE":
        try:
            structural = StructuralIntelligence(root).structural_context(
                query or family_id,
                max_chars=max(512, int(payload.get("structural_max_chars") or 6000)),
                max_items=max(1, int(payload.get("structural_max_items") or 16)),
            )
            compiled["structural_context"] = structural
            compiled["structural_rule"] = "STRUCTURE_AFFECTS_RELEVANCE_AND_INSPECTION_ONLY_NOT_TRUTH_OR_MUTATION_AUTHORITY"
            if budget and budget > 0:
                size = len(json.dumps(compiled, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))
                if size > budget:
                    compiled.pop("structural_context", None)
                    compiled["structural_context"] = {
                        "status": "STRUCTURAL_CONTEXT_UNAVAILABLE",
                        "reason_code": "CONTEXT_BUDGET_RESERVED_FOR_CANONICAL_STATE",
                        "blocking": False,
                    }
        except Exception as exc:
            compiled["structural_context"] = unavailable_structural_context(str(root), exc)
    return compiled


def _optional_structural_context(payload: dict[str, Any], query: str) -> dict[str, Any] | None:
    root = payload.get("workspace_root") or os.environ.get("MANGOME_WORKSPACE_ROOT")
    if not root:
        return None
    try:
        return StructuralIntelligence(root).structural_context(
            query,
            max_chars=max(512, int(payload.get("structural_max_chars") or 4000)),
            max_items=max(1, int(payload.get("structural_max_items") or 12)),
        )
    except Exception as exc:
        return unavailable_structural_context(str(root), exc)


def _optional_impact_candidates(payload: dict[str, Any]) -> dict[str, Any] | None:
    root = payload.get("workspace_root") or os.environ.get("MANGOME_WORKSPACE_ROOT")
    if not root:
        return None
    refs = list(payload.get("target_refs") or [])
    ids = list(payload.get("target_ids") or [])
    target = str((refs or ids or [payload.get("objective") or ""])[0] or "").strip()
    if not target:
        return None
    try:
        result = StructuralIntelligence(root).impact_frontier(
            target,
            max_depth=max(0, min(6, int(payload.get("structural_max_depth") or 3))),
            max_nodes=max(1, min(96, int(payload.get("structural_max_nodes") or 48))),
            max_files=max(1, min(48, int(payload.get("structural_max_files") or 24))),
        )
        result["use"] = "INSPECTION_CANDIDATES_ONLY"
        result["audit_mutation_scope_changed"] = False
        return result
    except Exception as exc:
        return unavailable_structural_context(str(root), exc)


def _structural(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    root = payload.get("workspace_root") or os.environ.get("MANGOME_WORKSPACE_ROOT") or os.getcwd()
    engine = StructuralIntelligence(
        root,
        max_files=int(payload.get("max_files") or 512),
        max_file_bytes=int(payload.get("max_file_bytes") or 512 * 1024),
    )
    op = _normalize_operation(operation)
    try:
        if op == "STRUCTURAL_STATUS":
            return engine.structural_status()
        if op == "STRUCTURAL_SEARCH":
            return engine.structural_search(str(payload.get("query") or ""), limit=int(payload.get("limit") or 24))
        if op == "SYMBOL_LOOKUP":
            return engine.symbol_lookup(str(payload.get("symbol") or ""), limit=int(payload.get("limit") or 16))
        if op == "SYMBOL_RELATIONS":
            return engine.symbol_relations(
                str(payload.get("symbol") or ""),
                depth=int(payload.get("depth") or 1),
                max_nodes=int(payload.get("max_nodes") or 32),
            )
        if op == "STRUCTURAL_CONTEXT":
            return engine.structural_context(
                str(payload.get("query") or ""),
                max_chars=int(payload.get("max_chars") or 12000),
                max_items=int(payload.get("max_items") or 24),
            )
        if op == "IMPACT_FRONTIER":
            return engine.impact_frontier(
                str(payload.get("target") or ""),
                max_depth=int(payload.get("max_depth") or 4),
                max_nodes=int(payload.get("max_nodes") or 64),
                max_files=int(payload.get("impact_max_files") or 32),
                min_confidence=float(payload.get("min_confidence") or 0.0),
            )
    except Exception as exc:
        return unavailable_structural_context(str(root), exc)
    return {
        "ok": False,
        "error": {
            "code": "UNSUPPORTED_STRUCTURAL_OPERATION",
            "message": "Use STRUCTURAL_STATUS, STRUCTURAL_SEARCH, SYMBOL_LOOKUP, SYMBOL_RELATIONS, STRUCTURAL_CONTEXT or IMPACT_FRONTIER",
            "recoverable": True,
        },
    }


@mcp.tool()
def mangome_status(scope: StatusScope = "HEALTH", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return bounded MangoMe status without admitting or mutating work."""
    data = dict(payload or {})
    op = _normalize_operation(scope)
    if op == "HEALTH":
        result = advanced.health()
    elif op == "WORKSPACE":
        result = advanced.workspace_status(**data)
    elif op == "RESTORE":
        result = advanced.session_restore(**data)
    elif op == "RECOVERY":
        result = advanced.recovery_context(**data)
    elif op == "BOOTSTRAP":
        result = advanced.session_bootstrap(**data)
    else:
        result = {"ok": False, "error": {"code": "UNSUPPORTED_STATUS_SCOPE", "message": op, "recoverable": True}}
    return _guidance(
        "STATUS", op, result,
        success_disposition="STATUS_COMPLETE", recommended="RETURN_TO_USER",
        allowed=["RETURN_TO_USER", "OBSERVE", "QUERY"],
        forbidden=["ADMIT_WORK_WITHOUT_USER_INTENT", "SYNTHESIZE_RECOVERY_STATE", "MUTATE_CANONICAL_TRUTH"],
    )


@mcp.tool()
def mangome_observe(operation: ObserveOperation, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read/inspect derived or canonical context. OBSERVE never creates work identity or truth."""
    data = dict(payload or {})
    op = _normalize_operation(operation)
    if op in {"STRUCTURAL_STATUS", "STRUCTURAL_SEARCH", "SYMBOL_LOOKUP", "SYMBOL_RELATIONS", "STRUCTURAL_CONTEXT", "IMPACT_FRONTIER"}:
        result = _structural(op, data)
    elif op == "COGNITIVE_HYGIENE":
        call_data = {k: v for k, v in data.items() if k not in {"workspace_root", "structural_max_chars", "structural_max_items"}}
        result = _call_allowlisted(_OBSERVE_ADVANCED, op, call_data)
        if isinstance(result, dict) and result.get("ok") is not False:
            query = str(data.get("query_text") or data.get("family_id") or "")
            structural = _optional_structural_context(data, query)
            if structural is not None:
                result = dict(result)
                result["structural_relevance"] = structural
                result["structural_rule"] = "STRUCTURAL_RELEVANCE_IS_ADVISORY_AND_DOES_NOT_CHANGE_PCH_TEMPERATURE_TRUTH_OR_ASSURANCE"
    elif op == "COMPILE_CONTEXT":
        result = _compile_context(data)
    elif op in _OBSERVE_ADVANCED:
        result = _call_allowlisted(_OBSERVE_ADVANCED, op, data)
    else:
        result = {"ok": False, "error": {"code": "UNSUPPORTED_OBSERVE_OPERATION", "message": op, "recoverable": True}}
    return _guidance(
        "OBSERVE", op, result,
        success_disposition="OBSERVATION_COMPLETE", recommended="RETURN_TO_USER",
        allowed=["RETURN_TO_USER", "QUERY", "WORK"],
        forbidden=["MUTATE_FROM_OBSERVATION", "PROMOTE_MAP_TO_TRUTH", "EXPAND_MUTATION_SCOPE_FROM_IMPACT"],
    )


@mcp.tool()
def mangome_query(operation: QueryOperation, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve/read MangoMe identity, graph, truth and work state through an allow-listed query surface."""
    op = _normalize_operation(operation)
    result = _call_allowlisted(_QUERY, op, dict(payload or {}))
    return _guidance(
        "QUERY", op, result,
        success_disposition="QUERY_COMPLETE", recommended="RETURN_TO_USER",
        allowed=["RETURN_TO_USER", "OBSERVE", "WORK"],
        forbidden=["MUTATE_CANONICAL_TRUTH", "ASSUME_VERIFICATION"],
    )


@mcp.tool()
def mangome_work(operation: WorkOperation, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Enter/progress governed work through deterministic allow-listed transitions.

    The semantic worker facade is intentionally more automatic than the precise
    advanced capability surface. RECONCILE_ASSIGNMENT remains read-only underneath,
    but when it deterministically proves that the current request is new operational
    work, the facade immediately performs ENTER_WORK. Ordinary agents must not stop
    to ask the user for internal WorkIdentity vocabulary.
    """
    op = _normalize_operation(operation)
    data = dict(payload or {})

    if op == "ENTER_WORK" and not str(data.get("actor_id") or "").strip():
        data["actor_id"] = _managed_worker_actor_id()

    result = _call_allowlisted(_WORK, op, data)
    next_map = {
        "RECONCILE_ASSIGNMENT": "FOLLOW_RECONCILIATION_DISPOSITION",
        "ENTER_WORK": "PREPARE_ASSIGNMENT",
        "PREPARE_ASSIGNMENT": "CONTINUE_GOVERNED_WORK",
        "BEGIN_WORK": "EXECUTE_CURRENT_SLICE",
        "START_SLICE": "EXECUTE_CURRENT_SLICE",
        "UPDATE_PROGRESS": "CONTINUE_GOVERNED_WORK",
        "CLAIM_DONE": "VERIFY",
        "CHECKPOINT_WORK": "CONTINUE_GOVERNED_WORK",
    }

    if op == "RECONCILE_ASSIGNMENT" and isinstance(result, dict):
        if result.get("disposition") == "MANGOME_BYPASSED_BY_USER":
            return _guidance(
                "WORK", op, result,
                success_disposition="MANGOME_BYPASSED_BY_USER",
                recommended="CONTINUE_TASK_WITHOUT_MANGOME",
                allowed=["RETURN_TO_USER"],
                forbidden=["REPAIR_MANGOME_FOR_THIS_TASK", "INVENT_CONTROL_AUTHORITY", "RETRY_MANGOME_FOR_THIS_TASK"],
            )

        if result.get("disposition") == "NEW_WORK_READY_FOR_AUTO_ADMISSION":
            request_text = str(data.get("request_text") or "").strip()
            if not request_text:
                return _guidance(
                    "WORK", op, {
                        "ok": False,
                        "error": {
                            "code": "REQUEST_TEXT_REQUIRED",
                            "message": "zero-touch new-work admission requires request_text",
                            "recoverable": True,
                        },
                    },
                    success_disposition="ACTION_BLOCKED",
                    recommended="REPAIR_INPUT_OR_ESCALATE",
                    allowed=["RETURN_TO_USER"],
                )
            admission = _call_allowlisted(
                _WORK,
                "ENTER_WORK",
                {
                    "actor_id": str(data.get("actor_id") or _managed_worker_actor_id()),
                    "request_text": request_text,
                },
            )
            if isinstance(admission, dict) and admission.get("ok") is False:
                return _guidance(
                    "WORK", op, {
                        "ok": False,
                        "error": {
                            "code": "ZERO_TOUCH_ADMISSION_FAILED",
                            "message": str(admission),
                            "recoverable": True,
                        },
                        "reconciliation": result,
                        "admission": admission,
                    },
                    success_disposition="ACTION_BLOCKED",
                    recommended="REPAIR_INPUT_OR_ESCALATE",
                    allowed=["OBSERVE", "QUERY", "RETURN_TO_USER"],
                )
            combined = {
                "reconciliation": result,
                "admission": admission,
                "zero_touch": {
                    "auto_admitted": True,
                    "user_confirmation_required": False,
                    "actor_id_source": "MANGOME_RUNTIME_ACTOR_OR_MANAGED_WORKER_DEFAULT",
                },
            }
            return _guidance(
                "WORK", op, combined,
                success_disposition="NEW_WORK_AUTO_ADMITTED",
                recommended="EXECUTE_CURRENT_SLICE",
                allowed=["OBSERVE", "QUERY", "WORK", "EFFECT", "VERIFY"],
                forbidden=["ASK_USER_FOR_WORK_REF", "ASK_USER_TO_CONFIRM_NEW_WORK", "MARK_TASK_BLOCKED_FOR_MISSING_WORK_IDENTITY"],
            )

        if result.get("disposition") == "CURRENT_REQUEST_MATCHES_EXISTING_WORK":
            return _guidance(
                "WORK", op, result,
                success_disposition="EXISTING_WORK_MATCHED",
                recommended="BIND_AND_CONTINUE_EXISTING_WORK",
                allowed=["WORK", "OBSERVE", "QUERY"],
                forbidden=["ASK_USER_FOR_KNOWN_WORK_REF", "CREATE_UNRELATED_REPLACEMENT_WORK", "MARK_TASK_BLOCKED_FOR_MISSING_WORK_IDENTITY"],
            )

    return _guidance(
        "WORK", op, result,
        success_disposition="WORK_TRANSITION_COMPLETE", recommended=next_map.get(op, "CONTINUE_GOVERNED_WORK"),
        allowed=["OBSERVE", "QUERY", "WORK", "EFFECT", "VERIFY", "RETURN_TO_USER"],
        forbidden=["BYPASS_WORK_IDENTITY", "SYNTHESIZE_TRUTH", "MARK_VERIFIED_FROM_DONE_CLAIM"],
    )


@mcp.tool()
def mangome_effect(operation: EffectOperation, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record/reconcile external effects. Unknown outcomes must not be blindly retried."""
    op = _normalize_operation(operation)
    result = _call_allowlisted(_EFFECT, op, dict(payload or {}))
    next_map = {
        "RECORD_INTENT": "DISPATCH_EFFECT",
        "MARK_DISPATCHED": "RECORD_EFFECT_OBSERVATION",
        "RECORD_OBSERVATION": "RECONCILE_EFFECT",
        "RECONCILE": "CHECK_EFFECT_STATUS",
        "STATUS": "RETURN_TO_USER",
        "CLOSURE_STATUS": "RETURN_TO_USER",
    }
    return _guidance(
        "EFFECT", op, result,
        success_disposition="EFFECT_STATE_UPDATED", recommended=next_map.get(op, "CHECK_EFFECT_STATUS"),
        allowed=["OBSERVE", "QUERY", "EFFECT", "VERIFY", "RETURN_TO_USER"],
        forbidden=["BLIND_RETRY_UNKNOWN_EFFECT", "BYPASS_EFFECT_JOURNAL", "SYNTHESIZE_EFFECT_SUCCESS"],
    )


@mcp.tool()
def mangome_verify(operation: VerifyOperation, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate, audit and verify without allowing a worker DONE claim to become trusted completion."""
    op = _normalize_operation(operation)
    data = dict(payload or {})
    call_data = dict(data)
    if op == "START_SCOPED_AUDIT":
        for key in ("workspace_root", "structural_max_depth", "structural_max_nodes", "structural_max_files"):
            call_data.pop(key, None)
    result = _call_allowlisted(_VERIFY, op, call_data)
    if op == "START_SCOPED_AUDIT" and isinstance(result, dict) and result.get("ok") is not False:
        impact = _optional_impact_candidates(data)
        if impact is not None:
            result = dict(result)
            result["structural_impact_candidates"] = impact
            result["structural_rule"] = "STRUCTURAL_IMPACT_IS_ADVISORY_BESIDE_SRA_AND_NEVER_EXPANDS_PERSISTED_MUTATION_AUTHORITY"
    return _guidance(
        "VERIFY", op, result,
        success_disposition="VERIFICATION_STEP_COMPLETE", recommended="FOLLOW_VERIFICATION_STATE",
        allowed=["OBSERVE", "QUERY", "VERIFY", "RETURN_TO_USER"],
        forbidden=["SELF_ATTEST_WITHOUT_AUTHORITY", "PROMOTE_CLAIM_TO_VERIFIED", "BYPASS_REQUIRED_EVIDENCE"],
    )


@mcp.tool()
def mangome_control(operation: ControlOperation, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Perform explicit controller/router/owner operations through the advanced capability layer."""
    op = _normalize_operation(operation)
    data = dict(payload or {})
    result = _call_allowlisted(_CONTROL, op, data)
    return _guidance(
        "CONTROL", op, result,
        success_disposition="CONTROL_STEP_COMPLETE", recommended="FOLLOW_CONTROL_STATE",
        allowed=["OBSERVE", "QUERY", "CONTROL", "WORK", "RETURN_TO_USER"],
        forbidden=["FORGE_CAPABILITY", "BYPASS_OWNER_GATE", "SYNTHESIZE_APPROVAL"],
    )


def main() -> None:
    enforce_expected_identity()
    reconcile_managed_runtime_generation(repair=True)
    transport = os.environ.get("MANGOME_MCP_TRANSPORT", "stdio")
    kwargs: dict[str, Any] = {}
    if transport in {"streamable-http", "sse"}:
        kwargs["host"] = os.environ.get("MANGOME_MCP_HOST", "127.0.0.1")
        kwargs["port"] = int(os.environ.get("MANGOME_MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
