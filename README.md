# MangoMe

<p align="center">
  <img src="docs/mangome-banner.png" alt="MangoMe — persistent multi-agent operational memory" width="100%">
</p>

<p align="center">
  <strong>Governed work state survives the agent.</strong><br>
  Persistent truth, work-state, evidence and reconciliation for long-lived multi-agent work.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.3.8-yellow">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="MongoDB" src="https://img.shields.io/badge/canonical%20store-MongoDB-47A248">
  <img alt="UAI" src="https://img.shields.io/badge/semantic%20transport-UAI%2F1-6f42c1">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
</p>

---

## MangoMe is not just a state machine

MangoMe is the **canonical operational memory** underneath long-running AI work.

It combines responsibilities that are usually scattered across chats, repositories, task trackers, reports and agent memory:

```text
DOCUMENT STORE
    +
WORK GRAPH
    +
DURABLE WORK IDENTITY
    +
STATE MACHINE
    +
SPECIFICATION / NORMATIVE BASELINE HISTORY
    +
EVIDENCE / PROVENANCE LEDGER
    +
EXECUTION ECONOMICS
    +
DETERMINISTIC CONTEXT COMPILER
    +
COMPACT SEMANTIC TRANSPORT
```

A worker is not a truth source. A worker can execute, observe, propose and claim completion. MangoMe persists what the work **is**, what is **expected**, what was **observed**, what was **claimed**, and what was independently **verified**.

> **Workers are ephemeral executors. MangoMe is the canonical operational record within its governed scope.**

The central distinction is:

```text
N = normative truth
    What must be true?

O = observed truth
    What is actually present?

J = worker judgment
    What does the worker conclude from N and O?

V = independent verification
    What has been independently demonstrated?
```

MangoMe externalizes state so agents spend model capacity on the unresolved delta instead of repeatedly reconstructing history from prompts, filesystem paths or prior agent prose.

> **Externalize state. Localize uncertainty. Preserve agency. Verify independently.**

---

# Why MangoMe exists

Long-running AI work tends to fail in a predictable way: artifacts survive, but the shared operational understanding does not.

A Claude session ends. Codex continues. Another agent sees a different database. A worker says “done”. A specification has changed. A previous test result exists but is stale. Two agents touch related work. A coordinator reconstructs state from a repository instead of reading the canonical system.

MangoMe moves that problem out of the prompt and into durable, inspectable state.

A normal worker should not need to know or expose MangoMe internals to the user. The worker should use MangoMe to organize its execution, persist progress and recover safely.

---

# v0.3.8 — Codex Skill Discovery & canonical workspace rebinding

v0.3.8 fixes two integration failures found during live Codex operation. First, Codex now receives the MangoMe Agent Skill in the user-scoped location `~/.codex/skills/mangome/SKILL.md`, so Skill discovery no longer depends on the current workspace being present in Codex's saved-project catalog. Managed attestation reports `SKILL_NOT_INSTALLED` or `SKILL_VERSION_MISMATCH` when that surface is absent or stale.

Second, canonical recovery no longer equates an exact workspace-path hash miss with missing MangoMe state. MangoMe first tries the exact deterministic workspace identity. If that misses, it may rebind read-only to exactly one compatible canonical workspace already persisted in the configured MangoMe database. This resolution uses only canonical MangoMe workspace identity; it never searches host memory, old contracts, Git history, or the filesystem and never creates replacement state.

```text
current cwd / workspace path
        ↓
exact canonical workspace key
        ↓ miss
existing canonical MangoMe workspace identities only
        ↓
1 compatible candidate → CANONICAL_REBOUND
>1 candidates          → STATE_PARTIAL / WORKSPACE_BINDING_AMBIGUOUS
0 candidates           → STATE_NOT_FOUND
```

Restore and reconciliation results now expose sanitized `database_binding` and `workspace_resolution` diagnostics so an operator can distinguish a wrong database from a wrong workspace identity in one call.

# v0.3.7 — deterministic runtime database binding

v0.3.7 makes database identity deployment state rather than agent-discovered state. Ordinary managed operation defaults to the canonical local database `mangome`; the legacy `mangome_uai_eval` database is rejected unless eval mode is explicitly enabled. `health()` exposes process readiness, database readiness and the effective sanitized database binding, while managed MongoDB timeouts prevent a stale or unreachable binding from producing multi-minute startup loops. Re-running managed setup/doctor also removes stale MangoMe eval client entries and rebinds the current managed server.

# v0.3.6 — bitemporal truth + hardened MongoDB trust boundary

v0.3.6 closes the two remaining core gaps identified after the v0.3.x architecture review. `BTTM/1` adds non-destructive bitemporal truth maintenance (`valid_time` vs `known_time`) with support/assumption/dependency invalidation and PCH revalidation heating. `MTB/1` adds an optional fail-closed production trust-boundary profile so canonical MongoDB credentials can live behind a dedicated MangoMe service identity instead of in worker-visible environment/configuration. See `docs/bitemporal-truth-maintenance.md` and `docs/trust-boundary.md`.

