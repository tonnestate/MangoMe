---
name: mangome
description: Use MangoMe for durable multi-agent work, recovery, evidence, verification, explicit discovery/scan requests, and MangoMe maintenance. Apply when the user asks to use MangoMe/MCP, continue admitted work, inspect MangoMe state, discover filesystem candidates, or govern a productive effect. Observation-only requests stay observation-only; external delegation uses runtime-profile governance.
---

# MangoMe Agent Skill

MangoMe is the canonical operational-memory and verification substrate for durable multi-agent work. Workers and sessions are replaceable; admitted WorkIdentity, normative state, Evidence and assurance history are not.

## v0.3.12 semantic worker surface

Normal workers use exactly seven top-level MangoMe tools:

```text
mangome_status
mangome_observe
mangome_query
mangome_work
mangome_effect
mangome_verify
mangome_control
```

Select the semantic operation first; MangoMe routes deterministically to the existing precise capability internally. Do not search for or require low-level tool names on the normal worker surface. Advanced/internal operators may use `mangome.mcp_server` / `mangome-mcp-advanced` explicitly.

Every semantic response includes `disposition`, `recommended_next_action`, `allowed_next_actions`, `forbidden_next_actions`, and `reason_codes`. Follow that guidance instead of inferring hidden MangoMe state.

Structural Intelligence is derived observation only:

```text
MAP != TRUTH
MAP != EVIDENCE
MAP != ASSURANCE
MAP != AUTHORITY
MAP != NORMATIVE BASELINE
MAP != WORK IDENTITY
```

Use structural status/search/symbol/context/impact operations through `mangome_observe`. Structural failure is non-blocking cognition and returns `STRUCTURAL_CONTEXT_UNAVAILABLE` or an equivalent reason code. It must never authorize canonical mutation.

## Zero-touch user rule

Zero-touch applies to the user interface, not to governance. The user should describe the real goal; do not require MangoMe vocabulary such as Project, Family, WorkIdentity, Plan, Slice, Big Bang, restore, or reconciliation.

The default productive-work rule is:

```text
THINK FREELY
    ↓
RECONCILE BEFORE EFFECT
    ↓
GOVERNED PRODUCTIVE WORK
```

A worker may read, search, inspect, reason, classify, and form a tentative decomposition before MangoMe reconciliation. Those are worker judgments, not canonical truth. Before the first productive mutation, external side effect, canonical MangoMe mutation, normative change, or assurance claim, use `mangome_work(operation="RECONCILE_ASSIGNMENT", ...)` and the appropriate bound authority.

Do **not** perform a ritual restore merely because a chat/session started. Managed clients bind cheaply; recovery is lazy and explicit when needed.

## First route the request

Before calling MangoMe, classify the *operation type*, not the business domain.

### A. Direct observation / query

Use `mangome_status`, `mangome_observe`, or `mangome_query` for observation-only requests such as:

- health, readiness, version, database binding;
- status, show, list, resolve;
- structural status/search/symbol/context/impact inspection;
- recovery/context inspection;
- cognitive-hygiene/context compilation;
- read-only canonical graph/truth/work queries.

Observation-only requests are **not work assignments by themselves**. They MUST NOT automatically admit work, create WorkIdentity, run productive reconciliation, authorize delegation, or mutate canonical state.

For an explicit discovery/structural request, perform exactly the bounded requested observation and return the result. Do not first run IntakeGov, restore the workspace merely to inspect structure, or promote discovered candidates automatically.

A `STATE_NOT_FOUND` value is irrelevant to a pure observation request; observation does not require admitted WorkIdentity.

### B. Productive assignment

For work that may change code, files, databases, deployments, external systems, canonical MangoMe state, or assurance:

```text
understand local problem
→ tentative decomposition
→ mangome_work(RECONCILE_ASSIGNMENT)
→ bind current WorkIdentity / turn / baseline as required
→ persist durable intent before relevant external effects
→ productive effects
→ observe / reconcile external reality
→ progress + Evidence
→ DONE_CLAIMED
→ validation: VALIDATED / REWORK_REQUIRED / INCONCLUSIVE
→ independent verification
→ CLOSED only when required effects are reconciled and satisfied
→ optional owner acceptance
```

Reconciliation is read-only. It never turns the worker's tentative plan into canonical truth.

- `STATE_FOUND`: map the current request to existing WorkIdentity/baseline/unfinished state. It does not mean “continue automatically”.
- `STATE_PARTIAL`: bounded recovery/backfill only; fail closed on productive mutation until resolved.
- `STATE_NOT_FOUND`: genuine new work may use `mangome_work(operation="ENTER_WORK", ...)`; historical/resume work needs explicit import/backfill. Never create replacement state and call it restored.

### C. Dedicated recovery/status

Use `mangome_status(scope="RESTORE")`, `mangome_status(scope="RECOVERY")`, or the relevant `mangome_observe` operation when the user explicitly asks to recover/inspect persisted work state, when an unmanaged host lacks the managed path, or when reconciliation reports a recovery gap.

