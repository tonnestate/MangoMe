from __future__ import annotations

import os
import uuid

import pytest

from mangome.integrity import IntegrityMangoMeService
from mangome.storage.mongo import MongoStore


URI = os.environ.get("MANGOME_TEST_MONGO_URI")


@pytest.mark.skipif(not URI, reason="MANGOME_TEST_MONGO_URI not configured")
def test_mongo_persists_verified_state_end_to_end():
    database = f"mangome_ci_{uuid.uuid4().hex}"
    store = MongoStore(URI, database)
    svc = IntegrityMangoMeService(store)
    try:
        family = svc.create_family("F-MONGO", "Mongo family")
        contract = svc.register_contract(declared_id="C-MONGO", family_id=family["entity_id"], title="Contract")
        req = svc.intake_request(
            request_text="implement mongo integration",
            classification="EXISTING_CONTRACT_WORK",
            family_id=family["entity_id"],
        )
        spec = svc.create_spec(
            family_id=family["entity_id"],
            objective="Persist state",
            contract_ids=[contract["entity_id"]],
        )
        plan = svc.submit_plan(
            family_id=family["entity_id"],
            request_id=req["entity_id"],
            spec_id=spec["entity_id"],
            actor_id="worker-a",
            intent="execute",
            proposed_slices=[{"declared_id": "S-MONGO", "title": "Mongo slice", "acceptance": ["mongo proof"]}],
        )
        sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
        svc.start_slice(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
        svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a", plan_id=plan["entity_id"])
        ev = svc.submit_evidence(
            subject_id=sl["entity_id"], evidence_type="INTEGRATION_TEST", evidence_class="TEST_RESULT", source="pytest", result="PASS", actor_id="verifier-b"
        )
        ev = svc.attest_evidence(evidence_id=ev["entity_id"], attested_by="verifier-b", capability_token=os.environ["MANGOME_VERIFIER_TOKEN"])
        gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
        svc.set_gate(
            slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]]
        )
        svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b", verifier_token=os.environ["MANGOME_VERIFIER_TOKEN"])

        fresh = IntegrityMangoMeService(MongoStore(URI, database))
        status = fresh.status(family["entity_id"])
        persisted = fresh.store.get("slices", sl["entity_id"])
        assert persisted["assurance_state"] == "VERIFIED"
        assert status["last_verified_slice_id"] == sl["entity_id"]
    finally:
        store.client.drop_database(database)
        store.client.close()


@pytest.mark.skipif(not URI, reason="MANGOME_TEST_MONGO_URI not configured")
def test_mongo_mcp_create_project_returns_serializable_result(monkeypatch):
    import asyncio

    from mcp.client.client import Client
    from mangome.mcp_server import mcp
    from mangome.runtime import reset_service_for_tests

    database = f"mangome_mcp_wire_{uuid.uuid4().hex}"
    monkeypatch.setenv("MANGOME_BACKEND", "mongo")
    monkeypatch.setenv("MANGOME_MONGODB_URI", URI)
    monkeypatch.setenv("MANGOME_DATABASE", database)
    reset_service_for_tests()

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(
                "create_project",
                {"project_key": "MCP-WIRE", "title": "MCP wire regression"},
            )
            assert result.is_error is False
            assert result.structured_content is not None
            payload = result.structured_content.get("result", result.structured_content)
            assert payload["project_key"] == "MCP-WIRE"
            assert "_id" not in payload

    try:
        asyncio.run(run())
    finally:
        cleanup = MongoStore(URI, database)
        cleanup.client.drop_database(database)
        cleanup.client.close()
        reset_service_for_tests()