# v0.3.5 — out-of-band control-plane self-maintenance

v0.3.5 closes a real control-plane deadlock found during live Codex operation. An explicit operator request to update/repair MangoMe itself must not require `enter_work`, a new WorkIdentity, or a self-approval persisted into the same MangoMe control plane being repaired. `reconcile_assignment` now returns the read-only `CPM/1` disposition for explicit MangoMe self-maintenance and short-circuits canonical restore/admission.

`CPM/1` is deliberately narrow: it covers only MangoMe source/package/runtime/service maintenance named by the current user. It never authorizes canonical MongoDB/schema mutation. If the requested target requires a database/schema migration without separate explicit authorization, the worker must stop with `DATABASE_CHANGE_REQUIRED`. Historical host memory and old eval/audit artifacts remain candidate-only hints; current user intent plus current repository/runtime observation outrank them for maintenance state. Casual status remarks are not work orders.

# v0.3.4 — non-blocking bootstrap / lazy discovery hotfix

v0.3.4 fixes a real-world zero-touch failure found during a Codex/MCP run: an explicit `session_bootstrap` on an unbound workspace could fall through to full workspace attachment, which may perform filesystem inventory and candidate Big-Bang discovery. That made a read-only bootstrap capable of blocking for minutes.

Binding and discovery are now separate operations. Managed startup creates only a volatile `READ_ONLY_FAST_PATH` workspace binding. No filesystem scan, Big-Bang scan, Git archaeology, or canonical mutation occurs merely because MangoMe starts or a worker requests restore/reconciliation. Canonical restore is lazy at the recovery/effect boundary, while full discovery remains explicit through refresh/onboarding operations.

The operational invariants are:

```text
MANGOME_MUST_NOT_BLOCK_COGNITION
BINDING_IS_NOT_DISCOVERY
BOOTSTRAP_PERFORMS_NO_FILESYSTEM_SCAN
BINDING_FAILURE_BLOCKS_EFFECTS_NOT_REASONING
```

`workspace_status(refresh=True)` remains available when a host/operator explicitly wants a full attachment/discovery refresh.

# v0.3.3 — zero-touch assignment reconciliation

v0.3.3 removes the worker-facing **restore-first ritual** from the normal managed workflow. A worker may inspect, search, reason, classify and form a tentative decomposition before MangoMe involvement. MangoMe becomes mandatory at the **effect boundary**, not at the first thought.

```text
user request
    ↓
free local understanding / tentative decomposition
    ↓
reconcile_assignment
    ↓
existing WorkIdentity / baseline / unfinished state / authority
    ↓
governed productive effect
```

The governing rule is **THINK FREELY, RECONCILE BEFORE EFFECT**. Managed clients bind the workspace through a cheap read-only fast path when MangoMe initializes; canonical restore is resolved lazily when reconciliation/recovery or an effect gate actually needs it. Workers therefore do not call `session_restore` merely because a session started. `session_restore` remains the explicit recovery/status primitive, while `reconcile_assignment` is the normal worker-facing bridge from tentative judgment to governed work.

The effect boundary includes durable code/file/database mutation, commits, deployment, external side effects, canonical MangoMe mutations, normative promotion and assurance claims. Tentative reasoning is never promoted automatically, and existing work is still reused before new work is admitted.

v0.3.3 also adds **FJD/1 Fast Judgment Decisions**, a deliberately small provider-neutral typed-decision layer for cheap repeated judgments. It accepts strict `BOOL`, `SCORE`, and `CHOICE` outputs with explicit confidence and returns `USE_SIGNAL`, `REVIEW`, `REVIEW_REQUIRED`, or `ESCALATE`. FJD/1 performs no model inference itself; a host may use a heuristic, small local classifier, specialized decision engine, or stronger model. Every result remains `WORKER_JUDGMENT`: confidence can guide classification, triage, routing, activation, or prioritization, but can never create truth, Evidence, assurance, verification, acceptance, normative promotion, or mutation authority. See `docs/fast-judgment.md`.

---

# v0.3.2 — scoped recursive audit and impact closure

v0.3.2 adds **SRA/1**, a bounded recursive audit layer for the normal engineering reality that a worker is competent inside a local assignment but does not and should not need to understand the entire system before acting.

```text
initial scope
    ↓
inspect current frontier
    ↓
persist finding / evidence / assumptions / unknowns
    ↓
material impact?
  no → frontier shrinks
  yes → follow bounded confirmed relations
    ↓
repeat until fixpoint or explicit boundary
```

SRA/1 separates **knowledge**, **inspection**, **mutation**, and **assurance** boundaries. The inspection frontier may grow when a finding has material impact; the mutation scope is frozen at audit start and never grows automatically. A closed audit therefore means only that the configured impact frontier has reached `FIXPOINT_REACHED` or `BOUNDED_FIXPOINT`. It never means the entire system is correct or that the audited object is `VERIFIED`.

