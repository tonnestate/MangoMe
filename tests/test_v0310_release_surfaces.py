from pathlib import Path


def test_v0310_release_surfaces_are_present_and_linked():
    root = Path(__file__).resolve().parents[1]
    required = [
        root / ".github" / "workflows" / "ci.yml",
        root / "docs" / "START_HERE.md",
        root / "docs" / "getting-started.md",
        root / "docs" / "QUICKSTART_DEMO.md",
        root / "docs" / "troubleshooting.md",
        root / "docs" / "WHY_MANGOME.md",
        root / "docs" / "COMPATIBILITY.md",
        root / "docs" / "RELEASE_CHECKLIST.md",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    assert missing == []

    readme = (root / "README.md").read_text(encoding="utf-8")
    for path in required[1:-1]:
        relative = str(path.relative_to(root)).replace("\\", "/")
        assert relative in readme


def test_v0310_contributing_matches_optional_skill_mirror_policy():
    root = Path(__file__).resolve().parents[1]
    text = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "two authoritative release surfaces" in text
    assert "optional convenience surfaces" in text
    assert "make check" in text


def test_v0310_project_view_uses_current_schema_constant():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "mangome" / "service.py").read_text(encoding="utf-8")
    assert 'payload["schema_version"] = CURRENT_SCHEMA_VERSION' in source
    assert 'payload["schema_version"] = 5' not in source
