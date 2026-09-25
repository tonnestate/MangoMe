# Test Report — MangoMe v0.1.9rc3

Date: 2026-09-25

Baseline: reconstructed v0.1.9rc2 release-candidate surface plus the authoritative-recovery, delegation-governance, and operational-language corrections.

## Local deterministic suite

Command:

```bash
PYTHONPATH=src python -m pytest -ra
```

Result in the packaging environment:

```text
86 passed, 3 skipped in 0.42s
```

Skipped checks in this packaging environment:

- MCP in-process surface integration: the optional/runtime `mcp` package is unavailable in this sandbox interpreter.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this sandbox.

These are environment skips, not PASS claims. The published GitHub Actions workflow remains responsible for executing the MCP surface test and MongoDB-backed checks.

## Additional checks

```text
python -m compileall -q src tests server.py                         PASS
MANGOME_BACKEND=memory PYTHONPATH=src python examples/uai_roundtrip.py PASS
PYTHONPATH=src make check                                           PASS
python -m pip wheel --no-deps --no-build-isolation .                PASS
wheel: mangome_mcp-0.1.9rc3-py3-none-any.whl                       PASS
wheel SHA-256: d298392aaef9df8423ee18195613f7484f057e3f847884dc39b3699d6dab3873
four Agent Skill surfaces byte-identical                            PASS
```

## Release-candidate scope

v0.1.9rc3 closes two observed governance failures: a parent agent reconstructed admitted state through broad repository/filesystem/path discovery, and multiple parent-agent families escalated bounded MangoMe work to high-cost subagents without an explicit task-bound routing authorization.

The release adds:

- canonical `recovery_context` derived from MangoMe Project/Family/Specification/Plan/Slice/Artifact/Evidence state;
- admitted-work state-source signaling in `workspace_status`;
- fail-closed MCP discovery boundaries for overlapping admitted work;
- targeted-only filesystem reference lookup for identities MangoMe already knows;
- stronger always-on Claude/Codex recovery instructions and all four Agent Skill surfaces;
- authoritative recovery documentation;
- UAI/1 semantic-hash scope clarification;
- explicit high-assurance MongoDB credential boundary guidance;
- restoration of required dotfile release surfaces in the upload package;
- current-runtime capability/cost eligibility and persisted delegation checkpoints;
- prevention of silent high-cost swarm fan-out through task-bound Owner authorization plus one-active-high-cost-delegation-per-family; high-tier escalation is never implied by difficulty, urgency, importance, self-repair, or capability loss;
- explicit external-dispatch integration boundary (policy is implemented; provider dispatch enforcement is not falsely claimed);
- operational-language inheritance for human-visible coordinator/recovery/control-plane narration.

No second truth store, new assurance state taxonomy, global repository lock, or replacement persistence backend is introduced.

## GitHub Actions release gate

The rc3 delta includes `.github/workflows/ci.yml` because the inspected public `main` tree still lacked that required dotfile after the rc2 upload. After upload, the workflow must:

- run the full Python 3.10/3.11/3.12 test matrix;
- execute MongoDB integration tests against MongoDB 7 without skips;
- run a Mongo-backed health assertion;
- run the MCP in-process surface test, including `recovery_context` discovery;
- run the UAI round-trip example;
- verify all four Agent Skill surfaces are byte-identical;
- compile `src`, `tests`, and `server.py`.

A local PASS is not a substitute for the post-upload GitHub Actions result.