The active audit frontier is supplied to PCH/1 as additional cognitive roots, so the worker receives the currently relevant impact region without loading the entire historical graph. See `docs/scoped-recursive-audit.md`.

---

# v0.3.1 — persistent cognitive hygiene and thermal working sets

v0.3.1 adds a deterministic homeostasis layer above MangoMe's durable v0.3 work graph and below the existing `ContextCompiler`. It does not create another memory system. Canonical MongoDB state remains the historical record; PCH/1 computes only which objects should be cognitively resident for the present task.

```text
Persistent canonical history H_t
        ↓
PCH/1 Cognitive Hygiene
  graph reachability + task relevance
  + authority + freshness + support
        ↓
Bounded active working set A_t
  HOT / WARM / COLD
        ↓
existing ContextCompiler
        ↓
worker / UAI context C_t
```

The central invariants are:

```text
temperature != truth
temperature != assurance
COLD != deleted
|C_t| <= B_context
|A_t| <= B_active
H_t remains historically recoverable
```

`HOT`, `WARM`, and `COLD` are buckets over a continuous task-relative temperature in `[0,1]`. Current canonical execution roots are pinned. Superseded or historical state normally cools, but a targeted historical query can reheat it for inspection/revalidation without restoring normative authority. The GC analogy is deliberately non-destructive: PCH/1 borrows reachability, generations and residency pressure, but "collection" only removes objects from the active worker set.

The full diagnostic surface is available through `cognitive_hygiene`; normal worker execution receives only the bounded selection summary through `ContextCompiler` and UAI/1.

---

# v0.3.0 — durable WorkIdentity, progressive persistence, and playbook isolation

v0.3.0 changes MangoMe's primary architectural anchor. Contracts and Specifications remain important normative inputs, but they no longer define the identity of the work. Playbooks remain procedural inputs and are explicitly non-normative.

> **Playbooks may change.  
> Specs may evolve.  
> Workers and sessions may disappear.  
> The identity of the work and its assurance history must survive them all.**

The governing model is:

```text
Intent-first
    ↓
Identity-bound
    ↓
Playbook-guided
    ↓
Spec-governed
    ↓
Assurance-preserving
```

MangoMe now separates three persistence levels:

```text
VOLATILE
  selected Playbook body / transient execution context

PROGRESSIVE
  crash-recovery checkpoint / working cursor / non-normative selection state

CANONICAL
  WorkIdentity / NormativeBaseline binding / Plan authority / Evidence / Claims / Assurance history
```

A prompt may admit a durable WorkIdentity, but it does **not** automatically become a Specification or Contract. Productive Plans are bound to the current immutable `NormativeBaseline`; if the effective Spec/Contract truth changes, an older Plan stops with `BASELINE_DRIFT` rather than silently inheriting the new target.

Playbooks are deliberately weaker than canonical state:

```text
Playbook = HOW work is normally performed
Specification = WHAT must become true
MangoMe = WHAT survives: identity, persistence, provenance, execution binding, and independent assurance
```

The hard recovery rule is therefore:

```text
filesystem / Git / Playbook / prior agent prose
        ↓
may guide or corroborate
        ↓
MUST NOT reconstruct WorkIdentity, current normative truth, or assurance
```

For managed MCP operation, first admission after `STATE_NOT_FOUND` may trust the current client-relayed user intent. Once canonical workspace state exists, minting additional durable work authority or a new WorkTurn belongs to the host/control-plane capability boundary. Recovered workers consume a bound turn; they do not self-authorize current-user intent. Direct library use remains a lower-level integration boundary and must be isolated from untrusted workers in high-assurance deployments.

The ContextCompiler and UAI projection now expose the persistence boundary explicitly so canonical identity/assurance survives context reduction while volatile Playbook material is trimmed first.

---

# v0.2.2 — execution integrity hardening

v0.2.2 is a hardening release built on GitHub `main` commit:

```text
10c7859826a0fa379e99ffbcada0321eb1c36560
```

That commit was `v0.1.9rc4`.

The release addresses an observed failure mode: an agent received an **audit assignment**, but instead of performing the audit it generated a large new audit/planning artifact and presented that planning output as the result.

MangoMe must allow agents to organize work internally without allowing planning to replace execution.

The v0.2.2 execution rule is therefore:

```text
USER ASSIGNMENT
      ↓
RESTORE CANONICAL STATE
      ↓
RELEVANT SLICES EXIST?
   ┌───────────────┴───────────────┐
  YES                              NO
   ↓                                ↓
REUSE EXISTING                MATERIALIZE MINIMUM
SLICES                        INTERNAL SLICE(S)
   └───────────────┬───────────────┘
                   ↓
              EXECUTE WORK
                   ↓
             OBSERVE REALITY
                   ↓
            PERSIST EVIDENCE
                   ↓
        RECONCILE EXPECTED/ACTUAL
                   ↓
          REPAIR / ADAPT IF NEEDED
                   ↓
              RE-OBSERVE
                   ↓
             CLAIM COMPLETION
                   ↓
          INDEPENDENT VERIFICATION
```

