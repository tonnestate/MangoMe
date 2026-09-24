from mangome.context import ContextCompiler
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def test_context_compiler_prefers_active_slice():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("F", "Family")
    contract = svc.register_contract(declared_id="C-1", family_id=family["entity_id"], title="Contract")
    req = svc.intake_request(request_text="continue", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"])
    spec = svc.create_spec(family_id=family["entity_id"], objective="Do it", contract_ids=[contract["entity_id"]])
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=req["entity_id"], spec_id=spec["entity_id"], actor_id="luna", intent="do it", contract_ids=[contract["entity_id"]],
        proposed_slices=[{"declared_id": "S-1", "title": "Slice"}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="luna", plan_id=plan["entity_id"])
    packet = ContextCompiler(svc).compile(family["entity_id"])
    assert packet["current_slice"]["entity_id"] == sl["entity_id"]
    assert packet["relevant_contracts"][0]["entity_id"] == contract["entity_id"]
