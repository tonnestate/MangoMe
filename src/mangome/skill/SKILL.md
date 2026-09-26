---
name: mangome
description: Use MangoMe automatically for durable multi-agent project work, including resuming existing work, reconciling normative and observed truth, planning mutations, evidence, verification, and handoff. Apply whenever work may change or continue a MangoMe-managed project; the user does not need to know MangoMe commands or vocabulary.
---

# MangoMe Agent Skill

MangoMe is the canonical operational-memory system for durable multi-agent projects: document store, work graph, state machine, evidence/provenance ledger and execution context source.

## Zero-touch user rule

Zero-touch applies to the **user interface**, not to MangoMe's governance. Never require the user to say “start Big Bang”, create a contract, create a slice, call `begin_work`, or otherwise operate MangoMe vocabulary manually. On every new or recovered session, call `session_restore` (or `session_bootstrap`) before project-changing work; use `workspace_status` as a status surface, not as a restore substitute. Unknown managed workspaces are attached/discovered automatically, but discovery remains `CANDIDATE_ONLY` and must never be mistaken for canonical project truth.

If restore returns `STATE_NOT_FOUND`, preserve that fact. Never create Project/Family/Specification state and call it recovered. Only genuinely new work may use `enter_work` with the user's actual request before productive mutation; historical/resume work requires explicit import/backfill distinct from restore. `enter_work` may create canonical operational state backed by the **user intent relayed by the client**; it does not promote discovered legacy contracts, reports, or audit prose. High-assurance hosts may bind that intake to a trusted user principal outside the worker process. For known admitted work, reuse the existing family/specification through `begin_work` or the lower-level lifecycle.

Do not treat a missing prior Big-Bang command as a user error. If the managed MangoMe tools are missing, stale, or report a deterministic binding/readiness problem, run `mangome doctor --repair` yourself when safe before asking the user to edit configuration. Ask the user only when intent is genuinely ambiguous or a protected authorization/acceptance decision is required. Verification and acceptance remain separate privileged transitions; a worker reaching `DONE_CLAIMED` is a valid durable state, not a reason to fabricate verifier authority.

## Non-negotiable rules

