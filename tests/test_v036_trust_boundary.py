from __future__ import annotations

import os

import pytest

from mangome.operability import OperabilityError
from mangome.trust_boundary import resolve_mongodb_connection


def _clear(monkeypatch):
    for name in (
        "MANGOME_TRUST_BOUNDARY", "MANGOME_MONGODB_URI", "MANGOME_MONGODB_URI_FILE",
        "MANGOME_EXPECTED_SERVICE_UID", "MANGOME_ALLOW_REMOTE_MONGODB",
    ):
        monkeypatch.delenv(name, raising=False)


def test_warn_mode_keeps_compatibility_but_reports_environment_credentials(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "WARN")
    monkeypatch.setenv("MANGOME_MONGODB_URI", "mongodb://user:secret@127.0.0.1:27017")
    cfg = resolve_mongodb_connection()
    assert cfg.status["credential_source"] == "ENVIRONMENT"
    assert cfg.status["credentials_in_environment"] is True
    assert "MONGODB_CREDENTIALS_IN_PROCESS_ENVIRONMENT" in cfg.status["warnings"]
    assert "secret" not in repr(cfg.status)


def test_strict_mode_rejects_environment_uri(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "STRICT")
    monkeypatch.setenv("MANGOME_MONGODB_URI", "mongodb://user:secret@127.0.0.1:27017")
    if hasattr(os, "geteuid"):
        monkeypatch.setenv("MANGOME_EXPECTED_SERVICE_UID", str(os.geteuid()))
    with pytest.raises(OperabilityError) as exc:
        resolve_mongodb_connection()
    assert exc.value.code == "TRUST_BOUNDARY_VIOLATION"


def test_strict_mode_accepts_owner_only_credential_file_and_loopback(monkeypatch, tmp_path):
    if not hasattr(os, "geteuid"):
        pytest.skip("strict service identity test requires POSIX uid")
    _clear(monkeypatch)
    secret = tmp_path / "mongodb-uri"
    secret.write_text("mongodb://mangome-runtime:secret@127.0.0.1:27017", encoding="utf-8")
    secret.chmod(0o600)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "STRICT")
    monkeypatch.setenv("MANGOME_MONGODB_URI_FILE", str(secret))
    monkeypatch.setenv("MANGOME_EXPECTED_SERVICE_UID", str(os.geteuid()))
    cfg = resolve_mongodb_connection()
    assert cfg.status["strict_ok"] is True
    assert cfg.status["credential_source"] == "CREDENTIAL_FILE"
    assert cfg.status["endpoint_scope"] == "LOOPBACK"
    assert cfg.status["credentials_in_environment"] is False


def test_strict_mode_rejects_remote_db_without_explicit_allow(monkeypatch, tmp_path):
    if not hasattr(os, "geteuid"):
        pytest.skip("strict service identity test requires POSIX uid")
    _clear(monkeypatch)
    secret = tmp_path / "mongodb-uri"
    secret.write_text("mongodb://mangome-runtime:secret@mongo.internal:27017", encoding="utf-8")
    secret.chmod(0o600)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "STRICT")
    monkeypatch.setenv("MANGOME_MONGODB_URI_FILE", str(secret))
    monkeypatch.setenv("MANGOME_EXPECTED_SERVICE_UID", str(os.geteuid()))
    with pytest.raises(OperabilityError) as exc:
        resolve_mongodb_connection()
    assert "REMOTE_MONGODB_NOT_EXPLICITLY_ALLOWED" in str(exc.value)
