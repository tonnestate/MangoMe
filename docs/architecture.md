# MangoMe architecture v0.1

MangoMe separates three responsibilities:

```text
Skill   = how an agent must behave
MCP     = tools + invariants + canonical state transitions
MongoDB = durable document-state substrate
```

The core is intentionally not a generic agent framework. It can sit under Claude, Codex, Luna, AVCOS, TonnEstate, Aurora or another orchestrator.

## Truth model

MangoMe is the canonical operational state. Worker statements are stored as claims. Assurance is separate.

```text
Worker: "done"
  ↓
DONE_CLAIMED
  ↓
Gates + evidence
  ↓
VERIFIED / ACCEPTED
```

## Contract evolution

A family is long-lived. Contracts are append-only contributions. Internal entity identity never changes. Human-declared IDs may collide and remain queryable.

```text
Family
├── Base contribution
├── Addition
├── Amendment
├── Repair
└── Extension
```

Specs are append-only versions. The family points at the current effective spec while older spec documents remain present.

## Project management

MangoMe adopts useful project-management dimensions (scope, plan, slice, dependency, estimate, time, blocker, status) without requiring Scrum concepts. A slice is primarily a durable execution address.

## Concurrency

Parallel plans are allowed. Expected family/artifact/scope overlap creates warnings only. MongoDB's atomic document writes protect MangoMe's own state; project work itself is not locked.

## Context compilation

MangoMe can emit current family/spec/slice/evidence state as a compact package. CogC can then perform capacity-aware compression for a particular worker.
