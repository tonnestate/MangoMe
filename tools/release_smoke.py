from __future__ import annotations

import asyncio
import json
import os
import tempfile
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




def _database_identity_gate() -> None:
    """Prove upgrade adoption preserves an existing database identity without MongoDB."""
    import mangome.zero_touch as zero_touch

    tracked = (
        "MANGOME_MONGODB_URI", "MANGOME_MONGODB_URI_FILE",
        "MANGOME_DATABASE", "MANGOME_EXPECTED_DATABASE",
        "MANGOME_ADOPT_EXISTING_DATABASE",
    )
    saved = {key: os.environ.get(key) for key in tracked}
    old_probe = zero_touch._probe_uri
    old_live = zero_touch._live_process_candidates
    try:
        for key in tracked:
            os.environ.pop(key, None)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / "home"
            workspace = root / "workspace"
            workspace.mkdir(parents=True)
            backup = home / ".codex" / "config.toml.mangome.bak"
            backup.parent.mkdir(parents=True)
            backup.write_text(
                '[mcp_servers.mangome_eval]\n'
                'command = "/old/mangome"\n\n'
                '[mcp_servers.mangome_eval.env]\n'
                'MANGOME_DATABASE = "mangome_uai_eval"\n'
                'MANGOME_MONGODB_URI = "mongodb://legacy:secret@127.0.0.1:27017/?authSource=admin"\n',
                encoding="utf-8",
            )
            zero_touch._live_process_candidates = lambda *args, **kwargs: []
            zero_touch._probe_uri = lambda uri, database, **kwargs: {
                "database_ready": database == "mangome_uai_eval",
                "canonical_indexes_ready": database == "mangome_uai_eval",
            } if database == "mangome_uai_eval" else (_ for _ in ()).throw(
                zero_touch.ZeroTouchBootstrapError(
                    "BOOTSTRAP_AUTHORITY_REQUIRED", "wrong database for legacy credential"
                )
            )

            first = zero_touch.prepare_mongodb_runtime(
                workspace, database="mangome", home=str(home)
            )
            if first.get("database") != "mangome_uai_eval":
                raise RuntimeError(f"existing database identity was not adopted: {first}")
            if first.get("database_migration_performed") is not False:
                raise RuntimeError("zero-touch must never perform implicit database migration")
            if os.environ.get("MANGOME_DATABASE") != "mangome_uai_eval":
                raise RuntimeError("runtime environment did not adopt existing database identity")

            binding_path = home / ".config" / "mangome" / "database-binding.json"
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            if binding.get("database") != "mangome_uai_eval":
                raise RuntimeError("managed database identity was not persisted")

            backup.unlink()
            for key in ("MANGOME_DATABASE", "MANGOME_EXPECTED_DATABASE", "MANGOME_ADOPT_EXISTING_DATABASE"):
                os.environ.pop(key, None)
            second = zero_touch.prepare_mongodb_runtime(
                workspace, database="mangome", home=str(home)
            )
            if second.get("database") != "mangome_uai_eval":
                raise RuntimeError("persisted database identity did not survive restart simulation")
    finally:
        zero_touch._probe_uri = old_probe
        zero_touch._live_process_candidates = old_live
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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
    _database_identity_gate()
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
        "database_identity_gate": "PASS",
        "backend": "memory",
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(_main()), indent=2, sort_keys=True))
