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