The user should receive the **result of the assignment**, not MangoMe's internal decomposition.

## Contract-first turn binding and immutable generations

MangoMe treats the **current user turn** and the **recovered work state** as different things. Restored ACTIVE work is durable context, not an instruction to continue it. For admitted contract work, an agent first binds the current turn to the intended logical Contract with one of six modes: `QUERY`, `CONTINUE`, `EXECUTE`, `VERIFY`, `MODIFY`, or `CONTROL`.

The recovery priority is therefore:

```text
CURRENT USER TURN
    ↓
EFFECTIVE CONTRACT / SPECIFICATION
    ↓
OBSERVED ARTIFACTS / EVIDENCE
    ↓
UNRESOLVED DELTA
    ↓
DERIVED PLAN / SLICE STATE
```

Plans and Slices remain durable and useful, but they are execution decomposition rather than normative truth. An active Slice never authorizes the current turn by itself.

Contract bodies can exist in more than one physical location. MangoMe keeps the logical Contract identity separate from those locations and can persist immutable canonical generations of the normative body in MongoDB. A local or Git/DMS copy may change, but that changed file is only an observation until an explicitly bound `MODIFY` turn promotes it.

Promotion is single-writer and compare-and-swap protected. A generation grant is bound to the Contract, actor, current turn, base generation, and base content hash. Only that grant may create the next immutable generation; concurrent or stale promotion fails closed instead of merging or overwriting silently.

This gives the intended asymmetry:

```text
logical Contract          durable identity
canonical generations    immutable normative history
physical files            mutable working representations / bindings
Plans and Slices          derived execution state
```

The key invariants are:

> **MangoMe context never substitutes for current user intent.**

> **A changed contract file is not canonical truth until the authorized MODIFY turn promotes a new generation.**

## Slices are internal execution state

Slices are durable execution addresses, not normal user-facing deliverables.

For an admitted assignment:

- if suitable Slices already exist, MangoMe reuses them;
- it does not create replacement Slices merely because a new session or agent started;
- if an admitted Family genuinely has no Slice, MangoMe may materialize the minimum internal Slice needed to execute the assignment;
- internal Slice/Plan details are not normal human-facing output;
- a user does not need to ask for, manage, name or approve ordinary internal Slices.

The new `prepare_assignment` surface exists for this execution path.

```text
prepare_assignment
    ↓
reuse existing Slice(s)
OR
materialize minimum internal Slice
    ↓
create/bind Plan
    ↓
start executable target(s)
```

It returns internal execution bindings for the client/worker, while the presentation policy explicitly marks Slice details as internal.

## Planning is not execution

For audit, review and verification work, a checklist, plan, specification or newly authored contract is not a substitute for executing the requested work.

An audit-like assignment cannot reach `DONE_CLAIMED` merely because the worker produced planning prose. The Slice must have persisted non-claim Evidence demonstrating that observation actually occurred.

This closes the failure pattern:

```text
AUDIT REQUEST
    ↓
WRITE AN AUDIT PLAN
    ↓
CLAIM SUCCESS
```

The valid path is:

```text
AUDIT REQUEST
    ↓
OBSERVE
    ↓
EVIDENCE
    ↓
FINDINGS / DELTA
    ↓
OPTIONAL REPAIR
    ↓
RE-OBSERVE
    ↓
DONE_CLAIMED
```

## Observe before repair

Audit/reconciliation work first establishes the delta between normative and observed state. Repair, adaptation or correction is a subsequent action where the assignment permits mutation.

A read-only audit remains read-only.

A repair-capable assignment may continue from findings into correction, but it must not silently rewrite normative Contract/Specification truth merely to make implementation appear compliant.

---

# Zero-touch operation

Zero-touch is a **user-interface property**, not a weaker truth model.

```text
user gives a normal task
        ↓
worker understands / inspects / forms tentative decomposition
        ↓
reconcile_assignment
        ↓
STATE_FOUND | STATE_PARTIAL | STATE_NOT_FOUND
        ↓
STATE_FOUND   → reconcile with existing WorkIdentity/baseline/work
STATE_PARTIAL → bounded validation/backfill only
STATE_NOT_FOUND → never synthesize recovery state
        ↓
new work?       → enter_work
admitted work?  → bind current turn + prepare_assignment / begin_work
        ↓
Plan-bound internal Slice execution
        ↓
Evidence / claims / verification
```

The user should not have to say:

- “create a Slice”;
- “start Big Bang”;
- “call `begin_work`”;
- “create a Plan”;
- or otherwise operate MangoMe vocabulary manually.

