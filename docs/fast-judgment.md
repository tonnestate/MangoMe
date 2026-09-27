# FJD/1 — Fast Judgment Decisions

MangoMe v0.3.3 includes a small provider-neutral fast-judgment protocol for repeated low-cost decisions such as classification, triage, routing, activation and prioritization.

FJD/1 does **not** include an inference model. It does not depend on Laya, does not vendor Laya source code, and does not copy its public API. The design adopts only a generic pattern that is useful for MangoMe: typed decision values, explicit confidence, and deterministic escalation when confidence is insufficient.

## Why this belongs in MangoMe

Large reasoning models are valuable for open-ended analysis, but many MangoMe operations repeatedly need small bounded judgments:

- Is this finding likely material?
- How relevant is this object to the current task?
- Which impact class best fits this observation?
- Which route should receive this request?
- Should this item be prioritized for revalidation?

Those are useful as **signals**, not as truth.

```text
state / object / finding
        ↓
external cheap classifier, heuristic, or small model
        ↓
BOOL / SCORE / CHOICE + confidence
        ↓
FJD/1 validation + gate
        ↓
USE_SIGNAL | REVIEW | ESCALATE
        ↓
normal MangoMe policy / evidence / assurance remains authoritative
```

## Typed decisions

FJD/1 supports three deliberately small primitives:

- `BOOL` — strict boolean value;
- `SCORE` — numeric value inside an explicitly declared range;
- `CHOICE` — one value from an explicitly declared option set.

Each decision also carries:

- a stable `name`;
- a `role` (`CLASSIFICATION`, `TRIAGE`, `ROUTING`, `ACTIVATION`, or `PRIORITIZATION`);
- a confidence in `[0,1]`;
- an inspectable disposition.

The default confidence thresholds are operational defaults, not scientific constants:

```text
confidence >= 0.80 → USE_SIGNAL
0.60 <= confidence < 0.80 → REVIEW
confidence < 0.60 → ESCALATE
```

Callers may set different thresholds. `high_impact=true` always produces `REVIEW_REQUIRED` even at high confidence.

## Epistemic boundary

Every FJD/1 result is explicitly:

```text
epistemic_role = WORKER_JUDGMENT
```

It may influence:

- classification;
- triage;
- routing;
- activation;
- prioritization.

It may **never** independently create:

- canonical truth;
- Evidence;
- assurance;
- verification;
- acceptance;
- mutation authority;
- normative promotion.

The hard rules are:

```text
CONFIDENCE != TRUTH
FAST_JUDGMENT != EVIDENCE
FAST_JUDGMENT != AUTHORITY
LOW_CONFIDENCE → ESCALATE
HIGH_IMPACT → REVIEW
```

## Persistence

`assess_fast_judgment` is transient and performs only validation/gating.

`record_fast_judgment` may persist an already produced result, but only when it is bound to an existing `WorkIdentity`. Persisted FJD/1 records are:

```text
persistence_level = PROGRESSIVE
epistemic_role = WORKER_JUDGMENT
```

They are useful for reproducible routing/activation history but never become canonical truth merely because they were stored.

## Provider neutrality

MangoMe deliberately does not prescribe the inference engine. A host may produce typed values with:

- deterministic heuristics;
- a small local classifier;
- a local embedding/classification model;
- a specialized decision model;
- a larger reasoning model as fallback.

This keeps MangoMe's decision semantics stable while the underlying inference implementation remains replaceable.

## Relationship to PCH/1 and SRA/1

FJD/1 is intentionally orthogonal to PCH/1 and SRA/1.

A fast relevance score may be used as an advisory PCH activation signal, and a fast materiality/impact classification may assist SRA/1 triage, but the deterministic PCH/SRA policies and MangoMe authority/evidence rules remain the governing layer.

FJD/1 therefore accelerates cheap judgment without turning probability into institutional truth.
