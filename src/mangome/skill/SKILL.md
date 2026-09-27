---
name: mangome
description: Use MangoMe automatically for durable multi-agent work: think freely, reconcile before effect, then bind WorkIdentity, current-user turn, normative baseline, evidence, verification, recovery, and handoff. Apply whenever work may change or continue a MangoMe-managed project; the user does not need MangoMe commands or vocabulary.
---

# MangoMe Agent Skill

MangoMe is the canonical operational-memory system for durable multi-agent work. Playbooks may change, Specs may evolve, and workers/sessions may disappear; WorkIdentity and assurance history must survive them all.

## Zero-touch user rule

Zero-touch applies to the **user interface**, not to MangoMe's governance. Never require the user to say “start Big Bang”, create a contract, create a slice, call `begin_work`, call `session_restore`, or otherwise operate MangoMe vocabulary manually. Managed clients bind the workspace automatically through a read-only fast path when MangoMe is first used. Binding performs no filesystem inventory or Big-Bang discovery; canonical restore is lazy at reconciliation/recovery or the effect boundary. Do **not** perform a ritual restore merely because a chat/session started.

The default rule is:

```text
THINK FREELY
    ↓
RECONCILE BEFORE EFFECT
    ↓
GOVERNED PRODUCTIVE WORK
```

A worker may inspect files, search a repository, understand architecture, form hypotheses, classify the request, and draft a **tentative** decomposition before MangoMe reconciliation. Those thoughts are worker judgment, not canonical project state. Before the first productive mutation, external side effect, canonical Plan/Spec/Contract change, or assurance claim, call `reconcile_assignment` and reconcile the tentative understanding with existing WorkIdentity, unfinished work, authority and the current normative baseline.

A bootstrap/reconciliation call must never be used as an excuse to stop ordinary cognition while MangoMe scans a filesystem. **Binding is not discovery.** If MangoMe is unresolved, continue safe reading/reasoning and keep productive effects blocked; explicit discovery/onboarding is a separate operation.

### Explicit MangoMe self-maintenance

When the current user explicitly asks to install, update, repair, hotfix, roll back, or reconfigure **MangoMe itself**, treat that as out-of-band control-plane maintenance rather than ordinary governed project work. If the immediate conversation already establishes MangoMe as the target and the next user turn is elliptical (for example “update it from GitHub”), pass the resolved current-turn target to `reconcile_assignment(target="MangoMe")`; do not rediscover the target from historical host memory. Do not create a WorkIdentity, Contract, Specification, Plan, Slice, approval, or `enter_work` record merely to authorize repair of the governance substrate itself. `reconcile_assignment` returns `CPM/1` for this case and must not require canonical restore/admission first.

The operator request authorizes only the explicitly named MangoMe maintenance surface: the MangoMe source checkout, its virtual environment/package installation, MCP launcher/runtime configuration, and MangoMe service/autostart configuration. It does not authorize unrelated application code or canonical database state. If the requested target version requires a MongoDB/schema migration and database changes are not separately explicit, stop immediately with `DATABASE_CHANGE_REQUIRED`; never manufacture a self-approval in MangoMe. A successful update may be recorded later as evidence/receipt, but that receipt is not a prerequisite for the update.

A worker must also keep **source authority** explicit. Current user intent determines the current turn; canonical MangoMe state determines admitted identity/normative/assurance state; current direct workspace/runtime observation determines observed implementation facts. Registered current documentation may supplement those sources. Generic host memory, prior chats, old audit/eval notes, cached summaries, and agent-specific memory files are **candidate-only discovery hints**. They must never establish current WorkIdentity, Contract/Specification truth, installation path/version, workspace binding, controller authority, or current operational state without revalidation against a higher-authority current source. Do not broadly search historical host memory merely because current state is unresolved.

Use explicit `session_restore` / `session_bootstrap` when the assignment is specifically about recovery/status, when an unmanaged host has no automatic bootstrap, or when `reconcile_assignment` reports that recovery/backfill is required. If canonical restore resolves to `STATE_NOT_FOUND`, preserve that fact. Never create Project/Family/Specification state and call it recovered. Only genuinely new work may use `enter_work` with the user's actual request before productive mutation; historical/resume work requires explicit import/backfill distinct from restore. `enter_work` admits a canonical **WorkIdentity** and an operational-intent baseline; it does **not** turn the prompt into a Specification or Contract.

Do not treat a missing prior Big-Bang command as a user error. If the managed MangoMe tools are missing, stale, or report a deterministic binding/readiness problem, run `mangome doctor --repair` yourself when safe before asking the user to edit configuration. Ask the user only when intent is genuinely ambiguous or a protected authorization/acceptance decision is required. Verification and acceptance remain separate privileged transitions; a worker reaching `DONE_CLAIMED` is a valid durable state, not a reason to fabricate verifier authority.

