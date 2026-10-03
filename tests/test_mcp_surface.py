from __future__ import annotations

import asyncio
import importlib.util

import pytest


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="mcp dependency not installed in local sandbox")
def test_mcp_v2_surface_lists_core_tools(monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "memory")

    async def run():
        from mcp.client.client import Client
        from mangome.mcp_server import mcp as advanced_mcp
        from mangome.worker_mcp_server import mcp as worker_mcp
        from mangome.runtime import reset_service_for_tests

        reset_service_for_tests()
        async with Client(worker_mcp) as client:
            result = await client.list_tools()
            names = {tool.name for tool in result.tools}
            assert names == {
                "mangome_status", "mangome_observe", "mangome_work", "mangome_effect",
                "mangome_verify", "mangome_query", "mangome_control",
            }

        async with Client(advanced_mcp) as client:
            result = await client.list_tools()
            names = {tool.name for tool in result.tools}
            required = {
                "health", "reconcile_assignment", "enter_work", "validate_slice",
                "record_effect_intent", "verify_slice", "bigbang_scan",
                "structural_status", "structural_refresh", "structural_search",
                "symbol_lookup", "symbol_relations", "structural_context", "impact_frontier",
            }
            assert required.issubset(names)

    asyncio.run(run())
