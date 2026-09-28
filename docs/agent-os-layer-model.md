# Agent-OS Layer Model — v0.3.10

MangoMe v0.3.10 makes the existing control boundaries explicit without turning every layer into an LLM.

```text
DOMAIN / INTENT
    what should be achieved?
        ↓
WORK / SLICE EXECUTION
    what bounded unit is being worked?
        ↓
VALIDATION
    was the claimed implementation scope actually completed?
        ↓
INDEPENDENT VERIFICATION
    is the result independently demonstrated?
        ↓
EFFECT / RECONCILIATION
    does observed external reality match durable intent?
        ↓
DETERMINISTIC ENFORCEMENT
    which state transitions and authorities are permitted?
```

## Kernel rule

> Agents reason. The kernel enforces. The ledger remembers.

A human, deterministic component, or specialized agent may later inhabit a cognitive layer. Selection for a layer never grants that layer's authority automatically. WorkTurn, capability, verifier, owner, revision-CAS and normative-baseline boundaries remain deterministic.

## Slice lifecycle

```text
ACTIVE
  ↓ worker
DONE_CLAIMED
  ↓ validator
  ├─ REWORK_REQUIRED → ACTIVE → DONE_CLAIMED
  ├─ INCONCLUSIVE    → OPEN
  └─ VALIDATED
         ↓ independent verifier
      VERIFIED
         ↓ required effects reconciled + satisfied
       CLOSED
         ↓ optional owner/business decision
      ACCEPTED
```

The important separation is:

```text
WORKER_COMPLETION != SLICE_COMPLETION
```

`DONE_CLAIMED` is an execution claim. `VALIDATED` means the claimed scope has no known implementation delta. `VERIFIED` is independent assurance. `CLOSED` is the terminal operational Slice state. `ACCEPTED` remains the separate owner/business decision already present in MangoMe.

A Slice may intentionally be `VERIFIED + OPEN` while a required external effect remains unresolved.

## Dependency levels

A downstream Slice can depend on the weakest sufficient predecessor state:

```text
DONE_CLAIMED
VALIDATED
VERIFIED
CLOSED
ACCEPTED
```

This avoids forcing business acceptance where only operational closure is needed, while allowing safety-critical dependencies to require more than a worker completion claim.

## Why this is a layer model, not an agent taxonomy

The layers define responsibility, authority and state transitions. They do not prescribe one model per layer. A later control-plane repository can assign specialized agents to Observation, Planning, Validation, Verification, Reconciliation or Scheduling without changing MangoMe's truth semantics.

This follows the same useful separation visible in agentic OS work such as SchedCP: semantic reasoning belongs in a control plane, while safety-critical execution remains inside a bounded deterministic mechanism. MangoMe applies that principle to durable work, truth and external effects rather than CPU scheduling.

## OS analogy boundary

MangoMe is not a Linux kernel module and does not claim CPU ring-0 privilege. The analogy is architectural:

- Linux governs machine resources and syscalls.
- MangoMe governs work identity, authority, truth mutation, assurance and recoverable effects.
- AVCOS or another orchestrator may schedule cognitive workers above MangoMe.
- Host/container/kernel mechanisms may later enforce MangoMe capabilities physically.

The semantic kernel and machine kernel therefore remain separate and composable.
