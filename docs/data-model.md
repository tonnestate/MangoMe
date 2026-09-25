# Canonical data model — schema v4

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
- `filesystem_entries` / `filesystem_roots` — deterministic observable workspace inventory

Every persisted document carries `schema_version`; mutable first-class documents carry `revision` for compare-and-swap protection.

## Schema v4 additions

v0.1.8.1 adds explicit fields to `Slice` for import trust and final verification provenance:

```text
imported_assurance_state
verification_evidence_ids[]
verification_observation_ids[]
verification_profile
verified_by
```

Imported historical assurance is never authoritative on admission. A newly imported Slice starts `UNVERIFIED`; the supplied historical assurance value is retained in `imported_assurance_state` for auditability.

When a Slice reaches `VERIFIED`, the verifier identity and exact Evidence/AV/1 observation ids that authorized the transition are written in the same revision-guarded Slice update as the assurance state. Secondary Claims and materialized views remain reconstructible/auditable projections rather than the sole location of verification provenance.

Historical pre-v4 verified Slices are not rewritten with invented provenance. `maintenance_diagnose` reports those gaps for explicit revalidation when needed.

## Derived truth level

`truth_level` is a deterministic output projection, not another persisted lifecycle. It prevents clients from flattening execution and assurance into a single “done” concept:

```text
CANONICAL_UNVERIFIED
CLAIMED
PARTIAL_VERIFIED
VERIFIED
ACCEPTED
REJECTED
```

Discovery has its own explicit `CANDIDATE` / `CANDIDATE_ONLY` boundary and does not enter this canonical projection merely by being observed.

## Schema v3 transport additions

Execution receipts can record the transport layer independently from raw/compiled context:

```text
context_tokens_raw
context_tokens_compiled
context_tokens_interlingua
output_tokens_interlingua
interlingua_version
```

This supports empirical RAW vs compiled vs UAI/1 comparisons by model/work class and verified outcome.

UAI/1 context packets themselves are not canonical documents and are not persisted as a new truth collection. They are disposable projections generated from current canonical state.
