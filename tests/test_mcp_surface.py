from __future__ import annotations

import asyncio
import importlib.util

import pytest


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="mcp dependency not installed in local sandbox")
def test_mcp_v2_surface_lists_core_tools(monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")

    async def run():
        from mcp.client.client import Client
        from mangome.mcp_server import mcp
        from mangome.runtime import reset_service_for_tests

        reset_service_for_tests()
        async with Client(mcp) as client:
            result = await client.list_tools()
            names = {tool.name for tool in result.tools}
            required = {
                "health", "workspace_status", "intake_request", "submit_plan", "start_slice", "update_slice_progress",
                "claim_done", "attest_evidence", "completion_review", "submit_verification_observation", "verify_slice", "project_overview", "recovery_context",
                "publish_worker_runtime", "execution_eligibility", "authorize_delegation", "complete_delegation", "delegation_status",
                "effective_family_view", "bigbang_scan", "reconcile_bigbang", "migrate_schema",
                "enter_work", "begin_work", "compile_uai_context", "expand_uai_context", "decode_uai_result", "render_uai_result",
                "filesystem_scan", "filesystem_references", "build_reproduction_binding", "evidence_freshness",
            }
            assert required.issubset(names)

    asyncio.run(run())
