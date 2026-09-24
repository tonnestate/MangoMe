# Canonical data model — schema v3

## Identity

Every first-class object receives an immutable MangoMe `entity_id`. External/human IDs remain declared identifiers and are not canonical identity keys.

## Primary collections

- `requests` — categorized assignments
- `projects` — project containers
- `families` — durable work/contract identities
- `contracts` — append-only contract contributions
- `specs` — append-only requirement/spec versions
- `slices` — durable execution units with independent execution/assurance state
- `plans` — declared execution intent before mutation
- `claims` — worker assertions
- `evidence` — observations with class, verdict and trust/attestation
- `artifacts` — physical/logical artifact references
- `edges` — typed graph relationships
- `approvals` — explicit owner/authority decisions
- `project_views` — deterministic materialized family status
- `models` — model/access-path profiles
- `execution_receipts` — token/cost/outcome telemetry

Every persisted document carries `schema_version` and mutable first-class documents carry `revision` for compare-and-swap protection.

## Schema v3 additions

Execution receipts can record the transport layer independently from raw/compiled context:

```text
context_tokens_raw
context_tokens_compiled
context_tokens_interlingua
output_tokens_interlingua
interlingua_version
```

This supports empirical RAW vs compiled vs UAI/1 comparisons by model/work class and verified outcome.

UAI/1 context packets themselves are not canonical documents and are not persisted as a new truth collection. They are disposable projections generated from the current state.
