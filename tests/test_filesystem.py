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


def test_build_reproduction_binding_hashes_inputs_and_does_not_store_environment_values(tmp_path: Path):
    source = tmp_path / "src.py"
    test_file = tmp_path / "test_src.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("def test_value(): assert True\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)
    scanner.scan([str(tmp_path)])

    first = scanner.build_reproduction_binding(
        command="pytest -q test_src.py",
        cwd=str(tmp_path),
        exit_code=0,
        input_paths=[str(test_file), str(source)],
        environment_names=["PYTHONPATH", "CI"],
        git_commit="deadbeef",
    )["reproduction"]
    second = scanner.build_reproduction_binding(
        command="pytest -q test_src.py",
        cwd=str(tmp_path),
        exit_code=0,
        input_paths=[str(source), str(test_file)],
        environment_names=["CI", "PYTHONPATH", "CI"],
        git_commit="deadbeef",
    )["reproduction"]

    assert first["version"] == "RB/1"
    assert first["fingerprint"] == second["fingerprint"]
    assert first["environment_names"] == ["CI", "PYTHONPATH"]
    assert "environment_values" not in first
    assert {item["role"] for item in first["input_bindings"]} == {"SOURCE", "TEST"}


def test_build_reproduction_binding_rejects_sensitive_environment_names(tmp_path: Path):
    source = tmp_path / "feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)

    import pytest
    with pytest.raises(ValueError, match="sensitive environment variable name"):
        scanner.build_reproduction_binding(
            command="pytest -q",
            cwd=str(tmp_path),
            exit_code=0,
            input_paths=[str(source)],
            environment_names=["OPENAI_API_TOKEN"],
            git_commit="deadbeef",
        )


def test_reproduction_freshness_reports_source_change_and_fingerprint_tampering(tmp_path: Path):
    source = tmp_path / "feature.py"
    test_file = tmp_path / "test_feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("def test_feature(): assert True\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)
    scanner.scan([str(tmp_path)])

    reproduction = scanner.build_reproduction_binding(
        command="pytest -q test_feature.py",
        cwd=str(tmp_path),
        exit_code=0,
        input_paths=[str(source), str(test_file)],
        git_commit="deadbeef",
    )["reproduction"]
    family = svc.create_family("RB1", "RB1")
    sl = svc.import_slice(
        family_id=family["entity_id"], declared_id="RB1-S1", title="RB1",
        execution_state="DONE_CLAIMED", assurance_state="UNVERIFIED",
    )
    evidence = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="unit-test", source="pytest", result="PASS",
        evidence_class="TEST_RESULT", payload={"reproduction": reproduction},
    )
    svc.store.update("evidence", evidence["entity_id"], {"trust": "VERIFIER_ATTESTED", "attested_by": "verifier"})

    # Explicit fake git commit makes exact-context freshness UNKNOWN even while files match.
    current = scanner.evidence_freshness(evidence["entity_id"])
    assert current["state"] == "UNKNOWN"
    assert "COMMIT_CHANGED" in current["reason_codes"] or "GIT_UNAVAILABLE" in current["reason_codes"]

    source.write_text("VALUE = 2\n", encoding="utf-8")
    stale = scanner.evidence_freshness(evidence["entity_id"])
    assert stale["state"] == "STALE"
    assert "SOURCE_CHANGED" in stale["reason_codes"]

    stored = svc.store.get("evidence", evidence["entity_id"])
    tampered = dict(stored["payload"])
    tampered_repro = dict(tampered["reproduction"])
    tampered_repro["command"] = "pytest -q --changed"
    tampered["reproduction"] = tampered_repro
    svc.store.update("evidence", evidence["entity_id"], {"payload": tampered})
    invalid = scanner.evidence_freshness(evidence["entity_id"])
    assert invalid["state"] == "INADMISSIBLE"
    assert invalid["reason_codes"] == ["FINGERPRINT_MISMATCH"]


