## 0.3.22 — 2026-10-05 — Zero-Touch Work Admission

- Distinguishes current-request identity from unrelated work already present in the same workspace.
- Adds exact normalized admission matching so workspace STATE_FOUND no longer forces a new request onto unrelated WorkIdentity.
- Normal seven-tool worker reconciliation auto-admits genuinely new current-user work instead of asking the user to create a MangoMe work entry.
- Supplies a stable non-privileged managed worker actor when ENTER_WORK is called without actor_id.
- Exposes in project overview that new work does not require a user-supplied work_ref or confirmation.
- Adds regression coverage for unrelated-work coexistence, automatic admission and managed actor fallback.

## 0.3.21 — 2026-10-04 — Agent-Proof Zero-Touch Runtime

- Reconciles stale managed MangoMe MCP generations on startup while preserving current/unknown processes.
- Adds runtime-generation visibility to HEALTH and repair/setup results.
- Allows safe in-process version rebound only when the managed source-root identity still matches.
- Honors explicit current-turn task opt-out so MangoMe cannot turn its own unavailability into failure of unrelated executable work.
- Aligns Skill, authority and zero-touch documentation with the v0.3.20+ ordinary WORKER execution path.

## 0.3.20 — 2026-10-03 — Correctness Recovery

- Makes Project/Family/Slice admission identity atomic with production/test-store uniqueness parity.
- Changes prompt hashes from durable WorkIdentity to normalized admission/dedup hints; continuation of an existing candidate requires explicit `work_ref`.
- Makes status/query projection side-effect-free and replaces recursive workspace discovery projection with bounded direct identity reads.
- Defines LOCAL_HOST honestly as `COOPERATIVE_HOST`; direct host/database writers are inside the trust boundary and v0.3.20 does not claim tamper-resistant verification.
- Removes the aggregate `MANGOME_RUNTIME_ROLE=FULL` privilege shortcut; privileged runtime roles are exact.
- Aligns stale trust/structural/release tests with the current runtime and adds adversarial concurrency/read-purity regressions.
- Adds a real MongoDB CI job for persistence and concurrent admission tests.

## 0.3.12 — 2026-09-29 — v0.3.11 Repair & External Enforcement Boundary

