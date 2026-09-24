# MangoMe

<p align="center">
  <img src="docs/mangome-banner.png" alt="MangoMe — persistent multi-agent operational memory" width="100%">
</p>

<p align="center">
  <strong>Governed project state survives the agent.</strong><br>
  Canonical operational memory for long-lived multi-agent work.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.7-green">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="MongoDB" src="https://img.shields.io/badge/canonical%20store-MongoDB-47A248">
  <img alt="UAI" src="https://img.shields.io/badge/semantic%20transport-UAI%2F1-6f42c1">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
</p>

---

## MangoMe is not just a state machine

MangoMe is the **canonical operational memory** underneath long-running AI work.

It combines several responsibilities that are usually scattered across chats, repositories, task trackers, reports and agent memory:

```text
DOCUMENT STORE
    +
WORK GRAPH
    +
STATE MACHINE
    +
CONTRACT HISTORY
    +
EVIDENCE / PROVENANCE LEDGER
    +
EXECUTION ECONOMICS
    +
DETERMINISTIC CONTEXT COMPILER
    +
COMPACT SEMANTIC TRANSPORT
```

That distinction matters.

A state machine can tell you that a task moved from `ACTIVE` to `DONE`.

MangoMe can tell you:

- what request caused the work;
- which project and contract family own it;
- which contract contributions remain effective;
- which specification currently governs it;
- which plan was declared before mutation;
- which persistent slice is being executed;
- which artifacts and graph relations belong to the work;
- what a worker merely claimed;
- what evidence exists;
- whether that evidence was actually attested;
- what has been verified by a separately authorized verifier;
- what an authorized approver explicitly accepted;
- which model identity was recorded for an execution, when an Execution Receipt exists;
- what execution, verification and repair costs were recorded;
- and what bounded context MangoMe compiled for a worker.

> **Workers are ephemeral executors. MangoMe is the canonical operational record within its governed scope.**

Sessions may disappear. Models may change. Agents may hand work to one another. The work does not have to reconstruct itself from chat history.

---

# Why MangoMe exists

Long-running AI projects tend to fail in a very specific way: the artifacts survive, but the **shared understanding of the work does not**.

A Claude Code session ends. Codex takes over. A contract has received two additions and a repair. One worker says “done”. Another agent starts from an older document. A test result exists somewhere in a report. Two workers touch the same area. The next model receives 30,000 tokens of history and still has to infer what is current.

MangoMe moves that problem out of the prompt.

```text
REQUEST
   │
   ▼
Intake / classification
   │
   ▼
Project + Contract Family
   │
   ├── BASE
   ├── ADDITION
   ├── AMENDMENT
   ├── REPAIR
   └── ... append-only contributions
   │
   ▼
Effective Specification
   │
   ▼
PLAN BEFORE MUTATE
   │
   ▼
Persistent Slices + Dependencies
   │
   ▼
Execution State + Claims + Evidence
   │
   ├── DONE_CLAIMED
   │       ≠
   └── VERIFIED / ACCEPTED
           │
           ▼
Deterministic Family / Project Views
           │
           ▼
Canonical MangoMe Context
           │
           ▼
UAI/1 compact semantic transport
           │
           ▼
CogC / Claude / Codex / Luna / other workers
```

MangoMe is not an autonomous project manager and not an agent framework. It is the durable substrate underneath them.

---

# What MangoMe knows

MangoMe gives first-class identity to:

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

Human identifiers such as `AVCOS-OSEP-001` remain `declared_id` values. They can collide without silently overwriting history.

The result is deliberately richer than a todo list.

---

# Core invariants

## 1. Work identity is more durable than a session

A chat, prompt, branch or model invocation is not the identity of the work.

A persistent Work Identity survives all of them.

## 2. Contract evolution is append-only

A new contribution does not silently rewrite an earlier one.

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

`effective_family_view` determines the currently active contribution set from confirmed supersession and exposes conflicts and suggested relations.

Ambiguous prose is not magically merged. The current effective specification remains the operational requirements view.

