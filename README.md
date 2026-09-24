# MangoMe

> **EXPERIMENTAL — v0.1.1**  
> MangoMe is an early multi-agent work-state MCP. The current release implements the core state machine, contract families, append-only contract contributions, specifications, plans, slices, claims, evidence, status projections, advisory collision detection, Big-Bang discovery, context compilation, and model/cost execution receipts. It is not yet a production authorization system or autonomous verifier.

**A persistent work graph and document-state machine for Claude, Codex, Luna and other agents.**

MangoMe exists for a practical failure mode in long-running AI projects: sessions die, workers forget state, contracts live in different places, every model invents its own project view, and `DONE` is frequently only a worker assertion.

MangoMe moves project truth out of the agent session.

```text
Request
  ↓
Intake / classification
  ↓
Contract family + append-only contributions
  ↓
Specification
  ↓
Mandatory plan + estimate
  ↓
Slices / dependencies / gates
  ↓
Execution state + claims + evidence
  ↓
DONE_CLAIMED ──not──> VERIFIED
  ↓                    ↑
Acceptance gates ──────┘
  ↓
Materialized project state
  ↓
Claude / Codex / Luna / dashboards / IntakeGov / CogC / OmniRoute
```

## Core rule

Workers are ephemeral executors, not sources of truth.

A worker may claim that work is complete. MangoMe records that as `DONE_CLAIMED`. Verification is a separate assurance state and requires the configured acceptance gates to pass.

## Why MangoMe is not another task manager

MangoMe joins several identities that are normally separate:

- the user request;
- a persistent contract family;
- append-only contract contributions;
- the currently effective specification;
- the agent's declared plan and estimate;
- persistent slices and their last known state;
- physical artifacts that may live in Git, root directories, web trees, reports, or other stores;
- evidence and verification state;
- active agents and advisory collision warnings;
- model/provider execution receipts and cost-per-verified-outcome data.

The same family can belong to several scopes, for example AVCOS, TonnEstate, Aurora and a WordPress admin surface, without duplicating the contract identity.

## Implemented in v0.1.0

### Persistent state

MongoDB is the production document store. Every document carries a `schema_version`. The Python domain layer can also run against an in-memory backend for tests.

Current collections:

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

### Contract families

Contracts are append-only contributions. A new contract never silently overwrites an old one. MangoMe separates its immutable internal `entity_id` from a human-declared contract id such as `AVCOS-OSEP-001`.

If two contributions use the same declared id, both survive and the family receives `DECLARED_ID_COLLISION`.

### Slices

Slices are first-class objects and survive agent sessions. Existing slice structures can be imported instead of being replanned.

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

This makes `DONE_CLAIMED / UNVERIFIED` a normal, stable state.

### v0.1.1 integrity layer

v0.1.1 keeps `DONE_CLAIMED` stable while tightening the assurance path:

- `PASS` gates require persisted evidence for the same slice;
- `WAIVED` gates require an approved `WAIVE_GATE` decision;
- the last executing actor cannot verify its own `DONE_CLAIMED`;
- `VERIFIED` and owner/human `ACCEPTED` are separate states;
- acceptance requires an approved `ACCEPT_SLICE` decision;
- plan closing, artifact registration, graph linking and approval lifecycle are exposed through MCP.

The approval records are an explicit state protocol, **not cryptographic authentication**. Caller identity still comes from the MCP host/runtime.

### Plan-before-mutate

All agents may read all MangoMe state. Productive slice execution requires a persisted plan associated with an intake request and a specification.

Plans can contain:

- intended slices;
- expected artifacts;
- affected scopes;
- acceptance expectations;
- effort, duration, cost and token estimates.

### Parallel agents

MangoMe does not lock project work. Overlap creates a warning, not inactivity.

```text
COLLISION_WARNING
family_overlap: true
artifact_overlap: [src/worker.py]
other_actor_ids: [claude]
action: CONTINUE_ALLOWED
```

