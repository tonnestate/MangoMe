# Test Report — MangoMe v0.1.7.1

Date: 2026-09-24

Command:

```bash
PYTHONPATH=src python -m pytest --disable-warnings
```

Result in the packaging environment:

```text
..........................................sss............                [100%]
54 passed, 3 skipped in 0.29s
```

Skipped checks:

- MCP surface integration: optional `mcp` dependency unavailable in the packaging sandbox.
- Two MongoDB integration checks: `MANGOME_TEST_MONGO_URI` not configured.

New v0.1.7.1 regression coverage includes:

- generic `submit_evidence` cannot populate the reserved AV/1 `verification_observation` namespace;
- a legacy/direct AV/1-shaped payload without dedicated verifier-path provenance cannot become independent AV/1 proof merely through later verifier attestation;
- AV/1 independent observations require verifier-originated trust;
- RB/1-bound AV/1 PASS Evidence is live-checked again immediately before final `VERIFIED` CAS; changing a bound input after observation blocks verification;
- the equivalent unchanged RB/1 replay path still verifies successfully;
- all existing v0.1.7 AV/1, v0.1.6 RB/1, filesystem, assurance, UAI/1, context and economics tests remain green.

This report is not a claim of full production validation. MangoMe does not execute AV/1 replay commands itself. The final RB/1 re-check reduces the practical artifact-change window but is not a distributed atomic transaction across arbitrary external artifact stores and MongoDB. The three skipped optional integration checks were not exercised in this packaging environment.