## 3. Slices are durable execution addresses

Execution and assurance are separate dimensions.

Execution state:

```text
PLANNED
STARTED
ACTIVE
PAUSED
BLOCKED
DONE_CLAIMED
CANCELLED
```

Assurance state:

```text
UNVERIFIED
PARTIAL
VERIFIED
ACCEPTED
REJECTED
```

This is a normal, stable state:

```text
DONE_CLAIMED / UNVERIFIED
```

It can remain that way for hours, days or weeks. MangoMe never converts inactivity into completion.

## 4. Plan-before-mutate is real enforcement

A plan is not just a note.

When a slice starts, MangoMe binds it to the active `plan_id`.

Subsequent progress mutations and the worker's DONE claim must stay on that binding.

```text
submit_plan
    ↓
start_slice(plan_id=P)
    ↓
update_slice_progress(plan_id=P)
    ↓
claim_done(plan_id=P)
```

A worker cannot start under one plan and quietly finish under another.

## 5. DONE is only a worker claim

```text
worker: "done"
        ↓
DONE_CLAIMED
        ↓
attested evidence + gates
        ↓
independent verifier
        ↓
VERIFIED
        ↓
optional authorized acceptance
        ↓
ACCEPTED
```

`DONE_CLAIMED != VERIFIED` is one of MangoMe's core invariants.

## 6. Evidence is not automatically proof

New evidence begins as `UNATTESTED`.

Verification-grade PASS evidence must be:

- attached to the correct slice;
- from an admissible evidence class;
- PASS-valued;
- attested by a verifier/owner capability.

From v0.1.7, final `verify_slice` also requires **independent AV/1 observed PASS Evidence** for every PASS gate, or for the explicit proof set of a gateless Slice. Merely attesting a worker-authored PASS claim is no longer enough to reach `VERIFIED`.

A worker cannot simply store `{result: "PASS"}` and thereby verify itself.

## 7. Parallel work warns instead of locking

MangoMe deliberately does not serialize all agent work.

Overlapping plans produce advisory collision information:

```text
family_overlap: true
artifact_overlap: [src/runtime.py]
other_actor_ids: [claude]
action: CONTINUE_ALLOWED
```

The workers remain free to continue, re-read or coordinate.

MangoMe protects **its own canonical writes** with revision / compare-and-swap semantics, while project work remains parallel.

---

# Why MangoMe is intentionally rich

A common reaction to MangoMe is that it has many first-class entities and states.

That is deliberate.

The problem MangoMe is solving is not:

> “How do I remember one task for one chat?”

It is:

> “How do many transient workers share one durable, inspectable and verifiable understanding of long-lived work?”

Reducing the canonical model until it resembles a todo list would make the interface look simpler while forcing every new agent to reconstruct the missing meaning again.

MangoMe chooses the opposite trade-off:

> **Rich canonical state, simple execution surfaces.**

The complexity belongs in the durable system, not repeatedly inside expensive model context.

---

# Bureaucracy is an interface problem, not a truth-model problem

MangoMe does not require every user or worker to manually operate every entity.

v0.1.3 introduces `begin_work`, a convenience surface that composes the normal path:

```text
intake_request
→ current effective spec
→ submit_plan
→ materialize/reuse slice
→ collision check
→ start_slice
```

into one call.

It does **not** create a second lightweight state model and it does not bypass any invariant.

The same Request, Plan and Slice are still persisted.

```text
simple interface ≠ simple data model
```

Longer term, IntakeGov is the natural place to decide how much workflow ceremony a request deserves. MangoMe should remain the canonical operational record, while IntakeGov decides the proportional execution route.

For a small bounded change, a worker can use a narrow surface.

For high-risk or multi-agent work, the full contract/evidence/approval model remains available.

---

# MongoDB is a design decision, not an accidental dependency

MangoMe's production truth is intentionally MongoDB.

MangoMe stores evolving documents with nested structures and heterogeneous payloads:

- contract contributions;
- versioned specifications;
- slices and gates;
- evidence classes and provenance;
- artifacts and bindings;
- typed graph relations;
- execution receipts;
- materialized views;
- schema versions and revisions.

