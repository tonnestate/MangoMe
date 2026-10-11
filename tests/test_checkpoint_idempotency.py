"""HANDOVER-002 Part D: recovery evidence is written idempotently (key = PlumMe receipt hash), so an outbox replay never duplicates it."""
from __future__ import annotations

from mangome.storage.memory import InMemoryStore
from mangome.work_control import WorkGovernedMangoMeService


def make():
    svc = WorkGovernedMangoMeService(InMemoryStore())
    work = svc.enter_work(workspace_id="/w", workspace_title="w", actor_id="a", request_text="research")["work_identity"]["entity_id"]
    return svc, work


def test_same_idempotency_key_returns_the_stored_checkpoint():
    svc, work = make()
    payload = {"idempotency_key": "hash-1", "failure_class": "QUOTA_EXHAUSTED"}
    first = svc.checkpoint_work(work_ref=work, actor_id="cherryme", payload=payload, kind="RECOVERY_DECISION")
    again = svc.checkpoint_work(work_ref=work, actor_id="cherryme", payload=dict(payload), kind="RECOVERY_DECISION")
    assert again["entity_id"] == first["entity_id"] and len(svc.store.find("work_checkpoints")) == 1


def test_key_is_scoped_to_work_and_kind_and_absent_key_never_dedupes():
    svc, work = make()
    other = svc.enter_work(workspace_id="/w", workspace_title="w", actor_id="a", request_text="other")["work_identity"]["entity_id"]
    svc.checkpoint_work(work_ref=work, actor_id="c", payload={"idempotency_key": "k"}, kind="RECOVERY_DECISION")
    svc.checkpoint_work(work_ref=other, actor_id="c", payload={"idempotency_key": "k"}, kind="RECOVERY_DECISION")   # other work
    svc.checkpoint_work(work_ref=work, actor_id="c", payload={"idempotency_key": "k"}, kind="DEFERRED")            # other kind
    svc.checkpoint_work(work_ref=work, actor_id="c", payload={"x": 1})
    svc.checkpoint_work(work_ref=work, actor_id="c", payload={"x": 1})                                             # no key: two rows
    assert len(svc.store.find("work_checkpoints")) == 5


def test_checkpoint_never_creates_work_identity():
    import pytest
    svc, _ = make()
    before = len(svc.store.find("work_identities"))
    with pytest.raises(KeyError):
        svc.checkpoint_work(work_ref="does-not-exist", actor_id="c", payload={"idempotency_key": "k"}, kind="DEFERRED")
    assert len(svc.store.find("work_identities")) == before
