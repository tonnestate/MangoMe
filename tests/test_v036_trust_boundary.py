from __future__ import annotations

import pytest

from mangome.operability import OperabilityError
from mangome.trust_boundary import resolve_mongodb_connection


def _clear(monkeypatch):
    for name in (
        "MANGOME_TRUST_BOUNDARY", "MANGOME_MONGODB_URI", "MANGOME_MONGODB_URI_FILE",
        "MANGOME_EXPECTED_SERVICE_UID", "MANGOME_ALLOW_REMOTE_MONGODB",
    ):
        monkeypatch.delenv(name, raising=False)


def test_local_host_accepts_credential_free_loopback_and_is_cooperative(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
    monkeypatch.setenv("MANGOME_MONGODB_URI", "mongodb://127.0.0.1:27017")
    cfg = resolve_mongodb_connection()
    assert cfg.status["credential_source"] == "NONE"
    assert cfg.status["endpoint_scope"] == "LOOPBACK"
    assert cfg.status["verification_boundary"] == "COOPERATIVE_HOST"
    assert cfg.status["tamper_resistant_verification"] is False


def test_local_host_rejects_credentials(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
    monkeypatch.setenv("MANGOME_MONGODB_URI", "mongodb://user:secret@127.0.0.1:27017")
    with pytest.raises(OperabilityError) as exc:
        resolve_mongodb_connection()
    assert exc.value.code == "LOCAL_HOST_CREDENTIALS_FORBIDDEN"


def test_legacy_strict_mode_is_rejected_until_a_real_service_boundary_exists(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "STRICT")
    with pytest.raises(OperabilityError) as exc:
        resolve_mongodb_connection()
    assert exc.value.code == "LEGACY_TRUST_MODE_REJECTED"


def test_local_host_rejects_remote_endpoint(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
    monkeypatch.setenv("MANGOME_MONGODB_URI", "mongodb://mongo.internal:27017")
    with pytest.raises(OperabilityError) as exc:
        resolve_mongodb_connection()
    assert exc.value.code == "LOCAL_HOST_ENDPOINT_REQUIRED"


def test_local_host_rejects_legacy_credential_file(monkeypatch, tmp_path):
    _clear(monkeypatch)
    secret = tmp_path / "mongodb-uri"
    secret.write_text("mongodb://user:secret@127.0.0.1:27017", encoding="utf-8")
    monkeypatch.setenv("MANGOME_TRUST_BOUNDARY", "LOCAL_HOST")
    monkeypatch.setenv("MANGOME_MONGODB_URI_FILE", str(secret))
    with pytest.raises(OperabilityError) as exc:
        resolve_mongodb_connection()
    assert exc.value.code == "LEGACY_CREDENTIAL_CONFIGURATION_REJECTED"
