# Schema evolution

MangoMe uses explicit `schema_version` metadata plus revision-aware migrations. Readers can upgrade registered older document shapes in memory; persistence migration is explicit:

```bash
mangome migrate
mangome migrate --apply
```

The first command is a dry-run. The second persists registered migrations with compare-and-swap protection.

## Current schema — v6

Schema v6 adds Slice lifecycle fields for v0.3.10:

```text
validation_state
validation_at
validation_actor_id
validation_note
validation_completed_items[]
validation_open_deltas[]
validation_evidence_ids[]
closure_state
closed_at
closed_by
```

Historical `VERIFIED`/`ACCEPTED` Slices migrate compatibly to `VALIDATED + CLOSED`; MangoMe does not retroactively require a validator record that did not exist at the time. Historical `DONE_CLAIMED` Slices become `PENDING + OPEN`; other unfinished Slices remain `NOT_STARTED + OPEN`. Unknown fields are preserved.

PER/1 effects are new canonical documents and therefore require no fabricated historical rows. The `effects` collection is created/indexed when the runtime initializes.

## Schema v5

Schema v5 added v0.3 WorkIdentity bindings to plans/evidence/claims, including `work_id`, `turn_id` and `normative_baseline_id` where applicable.

## Schema v4

Schema v4 added Slice verification provenance fields:

```text
imported_assurance_state
verification_evidence_ids[]
verification_observation_ids[]
verification_profile
verified_by
```

The migration initializes missing fields only. It does not invent historical verification provenance or promote imported assurance. Earlier registered migrations preserve the v2 plan/evidence/approval integrity fields and the v3 UAI/execution-receipt transport telemetry.
