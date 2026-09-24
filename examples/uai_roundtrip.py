"""Minimal in-memory UAI/1 round-trip example."""
from mangome.interlingua import UAICompiler, render_uai_result
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore

svc = MangoMeService(InMemoryStore())
family = svc.create_family("DEMO", "UAI Demo")
contract = svc.register_contract(declared_id="DEMO-1", family_id=family["entity_id"], title="Demo contract")
spec = svc.create_spec(family_id=family["entity_id"], objective="Demonstrate UAI/1", contract_ids=[contract["entity_id"]])
work = svc.begin_work(
    family_id=family["entity_id"], actor_id="worker", request_text="demo", intent="show UAI",
    proposed_slice={"declared_id": "DEMO-S1", "title": "Demo slice"},
)
compiler = UAICompiler(svc)
compiled = compiler.compile(family["entity_id"], work["slice"]["entity_id"])
print(compiled["wire"])
print(compiled["metrics"])

result = {
    "v": "UAI/1R",
    "h": compiled["semantic_hash"],
    "st": "SUCCESS",
    "a": [["P", 1, 1], ["D", "demo complete"]],
}
print(render_uai_result(result, language="en", expected_context_hash=compiled["semantic_hash"]))
