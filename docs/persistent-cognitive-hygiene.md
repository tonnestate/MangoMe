# Persistent Cognitive Hygiene — PCH/1

MangoMe v0.3.1 adds a deterministic, non-destructive cognitive-homeostasis layer over canonical persisted work state.

## Purpose

Persistent memory alone is not sufficient for persistent intelligence. A long-running system can preserve correct history while degrading operationally if obsolete, duplicated, superseded, conflicting, or merely irrelevant state remains equally active.

PCH/1 therefore separates:

```text
historical state H_t
active organizational state A_t
worker context C_t
```

with the intended relationship:

```text
H_t remains historically recoverable
|A_t| <= B_active
|C_t| <= B_context
```

The active-state budget and the context byte budget are deliberately separate controls.

## Placement

PCH/1 is not another memory database and not another compiler.

```text
MongoDB canonical history / MangoMe graph
        ↓
PCH/1 CognitiveHygieneService
        ↓
bounded active working set
        ↓
existing ContextCompiler
        ↓
UAI/1 or normal worker context
```

The ContextCompiler remains responsible for transport/context reduction. PCH/1 decides what should be resident before compilation.

## Temperature

Each candidate object receives a continuous task-relative temperature:

```text
T(x | q, state) ∈ [0, 1]
```

v0.3.1 uses inspectable deterministic signals:

- graph proximity to pinned execution roots;
- lexical/task relevance;
- operational authority/currentness;
- freshness/validity markers;
- epistemic support for Evidence;
- conflict attention boost;
- supersession penalty;
- representation cost.

The initial bands are:

```text
HOT   >= 0.72
WARM  >= 0.38 and < 0.72
COLD  < 0.38
```

These thresholds are an evaluation baseline, not a claim of optimality.

## GC analogy

PCH/1 deliberately borrows several ideas from garbage collectors and memory managers:

- canonical/current execution objects act as roots;
- graph traversal approximates reachability/locality;
- HOT/WARM/COLD are exposed as generation labels 0/1/2;
- an active-object budget creates residency pressure;
- pinned roots cannot be evicted merely to satisfy that budget.

The analogy stops at deletion. MangoMe does not destructively collect historical truth. In PCH/1:

```text
COLD == non-resident
COLD != deleted
```

Historical state remains queryable by provenance.

## Supersession and reheating

Superseded state loses default operational authority and normally cools. It is not erased. A task explicitly targeting historical behavior can increase its temperature and bring it back into the working set for inspection or revalidation.

Reheating does not restore normative authority.

## Safety invariants

```text
temperature != truth
temperature != assurance
temperature != authority
COLD != deleted
working-set eviction != canonical mutation
```

PCH/1 must not:

- verify or accept work;
- rewrite a Contract, Specification, NormativeBaseline, Claim or Evidence record;
- infer correctness from temperature;
- create a second canonical graph;
- destroy historical provenance.

## MCP surface

`cognitive_hygiene` returns the full diagnostic thermal map, including:

- temperature;
- HOT/WARM/COLD band;
- generation 0/1/2;
- graph distance;
- pinned status/reasons;
- component signals;
- residency decision;
- active-budget outcome.

Normal execution uses the same policy through `ContextCompiler`, but only the compact working-set summary enters the worker projection.

## Current limits

PCH/1 is intentionally a minimal deterministic baseline. It does not yet implement:

- general assumption-based truth maintenance;
- bitemporal `valid_time` / `transaction_time` semantics;
- learned activation weights;
- explicit hysteresis/residency time across calls;
- host-wide cross-project graph navigation;
- semantic consolidation from episodic to reusable procedural knowledge.

Those are separable research/implementation steps and should not be conflated with the v0.3.1 working-set primitive.
