# MangoMe

<p align="center">
  <strong>Project truth survives the agent.</strong><br>
  A persistent work-state, contract-family, evidence, and verification MCP for multi-agent systems.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.2-green">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-v2-5b5bd6">
  <img alt="MongoDB" src="https://img.shields.io/badge/store-MongoDB-47A248">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
</p>

---

## Why MangoMe exists

Long-running AI work fails in a very specific way: the work may survive, but the **agent's understanding of the work does not**.

Sessions end. SSH tunnels drop. Token budgets expire. A different model takes over. Contracts are copied into new chats. A worker says “done” although nobody has verified the result. Two agents start changing the same area. A project accumulates base contracts, additions, repairs, reports, evidence and half-finished slices until nobody can state the current truth without reconstructing it from files and memory.

MangoMe moves that truth out of the agent session.

> **Workers are ephemeral executors. MangoMe is durable operational state.**

It is designed to answer questions such as:

- Which project and contract family does this work belong to?
- Which contract contributions are still effective?
- Which slice was started last?
- Which slices are active, blocked, DONE-claimed, verified or accepted?
- Which plan is currently allowed to mutate a slice?
- Which evidence actually supports a gate?
- Which other agents are working in overlapping scope?
- Which approvals are still open?
- What is the current state of the whole project, not just one chat?

---

## The idea

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
Claude / Codex / Luna / dashboards / IntakeGov / CogC / OmniRoute / other MCP hosts
```

MangoMe is not an autonomous project manager and not an agent framework. It is the shared state substrate underneath them.

---

# Core principles

## 1. Work identity is more durable than a session

A prompt, chat, filename or model session is not the identity of the work.

MangoMe gives first-class identity to:

- projects;
- contract families;
- append-only contract contributions;
- specifications;
- plans;
- slices;
- evidence;
- artifacts;
- graph relations;
- approvals;
- model execution receipts.

Every entity receives an immutable internal `entity_id`. Human IDs such as `AVCOS-OSEP-001` remain `declared_id` values and may collide without overwriting history.

## 2. Contracts evolve by addition, not silent replacement

A new contract contribution does not rewrite an old one.

Relations are explicit:

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

It intentionally does **not** pretend that ambiguous prose can always be deterministically merged. The family's current effective specification is the operational requirements view.

## 3. Slices are durable execution addresses

A slice survives the worker that created or executed it.

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

Assurance state is independent:

```text
UNVERIFIED
PARTIAL
VERIFIED
ACCEPTED
REJECTED
```

Therefore this is normal and may remain stable for days or weeks:

```text
execution_state: DONE_CLAIMED
assurance_state: UNVERIFIED
```

## 4. Plan-before-mutate is enforced beyond `start_slice`

A plan is not merely a pre-flight note.

When a slice starts, MangoMe binds it to the active `plan_id`. Subsequent progress updates and `claim_done` must use that same actor + plan binding.

```text
submit_plan
   ↓
start_slice(plan_id=P1)
   ↓
update_slice_progress(plan_id=P1)
   ↓
claim_done(plan_id=P1)
```

A different or missing plan cannot mutate that execution state.

This closes a common loophole in agent workflows where planning is mandatory in theory but execution stops referencing it immediately afterwards.

## 5. Parallel work warns; it does not lock

MangoMe does not turn multi-agent work into a global lock manager.

Active plans declare expected scope and artifacts. Overlap produces advisory traffic information:

```text
COLLISION_WARNING
family_overlap: true
artifact_overlap:
  - src/worker.py
other_actor_ids:
  - claude
action: CONTINUE_ALLOWED
```

The worker observes the warning, re-reads overlapping state where useful, and continues.

## 6. Worker assertions are claims, not truth

`claim_done` records what the worker claims happened.

It does not set `VERIFIED`.

```text
worker
  ↓
DONE_CLAIMED
  ↓
attested evidence
  ↓
acceptance gates
  ↓
independent verifier capability
  ↓
VERIFIED
  ↓
optional owner approval
  ↓
