from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from . import operability
from .cli import main as _advanced_main

_original_server_identity = operability._server_identity
_WORKER_MODULE = "mangome.worker_mcp_server"


def _worker_server_identity(
    workspace, *, backend: str, database: str, portable_workspace: bool = False
) -> dict[str, Any]:
    """Return the canonical managed identity with the normal worker MCP selected."""
    entry = dict(
        _original_server_identity(
            workspace,
            backend=backend,
            database=database,
            portable_workspace=portable_workspace,
        )
    )
    entry["args"] = ["-m", _WORKER_MODULE]
    return entry


@contextmanager
def _worker_operability_target() -> Iterator[None]:
    """Scope the compatibility override to one normal CLI invocation only.

    Operability remains the single configuration implementation. The normal CLI
    changes only its MCP module target; the explicit advanced CLI keeps the
    precise legacy surface. The original helper is restored even on failure.
    """
    previous = operability._server_identity
    operability._server_identity = _worker_server_identity
    try:
        yield
    finally:
        operability._server_identity = previous


def main() -> None:
    """Run setup/doctor/attestation with the seven-tool worker endpoint."""
    with _worker_operability_target():
        _advanced_main()


if __name__ == "__main__":
    main()
