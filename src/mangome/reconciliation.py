from __future__ import annotations

from typing import Any


def assignment_reconciliation_result(
    restored: dict[str, Any],
    *,
    workspace_root: str,
) -> dict[str, Any]:
    """Build the read-only RAE/1 disposition from canonical restore state.

    This function does not persist anything and deliberately does not receive the
    worker's tentative decomposition. The decomposition remains worker judgment;
    only the canonical restore state determines the governance disposition.
    """
    state = str(restored.get("restore_state") or "STATE_NOT_FOUND")

    if state == "STATE_FOUND":
        disposition = "RECONCILE_WITH_EXISTING_WORK"
        next_action = (
            "Map the tentative understanding/decomposition to existing WorkIdentity, baseline, plans and unfinished work; "
            "bind the current user turn before productive effect. Do not create replacement work merely because a fresh plan is easier."
        )
    elif state == "STATE_PARTIAL":
        disposition = "BOUNDED_RECOVERY_REQUIRED"
        next_action = (
            "Use canonical recovery context and bounded validation/backfill. Productive mutation remains blocked until the partial state is resolved."
        )
    else:
        disposition = "NEW_OR_UNADMITTED_WORK"
        next_action = (
            "If this is genuinely new work, admit it with enter_work using the actual user request. "
            "If it is historical/resume work, use explicit import/backfill; never manufacture a restore."
        )

    return {
        "reconciliation_protocol": "RAE/1",
        "rule": "THINK_FREELY_RECONCILE_BEFORE_EFFECT",
        "request_is_canonical_truth": False,
        "tentative_worker_decomposition_allowed": True,
        "canonicalization_allowed_by_this_call": False,
        "productive_effect_allowed_by_this_call": False,
        "workspace_root": workspace_root,
        "restore_state": state,
        "disposition": disposition,
        "next_action": next_action,
        "canonical_state": restored,
    }
