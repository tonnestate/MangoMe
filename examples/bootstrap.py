from mangome.integrity import IntegrityMangoMeService
from mangome.storage.memory import InMemoryStore

svc = IntegrityMangoMeService(InMemoryStore())
project = svc.create_project("AVCOS", "AVCOS")
family = svc.create_family("AVCOS-OSEP", "OSEP", [project["entity_id"]], ["AVCOS"])
request = svc.intake_request(
    request_text="Continue OSEP phase 3B",
    classification="EXISTING_CONTRACT_WORK",
    classification_source="IntakeGov",
    family_id=family["entity_id"],
)
contract = svc.register_contract(
    declared_id="AVCOS-OSEP-001",
    family_id=family["entity_id"],
    title="OSEP",
    storage_system="filesystem",
    physical_location="/root/contracts/AVCOS-OSEP-001.md",
)
spec = svc.create_spec(
    family_id=family["entity_id"],
    objective="Complete OSEP phase 3B",
    contract_ids=[contract["entity_id"]],
    acceptance_criteria=["integration test passes", "runtime behavior observed"],
)
plan = svc.submit_plan(
    family_id=family["entity_id"],
    request_id=request["entity_id"],
    spec_id=spec["entity_id"],
    actor_id="codex",
    intent="Implement phase 3B",
    contract_ids=[contract["entity_id"]],
    proposed_slices=[{
        "declared_id": "OSEP-3B",
        "title": "Phase 3B",
        "acceptance": spec["acceptance_criteria"],
    }],
)
sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
svc.start_slice(slice_id=sl["entity_id"], actor_id="codex", plan_id=plan["entity_id"])
svc.update_slice_progress(slice_id=sl["entity_id"], actor_id="codex", plan_id=plan["entity_id"], current_step=1, total_steps=3)
print(svc.status(family["entity_id"]))
