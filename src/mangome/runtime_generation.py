from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable

from . import __version__

_MANAGED_MODULES = {"mangome.worker_mcp_server", "mangome.mcp_server"}


def _read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _cmdline(pid_dir: Path) -> list[str]:
    raw = _read_bytes(pid_dir / "cmdline")
    if not raw:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _environ(pid_dir: Path) -> dict[str, str]:
    raw = _read_bytes(pid_dir / "environ")
    if not raw:
        return {}
    out: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        out[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    return out


def _abspath(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def _current_identity() -> dict[str, Any]:
    from .operability import installation_identity

    return installation_identity()


def managed_runtime_generation_snapshot(
    *,
    proc_root: str | Path = "/proc",
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect managed MangoMe MCP generations without mutating any process.

    A process belongs to this managed installation only when it runs the same
    interpreter command path, launches a MangoMe MCP module, and carries the same
    expected source-root binding when that binding is available. Other Python/MCP
    processes are never adopted into the result merely because /proc exposes them.
    """

    current = dict(identity or _current_identity())
    current_python = _abspath(str(current.get("python") or sys.executable))
    current_root = str(current.get("source_root") or "").strip()
    current_version = str(current.get("version") or __version__)
    root = Path(proc_root)

    processes: list[dict[str, Any]] = []
    try:
        entries = list(root.iterdir())
    except OSError:
        entries = []

    for pid_dir in entries:
        if not pid_dir.name.isdigit():
            continue
        pid = int(pid_dir.name)
        if pid == os.getpid():
            continue

        argv = _cmdline(pid_dir)
        if len(argv) < 3 or argv[1] != "-m" or argv[2] not in _MANAGED_MODULES:
            continue
        if _abspath(argv[0]) != current_python:
            continue

        env = _environ(pid_dir)
        expected_root = str(env.get("MANGOME_EXPECTED_SOURCE_ROOT") or "").strip()
        if current_root and expected_root:
            try:
                if Path(expected_root).expanduser().resolve() != Path(current_root).expanduser().resolve():
                    continue
            except OSError:
                continue

        # Only touch processes that identify themselves as MangoMe-managed.
        managed_markers = (
            env.get("MANGOME_EXPECTED_VERSION"),
            env.get("MANGOME_DEPLOYMENT_ID"),
            env.get("MANGOME_AUTO_ATTACH"),
            expected_root,
        )
        if not any(str(value or "").strip() for value in managed_markers):
            continue

        expected_version = str(env.get("MANGOME_EXPECTED_VERSION") or "").strip()
        reasons: list[str] = []
        if expected_version and expected_version != current_version:
            reasons.append("VERSION_DRIFT")
        if current_root and expected_root:
            try:
                same_root = Path(expected_root).expanduser().resolve() == Path(current_root).expanduser().resolve()
            except OSError:
                same_root = False
            if not same_root:
                reasons.append("SOURCE_ROOT_DRIFT")

        state = "STALE_MANAGED_RUNTIME" if reasons else (
            "CURRENT_MANAGED_RUNTIME" if expected_version else "UNKNOWN_MANAGED_GENERATION"
        )
        processes.append({
            "pid": pid,
            "module": argv[2],
            "python": argv[0],
            "expected_version": expected_version or None,
            "expected_source_root": expected_root or None,
            "state": state,
            "reason_codes": reasons,
        })

    stale = [row for row in processes if row["state"] == "STALE_MANAGED_RUNTIME"]
    unknown = [row for row in processes if row["state"] == "UNKNOWN_MANAGED_GENERATION"]
    state = "GENERATION_DRIFT" if stale else ("UNKNOWN" if unknown else "READY")
    return {
        "state": state,
        "current_version": current_version,
        "current_python": current_python,
        "current_source_root": current_root or None,
        "active_processes": len(processes),
        "stale_processes": len(stale),
        "unknown_processes": len(unknown),
        "processes": processes,
        "rule": "ONE_MANAGED_INSTALLATION_ONE_ACTIVE_GENERATION; unknown processes are never killed automatically.",
    }


def reconcile_managed_runtime_generation(
    *,
    repair: bool,
    proc_root: str | Path = "/proc",
    identity: dict[str, Any] | None = None,
    timeout_seconds: float = 2.0,
    kill_fn: Callable[[int, int], None] = os.kill,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Report or recycle only stale managed MangoMe MCP processes.

    Repair is deliberately narrow: SIGTERM first, then SIGKILL only for a stale PID
    that still exists after the bounded wait. Current-generation and unknown-generation
    processes are never signalled.
    """

    before = managed_runtime_generation_snapshot(proc_root=proc_root, identity=identity)
    stale_pids = [int(row["pid"]) for row in before["processes"] if row["state"] == "STALE_MANAGED_RUNTIME"]
    if not repair or not stale_pids:
        return {**before, "repair_attempted": bool(repair), "terminated_pids": [], "killed_pids": []}

    terminated: list[int] = []
    killed: list[int] = []
    for pid in stale_pids:
        try:
            kill_fn(pid, signal.SIGTERM)
            terminated.append(pid)
        except ProcessLookupError:
            continue
        except PermissionError:
            # Fail closed: do not escalate to unrelated operator actions.
            continue

    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    proc_path = Path(proc_root)
    while terminated and time.monotonic() < deadline:
        remaining = [pid for pid in terminated if (proc_path / str(pid)).exists()]
        if not remaining:
            break
        sleep_fn(0.05)

    for pid in terminated:
        if not (proc_path / str(pid)).exists():
            continue
        try:
            kill_fn(pid, signal.SIGKILL)
            killed.append(pid)
        except (ProcessLookupError, PermissionError):
            continue

    after = managed_runtime_generation_snapshot(proc_root=proc_root, identity=identity)
    return {
        **after,
        "repair_attempted": True,
        "terminated_pids": terminated,
        "killed_pids": killed,
        "previous_state": before["state"],
        "previous_stale_processes": before["stale_processes"],
    }