Recovery follows identity. Never recover current WorkIdentity from broad filesystem search, Git/worktree archaeology, old contract folders, cached summaries, or prior agent prose.

### D. MangoMe self-maintenance

When the current user explicitly asks to install, update, repair, hotfix, roll back, or reconfigure MangoMe itself, use the existing out-of-band control-plane maintenance semantics (`CPM/1`) through the semantic facade where available.

Self-maintenance does not self-admit. Do not create a WorkIdentity, Contract, Specification, Plan, Slice, or self-approval merely to repair the governance substrate. Scope effects to the explicitly requested MangoMe source/package/runtime/client/service surface.

Zero-touch deployment bootstrap is part of the explicit install/update/repair request and of normal managed-runtime readiness. A managed MangoMe runtime invokes this bootstrap automatically on first database access; the user or worker must not be required to run `mangome setup` as a prerequisite. The bootstrap may discover/adopt an existing MongoDB credential source without exposing secrets, preserve a verified existing deployment database identity (fresh installations default to `mangome`), and run idempotent `ensure_indexes()` for the indexes declared by the installed MangoMe release. It must never create a new database merely to normalize a historical name or silently move durable state between databases. This bounded bootstrap is installation plumbing under CPM/1; it does not require a WorkIdentity or self-approval.

This exception does **not** authorize MongoDB user/role creation or changes, registered schema migrations, canonical domain-document mutation, business-data repair, or database-identity changes. If any of those are required, stop with `DATABASE_CHANGE_REQUIRED`. If MongoDB is authentication-protected and no reusable authority can be adopted, stop with `BOOTSTRAP_AUTHORITY_REQUIRED`.

## Source precedence and memory

Current user intent defines the current turn. Canonical MangoMe state defines admitted identity, normative state, progress and assurance. Current direct runtime/workspace observation defines observed implementation facts.

Historical host memory is never current authority. Prior chats, old Claude/Codex memory files, cached summaries, eval/audit notes, and old install notes are candidate-only discovery hints. They may help locate something, but must be revalidated against current user intent, current MangoMe state, and direct runtime/workspace observation.

Never recover current WorkIdentity, database identity, installation version/path, or controller authority from historical host memory.

Database identity is deployment state, not agent discovery. Fresh managed installations default to `mangome`, but upgrades MUST preserve a proven existing MangoMe database identity even when it has a historical name such as `mangome_uai_eval`. Never rename, copy, migrate, or switch databases implicitly during install/update. A historical name is not evidence that the durable state is disposable; only an explicit verified database migration may change deployment identity.

## Structural Intelligence / SIM/1

Structural observation is lazy and bounded. Bootstrap/status must not trigger a full structural scan. Use it only when the current task benefits from repository structure.

Normal operations are available under `mangome_observe`:

```text
STRUCTURAL_STATUS
STRUCTURAL_SEARCH
SYMBOL_LOOKUP
SYMBOL_RELATIONS
STRUCTURAL_CONTEXT
IMPACT_FRONTIER
```

PCH may use structure for relevance/residency only. SRA may use structural impact as inspection candidates only. The ContextCompiler may include bounded structural context when space permits. None of these paths can expand mutation scope, create Evidence, establish assurance, or promote derived structure into truth.

## Discovery semantics

Discovery is candidate-only observation. A discovered file is not automatically a Contract, Specification, WorkIdentity, Evidence item, or verified fact.

Use the narrowest path the user requested. Physical repositories/contracts/evidence/artifacts can live in multiple typed locations; do not assume `/root`, one home directory, one repository root, or one provider.

For admitted work, broad discovery must not be used to reconstruct current state. Start from canonical MangoMe identity and inspect only the bounded unresolved physical delta.

## Runtime profile and delegation boundary

Runtime capability governance applies to **external dispatch/delegation** and genuinely capability-sensitive host actions. It is not a prerequisite for a worker's ordinary local reading, reasoning, discovery, or already-authorized execution path.

Use `mangome_control(operation="EXECUTION_ELIGIBILITY", ...)` only when an external orchestrator is about to dispatch a worker, or immediately before a host action whose required capability is explicitly governed.

`RUNTIME_PROFILE_REQUIRED` means the host/router has not published the current worker runtime needed for a dispatch decision. It does **not** mean the project, WorkIdentity, local discovery, or ordinary current-worker reasoning is invalid. Do not ask the worker to self-declare a profile and do not use privileged runtime publication as a workaround; that remains host/router authority.

For delegation:

```text
bounded task
→ required capabilities + cost ceiling
→ mangome_control(EXECUTION_ELIGIBILITY)
→ mangome_control(AUTHORIZE_DELEGATION)
→ external orchestrator dispatches only if authorized=true
→ mangome_control(COMPLETE_DELEGATION) / checkpoint
```

Worker identity, model identity, runtime mode, capability, cost class and authority are separate. Missing capability means checkpoint and hand off only the missing capability. Difficulty, urgency, or importance never grants premium escalation.

## Work identity, Plans and normative state

