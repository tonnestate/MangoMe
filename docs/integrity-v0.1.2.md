# MangoMe v0.1.2 — Integrity, authority and state safety

## Plan binding

`submit_plan` is not only a pre-flight record. `start_slice` binds the slice to one `active_plan_id`. `update_slice_progress` and `claim_done` must present the same actor and plan. A DONE claim clears `active_plan_id` while preserving `last_plan_id` as provenance.

## Evidence trust

Evidence is persisted as `UNATTESTED`. Verification-grade evidence must be attested using the verifier or owner runtime capability. PASS gates accept only admissible evidence classes with PASS verdict and trusted attestation.

This distinction prevents a worker assertion from becoming proof merely by being stored in the evidence collection.

## Runtime capabilities

Verifier and owner approval are separate capabilities:

```text
MANGOME_VERIFIER_TOKEN
MANGOME_APPROVAL_TOKEN
```

Optional actor allowlists:

```text
MANGOME_VERIFIER_ACTORS
MANGOME_APPROVER_ACTORS
```

Tokens are compared at runtime and never written to MongoDB, claims, evidence or approvals. They should be injected by the host/runtime, not included in prompts.

The CLI reads capabilities from environment for human/operator actions.

## Revision safety

All first-class documents now carry `revision`. Mutable state transitions use compare-and-swap to reject stale writes. This protects MangoMe's own state without locking external project work.

## Remaining trust boundary

Capability tokens are a pragmatic self-hosted control-plane boundary, not a complete IAM system. Internet-facing deployments should add transport-native identity/authentication and scoped authorization before exposure.
