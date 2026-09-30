# MAC/1 — MangoMe Agent Context Compiler

MangoMe v0.3.15 adds a native, deterministic worker-context projection. Its purpose is to reduce the amount of canonical state an agent must carry while preserving the normative material that can change the correct next action.

MAC/1 is not a second truth store and is not a copy of CogC. CogC remains an independent experimental context-compression project. MangoMe integrates only the relevant boundary logic because MangoMe already owns the canonical Contract generation, WorkIdentity, Specification, PCH residency, Evidence and truth state.

## Position in the stack

```text
Contract / Spec / Evidence / Truth in MongoDB
                ↓
             PCH/1
      task-relative residency
                ↓
             MAC/1
 capacity-aware worker projection
                ↓
             UAI/1
 optional compact transport
                ↓
             worker
```

The boundaries are:

```text
MangoMe = what is true / binding
PCH/1   = what is currently resident/relevant
MAC/1   = what this worker should see
UAI/1   = how a projection may be transported
worker  = reasoning and action inside existing authority
```

## Canonical Contract source

Routine worker context is built from the current canonical `contract_generations` document in MongoDB. MAC/1 does not open the local Contract file.

The local file remains useful as a human-readable artifact, recovery/audit representation and authorized promotion source. A changed local file is still only an observation until the normal Contract-generation promotion path makes it canonical.

For every resident Contract MAC/1 resolves `contract_heads.current_generation_id`, requires the referenced generation to exist and be `CANONICAL`, and verifies its stored `content_hash` against the stored text before compiling clauses.

The projection fails closed on a missing, non-canonical or hash-mismatched current generation. It does not repair or reconstruct canonical Contract truth from local files, chats, agent memory or a legacy database.

## Deterministic clause projection

Canonical Markdown is split deterministically by heading path, paragraph and list-item boundaries. A clause handle has the form:

```text
MC:<generation_id>:<ordinal>
```

Each clause carries provenance rather than a second identity model:

```text
contract_id
generation_id
generation
section_path
line_start
line_end
content_hash
criticality
normative_type
```

The Contract generation remains authoritative. Clause projection is disposable and can be regenerated from it.

## Criticality

v0.3.15 uses a small deterministic criticality model:

- `C0`: prohibitions, stop/authorization/security boundaries, MUST NOT / NEVER semantics;
- `C1`: mandatory requirements, constraints, acceptance criteria and required Evidence;
- `C2`: high-value objectives, Evidence/verification language and current task state;
- `C3`: supporting information.

Specification constraints and acceptance semantics enter with explicit criticality. Contract language is classified deterministically. A future richer classifier may replace the heuristic only behind evaluation gates; it must not be allowed to demote explicit canonical constraints silently.

C0/C1 material is never dropped merely to satisfy a worker token budget. If the critical set alone exceeds the configured worker capacity, the receipt sets:

```text
over_budget_due_to_critical = true
routing_signal = SPLIT_OR_ROUTE_LARGER_CONTEXT
```

The correct response is to split the task or use a larger context, not truncate normative truth.

## Metadata-only expansion handles

Optional clauses that do not fit remain addressable through `expandable_handles`.

Critically, an omitted handle contains only provenance metadata and a hash. It does **not** contain the omitted text. This prevents a compressed JSON payload from accidentally carrying the full source context anyway.

The full text remains externalized in the canonical Contract generation until narrowly needed.

## Capacity profiles

Built-in deterministic profiles are deployment hints only:

```text
generic-small-agent   4096 estimated tokens
qwen-4b               4096 estimated tokens
qwen-9b               8192 estimated tokens
frontier-specialist  16000 estimated tokens
```

Select with:

```text
MANGOME_AGENT_CONTEXT_PROFILE
```

Override the planning envelope with:

```text
MANGOME_AGENT_CONTEXT_TOKEN_BUDGET
```

Token counts are provider-neutral estimates, not claims about a provider tokenizer.

## Outer transport budget

`MANGOME_CONTEXT_MAX_BYTES` remains the hard ContextCompiler transport envelope. When that envelope is tighter than the MAC/1 package, MangoMe may fold optional MAC/1 facts behind metadata handles before removing old Evidence/detail. It never drops MAC/1 C0/C1 units. If mandatory state still does not fit, ContextCompiler fails closed with `ContextBudgetExceeded`.

## No authority transfer

MAC/1 may change representation and residency only. It cannot:

- create or modify Contract truth;
- create WorkIdentity;
- grant execution or verification authority;
- turn Evidence into assurance;
- change PCH temperature;
- mutate a Plan/Slice;
- infer owner approval;
- repair schema drift.

A smaller prompt is not a weaker governance boundary.
