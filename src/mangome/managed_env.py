"""Managed-runtime defaults and fail-soft startup checks, applied by ENTRY POINTS only (never as an import side effect)."""
from __future__ import annotations

import logging
import os
import sys
import traceback

# v0.3.20 managed single-host invariant: LOCAL_HOST is a cooperative host trust boundary, not a tamper-resistant verifier
# boundary. Operator-provided values always win (setdefault).
_DEFAULTS = {
    "MANGOME_TRUST_BOUNDARY": "LOCAL_HOST",
    "MANGOME_ZERO_TOUCH_BOOTSTRAP": "1",
    "MANGOME_ZERO_TOUCH_HOST_MIGRATION": "1",
    "MANGOME_ALLOW_EVAL_DATABASE": "0",
}


def apply_managed_defaults() -> None:
    for key, value in _DEFAULTS.items():
        os.environ.setdefault(key, value)


def startup_checks() -> None:
    """stdout is reserved for MCP; checks must never prevent `initialize`. Sibling repair (SIGTERM/SIGKILL of other
    sessions' servers) is opt-in via MANGOME_RECONCILE_REPAIR=1."""
    from .operability import enforce_expected_identity
    from .runtime_generation import reconcile_managed_runtime_generation

    logging.basicConfig(stream=sys.stderr)
    sys.excepthook = lambda t, v, tb: traceback.print_exception(t, v, tb, file=sys.stderr)
    try:
        enforce_expected_identity()
    except Exception as exc:  # noqa: BLE001
        print(f"mangome startup identity check failed (continuing degraded): {exc!r}", file=sys.stderr)
    try:
        reconcile_managed_runtime_generation(repair=os.environ.get("MANGOME_RECONCILE_REPAIR") == "1")
    except Exception as exc:  # noqa: BLE001
        print(f"mangome runtime generation check failed (continuing): {exc!r}", file=sys.stderr)