## Default agent loop

For ordinary assignments in a MangoMe-managed workspace:

```text
USER REQUEST
   ↓
understand the local problem
inspect/search/read as needed
form assumptions + tentative decomposition
   ↓
reconcile_assignment(request_text)
   ↓
STATE_FOUND   → map candidate work onto existing WorkIdentity/baseline/unfinished state
STATE_PARTIAL → bounded recovery/backfill only
STATE_NOT_FOUND → genuinely new work may enter_work; historical work uses explicit import/backfill
   ↓
bind current turn / authority
   ↓
productive effects
   ↓
persist progress + evidence
   ↓
claim / independent assurance
```

This is the normal path. Do not make the agent rediscover MangoMe procedure from dozens of lower-level tools. `reconcile_assignment` is read-only and does not canonicalize the worker's tentative decomposition.

## Open-ended assignments

When the user says things such as “understand the system”, “make reasonable assumptions”, “fix it”, “review this”, or “just get started”:

- inspect enough of the local system to understand the assignment;
- make assumptions and unknowns explicit internally;
- form a tentative local plan/decomposition if useful;
- do **not** treat that tentative plan as canonical project truth;
- before productive effect, run `reconcile_assignment`;
- reuse existing WorkIdentity, Plans, Slices, baselines and evidence where applicable;
- expand inspection when material impact requires it, but never silently expand mutation authority;
- if wider impact is found, record a finding or use SRA/1 rather than casually repairing unrelated areas.

The effect boundary includes code/file/database writes, commits, deployments, external messages/actions, canonical MangoMe mutations, normative promotion, DONE/VERIFIED claims, and other durable project-changing operations. Reading, searching, reasoning, local classification and tentative planning are not themselves productive effects.

## Bitemporal truth maintenance (BTTM/1)

Use BTTM/1 when current work needs durable factual assertions whose real-world validity and organizational knowledge time can differ. `valid_*` answers when a fact is claimed to hold in the represented world; `known_*` answers when MangoMe knew that assertion version. Never collapse those axes.

Canonical truth assertions must be grounded by Evidence or explicit support/assumption/dependency links. Worker prose, model confidence, FJD/1 output and historical host memory are not sufficient grounding. Invalidation is non-destructive: close the known-time interval, preserve the historical row, propagate `REVALIDATION_REQUIRED`, and let PCH reheat the affected region. Truth maintenance decides supportability; Cognitive Hygiene decides activation.

Use `truth_at` for historical reconstruction, `truth_assertion_status` for supportability, `record_truth_assertion` under a bound `VERIFY`/`MODIFY` turn, and `invalidate_truth_assertion` only under `MODIFY`.

## MongoDB trust boundary (MTB/1)

For production, workers must not possess canonical MongoDB credentials. Prefer `MANGOME_TRUST_BOUNDARY=STRICT`, a dedicated MangoMe OS/service identity, an owner-only `MANGOME_MONGODB_URI_FILE`, and an expected service uid. Do not place canonical database credentials in a worker-visible environment or generated client configuration.

`trust_boundary_status` is diagnostic only and never exposes secrets. A trust-boundary failure is a host/deployment problem, not an invitation for the worker to search for credentials, relax permissions, or self-promote database authority.

## Fast bounded judgments (FJD/1)

Use FJD/1 only when a bounded typed decision would save expensive reasoning: classification, triage, routing, activation, relevance or prioritization. A host may produce the value with a heuristic, small local classifier, specialized decision model, or other cheap engine; MangoMe itself does not require a particular inference provider.

Prefer strict `BOOL`, `SCORE`, or `CHOICE` results with explicit confidence. `assess_fast_judgment` validates/gates a transient result; `record_fast_judgment` may persist a result as `PROGRESSIVE` `WORKER_JUDGMENT` after WorkIdentity exists. Do not call FJD/1 merely because it exists, and do not replace ordinary deterministic checks with model scoring.

Never treat confidence as truth. FJD/1 may guide which path to inspect or which context to heat, but it cannot create Evidence, normative truth, verification, acceptance, or mutation authority. Low-confidence signals escalate to stronger reasoning/deterministic inspection. High-impact decisions require review even at high confidence.

## Non-negotiable rules

