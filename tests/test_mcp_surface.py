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
                "claim_done", "validate_slice", "record_effect_intent", "mark_effect_dispatched", "record_effect_observation", "reconcile_effect", "effect_status", "slice_closure_status", "attest_evidence", "completion_review", "submit_verification_observation", "verify_slice", "close_verified_slice", "project_overview", "recovery_context",
                "publish_worker_runtime", "execution_eligibility", "authorize_delegation", "complete_delegation", "delegation_status",
                "effective_family_view", "bigbang_scan", "reconcile_bigbang", "reconcile_bigbang_scan", "filesystem_inventory", "migrate_schema",
                "enter_work", "begin_work", "compile_uai_context", "expand_uai_context", "decode_uai_result", "render_uai_result",
                "filesystem_scan", "filesystem_references", "build_reproduction_binding", "evidence_freshness",
                "backfill_work_identity", "bind_work_turn", "work_context", "checkpoint_work", "register_playbook", "select_playbook",
                "cognitive_hygiene", "reconcile_assignment", "start_scoped_audit", "audit_context", "audit_status",
                "audit_mutation_allowed", "record_audit_finding", "close_scoped_audit",
                "assess_fast_judgment", "record_fast_judgment", "fast_judgment_status",
            }
            assert required.issubset(names)

    asyncio.run(run())
