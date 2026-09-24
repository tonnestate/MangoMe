# Canonical data model

## Identity

Every first-class object receives an immutable MangoMe `entity_id`. External IDs such as `AVCOS-OSEP-001` are `declared_id` values and are not unique identity keys.

## Primary collections

`requests` stores categorized incoming assignments. `families` are durable work identities. `contracts` are append-only contract contributions. `specs` are append-only effective requirement versions. `slices` represent durable execution units. `plans` record what an agent intends to do before mutation. `claims` record worker assertions. `evidence` records supporting observations. `artifacts` map logical entities to physical storage. `edges` hold typed graph relationships. `project_views` are deterministic materialized status views. `models` and `execution_receipts` hold empirical execution economics.

Every persisted document contains `schema_version` to support lazy schema evolution.