This is not merely a relational task table.

MongoDB fits the core architecture because MangoMe is a **document-state system** as much as it is a state machine.

The in-memory backend exists for deterministic tests and local development. MangoMe deliberately does not promise several interchangeable canonical production stores with subtly different semantics.

```text
Production canonical persistence = MongoDB
```

A SQLite or filesystem backend could make a tiny deployment easier, but it would also introduce a second production truth model, additional migration behavior and another concurrency contract. That is outside the current product direction.

---

# UAI/1 — compact semantic transport

v0.1.3 adds a compact intermediate language between MangoMe and expensive workers.

The key rule is:

> **MangoMe does not compress canonical truth. It compiles a disposable execution projection of that truth for transport.**

The pipeline becomes:

```text
IntakeGov
"What kind of work is this?"
        │
        ▼
MangoMe
"What is durably true?"
        │
        ▼
UAI/1
"Represent that truth compactly and unambiguously."
        │
        ▼
CogC
"How much of it does this particular worker need?"
        │
        ▼
Claude / Codex / Luna / other worker
        │
        ▼
UAI/1R structured result
        │
        ├──────────────► deterministic human renderer
        │
        └──────────────► normal MangoMe mutation / evidence / verification tools
```

UAI/1 in this repository is a **MangoMe semantic transport profile**, not a claim that an external industry standard already exists.

## What is compacted

A normal execution context contains named dictionaries, repeated field names, timestamps and rich state documents.

UAI/1 compiles only the semantic projection needed for execution:

- family identity;
- execution/assurance state;
- effective contracts;
- current specification;
- current slice and active plan;
- dependencies;
- gates;
- relevant evidence;
- core MangoMe invariants.

It then uses a versioned compact tuple representation.

Example shape:

```json
{"v":"UAI/1","p":"mangome-work","h":"...","f":["...","FAMILY","Title",[]],"s":["ACTIVE","UNVERIFIED",null,["..."],null,null,[],["claude"],[]],"ef":[["..."],[],false],"sp":["...",3,"objective",[],[],["gate"],[]],"w":["...","S1","Slice","objective","ACTIVE","UNVERIFIED","...",1,3,null,[],[]],"c":[],"e":[],"r":["DONE_CLAIMED!=VERIFIED","MUTATE_REQUIRES_ACTIVE_PLAN"]}
```

## Semantic hash / stale-context protection

Every UAI/1 context packet contains a SHA-256 semantic hash.

```text
canonical execution projection
        ↓
canonical serialization
        ↓
SHA-256
        ↓
UAI/1.h
```

If the packet is altered, expansion fails.

A worker result can also be bound to the exact context hash it received. Results produced against stale or different context can therefore be rejected before they are considered.

## Round-trip

`expand_uai_context` reconstructs the defined semantic projection and verifies its hash.

The guarantee is intentionally scoped:

```text
semantic execution projection
        ↓ encode
UAI/1
        ↓ decode
same semantic execution projection
```

MangoMe does not claim that arbitrary natural-language history can be losslessly reconstructed from a compact packet. Historical source documents remain in MongoDB/artifact storage.

## Compact worker output

Workers can return `UAI/1R` rather than spending tokens on administrative prose.

Example:

```json
{
  "v":"UAI/1R",
  "h":"<context-hash>",
  "st":"SUCCESS",
  "a":[
    ["P",2,3],
    ["A","interlingua.py","SOURCE","git","src/mangome/interlingua.py"],
    ["E","ROUND_TRIP","TEST_RESULT","pytest","PASS"],
    ["D","implementation complete"]
  ]
}
```

Action codes:

```text
P  progress
A  artifact
E  evidence
D  DONE claim
N  discovered/new slice proposal
B  blocker
```

The decoder expands these into explicit structured actions.

Crucially:

> **Decoded UAI output never directly mutates MangoMe.**

It remains a proposal and must pass through the normal plan, evidence, verification and approval APIs.

## Human-readable rendering

