# SRA/1 — Scoped Recursive Audit and Impact Closure

MangoMe v0.3.2 adds a bounded recursive audit layer for the common case in which a worker receives a local assignment, understands only part of a larger system, and must proceed without silently turning local knowledge into a global correctness claim.

The governing principle is:

> **Local competence, explicit assumptions, bounded authority, global traceability.**

SRA/1 does not require a worker to understand the entire system before beginning. It requires the worker to state and preserve the boundary of what it inspected, what it assumed, what it does not know, what it may mutate, and what it may legitimately claim about the result.

## Why recursive audit is bounded

Naive audit strategies fail in two opposite directions:

```text
inspect only the originally named file
→ miss downstream impact
```

or:

```text
inspect the entire system every time
→ unbounded cost and no practical completion condition
```

SRA/1 instead expands scope only when an observation identifies material impact:

```text
initial scope S0
      ↓
inspect current frontier
      ↓
persist finding / evidence
      ↓
material impact?
   no ───────→ frontier shrinks
   yes
    ↓
follow allowed confirmed relations
    ↓
Sn+1 = Sn ∪ Impact(ΔSn)
    ↓
repeat until no pending frontier remains
```

A normal closure reaches:

```text
S(n+1) = Sn
```

which SRA/1 reports as `FIXPOINT_REACHED`.

If the configured depth or object budget prevents further traversal, the audit reaches `BOUNDED_FIXPOINT`. That is a valid bounded result, but it is explicitly not a whole-system correctness claim.

## Four different boundaries

SRA/1 keeps four boundaries distinct.

### Knowledge boundary

The worker knows only the current audit scope, persisted findings/evidence, explicit assumptions, and discovered frontier. Missing knowledge is represented as an unknown, not silently filled in.

### Inspection boundary

Inspection may expand along the configured graph relations when a finding uses `impact=EXPAND`.

### Mutation boundary

Mutation authority is frozen when the audit starts. Recursive inspection **never** recursively grants mutation authority.

```text
inspection scope expands
        ≠
mutation scope expands
```

A `READ_ONLY` audit has no mutation scope. `REPAIR_WITHIN_SCOPE` may name an explicit mutation subset, but actual changes still require the normal MangoMe Plan/WorkTurn and host/runtime permissions.

### Assurance boundary

An audit finding is scoped evidence about what was inspected. Closing an audit means that the configured impact frontier was exhausted or bounded. It does not promote the underlying Slice, Artifact, Ticket, or system to `VERIFIED`.

```text
AUDIT CLOSED
    ≠
SYSTEM VERIFIED
```

## Audit kinds

SRA/1 uses one engine for common audit intents:

```text
CLASSIFICATION
ARCHITECTURE
ARTIFACT
CODE_REVIEW
INCIDENT
RECONCILIATION
IMPACT
SECURITY
GENERAL
```

The audit kind is descriptive. The trust model and scope rules remain the same.

## Findings and impact

A finding has one of these classes:

```text
NO_ISSUE
INFO
ISSUE
CONFLICT
ASSUMPTION
UNKNOWN
```

and one impact mode:

```text
NONE
LOCAL
EXPAND
OUTSIDE_SCOPE
```

`EXPAND` permits one bounded graph-frontier step. `OUTSIDE_SCOPE` records the dependency/impact but does not absorb it into the current audit automatically.

Findings may also record:

- Evidence IDs;
- assumptions;
- unknowns;
- explicitly affected MangoMe entity IDs;
- external references such as repository paths, tickets, services, or APIs.

## Relationship to PCH/1

SRA/1 and PCH/1 solve different problems.

```text
SRA/1
What must be inspected next to close material impact?

PCH/1
What should be cognitively resident for the current task?
```

The active audit frontier is passed to PCH/1 as additional roots where those objects are present in the MangoMe graph. This makes the current impact frontier HOT without turning audit priority into truth or assurance.

## Relationship to AV/1

AV/1 remains the completion-verification mechanism for a Slice. SRA/1 is a broader inspection/impact mechanism.

A common path is:

```text
Ticket / Slice / Artifact
        ↓
SRA/1 scoped audit
        ↓
findings + bounded impact closure
        ↓
optional authorized repair
        ↓
AV/1 completion review / independent observation
        ↓
VERIFIED
```

Neither SRA/1 nor PCH/1 bypasses AV/1.

## MCP lifecycle

```text
start_scoped_audit
    ↓
audit_context / audit_status
    ↓
inspect real target
    ↓
record_audit_finding
    ↓
impact=EXPAND ? add bounded frontier : continue
    ↓
no pending frontier
    ↓
close_scoped_audit
```

Use `audit_mutation_allowed` before an audit-driven repair decision. A positive result only confirms the SRA/1 boundary; it does not replace the normal execution Plan, WorkTurn, filesystem permissions, or other host controls.

## Non-goals

SRA/1 does not:

- recursively verify verifiers forever;
- inspect the entire host by default;
- infer global correctness from local closure;
- create mutation authority by discovering dependencies;
- treat an LLM finding as verified truth;
- replace AV/1 verification;
- implement bitemporal truth maintenance;
- execute external code or tests itself.

The next temporal-truth layer can later use SRA/1 findings and impact edges as inputs, but audit closure and truth maintenance remain separate concepts.
