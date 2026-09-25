from pathlib import Path


def test_agent_skill_surfaces_are_present_and_identical():
    root = Path(__file__).resolve().parents[1]
    canonical = root / "skill" / "mangome" / "SKILL.md"
    mirrors = [
        root / "src" / "mangome" / "skill" / "SKILL.md",
        root / ".github" / "skills" / "mangome" / "SKILL.md",
        root / ".claude" / "skills" / "mangome" / "SKILL.md",
    ]

    assert canonical.is_file()
    expected = canonical.read_bytes()
    for mirror in mirrors:
        assert mirror.is_file(), f"missing Agent Skill surface: {mirror.relative_to(root)}"
        assert mirror.read_bytes() == expected, f"Agent Skill drift: {mirror.relative_to(root)}"


def test_operational_language_policy_is_present_in_skill_and_mcp_source():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")
    mcp_source = (root / "src" / "mangome" / "mcp_server.py").read_text(encoding="utf-8")
    assert "Operational language follows the user/session" in skill
    assert "INHERIT_CURRENT_USER_SESSION_LANGUAGE" in mcp_source
    assert "silent_language_switch" in mcp_source