- Repairs the v0.3.11 semantic-facade regression while keeping exactly seven visible worker MCP tools. All 100 pre-existing advanced capabilities remain reachable through deterministic semantic routing.
- Restores admission/specification, identity/backfill, Plan lifecycle, contract-generation, truth, UAI/context, discovery/filesystem, FJD, runtime/model/economics, evidence/reproduction and maintenance operations that were accidentally unreachable from the normal worker surface.
- Hardens Structural Intelligence for the Python binding variants present in current `tree-sitter-language-pack` 1.x: prefer `get_parser(...)`, tolerate str/bytes parser input and `type`/`kind` node shapes, and fall back without blocking cognition.
- Corrects the PCH/SRA wording: structural projections are advisory data beside PCH/1 and SRA/1; they do not silently rewrite PCH temperature or the persisted SRA frontier.
- Keeps the managed normal CLI bound to `mangome.worker_mcp_server` while retaining explicit `mangome-advanced` / `mangome-mcp-advanced` escape hatches for internal and compatibility use.
- Formalizes the external enforcement boundary without adding a dependency: host-side sandboxes/policy engines run after `execution_eligibility` / `authorize_delegation`, and enforcement provenance can be attached to the existing `record_execution_receipt(..., metadata=...)` field.
- Defines external enforcement/scanner outcomes as observations, FJD/1 judgments or AV/1 evidence inputs according to existing semantics; they never self-promote to canonical truth or verification.
- Deliberately does **not** add HMAC, a cryptographic mutation journal, key lifecycle, `nono`, OpenShell, LlamaFirewall, Inspect AI or another runtime subsystem to MangoMe. Those remain external/evaluation concerns until isolated spikes justify tighter integration.
- Freezes managed-client surface selection: direct/programmatic setup defaults to the seven-tool worker endpoint, while the explicit advanced CLI can request the advanced endpoint without monkeypatching module globals.
- Adds a deterministic release smoke gate for package import, exact seven-tool worker discovery, advanced-capability routing completeness, and one in-process read-only MCP health call.
- Repairs managed MongoDB credential wiring: `MANGOME_MONGODB_URI_FILE` and non-secret trust-boundary posture are propagated into managed Claude/Codex MCP configuration, while `MANGOME_MONGODB_URI` is deliberately never persisted.
- Adds sanitized client-attestation diagnostics for missing credential-file binding, process-only URI usage, and unsafe URI secrets found in managed client configuration.
- Closes the CPM/1 installer deadlock: explicit MangoMe install/update/repair now permits the bounded zero-touch bootstrap (`credential adoption -> canonical database binding -> idempotent ensure_indexes`) without creating a WorkIdentity or self-approval.
- Keeps that exception fail-closed: MongoDB user/role changes, registered schema migrations, canonical domain-document mutation, business-data repair and explicit database-identity migration remain outside bootstrap authority.
- Completes zero-touch MongoDB adoption: runtime/setup recover an already-authorized credential from process environment, current/backup Claude/Codex MangoMe bindings, the managed credential file, or a still-live managed/legacy process **before** stale aliases are removed. A successful source is normalized into an owner-only managed credential file and verified against the effective deployment database; `mangome` is only the fresh-install default.
- Fails once and explicitly with `BOOTSTRAP_AUTHORITY_REQUIRED` when MongoDB authentication is enabled but no discovered credential can authorize the canonical database; setup no longer writes a knowingly broken managed binding and then leaves the agent to rediscover the deployment problem.
- Moves zero-touch adoption into the managed runtime itself: first canonical database access now invokes the bounded credential-adoption/bootstrap path automatically, so a successful installation no longer depends on the agent remembering to run `mangome setup` before using MCP.
- Caches bootstrap success/failure once per MCP process to prevent repeated credential scans and MongoDB timeout loops; HEALTH exposes the sanitized `database_bootstrap` state and stable blocker code.
- Recomputes trust-boundary posture after zero-touch adoption so one HEALTH response cannot report a recovered database alongside stale pre-adoption credential metadata.
- Hardens the seven-tool facade: an internal capability `TypeError` is no longer mislabeled as bad tool arguments, error-shaped responses are treated as blocked even when `ok=false` is omitted, and stable `OperabilityError.code` values such as `BOOTSTRAP_AUTHORITY_REQUIRED` survive facade routing.
- Aligns CPM/1 runtime guidance and `tools/repair_runtime_binding.py` with the bounded bootstrap exception; `ensure_indexes()` and preservation of a verified existing database binding are deployment plumbing, while users/roles, registered migrations, domain rewrites and explicit cross-database migration remain forbidden without separate authority.
- Prioritizes still-live legacy MangoMe MCP processes ahead of stale client backups during credential adoption, reducing the chance that startup burns several MongoDB timeouts before reaching the most likely recoverable authority.
- Preserves verified pre-existing database identity across upgrades instead of forcing the fresh-install `mangome` default; historical deployment names such as `mangome_uai_eval` may remain canonical when proven by the existing authorized binding.
- Persists the adopted non-secret database identity for subsequent restarts and makes managed setup/doctor emit the effective adopted database instead of reverting the client binding to the requested default.
- Refuses false legacy adoption: a differently named historical database must already contain known MangoMe collections before zero-touch may adopt it; bootstrap never creates an empty legacy-named database and then treats that as proof of history.
- Performs no implicit database copy, rename, or cross-database migration during installation/update.

## 0.3.11 — 2026-09-29 — Structural Intelligence / Semantic Worker Facade / Graceful Cognition