ACCEPTED
```

## 7. Evidence is untrusted by default

New evidence is stored as `UNATTESTED`.

Supported evidence classes include:

```text
CLAIM
TEST_RESULT
RUNTIME_OBSERVATION
STATIC_ANALYSIS
ARTIFACT_CHECK
HUMAN_ATTESTATION
EXTERNAL_REVIEW
OTHER
```

Verification-grade gate PASS requires:

- evidence belonging to the same slice;
- an admissible evidence class;
- PASS verdict;
- trusted verifier/owner attestation.

A worker cannot turn arbitrary prose into verification proof merely by calling it evidence.

## 8. Verification and owner approval use different runtime capabilities

MangoMe v0.1.2 adds two explicit runtime capability boundaries:

```text
MANGOME_VERIFIER_TOKEN
MANGOME_APPROVAL_TOKEN
```

Optional actor allowlists:

```text
MANGOME_VERIFIER_ACTORS
MANGOME_APPROVER_ACTORS
```

The capability token is compared at runtime and is **never persisted** in MangoMe.

For a stronger host boundary without secrets in tool arguments, run a dedicated privileged MangoMe process:

```text
MANGOME_RUNTIME_ROLE=VERIFIER | OWNER
MANGOME_RUNTIME_ACTOR=<trusted actor id>
```

A `WORKER` runtime cannot become a verifier/owner by changing an `actor_id`. A dedicated `VERIFIER`/`OWNER` process authorizes only its configured runtime actor and can keep secrets entirely outside the tool call. OS/process/network access to that privileged endpoint then becomes the control boundary.

The last executing actor is still prohibited from verifying its own DONE claim.

Owner decisions such as `WAIVE_GATE` or `ACCEPT_SLICE` require the separate approval capability.

For local/self-hosted human approval, the CLI can read the capability from the environment so it does not need to be pasted into an agent prompt:

```bash
mangome approve <approval_id> --actor human-owner
mangome reject <approval_id> --actor human-owner
```

> MangoMe is still not a complete IAM platform. Protect capability tokens at the MCP host/runtime boundary and do not expose Streamable HTTP publicly without appropriate authentication and network controls.

## 9. Dependencies can require execution or assurance

A downstream slice may depend on another slice at different levels:

```text
DONE_CLAIMED
VERIFIED
ACCEPTED
```

This prevents an execution claim from accidentally satisfying a dependency that actually requires verification or owner acceptance.

## 10. Project status is deterministic

`status(family_id)` gives a family view.

`project_overview(project_ref)` aggregates all known families, contracts, slices, warnings, active actors and open approvals for a project.

No LLM is required to answer:

- what is active;
- what was started last;
- what is only DONE-claimed;
- what is verified;
- which approvals are open;
- what the current known next slices are.

---

# Big-Bang import and live onboarding

MangoMe supports both operating modes.

### Live / lazy onboarding

An agent handling an existing or new assignment can resolve/create the family, register the relevant contract contribution, preserve existing slices and submit its current plan.

### Big-Bang discovery

`bigbang_scan` can non-destructively inventory configured filesystem roots. v0.1.2 also records optional Git metadata such as:

- repository origin;
- HEAD;
- local branches;
- worktrees;
- recent commits.

Identifier extraction is generic and can be overridden with explicit regex patterns; MangoMe no longer hard-codes organization/project prefixes.

Discovery remains non-destructive:

```text
DISCOVER
  ↓
CONTRACT_CANDIDATE / WORK_STRUCTURE_CANDIDATE / SUPPORTING_ARTIFACT / UNRESOLVED
  ↓
reconcile_bigbang
  ↓
exact match / collision / unresolved
  ↓
