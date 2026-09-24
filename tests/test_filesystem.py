from __future__ import annotations

from pathlib import Path

from mangome.filesystem import FilesystemScanner
from mangome.service import MangoMeService
from mangome.storage.memory import InMemoryStore


def test_filesystem_scan_indexes_source_tests_hidden_workdirs_and_skips_secrets(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".ssh").mkdir()
    (tmp_path / "src" / "worker.py").write_text("# AVCOS-PROOF-001\n", encoding="utf-8")
    (tmp_path / "tests" / "test_worker.py").write_text("# AVCOS-PROOF-001\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("# AVCOS-PROOF-001\n", encoding="utf-8")
    (tmp_path / ".env").write_text("PASSWORD=do-not-read\n", encoding="utf-8")
    (tmp_path / ".ssh" / "id_rsa").write_text("secret\n", encoding="utf-8")

    svc = MangoMeService(InMemoryStore())
    result = FilesystemScanner(svc).scan([str(tmp_path)])
    refs = FilesystemScanner(svc).references("AVCOS-PROOF-001")

    assert result["coverage_complete"] is True
    assert refs["count"] == 3
    assert {entry["role"] for entry in refs["entries"]} == {"SOURCE", "TEST", "WORKFLOW"}
    indexed_paths = {row["path"] for row in svc.store.find("filesystem_entries")}
    assert str((tmp_path / ".env").resolve()) not in indexed_paths
    assert str((tmp_path / ".ssh" / "id_rsa").resolve()) not in indexed_paths


def test_filesystem_scan_is_incremental_and_marks_removed_files(tmp_path: Path):
    source = tmp_path / "src.py"
    source.write_text("print('a')\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)

    first = scanner.scan([str(tmp_path)])
    entry1 = svc.store.find("filesystem_entries")[0]
    second = scanner.scan([str(tmp_path)])
    entry2 = svc.store.find("filesystem_entries")[0]

    assert first["changed_count"] == 1
    assert second["changed_count"] == 0
    assert second["unchanged_count"] == 1
    assert entry2["revision"] == entry1["revision"]

    source.write_text("print('b')\n", encoding="utf-8")
    changed = scanner.scan([str(tmp_path)])
    entry3 = svc.store.find("filesystem_entries")[0]
    assert changed["changed_count"] == 1
    assert entry3["sha256"] != entry1["sha256"]

    source.unlink()
    removed = scanner.scan([str(tmp_path)])
    entry4 = svc.store.find("filesystem_entries")[0]
    assert removed["removed_count"] == 1
    assert entry4["present"] is False


def test_evidence_freshness_reuses_only_attested_pass_with_matching_hash(tmp_path: Path):
    source = tmp_path / "feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)
    scanner.scan([str(tmp_path)])
    indexed = svc.store.find("filesystem_entries")[0]
    family = svc.create_family("PROOF", "Proof")
    sl = svc.import_slice(
        family_id=family["entity_id"], declared_id="P1", title="Proof slice",
        execution_state="DONE_CLAIMED", assurance_state="UNVERIFIED",
    )
    evidence = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="unit-test", source="pytest", result="PASS",
        evidence_class="TEST_RESULT",
        payload={"filesystem_bindings": [{"path": str(source), "sha256": indexed["sha256"]}]},
    )
    svc.store.update("evidence", evidence["entity_id"], {
        "trust": "VERIFIER_ATTESTED", "attested_by": "verifier",
    })

    fresh = scanner.evidence_freshness(evidence["entity_id"])
    assert fresh["state"] == "REUSABLE"

    source.write_text("VALUE = 2\n", encoding="utf-8")
    stale = scanner.evidence_freshness(evidence["entity_id"])
    assert stale["state"] == "STALE"
    assert stale["checks"][0]["status"] == "HASH_MISMATCH"


def test_audit_claim_is_never_reusable_proof(tmp_path: Path):
    svc = MangoMeService(InMemoryStore())
    family = svc.create_family("CLAIM", "Claim")
    sl = svc.import_slice(
        family_id=family["entity_id"], declared_id="C1", title="Claim slice",
        execution_state="DONE_CLAIMED", assurance_state="UNVERIFIED",
    )
    evidence = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="legacy-audit", source="old-report.md", result="PASS",
        evidence_class="CLAIM", payload={"filesystem_bindings": []},
    )
    result = FilesystemScanner(svc).evidence_freshness(evidence["entity_id"])
    assert result["state"] == "INADMISSIBLE"
