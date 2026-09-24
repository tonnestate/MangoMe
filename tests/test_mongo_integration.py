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
        svc.claim_done(slice_id=sl["entity_id"], actor_id="worker-a")
        ev = svc.submit_evidence(
            subject_id=sl["entity_id"], evidence_type="INTEGRATION_TEST", source="pytest", result="PASS", actor_id="verifier-b"
        )
        gate_id = svc.store.get("slices", sl["entity_id"])["gates"][0]["gate_id"]
        svc.set_gate(
            slice_id=sl["entity_id"], gate_id=gate_id, status="PASS", actor_id="verifier-b", evidence_ids=[ev["entity_id"]]
        )
        svc.verify_slice(slice_id=sl["entity_id"], verifier_actor_id="verifier-b")

        fresh = IntegrityMangoMeService(MongoStore(URI, database))
        status = fresh.status(family["entity_id"])
        persisted = fresh.store.get("slices", sl["entity_id"])
        assert persisted["assurance_state"] == "VERIFIED"
        assert status["last_verified_slice_id"] == sl["entity_id"]
    finally:
        store.client.drop_database(database)
        store.client.close()
