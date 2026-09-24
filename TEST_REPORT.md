# Test Report — MangoMe v0.1.7

Date: 2026-09-24

Command:

```bash
PYTHONPATH=src python -m pytest --disable-warnings
```

Result in the packaging environment:

```text
.......................................sss............                   [100%]
51 passed, 3 skipped in 0.33s
```

Skipped checks:

- MCP surface integration: optional `mcp` dependency unavailable in the packaging sandbox.
- Two MongoDB integration checks: `MANGOME_TEST_MONGO_URI` not configured.

New v0.1.7 regression coverage includes:

- final verification rejects worker-authored PASS Evidence that was merely attested later but lacks an independent AV/1 observation;
- the last executor cannot submit its own independent verification observation;
- deterministic completion review surfaces scope deviations and changed-test review signals without treating them as automatic failures;
- `REPLAY` observations require an intact RB/1 reproduction binding, including when AV/1-shaped payloads are submitted through the generic Evidence path;
- approved `WAIVE_GATE` remains the explicit owner-governed exception to a gate Evidence requirement;
- existing v0.1.6 RB/1, filesystem, assurance, UAI/1, context and economics tests remain green.

This report is not a claim of full production validation. MangoMe does not execute AV/1 replay commands itself; an authorized verifier/host performs the observation and records it. The three skipped optional integration checks were not exercised in this packaging environment.