1. **Restore first.** On a new/recovered session, call `session_restore`/`session_bootstrap` before repository exploration, planning or execution. `STATE_NOT_FOUND` is not permission to synthesize recovery state.
2. **Categorize every assignment.** Call `intake_request`; reuse IntakeGov classification when available.
3. **Resolve before creating.** Search existing project/family/contract/slice identity before creating a new one.
4. **A prompt is not a contract.** Register only durable contract contributions.
5. **Spec before execution.** Ensure objective, deliverables, constraints, acceptance criteria and evidence expectations are explicit.
6. **Plan before mutate.** Submit a plan before productive work.
7. **Stay bound to the plan.** After `start_slice`, every progress mutation and `claim_done` must use the same active `plan_id`.
8. **Preserve existing slices.** Import/reuse existing phases/slices/workstreams instead of casually replanning them.
9. **Collision warnings never block.** Observe traffic, re-read overlapping artifacts where useful, and continue.
10. **Persist meaningful progress.** Do not rely on chat/session memory.
11. **DONE is a claim.** `DONE_CLAIMED` is not `VERIFIED` or `ACCEPTED`.
12. **Evidence is not automatically proof.** New evidence is `UNATTESTED`; verification-grade evidence must be attested by a trusted verifier/owner capability.
13. **PASS requires attested PASS evidence.** Claims or un-attested evidence cannot satisfy a gate.
14. **Final verification requires independent observation.** Worker-authored Evidence plus later attestation is not enough for `VERIFIED`; use AV/1 verifier observations.
15. **WAIVED requires owner approval.** Never waive a gate without an approved `WAIVE_GATE` decision.
16. **No self-verification.** The last executing actor may not verify its own DONE claim or submit its own independent AV/1 observation.
17. **ACCEPTED is explicit.** Authorized acceptance is separate from verification and requires approved `ACCEPT_SLICE` state.
18. **Close obsolete plans.** Stale plans create stale collision traffic.
19. **Do not invent missing truth.** Keep ambiguity `UNRESOLVED` / `SUGGESTED` until evidence or authorized confirmation exists.
20. **Reconcile; do not reconstruct.** Start from MangoMe's authoritative normative and observed state, then spend model reasoning on the unresolved delta. Expand context on demand when the bounded view is insufficient.
21. **Recovery follows identity.** For admitted work, NEVER reconstruct current state from filesystem paths, broad `rg`/`grep`, Git/worktree history, contract/evidence directories, filenames, or prior agent prose. Read MangoMe canonical state first.
22. **Discovery never creates admitted truth.** Big-Bang/filesystem discovery is onboarding/observation only. Once work is admitted, broad discovery MUST NOT be used as a recovery mechanism.
23. **Model identity is not execution capability.** Route from the worker's current runtime profile, not its model name or capabilities assumed earlier in the session.
24. **Capability downgrade means bounded handoff.** If the current runtime loses a required capability such as `DEPLOY`, checkpoint completed work and hand off only that missing capability. Never restart discovery or reimplement completed work.
25. **Fan-out freely; escalate deliberately.** Fan-out width, model tier, capability, cost and authority are independent. Failure, difficulty, urgency, importance, MangoMe self-repair, or a limited cheap worker never authorize stronger/more expensive models. High-cost delegation requires explicit Owner authorization bound to the exact bounded task; multiple separately authorized tasks may run in parallel subject to runtime concurrency limits.
26. **Delegation authorization is not dispatch.** MangoMe records eligibility/authorization/checkpoints; the actual external orchestrator MUST consume that decision at its real model-dispatch boundary. Do not claim routing enforcement when that integration is absent.
27. **Runtime facts come from the host/router.** Workers must not self-declare their own cost class, runtime mode, or capabilities. `publish_worker_runtime` is a privileged host/router surface.
28. **Operational language follows the user/session.** Human-visible coordinator, recovery and control-plane narration MUST remain in the current working language unless the user explicitly changes it. Persona, memory, model defaults, or imported Skill text MUST NOT silently switch the operational language. Stable machine fields, protocol identifiers and reason codes remain language-neutral.
29. **MangoMe is infrastructure.** Agents may use MangoMe but MUST NOT modify MangoMe source, tests, packaging or configuration unless the explicit assignment targets MangoMe itself. A project failure is never implicit permission to self-edit the governance substrate. Hard filesystem enforcement belongs at the host boundary.
30. **Unfinished intent is not execution permission.** ACTIVE Project/Family/goal state does not authorize productive work. Execute only canonical `next_executable_items`; BLOCKED work must not be bypassed by inventing a replacement Slice/Family.
31. **Use typed discovery scopes.** Physical repositories, worktrees, contract/evidence/artifact roots may be scattered across users, hosts and operating systems. Use persisted/configured typed locations; never assume `/root`, `$HOME`, one repository root or one provider layout.
32. **References, not file-body duplication.** Generic repository/filesystem/DMS files remain in their source systems. MangoMe stores bounded metadata, hashes, references, relations and explicitly admitted domain state; do not copy changelogs, context files or arbitrary documents into MongoDB merely because they were discovered.
33. **Do not load optional context gratuitously.** Use the smallest sufficient MangoMe projection first. Do not read unrelated optional host skills, memories, broad guidance packs or repository trees unless the bounded delta actually requires them. Host-mandated instructions remain authoritative.

## Start of work

Default decision path:

```text
session_restore / session_bootstrap
   ↓
STATE_FOUND?
   ├─ yes → use canonical next_executable_items / pending assurance delta
   ├─ partial → bounded validation/backfill only; no productive mutation
   └─ not found → preserve RESTORE_STATE_NOT_FOUND
                 ├─ genuinely NEW work → enter_work(...)
                 └─ historical/resume work → explicit import/backfill, not fake restore
```

`enter_work` is the zero-touch entry point for ordinary new work. It does not weaken governance and it does not admit discovery candidates. `begin_work` remains the convenience path for an already admitted family with an effective specification. Both paths must end with a persisted Plan before productive mutation.

Use lower-level `intake_request → submit_plan → start_slice` only when advanced control is needed. Plans should state expected scope/artifacts, acceptance expectations and an estimate when meaningful.

## Compact context / UAI/1

When the host supports UAI/1, prefer `compile_uai_context` for expensive workers that do not need the verbose execution-context shape. UAI/1 is a disposable representation of MangoMe truth, not a replacement for canonical documents.

Rules:

1. Bind worker output to the supplied `semantic_hash`.
2. Prefer structured `UAI/1R` actions over administrative prose when the worker can comply.
3. Use `decode_uai_result` before interpreting a result.
4. Use `render_uai_result` for deterministic English/German human output where useful.
5. Never apply decoded actions directly. Route progress, artifacts, evidence and DONE claims through the normal MangoMe tools and invariants.
6. A hash mismatch means stale/tampered context; do not silently accept it.
7. Token estimates from the compiler are heuristic only. Record provider-reported token counts in `ExecutionReceipt` for real routing/economic decisions.

## Reconciliation reasoning model

MangoMe externalizes project state so the worker can spend reasoning capacity on the unresolved delta instead of reconstructing facts the system already knows.