1. **Think freely; reconcile before effect.** Repository exploration, reasoning, classification and tentative decomposition may happen before MangoMe reconciliation. Before productive mutation, canonical state change, external side effect or assurance claim, call `reconcile_assignment` (or use explicit restore on an unmanaged/recovery path). Managed clients auto-bind the workspace without scanning and resolve canonical restore lazily; `STATE_NOT_FOUND` is never permission to synthesize recovery state.
2. **Categorize every actual assignment.** Call `intake_request` for real work requests; reuse IntakeGov classification when available. A casual status remark, acknowledgement, or observation is not automatically a new assignment and must not be inflated into one.
3. **Resolve before creating.** Search existing project/family/contract/slice identity before creating a new one.
4. **A prompt is not a Contract or Specification.** A user turn may admit durable WorkIdentity, but normative truth requires its own admission path.
5. **WorkIdentity before productive work.** New durable work must have a canonical WorkIdentity before any productive Plan starts.
6. **Plan binding is structural.** A v0.3 Plan binds WorkIdentity + controller-minted WorkTurn + immutable NormativeBaseline before mutation.
7. **Stay bound to the plan and baseline.** After `start_slice`, every progress mutation and `claim_done` uses the same active `plan_id`; `BASELINE_DRIFT` stops the old Plan rather than silently adopting new normative truth.
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
34. **Do not mutate host network/system configuration as part of MangoMe operation.** MangoMe setup/doctor may manage only its documented client/workspace integration surfaces. DNS/resolver, network-manager, firewall, package-manager, SSH and unrelated system configuration are outside MangoMe's normal authority unless the explicit assignment itself is a host-maintenance task.

34. **Slices are internal execution state.** Never expose Slice IDs, Slice decomposition, Plans, recovery cursors, or MangoMe orchestration to the user unless the user explicitly asks to inspect MangoMe itself. Human-visible responses contain outcomes, findings, evidence, blockers, and decisions.
35. **Execute the requested work; do not substitute planning.** An AUDIT/REVIEW/VERIFY request must produce observations/findings/evidence. A new contract, specification, checklist, plan, or audit instruction document is not a substitute for executing that assignment.
36. **Reuse Slices before creating any.** For admitted work, existing relevant Slices are reused exactly as they are. If none exist, MangoMe may materialize the minimum internal Slice(s) needed to execute the current assignment. This is internal state maintenance, not a new user deliverable.
37. **Observe before repair.** Audit/reconciliation first compares normative truth with observed implementation and persists evidence. Only after a concrete deviation is established may the worker repair/adapt/correct within the current authorized scope. Explicit read-only assignments remain read-only.
38. **Do not mutate normative truth to make implementation pass.** Audit findings may update execution state/evidence and may lead to repair work, but Contract/Specification truth changes only when the user explicitly requested a normative change or the authorized amendment path approves it.
39. **Current user intent is primary.** Recovered MangoMe state is context for the current turn; it never substitutes for the current user's request. `STATE_FOUND`, ACTIVE work, an active Plan, or an active Slice never means “continue now”.
40. **Bind the turn to WorkIdentity first.** For v0.3 admitted work, establish the current turn mode (`QUERY`, `CONTINUE`, `EXECUTE`, `VERIFY`, `MODIFY`, or `CONTROL`) against canonical WorkIdentity before productive action. Managed workers consume controller-minted authority; they do not self-authorize the current user turn.
41. **Playbooks are procedural, never authoritative project truth.** Playbooks may guide HOW work runs, but must never define WorkIdentity, effective normative truth, completion, or assurance.
42. **Effective normative truth is deterministic.** Every productive Plan binds an immutable NormativeBaseline derived from the admitted operational intent or current effective Spec/Contract generations. A later normative change causes `BASELINE_DRIFT`; it does not rewrite the old Plan.
43. **Progressive state cannot create canonical truth.** Checkpoints and Playbook selections may survive a crash, but they can only reference an existing WorkIdentity. Recovery/discovery may never promote them into identity, Specification, Contract, or assurance.
44. **Assurance history is Work-bound and append-only.** Claims, verification, and acceptance remain historically attached to WorkIdentity and the baseline under which they were produced, even when Specs or Playbooks later change.
45. **A changed local Contract file is an observation, not canonical truth.** Local, Git, DMS, or other physical copies may change. MangoMe retains immutable canonical Contract generations plus their physical storage bindings.
46. **Only the bound MODIFY path may change normative truth.** Work-bound Specs/contract relations require a MODIFY WorkTurn; Contract-body generation promotion additionally requires the existing single-writer generation grant.
47. **Persistence levels are explicit.** `VOLATILE` Playbook/transient context is trimmed first, `PROGRESSIVE` recovery state is non-normative, and `CANONICAL` identity/baseline/assurance survives context reduction.
48. **Temperature is activation, never truth.** PCH/1 `HOT/WARM/COLD` and continuous temperature only control task-relative cognitive residency. They must never change normative truth, Evidence verdict, assurance, or authority.
49. **COLD means non-resident, not forgotten.** Cognitive hygiene may suppress historical/superseded objects from the worker projection, but canonical history and provenance remain recoverable. A targeted query may reheat historical state without restoring its authority.
50. **Hygiene precedes compilation.** Use the PCH/1 active working set before ContextCompiler/UAI reduction. Canonical execution roots are pinned and cannot be evicted merely to satisfy the active-object budget.
51. **Audit locally, expand only on material impact.** For audit/review/reconciliation assignments, start from the named Ticket/Slice/Artifact/scope and expand SRA/1 only when a persisted finding identifies material downstream impact. Never scan the whole system merely because more context might exist.
52. **Inspection scope and mutation scope are different.** SRA/1 may expand what the worker inspects, but it never expands what the worker may modify. Outside the explicit mutation scope: persist/report the finding and stop mutation.
53. **State assumptions and unknowns.** A worker is not required to know the whole system. Persist assumptions and unknowns with audit findings instead of silently filling gaps from model intuition.
54. **Audit closure is bounded coverage, not global correctness.** `FIXPOINT_REACHED` means no material frontier remains under the configured traversal policy. `BOUNDED_FIXPOINT` means a depth/object boundary was reached. Neither means the whole system is correct or the underlying work is VERIFIED.
55. **Audit does not replace AV/1.** SRA/1 finds and closes an impact frontier; AV/1 still governs independent completion verification. Audit priority may heat PCH context, but never changes truth or assurance.
56. **Fast judgment is advisory only.** FJD/1 `BOOL`/`SCORE`/`CHOICE` outputs are `WORKER_JUDGMENT`; confidence never creates canonical truth, Evidence, assurance, verification, acceptance, or mutation authority.
57. **Escalate uncertainty instead of hiding it.** Low-confidence FJD/1 results must route to stronger reasoning or a deterministic check. `high_impact=true` always requires review even when confidence is high.
58. **Keep the decision engine replaceable.** FJD/1 defines typed decision semantics and gating, not a required model/runtime. Do not add a provider dependency where a heuristic or existing local model is sufficient.
59. **Database identity is deployment state, never agent-discovered state. For ordinary managed work, use the runtime-configured canonical database (default `mangome`). Never search old contracts, host memory, alternate databases, or `mangome_uai_eval` to rediscover the database. The legacy `mangome_uai_eval` database requires explicit eval opt-in; otherwise report the binding error and stop.