`render_uai_result` deterministically renders UAI/1R into English or German.

For example:

```text
Status: Erfolgreich.
Fortschritt: Schritt 2 von 3.
Artefakt: interlingua.py (SOURCE) unter src/mangome/interlingua.py.
Evidence: ROUND_TRIP aus pytest mit Ergebnis PASS.
Der Worker meldet DONE_CLAIMED; dies ist noch keine Verifikation.
```

This allows an expensive model to return structured semantics while a cheap/deterministic component produces the administrative human output.

## Measuring whether it is actually cheaper

The compiler reports character-level and clearly-labelled heuristic token estimates for immediate inspection.

A representative local v0.1.3 demo context produced:

```text
raw compiled context: 3,819 chars
UAI/1 wire:             729 chars
reduction:              80.91%
```

That is a demonstration, **not a provider-token benchmark**.

Actual economics belong in Execution Receipts. v0.1.3 can persist:

```text
context_tokens_raw
context_tokens_compiled
context_tokens_interlingua
output_tokens_interlingua
interlingua_version
```

This allows empirical comparison of cost per verified outcome rather than marketing claims about token savings.

---

# Context architecture

MangoMe now has a clean separation between truth, representation and worker capacity:

```text
MangoMe
canonical documents + current operational truth
        │
        ▼
ContextCompiler
bounded execution semantics
        │
        ▼
UAI/1
compact versioned representation
        │
        ▼
CogC (optional)
capacity-aware selection / further compaction
        │
        ▼
Worker
```

This architecture is intended to let expensive models avoid repeatedly consuming the full historical contract/document corpus merely to recover the current position.

The richer and better maintained MangoMe becomes as a document store, the **less reconstruction work a worker should usually have to perform**.

---

# Deterministic status instead of model opinion

MangoMe calculates family/project status programmatically.

A dashboard or worker does not need an LLM to answer:

- which slice started last;
- which slices are active;
- which slices only claim completion;
- which slices are verified;
- what can execute next;
- which plans are active;
- which approvals remain open;
- whether effective contracts conflict.

Use:

```text
status
project_overview
effective_family_view
graph
```

---

# Big-Bang discovery without invented truth

Existing organizations already have contracts, reports, branches, worktrees and half-finished work.

`bigbang_scan` performs non-destructive discovery across configured filesystem roots and optional Git metadata.

It can extract:

- generic/configurable declared IDs;
- explicit slice/phase/workstream markers;
- hashes and physical artifact locations;
- Git origin/HEAD;
- branches;
- worktrees;
- recent commits.

`reconcile_bigbang` compares those discoveries against canonical MangoMe state.

It produces matches, collisions and unresolved candidates.

It does **not** convert ambiguity into truth automatically.

---

# Deterministic filesystem inventory and reproducible Evidence bindings

MangoMe 0.1.5 introduced a cheap deterministic filesystem inventory for targeted legacy revalidation. v0.1.6 builds on that substrate with **RB/1 reproducible Evidence bindings**. The goal is still conservative: bind already-admissible Evidence to concrete execution context without pretending that a hash or an old audit proves semantic correctness.

```text
filesystem_scan
    ↓
SOURCE / TEST / CONTRACT / WORKFLOW / CONFIG / REPORT inventory
    ↓
filesystem_references(<declared-id>)
    ↓
small candidate set
    ↓
build_reproduction_binding
    ↓
Evidence.payload.reproduction (RB/1)
    ↓
evidence_freshness
```

The filesystem inventory still records stable path identity, SHA-256 where bounded, size/mtime, lexical declared-ID references and nearest Git root/HEAD. Repeated scans reuse persisted inventory state and avoid rewriting unchanged records, but the current scanner still walks explicitly supplied roots on each scan; it is not yet a Git-delta scanner, filesystem watcher, or host-wide auto-discovery daemon.

## RB/1

`build_reproduction_binding` does **not** run a test or shell command. It records the command and caller-supplied exit code, hashes the declared relevant input files, captures the current/provided Git commit, optionally binds an output Artifact, and creates a deterministic `fingerprint`.

