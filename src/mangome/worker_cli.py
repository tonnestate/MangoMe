from __future__ import annotations

from typing import Any

from . import operability
from .cli import main as _advanced_main

_original_server_identity = operability._server_identity


def _worker_server_identity(
    workspace, *, backend: str, database: str, portable_workspace: bool = False
) -> dict[str, Any]:
    """Return the existing managed identity with the normal worker MCP module selected."""
    entry = _original_server_identity(
        workspace, backend=backend, database=database, portable_workspace=portable_workspace
    )
    entry = dict(entry)
    entry["args"] = ["-m", "mangome.worker_mcp_server"]
    return entry


def main() -> None:
    """Run the normal MangoMe CLI with managed setup/doctor bound to the worker facade.

    The v0.3.10c operability implementation remains unchanged for advanced/internal use.
    Its server-identity helper is patched only for the lifetime of this CLI invocation,
    so setup, doctor --repair and attestation all agree on the same normal-worker target.
    """
    previous = operability._server_identity
    operability._server_identity = _worker_server_identity
    try:
        _advanced_main()
    finally:
        operability._server_identity = previous


if __name__ == "__main__":
    main()
