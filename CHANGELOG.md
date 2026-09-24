# Changelog

## 0.1.1 — 2026-09-24

- Added v0.1.1 integrity layer without rewriting the v0.1 domain service.
- PASS gates now require persisted evidence belonging to the same slice.
- WAIVED gates now require an approved `WAIVE_GATE` decision.
- The last executing actor may no longer verify its own `DONE_CLAIMED` state.
- Added explicit owner/human acceptance path: `VERIFIED` → approved `ACCEPT_SLICE` → `ACCEPTED`.
- Added MCP tools for artifacts, typed graph edges, plan closing, approval lifecycle, controlled gate updates, and acceptance.
- Added approval rejection/listing and optional decision references.
- Added GitHub Actions CI with Python 3.10–3.12, MongoDB 7 integration test, MCP import smoke test, and skill mirror check.
- Added `.gitignore` and restored the GitHub Agent Skill mirror.
- Added real MongoDB persistence coverage and integrity regression tests.

## 0.1.0 — 2026-09-24

- Initial MangoMe domain model and MCP server.
- Intake, specifications, contract families and append-only contract contributions.
- Persistent slices with independent execution and assurance states.
- Mandatory plan-before-mutate execution.
- Advisory multi-agent collision detection.
- Claims, evidence and hard acceptance-gate verification.
- Deterministic family/project status projection.
- Non-destructive Big-Bang filesystem discovery.
- Compact execution-context compiler.
- Model registry and durable-cost execution receipts.
- Canonical Agent Skill plus GitHub mirror.
