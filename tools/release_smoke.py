from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("MANGOME_BACKEND", "memory")

from mcp.client.client import Client

from mangome import __version__
from mangome import mcp_server as advanced
from mangome import worker_mcp_server as worker
from mangome.runtime import reset_service_for_tests

EXPECTED_WORKER_TOOLS = {
    "mangome_status",
    "mangome_observe",
    "mangome_query",
    "mangome_work",
    "mangome_effect",
    "mangome_verify",
    "mangome_control",
}


def _routed_capabilities() -> set[str]:
    routed: set[str] = set()
    for table in (
        worker._WORK,
        worker._EFFECT,
        worker._VERIFY,
        worker._CONTROL,
        worker._QUERY,
        worker._OBSERVE_ADVANCED,
    ):
        routed.update(table.values())
    routed.update(
        {
            "health",
            "workspace_status",
            "session_restore",
            "recovery_context",
            "session_bootstrap",
        }
    )
    return routed


async def _main() -> dict[str, object]:
    reset_service_for_tests()
    async with Client(worker.mcp, raise_exceptions=True) as client:
        worker_tools = {tool.name for tool in (await client.list_tools()).tools}
        health = await client.call_tool("mangome_status", {"scope": "HEALTH"})
        if health.is_error:
            raise RuntimeError("worker health MCP call failed")

    async with Client(advanced.mcp, raise_exceptions=True) as client:
        advanced_tools = {tool.name for tool in (await client.list_tools()).tools}

    routed = _routed_capabilities()
    missing = sorted(advanced_tools - routed)
    stale = sorted(routed - advanced_tools)

    if worker_tools != EXPECTED_WORKER_TOOLS:
        raise RuntimeError(
            f"worker surface mismatch: expected={sorted(EXPECTED_WORKER_TOOLS)} actual={sorted(worker_tools)}"
        )
    if missing or stale:
        raise RuntimeError(f"semantic routing mismatch: missing={missing} stale={stale}")

    return {
        "version": __version__,
        "worker_tool_count": len(worker_tools),
        "advanced_tool_count": len(advanced_tools),
        "routed_advanced_count": len(routed),
        "health_call": "PASS",
        "backend": "memory",
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(_main()), indent=2, sort_keys=True))
