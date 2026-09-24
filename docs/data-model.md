# Canonical data model — schema v2

## Identity and concurrency

Every first-class object has immutable `entity_id`, `schema_version` and mutable `revision`. External IDs such as `AVCOS-OSEP-001` are `declared_id` values and are not unique identity keys.

`revision` is used for compare-and-swap state transitions so stale concurrent writes are rejected without locking project work.

## Primary collections

- `requests`: categorized assignments.
- `projects`: project-level aggregation roots.
- `families`: durable contract/work identities.
- `contracts`: append-only contract contributions.
- `specs`: append-only effective requirement versions.
- `slices`: durable execution units, plan binding, dependency requirements and gates.
- `plans`: declared execution intent, scope, artifacts and estimates.
- `claims`: worker assertions.
- `evidence`: typed observations with verdict and trust/attestation state.
- `artifacts`: physical/logical storage references.
- `edges`: validated typed graph relationships.
- `approvals`: requested/approved/rejected owner decisions.
- `project_views`: deterministic materialized family status projections.
- `models`, `execution_receipts`: execution economics.

## Execution and assurance

Execution and assurance remain orthogonal. `DONE_CLAIMED / UNVERIFIED` is a valid stable state.

Dependencies can explicitly require `DONE_CLAIMED`, `VERIFIED` or `ACCEPTED` from an upstream slice.
