from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def test_execution_receipt_tracks_durable_cost_and_context_savings():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("F", "Family")
    contract = svc.register_contract(declared_id="C-1", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(request_text="implement", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Implement", contract_ids=[contract["entity_id"]])
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"],
        actor_id="luna", intent="do it", contract_ids=[contract["entity_id"]],
        proposed_slices=[{"declared_id": "S1", "title": "Slice"}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="luna", plan_id=plan["entity_id"])
    model = svc.register_model(model_key="openai/luna", provider="OpenAI", access_path="OmniRoute")
    receipt = svc.record_execution_receipt(
        family_id=family["entity_id"], slice_id=sl["entity_id"], actor_id="luna", model_id=model["entity_id"],
        work_class="CODING", execution_cost=0.10, verification_cost=0.02, repair_cost=0.03,
        outcome="VERIFIED", context_tokens_raw=10000, context_tokens_compiled=2500,
    )
    assert receipt["durable_cost"] == 0.15
    assert receipt["context_tokens_saved"] == 7500
    stats = svc.model_stats(model_id=model["entity_id"], work_class="CODING")
    assert stats["attempts"] == 1
    assert stats["verified_outcomes"] == 1
    assert stats["cost_per_verified_outcome"] == 0.15
