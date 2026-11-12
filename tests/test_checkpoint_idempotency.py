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


def test_concurrent_replays_store_exactly_one_checkpoint():
    """KIwiMe Phase 0 audit D: find-then-insert let parallel outbox replays both insert. The unique key decides."""
    import threading
    svc, work = make()
    barrier, results = threading.Barrier(8), []

    def replay():
        barrier.wait()
        results.append(svc.checkpoint_work(work_ref=work, actor_id="cherryme", kind="RECOVERY_DECISION",
                                           payload={"idempotency_key": "receipt-7", "failure_class": "TIMEOUT"}))

    threads = [threading.Thread(target=replay) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({r["entity_id"] for r in results}) == 1
    assert len(svc.store.find("work_checkpoints")) == 1


def test_legacy_checkpoint_with_key_only_in_payload_is_still_found():
    svc, work = make()
    legacy = svc.store.insert("work_checkpoints", {"entity_id": "legacy-1", "work_id": work, "kind": "RECOVERY_DECISION",
                                                   "payload": {"idempotency_key": "old"}, "created_at": "2026-10-01T00:00:00Z"})
    again = svc.checkpoint_work(work_ref=work, actor_id="c", payload={"idempotency_key": "old"}, kind="RECOVERY_DECISION")
    assert again["entity_id"] == legacy["entity_id"] and len(svc.store.find("work_checkpoints")) == 1