- Adds SIM/1 bounded Structural Intelligence with lazy indexing, symbol lookup/relations, structural search/context, impact-frontier projection and explicit derived-observation semantics.
- Reuses RepoMap design principles and Tree-sitter parsing without absorbing Aider as an application or making structural state canonical truth.
- Guarantees `BOOTSTRAP_PERFORMS_NO_FULL_STRUCTURAL_SCAN`; structural indexing occurs only on explicit structural operations or bounded context requests.
- Reduces the normal worker MCP surface to exactly seven semantic tools: `mangome_status`, `mangome_observe`, `mangome_query`, `mangome_work`, `mangome_effect`, `mangome_verify`, and `mangome_control`.
- Retains the existing precise v0.3.10c capability surface as the explicit advanced/internal endpoint `mangome-mcp-advanced` / `mangome.mcp_server`.
- Adds weak-agent guidance fields `disposition`, `recommended_next_action`, `allowed_next_actions`, `forbidden_next_actions`, and `reason_codes` to facade responses.
- Adds staged graceful degradation: optional structural failure is non-blocking; context-budget pressure can drop structural detail and fall back to minimal viable canonical context before reporting `CONTEXT_UNAVAILABLE`.
- Allows PCH to consume structural relevance only for residency/relevance and SRA to consume structural impact only as inspection candidates; neither path changes truth, assurance or mutation authority.
- Routes the normal CLI/MCP package entry points through the small worker facade while preserving explicit advanced compatibility entry points.
- Updates the canonical/package Agent Skill surfaces for the seven-tool semantic workflow and keeps both copies byte-identical.
- Adds v0.3.11 structural/worker-facade documentation and third-party acknowledgements for Aider design lineage, Tree-sitter and tree-sitter-language-pack.
- Does not add the planned cryptographic history chain, full bitemporal arbitration, or a new cross-agent protocol stack.

## 0.3.10 — 2026-09-28 — Persistent Effect Reconciliation & Slice Closure Semantics

- Separates worker completion from Slice completion: `DONE_CLAIMED -> VALIDATED -> VERIFIED -> CLOSED`; owner `ACCEPTED` remains distinct.
- Adds validation outcomes `VALIDATED`, `REWORK_REQUIRED`, and `INCONCLUSIVE`; only explicit `REWORK_REQUIRED` reopens a DONE-claimed Slice for execution.
- Adds dependency levels `VALIDATED` and `CLOSED` without replacing the existing execution/assurance state model.
- Adds PER/1 durable external-effect intent, dispatch, observation and reconciliation state bound to WorkIdentity, Slice and WorkTurn.
- Preserves `UNKNOWN` outcomes and rejects blind redispatch until external reality establishes known non-execution/failure.
- Allows `VERIFIED + OPEN` while required effects remain unresolved, followed by explicit `close_verified_slice` after reconciliation.
- Exposes open effect ids/counts in WorkView, recovery context and maintenance diagnostics.
- Formalizes the Agent-OS layer model while keeping deterministic enforcement separate from optional future layer-specific agents.
- Bumps the document schema to v6 with non-destructive compatibility defaults for historical Slice state.
- Hardens positive PER/1 reconciliation: `satisfied=true` requires a `CONFIRMED` observation, a VERIFY WorkTurn, and verifier authority.
- Uses deterministic effect identity and handles concurrent duplicate intent idempotently across storage backends.
- Fixes recovery projection so rework/pending-closure state is added to the active recovery methods rather than shadowed duplicate definitions.
- Preserves legacy non-WorkIdentity acceptance behavior; the new `CLOSED` prerequisite applies only to admitted v0.3 work.
- Adds a 5-minute demo, compatibility notes, a release checklist, and a v0.3.10 test report.

## 0.3.9 — 2026-09-28 — Observation Routing & Codex Integration Hardening

