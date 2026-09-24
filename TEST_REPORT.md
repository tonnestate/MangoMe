# MangoMe v0.1.2 test report

Date: 2026-09-24

## Local result

```text
25 passed
2 skipped
```

The two local skips are intentional integration checks that require external runtime dependencies unavailable in this sandbox:

- `tests/test_mcp_surface.py` — requires the installed MCP Python SDK v2 package;
- `tests/test_mongo_integration.py` — requires `MANGOME_TEST_MONGO_URI` and a live MongoDB instance.

GitHub Actions is configured to install the declared dependencies and run both checks against MongoDB 7.

## Covered behavior

The test suite covers:

- plan-before-mutate;
- persistent plan binding after `start_slice`;
- rejection of progress/DONE mutations outside the bound plan;
- stable `DONE_CLAIMED / UNVERIFIED` state;
- verifier capability enforcement;
- dedicated VERIFIER runtime role without secrets in tool calls;
- worker inability to spoof owner authority;
- owner approval capability enforcement;
- evidence classification, verdict and attestation;
- PASS gates requiring attested PASS evidence;
- WAIVED gates requiring approved owner decision;
- self-verification denial;
- VERIFIED → approved ACCEPT_SLICE → ACCEPTED;
- gate audit metadata in the canonical schema;
- advisory collision warnings;
- closing plans after active slice bindings are released;
- declared contract ID collision preservation;
- effective family supersession/conflict view;
- typed graph endpoint/relation validation;
- project-level overview across multiple families;
- multi-project / multi-scope family membership;
- assurance-aware dependencies;
- revision compare-and-swap conflict detection;
- schema v1 → v2 lazy/persisted migration;
- generic Big-Bang ID discovery;
- non-destructive Big-Bang reconciliation;
- context compilation;
- durable model/cost receipts;
- health/readiness state.

## Build checks

- `python -m compileall -q src tests server.py` — PASS
- canonical/GitHub skill mirror diff — PASS
- wheel build with `--no-deps --no-build-isolation` — PASS

Built wheel:

```text
mangome_mcp-0.1.2-py3-none-any.whl
SHA-256: 8392e85fc56c307aa6242b59f4a74e17b08a6cf93eeb03661ec6253dd491ce2f
```

## CI expectation

`.github/workflows/ci.yml` runs Python 3.10, 3.11 and 3.12 with MongoDB 7 and the real `mcp>=2,<3` dependency. CI additionally verifies MCP v2 tool discovery and the Agent Skill mirror.
