# MangoMe architecture v0.1.3

MangoMe separates durable truth, execution representation, worker capacity and ephemeral execution.

```text
IntakeGov (optional routing / proportional governance)
        |
        v
MangoMe canonical operational memory
  - MongoDB document store
  - contract/work graph
  - state machine
  - evidence/provenance
  - execution economics
        |
        v
ContextCompiler
bounded execution semantics
        |
        v
UAI/1
compact, versioned, hash-bound semantic transport
        |
        v
CogC (optional)
worker-capacity-aware shaping
        |
        v
Claude / Codex / Luna / other MCP workers
        |
        v
UAI/1R structured result
        |
        +--> deterministic human rendering
        |
        +--> normal MangoMe mutation/evidence/verification tools
```

## Storage contract

Production canonical persistence is MongoDB. The in-memory store exists for tests/dev and is not a second production truth contract.

## Truth model

Workers emit claims and proposals. MangoMe stores and derives operational state. Assurance remains separate from execution.

```text
DONE_CLAIMED != VERIFIED != ACCEPTED
```

## Contract evolution

A family is long-lived and contract contributions are append-only. Typed graph relations express evolution. Confirmed `SUPERSEDES` affects the effective contribution set; conflicts remain explicit.

## Concurrency

Project work is not globally locked. Overlap creates advisory warnings. MangoMe's own mutable documents use revision / compare-and-swap semantics.

## Context transport

The canonical database is intentionally rich. UAI/1 exists so expensive workers do not need the same verbosity. Its semantic projection is disposable and can always be regenerated from MangoMe.

## Product boundary

MangoMe v0.1.x is intentionally a single canonical deployment serving many projects/agents/models/humans. Cross-organization federation and interchangeable production stores are outside current scope.