Historical host memory is never current authority.** Prior Claude/Codex memory, chat summaries, old audit/eval artifacts, cached notes, and similar host-local memory are candidate-only discovery hints. Never recover current WorkIdentity, Contract/Specification truth, workspace binding, installation/version state, controller authority, or operational truth from them. If consulted, revalidate the candidate against current user intent, canonical MangoMe state, and current direct workspace/runtime observation before use.
60. **Self-maintenance does not self-admit.** An explicit operator request to install/update/repair/rollback/reconfigure MangoMe itself uses the out-of-band `CPM/1` control-plane maintenance path. Do not call `enter_work` or write an approval merely to make MangoMe capable of repairing itself.
61. **No hidden database exception.** `CPM/1` never authorizes canonical MongoDB/schema mutation. If the maintenance target requires such a change, stop with `DATABASE_CHANGE_REQUIRED` unless the user separately and explicitly authorizes it.
62. **Current sources outrank stale host memory.** For MangoMe version/install/runtime state, prefer current user intent, current repository/runtime observation, and current canonical MangoMe state. Old eval contracts, prior chats, host-memory files, and cached summaries are discovery hints only.
63. **Valid time and known time are separate.** BTTM/1 must preserve both represented-world validity and MangoMe transaction/knowledge time; do not overwrite history to make current truth convenient.
64. **Supportability is not activation.** BTTM/1 decides whether an assertion is supportable; PCH/1 decides whether it should be resident. Neither substitutes for assurance or normative authority.
65. **Invalidation propagates, history remains.** Closing a support assertion must mark dependent current assertions `REVALIDATION_REQUIRED` without deleting earlier truth/evidence history.
66. **Workers never receive canonical DB credentials in strict mode.** MTB/1 production deployments use a dedicated service identity and protected credential file. A worker-visible MongoDB URI places that worker inside the database trust boundary and invalidates claims of service-level isolation.
67. **Trust-boundary failures are host-owned.** A worker must not search for credentials, weaken filesystem permissions, switch to an admin MongoDB role, or bypass MangoMe when MTB/1 fails closed.

