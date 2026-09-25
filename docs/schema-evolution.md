# Schema evolution

MangoMe uses explicit `schema_version` metadata plus revision-aware migrations. Readers can upgrade registered older document shapes in memory; persistence migration is explicit:

```bash
mangome migrate
mangome migrate --apply
```

The first command is a dry-run. The second persists registered migrations with compare-and-swap protection.

## Current schema — v4

Schema v4 adds Slice fields used by the v0.1.8.1 integrity repair:

```text
imported_assurance_state
verification_evidence_ids[]
verification_observation_ids[]
verification_profile
verified_by
```

The migration initializes missing fields only. It does not invent historical verification provenance or promote imported assurance.

Earlier registered migrations preserve the v2 plan/evidence/approval integrity fields and the v3 UAI/execution-receipt transport telemetry.

Unknown fields are preserved; migrations do not destructively reinterpret semantic content.
