"""Regression tests H1-H3 (owner chronology 11-29 Oct) on real MongoDB. Skipped without MANGOME_TEST_MONGO_URI."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db_guard import DatabaseInUse, claim_database, release_database  # noqa: E402
from mangome.storage.mongo import MongoStore  # noqa: E402

URI = os.environ.get("MANGOME_TEST_MONGO_URI")
pytestmark = pytest.mark.skipif(not URI, reason="MANGOME_TEST_MONGO_URI not configured")
SRC = str(Path(__file__).resolve().parent.parent / "src")


def run_py(code: str, database: str, extra_env=None, wait=True):
    env = {**os.environ, "PYTHONPATH": SRC, "MANGOME_BACKEND": "mongo", "MANGOME_MONGODB_URI": URI, "MANGOME_DATABASE": database, "MANGOME_ZERO_TOUCH_BOOTSTRAP": "0",
           "PYTHONDONTWRITEBYTECODE": "1", **(extra_env or {})}
    p = subprocess.Popen([sys.executable, "-c", textwrap.dedent(code)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if not wait:
        return p
    out, err = p.communicate(timeout=120)
    assert p.returncode == 0, err[-1500:]
    return json.loads(out.strip().splitlines()[-1])


def drop(database):
    store = MongoStore(URI, database)
    store.client.drop_database(database)
    store.client.close()


WORKER = """
import json, sys, time, tempfile, os
sys.path.insert(0, %r)
from db_guard import claim_database
from mangome.work_control import WorkGovernedMangoMeService
from mangome.storage.mongo import MongoStore
db = os.environ["MANGOME_DATABASE"]
claim_database(db)
svc = WorkGovernedMangoMeService(MongoStore(os.environ["MANGOME_MONGODB_URI"], db))
r = svc.enter_work(workspace_id=tempfile.mkdtemp(), workspace_title="h1", actor_id="worker", request_text="fix the h1 problem now")
work, turn = r["work_identity"]["entity_id"], r["turn"]["entity_id"]
ok = []
for _ in range(15):
    t = svc.store.get("work_turn_bindings", turn)
    ok.append(bool(t) and t.get("work_id") in (work,) and t.get("actor_id") == "worker" and t.get("status") in ("BOUND", "ACTIVE") and t.get("mode") in ("CONTINUE", "EXECUTE"))
    time.sleep(0.2)
print(json.dumps({"db": db, "all_authorized": all(ok), "n": len(ok)}))
""" % str(Path(__file__).resolve().parent)


def test_h1_two_concurrent_processes_each_own_database_and_turn_stay_authorized():
    dbs = [f"mangome_h1_{uuid.uuid4().hex}" for _ in range(2)]
    procs = [run_py(WORKER, d, wait=False) for d in dbs]
    try:
        results = []
        for p in procs:
            out, err = p.communicate(timeout=180)
            assert p.returncode == 0, err[-1500:]
            results.append(json.loads(out.strip().splitlines()[-1]))
        assert [r["all_authorized"] for r in results] == [True, True] and {r["db"] for r in results} == set(dbs)
    finally:
        for d in dbs:
            drop(d)
            release_database(Path(tempfile.gettempdir()) / "mangome-test-db-locks" / f"{d}.lock")


def test_h1_fixture_refuses_a_database_in_use_by_another_live_process(tmp_path):
    holder = subprocess.Popen([sys.executable, "-c", f"import sys,time; sys.path.insert(0,{str(Path(__file__).resolve().parent)!r}); from db_guard import claim_database; from pathlib import Path; claim_database('shared_scratch', Path({str(tmp_path)!r})); print('claimed', flush=True); time.sleep(30)"],
                              stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "claimed"
        with pytest.raises(DatabaseInUse, match="DATABASE_IN_USE"):
            claim_database("shared_scratch", tmp_path)
    finally:
        holder.kill()
        holder.wait()
    claim_database("shared_scratch", tmp_path)          # a dead holder no longer blocks the name


def test_h2_second_run_on_same_work_reconciles_to_same_identity_without_new_enter_work():
    database = f"mangome_h2_{uuid.uuid4().hex}"
    code = """
        import json, os, tempfile
        from mangome import worker_mcp_server as w
        ws = os.environ["MANGOME_WORKSPACE_ROOT"]
        first = w.mangome_work("ENTER_WORK", {"actor_id": "host", "request_text": "fix the h2 problem in the code"})
        work = first["result"]["work_identity"]["entity_id"]
        print(json.dumps({"work": work, "ok": first["ok"]}))
    """
    ws = tempfile.mkdtemp()
    try:
        env = {"MANGOME_WORKSPACE_ROOT": ws}
        one = run_py(code, database, env)
        restart = """
            import json
            from mangome import worker_mcp_server as w
            from mangome.runtime import get_service
            rec = w.mangome_work("RECONCILE_ASSIGNMENT", {"request_text": "fix the h2 problem in the code"})
            store = get_service().store
            print(json.dumps({"ok": rec["ok"], "disposition": rec["result"].get("disposition") if isinstance(rec["result"], dict) else None,
                              "matched": json.dumps(rec["result"], default=str), "identities": len(store.find("work_identities"))}))
        """
        two = run_py(restart, database, env)
        assert one["ok"] and two["ok"]
        assert one["work"] in two["matched"] and two["identities"] == 1       # same WorkIdentity, ENTER_WORK count stays 1
        assert "MATCHED" in two["matched"]
    finally:
        drop(database)


def test_h3_recovery_says_bind_or_reconcile_and_enter_work_binds_without_control_op():
    database = f"mangome_h3_{uuid.uuid4().hex}"
    code = """
        import json, os
        from mangome import worker_mcp_server as w
        from mangome.runtime import get_service
        first = w.mangome_work("ENTER_WORK", {"actor_id": "host", "request_text": "fix the h3 problem in the code"})
        work = first["result"]["work_identity"]["entity_id"]
        rec = w.mangome_observe("RECOVERY_CONTEXT", {})
        bound = w.mangome_work("ENTER_WORK", {"actor_id": "host", "request_text": "fix the h3 problem in the code", "work_ref": work})
        turn = bound["result"]["turn"]
        stored = get_service().store.get("work_turn_bindings", turn["entity_id"])
        print(json.dumps({"rec": rec["recommended_next_action"], "auth": rec["result"].get("current_turn_execution_authorized"),
                          "step": "ENTER_WORK" in rec["result"].get("current_turn_next_step", ""), "bound_ok": bound["ok"],
                          "turn_status": stored["status"], "turn_mode": stored["mode"], "turn_work": stored["work_id"] == work}))
    """
    ws = tempfile.mkdtemp()
    try:
        r = run_py(code, database, {"MANGOME_WORKSPACE_ROOT": ws})
        assert r["rec"] == "BIND_OR_RECONCILE_CURRENT_TURN" and r["auth"] is False and r["step"] is True
        assert r["bound_ok"] and r["turn_status"] in ("BOUND", "ACTIVE") and r["turn_mode"] in ("EXECUTE", "CONTINUE") and r["turn_work"]
    finally:
        drop(database)
