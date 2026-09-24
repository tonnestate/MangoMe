from __future__ import annotations

import json

import pytest

from mangome.interlingua import InterlinguaError, UAICompiler, decode_uai_result, render_uai_result
from mangome.service import MangoMeService, PlanRequired
from mangome.storage.memory import InMemoryStore


def make_context():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("UAI", "Unified Agent Interlingua", scope_ids=["AVCOS", "TONNESTATE"])
    contract = svc.register_contract(
        declared_id="UAI-001", family_id=family["entity_id"], title="Compact semantic transport contract"
    )
    spec = svc.create_spec(
        family_id=family["entity_id"],
        objective="Transmit canonical work semantics to expensive models without retransmitting historical prose.",
        contract_ids=[contract["entity_id"]],
        deliverables=["Compact context", "Round-trip expansion", "Structured result rendering"],
        constraints=["Canonical truth remains in MangoMe", "UAI output never bypasses normal mutation gates"],
        acceptance_criteria=["Semantic hash verifies", "Round-trip preserves projection", "Result decoder rejects stale context"],
        required_evidence=["pytest", "runtime observation"],
    )
    request = svc.intake_request(
        request_text="Implement compact semantic transport for expensive coding models",
        classification="EXISTING_CONTRACT_WORK",
        family_id=family["entity_id"],
    )
    plan = svc.submit_plan(
        family_id=family["entity_id"], request_id=request["entity_id"], spec_id=spec["entity_id"],
        actor_id="claude-code", intent="implement UAI transport", contract_ids=[contract["entity_id"]],
        expected_artifacts=["src/mangome/interlingua.py", "tests/test_interlingua.py"],
        proposed_slices=[{
            "declared_id": "UAI-S1", "title": "Compact context", "objective": "Compile and round-trip UAI/1",
            "acceptance": ["round-trip", "hash binding", "result rendering"],
        }],
    )
    sl = svc.store.find("slices", {"family_id": family["entity_id"]})[0]
    svc.start_slice(slice_id=sl["entity_id"], actor_id="claude-code", plan_id=plan["entity_id"])
    return svc, family, sl, plan


def test_uai_context_round_trip_preserves_semantic_projection():
    svc, family, sl, _ = make_context()
    compiler = UAICompiler(svc)
    projection = compiler.semantic_projection(family["entity_id"], sl["entity_id"])
    compiled = compiler.compile(family["entity_id"], sl["entity_id"])
    expanded = compiler.decode_context(compiled["wire"])
    assert expanded == projection
    assert compiled["semantic_hash"] == compiled["packet"]["h"]
    assert compiled["metrics"]["uai_chars"] < compiled["metrics"]["raw_context_chars"]


def test_uai_hash_detects_semantic_tampering():
    svc, family, sl, _ = make_context()
    compiler = UAICompiler(svc)
    compiled = compiler.compile(family["entity_id"], sl["entity_id"])
    packet = json.loads(compiled["wire"])
    packet["s"][0] = "DONE_CLAIMED"
    with pytest.raises(InterlinguaError, match="semantic hash mismatch"):
        compiler.decode_context(json.dumps(packet))


def test_uai_result_decodes_and_renders_without_mutating_state():
    svc, family, sl, _ = make_context()
    compiled = UAICompiler(svc).compile(family["entity_id"], sl["entity_id"])
    result = {
        "v": "UAI/1R",
        "h": compiled["semantic_hash"],
        "st": "SUCCESS",
        "a": [
            ["P", 2, 3],
            ["A", "interlingua.py", "SOURCE", "git", "src/mangome/interlingua.py"],
            ["E", "ROUND_TRIP", "TEST_RESULT", "pytest", "PASS"],
            ["D", "compact transport complete"],
        ],
    }
    decoded = decode_uai_result(result, expected_context_hash=compiled["semantic_hash"])
    assert decoded["actions"][0]["type"] == "PROGRESS"
    rendered = render_uai_result(result, language="de", expected_context_hash=compiled["semantic_hash"])
    assert "DONE_CLAIMED" in rendered
    assert svc.store.get("slices", sl["entity_id"])["execution_state"] == "ACTIVE"


def test_uai_result_rejects_stale_context_hash():
    svc, family, sl, _ = make_context()
    compiled = UAICompiler(svc).compile(family["entity_id"], sl["entity_id"])
    result = {"v": "UAI/1R", "h": "0" * 64, "st": "SUCCESS", "a": []}
    with pytest.raises(InterlinguaError, match="does not match"):
        decode_uai_result(result, expected_context_hash=compiled["semantic_hash"])


def test_begin_work_reduces_calls_without_reducing_persisted_truth():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("BW", "Begin Work")
    contract = svc.register_contract(declared_id="BW-1", family_id=family["entity_id"], title="Contract")
    svc.create_spec(family_id=family["entity_id"], objective="Existing family work", contract_ids=[contract["entity_id"]])
    result = svc.begin_work(
        family_id=family["entity_id"], actor_id="worker", request_text="small bounded change", intent="change one thing",
        proposed_slice={"declared_id": "BW-S1", "title": "Small change"},
    )
    assert result["slice"]["execution_state"] == "ACTIVE"
    assert result["slice"]["active_plan_id"] == result["plan"]["entity_id"]
    assert len(svc.store.find("requests")) == 1
    assert len(svc.store.find("plans")) == 1


def test_begin_work_refuses_family_without_effective_spec():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("NO-SPEC", "No Spec")
    with pytest.raises(PlanRequired):
        svc.begin_work(
            family_id=family["entity_id"], actor_id="worker", request_text="do it", intent="work",
            proposed_slice={"declared_id": "S1", "title": "Slice"},
        )


def test_execution_receipt_tracks_interlingua_tokens():
    svc, family, sl, _ = make_context()
    model = svc.register_model(model_key="claude-code", provider="Anthropic", access_path="OmniRoute")
    receipt = svc.record_execution_receipt(
        family_id=family["entity_id"], slice_id=sl["entity_id"], actor_id="claude-code", model_id=model["entity_id"],
        work_class="CODING", context_tokens_raw=10000, context_tokens_compiled=4500,
        context_tokens_interlingua=1800, output_tokens_interlingua=220, interlingua_version="UAI/1",
    )
    assert receipt["context_tokens_interlingua"] == 1800
    stats = svc.model_stats(model_id=model["entity_id"], work_class="CODING")
    assert stats["context_tokens_interlingua"] == 1800
    assert stats["output_tokens_interlingua"] == 220
    assert stats["interlingua_versions"] == ["UAI/1"]


def test_begin_work_refuses_already_active_slice_without_creating_extra_request():
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("BW-ACTIVE", "Begin Work Active")
    contract = svc.register_contract(declared_id="BW-ACTIVE-1", family_id=family["entity_id"], title="Contract")
    svc.create_spec(family_id=family["entity_id"], objective="Existing family work", contract_ids=[contract["entity_id"]])
    first = svc.begin_work(
        family_id=family["entity_id"], actor_id="worker-a", request_text="first", intent="first",
        proposed_slice={"declared_id": "S1", "title": "Slice"},
    )
    assert first["slice"]["execution_state"] == "ACTIVE"
    before = len(svc.store.find("requests"))
    with pytest.raises(PlanRequired, match="already active"):
        svc.begin_work(
            family_id=family["entity_id"], actor_id="worker-b", request_text="second", intent="second",
            proposed_slice={"declared_id": "S1", "title": "Slice"},
        )
    assert len(svc.store.find("requests")) == before
