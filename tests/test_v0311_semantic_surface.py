from __future__ import annotations

import ast
from pathlib import Path

from mangome.semantic_surface import WORKER_TOOL_NAMES, envelope, semantic_guidance


def test_worker_surface_is_seven_tools():
    assert len(WORKER_TOOL_NAMES) == 7
    assert len(set(WORKER_TOOL_NAMES)) == 7


def test_observation_guidance_does_not_auto_mutate():
    wrapped = envelope("OBSERVE", "STRUCTURAL_SEARCH", {"matches": []})
    guide = wrapped["guidance"]
    assert guide["disposition"] == "OBSERVATION_COMPLETE"
    assert "AUTO_MUTATE" in guide["forbidden_next_actions"]
    assert guide["recommended_next_action"] == "RETURN_TO_USER"


def test_failure_guidance_forbids_blind_retry():
    guide = semantic_guidance("WORK", "PROGRESS", {"ok": False, "error": {"code": "RESTORE_NOT_EXECUTABLE"}})
    assert guide["disposition"] == "BLOCKED"
    assert "BLIND_RETRY" in guide["forbidden_next_actions"]


def test_worker_mcp_surface_is_small_and_advanced_surface_is_separate():
    root = Path(__file__).resolve().parents[1] / "src" / "mangome"
    worker_source = (root / "worker_mcp_server.py").read_text(encoding="utf-8")
    advanced_source = (root / "mcp_server.py").read_text(encoding="utf-8")
    for name in WORKER_TOOL_NAMES:
        assert f"def {name}(" in worker_source

    tree = ast.parse(worker_source)
    functions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert set(WORKER_TOOL_NAMES).issubset(functions)
    assert "mangome-mcp-advanced" not in worker_source
    assert "def create_project(" in advanced_source
