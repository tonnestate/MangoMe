"""Stdio contract: stdout is protocol-only, initialize is fast, no tool call kills the server."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SRC = str(Path(__file__).resolve().parents[1] / "src")

PROTO = "2025-06-18"


class Server:
    def __init__(self, extra_env: dict[str, str]):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "/tmp"), "PYTHONPATH": SRC, **extra_env}
        self.p = subprocess.Popen(
            [sys.executable, "-m", "mangome.worker_mcp_server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd="/tmp",
        )
        self.lines: list[str] = []
        self._id = 0

    def rpc(self, method: str, params: dict | None = None, timeout: float = 20.0) -> dict:
        self._id += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.p.stdout.readline()
            if not line:
                raise AssertionError(f"server closed stdout; exit={self.p.poll()} stderr={self.p.stderr.read()[-800:]}")
            self.lines.append(line)
            msg = json.loads(line)  # every stdout line must be JSON
            assert msg.get("jsonrpc") == "2.0", line
            if msg.get("id") == self._id:
                return msg
        raise AssertionError(f"timeout waiting for {method}")

    def tool(self, name: str, **args) -> dict:
        r = self.rpc("tools/call", {"name": name, "arguments": args})
        assert self.p.poll() is None, "server died"
        return r

    def close(self):
        self.p.terminate()
        self.p.wait(timeout=5)


def start(env: dict[str, str]) -> Server:
    s = Server(env)
    t = time.monotonic()
    r = s.rpc("initialize", {"protocolVersion": PROTO, "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
    assert "result" in r and time.monotonic() - t < 2.0 + 3.0  # ponytail: +3s import slack on cold cache
    s.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    s.p.stdin.flush()
    return s


MEM = {"MANGOME_BACKEND": "memory"}
# Unreachable DB; also a wrong identity binding that used to kill the process before initialize.
DOWN = {
    "MANGOME_BACKEND": "mongo", "MANGOME_MONGODB_URI": "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=300",
    "MANGOME_MONGO_SERVER_SELECTION_TIMEOUT_MS": "300", "MANGOME_MONGO_CONNECT_TIMEOUT_MS": "300",
    "MANGOME_DATABASE": "mangome_cc_test",
}


def _payload(r: dict) -> dict:
    res = r["result"]
    return res.get("structuredContent") or json.loads(res["content"][0]["text"])


def test_initialize_tools_health_memory():
    s = start(MEM)
    try:
        tools = s.rpc("tools/list")["result"]["tools"]
        assert {"mangome_status", "mangome_work"} <= {t["name"] for t in tools}
        assert _payload(s.tool("mangome_status", scope="HEALTH"))["ok"] is True
        assert _payload(s.tool("mangome_work", operation="RECONCILE_ASSIGNMENT", payload={"request_text": "x"}))
    finally:
        s.close()


def test_health_degraded_not_exit_when_db_unreachable():
    s = start(DOWN)
    try:
        h = s.tool("mangome_status", scope="HEALTH")
        assert s.p.poll() is None
        assert "DEGRADED" in json.dumps(h) or "UNAVAILABLE" in json.dumps(h)
    finally:
        s.close()


def test_wrong_identity_binding_does_not_prevent_initialize():
    s = start({**MEM, "MANGOME_EXPECTED_SOURCE_ROOT": "/nonexistent", "MANGOME_EXPECTED_VERSION": "0.0.1"})
    try:
        assert s.rpc("tools/list")["result"]["tools"]
    finally:
        s.close()


BAD_ARGS = [
    {}, {"operation": ""}, {"operation": None}, {"operation": 5}, {"operation": "X" * 100000},
    {"operation": "NOPE", "payload": "notadict"}, {"operation": "RECONCILE_ASSIGNMENT", "payload": {"request_text": 7}},
    {"operation": "RECONCILE_ASSIGNMENT", "payload": {"unknown_field": 1}}, {"scope": "???"},
]


@pytest.mark.parametrize("tool", ["mangome_status", "mangome_observe", "mangome_query", "mangome_work",
                                  "mangome_effect", "mangome_verify", "mangome_control"])
def test_bad_inputs_never_kill_server(tool):
    s = start(MEM)
    try:
        for args in BAD_ARGS:
            s.tool(tool, **args)  # may be a protocol error response, must not close the transport
        assert _payload(s.tool("mangome_status", scope="HEALTH"))["ok"] is True  # same transport still works
    finally:
        s.close()


def test_stderr_only_logging_stdout_is_json():
    s = start(MEM)
    try:
        s.tool("mangome_status", scope="HEALTH")
        assert all(json.loads(l) for l in s.lines)
    finally:
        s.close()
