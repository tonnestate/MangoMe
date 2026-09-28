# PER/1 — Persistent Effect Reconciliation

External systems do not share a single ACID transaction with MangoMe. Git, filesystems, deployment targets, APIs, mail systems and databases may acknowledge late, partially succeed, time out after success, or offer no rollback at all.

v0.3.10 therefore does not claim global side-effect atomizität. It provides **recoverable side-effect semantics**.

## Core invariant

> Every governed external effect is either reconciled or durably recoverable.

For every relevant external effect:

```text
WorkIdentity
    ↓
Slice
    ↓
WorkTurn / authority
    ↓
Effect intent persisted
    ↓
AUTHORIZED
    ↓
DISPATCHED
    ↓
OBSERVED
    ↓
RECONCILED
```

Intent is durable before dispatch. Success is not inferred from intent, a tool call, or a missing exception.

## Effect identity

Each logical effect has a stable `effect_key` within its Slice. Reusing that key with the same action, target and payload hash is idempotent at the MangoMe ledger boundary. Reusing it for a different logical effect is rejected.

The record can also carry a provider-native `idempotency_key`. MangoMe does not pretend that every external provider supports one.

## Outcome semantics

Observation outcomes are explicit:

```text
UNKNOWN
CONFIRMED
FAILED
PARTIAL
NOT_EXECUTED
```

A timeout or lost response is normally `UNKNOWN`, not `FAILED`.

After `UNKNOWN`, `PARTIAL` or `CONFIRMED`, MangoMe rejects blind redispatch. The external state must be observed/reconciled first. Redispatch becomes eligible only after observation establishes known non-execution (`FAILED` or `NOT_EXECUTED`).

## Reconciliation

`RECONCILED` means the durable intent has been compared with observed external reality. The additional `satisfied` field states whether the intended external condition currently holds.

Therefore these are different:

```text
RECONCILED + satisfied=true
RECONCILED + satisfied=false
```

The second case is a known unresolved delta, not missing history.

## Slice closure

A required effect blocks `CLOSED` unless:

```text
state == RECONCILED
AND
satisfied == true
```

This deliberately permits:

```text
DONE_CLAIMED
VALIDATED
VERIFIED
OPEN
```

when the implementation is independently verified but the outside world is not yet reconciled.

After the effect is reconciled and satisfied, the verifier can close the already verified Slice without re-running execution.

## Recovery strategies

MangoMe records the external recovery class but does not require every effect to be reversible:

```text
REVERSIBLE
COMPENSATABLE
RECONCILABLE
IRREVERSIBLE
```

Examples:

- deleting a newly created resource may be reversible;
- rolling back a deployment may be compensatable;
- an API write may only be reconciliable;
- a sent external message may be irreversible and require a corrective follow-up rather than an undo.

## Crash recovery

Worker or session death does not erase an open effect. Work views and recovery context expose unresolved effect records so the next coordinator inspects the bounded delta rather than reconstructing history from logs or repeating the action.

This is a journal/reconciliation guarantee, not a claim of cross-storage atomicity.
