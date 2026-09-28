from pathlib import Path


def test_agent_skill_surfaces_are_present_and_identical():
    root = Path(__file__).resolve().parents[1]
    canonical = root / "skill" / "mangome" / "SKILL.md"
    packaged = root / "src" / "mangome" / "skill" / "SKILL.md"
    optional_mirrors = [
        root / ".github" / "skills" / "mangome" / "SKILL.md",
        root / ".claude" / "skills" / "mangome" / "SKILL.md",
    ]

    assert canonical.is_file()
    assert packaged.is_file()
    expected = canonical.read_bytes()
    assert packaged.read_bytes() == expected
    for mirror in optional_mirrors:
        if mirror.exists():
            assert mirror.read_bytes() == expected, f"Agent Skill drift: {mirror.relative_to(root)}"


def test_operational_language_policy_is_present_in_skill_and_mcp_source():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")
    mcp_source = (root / "src" / "mangome" / "mcp_server.py").read_text(encoding="utf-8")
    assert "Operational language follows the user/session" in skill
    assert "INHERIT_CURRENT_USER_SESSION_LANGUAGE" in mcp_source
    assert "silent_language_switch" in mcp_source



def test_skill_treats_historical_host_memory_as_candidate_only():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")
    assert "Historical host memory is never current authority" in skill
    assert "candidate-only discovery hints" in skill
    assert "Never recover current WorkIdentity" in skill
    assert "controller authority" in skill


def test_skill_has_out_of_band_control_plane_self_maintenance_rule():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")
    operability = (root / "src" / "mangome" / "operability.py").read_text(encoding="utf-8")
    assert "Explicit MangoMe self-maintenance" in skill
    assert "Self-maintenance does not self-admit" in skill
    assert "DATABASE_CHANGE_REQUIRED" in skill
    assert "Self-maintenance does not self-admit" in skill
    assert "candidate-only discovery hints" in skill
