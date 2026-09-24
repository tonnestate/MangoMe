# MangoMe architecture v0.1.2

MangoMe separates four responsibilities:

```text
Skill        = how an agent must behave
MCP          = provider-neutral tools and state transitions
Domain Core  = identity, plans, slices, evidence, assurance, projections
MongoDB      = durable document-state substrate
```

## Truth model

```text
worker execution
   ↓
claim / evidence
   ↓
DONE_CLAIMED
   ↓
attested proof + gates
   ↓
VERIFIED
   ↓
optional owner approval
   ↓
ACCEPTED
```

Execution and assurance are deliberately orthogonal.

## Work identity

Project → Family → Contract Contributions / Specs / Slices is the durable hierarchy. Physical files, repositories and sessions are storage/execution references, not identity.

Families may belong to multiple projects/scopes without duplication.

## Contract evolution

Contract contributions are append-only. Typed relations express evolution. Confirmed `SUPERSEDES` removes the target from the effective contribution set; conflicts remain visible. The current Specification is the operational effective requirements view.

## Planning and concurrency

A persisted plan precedes productive mutation. Starting a slice binds it to `active_plan_id`; progress/DONE must remain on that binding.

Parallel plans remain allowed. Overlap creates advisory collision warnings only.

## Assurance authority

Evidence is un-attested by default. Verifier/owner authority is separated from worker execution using runtime roles or capability tokens. Direct database access remains outside the trust boundary.

## State concurrency

All first-class documents carry `revision`. State transitions use compare-and-swap so concurrent stale writers fail explicitly instead of silently overwriting newer MangoMe state.

## Import

Big-Bang discovery inventories filesystem and optional Git state. Reconciliation matches candidates against canonical identity but never auto-admits ambiguous semantic truth.

## Context

MangoMe emits deterministic current-state packages. CogC or another downstream compiler may then compress/shape that package for a target worker.
