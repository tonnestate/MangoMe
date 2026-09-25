# Changelog

## 0.1.9rc2 — 2026-09-25 — Reconciliation Reasoning / Skill Surface Repair

- Makes MangoMe's reconciliation reasoning doctrine explicit: **Externalize state. Localize uncertainty. Preserve agency. Verify independently.**
- Adds the worker rule **Do not constrain reasoning. Constrain truth mutation.** and formalizes `J = f(N_scope, O_scope, X)` over normative truth, observed truth and agent-selected expansion context.
- Treats `ABSENT` as a valid observed state and instructs workers not to spend model context rediscovering requirements, artifact existence, revisions, Evidence or assurance facts MangoMe already records authoritatively.
- Keeps scope as a bounded starting projection rather than a hard cognitive boundary; workers may expand context on demand to avoid context starvation.
- Preserves worker agency for inspection, implementation, refactoring, testing, criticism and improvement proposals while keeping normative truth mutation and final verification on existing governed paths.
- Adds `docs/reconciliation-reasoning.md` with the design rationale and measurable evaluation hypothesis; no token-saving claim is promoted to an empirical result.
- Repairs the repository Skill surface by adding the native Claude Code mirror at `.claude/skills/mangome/SKILL.md`.
- Defines four byte-identical Skill surfaces: canonical repository Skill, packaged Skill, GitHub mirror and Claude Code mirror. `make check` and CI now reject drift across all four.
- Adds regression coverage so the normal pytest suite also fails when any required Agent Skill surface is missing or diverges.
- Updates README, release metadata, upload notes and test report to match the actual published surface.
- Does **not** add a second truth store, new graph engine, new assurance states, or stronger action guardrails.

## 0.1.9rc1 — 2026-09-25 — Release Candidate

- Promotes the evaluation-driven v0.1.8.1 repair line into the first v0.1.9 release candidate without weakening MangoMe's canonical truth model.
- Restores the repository surface that must exist in the published tree: `.github/workflows/ci.yml`, `.github/skills/mangome/SKILL.md`, and `.gitignore`.
- Adds GitHub Actions coverage across Python 3.10, 3.11, and 3.12 with a MongoDB 7 service so the canonical MongoDB backend is exercised instead of being silently skipped.
- CI now fails if the dedicated MongoDB integration tests are skipped while the MongoDB service is available, and performs a real Mongo-backed health/readiness check.
- Preserves the byte-identical Agent Skill mirror check and the existing deterministic test, compile, MCP-surface, and UAI round-trip checks.
- Removes the obsolete `PATCH_MANIFEST.md` repository artifact from the release surface.
- Keeps `CODE_OF_CONDUCT.md`, `SECURITY.md`, and the v0.1.8.1 integrity/zero-touch repairs as part of the release candidate baseline.
- Version-sensitive operability regressions now bind to the package `__version__` instead of hard-coding the previous patch version, so release-candidate version bumps do not create false readiness failures.
- No new assurance states or alternate truth store are introduced in this release candidate.

## 0.1.8.1 — 2026-09-25

- Repairs the concrete defects found by the first Claude Code / direct-harness evaluation instead of expanding MangoMe with another parallel architecture.
- Claude Code managed setup now defaults to private LOCAL scope; PROJECT `.mcp.json` scope remains an explicit opt-in because it can require manual Claude trust approval. Live attestation no longer treats a merely visible or pending server as connected.
- Preserves the active virtual-environment interpreter path instead of resolving its symlink to a base interpreter that may not contain MangoMe; restores declared Python 3.10 support with a conditional `tomli` dependency.
- Adds `enter_work`, the zero-touch ingress for ordinary new work. It creates only current client-relayed user-intent operational state in a task-specific Family under the workspace Project and then uses the normal Request → Spec → Plan → Slice lifecycle; Big-Bang/filesystem discovery remains candidate-only and is never promoted implicitly.
- Makes worker-facing planning recoverable: missing `declared_id` values receive deterministic `AUTO-*` identifiers, and expected MangoMe/input failures from `enter_work`, `begin_work`, planning, start/progress and DONE paths are returned as structured error data instead of opaque MCP failures.
- Adds explicit derived `truth_level` to deterministic status/context surfaces without adding a second assurance state machine. Discovery stays candidate-only; `DONE_CLAIMED` maps to `CLAIMED`, while `VERIFIED` and `ACCEPTED` remain distinct protected states.
- Closes H1 by forcing newly imported Slice assurance to `UNVERIFIED` while preserving the imported historical assurance claim separately.
- Closes H2 by rejecting verification of already `VERIFIED` or `ACCEPTED` Slices, preventing assurance downgrade and duplicate verification claims.
- Narrows H3 by persisting verifier identity and exact verification Evidence/AV/1 observation ids atomically with the Slice `VERIFIED` CAS write; maintenance diagnostics flag historical verified slices that lack this provenance.
- Closes H4 on supported UAI/1R decode/render surfaces by requiring the expected semantic context hash rather than accepting unbound stale result packets.
- Fixes first-attach reporting after runtime auto-attachment and MongoDB maintenance diagnostics with naive BSON datetimes.
- Documents the direct-database/worker-process isolation boundary: MangoMe cannot protect canonical state from an agent that already has direct MongoDB write/admin access.
- Adds `CODE_OF_CONDUCT.md` and links it from contribution guidance.
- Makes `make check` fail if the CI workflow, public Agent-Skill mirror, or `.gitignore` dotfiles are missing, preventing the earlier browser-upload omission from silently passing packaging checks.
- Schema version advances to 4 for imported-assurance and verification-provenance fields. Historical documents are upgraded non-destructively; MangoMe does not invent missing provenance.