The internal machinery remains strict even though the user-facing workflow is simple.

---

# Restore is not creation

Recovery is identity-driven.

```text
STATE_FOUND
STATE_PARTIAL
STATE_NOT_FOUND
```

`STATE_NOT_FOUND` is a real state. It does **not** mean “create replacement state and call it restored”.

For admitted work:

> **Recovery follows identity. Discovery must never create or reconstruct admitted identity/state.**

Filesystem paths, Git/worktree history, contract folders, evidence folders and previous-agent prose may validate a bounded unresolved delta. They are not substitutes for canonical MangoMe state.

`GOAL_ACTIVE` or an unfinished Family does not itself grant execution permission. Productive work follows canonical executable items and active plan bindings.

---

# MangoMe is infrastructure

Agents may **use** MangoMe but must not modify MangoMe source, tests, packaging or managed configuration unless the explicit assignment targets MangoMe itself.

A blocked application task, failed verification, missing state or runtime defect is not implicit permission to self-edit the governance substrate.

Hard filesystem/process enforcement remains a host/runtime responsibility.

This distinction is important:

```text
application task fails
      ≠
permission to modify MangoMe
```

---

# Canonical persistence and runtime binding

MongoDB remains MangoMe's production canonical store.

```text
Production canonical persistence = MongoDB
```

v0.2.2 strengthens runtime binding because a correct state model is useless if different agents silently connect to different databases.

Managed client configuration now carries the expected database identity:

```text
MANGOME_DATABASE
MANGOME_EXPECTED_DATABASE
```

If the configured runtime database does not match the expected managed database, initialization fails closed with:

```text
WRONG_MANGOME_DATABASE
```

This is intentionally separate from source/version binding:

```text
MANGOME_EXPECTED_VERSION
MANGOME_EXPECTED_SOURCE_ROOT
MANGOME_EXPECTED_DATABASE
```

The practical invariant is:

```text
GitHub/source identity
        +
runtime package identity
        +
managed MCP target
        +
MongoDB database identity
        =
one intended MangoMe runtime
```

Direct worker access to MongoDB remains outside MangoMe's service trust boundary. Production deployments should isolate canonical database write credentials from untrusted workers.

---

# Schema evolution fails closed on the future

MangoMe persists a `schema_version` on canonical documents.

Older known schema versions can be upgraded deterministically by registered migrations.

v0.2.2 adds the opposite boundary as well: an older reader must not silently interpret a **future** schema it does not understand.

```text
persisted schema <= reader schema
    → normal read / migration path

persisted schema > reader schema
    → UnsupportedSchemaVersion
```

This protects mixed-version agent environments from quietly treating newer state as if it were older compatible state.

---

# Hard context envelope

Canonical truth is never truncated merely to fit an agent prompt.

MangoMe instead compiles a **disposable execution projection**.

v0.2.2 adds a deterministic hard byte envelope to `ContextCompiler`:

```python
ContextCompiler(service).compile(
    family_id,
    slice_id,
    max_bytes=...
)
```

The compiler follows a deterministic reduction policy when the projection exceeds the envelope:

1. preserve normative and active execution state;
2. compact optional Evidence payload detail;
3. compact optional Contract storage detail;
4. omit older optional Evidence entries where required;
5. fail closed if mandatory state itself cannot fit.

The failure is explicit:

```text
ContextBudgetExceeded
```

The rule is:

> **Canonical truth is never compressed destructively. Only the execution projection is bounded.**

MangoMe uses a byte envelope rather than pretending it can guarantee provider-specific token counts without the exact tokenizer. Provider-reported token counts continue to belong in Execution Receipts.

---

# Work Graph query hardening

MangoMe does not introduce an in-memory graph truth store in v0.2.2.

Before adding a Change-Stream-driven DAG cache, the repository first removes avoidable broad reads.

Graph lookup now uses indexed edge predicates for incoming and outgoing relationships rather than reading the whole Edge collection and filtering in Python.

MongoDB indexes include the relevant directional access paths, including reverse `to_id` lookup and Evidence subject access.

The current decision is deliberate:

```text
first: query/index correctness
then: measure
only then: consider an in-memory topology cache
```

A second live graph representation would add cache invalidation and runtime-consistency failure modes. That is not justified until profiling shows indexed MongoDB traversal to be a real bottleneck.

---

# Core entities

MangoMe gives first-class identity to durable operational objects including:

```text
Request
Project
Contract Family
Contract Contribution
Specification
Plan
Slice
Claim
Evidence
Artifact
Graph Edge
Approval
Model Profile
Execution Receipt
Materialized Status View
```

Every first-class entity has an immutable internal `entity_id`.

Human identifiers such as declared contract or Slice IDs may collide without silently overwriting history; ambiguity is surfaced rather than hidden.

---

# Core invariants

## 1. Work identity is more durable than a session

