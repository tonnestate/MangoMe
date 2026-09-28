# Test Report — MangoMe v0.3.10

Date: 2026-09-28

Base: public `tonnestate/MangoMe` v0.3.9 commit `8a58e18f0772c2f7a9254067a64d01d7dc2fe1ba`.

## Local release validation

The v0.3.10 web-upload candidate was reconstructed on the exact v0.3.9 file baseline and validated as normal repository files; no patch/applicator is required by the release artifact.

Commands:

```bash
PYTHONPATH=src python -m pytest -ra
PYTHONPATH=src python -m compileall -q src tests server.py
make check
python -m pip wheel --no-deps --no-build-isolation .
```

Result:

```text
184 passed, 3 skipped
compileall PASS
make check PASS
wheel build PASS
mangome_mcp-0.3.10-py3-none-any.whl
packaged mangome/skill/SKILL.md PASS
packaged mangome/effect_control.py PASS
```

Skipped checks:

- MCP in-process surface integration: the `mcp` dependency is not installed in this packaging interpreter.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this packaging environment.

These skips are not PASS claims. MCP in-process and real MongoDB integration remain environment-dependent acceptance checks and must be run in a clean environment with the required dependency/service configured.

The host container's global `pip check` is not a MangoMe release signal because it contains an unrelated pre-existing `moviepy`/`pillow` conflict outside this repository.

## v0.3.10 regression focus

The release suite covers the new PER/1 and Slice lifecycle semantics plus the review fixes:

- `DONE_CLAIMED` opens validation rather than implying Slice completion;
- `REWORK_REQUIRED` reopens execution and clears stale current-validation fields;
- verification requires `VALIDATED` for WorkIdentity-bound work;
- `VERIFIED + OPEN` is valid while a required external effect is unresolved;
- positive PER/1 reconciliation requires a `CONFIRMED` observation, a VERIFY WorkTurn, and verifier authority;
- effect identity is deterministic and concurrent duplicate intent remains idempotent;
- changed provider idempotency/expected-state data cannot silently reuse a logical effect key;
- recovery exposes rework and pending-closure state through the active recovery methods without granting current-turn execution authority;
- family status exposes validation/closure counts and unresolved required effects;
- materialized project views use `CURRENT_SCHEMA_VERSION` rather than persisting stale schema metadata;
- legacy non-WorkIdentity acceptance remains compatible;
- schema/version regression tests advance with schema v6 / release 0.3.10;
- canonical and packaged Agent Skill copies remain byte-identical;
- Release surfaces and the optional repository-local Skill-mirror policy are regression-checked.

## Post-upload acceptance

After upload, run the environment-dependent acceptance checks on the actual MangoMe host and confirm:

```text
1. health reports runtime version 0.3.10 and database=mangome.
2. Existing v0.3.9 canonical state reads successfully through schema v6 compatibility.
3. A DONE_CLAIMED WorkIdentity Slice enters PENDING validation.
4. REWORK_REQUIRED can resume only through a newly bound current turn.
5. A required external effect with UNKNOWN outcome cannot be blindly redispatched.
6. VERIFIED work remains OPEN until every required PER/1 effect is reconciled satisfied.
7. Recovery exposes unfinished/rework/closure work but productive_execution_allowed remains false until current intent is bound.
```