## 0.1.8 — 2026-09-24

- Added zero-touch operability/bootstrap without changing MangoMe's canonical domain model or assurance states.
- Added `mangome setup` for managed local Claude Code/Codex integration and `mangome doctor --repair` / `mangome attest-client` for deterministic client-binding diagnostics and safe managed drift repair. MangoMe-named stale client entries are backed up and removed when the current workspace can be repaired unambiguously.
- Added runtime identity expectations (`MANGOME_EXPECTED_VERSION` and optional source-root binding) so a managed client can fail closed instead of silently launching the wrong MangoMe installation.
- Added automatic workspace attachment (`MANGOME_AUTO_ATTACH=1`): an unknown managed workspace receives one non-destructive Big-Bang discovery pass plus filesystem inventory; known workspaces refresh the inventory without requiring a user to request Big Bang manually.
- Added `workspace_status` to expose the automatic attachment state to workers while keeping discovery/canonicalization conservative.
- Updated the Agent Skill with standard frontmatter and a zero-touch rule: ordinary user intent is sufficient; users should not be asked to operate MangoMe vocabulary manually.
- Added Claude Code Skill/project integration support and packaged the canonical Skill with the Python distribution; the packaged copy is checked against the canonical Skill in CI/Makefile.
- Added short always-on client instructions: `.claude/rules/mangome.md` for Claude Code and a bounded managed block in Codex `AGENTS.md`, so ordinary user requests enter MangoMe without an explicit Skill/Big-Bang command while the full Skill remains contextual.
- Added `docs/zero-touch-operability.md` and updated README installation/operability guidance.
- Added deterministic regression coverage for first-attach discovery, repeated workspace refresh, Claude Code/Codex managed configuration, Skill installation, identity mismatch fail-closed behavior, and runtime auto-attachment.
- Deliberately did not add new assurance states, Assignment/nonce/signature infrastructure, or semantic auto-admission of discovery candidates.

## 0.1.7.1 — 2026-09-24

- Reserved `Evidence.payload.verification_observation` for `submit_verification_observation`; generic Evidence submission can no longer manufacture AV/1-shaped verifier provenance.
- Added dedicated-path provenance marking and require `VERIFIER_ATTESTED` trust for AV/1 independent observations. Legacy/direct AV/1-shaped records without dedicated-path provenance remain readable but cannot satisfy final verification.
- Added final-time live RB/1 freshness validation for AV/1 PASS Evidence immediately before the revision-CAS `VERIFIED` write. Stale, unknown, unbound, or inadmissible declared reproduction context blocks the transition.
- Kept the boundary explicit: this narrows the practical TOCTOU window but does not claim an atomic transaction across arbitrary external filesystems and MongoDB.
- Restored `.github/workflows/ci.yml`, `.github/skills/mangome/SKILL.md`, and `.gitignore` to the upload delta; the Skill mirror is byte-identical to the canonical Skill.
- Added regression coverage for generic AV/1 payload spoofing, legacy-shaped payload + later verifier attestation, stale RB/1 between observation and commit, and the matching positive replay path.
- Deliberately did not add new assurance states, Assignment/nonce/signature entities, or a second fixture lifecycle. Those proposals belong to empirical evaluation before any domain-model expansion.
- Test result for this packaging run: 54 passed, 3 skipped (optional MCP/MongoDB runtime checks unavailable/unconfigured in the sandbox).

## 0.1.7 — 2026-09-24

- Added AV/1 adversarial completion verification without introducing a new Proof entity or parallel assurance state machine.
- Added `completion_review`, which deterministically exposes persisted completion claims, Plan scope/artifacts, Specification acceptance criteria/required Evidence, existing independent observations, and optional changed-path review signals.
- Added deterministic `SCOPE_DEVIATION` and `TEST_CHANGE_REVIEW_REQUIRED` signals; these are review prompts, not automatic fraud/correctness judgments.
- Added `submit_verification_observation`, a verifier-capability-backed path for independently observed `PASS`, `FAIL`, or `UNVERIFIABLE` Evidence. The last executor cannot submit its own independent observation.
- `UNVERIFIABLE` observations persist as `EvidenceVerdict.UNKNOWN`; they never become guessed PASS results.
- `REPLAY` observations require an intact RB/1 reproduction binding. MangoMe validates the binding but still does not execute the command itself.
- Hardened `verify_slice`: every PASS gate must contain at least one independent AV/1 observed PASS Evidence item; gateless verification requires one in the explicit proof set. Attesting worker-authored PASS Evidence alone is no longer sufficient for final verification.
- Existing already-VERIFIED historical Slices are not rewritten; the stronger rule applies to v0.1.7 verification calls.
- Added `THIRD_PARTY_NOTICES.md` and explicit credit to `Sahir619/fable-method` / `fable-judge` (MIT) for methodological influence. MangoMe reimplements the concepts in its own assurance model and does not bundle Fable source or fixtures.
- Added regression coverage for worker-evidence rejection at final verification, executor self-observation denial, deterministic scope/test-change review, and RB/1 requirements for replay observations.
- Hardened AV/1 recognition on the generic Evidence path so malformed/forged REPLAY-shaped payloads without valid RB/1 bindings cannot satisfy independent-observation enforcement.
- Preserved explicitly approved `WAIVE_GATE` as the owner-governed exception to a gate Evidence requirement.
- Test result for this packaging run: 51 passed, 3 skipped (optional MCP/MongoDB runtime checks unavailable/unconfigured in the sandbox).

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