The worker remains responsible for observing traffic and adapting its implementation.

### Deterministic project status

Family status is derived programmatically from stored slice state. A dashboard does not need an LLM to answer which slice was last started, which slices are active, which have only claimed completion, or which are verified.

### Big-Bang import

`bigbang_scan` non-destructively inventories configured filesystem roots and registers physical artifacts. It extracts cheap structural signals such as declared IDs and explicit slice/phase headings, but it does **not** automatically turn ambiguous files into canonical contracts.

The explicit `import_contract_bundle` operation can onboard an existing contract and its existing slices in one step.

### Context compiler

`compile_execution_context` returns a bounded current-state package for one family/slice. It is designed to feed IntakeGov/CogC rather than retransmitting an entire historic contract and session history to every worker.

### Model and cost ledger

Execution receipts can capture:

- agent and model identity;
- work class;
- input/output tokens;
- raw vs compiled context size;
- execution cost;
- verification cost;
- repair cost;
- human cost;
- outcome.

MangoMe calculates `durable_cost = execution + verification + repair + human` and can aggregate cost per verified outcome by model/work class.

## MCP tools

The v0.1.1 server exposes these tool groups:

```text
Intake / specs
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

Maintenance / import
  bigbang_scan
  refresh_views
```

## Install

Python 3.10+ and a MongoDB deployment are required for the production backend.

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

The default MCP transport is stdio. Streamable HTTP can be enabled with:

```bash
export MANGOME_MCP_TRANSPORT=streamable-http
export MANGOME_MCP_HOST=127.0.0.1
export MANGOME_MCP_PORT=8000
mangome-mcp
```

The repository also exposes a root `server.py`, so the official MCP CLI can run it after installation:

```bash
mcp dev server.py:mcp
mcp run server.py:mcp --transport streamable-http
```

## Agent Skill

The canonical skill is:

```text
skill/mangome/SKILL.md
```

A GitHub-discoverable mirror is included at:

```text
.github/skills/mangome/SKILL.md
```

The skill tells an agent *how it must work*. The MCP owns state and enforces domain invariants.

## Example lifecycle

```text
1. intake_request
2. resolve / create_family
3. register_contract (when a durable contract contribution exists)
4. create_spec
5. submit_plan
6. inspect returned collision warning
7. start_slice
8. update_slice_progress / submit_evidence
9. claim_done
10. set_gate
11. verify_slice
12. record_execution_receipt
13. status
```

A dead SSH tunnel, exhausted token budget, or terminated model session does not erase the state. The next worker reads MangoMe and creates a new plan from the persisted current state.

## What MangoMe deliberately does not do

- It does not treat every prompt as a contract.
- It does not block work because another agent is nearby.
- It does not replay or automatically recover a dead session; it stores state.
- It does not trust a worker's `DONE` statement as verification.
- It does not use an LLM for routine project-status calculation.
- It does not move, rename, merge or delete files during Big-Bang discovery.
- It does not require Git.
- It does not force Scrum, sprints or story points.

## ChatGPT / Claude reconciliation

Cross-provider reconciliation is intentionally a next-stage adapter, not part of v0.1 state truth. The intended pattern is to export a bounded MangoMe comparison package and let an external model produce a **suggestion** or review. It must never mutate canonical state directly. See `docs/external-reconciliation.md`.

## Repository layout

```text
.
├── src/mangome/             # domain service, MongoDB adapter, MCP server
├── skill/mangome/           # canonical Agent Skill
├── .github/skills/mangome/  # GitHub Agent Skill mirror
├── docs/
├── examples/
├── tests/
├── pyproject.toml
└── server.py
```

## Status

v0.1.1 is the first integrity-hardened executable baseline. The most important next integration work is IntakeGov → MangoMe intake, CogC → compiled execution context, OmniRoute → model/cost receipts, and deployment against the shared system-wide MongoDB instance.