Representative shape:

```json
{
  "version": "RB/1",
  "command": "pytest -q tests/test_policy.py",
  "cwd": "/opt/app",
  "exit_code": 0,
  "git_commit": "<commit>",
  "input_bindings": [
    {"path": "/opt/app/src/policy.py", "sha256": "<sha256>", "role": "SOURCE"},
    {"path": "/opt/app/tests/test_policy.py", "sha256": "<sha256>", "role": "TEST"}
  ],
  "output_artifact_id": null,
  "stdout_sha256": null,
  "stderr_sha256": null,
  "environment_names": ["CI", "PYTHONPATH"],
  "fingerprint": "<sha256>"
}
```

Environment **values are never part of RB/1**. The helper accepts names only and rejects names that look like password/token/secret/key credentials. Dependency or configuration state should be represented by explicit hashed input files such as lockfiles or config files, not by copying secrets into Evidence.

`evidence_freshness` remains deliberately narrow. For RB/1 Evidence it checks the stored fingerprint, the bound input hashes, optional output Artifact state, and the Git context where available. It can surface reason codes such as `SOURCE_CHANGED`, `TEST_CHANGED`, `OUTPUT_MISSING`, `COMMIT_CHANGED`, or `FINGERPRINT_MISMATCH`.

A different Git HEAD with unchanged bound inputs returns conservative `UNKNOWN`, not automatic `STALE` or `REUSABLE`: a commit change alone does not prove that a relevant dependency changed, but it also means exact execution context has not been re-established.

`REUSABLE` still has a deliberately narrow meaning:

> **The Evidence was already admissible, attested and PASS-valued, its RB/1 fingerprint is intact, and all declared live-checkable bindings remain current.**

It does **not** mean that MangoMe re-ran the command, re-proved the requirement, inferred semantic equivalence between requirements, or established that Evidence from one Slice automatically satisfies another Slice. A current revalidation still requires executing the relevant check and recording new Evidence when the binding is stale or insufficient.

Legacy `payload.filesystem_bindings` from v0.1.5 remain supported. Old AI/audit prose remains non-reusable `CLAIM` material unless it independently satisfies the normal Evidence and attestation rules. Freshness never creates `VERIFIED` or `ACCEPTED`, and MangoMe does not fabricate historical Slice provenance.

See [`docs/filesystem-proof-reuse.md`](docs/filesystem-proof-reuse.md).

---

# AV/1 adversarial completion verification

v0.1.7 hardens the transition from `DONE_CLAIMED` to `VERIFIED` without adding a new assurance state machine. The design treats a completion report and worker-authored Evidence as claims to inspect, not as independent proof.

```text
DONE_CLAIMED
    ↓
completion_review
    ↓
persisted claims + plan/spec obligations + optional observed change set
    ↓
verifier/host reruns or inspects the load-bearing check
    ↓
submit_verification_observation (AV/1)
    ↓
attested observed Evidence
    ↓
existing gate + verify_slice rules
    ↓
VERIFIED
```

`completion_review` is deterministic. It returns the persisted DONE/other claims verbatim, the Plan's expected scope/artifacts, current Specification acceptance criteria and required Evidence, existing independent observations, and an optional scope review over verifier-supplied changed paths. Changed test files produce `TEST_CHANGE_REVIEW_REQUIRED`; out-of-scope files produce `SCOPE_DEVIATION`. These are review signals, not accusations or automatic failures.

`submit_verification_observation` requires a verifier capability and rejects the last executing actor. AV/1 observation states are `PASS`, `FAIL`, and `UNVERIFIABLE`; the latter maps to `EvidenceVerdict.UNKNOWN`, never a guessed PASS. A `REPLAY` observation must carry an intact RB/1 reproduction binding. MangoMe still does **not** execute shell commands itself: the authorized verifier/host performs the check and records what was actually observed.