- Adds an explicit observation/query route to the Agent Skill. `health`, status/show/list/resolve, `discover PATH`, scan/inventory, scope listing, and read-only context inspection no longer automatically enter IntakeGov, assignment reconciliation, restore, WorkIdentity admission, or delegation gates.
- Makes explicit `bigbang_scan` a terminal, persistence-free candidate observation with bounded result payloads and Git inspection disabled by default. It no longer writes Artifact rows merely because a path was scanned.
- Adds server-side `reconcile_bigbang_scan` for explicitly requested advisory reconciliation so large candidate sets do not have to round-trip through model context. Direct `reconcile_bigbang` rejects oversized payloads with `CANDIDATE_PAYLOAD_TOO_LARGE`.
- Hardens Big-Bang scanning against symlinks, private agent/credential/cache/build trees, and whole-file memory loading; hashing is streamed, lexical extraction is bounded, excluded directories are pruned before descent, and traversal has explicit file/depth limits.
- Adds pure `filesystem_inventory` alongside the existing explicit persistent `filesystem_scan` maintenance path.
- Narrows runtime-profile governance to external delegation/dispatch and genuinely capability-sensitive host actions. `RUNTIME_PROFILE_REQUIRED` now reports `ordinary_local_work_blocked=false` and must not stop ordinary local reading, reasoning, discovery, or already-authorized execution.
- Moves managed Codex MCP registration, MangoMe Skill installation, and the small activation rule to user scope so availability no longer depends on Codex saved-project registration. The activation rule explicitly loads the installed `SKILL.md` before MangoMe work instead of relying only on heuristic Skill selection. Existing unrelated user configuration is preserved and stale MangoMe aliases are removed deterministically.
- Allows an explicit workspace argument to override a stale process-global read-only binding; canonical workspace rebinding remains deterministic and fails closed with `WORKSPACE_BINDING_AMBIGUOUS` when more than one candidate matches.
- Keeps canonical/package Skill copies byte-identical while treating repository-local `.github` / `.claude` mirrors as optional convenience surfaces.
- Removes the independent hard-coded MCP version literal in favor of package `__version__`.
- Updates release/test documentation and adds v0.3.9 regression coverage for the live failures above.

## 0.3.8 — 2026-09-28 — Codex Skill Discovery & Canonical Workspace Rebinding

- Installs the MangoMe Agent Skill user-scoped at `~/.codex/skills/mangome/SKILL.md` so Codex can discover it even when the current workspace is not present in the local saved-project catalog.
- Codex client attestation now fails explicitly with `SKILL_NOT_INSTALLED` / `SKILL_VERSION_MISMATCH` when the user-scoped Skill is absent or stale.
- Recovery no longer equates an exact workspace-path hash miss with missing canonical state. After an exact miss, MangoMe may rebind read-only to one unambiguous canonical workspace already present in the configured MongoDB.
- Canonical rebinding uses only persisted MangoMe `workspace:` scope identity; it never searches host memory, contracts, Git, or the filesystem and never creates replacement state.
- A broad cwd that covers multiple canonical workspaces returns `STATE_PARTIAL` with `WORKSPACE_BINDING_AMBIGUOUS` instead of guessing or reporting a false `STATE_NOT_FOUND`.
- Restore/reconciliation results now include sanitized `database_binding` and `workspace_resolution` diagnostics so database-vs-workspace failures are distinguishable in one call.

## 0.3.7 — 2026-09-27 — Deterministic Runtime Database Binding

- Treats database identity as deployment state, never agent-discovered state.
- Rejects the legacy `mangome_uai_eval` binding for ordinary managed work unless `MANGOME_ALLOW_EVAL_DATABASE=1` is explicitly set.
- `health()` now exposes `process_ready`, `database_ready`, and a sanitized `database_binding` block so the effective DB is visible in one call.
- Managed Codex/Claude configuration pins the canonical database and short MongoDB connection timeouts.
- MongoDB server selection/connect/socket timeouts are bounded to prevent multi-minute startup stalls.
- Re-running managed setup/doctor removes stale `mangome_eval` client entries and rebinds to the current `mangome` server.

## 0.3.6 — 2026-09-27 — Bitemporal Truth Maintenance & MongoDB Trust Boundary

- Added `BTTM/1` canonical truth assertions with separate valid-time and known-time intervals.
- Added Evidence/support/assumption/dependency/contradiction grounding and deterministic supportability states.
- Added non-destructive invalidation with recursive `REVALIDATION_REQUIRED` propagation and immutable truth events.
- Integrated current BTTM assertions into PCH/1 and ContextCompiler without conflating truth with cognitive temperature.
- Added `record_truth_assertion`, `truth_at`, `truth_assertion_status`, `invalidate_truth_assertion`, and `bitemporal_truth_status` MCP surfaces.
- Added `MTB/1` strict MongoDB trust-boundary mode: protected credential-file loading, expected service-uid enforcement, remote-endpoint fail-closed default, sanitized health posture, and optional rejection of dangerous built-in MongoDB roles.
- Added `trust_boundary_status` and production deployment guidance.
- No destructive migration of existing canonical collections is required; v0.3.6 adds new truth collections and indexes.

