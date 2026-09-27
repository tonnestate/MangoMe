from __future__ import annotations

from mangome.context import ContextCompiler
from mangome.hygiene import CognitiveHygieneService
from mangome.interlingua import UAICompiler
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def _fixture():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("PCH", "Persistent Cognitive Hygiene")
    old = svc.register_contract(declared_id="PCH-OLD", family_id=family["entity_id"], title="Legacy route implementation")
    current = svc.register_contract(declared_id="PCH-CUR", family_id=family["entity_id"], title="Current route implementation")
    svc.link(
        from_type="CONTRACT", from_id=current["entity_id"], relation="SUPERSEDES",
        to_type="CONTRACT", to_id=old["entity_id"], status="CONFIRMED",
    )
    spec = svc.create_spec(
        family_id=family["entity_id"], objective="Use the current route implementation",
        contract_ids=[current["entity_id"]], acceptance_criteria=["current route works"],
    )
    request = svc.intake_request(
        request_text="Implement the current route", classification="EXISTING_CONTRACT_WORK", family_id=family["entity_id"]
    )
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=request["entity_id"], spec_id=spec["entity_id"],
        actor_id="worker", intent="implement current route", contract_ids=[current["entity_id"]],
        proposed_slices=[{"declared_id": "PCH-S1", "title": "Current route", "objective": "Implement current route"}],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="worker", plan_id=plan["entity_id"])
    evidence = svc.submit_evidence(
        subject_id=old["entity_id"], evidence_type="LEGACY_PROOF", evidence_class="TEST_RESULT",
        source="legacy-suite", result="PASS", actor_id="worker",
    )
    svc.store.update("evidence", evidence["entity_id"], {"trust": "VERIFIER_ATTESTED"})
    return svc, family, old, current, sl


def _thermal(result):
    return {row["entity_id"]: row for row in result["thermal_map"]}


def test_pch_supersedes_without_erasing_and_targeted_history_can_reheat():
    svc, family, old, current, sl = _fixture()
    before = svc.store.get("contracts", old["entity_id"])

    normal = CognitiveHygieneService(svc).evaluate(
        family["entity_id"], sl["entity_id"], query_text="Implement the current route implementation"
    )
    normal_map = _thermal(normal)
    assert normal_map[current["entity_id"]]["band"] == "HOT"
    assert normal_map[current["entity_id"]]["resident"] is True
    assert normal_map[old["entity_id"]]["band"] == "COLD"
    assert normal_map[old["entity_id"]]["resident"] is False

    historical = CognitiveHygieneService(svc).evaluate(
        family["entity_id"], sl["entity_id"], query_text="Legacy route implementation"
    )
    historical_map = _thermal(historical)
    assert historical_map[old["entity_id"]]["temperature"] > normal_map[old["entity_id"]]["temperature"]
    assert historical_map[old["entity_id"]]["band"] in {"WARM", "HOT"}
    assert historical_map[old["entity_id"]]["resident"] is True

    after = svc.store.get("contracts", old["entity_id"])
    assert after == before
    assert normal["policy"]["principles"][-1] == "COLD_MEANS_NON_RESIDENT_NOT_FORGOTTEN"


def test_pch_active_budget_never_evicts_pinned_roots():
    svc, family, old, current, sl = _fixture()
    for idx in range(8):
        svc.submit_evidence(
            subject_id=sl["entity_id"], evidence_type=f"OBS-{idx}", evidence_class="RUNTIME_OBSERVATION",
            source="runtime", result=None, actor_id="worker",
        )

    result = CognitiveHygieneService(svc).evaluate(
        family["entity_id"], sl["entity_id"], query_text="current route", max_active_objects=1
    )
    thermal = _thermal(result)
    pinned = [row for row in result["thermal_map"] if row["pinned"]]
    assert result["policy"]["pinned_budget_override"] is True
    assert result["policy"]["effective_active_budget"] == len(pinned)
    assert all(row["resident"] for row in pinned)
    assert thermal[current["entity_id"]]["resident"] is True
    assert result["counts"]["evicted"] > 0
    assert len(svc.store.find("evidence")) == 9


def test_context_compiler_uses_hygiene_before_byte_compilation(monkeypatch):
    svc, family, old, current, sl = _fixture()
    for idx in range(5):
        svc.submit_evidence(
            subject_id=sl["entity_id"], evidence_type=f"NOISE-{idx}", evidence_class="OTHER",
            source="noise", result=None, actor_id="worker",
        )
    monkeypatch.setenv("MANGOME_ACTIVE_MAX_OBJECTS", "5")

    compiled = ContextCompiler(svc).compile(family["entity_id"], sl["entity_id"])
    assert compiled["cognitive_hygiene"]["policy"]["version"] == "PCH/1"
    assert compiled["cognitive_hygiene"]["counts"]["evicted"] > 0
    assert current["entity_id"] in compiled["cognitive_hygiene"]["working_set_ids"]
    assert old["entity_id"] not in compiled["cognitive_hygiene"]["working_set_ids"]
    assert all(e["entity_id"] in compiled["cognitive_hygiene"]["working_set_ids"] for e in compiled["evidence"])


def test_uai_round_trip_carries_hygiene_semantics():
    svc, family, _, _, sl = _fixture()
    compiler = UAICompiler(svc)
    projection = compiler.semantic_projection(family["entity_id"], sl["entity_id"])
    assert projection["hygiene"]["policy"] == "PCH/1"
    compiled = compiler.compile(family["entity_id"], sl["entity_id"])
    decoded = compiler.decode_context(compiled["wire"])
    assert decoded == projection
    assert decoded["hygiene"]["counts"]["resident"] >= 1
