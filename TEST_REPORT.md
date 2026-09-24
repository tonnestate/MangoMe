# MangoMe v0.1.1 patch test report

Date: 2026-09-24

## Local overlay test

The v0.1.1 patch was applied over the exact local v0.1.0 baseline and tested as an overlay.

Result:

```text
13 passed, 1 skipped
```

Passed coverage includes the original v0.1 tests plus new checks for:

- evidence-backed gate PASS;
- rejection of PASS without persisted evidence;
- separation of executor and verifier;
- approval-backed gate WAIVE;
- explicit VERIFIED → ACCEPTED owner/human acceptance;
- plan closing removing stale plans from active context;
- original plan-before-mutate, collision-warning, slice-state, Big-Bang and economics behavior.

Python bytecode compilation succeeded for `src`, `tests`, and `server.py`.

## Local environment limitations

The local sandbox does not have the external `mcp` package installed, so a live MCP import could not be executed locally.

The MongoDB integration test is present but is skipped locally unless `MANGOME_TEST_MONGO_URI` is configured.

## CI added by this patch

`.github/workflows/ci.yml` installs the declared dependencies and runs on Python 3.10, 3.11 and 3.12 with a MongoDB 7 service container. CI executes:

- all pytest tests including the real MongoDB persistence test;
- MCP import smoke test;
- Agent Skill mirror consistency check;
- Python source compilation.

The GitHub Actions result after upload is therefore the authoritative integration result for external MCP/PyMongo dependencies.