A chat, prompt, branch or model invocation is not the identity of the work.

## 2. A prompt is not automatically Contract Truth

User intent may admit operational work. Durable normative contract evolution remains explicit and append-only.

## 3. Slices are durable internal execution addresses

Execution state and assurance state remain separate dimensions.

Execution examples:

```text
PLANNED
STARTED
ACTIVE
PAUSED
BLOCKED
DONE_CLAIMED
CANCELLED
```

Assurance examples:

```text
UNVERIFIED
PARTIAL
VERIFIED
ACCEPTED
REJECTED
```

A normal state is:

```text
DONE_CLAIMED / UNVERIFIED
```

## 4. Existing Slices are reused

A new worker/session does not justify duplicate work decomposition.

When an admitted Family already contains relevant Slices, assignment preparation reuses them. Missing internal work structure may be created only where necessary for execution.

## 5. Plan before mutate

Productive mutations remain bound to a persisted Plan.

```text
submit_plan / prepare_assignment
    ↓
start_slice(plan_id=P)
    ↓
update_slice_progress(plan_id=P)
    ↓
claim_done(plan_id=P)
```

## 6. DONE is a claim

```text
worker: "done"
        ↓
DONE_CLAIMED
        ↓
independent Evidence / gates
        ↓
VERIFIED
        ↓
optional authorized acceptance
        ↓
ACCEPTED
```

`DONE_CLAIMED != VERIFIED` remains a core invariant.

## 7. Evidence is not automatically proof

Worker-authored Evidence can support work, but independent verification remains separately authorized.

Audit/review work in v0.2.2 must at minimum persist real observational Evidence before claiming completion; prose planning alone is insufficient.

## 8. Normative truth is not rewritten to fit implementation

If observed reality conflicts with the current Specification, that conflict is a finding. A worker may repair implementation where authorized or propose an amendment, but it may not silently redefine the requirement.

## 9. Parallelism is allowed; canonical writes are guarded

MangoMe does not globally serialize agents. It protects canonical document writes through revision / compare-and-swap semantics and surfaces collisions where useful.

---

# Contract evolution

Contract contributions are append-only.

Supported relations include:

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

`effective_family_view` resolves confirmed supersession and exposes conflict/suggestion state without silently merging ambiguous prose.

---

# AV/1 — adversarial completion verification

MangoMe treats worker completion as a claim to inspect.

```text
DONE_CLAIMED
    ↓
completion_review
    ↓
verifier observes / replays / inspects
    ↓
submit_verification_observation
    ↓
attested independent Evidence
    ↓
verify_slice
    ↓
VERIFIED
```

The verifier path is intentionally separate from worker execution.

A worker may not self-upgrade its completion claim into verified truth.

---

# RB/1 — reproducible Evidence binding

Where Evidence should remain reusable, MangoMe can bind it to concrete execution inputs through RB/1.

A reproduction binding can include:

- command identity;
- caller-supplied exit code;
- relevant input hashes;
- Git commit context;
- output Artifact identity;
- stdout/stderr hashes;
- environment **names** without secret values;
- a deterministic fingerprint.

Freshness can later become `REUSABLE`, `STALE`, `UNKNOWN`, `UNBOUND` or `INADMISSIBLE`, but freshness never creates `VERIFIED` by itself.

---

# UAI/1 — compact semantic transport

MangoMe can compile canonical state into a compact transport representation for expensive workers.

The key rule remains:

> **MangoMe does not compress canonical truth. It compiles a disposable execution projection of that truth.**

UAI/1 packets include a semantic hash, and UAI/1R worker results bind back to that hash. Decoded results never directly mutate canonical state; actions still flow through normal MangoMe mutation, Evidence and verification paths.

---

# Assignment surfaces

## `reconcile_assignment`

Read-only RAE/1 bridge from tentative worker understanding to governed work. It resolves canonical restore state and returns whether the worker should reconcile with existing work, perform bounded recovery/backfill, or admit genuinely new work. It never canonicalizes the worker's tentative decomposition.

## `enter_work`

Zero-touch admission for genuinely new ordinary work.

## `prepare_assignment`

v0.2.2 execution-preparation surface for already admitted work.

It:

- classifies the assignment;
- uses the current effective Specification;
- reuses existing Slices;
- materializes a minimal internal Slice only when none exist;
- persists a Plan;
- binds executable targets to that Plan;
- exposes a presentation policy that keeps Slices internal.

It is specifically intended to prevent agents from replacing execution with a new user-facing planning artifact.

## `begin_work`

Convenience composition for an already admitted Family/Specification when a specific bounded Slice is being started.

---

# MCP tools

The v0.2.2 MCP surface includes the existing MangoMe tools plus the hardened assignment path.