explicit semantic admission later
```

`reconcile_bigbang` performs **zero canonical semantic mutations**. It compares discovery against current state and leaves uncertainty visible.

---

# Schema evolution and concurrent state safety

Every first-class document carries:

```text
schema_version
revision
```

v0.1.2 introduces reader-side lazy migration plus an explicit migration registry path:

```bash
mangome migrate          # dry-run
mangome migrate --apply  # persist registered migrations
```

Mutable state updates use revision-aware compare-and-swap where MangoMe performs state transitions. This protects MangoMe's own state from silent concurrent overwrite without locking project work itself.

---

# Context compilation

`compile_execution_context` emits a deterministic bounded package containing current family state, effective contract view, current spec, selected slice, active plan binding, relevant contracts and evidence.

This is intentionally separate from cognitive compression.

A typical composition is:

```text
MangoMe
  ↓ current durable truth
ContextCompiler
  ↓ bounded execution package
CogC
  ↓ capacity-aware compression
worker model
```

---

# Model and cost ledger

Execution receipts can capture:

- model/provider/access-path identity;
- work class;
- input/output tokens;
- raw vs compiled context size;
- execution cost;
- verification cost;
- repair cost;
- human cost;
- outcome.

MangoMe computes:

```text
durable_cost = execution + verification + repair + human
```

and can aggregate cost per verified outcome by model/work class.

The ledger is empirical evidence for routing decisions, not a model popularity score.

---

# Where MangoMe fits

```text
                    REQUEST
                       │
                       ▼
                  IntakeGov
          classify / qualify / route
                       │
                       ▼
                    MangoMe
       identity / contracts / state / evidence
                       │
             ┌─────────┼─────────┐
             │         │         │
             ▼         ▼         ▼
           CogC    OmniRoute   Workers
        context       model    Claude/
       compiler       path     Codex/Luna
             │         │         │
             └─────────┼─────────┘
                       ▼
               claims + evidence
                       │
                       ▼
                  MangoMe
                       │
                       ▼
              verifier / owner
```

MangoMe does not replace IntakeGov, CogC, OmniRoute, Beads, Git, CI or a model provider. It gives those systems a shared durable work identity and state substrate.

---

# MCP tools

The v0.1.2 server exposes:

```text
Readiness
  health

Intake / specification
  intake_request
  create_spec

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
  set_gate
  set_gate_controlled       # v0.1.1 compatibility alias
  verify_slice
  request_override
  approve_override
  reject_override
  list_approvals
  accept_slice

Read / explanation
  status
  project_overview
  effective_family_view
  read_context
  compile_execution_context
  graph

Economics
  register_model
  record_execution_receipt
  model_stats

Import / maintenance
  bigbang_scan
  reconcile_bigbang
  refresh_views
  maintenance_diagnose
  migrate_schema
```

---

# Installation

Python 3.10+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For an in-memory development backend:

```bash
export MANGOME_BACKEND=memory
mangome-mcp
```

For MongoDB:

```bash
export MANGOME_BACKEND=mongo
export MANGOME_MONGODB_URI='mongodb://127.0.0.1:27017'
export MANGOME_DATABASE='mangome'
mangome-mcp
```

Configure either dedicated runtime roles (preferred when you can separate endpoints):

```bash
export MANGOME_RUNTIME_ROLE='VERIFIER'
export MANGOME_RUNTIME_ACTOR='verifier-service'
# run a verifier-scoped MangoMe process behind host/network controls
```

Or use capability tokens for a shared/self-hosted process:

```bash
export MANGOME_VERIFIER_TOKEN='runtime-secret'
export MANGOME_VERIFIER_ACTORS='verifier-service,codex-verifier'