# Changelog

## 0.3.5 — 2026-09-27 — Out-of-Band Control-Plane Self-Maintenance

- Added `CPM/1`: explicit operator requests to install/update/repair/hotfix/rollback/reconfigure MangoMe itself are classified as out-of-band control-plane maintenance rather than ordinary project work.
- `reconcile_assignment` now short-circuits canonical restore/admission for explicit MangoMe self-maintenance and returns a read-only maintenance disposition. It does not require `enter_work`, WorkIdentity, Contracts, Plans, Slices, or a MangoMe-persisted self-approval.
- `CPM/1` is tightly scoped to MangoMe source checkout, package/venv, MCP launcher/runtime configuration, and MangoMe service/autostart surfaces. It does not authorize unrelated application mutations.
- Database/schema mutation is never granted by `CPM/1`. If the target update requires a database/schema migration without separate explicit operator authorization, the worker must stop with `DATABASE_CHANGE_REQUIRED`.
- Promoted source-precedence hygiene into always-on managed-client instructions: old Claude/Codex memory, prior chats, cached summaries, and historical audit/eval artifacts are candidate-only hints, never current installation/workspace/controller authority.
- Clarified intent discipline: status remarks, acknowledgements, and observations are not automatically new assignments.


## 0.3.4 — 2026-09-27 — Non-Blocking Bootstrap / Lazy Discovery Hotfix

- Separates **workspace binding** from filesystem/Big-Bang discovery. A managed MCP process now creates only a volatile read-only workspace binding at startup; it does not inventory files, scan repositories, or run onboarding discovery.
- `session_restore`, `session_bootstrap`, and `reconcile_assignment` no longer fall back to `refresh_workspace_attachment()` when no attachment exists. They use the read-only binding fast path and consult canonical MangoMe state directly.
- Automatic startup no longer performs canonical recovery eagerly. Canonical restore is lazy and occurs only when reconciliation/recovery or an effect gate needs it.
- Explicit `workspace_status(..., refresh=True)` remains the opt-in path for full attachment/discovery refresh.
- `session_bootstrap` now returns timing/mode diagnostics and guarantees that the bootstrap path itself performs no filesystem inventory, Big-Bang discovery, or repository archaeology.
- Preserves the v0.3.3 effect-boundary rule: cognition may continue while MangoMe is unresolved; productive effects remain fail-closed until canonical reconciliation succeeds.

## 0.3.3 — 2026-09-27 — Zero-Touch Assignment Reconciliation / Effect Boundary

- Replaced the worker-facing restore-first ritual with **THINK FREELY, RECONCILE BEFORE EFFECT**.
- Added read-only MCP `reconcile_assignment` (`RAE/1`) as the default bridge from tentative worker understanding to governed MangoMe work.
- Managed clients now satisfy the read-only restore snapshot lazily/automatically when MangoMe initializes; productive gates no longer require a manual `session_restore` call solely because a session started.
- Updated the Agent Skill with a prominent default agent loop and open-ended-assignment behavior for requests such as “understand the system and proceed”.
- Preserved recovery semantics: `STATE_NOT_FOUND` is never synthesized into recovered state; `STATE_PARTIAL` remains bounded recovery/backfill only.
- Preserved authority semantics: tentative decomposition is worker judgment and never becomes canonical Plan/Spec/Contract truth without the normal admission/binding path.
- Added `docs/assignment-reconciliation.md` and aligned zero-touch/runtime instructions with the effect-boundary model.
- Added **FJD/1 Fast Judgment Decisions** as a MangoMe-native, provider-neutral typed-signal layer: strict `BOOL`, `SCORE`, and `CHOICE` values with explicit confidence and deterministic `USE_SIGNAL` / `REVIEW` / `ESCALATE` gating.
- FJD/1 performs no model inference and adds no Laya runtime dependency or vendored Laya code. It deliberately reuses only the general typed-decision/confidence/fallback pattern.
- Persisted fast judgments are `PROGRESSIVE` `WORKER_JUDGMENT` bound to an existing WorkIdentity; they can guide classification, triage, routing, activation or prioritization but never create canonical truth, Evidence, assurance, verification, acceptance or mutation authority.
- Added MCP tools `assess_fast_judgment`, `record_fast_judgment`, and `fast_judgment_status` plus `docs/fast-judgment.md`.

