# Test Report — MangoMe v0.1.9rc1

Date: 2026-09-25

Baseline: public `tonnestate/MangoMe` main after v0.1.8.1 and removal of the obsolete `PATCH_MANIFEST.md`, plus the v0.1.9rc1 release-candidate delta.

## Local deterministic suite

Command:

```bash
PYTHONPATH=src python -m pytest --disable-warnings
```

Result in the packaging environment:

```text
77 passed, 3 skipped in 0.46s
```

Skipped checks in this packaging environment:

- MCP in-process surface integration: the optional/runtime `mcp` package is unavailable in this sandbox interpreter.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this sandbox.

These are environment skips, not PASS claims.

## Additional checks

```text
python -m compileall -q src tests server.py                         PASS
MANGOME_BACKEND=memory python examples/uai_roundtrip.py             PASS
python -m pip wheel --no-deps --no-build-isolation .                PASS
wheel contains mangome/operability.py                               PASS
wheel contains mangome/skill/SKILL.md                               PASS
.github/workflows/ci.yml present                                    PASS
.github/skills/mangome/SKILL.md present                             PASS
.gitignore present                                                   PASS
canonical/package/GitHub Skill copies byte-identical                PASS
```

The wheel produced by this check is normalized as `mangome_mcp-0.1.9rc1-...whl`.

## GitHub Actions release-candidate gate

The v0.1.9rc1 workflow is part of this delta and is intended to become the authoritative published-repository check after upload. It runs on Python 3.10, 3.11, and 3.12 and provisions MongoDB 7.

The workflow:

- installs the package with development dependencies;
- runs the full test suite;
- runs `tests/test_mongo_integration.py` against the CI MongoDB service;
- fails explicitly if those MongoDB integration tests are skipped while MongoDB is available;
- runs a real Mongo-backed `health_snapshot()` readiness assertion;
- runs the MCP in-process surface smoke test;
- runs the UAI round-trip example;
- verifies the three Agent Skill copies are byte-identical;
- compiles `src`, `tests`, and `server.py`.

A local packaging PASS is not a substitute for the post-upload GitHub Actions result. The release candidate should not be promoted to final v0.1.9 until the published-tree workflow is green.

## Release-candidate scope

v0.1.9rc1 carries forward the v0.1.8.1 evaluation-driven integrity and zero-touch repairs and fixes the published repository surface/CI gap. It does not introduce a second truth store, new assurance states, or silently promote discovery candidates into canonical truth.
