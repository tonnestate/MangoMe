# Changelog

## 0.1.4 — 2026-09-24

- Fixed MongoDB create operations that persisted successfully but failed as MCP tool responses because PyMongo injected a BSON `ObjectId` into the returned Python mapping. MongoDB storage documents and MangoMe wire/domain documents are now separated.
- Added regression coverage for BSON `_id` leakage and real MongoDB MCP create serialization.
- Made `health` a safe observability boundary: MCP and CLI health now return sanitized `ok: false` diagnostics when backing-store bootstrap/authentication fails instead of crashing with a generic tool error.
- Health diagnostics never include connection strings, passwords, tokens, or raw exception messages.

## 0.1.3 — 2026-09-24

- Repositioned MangoMe explicitly as canonical operational memory: document store + work graph + state machine + contract history + evidence/provenance ledger + execution economics + context compiler.
- Added UAI/1, a versioned compact semantic transport profile for sending bounded MangoMe execution truth to expensive workers without retransmitting the verbose canonical context shape.
- Added SHA-256 semantic binding and deterministic UAI/1 round-trip expansion; tampered packets are rejected.
- Added UAI/1R structured worker results with validated action codes for progress, artifacts, evidence, DONE claims, discovered slices and blockers.
- Added deterministic English/German rendering of UAI/1R results. Decoding/rendering never mutates canonical state.
- Added `compile_uai_context`, `expand_uai_context`, `decode_uai_result` and `render_uai_result` MCP tools plus matching CLI utilities.
- Added `begin_work`, a convenience composition of intake -> current spec -> plan -> slice start for bounded work. It preserves the same persisted entities and enforcement rules.
- Extended execution receipts/model statistics with `context_tokens_interlingua`, `output_tokens_interlingua` and `interlingua_version` for empirical cost-per-verified-outcome comparisons.
- Advanced persisted schema to version 3 with lazy/explicit migration support for interlingua telemetry fields.
- Added design-decision documentation making MongoDB the intentional canonical production backend and keeping alternate production stores/federation out of current scope.
- Expanded Agent Skill and CI with UAI round-trip behavior and restored `.github/skills/mangome/SKILL.md` in the package.
- Added UAI/1 examples and regression coverage for round-trip equality, hash tampering, stale result rejection, deterministic rendering, convenience work start and interlingua economics.

## 0.1.2 — 2026-09-24

- Closed the plan-before-mutate loophole by binding active slices to the persisted `plan_id`; progress updates and DONE claims must remain on that binding.
- Added runtime verifier and owner-approval capabilities (`MANGOME_VERIFIER_TOKEN`, `MANGOME_APPROVAL_TOKEN`) with optional actor allowlists; capability values are never persisted.
- Added evidence classes, verdicts, trust state and explicit evidence attestation. Gate PASS now requires admissible attested PASS evidence.
- Promoted gate audit fields (`decided_by`, `decided_at`, `approval_id`) into the canonical schema.
- Added `revision` compare-and-swap protection for mutable MangoMe state.
- Added schema version 2 with reader-side lazy upgrade and explicit dry-run/apply migration support.
- Added assurance-aware slice dependencies (`DONE_CLAIMED`, `VERIFIED`, `ACCEPTED`).
- Added validated entity/relation types for graph edges and same-family enforcement for contract-evolution relations.
- Added `effective_family_view` for active contract contributions, supersession, conflicts and suggested relations.
- Added deterministic `project_overview` across all known families in a project.
- Generalized Big-Bang identifier extraction; removed project-prefix hard-coding.
- Added non-destructive Git discovery (origin, HEAD, branches, worktrees, recent commits) and `reconcile_bigbang` advisory matching.
- Expanded deterministic maintenance diagnostics and explicit schema migration.
- Consolidated the MCP surface back into one `mcp_server.py`; `mcp_integrity.py` is now a compatibility shim.
- Added health/readiness reporting.
- Added human-control CLI commands that read approval/verifier capabilities from environment rather than command-line arguments.
- Added MCP v2 in-process tool-discovery coverage and expanded regression tests.
- Updated README to the IntakeGov-style header and corrected MCP v2 CLI examples.

## 0.1.1 — 2026-09-24

- Added v0.1.1 integrity layer without rewriting the v0.1 domain service.
- PASS gates require persisted evidence belonging to the same slice.
- WAIVED gates require an approved `WAIVE_GATE` decision.
- The last executing actor may not verify its own `DONE_CLAIMED` state.
- Added explicit `VERIFIED` → approved `ACCEPT_SLICE` → `ACCEPTED` path.
- Added MCP tools for artifacts, graph edges, plan closing and approval lifecycle.
- Added MongoDB integration coverage and CI scaffold.

## 0.1.0 — 2026-09-24

- Initial MangoMe domain model and MCP server.
- Intake, specifications, contract families and append-only contract contributions.
- Persistent slices with independent execution and assurance states.
- Mandatory plan-before-mutate execution.
- Advisory multi-agent collision detection.
- Claims, evidence and acceptance-gate verification model.
- Deterministic family/project status projection.
- Non-destructive Big-Bang filesystem discovery.
- Compact execution-context compiler.
- Model registry and durable-cost execution receipts.