```text
Session / recovery
  health
  workspace_status
  reconcile_assignment
  session_restore
  session_bootstrap
  recovery_context

Intake / specification
  intake_request
  create_spec
  enter_work
  prepare_assignment
  begin_work

Identity / registry
  resolve
  create_project
  create_family
  register_contract
  import_contract_bundle
  attach_artifact
  link_entities

Planning / execution
  submit_plan
  start_slice
  update_slice_progress
  claim_done
  close_plan

Evidence / assurance
  submit_evidence
  attest_evidence
  completion_review
  submit_verification_observation
  set_gate
  set_gate_controlled
  verify_slice
  request_override
  approve_override
  reject_override
  list_approvals
  accept_slice

Read / truth
  status
  project_overview
  effective_family_view
  read_context
  compile_execution_context
  graph

Compact semantic transport
  compile_uai_context
  expand_uai_context
  decode_uai_result
  render_uai_result

Runtime / delegation
  publish_worker_runtime
  execution_eligibility
  authorize_delegation
  complete_delegation
  delegation_status

Fast judgment / decision gating
  assess_fast_judgment
  record_fast_judgment
  fast_judgment_status

Economics
  register_model
  record_execution_receipt
  model_stats

Discovery / maintenance
  discovery_scopes
  repository_locations
  bigbang_scan
  reconcile_bigbang
  filesystem_scan
  filesystem_references
  build_reproduction_binding
  evidence_freshness
  refresh_views
  maintenance_diagnose
  migrate_schema
```

---

# Installation

Requirements:

- Python 3.10+
- MongoDB for canonical production persistence

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Managed client setup:

```bash
mangome setup --client auto
```

For Codex, managed setup installs the MangoMe Agent Skill user-scoped at:

```text
~/.codex/skills/mangome/SKILL.md
```

This keeps the Skill available even when the current workspace is not present in Codex's saved-project catalog. The MCP binding remains workspace-scoped; Skill discovery and MCP registration are intentionally separate integration surfaces.

Claude Code can use private LOCAL scope by default; project scope remains explicit:

```bash
mangome setup --client claude-code --claude-scope project
```

For deterministic local tests:

```bash
export MANGOME_BACKEND=memory
mangome-mcp
```

For canonical MongoDB persistence:

```bash
export MANGOME_BACKEND=mongo
export MANGOME_MONGODB_URI='mongodb://127.0.0.1:27017'
export MANGOME_DATABASE='mangome'
mangome-mcp
```

Managed clients generated by MangoMe additionally bind the expected database identity.

The default MCP transport is stdio.

Streamable HTTP can be enabled through the existing `MANGOME_MCP_TRANSPORT`, host and port variables.

---

# Agent Skill

Canonical Skill source:

```text
skill/mangome/SKILL.md
```

The project keeps mirrored Skill surfaces for packaging and supported clients. They must remain synchronized. Managed Codex setup additionally installs the same canonical Skill user-scoped at `~/.codex/skills/mangome/SKILL.md`; this runtime installation is attested independently from MCP visibility and does not require the workspace to appear in Codex's saved-project catalog.

The Skill teaches the normal worker path:

- think freely and form only a tentative local decomposition;
- reconcile with MangoMe before productive effect;
- use `reconcile_assignment` instead of a ritual restore-first step;
- resolve/reuse existing WorkIdentity, plans and evidence before creating new work;
- keep Slice/Plan mechanics internal;
- use `prepare_assignment` for admitted assignments;
- planning is never a substitute for execution;
- audits must persist actual observation Evidence;
- observe the delta before repair;
- do not mutate MangoMe unless MangoMe itself is the assignment target.

---

# Typical lifecycle

Ordinary new work:

```text
understand locally
→ reconcile_assignment
→ STATE_NOT_FOUND for genuinely new work
→ enter_work
→ internal Plan/Slice execution
→ Evidence
→ claim_done
→ independent verification where required
```

Existing admitted work:

```text
understand locally
→ reconcile_assignment
→ STATE_FOUND
→ bind current turn / prepare_assignment
→ reuse existing Slice(s)
→ execute
→ persist Evidence
→ reconcile
→ repair/adapt if authorized
→ claim_done
→ verify
```

Audit/review path:

```text
reconcile_assignment
→ prepare_assignment
→ inspect actual system
→ persist observations
→ compare N vs O
→ findings
→ optional authorized repair
→ re-observe
→ DONE_CLAIMED
```

---

# Repository structure

```text
.
├── src/mangome/
│   ├── service.py            # canonical domain operations / assignment preparation
│   ├── integrity.py          # assurance and authority invariants
│   ├── hygiene.py            # PCH/1 thermal working-set / cognitive homeostasis
│   ├── context.py            # bounded execution context / hard envelope
│   ├── interlingua.py        # UAI/1 compile/decode/render
│   ├── importer.py           # Big-Bang discovery/reconciliation
│   ├── filesystem.py         # deterministic filesystem inventory / evidence freshness
│   ├── operability.py        # client bootstrap, identity/database binding, auto-attach
│   ├── maintenance.py        # deterministic diagnostics/migrations
│   ├── schema.py             # schema evolution / future-version fail-closed
│   ├── mcp_server.py         # MCP v2 surface
│   └── storage/
│       ├── mongo.py          # canonical MongoDB backend / indexes / OCC
│       └── memory.py         # deterministic test backend
├── skill/mangome/
├── src/mangome/skill/
├── .github/skills/mangome/
├── .claude/skills/mangome/
├── docs/
├── examples/
├── tests/
├── pyproject.toml
└── server.py
```

