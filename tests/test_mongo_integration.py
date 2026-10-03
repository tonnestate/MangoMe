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
    monkeypatch.setenv("MANGOME_RUNTIME_ROLE", "CONTROL")
    monkeypatch.setenv("MANGOME_RUNTIME_ACTOR", "control-plane")
    reset_service_for_tests()

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool(
                "create_project",
                {"project_key": "MCP-WIRE", "title": "MCP wire regression", "controller_actor_id": "control-plane"},
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


@pytest.mark.skipif(not URI, reason="MANGOME_TEST_MONGO_URI not configured")
def test_mongo_concurrent_enter_work_keeps_single_identity_and_active_slice():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from mangome.work_control import WorkGovernedMangoMeService

    database = f"mangome_concurrency_{uuid.uuid4().hex}"
    barrier = Barrier(2)

    class RacingService(WorkGovernedMangoMeService):
        def create_family(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            family = super().create_family(*args, **kwargs)
            barrier.wait(timeout=10)
            return family

    store_a = MongoStore(URI, database)
    store_b = MongoStore(URI, database)
    svc_a = RacingService(store_a)
    svc_b = RacingService(store_b)

    def enter(item):
        svc, actor = item
        return svc.enter_work(
            workspace_id="/tmp/mangome-v0320-mongo-race",
            workspace_title="mongo-race",
            actor_id=actor,
            request_text="Fix the login bug.",
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(enter, [(svc_a, "worker-a"), (svc_b, "worker-b")]))

        probe = MongoStore(URI, database)
        assert len(probe.find("projects")) == 1
        assert len(probe.find("families")) == 1
        assert len(probe.find("work_identities")) == 1
        assert len(probe.find("slices")) == 1
        active = [row for row in probe.find("slices") if row.get("execution_state") in {"STARTED", "ACTIVE"}]
        assert len(active) == 1
        assert {row["disposition"] for row in results} <= {
            "NEW_WORK_ADMITTED", "EXISTING_WORK_CANDIDATE", "CONCURRENT_WORK_REUSED"
        }
        probe.client.close()
    finally:
        store_a.client.drop_database(database)
        store_a.client.close()
        store_b.client.close()


@pytest.mark.skipif(not URI, reason="MANGOME_TEST_MONGO_URI not configured")
def test_v0320_unique_indexes_upgrade_over_legacy_nonunique_identity_indexes():
    database = f"mangome_index_upgrade_{uuid.uuid4().hex}"
    raw = MongoStore(URI, database)
    try:
        # Simulate v0.3.19 index names/options before the service creates v0.3.20
        # unique identity indexes under migration-safe names.
        raw.db["projects"].create_index([("project_key", 1)])
        raw.db["families"].create_index([("family_key", 1)])
        from mangome.work_control import WorkGovernedMangoMeService
        WorkGovernedMangoMeService(raw)
        project_indexes = raw.db["projects"].index_information()
        family_indexes = raw.db["families"].index_information()
        assert project_indexes["project_key_unique_v0320"]["unique"] is True
        assert family_indexes["family_key_unique_v0320"]["unique"] is True
    finally:
        raw.client.drop_database(database)
        raw.client.close()