## WorkIdentity-first turn binding

For v0.3 admitted work, the governing order is:

```text
CURRENT USER TURN
    ↓
controller-minted bind_work_turn(mode, actor, work_id)
    ↓
CANONICAL WORK IDENTITY
    ↓
CURRENT NORMATIVE BASELINE
    ↓
PLAYBOOK-GUIDED EXECUTION (non-normative)
    ↓
PROGRESSIVE CHECKPOINTS
    ↓
CANONICAL CLAIMS / EVIDENCE
    ↓
INDEPENDENT ASSURANCE
```

Turn modes have distinct semantics:

```text
QUERY     read/answer only; no productive or normative mutation
CONTINUE  explicitly continue unresolved execution for this Contract
EXECUTE   perform requested productive work for this Contract
VERIFY    observe/reconcile and persist Evidence; do not change normative truth
MODIFY    change normative Contract truth; receives the single generation write grant
CONTROL   explicit pause/accept/reject/override/control action
```

The following implications are forbidden:

```text
ACTIVE != CURRENTLY REQUESTED
STATE_FOUND != CONTINUE
CONTRACT_FOUND != EXECUTE CONTRACT
QUESTION ABOUT WORK != WORK ORDER
RESTORE != RESUME
PATH != IDENTITY
PLAN != EXECUTION
SLICE != CONTRACT
MANGOME CONTEXT != USER INTENT
```

Contract content is versioned by immutable generations. A local edit remains a working representation until `promote_contract_generation` succeeds using the active MODIFY-turn generation grant. Promotion is compare-and-swap bound to the generation/hash observed when the grant was acquired. If another generation wins first, stop with a generation conflict; never merge silently or rewrite history.

## Start of work

Default decision path:

```text
local understanding / tentative decomposition
   ↓
reconcile_assignment(request_text)
   ↓
STATE_FOUND?
   ├─ yes → reconcile with canonical WorkIdentity / baseline / unfinished work
   ├─ partial → bounded validation/backfill only; no productive mutation
   └─ not found → preserve RESTORE_STATE_NOT_FOUND
                 ├─ genuinely NEW work → enter_work(...)
                 └─ historical/resume work → explicit import/backfill, not fake restore
   ↓
current-turn binding / authority
   ↓
productive effect
```

Managed runtimes may already have a volatile read-only workspace binding, while canonical restore remains lazy. `reconcile_assignment` is therefore the preferred worker-facing bridge; it is not another persistence layer and does not make tentative worker judgment canonical. Explicit `session_restore` remains the recovery/status primitive.

`enter_work` is the zero-touch entry point for ordinary new work. In v0.3 it admits WorkIdentity and an operational-intent baseline without manufacturing a Specification from the prompt. `begin_work` remains the convenience path for already admitted work. Productive Plans must be bound to WorkIdentity, current WorkTurn and current NormativeBaseline before mutation.

`prepare_assignment` is the zero-touch path for an already admitted assignment when the worker must execute/reconcile work rather than invent a new user-facing planning artifact. It reuses existing Slices; only an admitted Family with no Slices may receive a minimal internal Slice. Slice/Plan details stay internal.


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

## Scoped recursive audit (SRA/1)

Use SRA/1 for classification, architecture, artifact/code review, incident, reconciliation, impact, or security audits where the initial assignment is local but material dependencies may extend beyond it.

```text
start_scoped_audit(
  family_id=...,
  actor_id=...,
  objective=...,
  target_ids=[...],        # or target_refs
  mode="READ_ONLY" | "REPAIR_WITHIN_SCOPE",
  mutation_scope_ids=[...], # only for repair mode; subset of initial scope
  max_depth=...,
  max_objects=...,
  turn_id=...
)

audit_context / audit_status
    ↓
inspect the returned frontier in the real system
    ↓
record_audit_finding(
  finding_class="NO_ISSUE" | "INFO" | "ISSUE" | "CONFLICT" | "ASSUMPTION" | "UNKNOWN",
  impact="NONE" | "LOCAL" | "EXPAND" | "OUTSIDE_SCOPE",
  assumptions=[...],
  unknowns=[...],
  evidence_ids=[...]
)
    ↓
repeat only while frontier remains
    ↓
close_scoped_audit
```

Before repairing something found during an audit, `audit_mutation_allowed` may confirm whether the target is inside the audit's frozen mutation boundary. A positive answer is not sufficient authorization by itself: the normal Plan/WorkTurn and host/filesystem permissions still apply.

Do not turn `OUTSIDE_SCOPE` findings into implicit scope or mutation authority. They are durable handoff signals for a separate assignment, audit, or authorized follow-up.

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
