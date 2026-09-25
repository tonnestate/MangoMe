# Reconciliation Reasoning

MangoMe separates persistent truth from non-deterministic agent judgment.

The core principle is:

> **Externalize state. Localize uncertainty. Preserve agency. Verify independently.**

The corresponding worker rule is:

> **Do not constrain reasoning. Constrain truth mutation.**

## The model

For bounded work, MangoMe distinguishes:

```text
N = normative truth
    What must be true?
    Effective specification, acceptance criteria, constraints, policy and scope.

O = observed truth
    What is actually present or observed?
    Artifacts, paths, digests, revisions, runtime state, tests and Evidence.

X = explored context
    Additional context selected by the worker when the bounded view is insufficient.

J = f(N_scope, O_scope, X)
    The worker's non-deterministic judgment about the delta between N and O.
```

`O` is truth about observed state, not a claim of correctness. A present artifact can be wrong. An absent artifact is also a valid observed state. The worker should not spend model context rediscovering state MangoMe already records authoritatively.

## Why this is different from a rigid reconciliation controller

Classic reconciliation loops can often compare desired and observed state mechanically. MangoMe applies the same separation of desired/normative and observed state to work where the comparison itself can require semantic judgment.

The system therefore externalizes the facts but deliberately leaves the unresolved judgment to the worker:

```text
authoritative normative state
          +
authoritative observed state
          ↓
non-deterministic worker judgment
          ↓
plan-bound action
          ↓
new observed state
          ↓
independent assurance
```

MangoMe does not attempt to make the worker deterministic. It makes the state over which the worker reasons durable, inspectable and independently verifiable.

## Minimum sufficient context, not minimum possible context

The starting view should contain the smallest sufficient projection of `N` and `O` for the current task. This reduces context dilution and repeated reconstruction.

Scope is not a cognitive prison. The worker may expand `X` on demand by reading graph neighbors, dependencies, related requirements, artifacts, tests, Evidence or history when responsible judgment requires it. This avoids the opposite failure mode: context starvation.

## Agent freedom

Within an admitted plan and scope, the worker remains free to:

- inspect and explore;
- implement and refactor;
- test and diagnose;
- criticize an existing implementation;
- identify improvements beyond bare mechanical compliance;
- request more context;
- propose changes to the governing contract.

The worker is constrained at truth mutation boundaries, not at thought boundaries. It may not silently:

- reinterpret an effective requirement as changed;
- invent an observed artifact or state;
- turn its own claim into `VERIFIED`;
- treat its own Evidence as independent observation of the same completion claim;
- overwrite effective normative truth through prose or memory.

If the worker believes normative truth should change, it uses the existing append-only contract-evolution path and leaves the proposal non-effective until the authorized process makes it effective. No new amendment entity or parallel state machine is required.

## Relationship to existing MangoMe primitives

This doctrine intentionally reuses the existing model:

- effective Specification / contract family -> normative truth;
- Artifact, filesystem inventory, runtime state and Evidence -> observed truth;
- ContextCompiler / UAI/1 -> bounded representation;
- Graph -> targeted expansion and traceability, not a replacement truth store;
- AV/1 + RB/1 + policy/authority/freshness/revision checks -> independent assurance;
- existing assurance states remain unchanged.

There is no second truth store, no new graph engine, and no additional verification-state taxonomy.

## Research hypothesis

The token-efficiency claim is a hypothesis to measure, not a guaranteed product result. A suitable ablation compares a normal history/repository-exploration agent against an agent receiving externalized `N/O` state and explicit reconciliation reasoning. Useful measures include:

- False-DONE rate;
- first-attempt verification rate;
- task success;
- tokens spent reconstructing known state;
- tool calls used to rediscover known facts;
- time/tokens until first useful action;
- scope deviations;
- cost per verified slice.

The protocol claim remains narrower: durable state is externalized, worker agency is preserved, and final verification remains independent.

## Recovery boundary

Reconciliation reasoning assumes that admitted work identity and current state come from MangoMe, not from path archaeology after session loss. See [`authoritative-recovery.md`](authoritative-recovery.md). Context expansion `X` remains agent-controlled, but it is used to judge or validate a bounded delta; it must not become a second mechanism for reconstructing which admitted work exists or what state it is in.