def test_reproduction_freshness_is_reusable_when_git_and_inputs_match(tmp_path: Path):
    import subprocess

    source = tmp_path / "feature.py"
    test_file = tmp_path / "test_feature.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    test_file.write_text("def test_feature(): assert True\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "MangoMe Test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "feature.py", "test_feature.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "fixture"], check=True)

    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)
    scanner.scan([str(tmp_path)])
    reproduction = scanner.build_reproduction_binding(
        command="pytest -q test_feature.py",
        cwd=str(tmp_path),
        exit_code=0,
        input_paths=[str(source), str(test_file)],
    )["reproduction"]
    family = svc.create_family("RB2", "RB2")
    sl = svc.import_slice(
        family_id=family["entity_id"], declared_id="RB2-S1", title="RB2",
        execution_state="DONE_CLAIMED", assurance_state="UNVERIFIED",
    )
    evidence = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="unit-test", source="pytest", result="PASS",
        evidence_class="TEST_RESULT", payload={"reproduction": reproduction},
    )
    svc.store.update("evidence", evidence["entity_id"], {"trust": "VERIFIER_ATTESTED", "attested_by": "verifier"})

    fresh = scanner.evidence_freshness(evidence["entity_id"])
    assert fresh["state"] == "REUSABLE"
    assert fresh["binding_version"] == "RB/1"
    assert fresh["reason_codes"] == []

    # Unrelated commit changes HEAD. Bound files remain identical, so the result is conservative UNKNOWN, not STALE.
    unrelated = tmp_path / "README.md"
    unrelated.write_text("unrelated\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "unrelated"], check=True)
    drift = scanner.evidence_freshness(evidence["entity_id"])
    assert drift["state"] == "UNKNOWN"
    assert "COMMIT_CHANGED" in drift["reason_codes"]


def test_reproduction_freshness_rejects_nonzero_pass_and_missing_output(tmp_path: Path):
    source = tmp_path / "feature.py"
    output = tmp_path / "report.txt"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    output.write_text("PASS\n", encoding="utf-8")
    svc = MangoMeService(InMemoryStore())
    scanner = FilesystemScanner(svc)
    scanner.scan([str(tmp_path)])
    import hashlib
    artifact = svc.attach_artifact(
        logical_name="report.txt", artifact_type="TEST_REPORT", storage_system="filesystem",
        physical_location=str(output), checksum=hashlib.sha256(output.read_bytes()).hexdigest(),
    )
    reproduction = scanner.build_reproduction_binding(
        command="pytest -q",
        cwd=str(tmp_path),
        exit_code=0,
        input_paths=[str(source)],
        output_artifact_id=artifact["entity_id"],
        git_commit="",
    )["reproduction"]
    # Avoid unrelated Git uncertainty in a non-repository fixture.
    reproduction["git_commit"] = None
    from mangome.filesystem import reproduction_fingerprint
    reproduction["fingerprint"] = reproduction_fingerprint(reproduction)

    family = svc.create_family("RB3", "RB3")
    sl = svc.import_slice(
        family_id=family["entity_id"], declared_id="RB3-S1", title="RB3",
        execution_state="DONE_CLAIMED", assurance_state="UNVERIFIED",
    )
    evidence = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="unit-test", source="pytest", result="PASS",
        evidence_class="TEST_RESULT", payload={"reproduction": reproduction},
    )
    svc.store.update("evidence", evidence["entity_id"], {"trust": "VERIFIER_ATTESTED", "attested_by": "verifier"})
    assert scanner.evidence_freshness(evidence["entity_id"])["state"] == "REUSABLE"

    output.unlink()
    stale = scanner.evidence_freshness(evidence["entity_id"])
    assert stale["state"] == "STALE"
    assert "OUTPUT_MISSING" in stale["reason_codes"]

    bad = dict(reproduction)
    bad["exit_code"] = 1
    bad["fingerprint"] = reproduction_fingerprint(bad)
    evidence2 = svc.submit_evidence(
        subject_id=sl["entity_id"], evidence_type="unit-test", source="pytest", result="PASS",
        evidence_class="TEST_RESULT", payload={"reproduction": bad},
    )
    svc.store.update("evidence", evidence2["entity_id"], {"trust": "VERIFIER_ATTESTED", "attested_by": "verifier"})
    inadmissible = scanner.evidence_freshness(evidence2["entity_id"])
    assert inadmissible["state"] == "INADMISSIBLE"
    assert inadmissible["reason_codes"] == ["EXIT_CODE_NONZERO"]
