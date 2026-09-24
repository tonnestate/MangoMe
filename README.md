# MangoMe

<p align="center">
  <strong>Move project truth out of the agent session.</strong><br>
  A persistent work-state graph and document-state machine for durable multi-agent execution.
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/status-experimental-orange">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.1-green">
  <img alt="MCP Server" src="https://img.shields.io/badge/MCP-server-blueviolet">
  <img alt="Agent Skill" src="https://img.shields.io/badge/agent-skill-purple">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="MongoDB" src="https://img.shields.io/badge/MongoDB-document%20state-47A248">
</p>

---

> [!WARNING]
> **EXPERIMENTAL — v0.1.1**  
> MangoMe is an early work-state MCP for multi-agent systems. The current release implements the core state model, contract families, append-only contract contributions, specifications, plans, slices, claims, evidence, deterministic status projections, advisory collision detection, Big-Bang discovery, context compilation, and model/cost receipts. It is **not yet a production authorization boundary** for untrusted remote clients.

## Why MangoMe exists

Long-running agent projects fail in a surprisingly mundane way: **the work survives longer than the session that was doing it**.

A Claude session ends.  
A Codex run loses context.  
An SSH tunnel dies.  
A token budget is exhausted.  
A different model continues tomorrow.  
Contracts, reports, Git branches, status files and implementation artifacts live in different places.

The next worker then has to reconstruct the project from fragments and often reaches a different conclusion about:

- which contract is canonical;
- which contracts belong together;
- which slices already exist;
- which slice was started last;
- what is currently active;
- what a worker only *claimed* to have finished;
- what has actually been verified;
- which artifacts and evidence support that state;
- which other agents are working in the same area.

**MangoMe exists to make that reconstruction unnecessary.**

The agent session is temporary. The work identity and work state are durable.

---

## The idea

```text
REQUEST
   │
   ▼
Intake / classification
   │
   ▼
PROJECT + CONTRACT FAMILY
   │
   ├── append-only contract contributions
   ├── specification
   ├── artifacts + graph relations
   └── existing slices
   │
   ▼
MANDATORY PLAN
   │
   ├── intended slices
   ├── expected artifacts / scope
   ├── estimate
   └── acceptance expectations
   │
   ▼
EXECUTION
   │
   ├── persistent slice state
   ├── advisory collision warnings
   ├── claims
   └── evidence
   │
   ▼
DONE_CLAIMED
   │
   ├── stable state
   └── NOT equivalent to VERIFIED
   │
   ▼
VERIFICATION / ACCEPTANCE
   │
   ▼
MATERIALIZED CURRENT STATE
   │
   ├── Claude
   ├── Codex
   ├── Luna
   ├── IntakeGov
   ├── CogC
   ├── OmniRoute
   └── dashboards / operators
```

The central rule is simple:

> **Workers may report what they did. MangoMe owns the durable operational state.**

---

# Core principles

## 1. Read is open; execution starts with a plan

Every agent may read MangoMe state and is expected to resolve the existing project/family context before productive work.

Before execution begins, the worker records a plan describing what it intends to change, which slices it will work on, expected scope/artifacts, acceptance expectations, and an estimate when meaningful.

MangoMe is not intended to make agents wait for locks or a central dispatcher.

## 2. Slices are durable execution addresses

Slices are first-class objects, not disposable checklist text.

Existing slices are preserved when a contract already defines phases, slices or workstreams. MangoMe records at least:

```text
last_started_slice_id
active_slice_ids
last_done_claimed_slice_id
last_verified_slice_id
next_known_slice_ids
current_step
total_steps
blocker
last_activity_at
```

This lets a new worker determine the last known project position without trusting another model's chat memory.

## 3. DONE is a claim

Execution state and assurance state are independent.

Execution:

```text
PLANNED
STARTED
ACTIVE
PAUSED
BLOCKED
DONE_CLAIMED
CANCELLED
```

Assurance:

```text
UNVERIFIED
PARTIAL
VERIFIED
ACCEPTED
REJECTED
```

Therefore this is a normal and potentially long-lived state:

```text
DONE_CLAIMED / UNVERIFIED
```

A worker saying "done" is useful state. It is not proof.

## 4. Contracts are append-only contributions

A new contract does not silently overwrite an older contract.

A durable family can contain:

```text
BASE
ADDITION
AMENDMENT
EXTENSION
REPAIR
RECOVERY
EVALUATION
VALIDATION
SPECIFICATION
```

MangoMe separates the immutable internal `entity_id` from a human-declared id such as `AVCOS-OSEP-001`.

Declared IDs may collide. Both contributions remain present and the collision is surfaced rather than repaired by silent renaming.

Typed relations can express:

```text
ADDS_TO
AMENDS
EXTENDS
REPAIRS
RECOVERS
SUPERSEDES
CONFLICTS_WITH
RELATES_TO
```

## 5. Parallel work warns; it does not lock

MangoMe deliberately allows several agents to work in the same family.

Plans publish expected scope and artifacts. Overlap produces advisory traffic information:

```text
COLLISION_WARNING
family_overlap: true
artifact_overlap:
  - src/worker.py
other_actor_ids:
  - claude
action: CONTINUE_ALLOWED
```

The agent remains responsible for observing concurrent changes and adapting.

## 6. Project status is deterministic whenever possible

Routine questions such as these should not require an LLM:

- Which slice was started last?
- Which slices are active?
- Which slices are only `DONE_CLAIMED`?
- Which slices are verified?
- Which actors are currently active?
- Which declared contract IDs collide?
- Which approvals remain open?

MangoMe materializes state views from stored data. LLM reasoning is reserved for genuinely semantic ambiguity.

## 7. MangoMe stores state, not automatic recovery

MangoMe does not replay a failed worker or guess how to recover a dead session.

The next worker reads the persisted state, inspects the current artifacts, submits a new plan, and continues from the observed project position.

## 8. Big-Bang and incremental onboarding must both exist

MangoMe supports two complementary paths:

```text
BIG-BANG DISCOVERY
    existing estate → inventory → candidates → reconciliation

LIVE / INCREMENTAL INTAKE
    new work → resolve → register → plan → execute
```

The v0.1 scanner is non-destructive: it discovers and hashes artifacts and extracts cheap structural signals without moving, renaming, merging or deleting source files.

---

# What MangoMe tracks

The current document model includes:

```text
requests
projects
families
contracts
specs
slices
plans
claims
evidence
artifacts
edges
approvals
project_views
models
execution_receipts
```

Every persisted first-class document carries a `schema_version`.

MongoDB is the durable production document store. An in-memory backend is included for deterministic tests.

---

# Verification and acceptance

v0.1.1 separates implementation claims from assurance more strictly:

```text
ACTIVE
  ↓
DONE_CLAIMED
  ↓
acceptance gates + persisted evidence
  ↓
VERIFIED
  ↓
explicit acceptance decision
  ↓
ACCEPTED
```

Current integrity rules include:

- a `PASS` gate requires persisted evidence belonging to the same slice;
- failing evidence cannot support a `PASS` gate;
- a `WAIVED` gate requires an approved `WAIVE_GATE` decision;
- the last executing actor may not verify its own `DONE_CLAIMED` state;
- `VERIFIED` and `ACCEPTED` are distinct states.

> [!IMPORTANT]
> In v0.1.1, actor identities and approval identities are still supplied by the MCP host/caller. The domain protocol is enforced, but caller authentication is **not** yet a production trust boundary. See **Known limitations** below.

---

# Big-Bang discovery

`bigbang_scan` inventories configured filesystem roots and registers discovered artifacts without changing them.

The current deterministic extraction layer can detect contract-like IDs, explicit slice/phase/workstream headings, report/status filename signals and checksums.

Discovery does not equal truth:

```text
DISCOVERED ARTIFACT
       ↓
CONTRACT_CANDIDATE / WORK_STRUCTURE_CANDIDATE / REFERENCE_ONLY / UNRESOLVED
       ↓
explicit onboarding or later reconciliation
       ↓
CANONICAL MANGOME STATE
```

Ambiguous relationships should remain unresolved or suggested rather than being silently promoted by a model.

---

# Context compilation

MangoMe can emit a bounded current-state package for a family or slice:

```text
family identity
current materialized state
current specification
selected/current slice
relevant contract contributions
relevant evidence
```

This is intentionally a deterministic projection.

A downstream system such as **CogC** can then perform capacity-aware compression for a particular worker instead of retransmitting the full historical contract/session context every time.

---

# Model and execution economics

Execution receipts can record:

- agent and model identity;
- provider/access path;
- work class;
- raw and compiled context size;
- input/output tokens;
- execution cost;
- verification cost;
- repair cost;
- human cost;
- final outcome.

MangoMe calculates:

```text
durable_cost = execution + verification + repair + human
```

This creates a foundation for future empirical routing based on **cost per durable verified outcome**, rather than cost per token alone.

---

# Where MangoMe fits

MangoMe is not intended to replace an intake governor, context compiler, model router, Git, or an agent framework.

It is the shared persistent work-state layer between them.

```text
                         USER / REQUEST
                              │
                              ▼
                         IntakeGov
                  classify + resolve work type
                              │
                              ▼
                           MangoMe
              identity + state + slices + evidence
                    + contracts + provenance
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
             CogC         OmniRoute        Agent runtime
        compile context   route models   Claude/Codex/Luna
              │               │                │
              └───────────────┴────────────────┘
                              │
                              ▼
                     execution receipts
                              │
                              └──────────► MangoMe
```

A useful division of responsibilities is:

```text
IntakeGov = what kind of work is this?
MangoMe   = what durable work identity/state does it belong to?
CogC      = what context does this worker actually need?
OmniRoute = which execution path/model should handle it?
```

---

# MCP tools

v0.1.1 exposes the following groups.

```text
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
  set_gate
  set_gate_controlled
  verify_slice
  request_override
  approve_override
  reject_override
  list_approvals
  accept_slice

Read / context
  status
  read_context
  compile_execution_context
  graph

Economics
  register_model
  record_execution_receipt
  model_stats

Maintenance / discovery
  bigbang_scan
  refresh_views
```

---

# Installation

Python 3.10+ is required. The production backend uses MongoDB.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For local development without MongoDB:

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

The default MCP transport is stdio.

Streamable HTTP can be enabled with:

```bash
export MANGOME_MCP_TRANSPORT=streamable-http
export MANGOME_MCP_HOST=127.0.0.1
export MANGOME_MCP_PORT=8000
mangome-mcp
```

The root `server.py` exposes the MCP server for the official MCP CLI.

Current MCP Python SDK v2 syntax:

```bash
mcp dev server.py
mcp run server.py --transport streamable-http
```

The MCP Python SDK v2 is the current stable release line and supports Python 3.10+.

---

# MCP host configuration

Example stdio configuration:

```json
{
  "mcpServers": {
    "mangome": {
      "command": "/absolute/path/to/.venv/bin/mangome-mcp",
      "env": {
        "MANGOME_BACKEND": "mongo",
        "MANGOME_MONGODB_URI": "mongodb://127.0.0.1:27017",
        "MANGOME_DATABASE": "mangome"
      }
    }
  }
}
```

See [`examples/mcp-config.json`](examples/mcp-config.json).

---

# Agent Skill

The canonical skill lives at:

```text
skill/mangome/SKILL.md
```

A GitHub-discoverable mirror should exist at:

```text
.github/skills/mangome/SKILL.md
```

The distinction is deliberate:

```text
SKILL   = how an agent must work
MCP     = what the system knows and enforces
MongoDB = what durably survives
```

---

# Example lifecycle

```text
intake_request
      ↓
resolve / read_context
      ↓
create or select family + contract contribution
      ↓
create/select specification
      ↓
submit_plan
      ↓
inspect collision warning
      ↓
start_slice
      ↓
update_slice_progress + submit_evidence
      ↓
claim_done
      ↓
gate evaluation
      ↓
verify_slice
      ↓
optional human/owner acceptance
      ↓
record_execution_receipt
      ↓
status
```

A terminated model session does not erase the durable work state. The next worker reads MangoMe and creates its own plan from the persisted state and current artifacts.

---

# Known limitations in v0.1.1

MangoMe is executable, but these boundaries are intentionally not hidden:

1. **Caller identity is still declarative.** The MCP host/runtime must eventually provide trusted actor identity for production authorization and human approvals.
2. **Plan enforcement is strongest at slice start.** Subsequent execution mutations still need tighter actor/plan binding.
3. **Evidence semantics are still coarse.** Persisted evidence is required for `PASS`, but gate-specific evidence policies and evidence assurance classes are not yet complete.
4. **Contract contributions do not yet compile into a full effective-family view.** The graph exists; deterministic effective-spec composition is a next step.
5. **Big-Bang discovery is not yet full reconciliation.** Git history/branches/worktrees, configurable identifier grammars, richer parsers and semantic candidate reconciliation are planned.
6. **`schema_version` exists, but an explicit migration registry is not yet implemented.**
7. **Project-level rollups are still thinner than family-level state.** A deterministic multi-family project overview is a planned core addition.
8. **Streamable HTTP should not be exposed publicly without transport authentication and deployment-specific authorization.**