The operating principle is:

```text
Externalize state. Localize uncertainty. Preserve agency. Verify independently.
```

And the corresponding agent rule is:

```text
Do not constrain reasoning. Constrain truth mutation.
```

For a bounded assignment, distinguish three inputs and one judgment:

```text
N = normative truth
    What must be true?
    Effective contract/specification, acceptance criteria, constraints, policy and scope.

O = observed truth
    What is actually present or observed?
    Artifacts, paths, digests, revisions, runtime state, tests and evidence.

X = explored context
    Additional context the worker chooses to inspect when N and O are not sufficient.

J = f(N_scope, O_scope, X)
    The worker's non-deterministic judgment about the delta between N and O.
```

`O` is truth about observed state, **not** a declaration of correctness. A present artifact may still be wrong; an absent artifact is also a valid observed state. Do not spend tokens rediscovering whether an artifact, revision, gate, evidence item or accepted requirement exists when MangoMe already provides that fact authoritatively.

The worker's primary job is to reason over the delta. It may conclude that the implementation is compliant, missing, contradictory, insufficient, unverified or improvable. It may explore dependencies, neighboring requirements, related artifacts, implementation detail, tests or history when that is needed for responsible judgment.

Start with the smallest sufficient scope, but do not turn scope into a cognitive prison. Use `read_context`, `effective_family_view`, `graph`, artifact/evidence records and other deterministic MangoMe projections to expand context on demand. Prefer targeted expansion over loading broad project history. The objective is to avoid both context dilution and context starvation.

The worker remains free to act within the admitted plan and scope: inspect, implement, refactor, test, criticize, propose alternatives and identify improvements. MangoMe must not make the reasoning process deterministic merely to make it controllable.

What the worker may not do is silently mutate truth:

- Do not reinterpret a requirement as changed merely because another solution appears better.
- Do not infer an observed artifact or state that MangoMe has not actually recorded or observed.
- Do not convert a worker claim into verification.
- Do not treat self-authored evidence as independent observation of the same completion claim.
- Do not rewrite effective normative truth through prose, memory or local interpretation.

If the worker believes the normative truth itself should change, persist that as a proposed/suggested contract contribution or amendment through the existing contract-evolution path. It remains non-effective until the authorized process promotes it into the effective specification.

This is a reconciliation model, not a rigid controller loop. The state presented to the worker is authoritative; the judgment over that state may be non-deterministic. Verification remains independently derived from evidence, policy, authority, freshness and revision state after the worker acts.

## Authoritative recovery — no path-derived reconstruction

For an already admitted workspace, recovery is a canonical-state operation, not a repository archaeology exercise.

Required order:

```text
workspace_status
    ↓
recovery_context / project_overview / status
    ↓
effective_family_view / read_context for the relevant family
    ↓
identify the unresolved delta and known artifact/evidence bindings
    ↓
only then inspect the bounded physical artifact(s) needed for that delta
```

Forbidden recovery pattern for admitted work:

```text
scan directories
→ grep contracts/reports
→ inspect worktrees/Git history
→ infer what probably happened
→ reconstruct a parallel project state
```

A filesystem path is an observation location, not work identity. Git history, worktree names, contract filenames, evidence folders and previous-agent summaries may corroborate or validate a MangoMe-bound delta, but they MUST NOT become the source from which current admitted state is rediscovered.

`ABSENT`, `MISSING`, `UNRESOLVED`, `DONE_CLAIMED / UNVERIFIED`, and similar MangoMe states are valid recovery inputs. Do not replace an explicit missing/unknown state with speculative path discovery.

When acting as a parent/coordinator for a recovery program, the parent remains orchestration-only: classify, delegate bounded tasks, consume concise summaries, persist progress/dependencies, and select the next delta. Broad repository exploration, evidence archaeology, test execution and implementation belong to bounded workers. A coordinator may make a narrowly targeted read when needed to resolve a handoff conflict, but it must not rebuild project state from paths.

The governing invariant is:

```text
Recovery follows identity. Discovery must never create or reconstruct admitted identity/state.
```

MangoMe's `bigbang_scan`, broad `filesystem_scan`, and Big-Bang reconciliation surfaces may be rejected for an admitted workspace. `filesystem_references` is only a targeted validation aid for an identity MangoMe already knows.

## Delegation, cost and runtime capability governance

Every MangoMe coordinator must treat model dispatch as a governed resource. Live tests showed both Claude- and Luna-family parents escalating MangoMe work to their strongest/high-cost subagents. The failure mode is not merely "too many agents"; it is a coordinator converting bounded work into an expensive model swarm without a persisted routing decision.

