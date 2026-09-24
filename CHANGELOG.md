# Changelog

## 0.1.6 — 2026-09-24

- Added RB/1 structured reproduction bindings inside existing `Evidence.payload`; no new Proof entity or parallel assurance lifecycle.
- Added `build_reproduction_binding`, which records a declared command, caller-supplied exit code, current/provided Git commit, hashed relevant input files, optional output Artifact, stdout/stderr hashes and environment-variable names without executing the command.
- Added deterministic RB/1 fingerprinting with canonicalized input ordering and explicit fingerprint-integrity checks.
- Environment values are never stored by RB/1; names that look like passwords, tokens, secrets, API keys, private keys or credentials are rejected.
- Extended `evidence_freshness` with RB/1 checks and explicit reason codes such as `SOURCE_CHANGED`, `TEST_CHANGED`, `OUTPUT_MISSING`, `COMMIT_CHANGED`, `FINGERPRINT_MISMATCH` and `EXIT_CODE_NONZERO`.
- A changed Git HEAD with unchanged declared input hashes is conservatively `UNKNOWN`, not silently reusable or automatically stale.
- Preserved v0.1.5 `filesystem_bindings` compatibility.
- RB/1 freshness never reruns commands, infers requirement coverage, transfers proof across slices, creates `VERIFIED`/`ACCEPTED`, or fabricates historical slices.
- Clarified README claims around UAI character reduction, authorized acceptance, filesystem-scan scope, proof freshness and test/runtime limits.
- Test result for this packaging run: 45 passed, 3 skipped (optional MCP/MongoDB runtime checks unavailable/unconfigured in the sandbox).

## 0.1.5 — 2026-09-24

- Added a bounded deterministic filesystem inventory for source, tests, contracts, workflows, configuration, documentation and reports.
- Added stable per-path filesystem entries with SHA-256, size/mtime, declared-ID references, nearest Git root/HEAD, presence state and per-root tree fingerprints.
- Added incremental rescans: unchanged files are not rewritten; complete scans mark removed files without inventing semantic state.
- Hidden work directories `.github`, `.gitlab` and `.devcontainer` can be indexed while secret/key/cache/build locations remain excluded.
- Added `filesystem_scan` and `filesystem_references` MCP tools so many legacy contracts can share one deterministic repository inventory instead of triggering one repository audit per contract.
- Added `evidence_freshness`: only verifier/owner-attested PASS evidence with reproducible filesystem hash bindings can be classified as reusable; changed bindings become STALE.
- Explicitly kept AI/audit prose as non-reusable CLAIM material unless it already satisfies the normal MangoMe evidence/attestation rules.
- Proof freshness never upgrades a slice to VERIFIED or ACCEPTED and does not fabricate historical slices or cross-slice semantic equivalence.

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
