---
name: mangome
description: Use MangoMe for durable multi-agent work, recovery, evidence, verification, explicit discovery/scan requests, and MangoMe maintenance. Apply when the user asks to use MangoMe/MCP, continue admitted work, inspect MangoMe state, discover filesystem candidates, or govern a productive effect. Observation-only requests stay observation-only; external delegation uses runtime-profile governance.
---

# MangoMe Agent Skill

MangoMe is the canonical operational-memory and verification substrate for durable multi-agent work. Workers and sessions are replaceable; admitted WorkIdentity, normative state, Evidence and assurance history are not.

## v0.3.11 semantic worker surface

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

Database/schema mutation is not implied. If the requested maintenance actually requires canonical database/schema mutation without separate authorization, stop with `DATABASE_CHANGE_REQUIRED`.

## Source precedence and memory

Current user intent defines the current turn. Canonical MangoMe state defines admitted identity, normative state, progress and assurance. Current direct runtime/workspace observation defines observed implementation facts.

Historical host memory is never current authority. Prior chats, old Claude/Codex memory files, cached summaries, eval/audit notes, and old install notes are candidate-only discovery hints. They may help locate something, but must be revalidated against current user intent, current MangoMe state, and direct runtime/workspace observation.

Never recover current WorkIdentity, database identity, installation version/path, or controller authority from historical host memory.

Database identity is deployment state, not agent discovery. For ordinary managed local operation the canonical database is `mangome`; `mangome_uai_eval` is eval-only and requires explicit opt-in. Do not search alternate databases because the expected state is missing.

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

## Bitemporal truth and cognitive hygiene

BTTM/1 separates when an assertion is valid in the represented world from when MangoMe knew it. Invalidation is non-destructive and can require revalidation.

PCH/1 temperature (`HOT/WARM/COLD`) is task-relative cognitive residency, not truth, assurance, or deletion. Truth maintenance decides what may be supported; Cognitive Hygiene decides what should be active; the ContextCompiler decides what can fit.

Under v0.3.11, structural relevance may influence cognitive residency only as derived observation. If structural context is unavailable or too large, continue with canonical/PCH context; do not block ordinary cognition solely because the map is unavailable.

## Scoped recursive audit

Use SRA/1 when an audit/review starts locally but material impact may extend outward. Expand the inspection frontier only on material impact, keep mutation authority bounded, persist findings/Evidence, and close only at a bounded fixpoint. Audit closure never means global correctness.

Structural impact candidates may help choose what to inspect next, but they never expand the audit mutation boundary.

## Operational language follows the user/session

Human-visible MangoMe narration must stay in the user's current working language unless the user explicitly changes it. Stable machine identifiers and reason codes remain language-neutral.

## Presentation rule

MangoMe orchestration is normally internal. Do not expose Slice IDs, Plan IDs, recovery cursors, WorkTurn IDs, or internal routing mechanics unless the user explicitly asks to inspect MangoMe itself. Report outcomes, evidence, blockers and decisions.

## Non-negotiable summary

1. Normal workers use the seven semantic facade tools; low-level capabilities are advanced/internal.
2. Observation-only requests stay observation-only.
3. Structural Map is derived observation, never truth/evidence/assurance/authority.
4. Bootstrap performs no full structural scan.
5. Structural failure degrades cognition gracefully and does not authorize mutation.
6. THINK FREELY, RECONCILE BEFORE EFFECT for productive work.
7. `STATE_NOT_FOUND` never authorizes fake recovery.
8. Recovery follows canonical identity, not filesystem archaeology.
9. Historical host memory is candidate-only, never current authority.
10. MangoMe is infrastructure; do not modify it unless MangoMe itself is the explicit assignment target.
11. Runtime profiles govern dispatch/delegation, not ordinary local cognition or discovery.
12. Database identity is deployment state; do not hunt for alternate databases.
13. DONE is a claim; verification and acceptance remain separate.
