# Test Report — MangoMe v0.1.9rc2

Date: 2026-09-25

Baseline: reconstructed public `tonnestate/MangoMe` v0.1.9rc1 release-candidate surface plus the reconciliation-reasoning / Agent-Skill-surface delta.

## Local deterministic suite

Command:

```bash
PYTHONPATH=src python -m pytest -ra
```

Result in the packaging environment:

```text
78 passed, 3 skipped in 0.37s
```

Skipped checks in this packaging environment:

- MCP in-process surface integration: the optional/runtime `mcp` package is unavailable in this sandbox interpreter.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this sandbox.

These are environment skips, not PASS claims.

The 78 passing tests include repository-surface regression coverage requiring all four Agent Skill copies to exist and remain byte-identical.

## Additional checks

```text
python -m compileall -q src tests server.py                         PASS
MANGOME_BACKEND=memory python examples/uai_roundtrip.py             PASS
PYTHONPATH=src make check                                           PASS
python -m pip wheel --no-deps --no-build-isolation .                PASS
wheel contains mangome/operability.py                               PASS
wheel contains mangome/skill/SKILL.md                               PASS
.github/workflows/ci.yml present                                    PASS
.github/skills/mangome/SKILL.md present                             PASS
.claude/skills/mangome/SKILL.md present                             PASS
.gitignore present                                                   PASS
canonical/package/GitHub/Claude Skill copies byte-identical         PASS
```

The wheel produced by this check is normalized as `mangome_mcp-0.1.9rc2-py3-none-any.whl`.

## Reconciliation-reasoning scope

The release candidate makes the reasoning doctrine explicit without changing MangoMe's assurance lifecycle:

```text
N = normative truth
O = observed truth
X = agent-selected expansion context
J = f(N_scope, O_scope, X)
```

The Skill instructs workers to reconcile authoritative N/O state rather than reconstruct known facts from conversation history. It preserves agent-controlled exploration and action within the existing admitted Plan, while truth mutation and final verification remain on governed paths.

No new truth store, graph engine, assurance state, verifier bypass or hard action cage is introduced.

## GitHub Actions release-candidate gate

The v0.1.9rc2 workflow remains a published-repository check and runs on Python 3.10, 3.11, and 3.12 with a MongoDB 7 service.

The workflow:

- installs the package with development dependencies;
- runs the full test suite;
- runs `tests/test_mongo_integration.py` against the CI MongoDB service;
- fails explicitly if those MongoDB integration tests are skipped while MongoDB is available;
- runs a real Mongo-backed `health_snapshot()` readiness assertion;
- runs the MCP in-process surface smoke test;
- runs the UAI round-trip example;
- verifies all four Agent Skill surfaces are present and byte-identical;
- compiles `src`, `tests`, and `server.py`.

A local packaging PASS is not a substitute for the post-upload GitHub Actions result. v0.1.9rc2 should remain a release candidate until the published-tree workflow is green.
