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
