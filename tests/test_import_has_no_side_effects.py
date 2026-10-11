"""HANDOVER-002: importing mangome must not arm production bootstrap; only the managed entry points apply defaults."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")
KEYS = ["MANGOME_TRUST_BOUNDARY", "MANGOME_ZERO_TOUCH_BOOTSTRAP", "MANGOME_ZERO_TOUCH_HOST_MIGRATION", "MANGOME_ALLOW_EVAL_DATABASE"]


def run(code: str) -> dict:
    env = {"PATH": os.environ["PATH"], "PYTHONPATH": SRC}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_importing_mangome_and_submodules_does_not_change_environment():
    code = ("import os, json; before = dict(os.environ); import mangome, mangome.runtime, mangome.worker_mcp_server, mangome.mcp_server; "
            "print(json.dumps({k: os.environ.get(k) for k in %r} | {'changed': sorted(set(os.environ) ^ set(before))}))" % KEYS)
    result = run(code)
    assert result["changed"] == [] and all(result[k] is None for k in KEYS)


def test_managed_entry_points_apply_defaults_without_overriding_operator_values():
    code = ("import os, json; os.environ['MANGOME_ALLOW_EVAL_DATABASE'] = '1'; from mangome.managed_env import apply_managed_defaults; "
            "apply_managed_defaults(); print(json.dumps({k: os.environ.get(k) for k in %r}))" % KEYS)
    result = run(code)
    assert result == {"MANGOME_TRUST_BOUNDARY": "LOCAL_HOST", "MANGOME_ZERO_TOUCH_BOOTSTRAP": "1",
                      "MANGOME_ZERO_TOUCH_HOST_MIGRATION": "1", "MANGOME_ALLOW_EVAL_DATABASE": "1"}


def test_worker_and_advanced_server_main_call_apply_managed_defaults():
    for module in ("worker_mcp_server", "mcp_server", "cli"):
        text = (Path(SRC) / "mangome" / f"{module}.py").read_text()
        main_body = text[text.index("def main("):]
        assert "apply_managed_defaults()" in main_body, module