## 0.3.2 — 2026-09-27 — Scoped Recursive Audit / Impact Closure

- Adds **SRA/1 Scoped Recursive Audit** for bounded system understanding: `initial scope → inspect → finding/evidence → affected frontier → bounded expansion → fixpoint`.
- Persists `audit_runs` and `audit_findings` without creating a second truth or assurance system. Audit findings remain scoped observations; audit closure never implies `VERIFIED` underlying work or global system correctness.
- Separates four boundaries explicitly: knowledge, inspection, mutation, and assurance. Inspection may expand; mutation authority is frozen at audit start and never expands recursively.
- Adds `READ_ONLY` and `REPAIR_WITHIN_SCOPE`. The repair mode is only an audit boundary and never bypasses the normal MangoMe Plan/WorkTurn or host/runtime permissions.
- Adds impact classes `NONE`, `LOCAL`, `EXPAND`, and `OUTSIDE_SCOPE`. Only `EXPAND` follows confirmed graph/structural relations; outside-scope effects are preserved as boundary findings instead of being silently absorbed.
- Adds deterministic `FIXPOINT_REACHED` and `BOUNDED_FIXPOINT` closure semantics. Depth/object limits produce an explicit bounded result rather than a false complete-audit claim.
- Adds MCP surfaces `start_scoped_audit`, `audit_context`, `audit_status`, `audit_mutation_allowed`, `record_audit_finding`, and `close_scoped_audit`.
- Integrates the active audit frontier with PCH/1 as additional cognitive roots where the objects are present in the MangoMe graph. Audit priority remains activation only, never truth or assurance.
- Extends PCH/1 bounded graph navigation to first-class Artifacts already bound to the Family context; no host-wide artifact scan is introduced.
- Adds MongoDB indexes and regression coverage for recursive expansion, immutable mutation scope, depth-bounded closure, outside-scope reporting, and read-only enforcement.

## 0.3.1 — 2026-09-27 — Persistent Cognitive Hygiene / Thermal Working Set

- Adds deterministic **PCH/1 Persistent Cognitive Hygiene** over the existing canonical MangoMe graph; no second truth store, memory database, or graph engine is introduced.
- Adds `CognitiveHygieneService` with task-relative continuous temperature `T(x|q,t) ∈ [0,1]` and inspectable `HOT`, `WARM`, `COLD` bands.
- Treats `HOT/WARM/COLD` as disposable activation/residency, never as truth, assurance, or persistence. `COLD` means non-resident, not deleted.
- Uses canonical roots, graph reachability, task relevance, operational authority, freshness, epistemic support, conflict attention, supersession and representation cost to derive a bounded active working set.
- Pins current canonical execution roots so active-budget pressure cannot evict the Family, current Spec/Slice/Plan dependencies, or effective Contract truth required for execution.
- Adds GC-inspired generation labels (`HOT=0`, `WARM=1`, `COLD=2`) without destructive collection; historical state remains recoverable in MongoDB.
- Allows explicitly targeted historical/superseded state to reheat for inspection or revalidation without restoring its normative authority.
- Integrates PCH/1 **before** the existing `ContextCompiler`: `History → Hygiene Active Set → ContextCompiler → Worker/UAI`.
- Adds MCP `cognitive_hygiene` for a full thermal map and working-set diagnostics.
- Extends UAI/1 semantic projection with compact hygiene semantics and the invariants `TEMPERATURE!=TRUTH` and `COLD!=DELETED`.
- Adds regression coverage for non-destructive supersession, targeted reheating, pinned-root budget protection, compiler filtering, and UAI round-trip hygiene semantics.

## 0.3.0 — 2026-09-27 — Durable WorkIdentity / Progressive Persistence