These are roadmap items, not claims of completed capability.

---

# Testing

The repository contains tests for:

- plan-before-mutate at slice start;
- `DONE_CLAIMED` vs `VERIFIED` separation;
- evidence-backed gate passing;
- approval-backed gate waivers;
- independent verification;
- explicit `VERIFIED → ACCEPTED` transition;
- advisory collision detection;
- last-started slice derivation;
- contract ID collision preservation;
- Big-Bang non-destructive discovery;
- context compilation;
- durable execution cost calculations;
- MongoDB persistence integration.

When `.github/workflows/ci.yml` is present, CI should run the test suite against Python 3.10–3.12 plus MongoDB 7 and verify the Agent Skill mirror.

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
│   ├── context.py
│   ├── importer.py
│   ├── integrity.py
│   ├── maintenance.py
│   ├── mcp_integrity.py
│   ├── mcp_server.py
│   ├── models.py
│   ├── runtime.py
│   ├── service.py
│   └── storage/
├── tests/
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── README.md
└── server.py
```

---

# Roadmap

## v0.1.x — integrity and operational truth

- [x] Contract families and append-only contributions
- [x] Persistent slices
- [x] Plan-before-start
- [x] Claims vs assurance state
- [x] Evidence-backed acceptance gates
- [x] Advisory collision warnings
- [x] Non-destructive Big-Bang discovery
- [x] Deterministic family status
- [x] Context compiler
- [x] Model/cost execution receipts
- [ ] Bind all execution mutations to an active actor plan
- [ ] Trusted human/owner approval boundary
- [ ] Evidence assurance classes and gate policies
- [ ] Deterministic project-level multi-family overview
- [ ] Effective-family specification compiled from contract contributions
- [ ] Typed/validated relation vocabulary and endpoint validation
- [ ] Explicit schema migration registry
- [ ] Optimistic revision/CAS protection for MangoMe internal state
- [ ] Stale-plan and stale-state maintenance

## Next — reconciliation and learning

- [ ] Configurable identifier grammars and parsers
- [ ] Git branch/history/worktree discovery
- [ ] Big-Bang candidate reconciliation
- [ ] External review packages for Claude / ChatGPT / Gemini
- [ ] Provider/model/version-aware execution receipts
- [ ] Cost-per-durable-verified-outcome routing feedback
- [ ] A/B/C replay evaluation for model and context strategies

---

# What MangoMe is not

MangoMe is not:

- another Jira/Scrum implementation;
- an agent framework;
- a replacement for Git;
- a generic vector memory;
- a model router;
- an automatic recovery/replay engine;
- a reason to trust worker completion claims;
- a license to block parallel agents because work overlaps.

It is the persistent **work identity + work state + evidence + provenance** layer that lets those systems cooperate without reconstructing project truth from scratch.

---

# Research and prior art

MangoMe is independently implemented and deliberately reuse-first in architecture.

Its design is informed by established concepts and systems including:

- MongoDB document storage and schema-versioning patterns;
- Model Context Protocol for provider-neutral agent tooling;
- OpenSpec-style specification/delta evolution;
- Beads/Gas Town-style persistent dependency-aware work structures;
- W3C PROV concepts for provenance;
- OpenTelemetry GenAI conventions for future telemetry alignment;
- CogC for downstream capacity-aware context compilation.

These are architectural references, not claims of affiliation.

See [`docs/research-foundations.md`](docs/research-foundations.md).

---

# The long-term goal

The goal is not merely to remember what an agent said.

The goal is for an agent organization to be able to answer, at any time and without reconstructing a lost session:

> **What are we building, which contracts define it, which slices exist, what is happening now, what has only been claimed, what has actually been verified, what evidence supports that state, who else is working nearby, and what should the next worker know before acting?**

That durable organizational state is MangoMe's job.

---

## License

Apache License 2.0.

See [`LICENSE`](LICENSE).

---

<p align="center">
  <strong>Read the state. Declare the plan. Execute freely. Persist the truth.</strong>
</p>