Keep these identities separate:

```text
Worker identity != model identity != runtime mode != capability != authority != cost class
```

A provider may leave the logical model name unchanged while moving the runtime into a restricted/reserve/degraded mode. Therefore eligibility is evaluated against the **current runtime profile**. Re-check before dispatch and again before a capability-sensitive action such as deployment.

Required path:

```text
classify bounded delta
    ↓
choose required capabilities + cost ceiling
    ↓
execution_eligibility
    ↓
authorize_delegation
    ↓
EXTERNAL ORCHESTRATOR enforces authorized=true at its real dispatch point
    ↓
worker executes bounded scope
    ↓
complete_delegation(task/artifact/status/missing_delta/next_dependency)
    ↓
recovery_context can recover orchestration state after coordinator/session death
```

Mechanical reconstruction/recovery SHOULD use `CHEAP` workers when they satisfy the required capabilities. More generally, `EXPENSIVE` and `PREMIUM` workers require explicit Owner approval for the exact `family + worker + task_key` delegation, and multiple separately Owner-authorized high-cost tasks may coexist; per-worker runtime concurrency limits still apply. Task difficulty, urgency, importance, or MangoMe self-repair never imply that approval. This avoids a coordinator silently producing a costly swarm.

If a worker is no longer eligible:

```text
CURRENT_RUNTIME_CAPABILITY_MISSING
    ↓
CHECKPOINT_AND_HANDOFF_MISSING_CAPABILITY_ONLY
```

Do **not** automatically select a substitute model. Do **not** reinterpret a missing `DEPLOY` capability as permission to launch a stronger model. Preserve the completed delta, Evidence and checkpoint, then route only the missing capability through the normal authorization path.

MangoMe does not contain the provider/model spawn implementation. `execution_eligibility` and `authorize_delegation` are a deterministic policy/coordination contract. Hard routing enforcement exists only when the external orchestrator checks that contract immediately before its actual dispatch call. If that hook is not integrated, report routing enforcement as **NOT ACTIVE** rather than claiming success.

`publish_worker_runtime` is reserved for the host/router capability. A worker must not be allowed to promote itself from a restricted runtime mode, add `DEPLOY`, lower its cost class, or disable owner gating by self-report.

## Operational language inheritance

MangoMe state is language-neutral, but human-visible control-plane narration is not allowed to drift arbitrarily. A worker/coordinator must inherit the current user/session working language for progress updates, recovery summaries, delegation summaries, and explanations.

Do not switch to another natural language because of a persona, remembered preference, provider/runtime default, prompt fragment, imported Skill, or model behavior. A language change is valid only when the user explicitly requests it or the bounded task itself requires output in that language.

Keep protocol tokens stable across languages:

```text
DONE_CLAIMED
VERIFIED
CURRENT_RUNTIME_CAPABILITY_MISSING
ADMITTED_WORK_DISCOVERY_FORBIDDEN
```

These are machine semantics. Translate the surrounding explanation, not the canonical identifier.

## Existing contract handoff

When given an existing contract and existing slices, use `import_contract_bundle` or equivalent explicit onboarding. Preserve supplied slice identity and state. Then create the current intake/spec/plan for the new execution session.

## During work

Use the same `plan_id` that started the slice:

```text
update_slice_progress(slice_id=..., actor_id=..., plan_id=...)
```

Register durable artifacts with `attach_artifact`. Use `link_entities` for explicit typed relations such as:

```text
ADDS_TO
AMENDS
EXTENDS
REPAIRS
RECOVERS
SUPERSEDES
CONFLICTS_WITH
VALIDATES
IMPLEMENTS
PART_OF
EXPOSED_BY
RELATES_TO
```

New work discovered during execution should become an additional slice or contract contribution without rewriting history.

## Completion

```text
claim_done(slice_id=..., actor_id=..., plan_id=...)
```

This produces a stable `DONE_CLAIMED / UNVERIFIED` state.

## Evidence and verification

New evidence is deliberately untrusted by default:

```text
submit_evidence(
  evidence_class=TEST_RESULT | RUNTIME_OBSERVATION | STATIC_ANALYSIS |
                 ARTIFACT_CHECK | HUMAN_ATTESTATION | EXTERNAL_REVIEW | ...
)
```

A trusted verifier or owner must attest verification-grade evidence through a runtime capability:

```text
attest_evidence
```

When Evidence should be reusable across time, prefer an RB/1 reproduction binding rather than prose. Run the check in the real execution environment first, then record its command/exit code and bind the relevant input hashes:

```text
build_reproduction_binding
→ submit_evidence(payload={"reproduction": ...})
→ attest_evidence
```