A prompt may admit durable WorkIdentity for genuine new work, but a prompt is not automatically a Contract or Specification.

Productive work must remain bound to the active Plan/WorkTurn/NormativeBaseline where the operation requires them. Baseline drift stops the old productive path rather than silently rewriting normative truth.

Recovered ACTIVE state, Plans or Slices are context only. They do not grant current-turn execution permission.

## Evidence and assurance

A worker completion statement is a claim:

```text
WORKER_COMPLETION != SLICE_COMPLETION
DONE_CLAIMED -> VALIDATED -> VERIFIED -> CLOSED -> optional ACCEPTED
```

Validation establishes whether the claimed implementation delta is complete; it is not independent verification. Required external effects use PER/1. Persist intent before dispatch, preserve `UNKNOWN` when the outcome cannot be established, and never blindly retry an unknown/partial/confirmed effect. A required effect blocks `CLOSED` until it is `RECONCILED` with `satisfied=true`.

Evidence is not automatically proof. Independent verification remains separate from worker execution; owner acceptance remains explicit. Do not self-verify or fabricate verifier/owner authority.

Preserve ambiguity as unresolved rather than inventing truth. Normative truth must not be rewritten merely to fit observed implementation.

## External runtime enforcement

MangoMe governs authority, identity, effects, evidence and assurance. Physical process restrictions belong outside the worker prompt and may be supplied by a host-side enforcement backend such as an OS sandbox. MangoMe must not treat the existence of such a backend as proof that the worker behaved correctly.

For external delegation, preserve the order:

```text
execution_eligibility
-> authorize_delegation
-> host applies external enforcement policy
-> worker executes
-> host records outcome / audit reference
-> MangoMe Evidence / AV/1 verifies what is material
```

The worker must never widen its own filesystem, network, command, credential or tool policy. Enforcement decisions and denials are observations from the host boundary, not canonical truth. Where useful, record backend/version/policy/audit references inside the existing `record_execution_receipt(..., metadata=...)` field; do not invent a second runtime state machine.

Recommended metadata keys are `enforcement_backend`, `enforcement_version`, `policy_ref`, `policy_digest`, `audit_ref`, and `enforcement_decision`. These are descriptive provenance only. A security scanner result remains WORKER_JUDGMENT or Evidence input according to the existing FJD/1 and AV/1 rules; it never self-promotes to verified truth.

## Bitemporal truth and cognitive hygiene

BTTM/1 separates when an assertion is valid in the represented world from when MangoMe knew it. Invalidation is non-destructive and can require revalidation.

PCH/1 temperature (`HOT/WARM/COLD`) is task-relative cognitive residency, not truth, assurance, or deletion. Truth maintenance decides what may be supported; Cognitive Hygiene decides what should be active; the ContextCompiler decides what can fit.

Under v0.3.12, structural relevance is a separate derived projection beside PCH/1; it may guide bounded inspection but does not silently rewrite canonical PCH temperature or residency. If structural context is unavailable or too large, continue with canonical/PCH context; do not block ordinary cognition solely because the map is unavailable.

## Scoped recursive audit

Use SRA/1 when an audit/review starts locally but material impact may extend outward. Expand the inspection frontier only on material impact, keep mutation authority bounded, persist findings/Evidence, and close only at a bounded fixpoint. Audit closure never means global correctness.

Structural impact candidates may help choose what to inspect next, but they never expand the audit mutation boundary.

## Operational language follows the user/session

Human-visible MangoMe narration must stay in the user's current working language unless the user explicitly changes it. Stable machine identifiers and reason codes remain language-neutral.

## Presentation rule

MangoMe orchestration is normally internal. Do not expose Slice IDs, Plan IDs, recovery cursors, WorkTurn IDs, or internal routing mechanics unless the user explicitly asks to inspect MangoMe itself. Report outcomes, evidence, blockers and decisions.

## Non-negotiable summary

1. Normal workers use seven semantic facade tools; v0.3.12 routes the full existing capability set behind them.
2. Observation-only requests stay observation-only.
3. Structural Map is derived observation, never truth/evidence/assurance/authority.
4. Bootstrap performs no full structural scan.
5. Structural failure degrades cognition gracefully and does not authorize mutation.
6. External runtime enforcement is host authority, not worker self-policy and not MangoMe truth.
7. Reuse the existing execution-receipt metadata for enforcement provenance; do not create a second runtime state machine.
8. THINK FREELY, RECONCILE BEFORE EFFECT for productive work.
9. `STATE_NOT_FOUND` never authorizes fake recovery.
10. Recovery follows canonical identity, not filesystem archaeology.
11. Historical host memory is candidate-only, never current authority.
12. MangoMe is infrastructure; do not modify it unless MangoMe itself is the explicit assignment target.
13. Runtime profiles govern dispatch/delegation, not ordinary local cognition or discovery.
14. Database identity is deployment state; preserve a proven existing binding across upgrades and never perform an implicit cross-database migration.
15. DONE is a claim; verification and acceptance remain separate.