---


## Release-layout integrity

v0.2.2 also hardens the repository/package boundary itself. The executable Python package lives under `src/mangome/`; package modules must not be duplicated into the repository root. Version metadata in `pyproject.toml`, `src/mangome/__init__.py`, and the MCP server must agree. Regression tests fail if shadow copies such as root-level `runtime.py`, `service.py`, `mcp_server.py`, `operability.py`, or duplicate root Skill files appear.

MangoMe setup/doctor code is not a host-network manager. The release guard also rejects source changes that add direct management of resolver/network/firewall surfaces such as `/etc/resolv.conf`, `systemd-resolved`, Netplan, iptables/nftables, or UFW to the MangoMe runtime. Host-network repair is outside MangoMe's normal execution scope.

# Deliberate v0.2.2 non-goals

v0.2.2 does **not**:

- replace MongoDB;
- add an in-memory DAG as a second graph truth;
- add MongoDB Change Stream cache synchronization;
- let workers self-verify;
- expose Slices as normal user-facing workflow;
- create recovery state when `STATE_NOT_FOUND`;
- automatically reinterpret a prompt as a durable Contract contribution;
- let planning artifacts count as execution Evidence;
- guarantee provider-specific token counts from byte budgeting;
- claim that external model dispatch enforcement exists unless the host actually binds to MangoMe authorization.

---

# Current status

**v0.3.2** adds Scoped Recursive Audit/Impact Closure on top of the v0.3.1 Persistent Cognitive Hygiene layer.

The current execution architecture is:

```text
ordinary user intent / recovered WorkIdentity
    ↓
current WorkTurn + immutable NormativeBaseline
    ↓
canonical Project / Family / Spec / Plan / Slice / Evidence graph
    ↓
SRA/1 bounded audit frontier (when auditing)
    ↓
PCH/1 thermal working-set selection
    ↓
existing ContextCompiler hard envelope
    ↓
UAI/1 or normal worker context
    ↓
execution / Evidence / DONE_CLAIMED
    ↓
independent verification
    ↓
VERIFIED / optional ACCEPTED
```

PCH/1 is deliberately projection-only. It does not delete history, alter assurance, infer correctness, or create a second source of truth. `HOT/WARM/COLD` express current cognitive residency; canonical state remains governed by MangoMe's existing truth, authority and verification paths.

## Important current limits

- SRA/1 closes bounded impact scope, not whole-system correctness. A `BOUNDED_FIXPOINT` explicitly means configured depth/object limits prevented further traversal.
- Audit scope expansion never grants additional mutation authority; external code/filesystem enforcement remains a host/runtime responsibility.
- PCH/1 uses an explicit deterministic heuristic policy; its weights and thresholds are an inspectable baseline for evaluation, not a claim of optimal cognitive allocation.
- The current graph-distance calculation is scoped to the Family execution context plus deterministic synthetic relations; it is not yet a host-wide graph navigator.
- Freshness can consume explicit `CURRENT`, `STALE`, `SOURCE_CHANGED`, `ENVIRONMENT_CHANGED`, or `REVALIDATION_REQUIRED` markers, but v0.3.3 does not yet implement a general bitemporal truth-maintenance engine.
- Temperature controls activation only. It cannot promote evidence, change normative authority, verify a Slice, or accept work.
- FJD/1 confidence is advisory worker judgment only. The default 0.80/0.60 thresholds are inspectable operational defaults, not calibrated truth guarantees; high-impact decisions still require review.
- MangoMe can only enforce writes that pass through MangoMe. Direct MongoDB/admin access remains outside the service trust boundary.
- External model dispatch and verifier command execution remain host responsibilities.


---

# Product boundaries

MangoMe deliberately does not:

- treat every prompt as a contract;
- infer verification from a worker's DONE statement;
- automatically recover/replay a dead model session;
- serialize all project work behind a global lock;
- use an LLM for ordinary status calculation;
- silently canonicalize ambiguous discovery;
- infer implementation correctness from filesystem presence alone;
- let compact UAI output directly mutate canonical state;
- make an external reviewer a source of truth;
- promise interchangeable production persistence semantics;
- require Scrum, sprints or story points.

---

# License

Apache License 2.0.

See [`LICENSE`](LICENSE).

---

<p align="center">
  <strong>Agents may forget. The work should not.</strong>
</p>