- Promotes **WorkIdentity** to the durable authority anchor above replaceable Playbooks and evolving Specifications.
- Adds explicit persistence levels: `VOLATILE`, `PROGRESSIVE`, and `CANONICAL`.
- Changes `enter_work`: the user request may admit durable WorkIdentity, but it no longer becomes a Specification automatically.
- Adds immutable `NormativeBaseline` snapshots and binds new productive Plans to `work_id + turn_id + normative_baseline_id`.
- Stops stale execution with `BASELINE_DRIFT` when effective normative truth changes after a Plan was created.
- Adds controller-minted WorkTurn authority at the managed MCP boundary so workers cannot treat recovered state, a Playbook, filesystem state, or their own prose as current execution authorization.
- Adds a non-normative Playbook registry/selection path; Playbooks may guide procedure but never affect effective truth.
- Adds `PROGRESSIVE` work checkpoints that can only reference an already canonical WorkIdentity; checkpoints/discovery cannot invent or promote identity.
- Adds append-only Work-bound assurance events so `DONE_CLAIMED`, `VERIFIED`, and `ACCEPTED` history survives Spec and Playbook changes and remains baseline-attributed.
- Extends ContextCompiler and UAI projection with explicit canonical/progressive/volatile boundaries; context reduction discards volatile/progressive detail before canonical identity/assurance.
- Adds materialized WorkView read paths and avoids recompute-and-write on the v0.3 `status()` hot path when a current projection exists.
- Closes the v0.2.2 contract-generation error-class mismatch: forged actor/turn promotion now fails as `ContractGenerationConflict`, matching the intended grant invariant.
- Advances schema to v5 and adds MongoDB indexes for WorkIdentity, WorkTurn, NormativeBaseline, checkpoints, Playbooks, assurance events, and WorkView.
- Restores required GitHub/Claude Skill mirrors and CI release surfaces in the generated v0.3 tree.
- External review feedback from **Grok** was considered selectively, especially around deterministic effective truth, evidence/assurance separation, and materialized read paths. Ideas were adopted only where they matched observed code and MangoMe invariants; no Grok code was incorporated.

## 0.2.2 — 2026-09-26 — Execution Integrity Hardening

- Separates current user intent from recovered ACTIVE work; restore never implies continue/execute.
- Adds Contract turn binding and immutable Contract generations with single-writer MODIFY grants.
- Reuses existing Slices and materializes only the minimum internal Slice when admitted work has none.
- Requires real observational Evidence before audit/review work can claim completion.
- Adds hard ContextCompiler byte budgets, future-schema fail-closed behavior, expected-database binding, and repository root-shadow regression checks.
- Keeps `DONE_CLAIMED != VERIFIED != ACCEPTED` and preserves independent AV/1 verification.

## 0.1.9rc4 — 2026-09-26 — Portable Discovery, Native Session Restore & Tiered Fan-Out