export MANGOME_APPROVAL_TOKEN='owner-runtime-secret'
export MANGOME_APPROVER_ACTORS='human-owner'
```

Do not place these values in contracts, prompts, committed configuration or MangoMe evidence.

The default MCP transport is stdio.

Streamable HTTP:

```bash
export MANGOME_MCP_TRANSPORT=streamable-http
export MANGOME_MCP_HOST=127.0.0.1
export MANGOME_MCP_PORT=8000
mangome-mcp
```

The repository exposes `server.py` for the official MCP Python SDK v2 CLI:

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

GitHub-discoverable mirror:

```text
.github/skills/mangome/SKILL.md
```

The Skill describes how agents must behave. The MCP owns persistent state and domain invariants.

---

# Example lifecycle

```text
intake_request
→ resolve / create_family
→ register_contract
→ create_spec
→ submit_plan
→ start_slice(plan_id)
→ update_slice_progress(plan_id)
→ submit_evidence
→ attest_evidence
→ claim_done(plan_id)
→ set_gate(PASS)
→ verify_slice(verifier capability)
→ optional ACCEPT_SLICE approval
→ accept_slice
→ close_plan
→ status / project_overview
```

A dead model session does not erase this chain.

---

# Repository structure

```text
.
├── .github/
│   ├── skills/mangome/SKILL.md
│   └── workflows/ci.yml
├── docs/
├── examples/
├── skill/mangome/SKILL.md
├── src/mangome/
│   ├── authority.py
│   ├── context.py
│   ├── importer.py
│   ├── integrity.py
│   ├── maintenance.py
│   ├── mcp_server.py
│   ├── models.py
│   ├── schema.py
│   ├── service.py
│   └── storage/
├── tests/
├── pyproject.toml
└── server.py
```

---

# Testing

The suite covers:

- plan-before-mutate and persistent plan binding;
- DONE vs verification separation;
- capability-backed verifier and owner approval boundaries;
- attested evidence requirements;
- gate schema/audit metadata;
- advisory collision warnings;
- declared-contract-ID collisions;
- effective family supersession/conflict views;
- project-level status aggregation;
- dependency assurance levels;
- optimistic revision conflicts;
- schema migration;
- generic Big-Bang discovery and reconciliation;
- MongoDB persistence;
- MCP v2 tool discovery.

GitHub Actions runs Python 3.10–3.12 with MongoDB 7 and the real MCP dependency.

---

# What MangoMe deliberately does not do

- It does not treat every prompt as a contract.
- It does not use agent memory as canonical truth.
- It does not block work merely because another agent overlaps.
- It does not automatically replay/recover a dead model session.
- It does not accept a worker's DONE statement as verification.
- It does not accept un-attested evidence as verification proof.
- It does not semantically merge ambiguous contract prose by guesswork.
- It does not let Big-Bang discovery silently canonicalize uncertain relationships.
- It does not require Git.
- It does not impose Scrum, sprints or story points.
- It is not yet a complete identity/IAM or internet-facing authorization platform.

---

# Roadmap

## 0.1.x — Durable truth foundation

- [x] Contract families and append-only contributions
- [x] Specifications and persistent slices
- [x] Plan-before-mutate
- [x] Persistent plan binding during execution
- [x] Execution vs assurance state
- [x] Evidence attestation
- [x] Separate verifier / owner capabilities
- [x] Advisory collision detection
- [x] Effective family view
- [x] Project overview
- [x] Big-Bang filesystem + Git discovery
- [x] Non-destructive reconciliation
- [x] Schema-version migration path
- [x] Revision/CAS state protection
- [x] MCP v2 and MongoDB integration tests

## Next

- [ ] Transport-native identity / scoped MCP authorization adapters
- [ ] Change-stream or scheduled materialized-view daemon
- [ ] Richer Git / repository artifact adapters
- [ ] OpenSpec / Beads adapters
- [ ] IntakeGov automatic handoff adapter
- [ ] CogC execution-package adapter
- [ ] OmniRoute automatic execution receipts
- [ ] External reviewer reconciliation adapter
- [ ] Provenance alignment with W3C PROV / OpenTelemetry conventions
- [ ] Dashboard / operator UI

---

# The long-term goal

The long-term idea is simple:

> AI systems should not depend on whichever model currently remembers the project best.

A project should have a durable, inspectable and evidence-aware operational state that survives model changes, session loss, parallel workers and years of contract evolution.

MangoMe is that layer.

---

## License

Apache License 2.0.

See [`LICENSE`](LICENSE).

---

<p align="center">
  <strong>Read the truth. Declare the plan. Persist the state. Verify the outcome.</strong>
</p>
