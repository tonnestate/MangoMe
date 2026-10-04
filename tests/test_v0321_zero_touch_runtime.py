from __future__ import annotations

import os
import signal
from pathlib import Path

from mangome.operability import _MANGOME_ALWAYS_ON_INSTRUCTION
from mangome.runtime_generation import (
    managed_runtime_generation_snapshot,
    reconcile_managed_runtime_generation,
)


def _fake_proc(root: Path, pid: int, *, python: str, module: str, env: dict[str, str]) -> None:
    proc = root / str(pid)
    proc.mkdir(parents=True)
    (proc / "cmdline").write_bytes(
        b"\0".join([python.encode(), b"-m", module.encode()]) + b"\0"
    )
    (proc / "environ").write_bytes(
        b"\0".join(f"{k}={v}".encode() for k, v in env.items()) + b"\0"
    )


def test_generation_snapshot_detects_only_same_managed_installation(tmp_path: Path):
    py = "/managed/mangome/bin/python3"
    source = "/srv/MangoMe"
    identity = {"version": "0.3.21", "python": py, "source_root": source}

    _fake_proc(
        tmp_path, 101, python=py, module="mangome.worker_mcp_server",
        env={
            "MANGOME_EXPECTED_VERSION": "0.3.20",
            "MANGOME_EXPECTED_SOURCE_ROOT": source,
            "MANGOME_DEPLOYMENT_ID": "managed-local",
        },
    )
    _fake_proc(
        tmp_path, 102, python=py, module="mangome.worker_mcp_server",
        env={
            "MANGOME_EXPECTED_VERSION": "0.3.21",
            "MANGOME_EXPECTED_SOURCE_ROOT": source,
            "MANGOME_DEPLOYMENT_ID": "managed-local",
        },
    )
    _fake_proc(
        tmp_path, 103, python="/other/python3", module="mangome.worker_mcp_server",
        env={
            "MANGOME_EXPECTED_VERSION": "0.1.0",
            "MANGOME_EXPECTED_SOURCE_ROOT": "/other/MangoMe",
            "MANGOME_DEPLOYMENT_ID": "other",
        },
    )

    result = managed_runtime_generation_snapshot(proc_root=tmp_path, identity=identity)

    assert result["state"] == "GENERATION_DRIFT"
    assert result["active_processes"] == 2
    assert result["stale_processes"] == 1
    states = {row["pid"]: row["state"] for row in result["processes"]}
    assert states == {101: "STALE_MANAGED_RUNTIME", 102: "CURRENT_MANAGED_RUNTIME"}


def test_repair_signals_only_stale_managed_runtime(tmp_path: Path):
    py = "/managed/mangome/bin/python3"
    source = "/srv/MangoMe"
    identity = {"version": "0.3.21", "python": py, "source_root": source}
    _fake_proc(
        tmp_path, 201, python=py, module="mangome.worker_mcp_server",
        env={
            "MANGOME_EXPECTED_VERSION": "0.3.20",
            "MANGOME_EXPECTED_SOURCE_ROOT": source,
            "MANGOME_DEPLOYMENT_ID": "managed-local",
        },
    )
    _fake_proc(
        tmp_path, 202, python=py, module="mangome.worker_mcp_server",
        env={
            "MANGOME_EXPECTED_VERSION": "0.3.21",
            "MANGOME_EXPECTED_SOURCE_ROOT": source,
            "MANGOME_DEPLOYMENT_ID": "managed-local",
        },
    )

    calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        calls.append((pid, sig))
        if sig == signal.SIGTERM:
            # Simulate graceful process exit.
            for child in (tmp_path / str(pid)).iterdir():
                child.unlink()
            (tmp_path / str(pid)).rmdir()

    result = reconcile_managed_runtime_generation(
        repair=True,
        proc_root=tmp_path,
        identity=identity,
        timeout_seconds=0,
        kill_fn=fake_kill,
    )

    assert calls == [(201, signal.SIGTERM)]
    assert result["terminated_pids"] == [201]
    assert result["killed_pids"] == []
    assert result["stale_processes"] == 0


def test_always_on_instruction_honors_explicit_mangome_opt_out():
    text = _MANGOME_ALWAYS_ON_INSTRUCTION
    assert "EXPLICIT BYPASS RULE" in text
    assert "FRAMEWORK_BLOCKED != TASK_BLOCKED" in text
    assert "do not invoke MangoMe" in text
