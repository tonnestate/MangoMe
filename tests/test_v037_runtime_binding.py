from __future__ import annotations

import pytest

import mangome.runtime as runtime
from mangome.operability import OperabilityError


def test_legacy_eval_database_fails_closed_without_explicit_opt_in(monkeypatch):
    runtime.reset_service_for_tests()
    monkeypatch.setenv("MANGOME_BACKEND", "mongo")
    monkeypatch.setenv("MANGOME_DATABASE", "mangome_uai_eval")
    monkeypatch.setenv("MANGOME_EXPECTED_DATABASE", "mangome_uai_eval")
    monkeypatch.delenv("MANGOME_ALLOW_EVAL_DATABASE", raising=False)
    with pytest.raises(OperabilityError) as exc:
        runtime.get_service()
    assert exc.value.code == "LEGACY_EVAL_DATABASE_REQUIRES_OPT_IN"
    result = runtime.health_snapshot()
    assert result["process_ready"] is True
    assert result["database_ready"] is False
    assert result["database_binding"]["database"] == "mangome_uai_eval"
    assert result["database_binding"]["state"] == "LEGACY_EVAL_REQUIRES_OPT_IN"
    runtime.reset_service_for_tests()


def test_eval_database_requires_explicit_opt_in(monkeypatch):
    binding = runtime.database_binding_snapshot()
    monkeypatch.setenv("MANGOME_BACKEND", "mongo")
    monkeypatch.setenv("MANGOME_DATABASE", "mangome_uai_eval")
    monkeypatch.setenv("MANGOME_EXPECTED_DATABASE", "mangome_uai_eval")
    monkeypatch.setenv("MANGOME_ALLOW_EVAL_DATABASE", "1")
    binding = runtime.database_binding_snapshot()
    assert binding["state"] == "BOUND"
    assert binding["eval_opt_in"] is True


def test_default_database_binding_is_canonical_mangome(monkeypatch):
    monkeypatch.setenv("MANGOME_BACKEND", "mongo")
    monkeypatch.delenv("MANGOME_DATABASE", raising=False)
    monkeypatch.delenv("MANGOME_EXPECTED_DATABASE", raising=False)
    monkeypatch.delenv("MANGOME_ALLOW_EVAL_DATABASE", raising=False)
    binding = runtime.database_binding_snapshot()
    assert binding["database"] == "mangome"
    assert binding["expected_database"] == "mangome"
    assert binding["state"] == "BOUND"
