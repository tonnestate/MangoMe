from __future__ import annotations

from pathlib import Path

from mangome.importer import BigBangScanner
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def test_bigbang_scan_is_non_destructive_and_only_creates_artifacts(tmp_path: Path):
    p = tmp_path / "AVCOS-FOO-001.md"
    p.write_text("# AVCOS-FOO-001 Contract\n\n## Slice 1 - Discovery\nAcceptance: pass tests\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    records = BigBangScanner(svc).scan([str(tmp_path)])
    assert len(records) == 1
    assert records[0].classification == "CONTRACT_CANDIDATE"
    assert "AVCOS-FOO-001" in records[0].declared_ids
    assert svc.store.find("artifacts")
    assert svc.store.find("contracts") == []
    assert p.exists()


def test_bigbang_scanner_skips_symlinks_and_private_agent_secret_trees(tmp_path: Path):
    visible = tmp_path / "VISIBLE-001.md"
    visible.write_text("# VISIBLE-001 Contract\n", encoding="utf-8")
    private = tmp_path / ".codex"
    private.mkdir()
    (private / "PRIVATE-001.md").write_text("# PRIVATE-001 Contract\n", encoding="utf-8")
    secrets = tmp_path / ".env.json"
    secrets.write_text('{"token":"secret"}', encoding="utf-8")
    link = tmp_path / "LINK-001.md"
    link.symlink_to(visible)

    records = BigBangScanner(None).scan([str(tmp_path)])
    paths = {Path(row.path).name for row in records}
    assert "VISIBLE-001.md" in paths
    assert "PRIVATE-001.md" not in paths
    assert ".env.json" not in paths
    assert "LINK-001.md" not in paths


def test_bigbang_scanner_hashes_full_file_but_bounds_text_sample(tmp_path: Path):
    import hashlib

    payload = ("# LARGE-001 Contract\n" + ("x" * 250_000)).encode("utf-8")
    path = tmp_path / "LARGE-001.md"
    path.write_bytes(payload)
    records = BigBangScanner(None).scan([str(path)], max_bytes=1024)
    assert len(records) == 1
    assert records[0].size == len(payload)
    assert records[0].sha256 == hashlib.sha256(payload).hexdigest()
    assert "LARGE-001" in records[0].declared_ids


def test_bigbang_scan_prunes_excluded_trees_and_enforces_file_limit(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    for idx in range(5):
        (root / f"C-{idx}.md").write_text(f"# Contract C-{idx}\n", encoding="utf-8")
    private = root / ".cache"
    private.mkdir()
    (private / "C-SECRET.md").write_text("# Contract C-SECRET\n", encoding="utf-8")
    deep = root / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "C-DEEP.md").write_text("# Contract C-DEEP\n", encoding="utf-8")

    scanner = BigBangScanner(None)
    limited = scanner.scan([str(root)], max_files=2, max_depth=16)
    assert len(limited) <= 2
    assert scanner.last_scan_stats["visited_files"] == 2
    assert scanner.last_scan_stats["limit_reached"] is True
    assert all(".cache" not in row.path for row in limited)

    shallow = scanner.scan([str(root)], max_files=50, max_depth=1)
    assert all("C-DEEP.md" not in row.path for row in shallow)
    assert all("C-SECRET.md" not in row.path for row in shallow)
