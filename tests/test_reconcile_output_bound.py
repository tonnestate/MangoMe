"""D6: RECONCILE_ASSIGNMENT returned the whole canonical state (762 KB on the managed workspace) and exceeded the MCP client's output limit."""
import json

import pytest

pytest.importorskip("mcp")
from mangome import worker_mcp_server as w


def test_reconcile_response_is_bounded_and_says_so(monkeypatch):
    big = {"families": [{"family_id": str(i), "title": "x" * 200} for i in range(5000)], "projects": [{"p": 1}], "note": "n"}
    raw = {"disposition": "CONFLICT", "reason": "NO_MATCH", "canonical_state": big, "request_match": {}, "search_criteria": {}}
    monkeypatch.setattr(w, "_call_allowlisted", lambda table, op, data: dict(raw))
    out = w.mangome_work("RECONCILE_ASSIGNMENT", {"request_text": "something new"})
    assert len(json.dumps(out, default=str)) < 70_000
    summary = out["result"]["canonical_state"]
    assert summary["summarized"] is True and summary["counts"]["families"] == 5000 and summary["original_bytes"] > 100_000
    assert "CANONICAL_STATE_SUMMARIZED" in out["reason_codes"] and out["disposition"] == "CONFLICT"


def test_small_canonical_state_is_left_untouched(monkeypatch):
    raw = {"disposition": "CONFLICT", "reason": "NO_MATCH", "canonical_state": {"families": [1, 2]}}
    monkeypatch.setattr(w, "_call_allowlisted", lambda table, op, data: dict(raw))
    out = w.mangome_work("RECONCILE_ASSIGNMENT", {"request_text": "something new"})
    assert out["result"]["canonical_state"] == {"families": [1, 2]} and "CANONICAL_STATE_SUMMARIZED" not in out["reason_codes"]
