# Test Report — MangoMe v0.1.8.1

Date: 2026-09-25

Baseline: public `tonnestate/MangoMe` v0.1.8 (`8f34f334cb71d3e4c76b4b11f230f9c4ffec9eb2`) plus the v0.1.8.1 repair delta.

## Deterministic suite

Command:

```bash
PYTHONPATH=src python -m pytest --disable-warnings
```

Result in the packaging environment:

```text
..........................................sss........................... [ 90%]
........                                                                 [100%]
77 passed, 3 skipped in 0.37s
```

Skipped checks:

- MCP in-process surface integration: optional `mcp` dependency is not installed in this offline packaging sandbox.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this sandbox.

These are environment skips, not PASS claims.

## Additional deterministic checks

```text
PYTHONPATH=src make check                                             PASS
python -m compileall -q src tests server.py                         PASS
skill/mangome/SKILL.md == src/mangome/skill/SKILL.md              PASS
skill/mangome/SKILL.md == .github/skills/mangome/SKILL.md          PASS
MANGOME_BACKEND=memory python examples/uai_roundtrip.py             PASS
python -m pip wheel --no-deps --no-build-isolation .                PASS
wheel contains mangome/operability.py                               PASS
wheel contains mangome/skill/SKILL.md                               PASS
CLI setup/attest argument parsing                                    PASS
```

`python -m build` itself was unavailable because the sandbox does not have the optional `build` package installed; `pip wheel --no-build-isolation` successfully built `mangome_mcp-0.1.8.1-py3-none-any.whl` instead.

## v0.1.8.1 regression coverage

The repair suite now covers the concrete findings from the first direct-harness / Claude Code evaluation, including:

- H1: imported `VERIFIED` / `ACCEPTED` assurance is preserved only as historical imported state and authoritative assurance starts `UNVERIFIED`;
- H2: an already `VERIFIED` / `ACCEPTED` Slice cannot be re-verified and downgraded/duplicated;
- H3: the authoritative `VERIFIED` Slice write carries verifier identity plus exact verification Evidence and AV/1 observation ids, while maintenance flags historical provenance gaps;
- H4: supported UAI/1R decode/render paths require the expected semantic context hash;
- F-OPS-001: managed client binding preserves the active virtual-environment interpreter path instead of resolving through a symlink to a base interpreter;
- F-OPS-002 / scope: Claude Code defaults to private LOCAL scope and live attestation does not treat `Pending approval` or mere name visibility as an effective connection;
- F-OPS-003: first attachment is not immediately overwritten by a second refresh that reports `first_attach=false`;
- F-OPS-004: ordinary work can enter the full governed lifecycle through `enter_work` without a user-supplied MangoMe `declared_id`; deterministic `AUTO-*` ids are generated where required and worker-facing lifecycle errors are structured;
- F-MAINT-001: maintenance diagnostics normalize naive Mongo/BSON-style datetimes before comparison;
- F-ENV-001: Python 3.10 compatibility is restored with conditional `tomli` fallback/dependency;
- zero-touch truth boundary: discovery remains candidate-only, while current client-relayed user intent can create new canonical operational work through the normal Specification → Plan → Slice path;
- derived `truth_level` distinguishes canonical unverified work, worker claims, verified work and accepted work without introducing a second assurance state machine.

## Scope of this report

This is a deterministic repair/packaging report. It does not repeat the earlier long-running Claude Code/Opus campaign and does not claim that every external client/runtime behavior was re-tested in this sandbox. The existing evaluation remains the pre-repair baseline; v0.1.8.1 is intended to rerun the already-known focused regression cases rather than launch another monolithic model evaluation.