- Adds provider-neutral `session_restore` plus `session_bootstrap` as a host-start alias. Restore is read-only with respect to Project/Family/Specification/Plan/Slice identity and returns exactly `STATE_FOUND`, `STATE_PARTIAL`, or `STATE_NOT_FOUND`.
- Makes missing recovery state explicit: `STATE_NOT_FOUND` never creates replacement Project/Family/Specification state and never masquerades as recovery. Genuine new work uses explicit `enter_work`; historical migration/backfill remains a separate explicit onboarding operation.
- Makes partial recovery fail closed: known state is preserved and missing recovery bindings are reported; productive mutation remains disabled until explicit backfill resolves the gap.
- Adds MCP-side restore gating for canonical mutation paths so lower-level state creation cannot proceed before session restore. `enter_work` remains an explicit NEW-WORK admission path, not a recovery substitute.
- Separates unfinished intent from execution permission: ACTIVE Project/Family/goal state does not authorize work when `next_executable_items` is empty; BLOCKED work cannot be bypassed by inventing a replacement Slice/Family.
- Preserves `DONE_CLAIMED != VERIFIED`: recovery exposes pending verification/acceptance as assurance work instead of treating worker completion claims as finished truth.
- Replaces the rc3 one-high-cost-per-family heuristic with tiered delegation budgets. Fan-out width, model tier, capability, cost and authority are independent; broad CHEAP/STANDARD parallelism is allowed while EXPENSIVE/PREMIUM escalation requires explicit authorization or an Owner-approved budget plus a concrete escalation reason.
- Adds portable typed discovery scopes and a physical-location registry for scattered repositories, worktrees, contract sources, evidence sources and artifact roots without hard-coding `/root`, one user, one OS, one provider, or one repository layout.
- Keeps repository/filesystem/DMS bodies in their source systems. MangoMe stores bounded metadata, hashes, references, relations and explicitly admitted domain state; generic changelog/context files are not copied into MongoDB merely because they are discovered.
- Treats agent-private context (for example `.claude`/`.codex` memory/config areas) as non-authoritative and excluded from project truth.
- Makes the infrastructure boundary explicit: agents may use MangoMe but may not modify MangoMe source/tests/configuration unless the assignment itself explicitly targets MangoMe; hard filesystem enforcement remains a host responsibility.
- Minimizes recovery context loading: optional host skills, memories and broad guidance packs are not part of restore unless the bounded delta requires them.
- Generalizes the product positioning: software engineering is the primary reference workload, not MangoMe's domain boundary. MangoMe is a persistent truth/work-state/evidence layer for durable multi-agent work.
- Adds regression coverage for portable multi-root discovery, scattered-repository identity, agent-private context exclusion, missing/partial/found restore states, DONE-claim assurance recovery, BLOCKED-work execution denial, and MCP restore gating.

## 0.1.9rc3 — 2026-09-25 — Authoritative Recovery & Delegation Governance

- Adds **Operational Language Inheritance** after a live recovery session emitted Japanese control-plane narration inside a German workflow: human-visible MangoMe/coordinator narration must inherit the current user/session language; persona/memory/runtime defaults may not silently switch it.
- Records the measured delegation incident precisely: five high-cost agents were dispatched during one recovery session (four completed, one safely stopped/checkpointed), while MangoMe itself had no provider/model dispatch entrypoint. rc3 therefore exposes deterministic dispatch authorization without falsely claiming end-to-end enforcement.
- Generalizes that live finding across parent-agent families: MangoMe task importance, difficulty, urgency, self-repair, or a capability gap never imply permission to spawn a stronger/high-cost subagent. `EXPENSIVE`/`PREMIUM` delegation is Owner-gated per exact bounded `family + worker + task_key`; one approval cannot authorize a sequence of premium tasks.
- Closes the observed Luna recovery failure in which a parent agent ignored MangoMe state and reconstructed its own project view through broad `rg`/`sed`, filesystem, Git/worktree, contract and evidence-path archaeology.
- Adds the hard invariant **Recovery follows identity. Discovery must never create or reconstruct admitted identity/state.**
- Adds deterministic `recovery_context` derived from canonical Project/Family/Specification/Plan/Slice/Artifact/Evidence state so resumed/coordinator agents have a bounded recovery entry point.
- Marks admitted work explicitly in `workspace_status` and disables discovery as a state-reconstruction path once canonical workspace work exists.
- Makes MCP `bigbang_scan`, broad `filesystem_scan` and overlapping Big-Bang reconciliation fail closed for admitted work; `filesystem_references` becomes targeted validation for identities MangoMe already knows.
- Strengthens the always-on Claude/Codex managed instruction and all four Skill surfaces so session death never authorizes path-derived state reconstruction.
- Adds `docs/authoritative-recovery.md` and regression coverage for canonical recovery state and managed recovery instructions.
- Clarifies that UAI/1 semantic hashes cover the compiled semantic projection, not the entire filesystem; unrelated filesystem changes do not automatically invalidate a worker result.
- Documents the trust-boundary deployment rule more explicitly: high-assurance workers must not possess direct MongoDB credentials; datastore access belongs to the MangoMe service boundary.
- Restores required dotfile release surfaces in the rc3 upload delta because public `main` still lacked `.github/workflows/ci.yml`, `.github/skills/...`, `.claude/skills/...` and `.gitignore` after the rc2 browser upload.
- Does **not** replace MongoDB, introduce global repository locks, add new assurance states, or weaken agent reasoning freedom.

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
