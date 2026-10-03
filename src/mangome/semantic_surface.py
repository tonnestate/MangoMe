from __future__ import annotations

from typing import Any

WORKER_TOOL_NAMES = (
    "mangome_status",
    "mangome_observe",
    "mangome_work",
    "mangome_effect",
    "mangome_verify",
    "mangome_query",
    "mangome_control",
)


def semantic_guidance(domain: str, operation: str, result: Any) -> dict[str, Any]:
    """Weak-agent guidance: make the next safe action explicit and deterministic."""
    domain = str(domain).upper()
    operation = str(operation).upper()
    if isinstance(result, dict) and result.get("ok") is False:
        code = str((result.get("error") or {}).get("code") or "OPERATION_FAILED")
        return {
            "disposition": "BLOCKED",
            "reason_code": code,
            "recommended_next_action": "INSPECT_STATUS_OR_REPAIR_INPUT",
            "allowed_next_actions": ["STATUS", "OBSERVE", "RETURN_TO_USER"],
            "forbidden_next_actions": ["BLIND_RETRY", "SYNTHESIZE_AUTHORITY", "SYNTHESIZE_STATE"],
        }

    if domain in {"STATUS", "OBSERVE"}:
        return {
            "disposition": "OBSERVATION_COMPLETE",
            "recommended_next_action": "RETURN_TO_USER",
            "allowed_next_actions": ["RETURN_TO_USER", "OBSERVE", "WORK_IF_EXPLICITLY_REQUESTED"],
            "forbidden_next_actions": ["AUTO_ADMIT", "AUTO_VERIFY", "AUTO_MUTATE"],
        }

    if domain == "WORK" and operation in {"RECONCILE", "RECONCILE_ASSIGNMENT"} and isinstance(result, dict):
        state = str(result.get("restore_state") or result.get("state") or result.get("disposition") or "")
        if state == "STATE_PARTIAL":
            return {
                "disposition": "RECOVERY_REQUIRED",
                "recommended_next_action": "BOUNDED_RECOVERY",
                "allowed_next_actions": ["OBSERVE", "RECOVERY", "RETURN_TO_USER"],
                "forbidden_next_actions": ["PRODUCTIVE_MUTATION", "FAKE_RECOVERY"],
            }
        if state == "STATE_NOT_FOUND":
            return {
                "disposition": "NO_ADMITTED_STATE",
                "recommended_next_action": "ADMIT_ONLY_IF_GENUINELY_NEW_WORK",
                "allowed_next_actions": ["ENTER_NEW_WORK_IF_EXPLICIT", "OBSERVE", "RETURN_TO_USER"],
                "forbidden_next_actions": ["SYNTHESIZE_RECOVERY"],
            }

    if domain == "EFFECT":
        state = str((result or {}).get("state") if isinstance(result, dict) else "").upper()
        if state in {"UNKNOWN", "PARTIAL"}:
            return {
                "disposition": "EFFECT_UNCERTAIN",
                "recommended_next_action": "OBSERVE_BEFORE_RETRY",
                "allowed_next_actions": ["OBSERVE_EFFECT", "RECONCILE_EFFECT", "RETURN_TO_USER"],
                "forbidden_next_actions": ["BLIND_RETRY"],
            }
        return {
            "disposition": "EFFECT_STEP_COMPLETE",
            "recommended_next_action": "FOLLOW_EFFECT_STATE_MACHINE",
            "allowed_next_actions": ["OBSERVE_EFFECT", "RECONCILE_EFFECT", "RETURN_TO_USER"],
            "forbidden_next_actions": ["BYPASS_EFFECT_JOURNAL"],
        }

    if domain == "VERIFY":
        return {
            "disposition": "ASSURANCE_STEP_COMPLETE",
            "recommended_next_action": "RETURN_OR_CONTINUE_ASSURANCE_FLOW",
            "allowed_next_actions": ["RETURN_TO_USER", "VERIFY", "CONTROL_IF_OWNER_ACTION_REQUIRED"],
            "forbidden_next_actions": ["SELF_VERIFY", "FABRICATE_EVIDENCE"],
        }

    if domain == "DELEGATE":
        return {
            "disposition": "DELEGATION_STEP_COMPLETE",
            "recommended_next_action": "DISPATCH_ONLY_IF_AUTHORIZED",
            "allowed_next_actions": ["DISPATCH_IF_AUTHORIZED", "CHECKPOINT", "RETURN_TO_USER"],
            "forbidden_next_actions": ["SELF_PUBLISH_RUNTIME", "BYPASS_CAPABILITY_GATE"],
        }

    return {
        "disposition": "GOVERNED_STEP_COMPLETE",
        "recommended_next_action": "FOLLOW_RETURNED_STATE",
        "allowed_next_actions": ["RETURN_TO_USER", "STATUS", "OBSERVE"],
        "forbidden_next_actions": ["SYNTHESIZE_AUTHORITY", "SYNTHESIZE_STATE"],
    }


def envelope(domain: str, operation: str, result: Any) -> dict[str, Any]:
    return {
        "semantic_surface": "MANGO/1",
        "domain": str(domain).upper(),
        "operation": str(operation).upper(),
        "result": result,
        "guidance": semantic_guidance(domain, operation, result),
    }
