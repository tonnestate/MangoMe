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


def test_release_tree_has_no_process_helper_documents():
    root = Path(__file__).resolve().parents[1]
    forbidden = ["REPO_AUDIT_2026-09-24.md", "TEST_REPORT.md", "UPLOAD_DOTFILES.md"]
    present = [name for name in forbidden if (root / name).exists()]
    assert present == [], f"release tree contains process-only helper documents: {present}"


def test_skill_treats_historical_host_memory_as_candidate_only():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "skill" / "mangome" / "SKILL.md").read_text(encoding="utf-8")
    assert "Historical host memory is never current authority" in skill
    assert "candidate-only discovery hints" in skill
    assert "Never recover current WorkIdentity" in skill
    assert "controller authority" in skill
