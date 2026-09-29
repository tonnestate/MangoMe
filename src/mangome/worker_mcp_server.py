from __future__ import annotations

import inspect
import json
import os
from typing import Any, Callable, Literal

from mcp.server import MCPServer

from . import __version__
from .context import ContextBudgetExceeded, ContextCompiler
from .runtime import get_service
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
    "ENTER_WORK": "enter_work",
    "PREPARE_ASSIGNMENT": "prepare_assignment",
    "BEGIN_WORK": "begin_work",
    "START_SLICE": "start_slice",
    "UPDATE_PROGRESS": "update_slice_progress",
    "CLAIM_DONE": "claim_done",
    "CHECKPOINT_WORK": "checkpoint_work",
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
    "VERIFY_SLICE": "verify_slice",
    "CLOSE_VERIFIED_SLICE": "close_verified_slice",
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
    "EXECUTION_ELIGIBILITY": "execution_eligibility",
    "AUTHORIZE_DELEGATION": "authorize_delegation",
    "COMPLETE_DELEGATION": "complete_delegation",
    "DELEGATION_STATUS": "delegation_status",
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
    "FAST_JUDGMENT_STATUS": "fast_judgment_status",
}


StatusScope = Literal["HEALTH", "WORKSPACE", "RESTORE", "RECOVERY"]
ObserveOperation = Literal[
    "STRUCTURAL_STATUS", "STRUCTURAL_SEARCH", "SYMBOL_LOOKUP", "SYMBOL_RELATIONS",
    "STRUCTURAL_CONTEXT", "IMPACT_FRONTIER", "WORKSPACE_STATUS", "RECOVERY_CONTEXT",
    "READ_CONTEXT", "COGNITIVE_HYGIENE", "COMPILE_CONTEXT",
]
QueryOperation = Literal[
    "RESOLVE", "PROJECT_OVERVIEW", "FAMILY_STATUS", "EFFECTIVE_FAMILY", "GRAPH", "TRUTH_AT",
    "TRUTH_ASSERTION_STATUS", "BITEMPORAL_STATUS", "TRUST_BOUNDARY_STATUS", "WORK_CONTEXT",
    "CONTRACT_STATE", "FAST_JUDGMENT_STATUS",
]
WorkOperation = Literal[
    "RECONCILE_ASSIGNMENT", "ENTER_WORK", "PREPARE_ASSIGNMENT", "BEGIN_WORK",
    "START_SLICE", "UPDATE_PROGRESS", "CLAIM_DONE", "CHECKPOINT_WORK",
]
EffectOperation = Literal[
    "RECORD_INTENT", "MARK_DISPATCHED", "RECORD_OBSERVATION", "RECONCILE", "STATUS", "CLOSURE_STATUS",
]
VerifyOperation = Literal[
    "VALIDATE_SLICE", "SUBMIT_EVIDENCE", "ATTEST_EVIDENCE", "COMPLETION_REVIEW", "SUBMIT_OBSERVATION",
    "VERIFY_SLICE", "CLOSE_VERIFIED_SLICE", "START_SCOPED_AUDIT", "AUDIT_CONTEXT", "AUDIT_STATUS",
    "AUDIT_MUTATION_ALLOWED", "RECORD_AUDIT_FINDING", "CLOSE_SCOPED_AUDIT",
]
ControlOperation = Literal[
    "REQUEST_OVERRIDE", "APPROVE_OVERRIDE", "REJECT_OVERRIDE", "LIST_APPROVALS",
    "EXECUTION_ELIGIBILITY", "AUTHORIZE_DELEGATION", "COMPLETE_DELEGATION",
    "DELEGATION_STATUS", "MAINTENANCE_DIAGNOSE",
]


def _normalize_operation(operation: str) -> str:
    return str(operation or "").strip().upper().replace("-", "_").replace(" ", "_")


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
    failed = isinstance(result, dict) and result.get("ok") is False
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
        return fn(**payload)
    except TypeError as exc:
        return {
            "ok": False,
            "error": {"code": "INVALID_CAPABILITY_ARGUMENTS", "message": str(exc), "recoverable": True},
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": {"code": type(exc).__name__, "message": str(exc), "recoverable": True},
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
    elif op == "WORKSPACE_STATUS":
        result = advanced.workspace_status(**data)
    elif op == "RECOVERY_CONTEXT":
        result = advanced.recovery_context(**data)
    elif op == "READ_CONTEXT":
        result = advanced.read_context(**data)
    elif op == "COGNITIVE_HYGIENE":
        call_data = {k: v for k, v in data.items() if k not in {"workspace_root", "structural_max_chars", "structural_max_items"}}
        result = advanced.cognitive_hygiene(**call_data)
        if isinstance(result, dict) and result.get("ok") is not False:
            query = str(data.get("query_text") or data.get("family_id") or "")
            structural = _optional_structural_context(data, query)
            if structural is not None:
                result = dict(result)
                result["structural_relevance"] = structural
                result["structural_rule"] = "PCH_MAY_USE_STRUCTURE_FOR_RELEVANCE_NOT_TRUTH_OR_ASSURANCE"
    elif op == "COMPILE_CONTEXT":
        result = _compile_context(data)
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
    """Enter/progress governed work through deterministic allow-listed transitions."""
    op = _normalize_operation(operation)
    result = _call_allowlisted(_WORK, op, dict(payload or {}))
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
            result["structural_rule"] = "SRA_MAY_EXPAND_INSPECTION_FRONTIER_NEVER_MUTATION_AUTHORITY"
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
    result = _call_allowlisted(_CONTROL, op, dict(payload or {}))
    return _guidance(
        "CONTROL", op, result,
        success_disposition="CONTROL_STEP_COMPLETE", recommended="FOLLOW_CONTROL_STATE",
        allowed=["OBSERVE", "QUERY", "CONTROL", "WORK", "RETURN_TO_USER"],
        forbidden=["FORGE_CAPABILITY", "BYPASS_OWNER_GATE", "SYNTHESIZE_APPROVAL"],
    )


def main() -> None:
    transport = os.environ.get("MANGOME_MCP_TRANSPORT", "stdio")
    kwargs: dict[str, Any] = {}
    if transport in {"streamable-http", "sse"}:
        kwargs["host"] = os.environ.get("MANGOME_MCP_HOST", "127.0.0.1")
        kwargs["port"] = int(os.environ.get("MANGOME_MCP_PORT", "8000"))
    mcp.run(transport=transport, **kwargs)


if __name__ == "__main__":
    main()