Final `verify_slice` now requires at least one independent AV/1 observed PASS Evidence item for each PASS gate. Gateless Slices require an independent AV/1 observed PASS in the explicit proof set. Existing pre-v0.1.7 Evidence remains readable and auditable, but worker Evidence plus later attestation alone no longer satisfies this stronger final-verification rule.
Explicitly `WAIVED` gates remain the governed exception: an approved `WAIVE_GATE` decision can remove that gate's Evidence requirement, exactly as before.

This mechanism deliberately does not parse free-text DONE summaries into invented structured truth, infer misconduct from changed tests, or create Fable-style parallel verdict states. MangoMe keeps its existing `UNVERIFIED / PARTIAL / VERIFIED / ACCEPTED / REJECTED` assurance model.

See [`docs/adversarial-verification.md`](docs/adversarial-verification.md).

---

# MCP tools

The v0.1.7 MCP surface includes:

```text
Intake / specification
  intake_request
  create_spec
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

Economics
  register_model
  record_execution_receipt
  model_stats

Discovery / maintenance
  bigbang_scan
  reconcile_bigbang
  filesystem_scan
  filesystem_references
  build_reproduction_binding
  evidence_freshness
  refresh_views
  maintenance_diagnose
  migrate_schema
  health
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

The default MCP transport is stdio.

Streamable HTTP can be enabled with:

```bash
export MANGOME_MCP_TRANSPORT=streamable-http
export MANGOME_MCP_HOST=127.0.0.1
export MANGOME_MCP_PORT=8000
mangome-mcp
```

With the current MCP Python SDK v2 CLI:

```bash
mcp dev server.py
mcp run server.py --transport streamable-http
```

---

# Agent Skill

Canonical skill:

```text
skill/mangome/SKILL.md
```

The current public repository exposes this canonical Skill path. A `.github/skills/...` mirror is not required for MangoMe runtime behavior.

The Skill describes how a worker must behave.

The MCP owns state and enforces the invariants.

---

# Typical lifecycle

Full explicit path:

```text
intake_request
→ resolve
→ read_context / effective_family_view
→ create/reuse spec
→ submit_plan
→ start_slice
→ update progress
→ attach artifacts / evidence
→ claim_done
→ attest evidence
→ pass gates
→ verify_slice
→ optional authorized acceptance
→ record_execution_receipt
```

Bounded convenience path for an existing family/spec:

```text
begin_work
→ update progress
→ claim_done
→ normal assurance path
```

Compact worker path:

```text
compile_uai_context
→ worker receives UAI/1
→ worker returns UAI/1R
→ decode_uai_result
→ optional render_uai_result
→ normal MangoMe tools apply validated actions
```

---

# Design trade-offs — explicitly accepted

## “There are many entities.”

Correct.

MangoMe optimizes for durable multi-agent state, provenance and assurance, not for having the smallest possible schema.

The interface can be simplified without deleting semantics from the source of truth.

## “MongoDB is heavier than SQLite.”

Correct.

MangoMe is a document store plus work graph plus state system. MongoDB is the canonical production backend by design.

The project does not currently pursue interchangeable production persistence backends.

## “Agents may not call every tool correctly.”

Correct, which is why MangoMe increasingly provides composed surfaces (`begin_work`), Agent Skills and deterministic enforcement rather than relying only on prompt discipline.

The intended integration is that runtimes/IntakeGov invoke the appropriate MangoMe path automatically where possible.

## “Strong governance can become bureaucracy.”

Correct — this is the trade-off MangoMe actively addresses.

The answer is proportional invocation and composed tools, not deleting the evidence, contract and state model required by difficult work.

## “Why not federation / enterprise cross-server sharing?”

Because it is not the current product.

MangoMe deliberately targets one canonical deployment with one canonical MongoDB truth serving many projects, models, agents and humans.

Cross-organization federation, key exchange, portable trust domains and server-independent shared truth are outside the current scope.

That boundary is intentional.

---

# Product boundaries

MangoMe deliberately does not:

- treat every prompt as a contract;
- infer verification from a worker's DONE statement;
- automatically recover/replay a dead agent session;
- serialize all parallel project work behind locks;
- use an LLM for ordinary status calculation;
- silently canonicalize ambiguous Big-Bang discoveries;
- infer implementation correctness from filesystem presence alone;
- treat `evidence_freshness=REUSABLE` as new verification or acceptance;
- infer cross-slice semantic proof equivalence automatically;
- fabricate historical Slices for legacy work;
- automatically discover every project/root on a host;
- let compact UAI output directly mutate canonical state;
- make external reviewers a source of truth;
- promise interchangeable production persistence semantics;
- implement cross-organization federation or Enterprise trust exchange;
- require Scrum, sprints or story points.

---

# Repository structure

```text
.
├── src/mangome/
│   ├── service.py            # canonical domain operations
│   ├── integrity.py          # assurance/authority invariants
│   ├── context.py            # bounded execution context
│   ├── interlingua.py        # UAI/1 compile/decode/render
│   ├── importer.py           # Big-Bang discovery/reconciliation
│   ├── filesystem.py         # deterministic filesystem inventory/evidence freshness
│   ├── maintenance.py        # deterministic diagnostics/migrations
│   ├── schema.py             # schema evolution
│   ├── mcp_server.py         # MCP v2 surface
│   └── storage/              # MongoDB + in-memory test backend
├── skill/mangome/
├── docs/
├── examples/
├── tests/
├── pyproject.toml
└── server.py
```

---

# Current status

v0.1.7 adds AV/1 adversarial completion verification on top of RB/1 reproducible Evidence bindings. It does not add a new Proof entity or a parallel verdict lifecycle. Instead, it strengthens the existing `DONE_CLAIMED → Evidence → VERIFIED` path so worker-authored PASS material cannot become final verification merely because a verifier later attests it.

The current architecture is:

```text
IntakeGov
    ↓
