# Structural Intelligence — MangoMe v0.3.12

MangoMe v0.3.11 introduced bounded structural sight; v0.3.12 hardens its parser bridge without creating a second truth system. Structural information is derived workspace observation only. It is never Contract truth, Evidence, Assurance, authority, WorkIdentity, or a normative baseline.

## Invariants

- `MAP != TRUTH`
- `MAP != EVIDENCE`
- `MAP != ASSURANCE`
- `MAP != AUTHORITY`
- `MAP != NORMATIVE BASELINE`
- `MAP != WORK IDENTITY`
- Bootstrap and ordinary status calls perform no repository scan.
- Structural indexing is lazy and starts only from an explicit structural/context/audit request.
- Structural failures return `STRUCTURAL_CONTEXT_UNAVAILABLE` and do not stop ordinary cognition.
- Impact expansion widens inspection candidates only; it never widens mutation authority.
- All structural results are revision-bound and carry provenance/confidence metadata.

## Implementation

`src/mangome/structural.py` provides six bounded operations:

- `structural_status`
- `structural_search`
- `symbol_lookup`
- `symbol_relations`
- `structural_context`
- `impact_frontier`

The implementation reuses RepoMap principles rather than absorbing Aider as an application: definitions/references, a dependency graph, centrality, task-conditioned ranking, incremental caching, and bounded rendering. Python uses the standard AST. Other supported programming languages use Tree-sitter through `tree-sitter-language-pack`. v0.3.12 adapts both observed Python binding shapes (`type` vs `kind`, str vs bytes parser input, alternate byte/position fields) and can fall back to the standalone `tree_sitter` binding. If parsing is unavailable or fails, MangoMe falls back to a bounded text parser and marks the observation partial. Parser/grammar work therefore cannot become a global MangoMe blocker.

The cache is process-local and disposable. File signatures are used for incremental refresh; a structural revision changes when the observed workspace changes. Canonical MangoMe state is not written by the structural subsystem.

## PCH, SRA, and ContextCompiler bridge

The normal worker facade enriches `COGNITIVE_HYGIENE` responses with a separate structural-relevance projection. The canonical PCH/1 thermal calculation remains deterministic and unchanged; a worker may use the structural projection to choose the next bounded inspection, but it does not silently rewrite PCH temperature, supportability, truth, or assurance.

`COMPILE_CONTEXT` first compiles canonical MangoMe execution context. Structural context is optional and is removed before canonical context if a transport budget would otherwise be exceeded. A `ContextBudgetExceeded` condition degrades to a minimal viable context before returning `CONTEXT_UNAVAILABLE`.

A `START_SCOPED_AUDIT` response may include `structural_impact_candidates`. They are advisory inspection candidates returned beside SRA/1 state; they do not silently mutate the persisted SRA frontier and never expand the audit mutation boundary.

## Operational boundary

The structural layer performs no LLM calls. It does not discover or admit WorkIdentity, does not restore canonical state, does not create Families/Specifications/Contracts, and does not issue verification or approval decisions.
