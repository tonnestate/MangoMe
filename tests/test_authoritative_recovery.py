from pathlib import Path

from mangome.service import MangoMeService, workspace_project_key
from mangome.storage.memory import InMemoryStore


def test_recovery_context_is_canonical_and_does_not_require_path_reconstruction(tmp_path: Path):
    svc = MangoMeService(InMemoryStore())
    result = svc.enter_work(
        workspace_id=str(tmp_path),
        workspace_title="Demo",
        actor_id="worker-a",
        request_text="Implement requirement R1",
        acceptance_criteria=["R1 is implemented"],
        expected_artifacts=["src/app.py"],
    )
    family_id = result["family"]["entity_id"]
    slice_id = result["work"]["slice"]["entity_id"]
    svc.attach_artifact(
        logical_name="app.py",
        artifact_type="SOURCE",
        storage_system="filesystem",
        physical_location=str(tmp_path / "src" / "app.py"),
        belongs_to=[family_id, slice_id],
        checksum="abc",
    )

    ctx = svc.recovery_context(workspace_project_key(str(tmp_path)))

    assert ctx["source"] == "MANGOME_CANONICAL_STATE"
    assert ctx["discovery_allowed_for_state_reconstruction"] is False
    assert ctx["families"][0]["family_id"] == family_id
    assert ctx["families"][0]["current_spec"]["objective"] == "Implement requirement R1"
    assert ctx["families"][0]["recovery_slices"][0]["entity_id"] == slice_id
    assert ctx["families"][0]["known_artifacts"][0]["logical_name"] == "app.py"
    assert "Do not reconstruct admitted work" in ctx["rule"]


def test_recovery_context_exposes_operational_language_inheritance(tmp_path: Path):
    svc = MangoMeService(InMemoryStore())
    svc.enter_work(
        workspace_id=str(tmp_path),
        workspace_title="Language Recovery",
        actor_id="coordinator",
        request_text="Recover the bounded state",
        acceptance_criteria=["state recovered"],
        expected_artifacts=[],
    )
    ctx = svc.recovery_context(workspace_project_key(str(tmp_path)))
    assert ctx["communication_policy"] == {
        "human_visible_language": "INHERIT_CURRENT_USER_SESSION_LANGUAGE",
        "silent_language_switch": "FORBIDDEN",
        "machine_identifiers": "STABLE_LANGUAGE_NEUTRAL_TOKENS",
    }
