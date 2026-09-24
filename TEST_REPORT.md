# Test Report — MangoMe v0.1.6

Date: 2026-09-24

Command:

```bash
PYTHONPATH=src python -m pytest --disable-warnings
```

Result in the packaging environment:

```text
.................................sss............                         [100%]
45 passed, 3 skipped in 0.28s
```

Skipped checks:

- MCP surface integration: optional `mcp` dependency unavailable in the packaging sandbox.
- Two MongoDB integration checks: `MANGOME_TEST_MONGO_URI` not configured.

New v0.1.6 coverage includes RB/1 deterministic fingerprinting, input hash binding, SOURCE/TEST stale reason codes, Git-context matching/drift, output Artifact disappearance, non-zero PASS contradiction, fingerprint tampering, sensitive environment-name rejection, and v0.1.5 filesystem-binding compatibility.

This report is not a claim of full production validation; it records the test scope that actually ran in this packaging environment.
