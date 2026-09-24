from __future__ import annotations

import os
from typing import Any

# Import the canonical v0.1 server and extend the same MCPServer instance.
from .mcp_server import mcp
from .runtime import get_service


@mcp.tool()
def attach_artifact(
    logical_name: str,
    artifact_type: str,
    storage_system: str,
    physical_location: str,
    belongs_to: list[str] | None = None,
    checksum: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a physical artifact/reference without changing its external storage."""
    return get_service().attach_artifact(
        logical_name=logical_name,
        artifact_type=artifact_type,
        storage_system=storage_system,
        physical_location=physical_location,
        belongs_to=belongs_to,
        checksum=checksum,
        metadata=metadata,
    )


@mcp.tool()
def link_entities(
    from_type: str,
    from_id: str,
    relation: str,
    to_type: str,
    to_id: str,
    status: str = "CONFIRMED",
    source_actor_id: str | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Create a typed MangoMe graph relation such as ADDS_TO, AMENDS, EXTENDS or REPAIRS."""
    return get_service().link(
        from_type=from_type,
        from_id=from_id,
        relation=relation,
        to_type=to_type,
        to_id=to_id,
        status=status,
        source_actor_id=source_actor_id,
        confidence=confidence,
    )


@mcp.tool()
def close_plan(plan_id: str, actor_id: str) -> dict[str, Any]:
    """Close a plan when that actor no longer intends to execute it; prevents stale collision traffic."""
    return get_service().close_plan(plan_id, actor_id)


@mcp.tool()
def request_override(action_type: str, subject_id: str, requested_by: str, reason: str) -> dict[str, Any]:
    """Create an explicit approval request. Common actions are WAIVE_GATE and ACCEPT_SLICE."""
    return get_service().request_override(
        action_type=action_type,
        subject_id=subject_id,
        requested_by=requested_by,
        reason=reason,
    )


@mcp.tool()
def approve_override(
    approval_id: str,
    decided_by: str,
    decision_ref: str | None = None,
) -> dict[str, Any]:
    """Record an explicit approval decision. Authentication remains the MCP host's responsibility."""
    return get_service().approve_override(
        approval_id=approval_id,
        decided_by=decided_by,
        decision_ref=decision_ref,
    )


@mcp.tool()
def reject_override(
    approval_id: str,
    decided_by: str,
    decision_ref: str | None = None,
) -> dict[str, Any]:
    """Record an explicit rejection decision."""
    return get_service().reject_override(
        approval_id=approval_id,
        decided_by=decided_by,
        decision_ref=decision_ref,
    )


@mcp.tool()
def list_approvals(status: str | None = None, subject_id: str | None = None) -> list[dict[str, Any]]:
    """List approval requests, optionally filtered by status and subject."""
    return get_service().list_approvals(status=status, subject_id=subject_id)


@mcp.tool()
def set_gate_controlled(
    slice_id: str,
    gate_id: str,
    status: str,
    actor_id: str,
    evidence_ids: list[str] | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Set a gate with v0.1.1 integrity rules: PASS needs evidence; WAIVED needs approved override."""
    return get_service().set_gate(
        slice_id=slice_id,
        gate_id=gate_id,
        status=status,
        evidence_ids=evidence_ids,
        actor_id=actor_id,
        approval_id=approval_id,
    )


@mcp.tool()
def accept_slice(slice_id: str, approval_id: str, accepted_by: str) -> dict[str, Any]:
    """Move a VERIFIED slice to ACCEPTED using an approved ACCEPT_SLICE decision."""
    return get_service().accept_slice(
        slice_id=slice_id,
        approval_id=approval_id,
        accepted_by=accepted_by,
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
