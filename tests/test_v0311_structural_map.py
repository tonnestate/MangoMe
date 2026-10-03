from __future__ import annotations

from pathlib import Path

from mangome.structural import StructuralIntelligence


def _fixture(root: Path) -> None:
    (root / "a.py").write_text(
        "from b import helper\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    (root / "b.py").write_text("def helper():\n    return 1\n", encoding="utf-8")


def test_status_never_indexes(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _fixture(root)
    StructuralIntelligence.reset_cache_for_tests()
    svc = StructuralIntelligence(root)
    status = svc.structural_status()
    assert status["status"] == "UNINDEXED"
    assert status["scan_performed"] is False
    assert status["files_indexed"] == 0


def test_search_lazily_builds_map_and_exact_lookup(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _fixture(root)
    StructuralIntelligence.reset_cache_for_tests()
    svc = StructuralIntelligence(root)
    search = svc.structural_search("helper")
    assert search["status"] == "EXACT"
    lookup = svc.symbol_lookup("helper")
    assert lookup["status"] == "EXACT"
    assert len(lookup["matches"]) == 1
    assert lookup["matches"][0]["path"] == "b.py"


def test_unchanged_refresh_keeps_same_revision(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _fixture(root)
    StructuralIntelligence.reset_cache_for_tests()
    svc = StructuralIntelligence(root)
    first = svc.structural_search("helper")["revision_id"]
    second = svc.structural_search("helper")["revision_id"]
    assert first == second


def test_ambiguous_symbol_stays_visible_as_multiple_matches(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "x.py").write_text("def duplicate():\n    pass\n", encoding="utf-8")
    (root / "y.py").write_text("def duplicate():\n    pass\n", encoding="utf-8")
    StructuralIntelligence.reset_cache_for_tests()
    lookup = StructuralIntelligence(root).symbol_lookup("duplicate")
    assert lookup["status"] == "EXACT"
    assert len(lookup["matches"]) == 2


def test_impact_frontier_is_bounded_and_inspection_only(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _fixture(root)
    StructuralIntelligence.reset_cache_for_tests()
    svc = StructuralIntelligence(root)
    result = svc.impact_frontier("helper", max_depth=2, max_nodes=3, max_files=2)
    assert result["mutation_scope_expanded"] is False
    assert len(result["relations"]) <= 3
    assert len(result["files"]) <= 2
    assert "INSPECTION" in result["rule"]


def test_context_projection_respects_char_budget(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _fixture(root)
    StructuralIntelligence.reset_cache_for_tests()
    ctx = StructuralIntelligence(root).structural_context("helper main", max_chars=800, max_items=20)
    assert sum(len(str(item)) for item in ctx["items"]) <= 800
    assert ctx["rule"] == "MAP_IS_DERIVED_OBSERVATION_NOT_TRUTH_AUTHORITY_EVIDENCE_OR_ASSURANCE"
