from __future__ import annotations

import mangome.runtime as runtime


def test_health_snapshot_survives_bootstrap_failure_without_leaking_message(monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "mongo")
    monkeypatch.setenv("MANGOME_DATABASE", "mangome_uai_eval")

    class SecretBearingFailure(RuntimeError):
        pass

    def fail():
        raise SecretBearingFailure("mongodb://user:TOP-SECRET@127.0.0.1:27017")

    monkeypatch.setattr(runtime, "get_service", fail)
    result = runtime.health_snapshot()

    assert result["ok"] is False
    assert result["store"]["database"] == "mangome_uai_eval"
    assert result["store"]["error_type"] == "SecretBearingFailure"
    assert "TOP-SECRET" not in str(result)
    assert "mongodb://" not in str(result)


def test_health_snapshot_memory_backend_is_healthy(monkeypatch):
    runtime.reset_service_for_tests()
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    result = runtime.health_snapshot()
    assert result["ok"] is True
    assert result["store"]["backend"] == "memory"
    runtime.reset_service_for_tests()


def test_health_snapshot_reports_managed_identity_mismatch_without_raw_path_leak(monkeypatch):
    runtime.reset_service_for_tests()
    monkeypatch.setenv("MANGOME_BACKEND", "memory")
    monkeypatch.setenv("MANGOME_EXPECTED_VERSION", "999.0")
    result = runtime.health_snapshot()
    assert result["ok"] is False
    assert result["store"]["reason_code"] == "WRONG_MANGOME_VERSION"
    assert "999.0" not in str(result)
    runtime.reset_service_for_tests()