`build_reproduction_binding` never executes the command and never reads environment-variable values. It records names only and rejects sensitive-looking environment names. `evidence_freshness` may later classify the binding as `REUSABLE`, `STALE`, `UNKNOWN`, `UNBOUND` or `INADMISSIBLE`, but freshness never upgrades assurance and never proves cross-slice semantic coverage.

For substantive DONE verification, first build the deterministic review brief:

```text
completion_review(slice_id=..., changed_paths=[...])
```

Treat worker reports and worker-authored Evidence as claims to inspect. The verifier/host must rerun or otherwise observe each load-bearing check it relies on. Record the observation with the verifier capability:

```text
submit_verification_observation(
  observation_type=REPLAY | DIFF | SCOPE | SPEC_CHECK | RUNTIME | ARTIFACT | OTHER,
  status=PASS | FAIL | UNVERIFIABLE,
  ...
)
```

`UNVERIFIABLE` maps to `UNKNOWN`, never PASS. `REPLAY` requires an intact RB/1 reproduction binding. MangoMe records the observation but does not execute the command itself. Never place `verification_observation` inside generic `submit_evidence`; that namespace is reserved for the verifier-capability path. If AV/1 Evidence carries RB/1, final verification live-checks the binding again immediately before the assurance CAS write and blocks stale/unknown context.

A gate may then become PASS using Evidence that includes an independent AV/1 observed PASS:

```text
set_gate(status=PASS, evidence_ids=[...])
```

Final verification remains a separate transition:

```text
verify_slice
```

For v0.1.7, every PASS gate must contain at least one independent AV/1 observed PASS Evidence item. A gateless Slice requires one in the explicit proof set. Changed tests or scope deviations are review signals, not automatic findings of fraud.

Never place capability tokens in contracts, project state, evidence payloads, chat summaries or source files. Runtime/host injection is preferred.

## Owner approval

A worker may request but cannot grant approval:

```text
request_override(action_type=WAIVE_GATE | ACCEPT_SLICE, ...)
```

Owner approval/rejection requires the separate runtime approval capability. For local/self-hosted operation, a human can use the CLI so the token remains in the environment rather than the prompt:

```text
mangome approve <approval_id> --actor human-owner
mangome reject <approval_id> --actor human-owner
```

After an approved `ACCEPT_SLICE`, `accept_slice` derives the authoritative accepting actor from the approval record.

## Contract evolution

Contract contributions are append-only. Use typed relations rather than overwriting history. `effective_family_view` resolves confirmed supersession and surfaces conflicts/suggestions. It does not silently merge ambiguous prose; the current effective specification remains the operational requirements view.

## Project status

Use:

```text
status                # one family
project_overview      # all known families in a project
effective_family_view # contract evolution/current contribution set
graph                 # explicit typed relations
```

These are deterministic projections, not LLM summaries.

## Dependencies

Slices may depend on another slice at one of three levels:

```text
DONE_CLAIMED
VERIFIED
ACCEPTED
```

Do not treat an execution-level completion dependency as equivalent to an assurance-level dependency.

## Session/context loss

Do not reconstruct project truth from your own memory **or from path/repository archaeology**. Read MangoMe again. Use `recovery_context` first for admitted work, then `last_started_slice_id`, active slices, last DONE claim, last verified slice, active plan binding, gates, evidence and timestamps as the durable starting point.

A dead session does not authorize `rg /`, broad filesystem inventory, Git/worktree reconstruction, contract-directory mining or evidence-folder inference to recreate a second version of project state. Inspect only the bounded unresolved delta identified by MangoMe.

MangoMe stores state; it does not replay or automatically recover a dead session.

## Big-Bang import

Big-Bang discovery is normally automatic on first attachment of an unknown managed workspace. Do not ask the user to invoke it manually. `bigbang_scan` remains available as an explicit diagnostic/maintenance tool and is non-destructive across configured filesystem roots and optional Git metadata.

`reconcile_bigbang` matches discovery against canonical state without semantic mutation. Candidates, collisions and unresolved items remain explicit. Automatic attachment never promotes ambiguous candidates into contract/specification truth.

## Schema evolution and maintenance

Readers can lazily understand older schema documents. Use `migrate_schema` for an explicit dry-run or persistence migration. Use `maintenance_diagnose` for stale-plan candidates, ID collisions, open approvals and suggested relations. Diagnostics must not silently change semantic truth.

## External model reconciliation

External ChatGPT/Claude/Gemini reviews are advisory. Import results as evidence/suggestions and route them through normal MangoMe verification/approval. External reviewers must not rewrite canonical truth directly.
