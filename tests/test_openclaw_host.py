"""OpenClaw host adapter ownership (FS-OPENCLAW-BOUNDARY-016): fail-closed interception gate, session authority via an injected store, truthful capability states."""
import pytest

from mangome.openclaw_host import (ABSENT, ADAPTER_REGISTERED, CODE_PRESENT, CONNECTED, EXECUTABLE, PROVEN, REQUIRED_INTERCEPTIONS, RUNTIME_INSTALLED, RUNTIME_RUNNING, UNAVAILABLE,
                                   UNKNOWN, OpenClawHostAdapter, OpenClawHostError, capability_report)
import mangome.openclaw_host as host

ALL = set(REQUIRED_INTERCEPTIONS)


class Store:
    """Stands in for PeachMe's SessionStore.assert_execution_authority."""
    def __init__(self, revision=3, fail=None):
        self.revision, self.fail, self.calls = revision, fail, 0

    def assert_execution_authority(self, session_id, revision):
        self.calls += 1
        if callable(self.fail) and self.fail(self.calls):
            raise RuntimeError("REFLEX_BLOCKED_HEALTH_WARNING")
        if revision != self.revision:
            raise RuntimeError("STALE_SESSION_REVISION")


def adapter(approve=lambda s, t: True, store=None, caps=ALL):
    return OpenClawHostAdapter(capabilities=caps, approve_effect=approve, store=store)


@pytest.fixture(autouse=True)
def _clean_registry():
    host._REGISTRY.clear()
    yield
    host._REGISTRY.clear()


def test_incomplete_interception_fails_closed():
    a = adapter(caps={"pre_tool"})
    assert not a.report().enforced
    with pytest.raises(OpenClawHostError, match="OPENCLAW_RUNTIME_INTERCEPTION_INCOMPLETE"):
        a.authorize_tool("sid", "exec")


def test_denied_tool_requires_revision_and_store():
    a = adapter(approve=lambda s, t: t == "read", store=Store())
    with pytest.raises(OpenClawHostError, match="OPENCLAW_REVISION_REQUIRED"):
        a.authorize_tool("sid", "read")
    with pytest.raises(OpenClawHostError, match="TOOL_EFFECT_DENIED"):
        a.authorize_tool("sid", "exec", expected_revision=3)
    a.authorize_tool("sid", "read", expected_revision=3)
    with pytest.raises(OpenClawHostError, match="OPENCLAW_SESSION_STORE_REQUIRED"):
        adapter().authorize_tool("sid", "read", expected_revision=3)


def test_stale_revision_and_authority_lost_while_the_host_policy_ran_are_refused():
    with pytest.raises(OpenClawHostError, match="STALE_SESSION_REVISION"):
        adapter(store=Store()).authorize_tool("sid", "read", expected_revision=2)
    slow = adapter(store=Store(fail=lambda n: n == 2))                 # second check (after the callback) finds a blocking signal
    with pytest.raises(OpenClawHostError, match="REFLEX_BLOCKED_HEALTH_WARNING"):
        slow.authorize_tool("sid", "exec", expected_revision=3)


def test_effect_approval_must_be_exactly_true():
    with pytest.raises(OpenClawHostError, match="TOOL_EFFECT_DENIED"):
        adapter(approve=lambda s, t: "yes", store=Store()).authorize_tool("sid", "read", expected_revision=3)


def test_connect_needs_host_attested_full_interception_and_executable_needs_an_authorized_receipt():
    a = adapter(store=Store()).register()
    with pytest.raises(OpenClawHostError, match="OPENCLAW_RUNTIME_INTERCEPTION_INCOMPLETE"):
        a.connect(session_id="s", attested_capabilities={"pre_tool"}, attested_by="host")
    with pytest.raises(OpenClawHostError, match="OPENCLAW_HANDSHAKE_EVIDENCE_REQUIRED"):
        a.connect(session_id="", attested_capabilities=ALL, attested_by="host")
    with pytest.raises(OpenClawHostError, match="OPENCLAW_NOT_CONNECTED"):
        a.record_execution(session_id="s", receipt_id="r1")
    a.connect(session_id="s", attested_capabilities=ALL, attested_by="host")
    r = capability_report(a)["capabilities"]
    assert r[CONNECTED]["status"] == PROVEN and r[EXECUTABLE]["status"] == UNKNOWN            # connected is not executable
    a.record_execution(session_id="s", receipt_id="r1")
    assert capability_report(a)["capabilities"][EXECUTABLE]["status"] == PROVEN
    a.disconnect()
    assert capability_report(a)["capabilities"][CONNECTED]["status"] == ABSENT


def test_a_stopped_runtime_is_not_a_missing_adapter(monkeypatch, tmp_path):
    fake = tmp_path / "openclaw"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr(host, "_running_processes", lambda name: (True, []))
    adapter(store=Store()).register()
    rep = capability_report(binary="openclaw", install_paths=(str(fake),))
    assert rep["stopped_runtime"] is True and rep["adapter_missing"] is False
    assert rep["capabilities"][ADAPTER_REGISTERED]["status"] == PROVEN and rep["capabilities"][RUNTIME_INSTALLED]["status"] == PROVEN
    assert rep["capabilities"][RUNTIME_RUNNING]["status"] == ABSENT and rep["summary"] == RUNTIME_INSTALLED            # reached exactly as far as the evidence goes
    host._REGISTRY.clear()
    rep2 = capability_report(binary="openclaw", install_paths=(str(fake),))
    assert rep2["adapter_missing"] is True and rep2["stopped_runtime"] is True and rep2["summary"] == CODE_PRESENT


def test_nothing_is_promoted_without_evidence(monkeypatch):
    monkeypatch.setattr(host, "_running_processes", lambda name: (None, []))
    monkeypatch.setattr(host.shutil, "which", lambda b: None)
    rep = capability_report()
    assert rep["capabilities"][RUNTIME_RUNNING]["status"] == UNKNOWN                       # unreadable process table is unknown, not absent
    assert rep["capabilities"][CONNECTED]["status"] == UNKNOWN and rep["capabilities"][EXECUTABLE]["status"] == UNKNOWN
    assert rep["summary"] == CODE_PRESENT and "not a model provider" in rep["note"]


def test_module_has_no_peachme_import():
    import inspect
    assert "import peachme" not in inspect.getsource(host) and "from peachme" not in inspect.getsource(host)


def test_integration_with_the_real_peachme_session_store_if_installed(tmp_path):
    peachme = pytest.importorskip("peachme")
    store = peachme.SessionStore(tmp_path / "db.sqlite")
    sid = store.open("host").session_id
    res = store.reserve(sid, store.get(sid).revision)
    store.attach(sid, res, {"lease_id": "l", "neuron_id": "n", "role_id": "R", "cognitive_owner": "CONSUMER", "effective_skill_ids": []})
    rev = store.get(sid).revision
    a = adapter(store=store)
    a.authorize_tool(sid, "read", expected_revision=rev)
    with pytest.raises(OpenClawHostError, match="STALE_SESSION_REVISION"):
        a.authorize_tool(sid, "read", expected_revision=rev - 1)
    store.transition(sid, rev, "SUSPENDED")
    with pytest.raises(OpenClawHostError, match="OPENCLAW_SESSION_NOT_READY"):
        a.authorize_tool(sid, "read", expected_revision=rev + 1)
