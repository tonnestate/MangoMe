# MangoMe v0.1.3 test report

Date: 2026-09-24

## Local result

```text
33 passed, 2 skipped
```

The two local skips are expected integration boundaries:

- `tests/test_mcp_surface.py` — external `mcp>=2` package is not installed in the local sandbox;
- `tests/test_mongo_integration.py` — no `MANGOME_TEST_MONGO_URI` is configured locally.

GitHub Actions installs the declared MCP dependency and runs MongoDB 7 as a service, so those two integration paths are exercised after the dot-prefixed `.github` workflow is present in the repository.

## v0.1.3 coverage added

- UAI/1 semantic execution projection;
- exact projection round-trip through compact wire format;
- SHA-256 semantic hash tampering detection;
- UAI/1R stale-context rejection;
- structured UAI result decoding without state mutation;
- deterministic English/German result rendering;
- `begin_work` composition while preserving persisted Request/Plan/Slice truth;
- refusal of duplicate active-slice convenience starts before new Request/Plan side effects;
- refusal of `begin_work` when no effective specification exists;
- interlingua token telemetry in execution receipts/model statistics;
- schema v3 migration behavior;
- MCP surface expectations for UAI and convenience tools.

## Additional validation

- Python bytecode compilation succeeded for `src`, `tests`, `examples` and `server.py`.
- `examples/uai_roundtrip.py` executed successfully with the in-memory backend.
- Local wheel build/install succeeded for `mangome-mcp==0.1.3` with `--no-deps --no-build-isolation`.
- Canonical and GitHub Agent Skill copies are byte-identical in the package.

## Demonstration compression measurement

A representative local v0.1.3 demo context measured:

```text
raw compiled context: 3,819 chars
UAI/1 wire:             729 chars
character reduction:    80.91%
```

This is a serialization demonstration, not a provider tokenizer benchmark. v0.1.3 therefore stores actual provider-reported UAI input/output token counts separately in `ExecutionReceipt`.

## Wheel artifact

```text
mangome_mcp-0.1.3-py3-none-any.whl
SHA-256: c3620ec5495425e59db839671375d116d5fdd9069504cfdb7e8a430979c2ffc4
```
