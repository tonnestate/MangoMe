from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

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

# These files have canonical nested locations. If any appears at repository root,
# a web-upload/release extraction flattened the delta and the installed package did
# not receive the intended fix. Fail before such a release is evaluated.
MISPLACED_ROOT_SHADOWS = {
    "runtime.py",
    "worker_mcp_server.py",
    "zero_touch.py",
    "operability.py",
    "control_plane.py",
    "repair_runtime_binding.py",
    "v0.3.12-release-notes.md",
    "SKILL.md",
    "SKILL (1).md",
}


def _repo_layout_gate() -> None:
    root = Path(__file__).resolve().parents[1]
    misplaced = sorted(name for name in MISPLACED_ROOT_SHADOWS if (root / name).exists())
    if misplaced:
        raise RuntimeError(
            "release delta was flattened into repository root: " + ", ".join(misplaced)
        )

    canonical = {
        "src/mangome/runtime.py",
        "src/mangome/worker_mcp_server.py",
        "src/mangome/zero_touch.py",
        "src/mangome/operability.py",
        "src/mangome/control_plane.py",
        "tools/repair_runtime_binding.py",
        "docs/v0.3.12-release-notes.md",
        "skill/mangome/SKILL.md",
        "src/mangome/skill/SKILL.md",
    }
    missing = sorted(path for path in canonical if not (root / path).is_file())
    if missing:
        raise RuntimeError("canonical release files missing: " + ", ".join(missing))

    if (root / "skill/mangome/SKILL.md").read_bytes() != (root / "src/mangome/skill/SKILL.md").read_bytes():
        raise RuntimeError("canonical/package MangoMe Skill copies differ")


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
    _repo_layout_gate()
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
        "layout_gate": "PASS",
        "backend": "memory",
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(_main()), indent=2, sort_keys=True))