MangoMe canonical operational memory
    ↓
UAI/1 semantic transport
    ↓
Agent execution
    ↓
DONE_CLAIMED + worker Evidence
    ↓
AV/1 independent observation
    ↓
RB/1 binding where replayable
    ↓
Verification
    ↓
Authorized acceptance
```

Important current limits:

- MangoMe does not execute verification commands itself. AV/1 records observations made by an authorized verifier/host; runtime isolation and command execution remain external responsibilities.
- `completion_review` returns persisted free-text claims verbatim. It does not pretend to perform deterministic semantic claim extraction from prose.
- Scope deviations and changed tests are adversarial review signals, not automatic evidence of fraud or incorrectness.
- AV/1 strengthens provenance/independence of observed Evidence but still does not prove that every requirement is semantically covered unless the relevant gates/specification make that coverage explicit.
- RB/1 freshness still does not create Verification or Acceptance and does not infer cross-Slice semantic proof equivalence.
- UAI/1's published `80.91%` figure remains a **character reduction in one representative demo**, not a universal provider-token saving.
- Filesystem scans require explicit roots and still walk the configured scope on each scan.
- The public implementation does not reconstruct missing historical Slices or certify old AI audits as truth.
- Execution-cost and token economics are only as complete as the Execution Receipts supplied by the surrounding runtime.
- The v0.1.7 packaging test result is recorded in `TEST_REPORT.md`; skipped optional integration checks are not represented as production validation.

The next phase is empirical evaluation: adversarial false-DONE fixtures, worker-vs-verifier separation tests, test-weakening/scope-deviation traps, and then RAW vs compiled vs UAI cost measurement per verified outcome.

---

# Acknowledgements

The AV/1 adversarial-completion design was informed by [`Sahir619/fable-method`](https://github.com/Sahir619/fable-method), especially the `fable-judge` pattern of treating completion reports as claims, independently re-observing claimed checks, inspecting actual changes, and looking for weakened verification. MangoMe reimplements these ideas inside its own Evidence/Verification/Acceptance model; it does not incorporate Fable's verdict state machine or bundle its fixtures. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

## License

Apache License 2.0.

See [`LICENSE`](LICENSE).

---

<p align="center">
  <strong>Agents may forget. The work should not.</strong>
</p>
